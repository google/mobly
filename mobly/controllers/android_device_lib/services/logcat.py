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
import copy
import io
import logging
import os
import shutil

from mobly import logger as mobly_logger
from mobly import utils
from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import errors
from mobly.controllers.android_device_lib.services import base_service


class Error(errors.ServiceError):
    """Root error type for logcat service."""
    SERVICE_TYPE = 'Logcat'


class Config(object):
    """Config object for logcat service.

    Attributes:
        clear_log: bool, clears the logcat before collection if True.
        logcat_params: string, extra params to be added to logcat command.
        output_file_path: string, the path on the host to write the log file
            to, including the actual filename. The service will automatically
            generate one if not specified.
    """
    def __init__(self,
                 logcat_params=None,
                 clear_log=True,
                 output_file_path=None):
        self.clear_log = clear_log
        self.logcat_params = logcat_params if logcat_params else ''
        self.output_file_path = output_file_path


class Logcat(base_service.BaseService):
    """Android logcat service for Mobly's AndroidDevice controller.

    Attributes:
        adb_logcat_file_path: string, path to the file that the service writes
            adb logcat to by default.
    """
    OUTPUT_FILE_TYPE = 'logcat'

    def __init__(self, android_device, configs=None):
        super(Logcat, self).__init__(android_device, configs)
        self._ad = android_device
        self._adb_logcat_process = None
        self.adb_logcat_file_path = None
        # Logcat service uses a single config obj, using singular internal
        # name: `_config`.
        self._config = configs if configs else Config()

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

    def _generate_file_path_with_test_info(self, test_info):
        """Generates a file path based on the given test_info object.

        Args:
            test_info: runtime_test_info.RuntimeTestInfo, the test info to base
                the generated logcat file path on.

        Returns:
            The logcat file path to use with the test_info object's context in
            the file path
        """
        dest_path = test_info.output_path
        utils.create_dir(dest_path)
        filename = self._ad.generate_filename(self.OUTPUT_FILE_TYPE, test_info,
                                              'txt')
        return os.path.join(dest_path, filename)

    def create_per_test_excerpt(self, current_test_info):
        """Convenient method for creating excerpts of adb logcat.

        .. deprecated:: 1.10
           Use :func:`create_output_excerpts` instead.

        To use this feature, call this method at the end of: `setup_class`,
        `teardown_test`, and `teardown_class`.

        This moves the current content of `self.adb_logcat_file_path` to the
        log directory specific to the current test.

        Args:
            current_test_info: `self.current_test_info` in a Mobly test.
        """
        self.create_output_excerpts(current_test_info)

    def create_output_excerpts(self, test_info):
        """Convenient method for creating excerpts of adb logcat.

        This moves the current content of `self.adb_logcat_file_path` to the
        log directory specific to the current test.

        Call this method at the end of: `setup_class`, `teardown_test`, and
        `teardown_class`.

        Args:
            test_info: `self.current_test_info` in a Mobly test.

        Returns:
            List of strings, the absolute paths to excerpt files.
        """
        self.pause()

        excerpt_file_path = self._generate_file_path_with_test_info(test_info)
        shutil.move(self.adb_logcat_file_path, excerpt_file_path)
        self._ad.log.debug('logcat excerpt created at: %s', excerpt_file_path)
        self.resume()
        return [excerpt_file_path]

    def continue_with_test_info(self, test_info):
        """Runs the logcat service with the given test context.

        This method exists as an alternative to `self.create_output_excerpts`
        for the specific case where `on_fail` takes bugreports. The problem in
        that use case is that `self.create_output_excerpts` will clear the
        logcat buffer before `on_fail` takes the bugreport, which results in the
        bugreport losing most of the logcat logs. This method clears data before
        the test runs instead of after it, which results in the logcat logs
        being preserved in bugreports. This method should not be used in
        conjunction with `self.create_output_excerpts`.

        This starts or restarts the service with the `self.adb_logcat_file_path`
        pointing to the log directory specific to the current test. If the
        service restarts after this call, then the service will revert to using
        the default log directory.

        Call this method only at the beginning of: `setup_test`

        Args:
            test_info: `self.current_test_info` in a Mobly test.
        """
        if self.is_alive:
            self.pause()
        elif self._config.clear_log:
            self.clear_adb_log()

        excerpt_file_path = self._generate_file_path_with_test_info(test_info)
        self._start(logcat_file_path=excerpt_file_path)

    @property
    def is_alive(self):
        return True if self._adb_logcat_process else False

    def clear_adb_log(self):
        """Clears cached adb content."""
        try:
            self._ad.adb.logcat('-c')
        except adb.AdbError as e:
            # On Android O, the clear command fails due to a known bug.
            # Catching this so we don't crash from this Android issue.
            if b'failed to clear' in e.stderr:
                self._ad.log.warning(
                    'Encountered known Android error to clear logcat.')
            else:
                raise

    def cat_adb_log(self, tag, begin_time):
        """Takes an excerpt of the adb logcat log from a certain time point to
        current time.

        .. deprecated:: 1.10
            Use :func:`create_output_excerpts` instead.

        Args:
            tag: An identifier of the time period, usualy the name of a test.
            begin_time: Logline format timestamp of the beginning of the time
                period.

        Returns:
            String, full path to the excerpt file created.
        """
        if not self.adb_logcat_file_path:
            raise Error(
                self._ad,
                'Attempting to cat adb log when none has been collected.')
        end_time = mobly_logger.get_log_line_timestamp()
        self._ad.log.debug('Extracting adb log from logcat.')
        adb_excerpt_path = os.path.join(self._ad.log_path, 'AdbLogExcerpts')
        utils.create_dir(adb_excerpt_path)
        out_name = '%s,%s.txt' % (tag, begin_time)
        out_name = mobly_logger.sanitize_filename(out_name)
        full_adblog_path = os.path.join(adb_excerpt_path, out_name)
        with io.open(full_adblog_path, 'w', encoding='utf-8') as out:
            in_file = self.adb_logcat_file_path
            with io.open(in_file, 'r', encoding='utf-8',
                         errors='replace') as f:
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
        return full_adblog_path

    def _assert_not_running(self):
        """Asserts the logcat service is not running.

        Raises:
            Error, if the logcat service is running.
        """
        if self.is_alive:
            raise Error(
                self._ad,
                'Logcat thread is already running, cannot start another one.')

    def update_config(self, new_config):
        """Updates the configuration for the service.

        The service needs to be stopped before updating, and explicitly started
        after the update.

        This will reset the service. Previous output files may be orphaned if
        output path is changed.

        Args:
            new_config: Config, the new config to use.
        """
        self._assert_not_running()
        self._ad.log.info('[LogcatService] Changing config from %s to %s',
                          self._config, new_config)
        self._config = new_config

    def start(self):
        """Starts a standing adb logcat collection.

        The collection runs in a separate subprocess and saves logs in a file.
        """
        self._assert_not_running()
        if self._config.clear_log:
            self.clear_adb_log()
        self._start()

    def _start(self, logcat_file_path=None):
        """The actual logic of starting logcat.

        Args:
          log_cat_file_path: optional str, the host side file path to store the
              logcat file. If not specified, then the service will generate the
              file path based on the device's `log_path` attribute.
        """
        self._enable_logpersist()
        if not logcat_file_path:
            logcat_file_path = self._config.output_file_path
        if not logcat_file_path:
            f_name = self._ad.generate_filename(self.OUTPUT_FILE_TYPE,
                                                extension_name='txt')
            logcat_file_path = os.path.join(self._ad.log_path, f_name)
        utils.create_dir(os.path.dirname(logcat_file_path))
        cmd = '"%s" -s %s logcat -v threadtime %s >> "%s"' % (
            adb.ADB, self._ad.serial, self._config.logcat_params,
            logcat_file_path)
        process = utils.start_standing_subprocess(cmd, shell=True)
        self._adb_logcat_process = process
        self.adb_logcat_file_path = logcat_file_path

    def stop(self):
        """Stops the adb logcat service."""
        if not self._adb_logcat_process:
            return
        try:
            utils.stop_standing_subprocess(self._adb_logcat_process)
        except:
            self._ad.log.exception('Failed to stop adb logcat.')
        self._adb_logcat_process = None

    def pause(self):
        """Pauses logcat.

        Note: the service is unable to collect the logs when paused, if more
        logs are generated on the device than the device's log buffer can hold,
        some logs would be lost.

        Clears cached adb content, so that when the service resumes, we don't
        duplicate what's in the device's log buffer already. This helps
        situations like USB off.
        """
        self.stop()
        # Clears cached adb content, so that the next time logcat is started,
        # we won't produce duplicated logs to log file.
        # This helps disconnection that caused by, e.g., USB off; at the
        # cost of losing logs at disconnection caused by reboot.
        self.clear_adb_log()

    def resume(self):
        """Resumes a paused logcat service."""
        self._assert_not_running()
        # Not clearing the log regardless of the config when resuming.
        # Otherwise the logs during the paused time will be lost.
        self._start()
