# Copyright 2022 Google Inc.
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

import unittest
from unittest import mock

from mobly.controllers.android_device_lib import fastboot


class FastbootTest(unittest.TestCase):
  """Unit tests for mobly.controllers.android_device_lib.adb."""

  @mock.patch('mobly.controllers.android_device_lib.fastboot.Popen')
  @mock.patch('logging.debug')
  def test_fastboot_commands_and_results_are_logged_to_debug_log(
      self, mock_debug_logger, mock_popen
  ):
    expected_stdout = 'stdout'
    expected_stderr = b'stderr'
    mock_popen.return_value.communicate = mock.Mock(
        return_value=(expected_stdout, expected_stderr)
    )
    mock_popen.return_value.returncode = 123

    fastboot.FastbootProxy().fake_command('extra', 'flags')

    mock_debug_logger.assert_called_with(
        'cmd: %s, stdout: %s, stderr: %s, ret: %s',
        "'fastboot fake-command extra flags'",
        expected_stdout,
        expected_stderr,
        123,
    )

  @mock.patch('mobly.controllers.android_device_lib.fastboot.Popen')
  def test_fastboot_without_serial(
      self, mock_popen
  ):
    expected_stdout = 'stdout'
    expected_stderr = b'stderr'
    mock_popen.return_value.communicate = mock.Mock(
        return_value=(expected_stdout, expected_stderr)
    )
    mock_popen.return_value.returncode = 123

    fastboot.FastbootProxy().fake_command('extra', 'flags')

    mock_popen.assert_called_with("fastboot fake-command extra flags", stdout=mock.ANY, stderr=mock.ANY, shell=True)

  @mock.patch('mobly.controllers.android_device_lib.fastboot.Popen')
  def test_fastboot_with_serial(
      self, mock_popen
  ):
    expected_stdout = 'stdout'
    expected_stderr = b'stderr'
    mock_popen.return_value.communicate = mock.Mock(
        return_value=(expected_stdout, expected_stderr)
    )
    mock_popen.return_value.returncode = 123

    fastboot.FastbootProxy('ABC').fake_command('extra', 'flags')

    mock_popen.assert_called_with("fastboot -s ABC fake-command extra flags", stdout=mock.ANY, stderr=mock.ANY, shell=True)

  @mock.patch('mobly.controllers.android_device_lib.fastboot.Popen')
  def test_fastboot_update_serial(
      self, mock_popen
  ):
    expected_stdout = 'stdout'
    expected_stderr = b'stderr'
    mock_popen.return_value.communicate = mock.Mock(
        return_value=(expected_stdout, expected_stderr)
    )
    mock_popen.return_value.returncode = 123

    fut = fastboot.FastbootProxy('ABC') 
    fut.fake_command('extra', 'flags')
    fut.serial = 'XYZ'
    fut.fake_command('extra', 'flags')
    
    mock_popen.assert_called_with("fastboot -s XYZ fake-command extra flags", stdout=mock.ANY, stderr=mock.ANY, shell=True)

if __name__ == '__main__':
  unittest.main()
