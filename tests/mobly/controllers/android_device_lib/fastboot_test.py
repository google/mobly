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
from subprocess import PIPE
from unittest import mock

from mobly.controllers.android_device_lib import fastboot


class FastbootTest(unittest.TestCase):
  """Unit tests for mobly.controllers.android_device_lib.fastboot."""

  def setUp(self):
    fastboot.FASTBOOT = 'fastboot'

  @mock.patch('mobly.utils.run_command')
  @mock.patch('logging.debug')
  def test_fastboot_commands_and_results_are_logged_to_debug_log(
      self, mock_debug_logger, mock_run_command
  ):
    expected_stdout = 'stdout'
    expected_stderr = b'stderr'
    mock_run_command.return_value = (123, expected_stdout, expected_stderr)

    fastboot.FastbootProxy().fake_command('extra', 'flags')

    mock_debug_logger.assert_called_with(
        'cmd: %s, stdout: %s, stderr: %s, ret: %s',
        "'fastboot fake-command extra flags'",
        expected_stdout,
        expected_stderr,
        123,
    )

  @mock.patch('mobly.utils.run_command')
  def test_fastboot_without_serial(self, mock_run_command):
    expected_stdout = 'stdout'
    expected_stderr = b'stderr'
    mock_run_command.return_value = (123, expected_stdout, expected_stderr)

    fastboot.FastbootProxy().fake_command('extra', 'flags')

    mock_run_command.assert_called_with(
        cmd='fastboot fake-command extra flags',
        stdout=PIPE,
        stderr=PIPE,
        shell=True,
        timeout=180,
    )

  @mock.patch('mobly.utils.run_command')
  def test_fastboot_with_serial(self, mock_run_command):
    expected_stdout = 'stdout'
    expected_stderr = b'stderr'
    mock_run_command.return_value = (123, expected_stdout, expected_stderr)

    fastboot.FastbootProxy('ABC').fake_command('extra', 'flags')

    mock_run_command.assert_called_with(
        cmd='fastboot -s ABC fake-command extra flags',
        stdout=PIPE,
        stderr=PIPE,
        shell=True,
        timeout=180,
    )

  @mock.patch('mobly.utils.run_command')
  def test_fastboot_update_serial(self, mock_run_command):
    expected_stdout = 'stdout'
    expected_stderr = b'stderr'
    mock_run_command.return_value = (123, expected_stdout, expected_stderr)

    fut = fastboot.FastbootProxy('ABC')
    fut.fake_command('extra', 'flags')
    fut.serial = 'XYZ'
    fut.fake_command('extra', 'flags')

    mock_run_command.assert_called_with(
        cmd='fastboot -s XYZ fake-command extra flags',
        stdout=PIPE,
        stderr=PIPE,
        shell=True,
        timeout=180,
    )

  @mock.patch('mobly.utils.run_command')
  def test_fastboot_use_customized_fastboot(self, mock_run_command):
    expected_stdout = 'stdout'
    expected_stderr = b'stderr'
    mock_run_command.return_value = (123, expected_stdout, expected_stderr)

    fastboot.FASTBOOT = 'my_fastboot'

    fastboot.FastbootProxy('ABC').fake_command('extra', 'flags')

    mock_run_command.assert_called_with(
        cmd='my_fastboot -s ABC fake-command extra flags',
        stdout=PIPE,
        stderr=PIPE,
        shell=True,
        timeout=180,
    )

  @mock.patch('mobly.utils.run_command')
  def test_fastboot_with_custom_timeout(self, mock_run_command):
    expected_stdout = 'stdout'
    expected_stderr = b'stderr'
    mock_run_command.return_value = (123, expected_stdout, expected_stderr)

    fastboot.FastbootProxy().fake_command('extra', 'flags', timeout=120)

    mock_run_command.assert_called_with(
        cmd='fastboot fake-command extra flags',
        stdout=PIPE,
        stderr=PIPE,
        shell=True,
        timeout=120,
    )

  @mock.patch('mobly.utils.run_command')
  def test_fastboot_args(self, mock_run_command):
    expected_stdout = 'stdout'
    expected_stderr = b'stderr'
    mock_run_command.return_value = (123, expected_stdout, expected_stderr)

    fastboot.FastbootProxy().args('-w', timeout=180)

    mock_run_command.assert_called_with(
        cmd='fastboot -w',
        stdout=PIPE,
        stderr=PIPE,
        shell=True,
        timeout=180,
    )

  @mock.patch('mobly.utils.run_command')
  def test_fastboot_args_with_custom_timeout(self, mock_run_command):
    expected_stdout = 'stdout'
    expected_stderr = b'stderr'
    mock_run_command.return_value = (123, expected_stdout, expected_stderr)

    fastboot.FastbootProxy().args('-w', timeout=20)

    mock_run_command.assert_called_with(
        cmd='fastboot -w',
        stdout=PIPE,
        stderr=PIPE,
        shell=True,
        timeout=20,
    )

  @mock.patch('mobly.utils.run_command')
  def test_fastboot_exe_cmd_without_timeout_arg(self, mock_run_command):
    expected_stdout = 'stdout'
    expected_stderr = b'stderr'
    mock_run_command.return_value = (123, expected_stdout, expected_stderr)

    fastboot.exe_cmd('fastboot -w')

    mock_run_command.assert_called_with(
        cmd='fastboot -w',
        stdout=PIPE,
        stderr=PIPE,
        shell=True,
        timeout=180,
    )


if __name__ == '__main__':
  unittest.main()
