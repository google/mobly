# Copyright 2018 Google Inc.
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
import io
import os

from mobly import logger as mobly_logger
from mobly import utils
from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import errors
from mobly.controllers.android_device_lib.services import base_service


class Error(errors.DeviceError):
    """Root error type for logcat service."""
    SERVICE_TYPE = 'Logcat'


class Config(object):
    def __init__(self):
        self.clear_log = True
        self.logcat_params = None


class Logcat(base_service.BaseService):
    """Android logcat service for Mobly's AndroidDevice controller."""

    def __init__(self, android_device, configs=None):
        self._ad = android_device
        self._adb_logcat_process = None
        self.adb_logcat_file_path = None
        self._configs = configs if configs else Config()

    def _enable_logpersist(self):
        """Attempts to enable logpersist daemon to persist logs."""
        # Logpersist is only allowed on rootable devices because of excessive
        # reads/writes for persisting logs.
        if not self._ad.is_rootable:
            return

        logpersist_warning = ('%s encountered an error enabling persistent'
                              ' logs, logs may not get saved.')
        # Android L and older versions do not have logpersist installed,
        # so check that the logpersist scripts exists before trying to use
        # them.
        if not self._ad.adb.has_shell_command('logpersist.start'):
            logging.warning(logpersist_warning, self)
            return

        try:
            # Disable adb log spam filter for rootable devices. Have to stop
            # and clear settings first because 'start' doesn't support --clear
            # option before Android N.
            self._ad.adb.shell('logpersist.stop --clear')
            self._ad.adb.shell('logpersist.start')
        except adb.AdbError:
            logging.warning(logpersist_warning, self)

    def _is_timestamp_in_range(self, target, begin_time, end_time):
        low = mobly_logger.logline_timestamp_comparator(begin_time,
                                                        target) <= 0
        high = mobly_logger.logline_timestamp_comparator(end_time, target) >= 0
        return low and high

    @property
    def is_alive(self):
        return True if self._adb_logcat_process else False

    def clear_adb_log(self):
        # Clears cached adb content.
        self._ad.adb.logcat('-c')

    def cat_adb_log(self, tag, begin_time):
        """Takes an excerpt of the adb logcat log from a certain time point to
        current time.

        Args:
            tag: An identifier of the time period, usualy the name of a test.
            begin_time: Logline format timestamp of the beginning of the time
                period.
        """
        if not self.adb_logcat_file_path:
            raise Error(
                self._ad,
                'Attempting to cat adb log when none has been collected.')
        end_time = mobly_logger.get_log_line_timestamp()
        self._ad.log.debug('Extracting adb log from logcat.')
        adb_excerpt_path = os.path.join(self._ad.log_path, 'AdbLogExcerpts')
        utils.create_dir(adb_excerpt_path)
        f_name = os.path.basename(self.adb_logcat_file_path)
        out_name = f_name.replace('adblog,', '').replace('.txt', '')
        out_name = ',%s,%s.txt' % (begin_time, out_name)
        out_name = out_name.replace(':', '-')
        tag_len = utils.MAX_FILENAME_LEN - len(out_name)
        tag = tag[:tag_len]
        out_name = tag + out_name
        full_adblog_path = os.path.join(adb_excerpt_path, out_name)
        with io.open(full_adblog_path, 'w', encoding='utf-8') as out:
            in_file = self.adb_logcat_file_path
            with io.open(
                    in_file, 'r', encoding='utf-8', errors='replace') as f:
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

    def start(self, configs=None):
        """Starts a standing adb logcat collection in separate subprocesses and
        save the logcat in a file.

        This clears the previous cached logcat content on device.

        Args:
            clear: If True, clear device log before starting logcat.
        """
        if self._adb_logcat_process:
            raise Error(
                self._ad,
                'Logcat thread is already running, cannot start another one.')
        configs = configs if configs else self._configs
        if configs.clear_log:
            self.clear_adb_log()

        self._enable_logpersist()

        f_name = 'adblog,%s,%s.txt' % (self._ad.model,
                                       self._ad._normalized_serial)
        utils.create_dir(self._ad.log_path)
        logcat_file_path = os.path.join(self._ad.log_path, f_name)
        extra_params = configs.logcat_params if configs.logcat_params else ''
        cmd = '"%s" -s %s logcat -v threadtime %s >> "%s"' % (adb.ADB,
                                                              self._ad.serial,
                                                              extra_params,
                                                              logcat_file_path)
        process = utils.start_standing_subprocess(cmd, shell=True)
        self._adb_logcat_process = process
        self.adb_logcat_file_path = logcat_file_path

    def _stop_logcat_process(self):
        """Stops logcat process."""
        if self._adb_logcat_process:
            try:
                self.stop_adb_logcat()
            except:
                self.log.exception('Failed to stop adb logcat.')
            self._adb_logcat_process = None

    def stop(self):
        """Stops the adb logcat collection subprocess.

        Raises:
            errors.DeviceError: raised if there's no adb logcat collection going on.
        """
        if not self._adb_logcat_process:
            raise Error(self._ad, 'No ongoing adb logcat collection found.')
        utils.stop_standing_subprocess(self._adb_logcat_process)
        self._adb_logcat_process = None

    def pause(self):
        """
        """
        self.stop()

    def resume(self, config=None):
        """
        """
        self.start(config)
