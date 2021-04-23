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
import unittest

from mobly import records
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
    'logpersist.stop --clear', b'',
    '/system/bin/sh: logpersist.stop: not found', 0)
MOCK_LOGPERSIST_START_MISSING_ADB_ERROR = adb.AdbError(
    'logpersist.start --clear', b'',
    b'/system/bin/sh: logpersist.stop: not found', 0)


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

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.utils.create_dir')
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(logcat.Logcat, '_open_logcat_file')
  @mock.patch('mobly.logger.get_log_file_timestamp')
  def test_start_and_stop(self, get_timestamp_mock, open_logcat_mock,
                          stop_proc_mock, start_proc_mock, create_dir_mock,
                          FastbootProxy, MockAdbProxy):
    """Verifies the steps of collecting adb logcat on an AndroidDevice
    object, including various function calls and the expected behaviors of
    the calls.
    """
    mock_serial = '1'
    get_timestamp_mock.return_value = '123'
    ad = android_device.AndroidDevice(serial=mock_serial)
    logcat_service = logcat.Logcat(ad)
    logcat_service.start()
    # Verify start did the correct operations.
    self.assertTrue(logcat_service._adb_logcat_process)
    expected_log_path = os.path.join(logging.log_path,
                                     'AndroidDevice%s' % ad.serial,
                                     'logcat,%s,fakemodel,123.txt' % ad.serial)
    create_dir_mock.assert_called_with(os.path.dirname(expected_log_path))
    adb_cmd = ' "adb" -s %s logcat -v threadtime -T 1  >> %s'
    start_proc_mock.assert_called_with(adb_cmd %
                                       (ad.serial, '"%s" ' % expected_log_path),
                                       shell=True)
    self.assertEqual(logcat_service.adb_logcat_file_path, expected_log_path)
    expected_msg = ('Logcat thread is already running, cannot start another'
                    ' one.')
    # Expect error if start is called back to back.
    with self.assertRaisesRegex(logcat.Error, expected_msg):
      logcat_service.start()
    # Verify stop did the correct operations.
    logcat_service.stop()
    stop_proc_mock.assert_called_with('process')
    self.assertIsNone(logcat_service._adb_logcat_process)
    self.assertEqual(logcat_service.adb_logcat_file_path, expected_log_path)

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.utils.create_dir')
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(logcat.Logcat, '_open_logcat_file')
  def test_update_config(self, open_logcat_mock, stop_proc_mock,
                         start_proc_mock, create_dir_mock, FastbootProxy,
                         MockAdbProxy):
    mock_serial = '1'
    ad = android_device.AndroidDevice(serial=mock_serial)
    logcat_service = logcat.Logcat(ad)
    logcat_service.start()
    logcat_service.stop()
    new_log_params = '-a -b -c'
    new_file_path = 'some/path/log.txt'
    new_config = logcat.Config(logcat_params=new_log_params,
                               output_file_path=new_file_path)
    logcat_service.update_config(new_config)
    logcat_service.start()
    self.assertTrue(logcat_service._adb_logcat_process)
    create_dir_mock.assert_has_calls([mock.call('some/path')])
    expected_adb_cmd = (' "adb" -s 1 logcat -v threadtime -T 1 -a -b -c >> '
                        '"some/path/log.txt" ')
    start_proc_mock.assert_called_with(expected_adb_cmd, shell=True)
    self.assertEqual(logcat_service.adb_logcat_file_path, 'some/path/log.txt')
    logcat_service.stop()

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.utils.create_dir')
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(logcat.Logcat, '_open_logcat_file')
  def test_update_config_while_running(self, open_logcat_mock, stop_proc_mock,
                                       start_proc_mock, create_dir_mock,
                                       FastbootProxy, MockAdbProxy):
    mock_serial = '1'
    ad = android_device.AndroidDevice(serial=mock_serial)
    logcat_service = logcat.Logcat(ad)
    logcat_service.start()
    new_config = logcat.Config(logcat_params='-blah',
                               output_file_path='some/path/file.txt')
    with self.assertRaisesRegex(
        logcat.Error,
        'Logcat thread is already running, cannot start another one'):
      logcat_service.update_config(new_config)
    self.assertTrue(logcat_service.is_alive)
    logcat_service.stop()

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.utils.create_dir')
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(logcat.Logcat, '_open_logcat_file')
  @mock.patch(
      'mobly.controllers.android_device_lib.services.logcat.Logcat.clear_adb_log',
      return_value=mock_android_device.MockAdbProxy('1'))
  def test_pause_and_resume(self, clear_adb_mock, open_logcat_mock,
                            stop_proc_mock, start_proc_mock, create_dir_mock,
                            FastbootProxy, MockAdbProxy):
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
    logcat_service.stop()

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch(
      'mobly.controllers.android_device_lib.services.logcat.Logcat.clear_adb_log',
      return_value=mock_android_device.MockAdbProxy('1'))
  def test_logcat_service_create_output_excerpts(self, clear_adb_mock,
                                                 stop_proc_mock,
                                                 start_proc_mock, FastbootProxy,
                                                 MockAdbProxy):
    mock_serial = '1'
    ad = android_device.AndroidDevice(serial=mock_serial)
    logcat_service = logcat.Logcat(ad)
    logcat_service._start()

    def _write_logcat_file_and_assert_excerpts_exists(logcat_file_content,
                                                      test_begin_time,
                                                      test_name):
      with open(logcat_service.adb_logcat_file_path, 'a') as f:
        f.write(logcat_file_content)
      test_output_dir = os.path.join(self.tmp_dir, test_name)
      mock_record = records.TestResultRecord(test_name)
      mock_record.begin_time = test_begin_time
      mock_record.signature = f'{test_name}-{test_begin_time}'
      test_run_info = runtime_test_info.RuntimeTestInfo(test_name,
                                                        test_output_dir,
                                                        mock_record)
      actual_path = logcat_service.create_output_excerpts(test_run_info)[0]
      expected_path = os.path.join(
          test_output_dir, '{test_name}-{test_begin_time}'.format(
              test_name=test_name, test_begin_time=test_begin_time),
          'logcat,{mock_serial},fakemodel,{test_name}-{test_begin_time}.txt'.
          format(mock_serial=mock_serial,
                 test_name=test_name,
                 test_begin_time=test_begin_time))
      self.assertEqual(actual_path, expected_path)
      self.assertTrue(os.path.exists(expected_path))
      return expected_path

    # Generate logs before the file pointer is created.
    # This message will not be captured in the excerpt.
    NOT_IN_EXCERPT = 'Not in excerpt.\n'
    with open(logcat_service.adb_logcat_file_path, 'a') as f:
      f.write(NOT_IN_EXCERPT)
    # With the file pointer created, generate logs and make an excerpt.
    logcat_service._open_logcat_file()
    FILE_CONTENT = 'Some log.\n'
    expected_path1 = _write_logcat_file_and_assert_excerpts_exists(
        logcat_file_content=FILE_CONTENT,
        test_begin_time=123,
        test_name='test_foo',
    )
    self.AssertFileContains(FILE_CONTENT, expected_path1)
    self.AssertFileDoesNotContain(NOT_IN_EXCERPT, expected_path1)
    # Generate some new logs and do another excerpt.
    FILE_CONTENT = 'Some more logs!!!\n'
    expected_path2 = _write_logcat_file_and_assert_excerpts_exists(
        logcat_file_content=FILE_CONTENT,
        test_begin_time=456,
        test_name='test_bar',
    )
    self.AssertFileContains(FILE_CONTENT, expected_path2)
    self.AssertFileDoesNotContain(FILE_CONTENT, expected_path1)
    # Simulate devices accidentally go offline, logcat service stopped.
    logcat_service.stop()
    FILE_CONTENT = 'Whatever logs\n'
    expected_path3 = _write_logcat_file_and_assert_excerpts_exists(
        logcat_file_content=FILE_CONTENT,
        test_begin_time=789,
        test_name='test_offline',
    )
    self.assertEqual(os.stat(expected_path3).st_size, 0)

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.utils.create_dir')
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(logcat.Logcat, '_open_logcat_file')
  @mock.patch('mobly.logger.get_log_file_timestamp')
  def test_take_logcat_with_extra_params(self, get_timestamp_mock,
                                         open_logcat_mock, stop_proc_mock,
                                         start_proc_mock, create_dir_mock,
                                         FastbootProxy, MockAdbProxy):
    """Verifies the steps of collecting adb logcat on an AndroidDevice
    object, including various function calls and the expected behaviors of
    the calls.
    """
    mock_serial = '1'
    get_timestamp_mock.return_value = '123'
    ad = android_device.AndroidDevice(serial=mock_serial)
    configs = logcat.Config()
    configs.logcat_params = '-b radio'
    logcat_service = logcat.Logcat(ad, configs)
    logcat_service.start()
    # Verify start did the correct operations.
    self.assertTrue(logcat_service._adb_logcat_process)
    expected_log_path = os.path.join(logging.log_path,
                                     'AndroidDevice%s' % ad.serial,
                                     'logcat,%s,fakemodel,123.txt' % ad.serial)
    create_dir_mock.assert_called_with(os.path.dirname(expected_log_path))
    adb_cmd = ' "adb" -s %s logcat -v threadtime -T 1 -b radio >> %s'
    start_proc_mock.assert_called_with(adb_cmd %
                                       (ad.serial, '"%s" ' % expected_log_path),
                                       shell=True)
    self.assertEqual(logcat_service.adb_logcat_file_path, expected_log_path)
    logcat_service.stop()

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
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

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock.MagicMock())
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  def test__enable_logpersist_with_logpersist(self, MockFastboot, MockAdbProxy):
    mock_serial = '1'
    mock_adb_proxy = MockAdbProxy.return_value
    mock_adb_proxy.getprops.return_value = {
        'ro.build.id': 'AB42',
        'ro.build.type': 'userdebug',
        'ro.debuggable': '1',
    }
    mock_adb_proxy.has_shell_command.side_effect = lambda command: {
        'logpersist.start': True,
        'logpersist.stop': True,
    }[command]
    ad = android_device.AndroidDevice(serial=mock_serial)
    logcat_service = logcat.Logcat(ad)
    logcat_service._enable_logpersist()
    mock_adb_proxy.shell.assert_has_calls([
        mock.call('logpersist.stop --clear'),
        mock.call('logpersist.start'),
    ])

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock.MagicMock())
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  def test__enable_logpersist_with_user_build_device(self, MockFastboot,
                                                     MockAdbProxy):
    mock_serial = '1'
    mock_adb_proxy = MockAdbProxy.return_value
    mock_adb_proxy.getprops.return_value = {
        'ro.build.id': 'AB42',
        'ro.build.type': 'user',
        'ro.debuggable': '0',
    }
    mock_adb_proxy.has_shell_command.side_effect = lambda command: {
        'logpersist.start': True,
        'logpersist.stop': True,
    }[command]
    ad = android_device.AndroidDevice(serial=mock_serial)
    logcat_service = logcat.Logcat(ad)
    logcat_service._enable_logpersist()
    mock_adb_proxy.shell.assert_not_called()

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock.MagicMock())
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  def test__enable_logpersist_with_missing_all_logpersist(
      self, MockFastboot, MockAdbProxy):

    def adb_shell_helper(command):
      if command == 'logpersist.start':
        raise MOCK_LOGPERSIST_START_MISSING_ADB_ERROR
      elif command == 'logpersist.stop --clear':
        raise MOCK_LOGPERSIST_STOP_MISSING_ADB_ERROR
      else:
        return b''

    mock_serial = '1'
    mock_adb_proxy = MockAdbProxy.return_value
    mock_adb_proxy.getprops.return_value = {
        'ro.build.id': 'AB42',
        'ro.build.type': 'userdebug',
        'ro.debuggable': '1',
    }
    mock_adb_proxy.has_shell_command.side_effect = lambda command: {
        'logpersist.start': False,
        'logpersist.stop': False,
    }[command]
    mock_adb_proxy.shell.side_effect = adb_shell_helper
    ad = android_device.AndroidDevice(serial=mock_serial)
    logcat_service = logcat.Logcat(ad)
    logcat_service._enable_logpersist()
    mock_adb_proxy.shell.assert_not_called()

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock.MagicMock())
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  def test__enable_logpersist_with_missing_logpersist_stop(
      self, MockFastboot, MockAdbProxy):

    def adb_shell_helper(command):
      if command == 'logpersist.stop --clear':
        raise MOCK_LOGPERSIST_STOP_MISSING_ADB_ERROR
      else:
        return b''

    mock_serial = '1'
    mock_adb_proxy = MockAdbProxy.return_value
    mock_adb_proxy.getprops.return_value = {
        'ro.build.id': 'AB42',
        'ro.build.type': 'userdebug',
        'ro.debuggable': '1',
    }
    mock_adb_proxy.has_shell_command.side_effect = lambda command: {
        'logpersist.start': True,
        'logpersist.stop': False,
    }[command]
    mock_adb_proxy.shell.side_effect = adb_shell_helper
    ad = android_device.AndroidDevice(serial=mock_serial)
    logcat_service = logcat.Logcat(ad)
    logcat_service._enable_logpersist()
    mock_adb_proxy.shell.assert_has_calls([
        mock.call('logpersist.stop --clear'),
    ])

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock.MagicMock())
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  def test__enable_logpersist_with_missing_logpersist_start(
      self, MockFastboot, MockAdbProxy):

    def adb_shell_helper(command):
      if command == 'logpersist.start':
        raise MOCK_LOGPERSIST_START_MISSING_ADB_ERROR
      else:
        return b''

    mock_serial = '1'
    mock_adb_proxy = MockAdbProxy.return_value
    mock_adb_proxy.getprops.return_value = {
        'ro.build.id': 'AB42',
        'ro.build.type': 'userdebug',
        'ro.debuggable': '1',
    }
    mock_adb_proxy.has_shell_command.side_effect = lambda command: {
        'logpersist.start': False,
        'logpersist.stop': True,
    }[command]
    mock_adb_proxy.shell.side_effect = adb_shell_helper
    ad = android_device.AndroidDevice(serial=mock_serial)
    logcat_service = logcat.Logcat(ad)
    logcat_service._enable_logpersist()
    mock_adb_proxy.shell.assert_not_called()

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy')
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  def test_clear_adb_log(self, MockFastboot, MockAdbProxy):
    mock_serial = '1'
    ad = android_device.AndroidDevice(serial=mock_serial)
    ad.adb.logcat = mock.MagicMock()
    ad.adb.logcat.side_effect = adb.AdbError(
        cmd='cmd', stdout=b'', stderr=b'failed to clear "main" log', ret_code=1)
    logcat_service = logcat.Logcat(ad)
    logcat_service.clear_adb_log()


if __name__ == '__main__':
  unittest.main()
