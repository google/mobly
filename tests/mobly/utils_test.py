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

from concurrent import futures
import io
import mock
import os
import platform
import shutil
import socket
import sys
import subprocess
import tempfile
import threading
import time
import unittest

import portpicker
import psutil
from mobly import base_instrumentation_test

from mobly import base_test
from mobly import signals
from mobly import test_runner
from mobly import utils
from tests.lib import integration_test
from tests.lib import mock_controller
from tests.lib import mock_instrumentation_test
from tests.lib import multiple_subclasses_module

MOCK_AVAILABLE_PORT = 5
ADB_MODULE_PACKAGE_NAME = 'mobly.controllers.android_device_lib.adb'


class UtilsTest(unittest.TestCase):
  """This test class has unit tests for the implementation of everything
  under mobly.utils.
  """

  def setUp(self):
    system = platform.system()
    self.tmp_dir = tempfile.mkdtemp()

  def tearDown(self):
    shutil.rmtree(self.tmp_dir)

  def sleep_cmd(self, wait_secs):
    if platform.system() == 'Windows':
      python_code = ['import time', 'time.sleep(%s)' % wait_secs]
      return ['python', '-c', 'exec("%s")' % r'\r\n'.join(python_code)]
    else:
      return ['sleep', str(wait_secs)]

  def test_run_command(self):
    (ret, out, err) = utils.run_command(self.sleep_cmd(0.01))
    self.assertEqual(ret, 0)

  def test_run_command_with_timeout(self):
    (ret, out, err) = utils.run_command(self.sleep_cmd(0.01), timeout=4)
    self.assertEqual(ret, 0)

  def test_run_command_with_timeout_expired(self):
    with self.assertRaises(psutil.TimeoutExpired):
      _ = utils.run_command(self.sleep_cmd(4), timeout=0.01)

  @mock.patch('threading.Timer')
  @mock.patch('psutil.Popen')
  def test_run_command_with_default_params(self, mock_Popen, mock_Timer):
    mock_command = mock.MagicMock(spec=dict)
    mock_proc = mock_Popen.return_value
    mock_proc.communicate.return_value = ('fake_out', 'fake_err')
    mock_proc.returncode = 0
    out = utils.run_command(mock_command)
    self.assertEqual(out, (0, 'fake_out', 'fake_err'))
    mock_Popen.assert_called_with(
        mock_command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        cwd=None,
        env=None,
        universal_newlines=False,
    )
    mock_Timer.assert_not_called()

  @mock.patch('threading.Timer')
  @mock.patch('psutil.Popen')
  def test_run_command_with_custom_params(self, mock_Popen, mock_Timer):
    mock_command = mock.MagicMock(spec=dict)
    mock_stdout = mock.MagicMock(spec=int)
    mock_stderr = mock.MagicMock(spec=int)
    mock_shell = mock.MagicMock(spec=bool)
    mock_timeout = 1234
    mock_env = mock.MagicMock(spec=dict)
    mock_universal_newlines = mock.MagicMock(spec=bool)
    mock_proc = mock_Popen.return_value
    mock_proc.communicate.return_value = ('fake_out', 'fake_err')
    mock_proc.returncode = 127
    out = utils.run_command(mock_command,
                            stdout=mock_stdout,
                            stderr=mock_stderr,
                            shell=mock_shell,
                            timeout=mock_timeout,
                            env=mock_env,
                            universal_newlines=mock_universal_newlines)
    self.assertEqual(out, (127, 'fake_out', 'fake_err'))
    mock_Popen.assert_called_with(
        mock_command,
        stdout=mock_stdout,
        stderr=mock_stderr,
        shell=mock_shell,
        cwd=None,
        env=mock_env,
        universal_newlines=mock_universal_newlines,
    )
    mock_Timer.assert_called_with(1234, mock.ANY)

  def test_run_command_with_universal_newlines_false(self):
    (ret, out, err) = utils.run_command(
        self.sleep_cmd(0.01), universal_newlines=False)
    self.assertIsInstance(out, bytes)

  def test_run_command_with_universal_newlines_true(self):
    (ret, out, err) = utils.run_command(
        self.sleep_cmd(0.01), universal_newlines=True)
    self.assertIsInstance(out, str)

  def test_start_standing_subproc(self):
    try:
      p = utils.start_standing_subprocess(self.sleep_cmd(0.01))
      p1 = psutil.Process(p.pid)
      self.assertTrue(p1.is_running())
    finally:
      p.stdout.close()
      p.stderr.close()
      p.wait()

  @mock.patch('subprocess.Popen')
  def test_start_standing_subproc_without_env(self, mock_Popen):
    p = utils.start_standing_subprocess(self.sleep_cmd(0.01))
    mock_Popen.assert_called_with(
        self.sleep_cmd(0.01),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        env=None,
    )

  @mock.patch('subprocess.Popen')
  def test_start_standing_subproc_with_custom_env(self, mock_Popen):
    mock_env = mock.MagicMock(spec=dict)
    p = utils.start_standing_subprocess(self.sleep_cmd(0.01), env=mock_env)
    mock_Popen.assert_called_with(
        self.sleep_cmd(0.01),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        env=mock_env,
    )

  def test_stop_standing_subproc(self):
    p = utils.start_standing_subprocess(self.sleep_cmd(4))
    p1 = psutil.Process(p.pid)
    utils.stop_standing_subprocess(p)
    self.assertFalse(p1.is_running())

  def test_stop_standing_subproc_wihtout_pipe(self):
    p = subprocess.Popen(self.sleep_cmd(4))
    self.assertIsNone(p.stdout)
    p1 = psutil.Process(p.pid)
    utils.stop_standing_subprocess(p)
    self.assertFalse(p1.is_running())

  @unittest.skipIf(sys.version_info >= (3, 4) and sys.version_info < (3, 5),
                   'Python 3.4 does not support `None` max_workers.')
  def test_concurrent_exec_when_none_workers(self):

    def adder(a, b):
      return a + b

    with mock.patch.object(futures,
                           'ThreadPoolExecutor',
                           wraps=futures.ThreadPoolExecutor) as thread_pool_spy:
      results = utils.concurrent_exec(adder, [(1, 1), (2, 2)], max_workers=None)

    thread_pool_spy.assert_called_once_with(max_workers=None)

    self.assertEqual(len(results), 2)
    self.assertIn(2, results)
    self.assertIn(4, results)

  def test_concurrent_exec_when_default_max_workers(self):

    def adder(a, b):
      return a + b

    with mock.patch.object(futures,
                           'ThreadPoolExecutor',
                           wraps=futures.ThreadPoolExecutor) as thread_pool_spy:
      results = utils.concurrent_exec(adder, [(1, 1), (2, 2)])

    thread_pool_spy.assert_called_once_with(max_workers=30)

    self.assertEqual(len(results), 2)
    self.assertIn(2, results)
    self.assertIn(4, results)

  def test_concurrent_exec_when_custom_max_workers(self):

    def adder(a, b):
      return a + b

    with mock.patch.object(futures,
                           'ThreadPoolExecutor',
                           wraps=futures.ThreadPoolExecutor) as thread_pool_spy:
      results = utils.concurrent_exec(adder, [(1, 1), (2, 2)], max_workers=1)

    thread_pool_spy.assert_called_once_with(max_workers=1)
    self.assertEqual(len(results), 2)
    self.assertIn(2, results)
    self.assertIn(4, results)

  def test_concurrent_exec_makes_all_calls(self):
    mock_function = mock.MagicMock()
    _ = utils.concurrent_exec(mock_function, [
        (1, 1),
        (2, 2),
        (3, 3),
    ])
    self.assertEqual(mock_function.call_count, 3)
    mock_function.assert_has_calls(
        [mock.call(1, 1), mock.call(2, 2),
         mock.call(3, 3)], any_order=True)

  def test_concurrent_exec_generates_results(self):

    def adder(a, b):
      return a + b

    results = utils.concurrent_exec(adder, [(1, 1), (2, 2)])
    self.assertEqual(len(results), 2)
    self.assertIn(2, results)
    self.assertIn(4, results)

  def test_concurrent_exec_when_exception_makes_all_calls(self):
    mock_call_recorder = mock.MagicMock()
    lock_call_count = threading.Lock()

    def fake_int(a,):
      with lock_call_count:
        mock_call_recorder(a)
      return int(a)

    results = utils.concurrent_exec(fake_int, [
        (1,),
        ('123',),
        ('not_int',),
        (5435,),
    ])

    self.assertEqual(mock_call_recorder.call_count, 4)
    mock_call_recorder.assert_has_calls([
        mock.call(1),
        mock.call('123'),
        mock.call('not_int'),
        mock.call(5435),
    ],
                                        any_order=True)

  def test_concurrent_exec_when_exception_generates_results(self):
    mock_call_recorder = mock.MagicMock()
    lock_call_count = threading.Lock()

    def fake_int(a,):
      with lock_call_count:
        mock_call_recorder(a)
      return int(a)

    results = utils.concurrent_exec(fake_int, [
        (1,),
        ('123',),
        ('not_int',),
        (5435,),
    ])

    self.assertEqual(len(results), 4)
    self.assertIn(1, results)
    self.assertIn(123, results)
    self.assertIn(5435, results)
    exceptions = [result for result in results if isinstance(result, Exception)]
    self.assertEqual(len(exceptions), 1)
    self.assertIsInstance(exceptions[0], ValueError)

  def test_concurrent_exec_when_multiple_exceptions_makes_all_calls(self):
    mock_call_recorder = mock.MagicMock()
    lock_call_count = threading.Lock()

    def fake_int(a,):
      with lock_call_count:
        mock_call_recorder(a)
      return int(a)

    results = utils.concurrent_exec(fake_int, [
        (1,),
        ('not_int1',),
        ('not_int2',),
        (5435,),
    ])

    self.assertEqual(mock_call_recorder.call_count, 4)
    mock_call_recorder.assert_has_calls([
        mock.call(1),
        mock.call('not_int1'),
        mock.call('not_int2'),
        mock.call(5435),
    ],
                                        any_order=True)

  def test_concurrent_exec_when_multiple_exceptions_generates_results(self):
    mock_call_recorder = mock.MagicMock()
    lock_call_count = threading.Lock()

    def fake_int(a,):
      with lock_call_count:
        mock_call_recorder(a)
      return int(a)

    results = utils.concurrent_exec(fake_int, [
        (1,),
        ('not_int1',),
        ('not_int2',),
        (5435,),
    ])

    self.assertEqual(len(results), 4)
    self.assertIn(1, results)
    self.assertIn(5435, results)
    exceptions = [result for result in results if isinstance(result, Exception)]
    self.assertEqual(len(exceptions), 2)
    self.assertIsInstance(exceptions[0], ValueError)
    self.assertIsInstance(exceptions[1], ValueError)
    self.assertNotEqual(exceptions[0], exceptions[1])

  def test_concurrent_exec_when_raising_exception_generates_results(self):

    def adder(a, b):
      return a + b

    results = utils.concurrent_exec(adder, [(1, 1), (2, 2)],
                                    raise_on_exception=True)
    self.assertEqual(len(results), 2)
    self.assertIn(2, results)
    self.assertIn(4, results)

  def test_concurrent_exec_when_raising_exception_makes_all_calls(self):
    mock_call_recorder = mock.MagicMock()
    lock_call_count = threading.Lock()

    def fake_int(a,):
      with lock_call_count:
        mock_call_recorder(a)
      return int(a)

    with self.assertRaisesRegex(RuntimeError, '.*not_int.*'):
      _ = utils.concurrent_exec(fake_int, [
          (1,),
          ('123',),
          ('not_int',),
          (5435,),
      ],
                                raise_on_exception=True)

    self.assertEqual(mock_call_recorder.call_count, 4)
    mock_call_recorder.assert_has_calls([
        mock.call(1),
        mock.call('123'),
        mock.call('not_int'),
        mock.call(5435),
    ],
                                        any_order=True)

  def test_concurrent_exec_when_raising_multiple_exceptions_makes_all_calls(
      self):
    mock_call_recorder = mock.MagicMock()
    lock_call_count = threading.Lock()

    def fake_int(a,):
      with lock_call_count:
        mock_call_recorder(a)
      return int(a)

    with self.assertRaisesRegex(
        RuntimeError,
        r'(?m).*(not_int1(.|\s)+not_int2|not_int2(.|\s)+not_int1).*'):
      _ = utils.concurrent_exec(fake_int, [
          (1,),
          ('not_int1',),
          ('not_int2',),
          (5435,),
      ],
                                raise_on_exception=True)

    self.assertEqual(mock_call_recorder.call_count, 4)
    mock_call_recorder.assert_has_calls([
        mock.call(1),
        mock.call('not_int1'),
        mock.call('not_int2'),
        mock.call(5435),
    ],
                                        any_order=True)

  def test_create_dir(self):
    new_path = os.path.join(self.tmp_dir, 'haha')
    self.assertFalse(os.path.exists(new_path))
    utils.create_dir(new_path)
    self.assertTrue(os.path.exists(new_path))

  def test_create_dir_already_exists(self):
    self.assertTrue(os.path.exists(self.tmp_dir))
    utils.create_dir(self.tmp_dir)
    self.assertTrue(os.path.exists(self.tmp_dir))

  @mock.patch(f'{ADB_MODULE_PACKAGE_NAME}.is_adb_available', return_value=True)
  @mock.patch(f'{ADB_MODULE_PACKAGE_NAME}.list_occupied_adb_ports')
  @mock.patch('portpicker.pick_unused_port', return_value=MOCK_AVAILABLE_PORT)
  def test_get_available_port_positive(self, mock_is_adb_available,
                                       mock_list_occupied_adb_ports,
                                       mock_pick_unused_port):
    self.assertEqual(utils.get_available_host_port(), MOCK_AVAILABLE_PORT)

  @mock.patch(f'{ADB_MODULE_PACKAGE_NAME}.is_adb_available', return_value=False)
  @mock.patch(f'{ADB_MODULE_PACKAGE_NAME}.list_occupied_adb_ports')
  @mock.patch('portpicker.pick_unused_port', return_value=MOCK_AVAILABLE_PORT)
  def test_get_available_port_positive_no_adb(self, mock_is_adb_available,
                                              mock_list_occupied_adb_ports,
                                              mock_pick_unused_port):
    self.assertEqual(utils.get_available_host_port(), MOCK_AVAILABLE_PORT)
    mock_list_occupied_adb_ports.assert_not_called()

  @mock.patch(f'{ADB_MODULE_PACKAGE_NAME}.is_adb_available', return_value=True)
  @mock.patch(f'{ADB_MODULE_PACKAGE_NAME}.list_occupied_adb_ports',
              return_value=[MOCK_AVAILABLE_PORT])
  @mock.patch('portpicker.pick_unused_port', return_value=MOCK_AVAILABLE_PORT)
  def test_get_available_port_negative(self, mock_is_adb_available,
                                       mock_list_occupied_adb_ports,
                                       mock_pick_unused_port):
    with self.assertRaisesRegex(utils.Error, 'Failed to find.* retries'):
      utils.get_available_host_port()

  @mock.patch(f'{ADB_MODULE_PACKAGE_NAME}.list_occupied_adb_ports')
  def test_get_available_port_returns_free_port(self,
                                                mock_list_occupied_adb_ports):
    """Verifies logic to pick a free port on the host.

    Test checks we can bind to either an ipv4 or ipv6 socket on the port
    returned by get_available_host_port.
    """
    port = utils.get_available_host_port()
    got_socket = False
    for family in (socket.AF_INET, socket.AF_INET6):
      try:
        s = socket.socket(family, socket.SOCK_STREAM)
        got_socket = True
        break
      except socket.error:
        continue
    self.assertTrue(got_socket)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
      s.bind(('localhost', port))
    finally:
      s.close()

  def test_load_file_to_base64_str_reads_bytes_file_as_base64_string(self):
    tmp_file_path = os.path.join(self.tmp_dir, 'b64.bin')
    expected_base64_encoding = u'SGVsbG93IHdvcmxkIQ=='
    with io.open(tmp_file_path, 'wb') as f:
      f.write(b'Hellow world!')
    self.assertEqual(utils.load_file_to_base64_str(tmp_file_path),
                     expected_base64_encoding)

  def test_load_file_to_base64_str_reads_text_file_as_base64_string(self):
    tmp_file_path = os.path.join(self.tmp_dir, 'b64.bin')
    expected_base64_encoding = u'SGVsbG93IHdvcmxkIQ=='
    with io.open(tmp_file_path, 'w', encoding='utf-8') as f:
      f.write(u'Hellow world!')
    self.assertEqual(utils.load_file_to_base64_str(tmp_file_path),
                     expected_base64_encoding)

  def test_load_file_to_base64_str_reads_unicode_file_as_base64_string(self):
    tmp_file_path = os.path.join(self.tmp_dir, 'b64.bin')
    expected_base64_encoding = u'6YCa'
    with io.open(tmp_file_path, 'w', encoding='utf-8') as f:
      f.write(u'\u901a')
    self.assertEqual(utils.load_file_to_base64_str(tmp_file_path),
                     expected_base64_encoding)

  def test_cli_cmd_to_string(self):
    cmd = ['"adb"', 'a b', 'c//']
    self.assertEqual(utils.cli_cmd_to_string(cmd), '\'"adb"\' \'a b\' c//')
    cmd = 'adb -s meme do something ab_cd'
    self.assertEqual(utils.cli_cmd_to_string(cmd), cmd)

  def test_get_settable_properties(self):

    class SomeClass:
      regular_attr = 'regular_attr'
      _foo = 'foo'
      _bar = 'bar'

      @property
      def settable_prop(self):
        return self._foo

      @settable_prop.setter
      def settable_prop(self, new_foo):
        self._foo = new_foo

      @property
      def readonly_prop(self):
        return self._bar

      def func(self):
        """Func should not be considered as a settable prop."""

    actual = utils.get_settable_properties(SomeClass)
    self.assertEqual(actual, ['settable_prop'])

  def test_find_subclasses_in_module_when_one_subclass(self):
    subclasses = utils.find_subclasses_in_module([base_test.BaseTestClass],
                                                 integration_test)
    self.assertEqual(len(subclasses), 1)
    self.assertEqual(subclasses[0], integration_test.IntegrationTest)

  def test_find_subclasses_in_module_when_indirect_subclass(self):
    subclasses = utils.find_subclasses_in_module([base_test.BaseTestClass],
                                                 mock_instrumentation_test)
    self.assertEqual(len(subclasses), 1)
    self.assertEqual(subclasses[0],
                     mock_instrumentation_test.MockInstrumentationTest)

  def test_find_subclasses_in_module_when_no_subclasses(self):
    subclasses = utils.find_subclasses_in_module([base_test.BaseTestClass],
                                                 mock_controller)
    self.assertEqual(len(subclasses), 0)

  def test_find_subclasses_in_module_when_multiple_subclasses(self):
    subclasses = utils.find_subclasses_in_module([base_test.BaseTestClass],
                                                 multiple_subclasses_module)
    self.assertEqual(len(subclasses), 2)
    self.assertIn(multiple_subclasses_module.Subclass1Test, subclasses)
    self.assertIn(multiple_subclasses_module.Subclass2Test, subclasses)

  def test_find_subclasses_in_module_when_multiple_base_classes(self):
    subclasses = utils.find_subclasses_in_module(
        [base_test.BaseTestClass, test_runner.TestRunner],
        multiple_subclasses_module)
    self.assertEqual(len(subclasses), 4)
    self.assertIn(multiple_subclasses_module.Subclass1Test, subclasses)
    self.assertIn(multiple_subclasses_module.Subclass2Test, subclasses)
    self.assertIn(multiple_subclasses_module.Subclass1Runner, subclasses)
    self.assertIn(multiple_subclasses_module.Subclass2Runner, subclasses)

  def test_find_subclasses_in_module_when_only_some_base_classes_present(self):
    subclasses = utils.find_subclasses_in_module(
        [signals.TestSignal, test_runner.TestRunner],
        multiple_subclasses_module)
    self.assertEqual(len(subclasses), 2)
    self.assertIn(multiple_subclasses_module.Subclass1Runner, subclasses)
    self.assertIn(multiple_subclasses_module.Subclass2Runner, subclasses)

  def test_find_subclass_in_module_when_one_subclass(self):
    subclass = utils.find_subclass_in_module(base_test.BaseTestClass,
                                             integration_test)
    self.assertEqual(subclass, integration_test.IntegrationTest)

  def test_find_subclass_in_module_when_indirect_subclass(self):
    subclass = utils.find_subclass_in_module(base_test.BaseTestClass,
                                             mock_instrumentation_test)
    self.assertEqual(subclass,
                     mock_instrumentation_test.MockInstrumentationTest)

  def test_find_subclass_in_module_when_no_subclasses(self):
    with self.assertRaisesRegex(
        ValueError, '.*Expected 1 subclass of BaseTestClass per module, found'
        r' \[\].*'):
      _ = utils.find_subclass_in_module(base_test.BaseTestClass,
                                        mock_controller)

  def test_find_subclass_in_module_when_multiple_subclasses(self):
    with self.assertRaisesRegex(
        ValueError, '.*Expected 1 subclass of BaseTestClass per module, found'
        r' \[(\'Subclass1Test\', \'Subclass2Test\''
        r'|\'Subclass2Test\', \'Subclass1Test\')\].*'):
      _ = utils.find_subclass_in_module(base_test.BaseTestClass,
                                        multiple_subclasses_module)


if __name__ == '__main__':
  unittest.main()
