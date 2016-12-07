#!/usr/bin/env python3.4
#
# Copyright 2016 Google Inc.
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Interface for a USB-connected Monsoon power meter
(http://msoon.com/LabEquipment/PowerMonitor/).
"""

import fcntl
import logging
import os
import select
import struct
import sys
import time
import collections

# http://pyserial.sourceforge.net/
# On ubuntu, apt-get install python3-pyserial
import serial

import mobly.signals

from mobly import utils
from mobly.controllers import android_device

MOBLY_CONTROLLER_CONFIG_NAME = "Monsoon"


def create(configs):
    objs = []
    for c in configs:
        objs.append(Monsoon(serial=c))
    return objs


def destroy(objs):
    return


class MonsoonError(mobly.signals.ControllerError):
    """Raised for exceptions encountered in monsoon lib."""


class MonsoonProxy(object):
    """Class that directly talks to monsoon over serial.

    Provides a simple class to use the power meter, e.g.
    mon = monsoon.Monsoon()
    mon.SetVoltage(3.7)
    mon.StartDataCollection()
    mydata = []
    while len(mydata) < 1000:
        mydata.extend(mon.CollectData())
    mon.StopDataCollection()
    """

    def __init__(self, device=None, serialno=None, wait=1):
        """Establish a connection to a Monsoon.

        By default, opens the first available port, waiting if none are ready.
        A particular port can be specified with "device", or a particular
        Monsoon can be specified with "serialno" (using the number printed on
        its back). With wait=0, IOError is thrown if a device is not
        immediately available.
        """
        self._coarse_ref = self._fine_ref = self._coarse_zero = 0
        self._fine_zero = self._coarse_scale = self._fine_scale = 0
        self._last_seq = 0
        self.start_voltage = 0
        self.serial = serialno

        if device:
            self.ser = serial.Serial(device, timeout=1)
            return
        # Try all devices connected through USB virtual serial ports until we
        # find one we can use.
        while True:
            for dev in os.listdir("/dev"):
                prefix = "ttyACM"
                # Prefix is different on Mac OS X.
                if sys.platform == "darwin":
                    prefix = "tty.usbmodem"
                if not dev.startswith(prefix):
                    continue
                tmpname = "/tmp/monsoon.%s.%s" % (os.uname()[0], dev)
                self._tempfile = open(tmpname, "w")
                try:
                    os.chmod(tmpname, 0o666)
                except OSError as e:
                    pass

                try:  # use a lockfile to ensure exclusive access
                    fcntl.lockf(self._tempfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except IOError as e:
                    logging.error("device %s is in use", dev)
                    continue

                try:  # try to open the device
                    self.ser = serial.Serial("/dev/%s" % dev, timeout=1)
                    self.StopDataCollection()  # just in case
                    self._FlushInput()  # discard stale input
                    status = self.GetStatus()
                except Exception as e:
                    logging.exception("Error opening device %s: %s", dev, e)
                    continue

                if not status:
                    logging.error("no response from device %s", dev)
                elif serialno and status["serialNumber"] != serialno:
                    logging.error("Another device serial #%d seen on %s",
                                  status["serialNumber"], dev)
                else:
                    self.start_voltage = status["voltage1"]
                    return

            self._tempfile = None
            if not wait: raise IOError("No device found")
            logging.info("Waiting for device...")
            time.sleep(1)

    def GetStatus(self):
        """Requests and waits for status.

        Returns:
            status dictionary.
        """
        # status packet format
        STATUS_FORMAT = ">BBBhhhHhhhHBBBxBbHBHHHHBbbHHBBBbbbbbbbbbBH"
        STATUS_FIELDS = [
            "packetType",
            "firmwareVersion",
            "protocolVersion",
            "mainFineCurrent",
            "usbFineCurrent",
            "auxFineCurrent",
            "voltage1",
            "mainCoarseCurrent",
            "usbCoarseCurrent",
            "auxCoarseCurrent",
            "voltage2",
            "outputVoltageSetting",
            "temperature",
            "status",
            "leds",
            "mainFineResistor",
            "serialNumber",
            "sampleRate",
            "dacCalLow",
            "dacCalHigh",
            "powerUpCurrentLimit",
            "runTimeCurrentLimit",
            "powerUpTime",
            "usbFineResistor",
            "auxFineResistor",
            "initialUsbVoltage",
            "initialAuxVoltage",
            "hardwareRevision",
            "temperatureLimit",
            "usbPassthroughMode",
            "mainCoarseResistor",
            "usbCoarseResistor",
            "auxCoarseResistor",
            "defMainFineResistor",
            "defUsbFineResistor",
            "defAuxFineResistor",
            "defMainCoarseResistor",
            "defUsbCoarseResistor",
            "defAuxCoarseResistor",
            "eventCode",
            "eventData",
        ]

        self._SendStruct("BBB", 0x01, 0x00, 0x00)
        while 1:  # Keep reading, discarding non-status packets
            read_bytes = self._ReadPacket()
            if not read_bytes:
                return None
            calsize = struct.calcsize(STATUS_FORMAT)
            if len(read_bytes) != calsize or read_bytes[0] != 0x10:
                logging.warning("Wanted status, dropped type=0x%02x, len=%d",
                                read_bytes[0], len(read_bytes))
                continue
            status = dict(zip(STATUS_FIELDS, struct.unpack(STATUS_FORMAT,
                                                           read_bytes)))
            p_type = status["packetType"]
            if p_type != 0x10:
                raise MonsoonError("Package type %s is not 0x10." % p_type)
            for k in status.keys():
                if k.endswith("VoltageSetting"):
                    status[k] = 2.0 + status[k] * 0.01
                elif k.endswith("FineCurrent"):
                    pass  # needs calibration data
                elif k.endswith("CoarseCurrent"):
                    pass  # needs calibration data
                elif k.startswith("voltage") or k.endswith("Voltage"):
                    status[k] = status[k] * 0.000125
                elif k.endswith("Resistor"):
                    status[k] = 0.05 + status[k] * 0.0001
                    if k.startswith("aux") or k.startswith("defAux"):
                        status[k] += 0.05
                elif k.endswith("CurrentLimit"):
                    status[k] = 8 * (1023 - status[k]) / 1023.0
            return status

    def RampVoltage(self, start, end):
        v = start
        if v < 3.0: v = 3.0  # protocol doesn't support lower than this
        while (v < end):
            self.SetVoltage(v)
            v += .1
            time.sleep(.1)
        self.SetVoltage(end)

    def SetVoltage(self, v):
        """Set the output voltage, 0 to disable.
        """
        if v == 0:
            self._SendStruct("BBB", 0x01, 0x01, 0x00)
        else:
            self._SendStruct("BBB", 0x01, 0x01, int((v - 2.0) * 100))

    def GetVoltage(self):
        """Get the output voltage.

        Returns:
            Current Output Voltage (in unit of v).
        """
        return self.GetStatus()["outputVoltageSetting"]

    def SetMaxCurrent(self, i):
        """Set the max output current.
        """
        if i < 0 or i > 8:
            raise MonsoonError(("Target max current %sA, is out of acceptable "
                                "range [0, 8].") % i)
        val = 1023 - int((i / 8) * 1023)
        self._SendStruct("BBB", 0x01, 0x0a, val & 0xff)
        self._SendStruct("BBB", 0x01, 0x0b, val >> 8)

    def SetMaxPowerUpCurrent(self, i):
        """Set the max power up current.
        """
        if i < 0 or i > 8:
            raise MonsoonError(("Target max current %sA, is out of acceptable "
                                "range [0, 8].") % i)
        val = 1023 - int((i / 8) * 1023)
        self._SendStruct("BBB", 0x01, 0x08, val & 0xff)
        self._SendStruct("BBB", 0x01, 0x09, val >> 8)

    def SetUsbPassthrough(self, val):
        """Set the USB passthrough mode: 0 = off, 1 = on,  2 = auto.
        """
        self._SendStruct("BBB", 0x01, 0x10, val)

    def GetUsbPassthrough(self):
        """Get the USB passthrough mode: 0 = off, 1 = on,  2 = auto.

        Returns:
            Current USB passthrough mode.
        """
        return self.GetStatus()["usbPassthroughMode"]

    def StartDataCollection(self):
        """Tell the device to start collecting and sending measurement data.
        """
        self._SendStruct("BBB", 0x01, 0x1b, 0x01)  # Mystery command
        self._SendStruct("BBBBBBB", 0x02, 0xff, 0xff, 0xff, 0xff, 0x03, 0xe8)

    def StopDataCollection(self):
        """Tell the device to stop collecting measurement data.
        """
        self._SendStruct("BB", 0x03, 0x00)  # stop

    def CollectData(self):
        """Return some current samples. Call StartDataCollection() first.
        """
        while 1:  # loop until we get data or a timeout
            _bytes = self._ReadPacket()
            if not _bytes:
                return None
            if len(_bytes) < 4 + 8 + 1 or _bytes[0] < 0x20 or _bytes[0] > 0x2F:
                logging.warning("Wanted data, dropped type=0x%02x, len=%d",
                                _bytes[0], len(_bytes))
                continue

            seq, _type, x, y = struct.unpack("BBBB", _bytes[:4])
            data = [struct.unpack(">hhhh", _bytes[x:x + 8])
                    for x in range(4, len(_bytes) - 8, 8)]

            if self._last_seq and seq & 0xF != (self._last_seq + 1) & 0xF:
                logging.warning("Data sequence skipped, lost packet?")
            self._last_seq = seq

            if _type == 0:
                if not self._coarse_scale or not self._fine_scale:
                    logging.warning(
                        "Waiting for calibration, dropped data packet.")
                    continue
                out = []
                for main, usb, aux, voltage in data:
                    if main & 1:
                        coarse = ((main & ~1) - self._coarse_zero)
                        out.append(coarse * self._coarse_scale)
                    else:
                        out.append((main - self._fine_zero) * self._fine_scale)
                return out
            elif _type == 1:
                self._fine_zero = data[0][0]
                self._coarse_zero = data[1][0]
            elif _type == 2:
                self._fine_ref = data[0][0]
                self._coarse_ref = data[1][0]
            else:
                logging.warning("Discarding data packet type=0x%02x", _type)
                continue

            # See http://wiki/Main/MonsoonProtocol for details on these values.
            if self._coarse_ref != self._coarse_zero:
                self._coarse_scale = 2.88 / (
                    self._coarse_ref - self._coarse_zero)
            if self._fine_ref != self._fine_zero:
                self._fine_scale = 0.0332 / (self._fine_ref - self._fine_zero)

    def _SendStruct(self, fmt, *args):
        """Pack a struct (without length or checksum) and send it.
        """
        data = struct.pack(fmt, *args)
        data_len = len(data) + 1
        checksum = (data_len + sum(bytearray(data))) % 256
        out = struct.pack("B", data_len) + data + struct.pack("B", checksum)
        self.ser.write(out)

    def _ReadPacket(self):
        """Read a single data record as a string (without length or checksum).
        """
        len_char = self.ser.read(1)
        if not len_char:
            logging.error("Reading from serial port timed out.")
            return None

        data_len = ord(len_char)
        if not data_len:
            return ""
        result = self.ser.read(int(data_len))
        result = bytearray(result)
        if len(result) != data_len:
            logging.error("Length mismatch, expected %d bytes, got %d bytes.",
                          data_len, len(result))
            return None
        body = result[:-1]
        checksum = (sum(struct.unpack("B" * len(body), body)) + data_len) % 256
        if result[-1] != checksum:
            logging.error(
                "Invalid checksum from serial port! Expected %s, got %s",
                hex(checksum), hex(result[-1]))
            return None
        return result[:-1]

    def _FlushInput(self):
        """ Flush all read data until no more available. """
        self.ser.flush()
        flushed = 0
        while True:
            ready_r, ready_w, ready_x = select.select(
                [self.ser], [], [self.ser], 0)
            if len(ready_x) > 0:
                logging.error("Exception from serial port.")
                return None
            elif len(ready_r) > 0:
                flushed += 1
                self.ser.read(1)  # This may cause underlying buffering.
                self.ser.flush()  # Flush the underlying buffer too.
            else:
                break
        # if flushed > 0:
        #     logging.info("dropped >%d bytes" % flushed)


class MonsoonData(object):
    """A class for reporting power measurement data from monsoon.

    Data means the measured current value in Amps.
    """
    # Number of digits for long rounding.
    lr = 8
    # Number of digits for short rounding
    sr = 6
    # Delimiter for writing multiple MonsoonData objects to text file.
    delimiter = "\n\n==========\n\n"

    def __init__(self, data_points, timestamps, hz, voltage, offset=0):
        """Instantiates a MonsoonData object.

        Args:
            data_points: A list of current values in Amp (float).
            timestamps: A list of epoch timestamps (int).
            hz: The hertz at which the data points are measured.
            voltage: The voltage at which the data points are measured.
            offset: The number of initial data points to discard
                in calculations.
        """
        self._data_points = data_points
        self._timestamps = timestamps
        self.offset = offset
        num_of_data_pt = len(self._data_points)
        if self.offset >= num_of_data_pt:
            raise MonsoonError(("Offset number (%d) must be smaller than the "
                                "number of data points (%d).") %
                               (offset, num_of_data_pt))
        self.data_points = self._data_points[self.offset:]
        self.timestamps = self._timestamps[self.offset:]
        self.hz = hz
        self.voltage = voltage
        self.tag = None
        self._validate_data()

    @property
    def average_current(self):
        """Average current in the unit of mA.
        """
        len_data_pt = len(self.data_points)
        if len_data_pt == 0:
            return 0
        cur = sum(self.data_points) * 1000 / len_data_pt
        return round(cur, self.sr)

    @property
    def total_charge(self):
        """Total charged used in the unit of mAh.
        """
        charge = (sum(self.data_points) / self.hz) * 1000 / 3600
        return round(charge, self.sr)

    @property
    def total_power(self):
        """Total power used.
        """
        power = self.average_current * self.voltage
        return round(power, self.sr)

    @staticmethod
    def from_string(data_str):
        """Creates a MonsoonData object from a string representation generated
        by __str__.

        Args:
            str: The string representation of a MonsoonData.

        Returns:
            A MonsoonData object.
        """
        lines = data_str.strip().split('\n')
        err_msg = ("Invalid input string format. Is this string generated by "
                   "MonsoonData class?")
        conditions = [len(lines) <= 4, "Average Current:" not in lines[1],
                      "Voltage: " not in lines[2],
                      "Total Power: " not in lines[3],
                      "samples taken at " not in lines[4],
                      lines[5] != "Time" + ' ' * 7 + "Amp"]
        if any(conditions):
            raise MonsoonError(err_msg)
        hz_str = lines[4].split()[2]
        hz = int(hz_str[:-2])
        voltage_str = lines[2].split()[1]
        voltage = int(voltage[:-1])
        lines = lines[6:]
        t = []
        v = []
        for l in lines:
            try:
                timestamp, value = l.split(' ')
                t.append(int(timestamp))
                v.append(float(value))
            except ValueError:
                raise MonsoonError(err_msg)
        return MonsoonData(v, t, hz, voltage)

    @staticmethod
    def save_to_text_file(monsoon_data, file_path):
        """Save multiple MonsoonData objects to a text file.

        Args:
            monsoon_data: A list of MonsoonData objects to write to a text
                file.
            file_path: The full path of the file to save to, including the file
                name.
        """
        if not monsoon_data:
            raise MonsoonError("Attempting to write empty Monsoon data to "
                               "file, abort")
        utils.create_dir(os.path.dirname(file_path))
        with open(file_path, 'w') as f:
            for md in monsoon_data:
                f.write(str(md))
                f.write(MonsoonData.delimiter)

    @staticmethod
    def from_text_file(file_path):
        """Load MonsoonData objects from a text file generated by
        MonsoonData.save_to_text_file.

        Args:
            file_path: The full path of the file load from, including the file
                name.

        Returns:
            A list of MonsoonData objects.
        """
        results = []
        with open(file_path, 'r') as f:
            data_strs = f.read().split(MonsoonData.delimiter)
            for data_str in data_strs:
                results.append(MonsoonData.from_string(data_str))
        return results

    def _validate_data(self):
        """Verifies that the data points contained in the class are valid.
        """
        msg = "Error! Expected {} timestamps, found {}.".format(
            len(self._data_points), len(self._timestamps))
        if len(self._data_points) != len(self._timestamps):
            raise MonsoonError(msg)

    def update_offset(self, new_offset):
        """Updates how many data points to skip in caculations.

        Always use this function to update offset instead of directly setting
        self.offset.

        Args:
            new_offset: The new offset.
        """
        self.offset = new_offset
        self.data_points = self._data_points[self.offset:]
        self.timestamps = self._timestamps[self.offset:]

    def get_data_with_timestamps(self):
        """Returns the data points with timestamps.

        Returns:
            A list of tuples in the format of (timestamp, data)
        """
        result = []
        for t, d in zip(self.timestamps, self.data_points):
            result.append(t, round(d, self.lr))
        return result

    def get_average_record(self, n):
        """Returns a list of average current numbers, each representing the
        average over the last n data points.

        Args:
            n: Number of data points to average over.

        Returns:
            A list of average current values.
        """
        history_deque = collections.deque()
        averages = []
        for d in self.data_points:
            history_deque.appendleft(d)
            if len(history_deque) > n:
                history_deque.pop()
            avg = sum(history_deque) / len(history_deque)
            averages.append(round(avg, self.lr))
        return averages

    def _header(self):
        strs = [""]
        if self.tag:
            strs.append(self.tag)
        else:
            strs.append("Monsoon Measurement Data")
        strs.append("Average Current: {}mA.".format(self.average_current))
        strs.append("Voltage: {}V.".format(self.voltage))
        strs.append("Total Power: {}mW.".format(self.total_power))
        strs.append(("{} samples taken at {}Hz, with an offset of {} samples."
                     ).format(
                         len(self._data_points), self.hz, self.offset))
        return "\n".join(strs)

    def __len__(self):
        return len(self.data_points)

    def __str__(self):
        strs = []
        strs.append(self._header())
        strs.append("Time" + ' ' * 7 + "Amp")
        for t, d in zip(self.timestamps, self.data_points):
            strs.append("{} {}".format(t, round(d, self.sr)))
        return "\n".join(strs)

    def __repr__(self):
        return self._header()


class Monsoon(object):
    """The wrapper class for test scripts to interact with monsoon.
    """

    def __init__(self, *args, **kwargs):
        serial = kwargs["serial"]
        device = None
        self.log = logging.getLogger()
        if "device" in kwargs:
            device = kwargs["device"]
        self.mon = MonsoonProxy(serialno=serial, device=device)
        self.dut = None

    def attach_device(self, dut):
        """Attach the controller object for the Device Under Test (DUT)
        physically attached to the Monsoon box.

        Args:
            dut: A controller object representing the device being powered by
                this Monsoon box.
        """
        self.dut = dut

    def set_voltage(self, volt, ramp=False):
        """Sets the output voltage of monsoon.

        Args:
            volt: Voltage to set the output to.
            ramp: If true, the output voltage will be increased gradually to
                prevent tripping Monsoon overvoltage.
        """
        if ramp:
            self.mon.RampVoltage(mon.start_voltage, volt)
        else:
            self.mon.SetVoltage(volt)

    def set_max_current(self, cur):
        """Sets monsoon's max output current.

        Args:
            cur: The max current in A.
        """
        self.mon.SetMaxCurrent(cur)

    def set_max_init_current(self, cur):
        """Sets the max power-up/inital current.

        Args:
            cur: The max initial current allowed in mA.
        """
        self.mon.SetMaxPowerUpCurrent(cur)

    @property
    def status(self):
        """Gets the status params of monsoon.

        Returns:
            A dictionary where each key-value pair represents a monsoon status
            param.
        """
        return self.mon.GetStatus()

    def take_samples(self, sample_hz, sample_num, sample_offset=0, live=False):
        """Take samples of the current value supplied by monsoon.

        This is the actual measurement for power consumption. This function
        blocks until the number of samples requested has been fulfilled.

        Args:
            hz: Number of points to take for every second.
            sample_num: Number of samples to take.
            offset: The number of initial data points to discard in MonsoonData
                calculations. sample_num is extended by offset to compensate.
            live: Print each sample in console as measurement goes on.

        Returns:
            A MonsoonData object representing the data obtained in this
            sampling. None if sampling is unsuccessful.
        """
        sys.stdout.flush()
        voltage = self.mon.GetVoltage()
        self.log.info("Taking samples at %dhz for %ds, voltage %.2fv.",
                      sample_hz, (sample_num / sample_hz), voltage)
        sample_num += sample_offset
        # Make sure state is normal
        self.mon.StopDataCollection()
        status = self.mon.GetStatus()
        native_hz = status["sampleRate"] * 1000

        # Collect and average samples as specified
        self.mon.StartDataCollection()

        # In case sample_hz doesn't divide native_hz exactly, use this
        # invariant: 'offset' = (consumed samples) * sample_hz -
        # (emitted samples) * native_hz
        # This is the error accumulator in a variation of Bresenham's
        # algorithm.
        emitted = offset = 0
        collected = []
        # past n samples for rolling average
        history_deque = collections.deque()
        current_values = []
        timestamps = []

        try:
            last_flush = time.time()
            while emitted < sample_num or sample_num == -1:
                # The number of raw samples to consume before emitting the next
                # output
                need = int((native_hz - offset + sample_hz - 1) / sample_hz)
                if need > len(collected):  # still need more input samples
                    samples = self.mon.CollectData()
                    if not samples:
                        break
                    collected.extend(samples)
                else:
                    # Have enough data, generate output samples.
                    # Adjust for consuming 'need' input samples.
                    offset += need * sample_hz
                    # maybe multiple, if sample_hz > native_hz
                    while offset >= native_hz:
                        # TODO(angli): Optimize "collected" operations.
                        this_sample = sum(collected[:need]) / need
                        this_time = int(time.time())
                        timestamps.append(this_time)
                        if live:
                            self.log.info("%s %s", this_time, this_sample)
                        current_values.append(this_sample)
                        sys.stdout.flush()
                        offset -= native_hz
                        emitted += 1  # adjust for emitting 1 output sample
                    collected = collected[need:]
                    now = time.time()
                    if now - last_flush >= 0.99:  # flush every second
                        sys.stdout.flush()
                        last_flush = now
        except Exception as e:
            pass
        self.mon.StopDataCollection()
        try:
            return MonsoonData(current_values,
                               timestamps,
                               sample_hz,
                               voltage,
                               offset=sample_offset)
        except:
            return None

    @utils.timeout(60)
    def usb(self, state):
        """Sets the monsoon's USB passthrough mode. This is specific to the
        USB port in front of the monsoon box which connects to the powered
        device, NOT the USB that is used to talk to the monsoon itself.

        "Off" means USB always off.
        "On" means USB always on.
        "Auto" means USB is automatically turned off when sampling is going on,
        and turned back on when sampling finishes.

        Args:
            stats: The state to set the USB passthrough to.

        Returns:
            True if the state is legal and set. False otherwise.
        """
        state_lookup = {"off": 0, "on": 1, "auto": 2}
        state = state.lower()
        if state in state_lookup:
            current_state = self.mon.GetUsbPassthrough()
            while (current_state != state_lookup[state]):
                self.mon.SetUsbPassthrough(state_lookup[state])
                time.sleep(1)
                current_state = self.mon.GetUsbPassthrough()
            return True
        return False

    def _check_dut(self):
        """Verifies there is a DUT attached to the monsoon.

        This should be called in the functions that operate the DUT.
        """
        if not self.dut:
            raise MonsoonError("Need to attach the device before using it.")

    @utils.timeout(15)
    def _wait_for_device(self, ad):
        while ad.serial not in android_device.list_adb_devices():
            pass
        ad.adb.wait_for_device()

    def execute_sequence_and_measure(self,
                                     step_funcs,
                                     hz,
                                     duration,
                                     offset_sec=20,
                                     *args,
                                     **kwargs):
        """@Deprecated.
        Executes a sequence of steps and take samples in-between.

        For each step function, the following steps are followed:
        1. The function is executed to put the android device in a state.
        2. If the function returns False, skip to next step function.
        3. If the function returns True, sl4a session is disconnected.
        4. Monsoon takes samples.
        5. Sl4a is reconnected.

        Because it takes some time for the device to calm down after the usb
        connection is cut, an offset is set for each measurement. The default
        is 20s.

        Args:
            hz: Number of samples to take per second.
            durations: Number(s) of minutes to take samples for in each step.
                If this is an integer, all the steps will sample for the same
                amount of time. If this is an iterable of the same length as
                step_funcs, then each number represents the number of minutes
                to take samples for after each step function.
                e.g. If durations[0] is 10, we'll sample for 10 minutes after
                step_funcs[0] is executed.
            step_funcs: A list of funtions, whose first param is an android
                device object. If a step function returns True, samples are
                taken after this step, otherwise we move on to the next step
                function.
            ad: The android device object connected to this monsoon.
            offset_sec: The number of seconds of initial data to discard.
            *args, **kwargs: Extra args to be passed into each step functions.

        Returns:
            The MonsoonData objects from samplings.
        """
        self._check_dut()
        sample_nums = []
        try:
            if len(duration) != len(step_funcs):
                raise MonsoonError(("The number of durations need to be the "
                                    "same as the number of step functions."))
            for d in duration:
                sample_nums.append(d * 60 * hz)
        except TypeError:
            num = duration * 60 * hz
            sample_nums = [num] * len(step_funcs)
        results = []
        oset = offset_sec * hz
        for func, num in zip(step_funcs, sample_nums):
            try:
                self.usb("auto")
                step_name = func.__name__
                self.log.info("Executing step function %s.", step_name)
                take_sample = func(ad, *args, **kwargs)
                if not take_sample:
                    self.log.info("Skip taking samples for %s", step_name)
                    continue
                time.sleep(1)
                self.dut.stop_services()
                time.sleep(1)
                self.log.info("Taking samples for %s.", step_name)
                data = self.take_samples(hz, num, sample_offset=oset)
                if not data:
                    raise MonsoonError("Sampling for %s failed." % step_name)
                self.log.info("Sample summary: %s", repr(data))
                data.tag = step_name
                results.append(data)
            except Exception:
                self.log.exception("Exception happened during step %s, abort!"
                                   % func.__name__)
                return results
            finally:
                self.mon.StopDataCollection()
                self.usb("on")
                self._wait_for_device(self.dut)
                # Wait for device to come back online.
                time.sleep(10)
                self.dut.start_services(skip_sl4a=getattr(self.dut,
                                                          "skip_sl4a", False))
                # Release wake lock to put device into sleep.
                self.dut.sl4a.goToSleepNow()
        return results

    def measure_power(self, hz, duration, tag, offset=30):
        """Measure power consumption of the attached device.

        Because it takes some time for the device to calm down after the usb
        connection is cut, an offset is set for each measurement. The default
        is 30s. The total time taken to measure will be (duration + offset).

        Args:
            hz: Number of samples to take per second.
            duration: Number of seconds to take samples for in each step.
            offset: The number of seconds of initial data to discard.
            tag: A string that's the name of the collected data group.

        Returns:
            A MonsoonData object with the measured power data.
        """
        num = duration * hz
        oset = offset * hz
        data = None
        try:
            self.usb("auto")
            time.sleep(1)
            self.dut.stop_services()
            time.sleep(1)
            data = self.take_samples(hz, num, sample_offset=oset)
            if not data:
                raise MonsoonError((
                    "No data was collected in measurement %s.") % tag)
            data.tag = tag
            self.log.info("Measurement summary: %s", repr(data))
        finally:
            self.mon.StopDataCollection()
            self.log.info("Finished taking samples, reconnecting to dut.")
            self.usb("on")
            self._wait_for_device(self.dut)
            # Wait for device to come back online.
            time.sleep(10)
            self.dut.start_services(skip_sl4a=getattr(self.dut,
                                                      "skip_sl4a", False))
            # Release wake lock to put device into sleep.
            self.dut.sl4a.goToSleepNow()
            self.log.info("Dut reconnected.")
            return data
