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

import importlib
import logging

MOBLY_CONTROLLER_CONFIG_NAME = "Sniffer"


def create(configs):
    """Initializes the sniffer structures based on the JSON configuration. The
    expected keys are:

        Type: A first-level type of sniffer. Planned to be 'local' for sniffers
            running on the local machine, or 'remote' for sniffers running
            remotely.

        SubType: The specific sniffer type to be used.

        Interface: The WLAN interface used to configure the sniffer.

        BaseConfigs: A dictionary specifying baseline configurations of the
            sniffer. Configurations can be overridden when starting a capture.
            The keys must be one of the Sniffer.CONFIG_KEY_* values.
    """
    objs = []
    for c in configs:
        sniffer_type = c["Type"]
        sniffer_subtype = c["SubType"]
        interface = c["Interface"]
        base_configs = c["BaseConfigs"]
        module_name = "mobly.controllers.sniffer_lib.{}.{}".format(
            sniffer_type, sniffer_subtype)
        module = importlib.import_module(module_name)
        objs.append(module.Sniffer(interface,
                                   logging.getLogger(),
                                   base_configs=base_configs))
    return objs


def destroy(objs):
    """Destroys the sniffers and terminates any ongoing capture sessions.
    """
    for sniffer in objs:
        try:
            sniffer.stop_capture()
        except SnifferError:
            pass


class SnifferError(Exception):
    """This is the Exception class defined for all errors generated by
    Sniffer-related modules.
    """
    pass


class InvalidDataError(Exception):
    """This exception is thrown when invalid configuration data is passed
    to a method.
    """
    pass


class ExecutionError(SnifferError):
    """This exception is thrown when trying to configure the capture device
    or when trying to execute the capture operation.

    When this exception is seen, it is possible that the sniffer module is run
    without sudo (for local sniffers) or keys are out-of-date (for remote
    sniffers).
    """
    pass


class InvalidOperationError(SnifferError):
    """Certain methods may only be accessed when the instance upon which they
    are invoked is in a certain state. This indicates that the object is not
    in the correct state for a method to be called.
    """
    pass


class Sniffer(object):
    """This class defines an object representing a sniffer.

    The object defines the generic behavior of sniffers - irrespective of how
    they are implemented, or where they are located: on the local machine or on
    the remote machine.
    """

    CONFIG_KEY_CHANNEL = "channel"

    def __init__(self, interface, logger, base_configs=None):
        """The constructor for the Sniffer. It constructs a sniffer and
        configures it to be ready for capture.

        Args:
            interface: A string specifying the interface used to configure the
                sniffer.
            logger: Mobly logger object.
            base_configs: A dictionary containing baseline configurations of the
                sniffer. These can be overridden when staring a capture. The
                keys are specified by Sniffer.CONFIG_KEY_*.

        Returns:
            self: A configured sniffer.

        Raises:
            InvalidDataError: if the config_path is invalid.
            NoPermissionError: if an error occurs while configuring the
                sniffer.
        """
        raise NotImplementedError("Base class should not be called directly!")

    def get_descriptor(self):
        """This function returns a string describing the sniffer. The specific
        string (and its format) is up to each derived sniffer type.

        Returns:
            A string describing the sniffer.
        """
        raise NotImplementedError("Base class should not be called directly!")

    def get_type(self):
        """This function returns the type of the sniffer.

        Returns:
            The type (string) of the sniffer. Corresponds to the 'Type' key of
            the sniffer configuration.
        """
        raise NotImplementedError("Base class should not be called directly!")

    def get_subtype(self):
        """This function returns the sub-type of the sniffer.

        Returns:
            The sub-type (string) of the sniffer. Corresponds to the 'SubType'
            key of the sniffer configuration.
        """
        raise NotImplementedError("Base class should not be called directly!")

    def get_interface(self):
        """This function returns The interface used to configure the sniffer,
        e.g. 'wlan0'.

        Returns:
            The interface (string) used to configure the sniffer. Corresponds to
            the 'Interface' key of the sniffer configuration.
        """
        raise NotImplementedError("Base class should not be called directly!")

    def get_capture_file(self):
        """The sniffer places a capture in the logger directory. This function
        enables the caller to obtain the path of that capture.

        Returns:
            The full path of the current or last capture.
        """
        raise NotImplementedError("Base class should not be called directly!")

    def start_capture(self,
                      override_configs=None,
                      additional_args=None,
                      duration=None,
                      packet_count=None):
        """This function starts a capture which is saved to the specified file
        path.

        Depending on the type/subtype and configuration of the sniffer the
        capture may terminate on its own or may require an explicit call to the
        stop_capture() function.

        This is a non-blocking function so a terminating function must be
        called either explicitly or implicitly:

            - Explicitly: call either stop_capture() or wait_for_capture()

            - Implicitly: use with a with clause. The wait_for_capture() function
                will be called if a duration is specified (i.e. is not
                None), otherwise a stop_capture() will be called.

        The capture is saved to a file in the log path of the logger. Use
        the get_capture_file() to get the full path to the current or most
        recent capture.

        Args:
            override_configs: A dictionary which is combined with the
                base_configs ("BaseConfigs" in the sniffer configuration). The
                keys (specified by Sniffer.CONFIG_KEY_*) determine the
                configuration of the sniffer for this specific capture.
            additional_args: A string specifying additional raw
                command-line arguments to pass to the underlying sniffer. The
                interpretation of these flags is sniffer-dependent.
            duration: An integer specifying the number of seconds over which to
                capture packets. The sniffer will be terminated after this
                duration. Used in implicit mode when using a 'with' clause. In
                explicit control cases may have to be performed using a
                sleep+stop or as the timeout argument to the wait function.
            packet_count: An integer specifying the number of packets to capture
                before terminating. Should be used with duration to guarantee
                that capture terminates at some point (even if did not capture
                the specified number of packets).

        Returns:
            An ActiveCaptureContext process which can be used with a 'with'
            clause.

        Raises:
            InvalidDataError: for invalid configurations
            NoPermissionError: if an error occurs while configuring and running
                the sniffer.
        """
        raise NotImplementedError("Base class should not be called directly!")

    def stop_capture(self):
        """This function stops a capture and guarantees that the capture is
        saved to the capture file configured during the start_capture() method.
        Depending on the type of the sniffer the file may previously contain
        partial results (e.g. for a local sniffer) or may not exist until the
        stop_capture() method is executed (e.g. for a remote sniffer).

        Depending on the type/subtype and configuration of the sniffer the
        capture may terminate on its own without requiring a call to this
        function. In such a case it is still necessary to call either this
        function or the wait_for_capture() function to make sure that the
        capture file is moved to the correct location.

        Raises:
            NoPermissionError: No permission when trying to stop a capture
                and save the capture file.
        """
        raise NotImplementedError("Base class should not be called directly!")

    def wait_for_capture(self, timeout=None):
        """This function waits for a capture to terminate and guarantees that
        the capture is saved to the capture file configured during the
        start_capture() method. Depending on the type of the sniffer the file
        may previously contain partial results (e.g. for a local sniffer) or
        may not exist until the stop_capture() method is executed (e.g. for a
        remote sniffer).

        Depending on the type/subtype and configuration of the sniffer the
        capture may terminate on its own without requiring a call to this
        function. In such a case it is still necessary to call either this
        function or the stop_capture() function to make sure that the capture
        file is moved to the correct location.

        Args:
            timeout: An integer specifying the number of seconds to wait for
                the capture to terminate on its own. On expiration of the
                timeout the sniffer is stopped explicitly using the
                stop_capture() function.

        Raises:
            NoPermissionError: No permission when trying to stop a capture and
                save the capture file.
        """
        raise NotImplementedError("Base class should not be called directly!")


class ActiveCaptureContext(object):
    """This class defines an object representing an active sniffer capture.

    The object is returned by a Sniffer.start_capture() command and terminates
    the capture when the 'with' clause exits. It is syntactic sugar for
    try/finally.
    """

    _sniffer = None
    _timeout = None

    def __init__(self, sniffer, timeout=None):
        self._sniffer = sniffer
        self._timeout = timeout

    def __enter__(self):
        pass

    def __exit__(self, type, value, traceback):
        if self._sniffer is not None:
            if self._timeout is None:
                self._sniffer.stop_capture()
            else:
                self._sniffer.wait_for_capture(self._timeout)
        self._sniffer = None
