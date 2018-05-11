# Copyright 2017 Google Inc.
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
import mock
import subprocess

from collections import OrderedDict
from future.tests.base import unittest
from mobly.controllers.android_device_lib import adb

# Mock parameters for instrumentation.
MOCK_INSTRUMENTATION_PACKAGE = 'com.my.instrumentation.tests'
MOCK_INSTRUMENTATION_RUNNER = 'com.my.instrumentation.runner'
MOCK_INSTRUMENTATION_OPTIONS = OrderedDict([
    ('option1', 'value1'),
    ('option2', 'value2'),
])
# Mock android instrumentation commands.
MOCK_BASIC_INSTRUMENTATION_COMMAND = ('am instrument -r -w  com.my'
                                      '.instrumentation.tests/com.android'
                                      '.common.support.test.runner'
                                      '.AndroidJUnitRunner')
MOCK_RUNNER_INSTRUMENTATION_COMMAND = ('am instrument -r -w  com.my'
                                       '.instrumentation.tests/com.my'
                                       '.instrumentation.runner')
MOCK_OPTIONS_INSTRUMENTATION_COMMAND = ('am instrument -r -w -e option1 value1'
                                        ' -e option2 value2 com.my'
                                        '.instrumentation.tests/com.android'
                                        '.common.support.test.runner'
                                        '.AndroidJUnitRunner')
# Mock Shell Command
MOCK_SHELL_COMMAND = 'ls'
MOCK_COMMAND_OUTPUT = '/system/bin/ls'.encode('utf-8')
MOCK_DEFAULT_STDOUT = 'out'
MOCK_DEFAULT_STDERR = 'err'
MOCK_DEFAULT_COMMAND_OUTPUT = MOCK_DEFAULT_STDOUT.encode('utf-8')
MOCK_ADB_SHELL_COMMAND_CHECK = 'adb shell command -v ls'


class AdbTest(unittest.TestCase):
    """Unit tests for mobly.controllers.android_device_lib.adb.
    """

    def _mock_process(self, mock_psutil_process, mock_popen):
        # the created proc object in adb._exec_cmd()
        mock_proc = mock.Mock()
        mock_popen.return_value = mock_proc

        # the created process object in adb._exec_cmd()
        mock_psutil_process.return_value = mock.Mock()

        mock_proc.communicate = mock.Mock(
            return_value=(MOCK_DEFAULT_STDOUT.encode('utf-8'),
                          MOCK_DEFAULT_STDERR.encode('utf-8')))
        mock_proc.returncode = 0
        return (mock_psutil_process, mock_popen)

    @mock.patch('mobly.controllers.android_device_lib.adb.subprocess.Popen')
    @mock.patch('mobly.controllers.android_device_lib.adb.psutil.Process')
    def test_exec_cmd_no_timeout_success(self, mock_psutil_process,
                                         mock_Popen):
        self._mock_process(mock_psutil_process, mock_Popen)

        out = adb.AdbProxy()._exec_cmd(
            ['fake_cmd'], shell=False, timeout=None, stderr=None)
        self.assertEqual(MOCK_DEFAULT_STDOUT, out.decode('utf-8'))

    @mock.patch('mobly.controllers.android_device_lib.adb.subprocess.Popen')
    @mock.patch('mobly.controllers.android_device_lib.adb.psutil.Process')
    def test_exec_cmd_error_no_timeout(self, mock_psutil_process, mock_popen):
        self._mock_process(mock_psutil_process, mock_popen)
        # update return code to indicate command execution error
        mock_popen.return_value.returncode = 1

        with self.assertRaisesRegex(adb.AdbError,
                                    'Error executing adb cmd .*'):
            adb.AdbProxy()._exec_cmd(
                ['fake_cmd'], shell=False, timeout=None, stderr=None)

    @mock.patch('mobly.controllers.android_device_lib.adb.subprocess.Popen')
    @mock.patch('mobly.controllers.android_device_lib.adb.psutil.Process')
    def test_exec_cmd_with_timeout_success(self, mock_psutil_process,
                                           mock_popen):
        self._mock_process(mock_psutil_process, mock_popen)

        out = adb.AdbProxy()._exec_cmd(
            ['fake_cmd'], shell=False, timeout=1, stderr=None)
        self.assertEqual(MOCK_DEFAULT_STDOUT, out.decode('utf-8'))

    @mock.patch('mobly.controllers.android_device_lib.adb.subprocess.Popen')
    @mock.patch('mobly.controllers.android_device_lib.adb.psutil.Process')
    def test_exec_cmd_timed_out(self, mock_psutil_process, mock_popen):
        self._mock_process(mock_psutil_process, mock_popen)
        # mock process.wait(timeout=timeout) to
        # throw psutil.TimeoutExpired exception
        mock_psutil_process.return_value.wait.side_effect = (
            adb.psutil.TimeoutExpired('Timed out'))

        with self.assertRaisesRegex(adb.AdbTimeoutError,
                                    'Timed out executing command "fake_cmd" '
                                    'after 0.1s.'):
            adb.AdbProxy()._exec_cmd(
                ['fake_cmd'], shell=False, timeout=0.1, stderr=None)

    @mock.patch('mobly.controllers.android_device_lib.adb.subprocess.Popen')
    @mock.patch('mobly.controllers.android_device_lib.adb.psutil.Process')
    def test_exec_cmd_with_negative_timeout_value(self, mock_psutil_process,
                                                  mock_popen):
        self._mock_process(mock_psutil_process, mock_popen)
        with self.assertRaisesRegex(adb.Error,
                                    'Timeout is not a positive value: -1'):
            adb.AdbProxy()._exec_cmd(
                ['fake_cmd'], shell=False, timeout=-1, stderr=None)

    def test_exec_adb_cmd(self):
        with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
            mock_exec_cmd.return_value = MOCK_DEFAULT_COMMAND_OUTPUT
            adb.AdbProxy().shell(['arg1', 'arg2'])
            mock_exec_cmd.assert_called_once_with(
                ['adb', 'shell', 'arg1', 'arg2'],
                shell=False,
                timeout=None,
                stderr=None)

    def test_exec_adb_cmd_with_serial(self):
        with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
            mock_exec_cmd.return_value = MOCK_DEFAULT_COMMAND_OUTPUT
            adb.AdbProxy('12345').shell(['arg1', 'arg2'])
            mock_exec_cmd.assert_called_once_with(
                ['adb', '-s', '12345', 'shell', 'arg1', 'arg2'],
                shell=False,
                timeout=None,
                stderr=None)

    def test_exec_adb_cmd_with_shell_true(self):
        with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
            mock_exec_cmd.return_value = MOCK_DEFAULT_COMMAND_OUTPUT
            adb.AdbProxy().shell('arg1 arg2', shell=True)
            mock_exec_cmd.assert_called_once_with(
                '"adb" shell arg1 arg2', shell=True, timeout=None, stderr=None)

    def test_exec_adb_cmd_with_shell_true_with_serial(self):
        with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
            mock_exec_cmd.return_value = MOCK_DEFAULT_COMMAND_OUTPUT
            adb.AdbProxy('12345').shell('arg1 arg2', shell=True)
            mock_exec_cmd.assert_called_once_with(
                '"adb" -s "12345" shell arg1 arg2',
                shell=True,
                timeout=None,
                stderr=None)

    @mock.patch('mobly.controllers.android_device_lib.adb.subprocess.Popen')
    @mock.patch('mobly.controllers.android_device_lib.adb.psutil.Process')
    def test_exec_adb_cmd_with_stderr_pipe(self, mock_psutil_process,
                                           mock_popen):
        self._mock_process(mock_psutil_process, mock_popen)
        stderr_redirect = io.BytesIO()
        out = adb.AdbProxy().shell(
            'arg1 arg2', shell=True, stderr=stderr_redirect)
        self.assertEqual(MOCK_DEFAULT_STDOUT, out.decode('utf-8'))
        self.assertEqual(MOCK_DEFAULT_STDERR,
                         stderr_redirect.getvalue().decode('utf-8'))

    def test_forward(self):
        with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
            adb.AdbProxy().forward(MOCK_SHELL_COMMAND)

    def test_instrument_without_parameters(self):
        """Verifies the AndroidDevice object's instrument command is correct in
        the basic case.
        """
        with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
            mock_exec_cmd.return_value = MOCK_DEFAULT_COMMAND_OUTPUT
            adb.AdbProxy().instrument(MOCK_INSTRUMENTATION_PACKAGE)
            mock_exec_cmd.assert_called_once_with(
                ['adb', 'shell', MOCK_BASIC_INSTRUMENTATION_COMMAND],
                shell=False,
                timeout=None,
                stderr=None)

    def test_instrument_with_runner(self):
        """Verifies the AndroidDevice object's instrument command is correct
        with a runner specified.
        """
        with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
            mock_exec_cmd.return_value = MOCK_DEFAULT_COMMAND_OUTPUT
            adb.AdbProxy().instrument(
                MOCK_INSTRUMENTATION_PACKAGE,
                runner=MOCK_INSTRUMENTATION_RUNNER)
            mock_exec_cmd.assert_called_once_with(
                ['adb', 'shell', MOCK_RUNNER_INSTRUMENTATION_COMMAND],
                shell=False,
                timeout=None,
                stderr=None)

    def test_instrument_with_options(self):
        """Verifies the AndroidDevice object's instrument command is correct
        with options.
        """
        with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
            mock_exec_cmd.return_value = MOCK_DEFAULT_COMMAND_OUTPUT
            adb.AdbProxy().instrument(
                MOCK_INSTRUMENTATION_PACKAGE,
                options=MOCK_INSTRUMENTATION_OPTIONS)
            mock_exec_cmd.assert_called_once_with(
                ['adb', 'shell', MOCK_OPTIONS_INSTRUMENTATION_COMMAND],
                shell=False,
                timeout=None,
                stderr=None)

    def test_cli_cmd_to_string(self):
        cmd = ['"adb"', 'a b', 'c//']
        self.assertEqual(adb.cli_cmd_to_string(cmd), '\'"adb"\' \'a b\' c//')
        cmd = 'adb -s meme do something ab_cd'
        self.assertEqual(adb.cli_cmd_to_string(cmd), cmd)

    def test_has_shell_command_called_correctly(self):
        with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
            mock_exec_cmd.return_value = MOCK_DEFAULT_COMMAND_OUTPUT
            adb.AdbProxy().has_shell_command(MOCK_SHELL_COMMAND)
            mock_exec_cmd.assert_called_once_with(
                ['adb', 'shell', 'command', '-v', MOCK_SHELL_COMMAND],
                shell=False,
                timeout=None,
                stderr=None)

    def test_has_shell_command_with_existing_command(self):
        with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
            mock_exec_cmd.return_value = MOCK_COMMAND_OUTPUT
            self.assertTrue(
                adb.AdbProxy().has_shell_command(MOCK_SHELL_COMMAND))

    def test_has_shell_command_with_missing_command_on_older_devices(self):
        with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
            mock_exec_cmd.return_value = MOCK_DEFAULT_COMMAND_OUTPUT
            mock_exec_cmd.side_effect = adb.AdbError(
                MOCK_ADB_SHELL_COMMAND_CHECK, '', '', 0)
            self.assertFalse(
                adb.AdbProxy().has_shell_command(MOCK_SHELL_COMMAND))

    def test_has_shell_command_with_missing_command_on_newer_devices(self):
        with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
            mock_exec_cmd.return_value = MOCK_DEFAULT_COMMAND_OUTPUT
            mock_exec_cmd.side_effect = adb.AdbError(
                MOCK_ADB_SHELL_COMMAND_CHECK, '', '', 1)
            self.assertFalse(
                adb.AdbProxy().has_shell_command(MOCK_SHELL_COMMAND))


if __name__ == '__main__':
    unittest.main()
