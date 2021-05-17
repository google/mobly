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

import collections
import io
import mock
import subprocess
import unittest

from mobly.controllers.android_device_lib import adb

# Mock parameters for instrumentation.
MOCK_INSTRUMENTATION_PACKAGE = 'com.my.instrumentation.tests'
MOCK_INSTRUMENTATION_RUNNER = 'com.my.instrumentation.runner'
MOCK_INSTRUMENTATION_OPTIONS = collections.OrderedDict([
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

# Mock root command outputs.
MOCK_ROOT_SUCCESS_OUTPUT = 'adbd is already running as root'
MOCK_ROOT_ERROR_OUTPUT = (
    'adb: unable to connect for root: closed'.encode('utf-8'))

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

  def _mock_execute_and_process_stdout_process(self, mock_popen):
    # the created proc object in adb._execute_and_process_stdout()
    mock_proc = mock.Mock()
    mock_popen.return_value = mock_proc

    mock_popen.return_value.stdout.readline.side_effect = ['']

    mock_proc.communicate = mock.Mock(
        return_value=('', MOCK_DEFAULT_STDERR.encode('utf-8')))
    mock_proc.returncode = 0
    return mock_popen

  @mock.patch('mobly.utils.run_command')
  def test_is_adb_available(self, mock_run_command):
    mock_run_command.return_value = (0, '/usr/local/bin/adb\n'.encode('utf-8'),
                                     ''.encode('utf-8'))
    self.assertTrue(adb.is_adb_available())

  @mock.patch('mobly.utils.run_command')
  def test_is_adb_available_negative(self, mock_run_command):
    mock_run_command.return_value = (0, ''.encode('utf-8'), ''.encode('utf-8'))
    self.assertFalse(adb.is_adb_available())

  @mock.patch('mobly.utils.run_command')
  def test_exec_cmd_no_timeout_success(self, mock_run_command):
    mock_run_command.return_value = (0, MOCK_DEFAULT_STDOUT.encode('utf-8'),
                                     MOCK_DEFAULT_STDERR.encode('utf-8'))
    out = adb.AdbProxy()._exec_cmd(['fake_cmd'],
                                   shell=False,
                                   timeout=None,
                                   stderr=None)
    self.assertEqual(MOCK_DEFAULT_STDOUT, out.decode('utf-8'))
    mock_run_command.assert_called_with(['fake_cmd'], shell=False, timeout=None)

  @mock.patch('mobly.utils.run_command')
  def test_exec_cmd_error_with_serial(self, mock_run_command):
    # Return 1 for retcode for error.
    mock_run_command.return_value = (1, MOCK_DEFAULT_STDOUT.encode('utf-8'),
                                     MOCK_DEFAULT_STDERR.encode('utf-8'))
    mock_serial = 'ABCD1234'
    with self.assertRaisesRegex(adb.AdbError,
                                'Error executing adb cmd .*') as context:
      adb.AdbProxy(mock_serial).fake_cmd()
    self.assertEqual(context.exception.serial, mock_serial)
    self.assertIn(mock_serial, context.exception.cmd)

  @mock.patch('mobly.utils.run_command')
  def test_exec_cmd_error_without_serial(self, mock_run_command):
    # Return 1 for retcode for error.
    mock_run_command.return_value = (1, MOCK_DEFAULT_STDOUT.encode('utf-8'),
                                     MOCK_DEFAULT_STDERR.encode('utf-8'))
    with self.assertRaisesRegex(adb.AdbError,
                                'Error executing adb cmd .*') as context:
      adb.AdbProxy()._exec_cmd(['fake_cmd'],
                               shell=False,
                               timeout=None,
                               stderr=None)
    self.assertFalse(context.exception.serial)
    mock_run_command.assert_called_with(['fake_cmd'], shell=False, timeout=None)

  @mock.patch('mobly.utils.run_command')
  def test_exec_cmd_with_timeout_success(self, mock_run_command):
    mock_run_command.return_value = (0, MOCK_DEFAULT_STDOUT.encode('utf-8'),
                                     MOCK_DEFAULT_STDERR.encode('utf-8'))

    out = adb.AdbProxy()._exec_cmd(['fake_cmd'],
                                   shell=False,
                                   timeout=1,
                                   stderr=None)
    self.assertEqual(MOCK_DEFAULT_STDOUT, out.decode('utf-8'))
    mock_run_command.assert_called_with(['fake_cmd'], shell=False, timeout=1)

  @mock.patch('mobly.utils.run_command')
  def test_exec_cmd_timed_out(self, mock_run_command):
    mock_run_command.side_effect = adb.psutil.TimeoutExpired('Timed out')
    mock_serial = '1234Abcd'
    with self.assertRaisesRegex(
        adb.AdbTimeoutError, 'Timed out executing command "adb -s '
        '1234Abcd fake-cmd" after 0.01s.') as context:
      adb.AdbProxy(mock_serial).fake_cmd(timeout=0.01)
    self.assertEqual(context.exception.serial, mock_serial)
    self.assertIn(mock_serial, context.exception.cmd)

  @mock.patch('mobly.utils.run_command')
  def test_exec_cmd_timed_out_without_serial(self, mock_run_command):
    mock_run_command.side_effect = adb.psutil.TimeoutExpired('Timed out')
    with self.assertRaisesRegex(
        adb.AdbTimeoutError, 'Timed out executing command "adb '
        'fake-cmd" after 0.01s.') as context:
      adb.AdbProxy().fake_cmd(timeout=0.01)

  def test_exec_cmd_with_negative_timeout_value(self):
    with self.assertRaisesRegex(ValueError,
                                'Timeout is not a positive value: -1'):
      adb.AdbProxy()._exec_cmd(['fake_cmd'],
                               shell=False,
                               timeout=-1,
                               stderr=None)

  @mock.patch('mobly.controllers.android_device_lib.adb.subprocess.Popen')
  def test_execute_and_process_stdout_reads_stdout(self, mock_popen):
    self._mock_execute_and_process_stdout_process(mock_popen)
    mock_popen.return_value.stdout.readline.side_effect = ['1', '2', '']
    mock_handler = mock.MagicMock()

    err = adb.AdbProxy()._execute_and_process_stdout(['fake_cmd'],
                                                     shell=False,
                                                     handler=mock_handler)
    self.assertEqual(mock_handler.call_count, 2)
    mock_handler.assert_any_call('1')
    mock_handler.assert_any_call('2')

  @mock.patch('mobly.controllers.android_device_lib.adb.subprocess.Popen')
  def test_execute_and_process_stdout_reads_unexpected_stdout(self, mock_popen):
    unexpected_stdout = MOCK_DEFAULT_STDOUT.encode('utf-8')

    self._mock_execute_and_process_stdout_process(mock_popen)
    mock_handler = mock.MagicMock()
    mock_popen.return_value.communicate = mock.Mock(
        return_value=(unexpected_stdout, MOCK_DEFAULT_STDERR.encode('utf-8')))

    err = adb.AdbProxy()._execute_and_process_stdout(['fake_cmd'],
                                                     shell=False,
                                                     handler=mock_handler)
    self.assertEqual(mock_handler.call_count, 1)
    mock_handler.assert_called_with(unexpected_stdout)

  @mock.patch('mobly.controllers.android_device_lib.adb.subprocess.Popen')
  @mock.patch('logging.debug')
  def test_execute_and_process_stdout_logs_cmd(self, mock_debug_logger,
                                               mock_popen):
    raw_expected_stdout = ''
    expected_stdout = '[elided, processed via handler]'
    expected_stderr = MOCK_DEFAULT_STDERR.encode('utf-8')
    self._mock_execute_and_process_stdout_process(mock_popen)
    mock_popen.return_value.communicate = mock.Mock(
        return_value=(raw_expected_stdout, expected_stderr))

    err = adb.AdbProxy()._execute_and_process_stdout(['fake_cmd'],
                                                     shell=False,
                                                     handler=mock.MagicMock())
    mock_debug_logger.assert_called_with(
        'cmd: %s, stdout: %s, stderr: %s, ret: %s', 'fake_cmd', expected_stdout,
        expected_stderr, 0)

  @mock.patch('mobly.controllers.android_device_lib.adb.subprocess.Popen')
  @mock.patch('logging.debug')
  def test_execute_and_process_stdout_logs_cmd_with_unexpected_stdout(
      self, mock_debug_logger, mock_popen):
    raw_expected_stdout = MOCK_DEFAULT_STDOUT.encode('utf-8')
    expected_stdout = '[unexpected stdout] %s' % raw_expected_stdout
    expected_stderr = MOCK_DEFAULT_STDERR.encode('utf-8')

    self._mock_execute_and_process_stdout_process(mock_popen)
    mock_popen.return_value.communicate = mock.Mock(
        return_value=(raw_expected_stdout, expected_stderr))

    err = adb.AdbProxy()._execute_and_process_stdout(['fake_cmd'],
                                                     shell=False,
                                                     handler=mock.MagicMock())
    mock_debug_logger.assert_called_with(
        'cmd: %s, stdout: %s, stderr: %s, ret: %s', 'fake_cmd', expected_stdout,
        expected_stderr, 0)

  @mock.patch('mobly.controllers.android_device_lib.adb.subprocess.Popen')
  def test_execute_and_process_stdout_despite_cmd_exits(self, mock_popen):
    self._mock_execute_and_process_stdout_process(mock_popen)
    mock_popen.return_value.poll.side_effect = [None, 0]
    mock_popen.return_value.stdout.readline.side_effect = ['1', '2', '3', '']
    mock_handler = mock.MagicMock()

    err = adb.AdbProxy()._execute_and_process_stdout(['fake_cmd'],
                                                     shell=False,
                                                     handler=mock_handler)

    self.assertEqual(mock_handler.call_count, 3)
    mock_handler.assert_any_call('1')
    mock_handler.assert_any_call('2')
    mock_handler.assert_any_call('3')

  @mock.patch('mobly.controllers.android_device_lib.adb.subprocess.Popen')
  def test_execute_and_process_stdout_when_cmd_eof(self, mock_popen):
    self._mock_execute_and_process_stdout_process(mock_popen)
    mock_popen.return_value.stdout.readline.side_effect = ['1', '2', '3', '']
    mock_handler = mock.MagicMock()

    err = adb.AdbProxy()._execute_and_process_stdout(['fake_cmd'],
                                                     shell=False,
                                                     handler=mock_handler)

    self.assertEqual(mock_handler.call_count, 3)
    mock_handler.assert_any_call('1')
    mock_handler.assert_any_call('2')
    mock_handler.assert_any_call('3')

  @mock.patch('mobly.controllers.android_device_lib.adb.subprocess.Popen')
  def test_execute_and_process_stdout_returns_stderr(self, mock_popen):
    self._mock_execute_and_process_stdout_process(mock_popen)

    err = adb.AdbProxy()._execute_and_process_stdout(['fake_cmd'],
                                                     shell=False,
                                                     handler=mock.MagicMock())
    self.assertEqual(MOCK_DEFAULT_STDERR, err.decode('utf-8'))

  @mock.patch('mobly.controllers.android_device_lib.adb.subprocess.Popen')
  def test_execute_and_process_stdout_raises_adb_error(self, mock_popen):
    self._mock_execute_and_process_stdout_process(mock_popen)
    mock_popen.return_value.returncode = 1

    with self.assertRaisesRegex(adb.AdbError, 'Error executing adb cmd .*'):
      err = adb.AdbProxy()._execute_and_process_stdout(['fake_cmd'],
                                                       shell=False,
                                                       handler=mock.MagicMock())

  @mock.patch('mobly.controllers.android_device_lib.adb.subprocess.Popen')
  def test_execute_and_process_stdout_when_handler_crash(self, mock_popen):
    self._mock_execute_and_process_stdout_process(mock_popen)
    mock_popen.return_value.stdout.readline.side_effect = ['1', '2', '3', '']
    mock_handler = mock.MagicMock()
    mock_handler.side_effect = ['', TypeError('fake crash'), '', '']

    with self.assertRaisesRegex(TypeError, 'fake crash'):
      err = adb.AdbProxy()._execute_and_process_stdout(['fake_cmd'],
                                                       shell=False,
                                                       handler=mock_handler)

    mock_popen.return_value.communicate.assert_called_once_with()

  def test_construct_adb_cmd(self):
    adb_cmd = adb.AdbProxy()._construct_adb_cmd('shell', 'arg1', shell=False)
    self.assertEqual(adb_cmd, ['adb', 'shell', 'arg1'])

  def test_construct_adb_cmd_with_one_command(self):
    adb_cmd = adb.AdbProxy()._construct_adb_cmd(
        'shell ls /asdafsfd/asdf-asfd/asa', [], shell=False)
    self.assertEqual(adb_cmd, ['adb', 'shell ls /asdafsfd/asdf-asfd/asa'])

  def test_construct_adb_cmd_with_one_arg_command(self):
    adb_cmd = adb.AdbProxy()._construct_adb_cmd('shell',
                                                'ls /asdafsfd/asdf-asfd/asa',
                                                shell=False)
    self.assertEqual(adb_cmd, ['adb', 'shell', 'ls /asdafsfd/asdf-asfd/asa'])

  def test_construct_adb_cmd_with_one_arg_command_list(self):
    adb_cmd = adb.AdbProxy()._construct_adb_cmd('shell',
                                                ['ls /asdafsfd/asdf-asfd/asa'],
                                                shell=False)
    self.assertEqual(adb_cmd, ['adb', 'shell', 'ls /asdafsfd/asdf-asfd/asa'])

  def test_construct_adb_cmd_with_special_characters(self):
    adb_cmd = adb.AdbProxy()._construct_adb_cmd('shell',
                                                ['a b', '"blah"', r'\/\/'],
                                                shell=False)
    self.assertEqual(adb_cmd, ['adb', 'shell', 'a b', '"blah"', r"\/\/"])

  def test_construct_adb_cmd_with_serial(self):
    adb_cmd = adb.AdbProxy('12345')._construct_adb_cmd('shell',
                                                       'arg1',
                                                       shell=False)
    self.assertEqual(adb_cmd, ['adb', '-s', '12345', 'shell', 'arg1'])

  def test_construct_adb_cmd_with_list(self):
    adb_cmd = adb.AdbProxy()._construct_adb_cmd('shell', ['arg1', 'arg2'],
                                                shell=False)
    self.assertEqual(adb_cmd, ['adb', 'shell', 'arg1', 'arg2'])

  def test_construct_adb_cmd_with_serial_with_list(self):
    adb_cmd = adb.AdbProxy('12345')._construct_adb_cmd('shell',
                                                       ['arg1', 'arg2'],
                                                       shell=False)
    self.assertEqual(adb_cmd, ['adb', '-s', '12345', 'shell', 'arg1', 'arg2'])

  def test_construct_adb_cmd_with_shell_true(self):
    adb_cmd = adb.AdbProxy()._construct_adb_cmd('shell',
                                                'arg1 arg2',
                                                shell=True)
    self.assertEqual(adb_cmd, '"adb" shell arg1 arg2')

  def test_construct_adb_cmd_with_shell_true_with_one_command(self):
    adb_cmd = adb.AdbProxy()._construct_adb_cmd(
        'shell ls /asdafsfd/asdf-asfd/asa', [], shell=True)
    self.assertEqual(adb_cmd, '"adb" shell ls /asdafsfd/asdf-asfd/asa ')

  def test_construct_adb_cmd_with_shell_true_with_one_arg_command(self):
    adb_cmd = adb.AdbProxy()._construct_adb_cmd('shell',
                                                'ls /asdafsfd/asdf-asfd/asa',
                                                shell=True)
    self.assertEqual(adb_cmd, '"adb" shell ls /asdafsfd/asdf-asfd/asa')

  def test_construct_adb_cmd_with_shell_true_with_one_arg_command_list(self):
    adb_cmd = adb.AdbProxy()._construct_adb_cmd('shell',
                                                ['ls /asdafsfd/asdf-asfd/asa'],
                                                shell=True)
    self.assertEqual(adb_cmd, '"adb" shell \'ls /asdafsfd/asdf-asfd/asa\'')

  def test_construct_adb_cmd_with_shell_true_with_auto_quotes(self):
    adb_cmd = adb.AdbProxy()._construct_adb_cmd('shell',
                                                ['a b', '"blah"', r'\/\/'],
                                                shell=True)
    self.assertEqual(adb_cmd, '"adb" shell \'a b\' \'"blah"\' \'\\/\\/\'')

  def test_construct_adb_cmd_with_shell_true_with_serial(self):
    adb_cmd = adb.AdbProxy('12345')._construct_adb_cmd('shell',
                                                       'arg1 arg2',
                                                       shell=True)
    self.assertEqual(adb_cmd, '"adb" -s "12345" shell arg1 arg2')

  def test_construct_adb_cmd_with_shell_true_with_list(self):
    adb_cmd = adb.AdbProxy()._construct_adb_cmd('shell', ['arg1', 'arg2'],
                                                shell=True)
    self.assertEqual(adb_cmd, '"adb" shell arg1 arg2')

  def test_construct_adb_cmd_with_shell_true_with_serial_with_list(self):
    adb_cmd = adb.AdbProxy('12345')._construct_adb_cmd('shell',
                                                       ['arg1', 'arg2'],
                                                       shell=True)
    self.assertEqual(adb_cmd, '"adb" -s "12345" shell arg1 arg2')

  def test_exec_adb_cmd(self):
    with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
      mock_exec_cmd.return_value = MOCK_DEFAULT_COMMAND_OUTPUT
      adb.AdbProxy().shell(['arg1', 'arg2'])
      mock_exec_cmd.assert_called_once_with(['adb', 'shell', 'arg1', 'arg2'],
                                            shell=False,
                                            timeout=None,
                                            stderr=None)

  def test_exec_adb_cmd_with_shell_true(self):
    with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
      mock_exec_cmd.return_value = MOCK_DEFAULT_COMMAND_OUTPUT
      adb.AdbProxy().shell('arg1 arg2', shell=True)
      mock_exec_cmd.assert_called_once_with('"adb" shell arg1 arg2',
                                            shell=True,
                                            timeout=None,
                                            stderr=None)

  def test_exec_adb_cmd_formats_command(self):
    with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
      with mock.patch.object(adb.AdbProxy,
                             '_construct_adb_cmd') as mock_construct_adb_cmd:
        mock_adb_cmd = mock.MagicMock()
        mock_adb_args = mock.MagicMock()
        mock_construct_adb_cmd.return_value = mock_adb_cmd
        mock_exec_cmd.return_value = MOCK_DEFAULT_COMMAND_OUTPUT

        adb.AdbProxy().shell(mock_adb_args)
        mock_construct_adb_cmd.assert_called_once_with('shell',
                                                       mock_adb_args,
                                                       shell=False)
        mock_exec_cmd.assert_called_once_with(mock_adb_cmd,
                                              shell=False,
                                              timeout=None,
                                              stderr=None)

  def test_exec_adb_cmd_formats_command_with_shell_true(self):
    with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
      with mock.patch.object(adb.AdbProxy,
                             '_construct_adb_cmd') as mock_construct_adb_cmd:
        mock_adb_cmd = mock.MagicMock()
        mock_adb_args = mock.MagicMock()
        mock_construct_adb_cmd.return_value = mock_adb_cmd

        adb.AdbProxy().shell(mock_adb_args, shell=True)
        mock_construct_adb_cmd.assert_called_once_with('shell',
                                                       mock_adb_args,
                                                       shell=True)
        mock_exec_cmd.assert_called_once_with(mock_adb_cmd,
                                              shell=True,
                                              timeout=None,
                                              stderr=None)

  def test_execute_adb_and_process_stdout_formats_command(self):
    with mock.patch.object(
        adb.AdbProxy,
        '_execute_and_process_stdout') as mock_execute_and_process_stdout:
      with mock.patch.object(adb.AdbProxy,
                             '_construct_adb_cmd') as mock_construct_adb_cmd:
        mock_adb_cmd = mock.MagicMock()
        mock_adb_args = mock.MagicMock()
        mock_handler = mock.MagicMock()
        mock_construct_adb_cmd.return_value = mock_adb_cmd

        adb.AdbProxy()._execute_adb_and_process_stdout('shell',
                                                       mock_adb_args,
                                                       shell=False,
                                                       handler=mock_handler)
        mock_construct_adb_cmd.assert_called_once_with('shell',
                                                       mock_adb_args,
                                                       shell=False)
        mock_execute_and_process_stdout.assert_called_once_with(
            mock_adb_cmd, shell=False, handler=mock_handler)

  @mock.patch('mobly.utils.run_command')
  def test_exec_adb_cmd_with_stderr_pipe(self, mock_run_command):
    mock_run_command.return_value = (0, MOCK_DEFAULT_STDOUT.encode('utf-8'),
                                     MOCK_DEFAULT_STDERR.encode('utf-8'))
    stderr_redirect = io.BytesIO()
    out = adb.AdbProxy().shell('arg1 arg2', shell=True, stderr=stderr_redirect)
    self.assertEqual(MOCK_DEFAULT_STDOUT, out.decode('utf-8'))
    self.assertEqual(MOCK_DEFAULT_STDERR,
                     stderr_redirect.getvalue().decode('utf-8'))

  @mock.patch('mobly.utils.run_command')
  def test_connect_success(self, mock_run_command):
    mock_address = 'localhost:1234'
    mock_run_command.return_value = (
        0, f'connected to {mock_address}'.encode('utf-8'),
        MOCK_DEFAULT_STDERR.encode('utf-8'))

    out = adb.AdbProxy().connect(mock_address)
    self.assertEqual('connected to localhost:1234', out.decode('utf-8'))

  @mock.patch('mobly.utils.run_command')
  def test_connect_already_connected(self, mock_run_command):
    mock_address = 'localhost:1234'
    mock_run_command.return_value = (
        0, f'already connected to {mock_address}'.encode('utf-8'),
        MOCK_DEFAULT_STDERR.encode('utf-8'))

    out = adb.AdbProxy().connect(mock_address)
    self.assertEqual('already connected to localhost:1234', out.decode('utf-8'))

  @mock.patch('mobly.utils.run_command')
  def test_connect_fail(self, mock_run_command):
    mock_address = 'localhost:1234'
    mock_run_command.return_value = (0, 'Connection refused\n'.encode('utf-8'),
                                     MOCK_DEFAULT_STDERR.encode('utf-8'))

    with self.assertRaisesRegex(
        adb.AdbError, 'Error executing adb cmd "connect localhost:1234".'):
      out = adb.AdbProxy().connect(mock_address)

  def test_getprop(self):
    with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
      mock_exec_cmd.return_value = b'blah'
      self.assertEqual(adb.AdbProxy().getprop('haha'), 'blah')
      mock_exec_cmd.assert_called_once_with(
          ['adb', 'shell', 'getprop', 'haha'],
          shell=False,
          stderr=None,
          timeout=adb.DEFAULT_GETPROP_TIMEOUT_SEC)

  def test__parse_getprop_output_special_values(self):
    mock_adb_output = (
        b'[selinux.restorecon_recursive]: [/data/misc_ce/10]\n'
        b'[selinux.abc]: [key: value]\n'  # "key: value" as value
        b'[persist.sys.boot.reason.history]: [reboot,adb,1558549857\n'
        b'reboot,factory_reset,1558483886\n'  # multi-line value
        b'reboot,1558483823]\n'
        b'[persist.something]: [haha\n'
        b']\n'
        b'[[wrapped.key]]: [[wrapped value]]\n'
        b'[persist.byte]: [J\xaa\x8bb\xab\x9dP\x0f]\n'  # non-decodable
    )
    parsed_props = adb.AdbProxy()._parse_getprop_output(mock_adb_output)
    expected_output = {
        'persist.sys.boot.reason.history':
            ('reboot,adb,1558549857\nreboot,factory_reset,1558483886\n'
             'reboot,1558483823'),
        'selinux.abc': 'key: value',
        'persist.something': 'haha\n',
        'selinux.restorecon_recursive': '/data/misc_ce/10',
        '[wrapped.key]': '[wrapped value]',
        'persist.byte': 'JbP\x0f',
    }
    self.assertEqual(parsed_props, expected_output)

  def test__parse_getprop_output_malformat_output(self):
    mock_adb_output = (
        b'[selinux.restorecon_recursive][/data/misc_ce/10]\n'  # Malformat
        b'[persist.sys.boot.reason]: [reboot,adb,1558549857]\n'
        b'[persist.something]: [haha]\n')
    parsed_props = adb.AdbProxy()._parse_getprop_output(mock_adb_output)
    expected_output = {
        'persist.sys.boot.reason': 'reboot,adb,1558549857',
        'persist.something': 'haha'
    }
    self.assertEqual(parsed_props, expected_output)

  def test__parse_getprop_output_special_line_separator(self):
    mock_adb_output = (
        b'[selinux.restorecon_recursive][/data/misc_ce/10]\r\n'  # Malformat
        b'[persist.sys.boot.reason]: [reboot,adb,1558549857]\r\n'
        b'[persist.something]: [haha]\r\n')
    parsed_props = adb.AdbProxy()._parse_getprop_output(mock_adb_output)
    expected_output = {
        'persist.sys.boot.reason': 'reboot,adb,1558549857',
        'persist.something': 'haha'
    }
    self.assertEqual(parsed_props, expected_output)

  @mock.patch('time.sleep', return_value=mock.MagicMock())
  def test_getprops(self, mock_sleep):
    with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
      mock_exec_cmd.return_value = (
          b'\n[sendbug.preferred.domain]: [google.com]\n'
          b'[sys.uidcpupower]: []\n'
          b'[sys.wifitracing.started]: [1]\n'
          b'[telephony.lteOnCdmaDevice]: [1]\n\n')
      actual_output = adb.AdbProxy().getprops([
          'sys.wifitracing.started',  # "numeric" value
          'sys.uidcpupower',  # empty value
          'sendbug.preferred.domain',  # string value
          'nonExistentProp'
      ])
      self.assertEqual(
          actual_output, {
              'sys.wifitracing.started': '1',
              'sys.uidcpupower': '',
              'sendbug.preferred.domain': 'google.com'
          })
      mock_exec_cmd.assert_called_once_with(
          ['adb', 'shell', 'getprop'],
          shell=False,
          stderr=None,
          timeout=adb.DEFAULT_GETPROP_TIMEOUT_SEC)
      mock_sleep.assert_not_called()

  @mock.patch('time.sleep', return_value=mock.MagicMock())
  def test_getprops_when_empty_string_randomly_returned(self, mock_sleep):
    with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
      mock_exec_cmd.side_effect = [
          b'', (b'\n[ro.build.id]: [AB42]\n'
                b'[ro.build.type]: [userdebug]\n\n')
      ]
      actual_output = adb.AdbProxy().getprops(['ro.build.id'])
      self.assertEqual(actual_output, {
          'ro.build.id': 'AB42',
      })
      self.assertEqual(mock_exec_cmd.call_count, 2)
      mock_exec_cmd.assert_called_with(['adb', 'shell', 'getprop'],
                                       shell=False,
                                       stderr=None,
                                       timeout=adb.DEFAULT_GETPROP_TIMEOUT_SEC)
      self.assertEqual(mock_sleep.call_count, 1)
      mock_sleep.assert_called_with(1)

  @mock.patch('time.sleep', return_value=mock.MagicMock())
  def test_getprops_when_empty_string_always_returned(self, mock_sleep):
    with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
      mock_exec_cmd.return_value = b''
      actual_output = adb.AdbProxy().getprops(['ro.build.id'])
      self.assertEqual(actual_output, {})
      self.assertEqual(mock_exec_cmd.call_count, 3)
      mock_exec_cmd.assert_called_with(['adb', 'shell', 'getprop'],
                                       shell=False,
                                       stderr=None,
                                       timeout=adb.DEFAULT_GETPROP_TIMEOUT_SEC)
      self.assertEqual(mock_sleep.call_count, 2)
      mock_sleep.assert_called_with(1)

  def test_forward(self):
    with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
      adb.AdbProxy().forward(MOCK_SHELL_COMMAND)

  def test_instrument_without_parameters(self):
    """Verifies the AndroidDevice object's instrument command is correct in
    the basic case.
    """
    with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
      output = adb.AdbProxy().instrument(MOCK_INSTRUMENTATION_PACKAGE)
      mock_exec_cmd.assert_called_once_with(
          ['adb', 'shell', MOCK_BASIC_INSTRUMENTATION_COMMAND],
          shell=False,
          timeout=None,
          stderr=None)
      self.assertEqual(output, mock_exec_cmd.return_value)

  def test_instrument_with_runner(self):
    """Verifies the AndroidDevice object's instrument command is correct
    with a runner specified.
    """
    with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
      stdout = adb.AdbProxy().instrument(MOCK_INSTRUMENTATION_PACKAGE,
                                         runner=MOCK_INSTRUMENTATION_RUNNER)
      mock_exec_cmd.assert_called_once_with(
          ['adb', 'shell', MOCK_RUNNER_INSTRUMENTATION_COMMAND],
          shell=False,
          timeout=None,
          stderr=None)
      self.assertEqual(stdout, mock_exec_cmd.return_value)

  def test_instrument_with_options(self):
    """Verifies the AndroidDevice object's instrument command is correct
    with options.
    """
    with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
      stdout = adb.AdbProxy().instrument(MOCK_INSTRUMENTATION_PACKAGE,
                                         options=MOCK_INSTRUMENTATION_OPTIONS)
      mock_exec_cmd.assert_called_once_with(
          ['adb', 'shell', MOCK_OPTIONS_INSTRUMENTATION_COMMAND],
          shell=False,
          timeout=None,
          stderr=None)
      self.assertEqual(stdout, mock_exec_cmd.return_value)

  def test_instrument_with_handler(self):
    """Verifies the AndroidDevice object's instrument command is correct
    with a handler passed in.
    """

    def mock_handler(raw_line):
      pass

    with mock.patch.object(
        adb.AdbProxy,
        '_execute_and_process_stdout') as mock_execute_and_process_stdout:
      stderr = adb.AdbProxy().instrument(MOCK_INSTRUMENTATION_PACKAGE,
                                         handler=mock_handler)
      mock_execute_and_process_stdout.assert_called_once_with(
          ['adb', 'shell', MOCK_BASIC_INSTRUMENTATION_COMMAND],
          shell=False,
          handler=mock_handler)
      self.assertEqual(stderr, mock_execute_and_process_stdout.return_value)

  def test_instrument_with_handler_with_runner(self):
    """Verifies the AndroidDevice object's instrument command is correct
    with a handler passed in and a runner specified.
    """

    def mock_handler(raw_line):
      pass

    with mock.patch.object(
        adb.AdbProxy,
        '_execute_and_process_stdout') as mock_execute_and_process_stdout:
      stderr = adb.AdbProxy().instrument(MOCK_INSTRUMENTATION_PACKAGE,
                                         runner=MOCK_INSTRUMENTATION_RUNNER,
                                         handler=mock_handler)
      mock_execute_and_process_stdout.assert_called_once_with(
          ['adb', 'shell', MOCK_RUNNER_INSTRUMENTATION_COMMAND],
          shell=False,
          handler=mock_handler)
      self.assertEqual(stderr, mock_execute_and_process_stdout.return_value)

  def test_instrument_with_handler_with_options(self):
    """Verifies the AndroidDevice object's instrument command is correct
    with a handler passed in and options.
    """

    def mock_handler(raw_line):
      pass

    with mock.patch.object(
        adb.AdbProxy,
        '_execute_and_process_stdout') as mock_execute_and_process_stdout:
      stderr = adb.AdbProxy().instrument(MOCK_INSTRUMENTATION_PACKAGE,
                                         options=MOCK_INSTRUMENTATION_OPTIONS,
                                         handler=mock_handler)
      mock_execute_and_process_stdout.assert_called_once_with(
          ['adb', 'shell', MOCK_OPTIONS_INSTRUMENTATION_COMMAND],
          shell=False,
          handler=mock_handler)
      self.assertEqual(stderr, mock_execute_and_process_stdout.return_value)

  @mock.patch.object(adb.AdbProxy, '_exec_cmd')
  def test_root_success(self, mock_exec_cmd):
    mock_exec_cmd.return_value = MOCK_ROOT_SUCCESS_OUTPUT
    output = adb.AdbProxy().root()
    mock_exec_cmd.assert_called_once_with(['adb', 'root'],
                                          shell=False,
                                          timeout=None,
                                          stderr=None)
    self.assertEqual(output, MOCK_ROOT_SUCCESS_OUTPUT)

  @mock.patch('time.sleep', return_value=mock.MagicMock())
  @mock.patch.object(adb.AdbProxy, '_exec_cmd')
  def test_root_success_with_retry(self, mock_exec_cmd, mock_sleep):
    mock_exec_cmd.side_effect = [
        adb.AdbError('adb root', '', MOCK_ROOT_ERROR_OUTPUT, 1),
        MOCK_ROOT_SUCCESS_OUTPUT
    ]
    output = adb.AdbProxy().root()
    mock_exec_cmd.assert_called_with(['adb', 'root'],
                                     shell=False,
                                     timeout=None,
                                     stderr=None)
    self.assertEqual(output, MOCK_ROOT_SUCCESS_OUTPUT)
    self.assertEqual(mock_sleep.call_count, 1)
    mock_sleep.assert_called_with(10)

  @mock.patch('time.sleep', return_value=mock.MagicMock())
  @mock.patch.object(adb.AdbProxy, '_exec_cmd')
  def test_root_raises_adb_error_when_all_retries_failed(
      self, mock_exec_cmd, mock_sleep):
    mock_exec_cmd.side_effect = adb.AdbError('adb root', '',
                                             MOCK_ROOT_ERROR_OUTPUT, 1)
    expected_msg = ('Error executing adb cmd "adb root". '
                    'ret: 1, stdout: , stderr: %s' % MOCK_ROOT_ERROR_OUTPUT)
    with self.assertRaisesRegex(adb.AdbError, expected_msg):
      adb.AdbProxy().root()
      mock_exec_cmd.assert_called_with(['adb', 'root'],
                                       shell=False,
                                       timeout=None,
                                       stderr=None)
    self.assertEqual(mock_sleep.call_count, 2)
    mock_sleep.assert_called_with(10)

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
      self.assertTrue(adb.AdbProxy().has_shell_command(MOCK_SHELL_COMMAND))

  def test_has_shell_command_with_missing_command_on_older_devices(self):
    with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
      mock_exec_cmd.return_value = MOCK_DEFAULT_COMMAND_OUTPUT
      mock_exec_cmd.side_effect = adb.AdbError(MOCK_ADB_SHELL_COMMAND_CHECK, '',
                                               '', 0)
      self.assertFalse(adb.AdbProxy().has_shell_command(MOCK_SHELL_COMMAND))

  def test_has_shell_command_with_missing_command_on_newer_devices(self):
    with mock.patch.object(adb.AdbProxy, '_exec_cmd') as mock_exec_cmd:
      mock_exec_cmd.return_value = MOCK_DEFAULT_COMMAND_OUTPUT
      mock_exec_cmd.side_effect = adb.AdbError(MOCK_ADB_SHELL_COMMAND_CHECK, '',
                                               '', 1)
      self.assertFalse(adb.AdbProxy().has_shell_command(MOCK_SHELL_COMMAND))

  @mock.patch.object(adb.AdbProxy, 'getprop')
  @mock.patch.object(adb.AdbProxy, '_exec_cmd')
  def test_current_user_id_25_and_above(self, mock_exec_cmd, mock_getprop):
    mock_getprop.return_value = b'25'
    mock_exec_cmd.return_value = b'123'
    user_id = adb.AdbProxy().current_user_id
    mock_exec_cmd.assert_called_once_with(
        ['adb', 'shell', 'am', 'get-current-user'],
        shell=False,
        stderr=None,
        timeout=None)
    self.assertEqual(user_id, 123)

  @mock.patch.object(adb.AdbProxy, 'getprop')
  @mock.patch.object(adb.AdbProxy, '_exec_cmd')
  def test_current_user_id_between_21_and_24(self, mock_exec_cmd, mock_getprop):
    mock_getprop.return_value = b'23'
    mock_exec_cmd.return_value = (b'Users:\n'
                                  b'UserInfo{123:Owner:13} serialNo=0\n'
                                  b'Created: <unknown>\n'
                                  b'Last logged in: +1h22m12s497ms ago\n'
                                  b'UserInfo{456:Owner:14} serialNo=0\n'
                                  b'Created: <unknown>\n'
                                  b'Last logged in: +1h01m12s497ms ago\n')
    user_id = adb.AdbProxy().current_user_id
    mock_exec_cmd.assert_called_once_with(['adb', 'shell', 'dumpsys', 'user'],
                                          shell=False,
                                          stderr=None,
                                          timeout=None)
    self.assertEqual(user_id, 123)


if __name__ == '__main__':
  unittest.main()
