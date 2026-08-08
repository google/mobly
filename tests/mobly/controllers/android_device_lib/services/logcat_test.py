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

import logging
import os
import re
import shutil
import tempfile
import threading
import time
import unittest
from unittest import mock

from mobly import records
from mobly import runtime_test_info
from mobly.controllers import android_device
from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import logcat_processor
from mobly.controllers.android_device_lib.services import logcat
from tests.lib import mock_android_device

# The expected result of the cat adb operation.
MOCK_ADB_LOGCAT_CAT_RESULT = [
    '02-29 14:02:21.456  4454  Something\n',
    '02-29 14:02:21.789  4454  Something again\n',
]
# A mocked piece of adb logcat output.
MOCK_ADB_LOGCAT = (
    '02-29 14:02:19.123  4454  Nothing\n'
    '%s'
    '02-29 14:02:22.123  4454  Something again and again\n'
) % ''.join(MOCK_ADB_LOGCAT_CAT_RESULT)
# The expected result of the cat adb operation.
MOCK_ADB_UNICODE_LOGCAT_CAT_RESULT = [
    '02-29 14:02:21.456  4454  Something \u901a\n',
    '02-29 14:02:21.789  4454  Something again\n',
]
# A mocked piece of adb logcat output.
MOCK_ADB_UNICODE_LOGCAT = (
    '02-29 14:02:19.123  4454  Nothing\n'
    '%s'
    '02-29 14:02:22.123  4454  Something again and again\n'
) % ''.join(MOCK_ADB_UNICODE_LOGCAT_CAT_RESULT)

# Mock start and end time of the adb cat.
MOCK_ADB_LOGCAT_BEGIN_TIME = '02-29 14:02:20.123'
MOCK_ADB_LOGCAT_END_TIME = '02-29 14:02:22.000'

# Mock AdbError for missing logpersist scripts
MOCK_LOGPERSIST_STOP_MISSING_ADB_ERROR = adb.AdbError(
    'logpersist.stop --clear',
    b'',
    '/system/bin/sh: logpersist.stop: not found',
    0,
)
MOCK_LOGPERSIST_START_MISSING_ADB_ERROR = adb.AdbError(
    'logpersist.start --clear',
    b'',
    b'/system/bin/sh: logpersist.stop: not found',
    0,
)

_DATE_COMMAND = ['date', r'+%Y-%m-%d\ %H:%M:%S.%3N']


class LogcatTest(unittest.TestCase):
  """Tests for Logcat service and its integration with AndroidDevice."""

  def setUp(self):
    # Set log_path to logging since mobly logger setup is not called.
    if not hasattr(logging, 'log_path'):
      setattr(logging, 'log_path', '/tmp/logs')
    # Creates a temp dir to be used by tests in this test class.
    self.tmp_dir = tempfile.mkdtemp()

  def tearDown(self):
    """Removes the temp dir."""
    shutil.rmtree(self.tmp_dir)

  def AssertFileContains(self, content, file_path):
    with open(file_path, 'r', newline='') as f:
      output = f.read()
    self.assertIn(content, output)

  def AssertFileDoesNotContain(self, content, file_path):
    with open(file_path, 'r', newline='') as f:
      output = f.read()
    self.assertNotIn(content, output)

  @mock.patch(
      'mobly.controllers.android_device_lib.adb.AdbProxy',
      return_value=mock_android_device.MockAdbProxy('1'),
  )
  @mock.patch(
      'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
      return_value=mock_android_device.MockFastbootProxy('1'),
  )
  @mock.patch('mobly.utils.create_dir')
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(logcat.Logcat, '_open_logcat_file')
  @mock.patch('mobly.logger.get_log_file_timestamp')
  def test_start_and_stop(
      self,
      get_timestamp_mock,
      open_logcat_mock,
      stop_proc_mock,
      start_proc_mock,
      create_dir_mock,
      FastbootProxy,
      MockAdbProxy,
  ):
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
    expected_log_path = os.path.join(
        logging.log_path,
        'AndroidDevice%s' % ad.serial,
        'logcat,%s,fakemodel,123.txt' % ad.serial,
    )
    create_dir_mock.assert_called_with(os.path.dirname(expected_log_path))
    adb_cmd = ' "adb" -s %s logcat -v threadtime -T "1"  >> %s'
    start_proc_mock.assert_called_with(
        adb_cmd % (ad.serial, '"%s" ' % expected_log_path), shell=True
    )
    self.assertEqual(logcat_service.adb_logcat_file_path, expected_log_path)
    expected_msg = 'Logcat thread is already running, cannot start another one.'
    # Expect error if start is called back to back.
    with self.assertRaisesRegex(logcat.Error, expected_msg):
      logcat_service.start()
    # Verify stop did the correct operations.
    logcat_service.stop()
    stop_proc_mock.assert_called_with('process')
    self.assertIsNone(logcat_service._adb_logcat_process)
    self.assertEqual(logcat_service.adb_logcat_file_path, expected_log_path)

  @mock.patch(
      'mobly.controllers.android_device_lib.adb.AdbProxy',
      return_value=mock_android_device.MockAdbProxy('1', adb_detectable=False),
  )
  @mock.patch(
      'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
      return_value=mock_android_device.MockFastbootProxy('1'),
  )
  @mock.patch('mobly.utils.start_standing_subprocess')
  @mock.patch(
      'mobly.controllers.android_device.list_fastboot_devices', return_value='1'
  )
  def test_start_in_fastboot_mode(
      self, _, start_proc_mock, FastbootProxy, MockAdbProxy
  ):
    mock_serial = '1'
    ad = android_device.AndroidDevice(serial=mock_serial)
    logcat_service = logcat.Logcat(ad)
    logcat_service.start()
    # Verify start is not performed
    self.assertFalse(logcat_service._adb_logcat_process)
    start_proc_mock.assert_not_called()

  @mock.patch(
      'mobly.controllers.android_device_lib.adb.AdbProxy',
      return_value=mock_android_device.MockAdbProxy('1'),
  )
  @mock.patch(
      'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
      return_value=mock_android_device.MockFastbootProxy('1'),
  )
  @mock.patch('mobly.utils.create_dir')
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(logcat.Logcat, '_open_logcat_file')
  def test_update_config(
      self,
      open_logcat_mock,
      stop_proc_mock,
      start_proc_mock,
      create_dir_mock,
      FastbootProxy,
      MockAdbProxy,
  ):
    mock_serial = '1'
    ad = android_device.AndroidDevice(serial=mock_serial)
    logcat_service = logcat.Logcat(ad)
    logcat_service.start()
    logcat_service.stop()
    new_log_params = '-a -b -c'
    new_file_path = 'some/path/log.txt'
    new_config = logcat.Config(
        logcat_params=new_log_params, output_file_path=new_file_path
    )
    logcat_service.update_config(new_config)
    logcat_service.start()
    self.assertTrue(logcat_service._adb_logcat_process)
    create_dir_mock.assert_has_calls([mock.call('some/path')])
    expected_adb_cmd = (
        ' "adb" -s 1 logcat -v threadtime -T "1" -a -b -c >>'
        ' "some/path/log.txt" '
    )
    start_proc_mock.assert_called_with(expected_adb_cmd, shell=True)
    self.assertEqual(logcat_service.adb_logcat_file_path, 'some/path/log.txt')
    logcat_service.stop()

  @mock.patch(
      'mobly.controllers.android_device_lib.adb.AdbProxy',
      return_value=mock_android_device.MockAdbProxy('1'),
  )
  @mock.patch(
      'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
      return_value=mock_android_device.MockFastbootProxy('1'),
  )
  @mock.patch('mobly.utils.create_dir')
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(logcat.Logcat, '_open_logcat_file')
  def test_update_config_while_running(
      self,
      open_logcat_mock,
      stop_proc_mock,
      start_proc_mock,
      create_dir_mock,
      FastbootProxy,
      MockAdbProxy,
  ):
    mock_serial = '1'
    ad = android_device.AndroidDevice(serial=mock_serial)
    logcat_service = logcat.Logcat(ad)
    logcat_service.start()
    new_config = logcat.Config(
        logcat_params='-blah', output_file_path='some/path/file.txt'
    )
    with self.assertRaisesRegex(
        logcat.Error,
        'Logcat thread is already running, cannot start another one',
    ):
      logcat_service.update_config(new_config)
    self.assertTrue(logcat_service.is_alive)
    logcat_service.stop()

  def _adb_shell_logic(self, cmd, date_result=None, raise_error=False):
    if cmd == _DATE_COMMAND:
      if raise_error:
        raise adb.AdbError(cmd, b'', b'Device is disconnected', 1)
      return date_result.encode('utf-8')
    return b''

  def _pause_and_resume_logcat_service(
      self,
      logcat_service,
      date,
      state,
      expected_log_path,
      ad_serial,
      stop_proc_mock,
      start_proc_mock,
      clear_adb_mock,
  ):
    """Pauses and resumes the log collection and verifies the operations."""
    # Pause the logcat collection at time stamp `date`.
    state['date_result'] = date
    logcat_service.pause()
    self.assertFalse(logcat_service.is_alive)
    stop_proc_mock.assert_called_with('process')
    self.assertIsNone(logcat_service._adb_logcat_process)
    clear_adb_mock.reset_mock()

    # Resume the logcat collection, which should look back to time
    # stamp `date`.
    logcat_service.resume()
    self.assertTrue(logcat_service.is_alive)
    clear_adb_mock.assert_not_called()
    adb_cmd = ' "adb" -s %s logcat -v threadtime -T "' + date + '"  >> %s'
    start_proc_mock.assert_called_with(
        adb_cmd % (ad_serial, '"%s" ' % expected_log_path), shell=True
    )
    self.assertIsNone(logcat_service._last_connection_time)

  @mock.patch(
      'mobly.controllers.android_device_lib.adb.AdbProxy',
      return_value=mock_android_device.MockAdbProxy('1'),
  )
  @mock.patch(
      'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
      return_value=mock_android_device.MockFastbootProxy('1'),
  )
  @mock.patch('mobly.utils.create_dir')
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(logcat.Logcat, '_open_logcat_file')
  @mock.patch(
      'mobly.controllers.android_device_lib.services.logcat.Logcat.clear_adb_log',
      return_value=mock_android_device.MockAdbProxy('1'),
  )
  @mock.patch('mobly.logger.get_log_file_timestamp')
  def test_pause_and_resume(
      self,
      get_timestamp_mock,
      clear_adb_mock,
      open_logcat_mock,
      stop_proc_mock,
      start_proc_mock,
      create_dir_mock,
      FastbootProxy,
      MockAdbProxy,
  ):
    # The test will pause and resume the log collection twice. The
    # resume operation is supposed to request the log messages since the
    # log collection got paused.

    state = {'date_result': ''}
    date_result_first_pause = '2026-01-14 17:01:02.342'
    date_result_second_pause = '2026-01-14 17:03:04.789'

    adb_instance = MockAdbProxy.return_value
    adb_instance.shell = mock.MagicMock()
    adb_instance.has_shell_command = mock.MagicMock(return_value=True)

    adb_instance.shell.side_effect = (
        lambda cmd, *args, **kwargs: self._adb_shell_logic(
            cmd, state['date_result']
        )
    )

    # Set up the logcat instance.
    mock_serial = '1'
    ad = android_device.AndroidDevice(serial=mock_serial)
    get_timestamp_mock.return_value = '123'
    configs = logcat.Config(clear_log=True)
    logcat_service = logcat.Logcat(ad, configs)
    logcat_service.start()
    expected_log_path = os.path.join(
        logging.log_path,
        'AndroidDevice%s' % ad.serial,
        'logcat,%s,fakemodel,123.txt' % ad.serial,
    )

    # We expect that the first logcat invocation happens with time "1"
    # to include all previously generated log messages.
    adb_cmd = ' "adb" -s %s logcat -v threadtime -T "1"  >> %s'
    start_proc_mock.assert_called_with(
        adb_cmd % (ad.serial, '"%s" ' % expected_log_path), shell=True
    )

    clear_adb_mock.assert_called_once_with()
    self.assertTrue(logcat_service.is_alive)

    # First pause / resume iteration
    self._pause_and_resume_logcat_service(
        logcat_service,
        date_result_first_pause,
        state,
        expected_log_path,
        ad.serial,
        stop_proc_mock,
        start_proc_mock,
        clear_adb_mock,
    )

    # Second pause / resume iteration
    self._pause_and_resume_logcat_service(
        logcat_service,
        date_result_second_pause,
        state,
        expected_log_path,
        ad.serial,
        stop_proc_mock,
        start_proc_mock,
        clear_adb_mock,
    )

    logcat_service.stop()

  @mock.patch(
      'mobly.controllers.android_device_lib.adb.AdbProxy',
      return_value=mock_android_device.MockAdbProxy('1'),
  )
  @mock.patch(
      'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
      return_value=mock_android_device.MockFastbootProxy('1'),
  )
  @mock.patch('mobly.utils.create_dir')
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(logcat.Logcat, '_open_logcat_file')
  @mock.patch(
      'mobly.controllers.android_device_lib.services.logcat.Logcat.clear_adb_log',
      return_value=mock_android_device.MockAdbProxy('1'),
  )
  @mock.patch('mobly.logger.get_log_file_timestamp')
  def test_pause_and_resume_while_raising_exception_when_getting_pause_time(
      self,
      get_timestamp_mock,
      clear_adb_mock,
      open_logcat_mock,
      stop_proc_mock,
      start_proc_mock,
      create_dir_mock,
      FastbootProxy,
      MockAdbProxy,
  ):
    # The test will pause and resume the log collection, but it will
    # fail to retrieve a date while pausing the log collection. The log
    # collection is expected to resume back from the earliest time stamp
    # "1".

    adb_instance = MockAdbProxy.return_value
    adb_instance.shell = mock.MagicMock()
    adb_instance.has_shell_command = mock.MagicMock(return_value=True)

    adb_instance.shell.side_effect = (
        lambda cmd, *args, **kwargs: self._adb_shell_logic(
            cmd, raise_error=True
        )
    )

    # Set up the logcat instance.
    mock_serial = '1'
    ad = android_device.AndroidDevice(serial=mock_serial)
    get_timestamp_mock.return_value = '123'
    configs = logcat.Config(clear_log=True)
    logcat_service = logcat.Logcat(ad, configs)
    logcat_service.start()
    expected_log_path = os.path.join(
        logging.log_path,
        'AndroidDevice%s' % ad.serial,
        'logcat,%s,fakemodel,123.txt' % ad.serial,
    )

    # We expect that the first logcat invocation happens with time "1"
    # to include all previously generated log messages.
    adb_cmd = ' "adb" -s %s logcat -v threadtime -T "1"  >> %s'
    start_proc_mock.assert_called_with(
        adb_cmd % (ad.serial, '"%s" ' % expected_log_path), shell=True
    )

    clear_adb_mock.assert_called_once_with()
    self.assertTrue(logcat_service.is_alive)

    # Pause should fail to retrieve a valid date
    logcat_service.pause()
    self.assertFalse(logcat_service.is_alive)
    stop_proc_mock.assert_called_with('process')
    self.assertIsNone(logcat_service._adb_logcat_process)
    clear_adb_mock.reset_mock()

    # Resume should start with the first logcat message again
    logcat_service.resume()
    self.assertTrue(logcat_service.is_alive)
    clear_adb_mock.assert_not_called()
    adb_cmd = ' "adb" -s %s logcat -v threadtime -T "1"  >> %s'
    start_proc_mock.assert_called_with(
        adb_cmd % (ad.serial, '"%s" ' % expected_log_path), shell=True
    )

    logcat_service.stop()

  @mock.patch(
      'mobly.controllers.android_device_lib.adb.AdbProxy',
      return_value=mock_android_device.MockAdbProxy('1'),
  )
  @mock.patch(
      'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
      return_value=mock_android_device.MockFastbootProxy('1'),
  )
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch(
      'mobly.controllers.android_device_lib.services.logcat.Logcat.clear_adb_log',
      return_value=mock_android_device.MockAdbProxy('1'),
  )
  def test_logcat_service_create_output_excerpts(
      self,
      clear_adb_mock,
      stop_proc_mock,
      start_proc_mock,
      FastbootProxy,
      MockAdbProxy,
  ):
    mock_serial = '1'
    ad = android_device.AndroidDevice(serial=mock_serial)
    logcat_service = logcat.Logcat(ad)
    logcat_service._start()

    def _write_logcat_file_and_assert_excerpts_exists(
        logcat_file_content, test_begin_time, test_name
    ):
      with open(logcat_service.adb_logcat_file_path, 'a', newline='') as f:
        f.write(logcat_file_content)
      test_output_dir = os.path.join(self.tmp_dir, test_name)
      mock_record = records.TestResultRecord(test_name)
      mock_record.begin_time = test_begin_time
      mock_record.signature = f'{test_name}-{test_begin_time}'
      test_run_info = runtime_test_info.RuntimeTestInfo(
          test_name, test_output_dir, mock_record
      )
      actual_path = logcat_service.create_output_excerpts(test_run_info)[0]
      expected_path = os.path.join(
          test_output_dir,
          '{test_name}-{test_begin_time}'.format(
              test_name=test_name, test_begin_time=test_begin_time
          ),
          'logcat,{mock_serial},fakemodel,{test_name}-{test_begin_time}.txt'.format(
              mock_serial=mock_serial,
              test_name=test_name,
              test_begin_time=test_begin_time,
          ),
      )
      self.assertEqual(actual_path, expected_path)
      self.assertTrue(os.path.exists(expected_path))
      return expected_path

    # Generate logs before the file pointer is created.
    # This message will not be captured in the excerpt.
    NOT_IN_EXCERPT = 'Not in excerpt.\n'
    with open(logcat_service.adb_logcat_file_path, 'a', newline='') as f:
      f.write(NOT_IN_EXCERPT)
    # With the file pointer created, generate logs and make an excerpt.
    logcat_service._open_logcat_file()
    # Both CR and LF should be preserved no matter the operating system.
    FILE_CONTENT = 'Some log.\r\nAnother log.\n'
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

  @mock.patch(
      'mobly.controllers.android_device_lib.adb.AdbProxy',
      return_value=mock_android_device.MockAdbProxy('1'),
  )
  @mock.patch(
      'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
      return_value=mock_android_device.MockFastbootProxy('1'),
  )
  @mock.patch('mobly.utils.create_dir')
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(logcat.Logcat, '_open_logcat_file')
  @mock.patch('mobly.logger.get_log_file_timestamp')
  def test_take_logcat_with_extra_params(
      self,
      get_timestamp_mock,
      open_logcat_mock,
      stop_proc_mock,
      start_proc_mock,
      create_dir_mock,
      FastbootProxy,
      MockAdbProxy,
  ):
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
    expected_log_path = os.path.join(
        logging.log_path,
        'AndroidDevice%s' % ad.serial,
        'logcat,%s,fakemodel,123.txt' % ad.serial,
    )
    create_dir_mock.assert_called_with(os.path.dirname(expected_log_path))
    adb_cmd = ' "adb" -s %s logcat -v threadtime -T "1" -b radio >> %s'
    start_proc_mock.assert_called_with(
        adb_cmd % (ad.serial, '"%s" ' % expected_log_path), shell=True
    )
    self.assertEqual(logcat_service.adb_logcat_file_path, expected_log_path)
    logcat_service.stop()

  @mock.patch(
      'mobly.controllers.android_device_lib.adb.AdbProxy',
      return_value=mock_android_device.MockAdbProxy('1'),
  )
  @mock.patch(
      'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
      return_value=mock_android_device.MockFastbootProxy('1'),
  )
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
      return_value=mock.MagicMock(),
  )
  @mock.patch(
      'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
      return_value=mock_android_device.MockFastbootProxy('1'),
  )
  def test__enable_logpersist_with_logpersist(self, MockFastboot, MockAdbProxy):
    mock_serial = '1'
    mock_adb_proxy = MockAdbProxy.return_value
    mock_adb_proxy.devices.return_value = f'{mock_serial}\tdevice'.encode()
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
    mock_adb_proxy.shell.assert_has_calls(
        [
            mock.call('logpersist.stop --clear'),
            mock.call('logpersist.start'),
        ]
    )

  @mock.patch(
      'mobly.controllers.android_device_lib.adb.AdbProxy',
      return_value=mock.MagicMock(),
  )
  @mock.patch(
      'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
      return_value=mock_android_device.MockFastbootProxy('1'),
  )
  def test__enable_logpersist_with_user_build_device(
      self, MockFastboot, MockAdbProxy
  ):
    mock_serial = '1'
    mock_adb_proxy = MockAdbProxy.return_value
    mock_adb_proxy.devices.return_value = f'{mock_serial}\tdevice'.encode()
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

  @mock.patch(
      'mobly.controllers.android_device_lib.adb.AdbProxy',
      return_value=mock.MagicMock(),
  )
  @mock.patch(
      'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
      return_value=mock_android_device.MockFastbootProxy('1'),
  )
  def test__enable_logpersist_with_missing_all_logpersist(
      self, MockFastboot, MockAdbProxy
  ):
    def adb_shell_helper(command):
      if command == 'logpersist.start':
        raise MOCK_LOGPERSIST_START_MISSING_ADB_ERROR
      elif command == 'logpersist.stop --clear':
        raise MOCK_LOGPERSIST_STOP_MISSING_ADB_ERROR
      else:
        return b''

    mock_serial = '1'
    mock_adb_proxy = MockAdbProxy.return_value
    mock_adb_proxy.devices.return_value = f'{mock_serial}\tdevice'.encode()
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

  @mock.patch(
      'mobly.controllers.android_device_lib.adb.AdbProxy',
      return_value=mock.MagicMock(),
  )
  @mock.patch(
      'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
      return_value=mock_android_device.MockFastbootProxy('1'),
  )
  def test__enable_logpersist_with_missing_logpersist_stop(
      self, MockFastboot, MockAdbProxy
  ):
    def adb_shell_helper(command):
      if command == 'logpersist.stop --clear':
        raise MOCK_LOGPERSIST_STOP_MISSING_ADB_ERROR
      else:
        return b''

    mock_serial = '1'
    mock_adb_proxy = MockAdbProxy.return_value
    mock_adb_proxy.devices.return_value = f'{mock_serial}\tdevice'.encode()
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
    mock_adb_proxy.shell.assert_has_calls(
        [
            mock.call('logpersist.stop --clear'),
        ]
    )

  @mock.patch(
      'mobly.controllers.android_device_lib.adb.AdbProxy',
      return_value=mock.MagicMock(),
  )
  @mock.patch(
      'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
      return_value=mock_android_device.MockFastbootProxy('1'),
  )
  def test__enable_logpersist_with_missing_logpersist_start(
      self, MockFastboot, MockAdbProxy
  ):
    def adb_shell_helper(command):
      if command == 'logpersist.start':
        raise MOCK_LOGPERSIST_START_MISSING_ADB_ERROR
      else:
        return b''

    mock_serial = '1'
    mock_adb_proxy = MockAdbProxy.return_value
    mock_adb_proxy.devices.return_value = f'{mock_serial}\tdevice'.encode()
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

  @mock.patch(
      'mobly.controllers.android_device_lib.adb.AdbProxy',
      return_value=mock_android_device.MockAdbProxy('1'),
  )
  @mock.patch(
      'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
      return_value=mock_android_device.MockFastbootProxy('1'),
  )
  def test_clear_adb_log(self, MockFastboot, MockAdbProxy):
    mock_serial = '1'
    ad = android_device.AndroidDevice(serial=mock_serial)
    ad.adb.logcat = mock.MagicMock()
    ad.adb.logcat.side_effect = adb.AdbError(
        cmd='cmd', stdout=b'', stderr=b'failed to clear "main" log', ret_code=1
    )
    logcat_service = logcat.Logcat(ad)
    logcat_service.clear_adb_log()


SAMPLE_REALISTIC_LOGCAT = (
    '--------- beginning of system\n'
    '08-09 22:00:00.100  1000  1010 I SystemServer: Entered SystemServer main\n'
    '08-09 22:00:01.200  1000  1020 I ActivityManager: Starting activity'
    ' com.example.app/.MainActivity\n'
    '2026-08-09 22:00:02.300  1000  1030 D WifiService: Enabling Wi-Fi'
    ' interface wlan0\n'
    '2026-08-09 22:00:02.500  1000  1030 I DhcpClient: DHCP DISCOVER sent on'
    ' wlan0\n'
    '--------- beginning of main\n'
    '2026-08-09 22:00:02.700  2050  2050 I ExampleApp: App initialized'
    ' successfully\n'
    '2026-08-09 22:00:03.100  1000  1030 I DhcpClient: DHCP OFFER received from'
    ' 192.168.1.1\n'
    '08-09 22:00:03.400  1000  1040 W BtGatt: Connection retry count 1 for'
    ' device AA:BB:CC:DD:EE:FF\n'
    '2026-08-09 22:00:03.600  1000  1030 I DhcpClient: DHCP ACK received,'
    ' assigned IP 192.168.1.50\n'
    '08-09 22:00:04.000  1000  1020 I WifiService: Network STATE_CONNECTED on'
    ' wlan0\n'
    '08-09 22:00:05.150  2050  2060 E ExampleApp: Failed to connect to'
    ' server\n'
    '\tat com.example.app.NetworkClient.connect(NetworkClient.java:42)\n'
    '\tat com.example.app.MainActivity.onStart(MainActivity.java:108)\n'
    '08-09 22:00:05.800  1000  1040 F BtGatt: Fatal hardware controller error'
)


class LogcatServiceUserBehaviorTest(unittest.TestCase):
  """User-facing behavior tests for Logcat service."""

  def setUp(self):
    self.tmp_dir = tempfile.mkdtemp()
    self.log_file = os.path.join(self.tmp_dir, 'logcat.txt')
    with open(self.log_file, 'w', encoding='utf-8') as f:
      f.write(SAMPLE_REALISTIC_LOGCAT)

    self.mock_serial = '12345'
    self.ad = mock.MagicMock(name='AndroidDevice', serial=self.mock_serial)
    self.ad.log = logging.getLogger('mock_ad')
    self.ad.adb = mock.MagicMock()
    self.ad.adb.shell.return_value = b'2026-08-09 22:00:00.000'

    self.logcat_service = logcat.Logcat(self.ad)
    self.logcat_service.adb_logcat_file_path = self.log_file

  def tearDown(self):
    self.logcat_service.stop()
    shutil.rmtree(self.tmp_dir)

  def _append_log(self, text: str):
    with open(self.log_file, 'a', encoding='utf-8', newline='') as f:
      f.write(text)

  def test_query_logs_by_tag_level_and_pattern(self):
    # Search for error logs
    error_logs = self.logcat_service.get_lines(level=['E', 'F'])
    self.assertEqual(len(error_logs), 2)
    self.assertEqual([r.tag for r in error_logs], ['ExampleApp', 'BtGatt'])
    self.assertTrue(error_logs[0].is_error)

    # Filter logs by tag exact match
    wifi_logs = self.logcat_service.get_lines(tag='WifiService')
    self.assertEqual(len(wifi_logs), 2)
    self.assertEqual(
        [r.message for r in wifi_logs],
        ['Enabling Wi-Fi interface wlan0', 'Network STATE_CONNECTED on wlan0'],
    )

    # Search by pattern
    dhcp_offer = self.logcat_service.get_lines(pattern=r'DHCP OFFER.*192\.168')
    self.assertEqual(len(dhcp_offer), 1)
    self.assertEqual(dhcp_offer[0].tag, 'DhcpClient')

  def test_tail_recent_logs(self):
    recent_logs = self.logcat_service.tail(num_lines=3)
    self.assertEqual(len(recent_logs), 3)
    self.assertEqual(recent_logs[-1].tag, 'BtGatt')
    self.assertEqual(recent_logs[-1].level, 'F')

  def test_now_and_bounded_query(self):
    # Take position marker before triggering an action
    start = self.logcat_service.now()

    # Append new logs simulating device activity after start
    self._append_log(
        '08-09 22:00:06.000  1000  1030 I WifiService: Disconnected from'
        ' wlan0\n'
    )

    lines_since = self.logcat_service.get_lines(
        pattern='Disconnected', since=start
    )
    self.assertEqual(len(lines_since), 1)
    self.assertEqual(lines_since[0].tag, 'WifiService')
    self.assertTrue(lines_since[0].position > start)

    # Test passing a LogLine directly to since
    self._append_log(
        '08-09 22:00:07.000  1000  1030 I WifiService: Reconnected to wlan0\n'
    )
    reconnected_lines = self.logcat_service.get_lines(
        pattern='Reconnected', since=lines_since[0]
    )
    self.assertEqual(len(reconnected_lines), 1)
    self.assertTrue(reconnected_lines[0] > lines_since[0])

  def test_wait_for_sequential_protocol_handshake(self):
    handshake_steps = [
        'DHCP DISCOVER',
        'DHCP OFFER',
        'DHCP ACK',
        'STATE_CONNECTED',
    ]
    matched_lines = self.logcat_service.wait_for(
        handshake_steps, in_order=True, timeout_sec=2.0
    )
    self.assertEqual(len(matched_lines), 4)
    self.assertEqual(
        [r.tag for r in matched_lines],
        ['DhcpClient', 'DhcpClient', 'DhcpClient', 'WifiService'],
    )
    self.assertTrue(matched_lines[0] < matched_lines[1] < matched_lines[2])

  def test_wait_for_timeout_when_event_does_not_occur(self):
    with self.assertRaises(logcat.LogcatTimeoutError):
      self.logcat_service.wait_for(
          ['Nonexistent System Event'], timeout_sec=0.1
      )

  def test_listen_realtime_event_stream(self):
    with self.logcat_service.listen(tag='WifiService') as listener:
      self.assertFalse(listener.has_events())

      # Simulate background service writing new logcat entry
      self._append_log(
          '08-09 22:00:07.000  1000  1030 I WifiService: Reconnected to wlan0\n'
      )

      event = listener.get_next_event(timeout=2.0)
      self.assertEqual(event.tag, 'WifiService')
      self.assertEqual(event.message, 'Reconnected to wlan0')
      self.assertTrue(listener.has_events())


if __name__ == '__main__':
  unittest.main()
