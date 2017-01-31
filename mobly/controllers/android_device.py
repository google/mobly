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

from builtins import str
from builtins import open

import logging
import os
import time

from mobly import logger as mobly_logger
from mobly import signals
from mobly import utils
from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import event_dispatcher
from mobly.controllers.android_device_lib import fastboot
from mobly.controllers.android_device_lib import jsonrpc_client_base
from mobly.controllers.android_device_lib import sl4a_client
from mobly.controllers.android_device_lib import snippet_client

MOBLY_CONTROLLER_CONFIG_NAME = 'AndroidDevice'

ANDROID_DEVICE_PICK_ALL_TOKEN = '*'

# Key name for adb logcat extra params in config file.
ANDROID_DEVICE_ADB_LOGCAT_PARAM_KEY = 'adb_logcat_param'
ANDROID_DEVICE_EMPTY_CONFIG_MSG = 'Configuration is empty, abort!'
ANDROID_DEVICE_NOT_LIST_CONFIG_MSG = 'Configuration should be a list, abort!'

# Keys for attributes in configs that alternate device behavior
KEY_SKIP_SL4A = 'skip_sl4a'
KEY_DEVICE_REQUIRED = 'required'


class Error(signals.ControllerError):
    pass


class SnippetError(signals.ControllerError):
    """Raised when somethig wrong with snippet happens."""


class DoesNotExistError(Error):
    """Raised when something that does not exist is referenced."""


def create(configs):
    """Creates AndroidDevice controller objects.

    Args:
        configs: A list of dicts, each representing a configuration for an
                 Android device.

    Returns:
        A list of AndroidDevice objects.
    """
    if not configs:
        raise Error(ANDROID_DEVICE_EMPTY_CONFIG_MSG)
    elif configs == ANDROID_DEVICE_PICK_ALL_TOKEN:
        ads = get_all_instances()
    elif not isinstance(configs, list):
        raise Error(ANDROID_DEVICE_NOT_LIST_CONFIG_MSG)
    elif isinstance(configs[0], str):
        # Configs is a list of serials.
        ads = get_instances(configs)
    else:
        # Configs is a list of dicts.
        ads = get_instances_with_configs(configs)
    connected_ads = list_adb_devices()

    for ad in ads:
        if ad.serial not in connected_ads:
            raise DoesNotExistError('Android device %s is specified in config'
                                    ' but is not attached.' % ad.serial)
    _start_services_on_ads(ads)
    return ads


def destroy(ads):
    """Cleans up AndroidDevice objects.

    Args:
        ads: A list of AndroidDevice objects.
    """
    for ad in ads:
        try:
            ad.stop_services()
        except:
            ad.log.exception('Failed to clean up properly.')


def get_info(ads):
    """Get information on a list of AndroidDevice objects.

    Args:
        ads: A list of AndroidDevice objects.

    Returns:
        A list of dict, each representing info for an AndroidDevice objects.
    """
    device_info = []
    for ad in ads:
        info = {'serial': ad.serial, 'model': ad.model}
        info.update(ad.build_info)
        device_info.append(info)
    return device_info


def _start_services_on_ads(ads):
    """Starts long running services on multiple AndroidDevice objects.

    If any one AndroidDevice object fails to start services, cleans up all
    existing AndroidDevice objects and their services.

    Args:
        ads: A list of AndroidDevice objects whose services to start.
    """
    running_ads = []
    for ad in ads:
        running_ads.append(ad)
        try:
            ad.start_services(skip_sl4a=getattr(ad, KEY_SKIP_SL4A, False))
        except Exception as e:
            is_required = getattr(ad, KEY_DEVICE_REQUIRED, True)
            if is_required:
                ad.log.exception('Failed to start some services, abort!')
                destroy(running_ads)
                raise
            else:
                logging.warning('Skipping device %s because some service '
                                'failed to start: %s', ad.serial, e)


def _parse_device_list(device_list_str, key):
    """Parses a byte string representing a list of devices. The string is
    generated by calling either adb or fastboot.

    Args:
        device_list_str: Output of adb or fastboot.
        key: The token that signifies a device in device_list_str.

    Returns:
        A list of android device serial numbers.
    """
    clean_lines = str(device_list_str, 'utf-8').strip().split('\n')
    results = []
    for line in clean_lines:
        tokens = line.strip().split('\t')
        if len(tokens) == 2 and tokens[1] == key:
            results.append(tokens[0])
    return results


def list_adb_devices():
    """List all android devices connected to the computer that are detected by
    adb.

    Returns:
        A list of android device serials. Empty if there's none.
    """
    out = adb.AdbProxy().devices()
    return _parse_device_list(out, 'device')


def list_fastboot_devices():
    """List all android devices connected to the computer that are in in
    fastboot mode. These are detected by fastboot.

    Returns:
        A list of android device serials. Empty if there's none.
    """
    out = fastboot.FastbootProxy().devices()
    return _parse_device_list(out, 'fastboot')


def get_instances(serials):
    """Create AndroidDevice instances from a list of serials.

    Args:
        serials: A list of android device serials.

    Returns:
        A list of AndroidDevice objects.
    """
    results = []
    for s in serials:
        results.append(AndroidDevice(s))
    return results


def get_instances_with_configs(configs):
    """Create AndroidDevice instances from a list of json configs.

    Each config should have the required key-value pair 'serial'.

    Args:
        configs: A list of dicts each representing the configuration of one
            android device.

    Returns:
        A list of AndroidDevice objects.
    """
    results = []
    for c in configs:
        try:
            serial = c.pop('serial')
        except KeyError:
            raise Error(
                'Required value "serial" is missing in AndroidDevice config %s.'
                % c)
        is_required = c.get(KEY_DEVICE_REQUIRED, True)
        try:
            ad = AndroidDevice(serial)
            ad.load_config(c)
        except Exception as e:
            if is_required:
                raise
            logging.warning('Skipping device %s due to error: %s', serial, e)
            continue
        results.append(ad)
    return results


def get_all_instances(include_fastboot=False):
    """Create AndroidDevice instances for all attached android devices.

    Args:
        include_fastboot: Whether to include devices in bootloader mode or not.

    Returns:
        A list of AndroidDevice objects each representing an android device
        attached to the computer.
    """
    if include_fastboot:
        serial_list = list_adb_devices() + list_fastboot_devices()
        return get_instances(serial_list)
    return get_instances(list_adb_devices())


def filter_devices(ads, func):
    """Finds the AndroidDevice instances from a list that match certain
    conditions.

    Args:
        ads: A list of AndroidDevice instances.
        func: A function that takes an AndroidDevice object and returns True
            if the device satisfies the filter condition.

    Returns:
        A list of AndroidDevice instances that satisfy the filter condition.
    """
    results = []
    for ad in ads:
        if func(ad):
            results.append(ad)
    return results


def get_device(ads, **kwargs):
    """Finds a unique AndroidDevice instance from a list that has specific
    attributes of certain values.

    Example:
        get_device(android_devices, label='foo', phone_number='1234567890')
        get_device(android_devices, model='angler')

    Args:
        ads: A list of AndroidDevice instances.
        kwargs: keyword arguments used to filter AndroidDevice instances.

    Returns:
        The target AndroidDevice instance.

    Raises:
        Error is raised if none or more than one device is
        matched.
    """

    def _get_device_filter(ad):
        for k, v in kwargs.items():
            if not hasattr(ad, k):
                return False
            elif getattr(ad, k) != v:
                return False
        return True

    filtered = filter_devices(ads, _get_device_filter)
    if not filtered:
        raise Error(
            'Could not find a target device that matches condition: %s.' %
            kwargs)
    elif len(filtered) == 1:
        return filtered[0]
    else:
        serials = [ad.serial for ad in filtered]
        raise Error('More than one device matched: %s' % serials)


def take_bug_reports(ads, test_name, begin_time):
    """Takes bug reports on a list of android devices.

    If you want to take a bug report, call this function with a list of
    android_device objects in on_fail. But reports will be taken on all the
    devices in the list concurrently. Bug report takes a relative long
    time to take, so use this cautiously.

    Args:
        ads: A list of AndroidDevice instances.
        test_name: Name of the test case that triggered this bug report.
        begin_time: Logline format timestamp taken when the test started.
    """
    begin_time = mobly_logger.normalize_log_line_timestamp(begin_time)

    def take_br(test_name, begin_time, ad):
        ad.take_bug_report(test_name, begin_time)

    args = [(test_name, begin_time, ad) for ad in ads]
    utils.concurrent_exec(take_br, args)


class AndroidDevice(object):
    """Class representing an android device.

    Each object of this class represents one Android device in Mobly, including
    handles to adb, fastboot, and sl4a clients. In addition to direct adb
    commands, this object also uses adb port forwarding to talk to the Android
    device.

    Attributes:
        serial: A string that's the serial number of the Androi device.
        log_path: A string that is the path where all logs collected on this
                  android device should be stored.
        log: A logger adapted from root logger with an added prefix specific
             to an AndroidDevice instance. The default prefix is
             [AndroidDevice|<serial>]. Use self.set_logger_prefix_tag to use
             a different tag in the prefix.
        adb_logcat_file_path: A string that's the full path to the adb logcat
                              file collected, if any.
        adb: An AdbProxy object used for interacting with the device via adb.
        fastboot: A FastbootProxy object used for interacting with the device
                  via fastboot.
    """

    def __init__(self, serial=''):
        self.serial = serial
        # logging.log_path only exists when this is used in an Mobly test run.
        log_path_base = getattr(logging, 'log_path', '/tmp/logs')
        self.log_path = os.path.join(log_path_base, 'AndroidDevice%s' % serial)
        self.log = AndroidDeviceLoggerAdapter(logging.getLogger(), {
            'tag': self.serial
        })
        self.sl4a = None
        self.ed = None
        self._adb_logcat_process = None
        self.adb_logcat_file_path = None
        self.adb = adb.AdbProxy(serial)
        self.fastboot = fastboot.FastbootProxy(serial)
        if not self.is_bootloader and self.is_rootable:
            self.root_adb()
        # A dict for tracking snippet clients. Keys are clients' attribute
        # names, values are the clients: {<attr name string>: <client object>}.
        self._snippet_clients = {}

    def set_logger_prefix_tag(self, tag):
        """Set a tag for the log line prefix of this instance.

        By default, the tag is the serial of the device, but sometimes having
        the serial number in the log line doesn't help much with debugging. It
        could be more helpful if users can mark the role of the device instead.

        For example, instead of marking the serial number:
            'INFO [AndroidDevice|abcdefg12345] One pending call ringing.'

        marking the role of the device here is  more useful here:
            'INFO [AndroidDevice|Caller] One pending call ringing.'

        Args:
            tag: A string that is the tag to use.
        """
        self.log.extra['tag'] = tag

    # TODO(angli): This function shall be refactored to accommodate all services
    # and not have hard coded switch for SL4A when b/29157104 is done.
    def start_services(self, skip_sl4a=False):
        """Starts long running services on the android device.

        1. Start adb logcat capture.
        2. Start SL4A if not skipped.

        Args:
            skip_sl4a: Does not attempt to start SL4A if True.
        """
        try:
            self.start_adb_logcat()
        except:
            self.log.exception('Failed to start adb logcat!')
            raise
        if not skip_sl4a:
            self._start_sl4a()

    def stop_services(self):
        """Stops long running services on the android device.

        Stop adb logcat and terminate sl4a sessions if exist.
        """
        if self._adb_logcat_process:
            self.stop_adb_logcat()
        self._terminate_sl4a()
        for name, client in self._snippet_clients.items():
            self._terminate_jsonrpc_client(client)
            delattr(self, name)
        self._snippet_clients = {}

    @property
    def build_info(self):
        """Get the build info of this Android device, including build id and
        build type.

        This is not available if the device is in bootloader mode.

        Returns:
            A dict with the build info of this Android device, or None if the
            device is in bootloader mode.
        """
        if self.is_bootloader:
            self.log.error('Device is in fastboot mode, could not get build '
                           'info.')
            return
        info = {}
        info['build_id'] = self.adb.getprop('ro.build.id')
        info['build_type'] = self.adb.getprop('ro.build.type')
        return info

    @property
    def is_bootloader(self):
        """True if the device is in bootloader mode.
        """
        return self.serial in list_fastboot_devices()

    @property
    def is_adb_root(self):
        """True if adb is running as root for this device.
        """
        try:
            return '0' == self.adb.shell('id -u').decode('utf-8').strip()
        except adb.AdbError:
            # Wait a bit and retry to work around adb flakiness for this cmd.
            time.sleep(0.2)
            return '0' == self.adb.shell('id -u').decode('utf-8').strip()

    @property
    def is_rootable(self):
        """If the build type is 'user', the device is not rootable.

        Other possible build types are 'userdebug' and 'eng', both are rootable.
        We are checking the last four chars of the clean stdout because the
        stdout of the adb command could be polluted with other info like adb
        server startup message.
        """
        build_type_output = self.adb.getprop('ro.build.type').lower()
        return build_type_output[-4:] != 'user'

    @property
    def model(self):
        """The Android code name for the device.
        """
        # If device is in bootloader mode, get mode name from fastboot.
        if self.is_bootloader:
            out = self.fastboot.getvar('product').strip()
            # 'out' is never empty because of the 'total time' message fastboot
            # writes to stderr.
            lines = out.decode('utf-8').split('\n', 1)
            if lines:
                tokens = lines[0].split(' ')
                if len(tokens) > 1:
                    return tokens[1].lower()
            return None
        model = self.adb.getprop('ro.build.product').lower()
        if model == 'sprout':
            return model
        else:
            return self.adb.getprop('ro.product.name').lower()

    def load_config(self, config):
        """Add attributes to the AndroidDevice object based on json config.

        Args:
            config: A dictionary representing the configs.

        Raises:
            Error is raised if the config is trying to overwrite
            an existing attribute.
        """
        for k, v in config.items():
            if hasattr(self, k):
                raise Error('Attempting to set existing attribute %s on %s' %
                            (k, self.serial))
            setattr(self, k, v)

    def root_adb(self):
        """Change adb to root mode for this device if allowed.

        If executed on a production build, adb will not be switched to root
        mode per security restrictions.
        """
        self.adb.root()
        self.adb.wait_for_device()

    def load_snippet(self, name, package):
        """Starts the snippet apk with the given package name and connects.

        Examples:
            >>> ad = AndroidDevice()
            >>> ad.load_snippet(
                    name='maps', package='com.google.maps.snippets')
            >>> ad.maps.activateZoom('3')

        Args:
            name: The attribute name to which to attach the snippet server.
                  e.g. name='maps' will attach the snippet server to ad.maps.
            package: The package name defined in AndroidManifest.xml of the
                     snippet apk.

        Raises:
            SnippetError is raised if illegal load operations are attempted.
        """
        # Should not load snippet with the same attribute more than once.
        if name in self._snippet_clients:
            raise SnippetError(
                'Attribute "%s" is already registered with package "%s", it '
                'cannot be used again.' %
                (name, self._snippet_clients[name].package))
        # Should not load snippet with an existing attribute.
        if hasattr(self, name):
            raise SnippetError('Attribute "%s" already exists, please use a '
                               'different name.' % name)
        # Should not load the same snippet package more than once.
        for client_name, client in self._snippet_clients.items():
            if package == client.package:
                raise SnippetError(
                    'Snippet package "%s" has already been loaded under name'
                    ' "%s".' % (package, client_name))
        host_port = utils.get_available_host_port()
        # TODO(adorokhine): Don't assume that a free host-side port is free on
        # the device as well. Both sides should allocate a unique port.
        device_port = host_port
        client = snippet_client.SnippetClient(
            package=package, port=host_port, adb_proxy=self.adb)
        self._start_jsonrpc_client(client, host_port, device_port)
        self._snippet_clients[name] = client
        setattr(self, name, client)

    def _start_sl4a(self):
        """Create an sl4a connection to the device.

        Assigns the open sl4a client to self.sl4a. By default, another
        connection on the same session is made for EventDispatcher, and the
        dispatcher is bound to self.ed.

        If sl4a server is not started on the device, tries to start it.
        """
        host_port = utils.get_available_host_port()
        device_port = sl4a_client.DEVICE_SIDE_PORT
        self.sl4a = sl4a_client.Sl4aClient(self.adb)
        self._start_jsonrpc_client(self.sl4a, host_port, device_port)

        # Start an EventDispatcher for the current sl4a session
        event_client = sl4a_client.Sl4aClient(self.adb)
        event_client.connect(
            port=host_port,
            uid=self.sl4a.uid,
            cmd=jsonrpc_client_base.JsonRpcCommand.CONTINUE)
        self.ed = event_dispatcher.EventDispatcher(event_client)
        self.ed.start()

    def _start_jsonrpc_client(self, client, host_port, device_port):
        """Create a connection to a jsonrpc server running on the device.

        If the connection cannot be made, tries to restart it.
        """
        client.check_app_installed()
        self.adb.tcp_forward(host_port, device_port)
        try:
            client.connect(port=host_port)
        except:
            try:
                client.stop_app()
            except Exception as e:
                self.log.warning(e)
            client.start_app()
            client.connect(port=host_port)

    def _terminate_jsonrpc_client(self, client):
        client.closeSl4aSession()
        client.close()
        client.stop_app()
        self.adb.forward('--remove tcp:%d' % client.port)

    def _is_timestamp_in_range(self, target, begin_time, end_time):
        low = mobly_logger.logline_timestamp_comparator(begin_time,
                                                        target) <= 0
        high = mobly_logger.logline_timestamp_comparator(end_time, target) >= 0
        return low and high

    def cat_adb_log(self, tag, begin_time):
        """Takes an excerpt of the adb logcat log from a certain time point to
        current time.

        Args:
            tag: An identifier of the time period, usualy the name of a test.
            begin_time: Logline format timestamp of the beginning of the time
                period.
        """
        if not self.adb_logcat_file_path:
            raise Error('Attempting to cat adb log when none has been collected'
                        ' on Android device %s.' % self.serial)
        end_time = mobly_logger.get_log_line_timestamp()
        self.log.debug('Extracting adb log from logcat.')
        adb_excerpt_path = os.path.join(self.log_path, 'AdbLogExcerpts')
        utils.create_dir(adb_excerpt_path)
        f_name = os.path.basename(self.adb_logcat_file_path)
        out_name = f_name.replace('adblog,', '').replace('.txt', '')
        out_name = ',%s,%s.txt' % (begin_time, out_name)
        tag_len = utils.MAX_FILENAME_LEN - len(out_name)
        tag = tag[:tag_len]
        out_name = tag + out_name
        full_adblog_path = os.path.join(adb_excerpt_path, out_name)
        with open(full_adblog_path, 'w', encoding='utf-8') as out:
            in_file = self.adb_logcat_file_path
            with open(in_file, 'r', encoding='utf-8', errors='replace') as f:
                in_range = False
                while True:
                    line = None
                    try:
                        line = f.readline()
                        if not line:
                            break
                    except:
                        continue
                    line_time = line[:mobly_logger.log_line_timestamp_len]
                    if not mobly_logger.is_valid_logline_timestamp(line_time):
                        continue
                    if self._is_timestamp_in_range(line_time, begin_time,
                                                   end_time):
                        in_range = True
                        if not line.endswith('\n'):
                            line += '\n'
                        out.write(line)
                    else:
                        if in_range:
                            break

    def start_adb_logcat(self):
        """Starts a standing adb logcat collection in separate subprocesses and
        save the logcat in a file.
        """
        if self._adb_logcat_process:
            raise Error('Android device %s already has an adb logcat thread '
                        'going on. Cannot start another one.' % self.serial)
        # Disable adb log spam filter for rootable. Have to stop and clear
        # settings first because 'start' doesn't support --clear option before
        # Android N.
        if self.is_rootable:
            self.adb.shell('logpersist.stop --clear')
            self.adb.shell('logpersist.start')
        f_name = 'adblog,%s,%s.txt' % (self.model, self.serial)
        utils.create_dir(self.log_path)
        logcat_file_path = os.path.join(self.log_path, f_name)
        try:
            extra_params = self.adb_logcat_param
        except AttributeError:
            extra_params = '-b all'
        cmd = 'adb -s %s logcat -v threadtime %s >> %s' % (
              self.serial, extra_params, logcat_file_path)
        self._adb_logcat_process = utils.start_standing_subprocess(cmd)
        self.adb_logcat_file_path = logcat_file_path

    def stop_adb_logcat(self):
        """Stops the adb logcat collection subprocess.
        """
        if not self._adb_logcat_process:
            raise Error('Android device %s does not have an ongoing adb logcat '
                        'collection.' % self.serial)
        utils.stop_standing_subprocess(self._adb_logcat_process)
        self._adb_logcat_process = None

    def take_bug_report(self, test_name, begin_time):
        """Takes a bug report on the device and stores it in a file.

        Args:
            test_name: Name of the test case that triggered this bug report.
            begin_time: Logline format timestamp taken when the test started.
        """
        new_br = True
        try:
            stdout = self.adb.shell('bugreportz -v').decode('utf-8')
            # This check is necessary for builds before N, where adb shell's ret
            # code and stderr are not propagated properly.
            if 'not found' in stdout:
                new_br = False
        except adb.AdbError:
            new_br = False
        br_path = os.path.join(self.log_path, 'BugReports')
        utils.create_dir(br_path)
        base_name = ',%s,%s.txt' % (begin_time, self.serial)
        if new_br:
            base_name = base_name.replace('.txt', '.zip')
        test_name_len = utils.MAX_FILENAME_LEN - len(base_name)
        out_name = test_name[:test_name_len] + base_name
        full_out_path = os.path.join(br_path, out_name.replace(' ', r'\ '))
        # in case device restarted, wait for adb interface to return
        self.wait_for_boot_completion()
        self.log.info('Taking bugreport for %s.', test_name)
        if new_br:
            out = self.adb.shell('bugreportz').decode('utf-8')
            if not out.startswith('OK'):
                raise Error('Failed to take bugreport on %s: %s' %
                            (self.serial, out))
            br_out_path = out.split(':')[1].strip()
            self.adb.pull('%s %s' % (br_out_path, full_out_path))
        else:
            self.adb.bugreport(' > %s' % full_out_path)
        self.log.info('Bugreport for %s taken at %s.', test_name,
                      full_out_path)

    def _terminate_sl4a(self):
        """Terminate the current sl4a session.

        Send terminate signal to sl4a server; stop dispatcher associated with
        the session. Clear corresponding droids and dispatchers from cache.
        """
        if self.sl4a:
            self._terminate_jsonrpc_client(self.sl4a)
            self.sl4a = None
        if self.ed:
            self.ed.clean_up()
            self.ed = None

    def run_iperf_client(self, server_host, extra_args=''):
        """Start iperf client on the device.

        Return status as true if iperf client start successfully.
        And data flow information as results.

        Args:
            server_host: Address of the iperf server.
            extra_args: A string representing extra arguments for iperf client,
                e.g. '-i 1 -t 30'.

        Returns:
            status: true if iperf client start successfully.
            results: results have data flow information
        """
        out = self.adb.shell('iperf3 -c %s %s' % (server_host, extra_args))
        clean_out = str(out, 'utf-8').strip().split('\n')
        if 'error' in clean_out[0].lower():
            return False, clean_out
        return True, clean_out

    def wait_for_boot_completion(self):
        """Waits for Android framework to broadcast ACTION_BOOT_COMPLETED.

        This function times out after 15 minutes.
        """
        timeout_start = time.time()
        timeout = 15 * 60

        self.adb.wait_for_device()
        while time.time() < timeout_start + timeout:
            try:
                completed = self.adb.getprop('sys.boot_completed')
                if completed == '1':
                    return
            except adb.AdbError:
                # adb shell calls may fail during certain period of booting
                # process, which is normal. Ignoring these errors.
                pass
            time.sleep(5)
        raise Error('Device %s booting process timed out.' % self.serial)

    def _get_active_snippet_info(self):
        """Collects information on currently active snippet clients.

        The info is used for restoring the snippet clients after rebooting the
        device.

        Returns:
            A list of tuples, each tuple's first element is the name of the
            snippet client's attribute, the second element is the package name
            of the snippet.
        """
        snippet_info = []
        for attr_name, client in self._snippet_clients.items():
            snippet_info.append((attr_name, client.package))
        return snippet_info

    def reboot(self):
        """Reboots the device.

        Terminate all sl4a sessions, reboot the device, wait for device to
        complete booting, and restart an sl4a session.

        This is a blocking method.

        This is probably going to print some error messages in console. Only
        use if there's no other option.

        Raises:
            Error is raised if waiting for completion timed out.
        """
        if self.is_bootloader:
            self.fastboot.reboot()
            return
        snippet_info = self._get_active_snippet_info()
        self.stop_services()
        self.adb.reboot()
        self.wait_for_boot_completion()
        if self.is_rootable:
            self.root_adb()
        skip_sl4a = getattr(self, KEY_SKIP_SL4A, False) or self.sl4a is None
        self.start_services(skip_sl4a=skip_sl4a)
        for attr_name, package_name in snippet_info:
            self.load_snippet(attr_name, package_name)


class AndroidDeviceLoggerAdapter(logging.LoggerAdapter):
    """A wrapper class that adds a prefix to each log line.

    Usage:
        my_log = AndroidDeviceLoggerAdapter(logging.getLogger(), {
            'tag': <custom tag>
        })

        Then each log line added by my_log will have a prefix
        '[AndroidDevice|<tag>]'
    """

    def process(self, msg, kwargs):
        msg = '[AndroidDevice|%s] %s' % (self.extra['tag'], msg)
        return (msg, kwargs)
