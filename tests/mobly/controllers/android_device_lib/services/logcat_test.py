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
import logging
import mock
import os
import shutil
import tempfile

from future.tests.base import unittest

from mobly import utils
from mobly import runtime_test_info
from mobly.controllers import android_device
from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib.services import logcat

from tests.lib import mock_android_device

# The expected result of the cat adb operation.
MOCK_ADB_LOGCAT_CAT_RESULT = [
    '02-29 14:02:21.456  4454  Something\n',
    '02-29 14:02:21.789  4454  Something again\n'
]
# A mocked piece of adb logcat output.
MOCK_ADB_LOGCAT = (u'02-29 14:02:19.123  4454  Nothing\n'
                   u'%s'
                   u'02-29 14:02:22.123  4454  Something again and again\n'
                   ) % u''.join(MOCK_ADB_LOGCAT_CAT_RESULT)
# The expected result of the cat adb operation.
MOCK_ADB_UNICODE_LOGCAT_CAT_RESULT = [
    '02-29 14:02:21.456  4454  Something \u901a\n',
    '02-29 14:02:21.789  4454  Something again\n'
]
# A mocked piece of adb logcat output.
MOCK_ADB_UNICODE_LOGCAT = (
    u'02-29 14:02:19.123  4454  Nothing\n'
    u'%s'
    u'02-29 14:02:22.123  4454  Something again and again\n'
) % u''.join(MOCK_ADB_UNICODE_LOGCAT_CAT_RESULT)

# Mock start and end time of the adb cat.
MOCK_ADB_LOGCAT_BEGIN_TIME = '02-29 14:02:20.123'
MOCK_ADB_LOGCAT_END_TIME = '02-29 14:02:22.000'

# Mock AdbError for missing logpersist scripts
MOCK_LOGPERSIST_STOP_MISSING_ADB_ERROR = adb.AdbError(
    'logpersist.stop --clear', '',
    '/system/bin/sh: logpersist.stop: not found', 0)
MOCK_LOGPERSIST_START_MISSING_ADB_ERROR = adb.AdbError(
    'logpersist.start --clear', '',
    '/system/bin/sh: logpersist.stop: not found', 0)


class LogcatTest(unittest.TestCase):
    """Tests for Logcat service and its integration with AndroidDevice."""

    def setUp(self):
        # Set log_path to logging since mobly logger setup is not called.
        if not hasattr(logging, 'log_path'):
            setattr(logging, 'log_path', '/tmp/logs')
        # Creates a temp dir to be used by tests in this test class.
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Removes the temp dir.
        """
        shutil.rmtree(self.tmp_dir)

    def AssertFileContains(self, content, file_path):
        with open(file_path, 'r') as f:
            output = f.read()
        self.assertIn(content, output)

    def AssertFileDoesNotContain(self, content, file_path):
        with open(file_path, 'r') as f:
            output = f.read()
        self.assertNotIn(content, output)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch('mobly.utils.create_dir')
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_start_and_stop(self, stop_proc_mock, start_proc_mock,
                            create_dir_mock, FastbootProxy, MockAdbProxy):
        """Verifies the steps of collecting adb logcat on an AndroidDevice
        object, including various function calls and the expected behaviors of
        the calls.
        """
        mock_serial = '1'
        ad = android_device.AndroidDevice(serial=mock_serial)
        logcat_service = logcat.Logcat(ad)
        logcat_service.start()
        # Verify start did the correct operations.
        self.assertTrue(logcat_service._adb_logcat_process)
        expected_log_path = os.path.join(logging.log_path,
                                         'AndroidDevice%s' % ad.serial,
                                         'adblog,fakemodel,%s.txt' % ad.serial)
        create_dir_mock.assert_called_with(os.path.dirname(expected_log_path))
        adb_cmd = '"adb" -s %s logcat -v threadtime  >> %s'
        start_proc_mock.assert_called_with(
            adb_cmd % (ad.serial, '"%s"' % expected_log_path), shell=True)
        self.assertEqual(logcat_service.adb_logcat_file_path,
                         expected_log_path)
        expected_msg = (
            'Logcat thread is already running, cannot start another'
            ' one.')
        # Expect error if start is called back to back.
        with self.assertRaisesRegex(logcat.Error, expected_msg):
            logcat_service.start()
        # Verify stop did the correct operations.
        logcat_service.stop()
        stop_proc_mock.assert_called_with('process')
        self.assertIsNone(logcat_service._adb_logcat_process)
        self.assertEqual(logcat_service.adb_logcat_file_path,
                         expected_log_path)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch('mobly.utils.create_dir')
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    @mock.patch(
        'mobly.controllers.android_device_lib.services.logcat.Logcat.clear_adb_log',
        return_value=mock_android_device.MockAdbProxy('1'))
    def test_pause_and_resume(self, clear_adb_mock, stop_proc_mock,
                              start_proc_mock, create_dir_mock, FastbootProxy,
                              MockAdbProxy):
        mock_serial = '1'
        ad = android_device.AndroidDevice(serial=mock_serial)
        logcat_service = logcat.Logcat(ad, logcat.Config(clear_log=True))
        logcat_service.start()
        clear_adb_mock.assert_called_once_with()
        self.assertTrue(logcat_service.is_alive)
        logcat_service.pause()
        self.assertFalse(logcat_service.is_alive)
        stop_proc_mock.assert_called_with('process')
        self.assertIsNone(logcat_service._adb_logcat_process)
        clear_adb_mock.reset_mock()
        logcat_service.resume()
        self.assertTrue(logcat_service.is_alive)
        clear_adb_mock.assert_not_called()

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    @mock.patch(
        'mobly.controllers.android_device_lib.services.logcat.Logcat.clear_adb_log',
        return_value=mock_android_device.MockAdbProxy('1'))
    def test_logcat_service_create_excerpt(self, clear_adb_mock,
                                           stop_proc_mock, start_proc_mock,
                                           FastbootProxy, MockAdbProxy):
        mock_serial = '1'
        ad = android_device.AndroidDevice(serial=mock_serial)
        logcat_service = logcat.Logcat(ad)
        logcat_service.start()
        FILE_CONTENT = 'Some log.\n'
        with open(logcat_service.adb_logcat_file_path, 'w') as f:
            f.write(FILE_CONTENT)
        test_output_dir = os.path.join(self.tmp_dir, 'test_foo')
        mock_record = mock.MagicMock()
        mock_record.begin_time = 123
        test_run_info = runtime_test_info.RuntimeTestInfo(
            'test_foo', test_output_dir, mock_record)
        logcat_service.create_per_test_excerpt(test_run_info)
        expected_path1 = os.path.join(test_output_dir, 'test_foo-123',
                                      'adblog,fakemodel,1.txt')
        self.assertTrue(os.path.exists(expected_path1))
        self.AssertFileContains(FILE_CONTENT, expected_path1)
        self.assertFalse(os.path.exists(logcat_service.adb_logcat_file_path))
        # Generate some new logs and do another excerpt.
        FILE_CONTENT = 'Some more logs!!!\n'
        with open(logcat_service.adb_logcat_file_path, 'w') as f:
            f.write(FILE_CONTENT)
        test_output_dir = os.path.join(self.tmp_dir, 'test_bar')
        mock_record = mock.MagicMock()
        mock_record.begin_time = 456
        test_run_info = runtime_test_info.RuntimeTestInfo(
            'test_bar', test_output_dir, mock_record)
        logcat_service.create_per_test_excerpt(test_run_info)
        expected_path2 = os.path.join(test_output_dir, 'test_bar-456',
                                      'adblog,fakemodel,1.txt')
        self.assertTrue(os.path.exists(expected_path2))
        self.AssertFileContains(FILE_CONTENT, expected_path2)
        self.AssertFileDoesNotContain(FILE_CONTENT, expected_path1)
        self.assertFalse(os.path.exists(logcat_service.adb_logcat_file_path))

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch('mobly.utils.create_dir')
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_take_logcat_with_extra_params(self, stop_proc_mock,
                                           start_proc_mock, create_dir_mock,
                                           FastbootProxy, MockAdbProxy):
        """Verifies the steps of collecting adb logcat on an AndroidDevice
        object, including various function calls and the expected behaviors of
        the calls.
        """
        mock_serial = '1'
        ad = android_device.AndroidDevice(serial=mock_serial)
        configs = logcat.Config()
        configs.logcat_params = '-b radio'
        logcat_service = logcat.Logcat(ad, configs)
        logcat_service.start()
        # Verify start did the correct operations.
        self.assertTrue(logcat_service._adb_logcat_process)
        expected_log_path = os.path.join(logging.log_path,
                                         'AndroidDevice%s' % ad.serial,
                                         'adblog,fakemodel,%s.txt' % ad.serial)
        create_dir_mock.assert_called_with(os.path.dirname(expected_log_path))
        adb_cmd = '"adb" -s %s logcat -v threadtime -b radio >> %s'
        start_proc_mock.assert_called_with(
            adb_cmd % (ad.serial, '"%s"' % expected_log_path), shell=True)
        self.assertEqual(logcat_service.adb_logcat_file_path,
                         expected_log_path)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    def test_instantiation(self, MockFastboot, MockAdbProxy):
        """Verifies the AndroidDevice object's basic attributes are correctly
        set after instantiation.
        """
        mock_serial = 1
        ad = android_device.AndroidDevice(serial=mock_serial)
        logcat_service = logcat.Logcat(ad)
        self.assertIsNone(logcat_service._adb_logcat_process)
        self.assertIsNone(logcat_service.adb_logcat_file_path)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    @mock.patch(
        'mobly.logger.get_log_line_timestamp',
        return_value=MOCK_ADB_LOGCAT_END_TIME)
    def test_cat_adb_log(self, mock_timestamp_getter, stop_proc_mock,
                         start_proc_mock, FastbootProxy, MockAdbProxy):
        """Verifies that AndroidDevice.cat_adb_log loads the correct adb log
        file, locates the correct adb log lines within the given time range,
        and writes the lines to the correct output file.
        """
        mock_serial = '1'
        ad = android_device.AndroidDevice(serial=mock_serial)
        logcat_service = logcat.Logcat(ad)
        logcat_service._enable_logpersist()
        # Direct the log path of the ad to a temp dir to avoid racing.
        logcat_service._ad._log_path = self.tmp_dir
        # Expect error if attempted to cat adb log before starting adb logcat.
        expected_msg = ('.* Attempting to cat adb log when none'
                        ' has been collected.')
        with self.assertRaisesRegex(logcat.Error, expected_msg):
            logcat_service.cat_adb_log('some_test', MOCK_ADB_LOGCAT_BEGIN_TIME)
        logcat_service.start()
        utils.create_dir(ad.log_path)
        mock_adb_log_path = os.path.join(ad.log_path, 'adblog,%s,%s.txt' %
                                         (ad.model, ad.serial))
        with io.open(mock_adb_log_path, 'w', encoding='utf-8') as f:
            f.write(MOCK_ADB_LOGCAT)
        logcat_service.cat_adb_log('some_test', MOCK_ADB_LOGCAT_BEGIN_TIME)
        cat_file_path = os.path.join(
            ad.log_path, 'AdbLogExcerpts',
            ('some_test,02-29 14-02-20.123,%s,%s.txt') % (ad.model, ad.serial))
        with io.open(cat_file_path, 'r', encoding='utf-8') as f:
            actual_cat = f.read()
        self.assertEqual(actual_cat, ''.join(MOCK_ADB_LOGCAT_CAT_RESULT))
        # Stops adb logcat.
        logcat_service.stop()

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    @mock.patch(
        'mobly.logger.get_log_line_timestamp',
        return_value=MOCK_ADB_LOGCAT_END_TIME)
    def test_cat_adb_log_with_unicode(self, mock_timestamp_getter,
                                      stop_proc_mock, start_proc_mock,
                                      FastbootProxy, MockAdbProxy):
        """Verifies that AndroidDevice.cat_adb_log loads the correct adb log
        file, locates the correct adb log lines within the given time range,
        and writes the lines to the correct output file.
        """
        mock_serial = '1'
        ad = android_device.AndroidDevice(serial=mock_serial)
        logcat_service = logcat.Logcat(ad)
        logcat_service._enable_logpersist()
        # Direct the log path of the ad to a temp dir to avoid racing.
        logcat_service._ad._log_path = self.tmp_dir
        # Expect error if attempted to cat adb log before starting adb logcat.
        expected_msg = ('.* Attempting to cat adb log when none'
                        ' has been collected.')
        with self.assertRaisesRegex(logcat.Error, expected_msg):
            logcat_service.cat_adb_log('some_test', MOCK_ADB_LOGCAT_BEGIN_TIME)
        logcat_service.start()
        utils.create_dir(ad.log_path)
        mock_adb_log_path = os.path.join(ad.log_path, 'adblog,%s,%s.txt' %
                                         (ad.model, ad.serial))
        with io.open(mock_adb_log_path, 'w', encoding='utf-8') as f:
            f.write(MOCK_ADB_UNICODE_LOGCAT)
        logcat_service.cat_adb_log('some_test', MOCK_ADB_LOGCAT_BEGIN_TIME)
        cat_file_path = os.path.join(
            ad.log_path, 'AdbLogExcerpts',
            ('some_test,02-29 14-02-20.123,%s,%s.txt') % (ad.model, ad.serial))
        with io.open(cat_file_path, 'r', encoding='utf-8') as f:
            actual_cat = f.read()
        self.assertEqual(actual_cat,
                         ''.join(MOCK_ADB_UNICODE_LOGCAT_CAT_RESULT))
        # Stops adb logcat.
        logcat_service.stop()

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock.MagicMock())
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    def test__enable_logpersist_with_logpersist(self, MockFastboot,
                                                MockAdbProxy):
        mock_serial = '1'
        mock_adb_proxy = MockAdbProxy.return_value
        # Set getprop to return '1' to indicate the device is rootable.
        mock_adb_proxy.getprop.return_value = '1'
        mock_adb_proxy.has_shell_command.side_effect = lambda command: {
            'logpersist.start': True,
            'logpersist.stop': True, }[command]
        ad = android_device.AndroidDevice(serial=mock_serial)
        logcat_service = logcat.Logcat(ad)
        logcat_service._enable_logpersist()
        mock_adb_proxy.shell.assert_has_calls([
            mock.call('logpersist.stop --clear'),
            mock.call('logpersist.start'),
        ])

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock.MagicMock())
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    def test__enable_logpersist_with_missing_all_logpersist(
            self, MockFastboot, MockAdbProxy):
        def adb_shell_helper(command):
            if command == 'logpersist.start':
                raise MOCK_LOGPERSIST_START_MISSING_ADB_ERROR
            elif command == 'logpersist.stop --clear':
                raise MOCK_LOGPERSIST_STOP_MISSING_ADB_ERROR
            else:
                return ''

        mock_serial = '1'
        mock_adb_proxy = MockAdbProxy.return_value
        mock_adb_proxy.getprop.return_value = 'userdebug'
        mock_adb_proxy.has_shell_command.side_effect = lambda command: {
            'logpersist.start': False,
            'logpersist.stop': False, }[command]
        mock_adb_proxy.shell.side_effect = adb_shell_helper
        ad = android_device.AndroidDevice(serial=mock_serial)
        logcat_service = logcat.Logcat(ad)
        logcat_service._enable_logpersist()

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock.MagicMock())
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    def test__enable_logpersist_with_missing_logpersist_stop(
            self, MockFastboot, MockAdbProxy):
        def adb_shell_helper(command):
            if command == 'logpersist.stop --clear':
                raise MOCK_LOGPERSIST_STOP_MISSING_ADB_ERROR
            else:
                return ''

        mock_serial = '1'
        mock_adb_proxy = MockAdbProxy.return_value
        mock_adb_proxy.getprop.return_value = 'userdebug'
        mock_adb_proxy.has_shell_command.side_effect = lambda command: {
            'logpersist.start': True,
            'logpersist.stop': False, }[command]
        mock_adb_proxy.shell.side_effect = adb_shell_helper
        ad = android_device.AndroidDevice(serial=mock_serial)
        logcat_service = logcat.Logcat(ad)
        logcat_service._enable_logpersist()

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock.MagicMock())
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test__enable_logpersist_with_missing_logpersist_start(
            self, MockFastboot, MockAdbProxy):
        def adb_shell_helper(command):
            if command == 'logpersist.start':
                raise MOCK_LOGPERSIST_START_MISSING_ADB_ERROR
            else:
                return ''

        mock_serial = '1'
        mock_adb_proxy = MockAdbProxy.return_value
        mock_adb_proxy.getprop.return_value = 'userdebug'
        mock_adb_proxy.has_shell_command.side_effect = lambda command: {
            'logpersist.start': False,
            'logpersist.stop': True, }[command]
        mock_adb_proxy.shell.side_effect = adb_shell_helper
        ad = android_device.AndroidDevice(serial=mock_serial)
        logcat_service = logcat.Logcat(ad)
        logcat_service._enable_logpersist()

    @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy')
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    def test_clear_adb_log(self, MockFastboot, MockAdbProxy):
        mock_serial = '1'
        ad = android_device.AndroidDevice(serial=mock_serial)
        ad.adb.logcat = mock.MagicMock()
        ad.adb.logcat.side_effect = adb.AdbError(
            cmd='cmd',
            stdout='',
            stderr='failed to clear "main" log',
            ret_code=1)
        logcat_service = logcat.Logcat(ad)
        logcat_service.clear_adb_log()


if __name__ == '__main__':
    unittest.main()
