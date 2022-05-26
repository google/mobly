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
"""Unit tests for mobly.controllers.android_device_lib.snippet_client_v2."""

import socket
import unittest
from unittest import mock

from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import errors as android_device_lib_errors
from mobly.controllers.android_device_lib import snippet_client_v2
from mobly.snippet import errors
from tests.lib import mock_android_device

MOCK_PACKAGE_NAME = 'some.package.name'
MOCK_SERVER_PATH = f'{MOCK_PACKAGE_NAME}/{snippet_client_v2._INSTRUMENTATION_RUNNER_PACKAGE}'
MOCK_USER_ID = 0
MOCK_DEVICE_PORT = 1234


class _MockAdbProxy(mock_android_device.MockAdbProxy):
  """Mock class of adb proxy which covers all the calls used by snippet clients.

  To enable testing snippet clients, this class extends the functionality of
  base class from the following aspects:
  * Records the arguments of all the calls to the shell method and forward
    method.
  * Handles the adb calls to stop the snippet server in the shell function
    properly.


  Attributes:
    mock_shell_func: mock.Mock, used for recording the calls to the shell
      method.
    mock_forward_func: mock.Mock, used for recording the calls to the forward
      method.
  """

  def __init__(self, *args, **kwargs):
    """Initializes the instance of _MockAdbProxy."""
    super().__init__(*args, **kwargs)
    self.mock_shell_func = mock.Mock()
    self.mock_forward_func = mock.Mock()

  def shell(self, *args, **kwargs):
    """Mock `shell` of mobly.controllers.android_device_lib.adb.AdbProxy."""
    # Record all the call args
    self.mock_shell_func(*args, **kwargs)

    # Handle the server stop command properly
    if f'am instrument --user 0 -w -e action stop {MOCK_SERVER_PATH}' in args:
      return b'OK (0 tests)'

    # For other commands, hand it over to the base class.
    return super().shell(*args, **kwargs)

  def forward(self, *args, **kwargs):
    """Mock `forward` of mobly.controllers.android_device_lib.adb.AdbProxy."""
    self.mock_forward_func(*args, **kwargs)


def _setup_mock_socket_file(mock_socket_create_conn, resp):
  """Sets up a mock socket file from the mock connection.

  Args:
    mock_socket_create_conn: The mock method for creating a socket connection.
    resp: iterable, the side effect of the `readline` function of the mock
      socket file.

  Returns:
    The mock socket file that will be injected into the code.
  """
  fake_file = mock.Mock()
  fake_file.readline.side_effect = resp
  fake_conn = mock.Mock()
  fake_conn.makefile.return_value = fake_file
  mock_socket_create_conn.return_value = fake_conn
  return fake_file


class SnippetClientV2Test(unittest.TestCase):
  """Unit tests for SnippetClientV2."""

  def _make_client(self, adb_proxy=None, mock_properties=None):
    adb_proxy = adb_proxy or _MockAdbProxy(instrumented_packages=[
        (MOCK_PACKAGE_NAME, snippet_client_v2._INSTRUMENTATION_RUNNER_PACKAGE,
         MOCK_PACKAGE_NAME)
    ],
                                           mock_properties=mock_properties)
    self.adb = adb_proxy

    device = mock.Mock()
    device.adb = adb_proxy
    device.adb.current_user_id = MOCK_USER_ID
    device.build_info = {
        'build_version_codename':
            adb_proxy.getprop('ro.build.version.codename'),
        'build_version_sdk':
            adb_proxy.getprop('ro.build.version.sdk'),
    }
    self.device = device

    self.client = snippet_client_v2.SnippetClientV2(MOCK_PACKAGE_NAME, device)

  def _make_client_with_extra_adb_properties(self, extra_properties):
    mock_properties = mock_android_device.DEFAULT_MOCK_PROPERTIES.copy()
    mock_properties.update(extra_properties)
    self._make_client(mock_properties=mock_properties)

  def _mock_server_process_starting_response(self,
                                             mock_start_subprocess,
                                             resp_lines=None):
    resp_lines = resp_lines or [
        b'SNIPPET START, PROTOCOL 1 0', b'SNIPPET SERVING, PORT 1234'
    ]
    mock_proc = mock_start_subprocess.return_value
    mock_proc.stdout.readline.side_effect = resp_lines

  def _make_client_and_mock_socket_conn(self,
                                        mock_socket_create_conn,
                                        socket_resp=None,
                                        device_port=MOCK_DEVICE_PORT,
                                        adb_proxy=None,
                                        mock_properties=None,
                                        set_counter=True):
    """Makes the snippet client and mocks the socket connection."""
    self._make_client(adb_proxy, mock_properties)

    if socket_resp is None:
      socket_resp = [b'{"status": true, "uid": 1}']
    self.mock_socket_file = _setup_mock_socket_file(mock_socket_create_conn,
                                                    socket_resp)
    self.client.device_port = device_port
    self.socket_conn = mock_socket_create_conn.return_value
    if set_counter:
      self.client._counter = self.client._id_counter()

  def _assert_client_resources_released(self, mock_start_subprocess,
                                        mock_stop_standing_subprocess,
                                        mock_get_port):
    """Asserts the resources had been released before the client stopped."""
    self.assertIs(self.client._proc, None)
    self.adb.mock_shell_func.assert_any_call(
        f'am instrument --user {MOCK_USER_ID} -w -e action stop '
        f'{MOCK_SERVER_PATH}')
    mock_stop_standing_subprocess.assert_called_once_with(
        mock_start_subprocess.return_value)
    self.assertFalse(self.client.is_alive)
    self.assertIs(self.client._conn, None)
    self.socket_conn.close.assert_called()
    self.assertIs(self.client.host_port, None)
    self.adb.mock_forward_func.assert_any_call(
        ['--remove', f'tcp:{mock_get_port.return_value}'])
    self.assertIsNone(self.client._event_client)

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port',
              return_value=12345)
  @mock.patch('socket.create_connection')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_the_whole_lifecycle_with_a_sync_rpc(self, mock_start_subprocess,
                                               mock_stop_standing_subprocess,
                                               mock_socket_create_conn,
                                               mock_get_port):
    """Tests the whole lifecycle of the client with sending a sync RPC."""
    socket_resp = [
        b'{"status": true, "uid": 1}',
        b'{"id": 0, "result": 123, "error": null, "callback": null}',
    ]
    expected_socket_writes = [
        mock.call(b'{"cmd": "initiate", "uid": -1}\n'),
        mock.call(b'{"id": 0, "method": "some_sync_rpc", '
                  b'"params": [1, 2, "hello"]}\n'),
    ]
    self._make_client_and_mock_socket_conn(mock_socket_create_conn,
                                           socket_resp,
                                           set_counter=False)
    self._mock_server_process_starting_response(mock_start_subprocess)

    self.client.initialize()
    rpc_result = self.client.some_sync_rpc(1, 2, 'hello')
    self.client.stop()

    self._assert_client_resources_released(mock_start_subprocess,
                                           mock_stop_standing_subprocess,
                                           mock_get_port)

    self.assertListEqual(self.mock_socket_file.write.call_args_list,
                         expected_socket_writes)
    self.assertEqual(rpc_result, 123)

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port',
              return_value=12345)
  @mock.patch('socket.create_connection')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  @mock.patch('mobly.snippet.general_callback_handler.GeneralCallbackHandler')
  def test_the_whole_lifecycle_with_an_async_rpc(self, mock_callback_class,
                                                 mock_start_subprocess,
                                                 mock_stop_standing_subprocess,
                                                 mock_socket_create_conn,
                                                 mock_get_port):
    """Tests the whole lifecycle of the client with sending an async RPC."""
    mock_socket_resp = [
        b'{"status": true, "uid": 1}',
        b'{"id": 0, "result": 123, "error": null, "callback": "1-0"}',
        b'{"status": true, "uid": 1}',
    ]
    expected_socket_writes = [
        mock.call(b'{"cmd": "initiate", "uid": -1}\n'),
        mock.call(b'{"id": 0, "method": "some_async_rpc", '
                  b'"params": [1, 2, "async"]}\n'),
        mock.call(b'{"cmd": "continue", "uid": 1}\n'),
    ]
    self._make_client_and_mock_socket_conn(mock_socket_create_conn,
                                           mock_socket_resp,
                                           set_counter=False)
    self._mock_server_process_starting_response(mock_start_subprocess)

    self.client.initialize()
    rpc_result = self.client.some_async_rpc(1, 2, 'async')
    event_client = self.client._event_client
    self.client.stop()

    self._assert_client_resources_released(mock_start_subprocess,
                                           mock_stop_standing_subprocess,
                                           mock_get_port)

    self.assertListEqual(self.mock_socket_file.write.call_args_list,
                         expected_socket_writes)
    mock_callback_class.assert_called_with(
        callback_id='1-0',
        event_client=event_client,
        ret_value=123,
        method_name='some_async_rpc',
        device=self.device,
        rpc_max_timeout_sec=snippet_client_v2._SOCKET_READ_TIMEOUT,
        default_timeout_sec=snippet_client_v2._CALLBACK_DEFAULT_TIMEOUT_SEC)
    self.assertIs(rpc_result, mock_callback_class.return_value)
    self.assertIsNone(event_client.host_port, None)
    self.assertIsNone(event_client.device_port, None)

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port',
              return_value=12345)
  @mock.patch('socket.create_connection')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  @mock.patch('mobly.snippet.general_callback_handler.GeneralCallbackHandler')
  def test_the_whole_lifecycle_with_multiple_rpcs(self, mock_callback_class,
                                                  mock_start_subprocess,
                                                  mock_stop_standing_subprocess,
                                                  mock_socket_create_conn,
                                                  mock_get_port):
    """Tests the whole lifecycle of the client with sending multiple RPCs."""
    # Prepare the test
    mock_socket_resp = [
        b'{"status": true, "uid": 1}',
        b'{"id": 0, "result": 123, "error": null, "callback": null}',
        b'{"id": 1, "result": 456, "error": null, "callback": "1-0"}',
        # Response for starting the event client
        b'{"status": true, "uid": 1}',
        b'{"id": 2, "result": 789, "error": null, "callback": null}',
        b'{"id": 3, "result": 321, "error": null, "callback": "2-0"}',
    ]
    self._make_client_and_mock_socket_conn(mock_socket_create_conn,
                                           mock_socket_resp,
                                           set_counter=False)
    self._mock_server_process_starting_response(mock_start_subprocess)

    rpc_results_expected = [
        123,
        mock.Mock(),
        789,
        mock.Mock(),
    ]
    # Extract the two mock objects to use as return values of callback handler
    # class
    mock_callback_class.side_effect = [
        rpc_results_expected[1], rpc_results_expected[3]
    ]

    # Run tests
    rpc_results = []
    self.client.initialize()
    rpc_results.append(self.client.some_sync_rpc(1, 2, 'hello'))
    rpc_results.append(self.client.some_async_rpc(3, 4, 'async'))
    rpc_results.append(self.client.some_sync_rpc(5, 'hello'))
    rpc_results.append(self.client.some_async_rpc(6, 'async'))
    event_client = self.client._event_client
    self.client.stop()

    # Assertions
    mock_callback_class_calls_expected = [
        mock.call(
            callback_id='1-0',
            event_client=event_client,
            ret_value=456,
            method_name='some_async_rpc',
            device=self.device,
            rpc_max_timeout_sec=snippet_client_v2._SOCKET_READ_TIMEOUT,
            default_timeout_sec=(
                snippet_client_v2._CALLBACK_DEFAULT_TIMEOUT_SEC)),
        mock.call(
            callback_id='2-0',
            event_client=event_client,
            ret_value=321,
            method_name='some_async_rpc',
            device=self.device,
            rpc_max_timeout_sec=snippet_client_v2._SOCKET_READ_TIMEOUT,
            default_timeout_sec=snippet_client_v2._CALLBACK_DEFAULT_TIMEOUT_SEC)
    ]
    self.assertListEqual(rpc_results, rpc_results_expected)
    mock_callback_class.assert_has_calls(mock_callback_class_calls_expected)
    self._assert_client_resources_released(mock_start_subprocess,
                                           mock_stop_standing_subprocess,
                                           mock_get_port)
    self.assertIsNone(event_client.host_port, None)
    self.assertIsNone(event_client.device_port, None)

  def test_check_app_installed_normally(self):
    """Tests that app checker runs normally when app installed correctly."""
    self._make_client()
    self.client._validate_snippet_app_on_device()

  def test_check_app_installed_fail_app_not_installed(self):
    """Tests that app checker fails without installing app."""
    self._make_client(_MockAdbProxy())
    expected_msg = f'.* {MOCK_PACKAGE_NAME} is not installed.'
    with self.assertRaisesRegex(errors.ServerStartPreCheckError, expected_msg):
      self.client._validate_snippet_app_on_device()

  def test_check_app_installed_fail_not_instrumented(self):
    """Tests that app checker fails without instrumenting app."""
    self._make_client(_MockAdbProxy(installed_packages=[MOCK_PACKAGE_NAME]))
    expected_msg = (
        f'.* {MOCK_PACKAGE_NAME} is installed, but it is not instrumented.')
    with self.assertRaisesRegex(errors.ServerStartPreCheckError, expected_msg):
      self.client._validate_snippet_app_on_device()

  def test_check_app_installed_fail_instrumentation_not_installed(self):
    """Tests that app checker fails without installing instrumentation."""
    self._make_client(
        _MockAdbProxy(instrumented_packages=[(
            MOCK_PACKAGE_NAME,
            snippet_client_v2._INSTRUMENTATION_RUNNER_PACKAGE,
            'not.installed')]))
    expected_msg = ('.* Instrumentation target not.installed is not installed.')
    with self.assertRaisesRegex(errors.ServerStartPreCheckError, expected_msg):
      self.client._validate_snippet_app_on_device()

  def test_disable_hidden_api_normally(self):
    """Tests the disabling hidden api process works normally."""
    self._make_client_with_extra_adb_properties({
        'ro.build.version.codename': 'S',
        'ro.build.version.sdk': '31',
    })
    self.device.is_rootable = True
    self.client._disable_hidden_api_blocklist()
    self.adb.mock_shell_func.assert_called_with(
        'settings put global hidden_api_blacklist_exemptions "*"')

  def test_disable_hidden_api_low_sdk(self):
    """Tests it doesn't disable hidden api with low SDK."""
    self._make_client_with_extra_adb_properties({
        'ro.build.version.codename': 'O',
        'ro.build.version.sdk': '26',
    })
    self.device.is_rootable = True
    self.client._disable_hidden_api_blocklist()
    self.adb.mock_shell_func.assert_not_called()

  def test_disable_hidden_api_non_rootable(self):
    """Tests it doesn't disable hidden api with non-rootable device."""
    self._make_client_with_extra_adb_properties({
        'ro.build.version.codename': 'S',
        'ro.build.version.sdk': '31',
    })
    self.device.is_rootable = False
    self.client._disable_hidden_api_blocklist()
    self.adb.mock_shell_func.assert_not_called()

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  @mock.patch.object(_MockAdbProxy, 'shell', return_value=b'setsid')
  def test_start_server_with_user_id(self, mock_adb, mock_start_subprocess):
    """Tests that `--user` is added to starting command with SDK >= 24."""
    self._make_client_with_extra_adb_properties({'ro.build.version.sdk': '30'})
    self._mock_server_process_starting_response(mock_start_subprocess)

    self.client.start_server()
    start_cmd_list = [
        'adb', 'shell',
        (f'setsid am instrument --user {MOCK_USER_ID} -w -e action start '
         f'{MOCK_SERVER_PATH}')
    ]
    self.assertListEqual(mock_start_subprocess.call_args_list,
                         [mock.call(start_cmd_list, shell=False)])
    self.assertEqual(self.client.device_port, 1234)
    mock_adb.assert_called_with(['which', 'setsid'])

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  @mock.patch.object(_MockAdbProxy, 'shell', return_value=b'setsid')
  def test_start_server_without_user_id(self, mock_adb, mock_start_subprocess):
    """Tests that `--user` is not added to starting command on SDK < 24."""
    self._make_client_with_extra_adb_properties({'ro.build.version.sdk': '21'})
    self._mock_server_process_starting_response(mock_start_subprocess)

    self.client.start_server()
    start_cmd_list = [
        'adb', 'shell',
        f'setsid am instrument  -w -e action start {MOCK_SERVER_PATH}'
    ]
    self.assertListEqual(mock_start_subprocess.call_args_list,
                         [mock.call(start_cmd_list, shell=False)])
    mock_adb.assert_called_with(['which', 'setsid'])
    self.assertEqual(self.client.device_port, 1234)

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  @mock.patch.object(_MockAdbProxy,
                     'shell',
                     side_effect=adb.AdbError('cmd', 'stdout', 'stderr',
                                              'ret_code'))
  def test_start_server_without_persisting_commands(self, mock_adb,
                                                    mock_start_subprocess):
    """Checks the starting server command without persisting commands."""
    self._make_client()
    self._mock_server_process_starting_response(mock_start_subprocess)

    self.client.start_server()
    start_cmd_list = [
        'adb', 'shell',
        (f' am instrument --user {MOCK_USER_ID} -w -e action start '
         f'{MOCK_SERVER_PATH}')
    ]
    self.assertListEqual(mock_start_subprocess.call_args_list,
                         [mock.call(start_cmd_list, shell=False)])
    mock_adb.assert_has_calls(
        [mock.call(['which', 'setsid']),
         mock.call(['which', 'nohup'])])
    self.assertEqual(self.client.device_port, 1234)

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_start_server_with_nohup(self, mock_start_subprocess):
    """Checks the starting server command with nohup."""
    self._make_client()
    self._mock_server_process_starting_response(mock_start_subprocess)

    def _mocked_shell(arg):
      if 'nohup' in arg:
        return b'nohup'
      raise adb.AdbError('cmd', 'stdout', 'stderr', 'ret_code')

    self.client._adb.shell = _mocked_shell

    self.client.start_server()
    start_cmd_list = [
        'adb', 'shell',
        (f'nohup am instrument --user {MOCK_USER_ID} -w -e action start '
         f'{MOCK_SERVER_PATH}')
    ]
    self.assertListEqual(mock_start_subprocess.call_args_list,
                         [mock.call(start_cmd_list, shell=False)])
    self.assertEqual(self.client.device_port, 1234)

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_start_server_with_setsid(self, mock_start_subprocess):
    """Checks the starting server command with setsid."""
    self._make_client()
    self._mock_server_process_starting_response(mock_start_subprocess)

    def _mocked_shell(arg):
      if 'setsid' in arg:
        return b'setsid'
      raise adb.AdbError('cmd', 'stdout', 'stderr', 'ret_code')

    self.client._adb.shell = _mocked_shell
    self.client.start_server()
    start_cmd_list = [
        'adb', 'shell',
        (f'setsid am instrument --user {MOCK_USER_ID} -w -e action start '
         f'{MOCK_SERVER_PATH}')
    ]
    self.assertListEqual(mock_start_subprocess.call_args_list,
                         [mock.call(start_cmd_list, shell=False)])
    self.assertEqual(self.client.device_port, 1234)

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_start_server_server_crash(self, mock_start_standing_subprocess):
    """Tests that starting server process crashes."""
    self._make_client()
    self._mock_server_process_starting_response(
        mock_start_standing_subprocess,
        resp_lines=[b'INSTRUMENTATION_RESULT: shortMsg=Process crashed.\n'])
    with self.assertRaisesRegex(
        errors.ServerStartProtocolError,
        'INSTRUMENTATION_RESULT: shortMsg=Process crashed.'):
      self.client.start_server()

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_start_server_unknown_protocol_version(
      self, mock_start_standing_subprocess):
    """Tests that starting server process reports unknown protocol version."""
    self._make_client()
    self._mock_server_process_starting_response(
        mock_start_standing_subprocess,
        resp_lines=[b'SNIPPET START, PROTOCOL 99 0\n'])
    with self.assertRaisesRegex(errors.ServerStartProtocolError,
                                'SNIPPET START, PROTOCOL 99 0'):
      self.client.start_server()

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_start_server_invalid_device_port(self,
                                            mock_start_standing_subprocess):
    """Tests that starting server process reports invalid device port."""
    self._make_client()
    self._mock_server_process_starting_response(
        mock_start_standing_subprocess,
        resp_lines=[
            b'SNIPPET START, PROTOCOL 1 0\n', b'SNIPPET SERVING, PORT ABC\n'
        ])
    with self.assertRaisesRegex(errors.ServerStartProtocolError,
                                'SNIPPET SERVING, PORT ABC'):
      self.client.start_server()

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_start_server_with_junk(self, mock_start_standing_subprocess):
    """Tests that starting server process reports known protocol with junk."""
    self._make_client()
    self._mock_server_process_starting_response(
        mock_start_standing_subprocess,
        resp_lines=[
            b'This is some header junk\n',
            b'Some phones print arbitrary output\n',
            b'SNIPPET START, PROTOCOL 1 0\n',
            b'Maybe in the middle too\n',
            b'SNIPPET SERVING, PORT 123\n',
        ])
    self.client.start_server()
    self.assertEqual(123, self.client.device_port)

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_start_server_no_valid_line(self, mock_start_standing_subprocess):
    """Tests that starting server process reports unknown protocol message."""
    self._make_client()
    self._mock_server_process_starting_response(
        mock_start_standing_subprocess,
        resp_lines=[
            b'This is some header junk\n',
            b'Some phones print arbitrary output\n',
            b'',  # readline uses '' to mark EOF
        ])
    with self.assertRaisesRegex(
        errors.ServerStartError,
        'Unexpected EOF when waiting for server to start.'):
      self.client.start_server()

  @mock.patch('mobly.utils.stop_standing_subprocess')
  def test_stop_normally(self, mock_stop_standing_subprocess):
    """Tests that stopping server process works normally."""
    self._make_client()
    mock_proc = mock.Mock()
    self.client._proc = mock_proc
    mock_conn = mock.Mock()
    self.client._conn = mock_conn
    self.client.host_port = 12345

    self.client.stop()

    self.assertIs(self.client._proc, None)
    self.adb.mock_shell_func.assert_called_once_with(
        f'am instrument --user {MOCK_USER_ID} -w -e action stop '
        f'{MOCK_SERVER_PATH}')
    mock_stop_standing_subprocess.assert_called_once_with(mock_proc)
    self.assertFalse(self.client.is_alive)
    self.assertIs(self.client._conn, None)
    mock_conn.close.assert_called_once_with()
    self.assertIs(self.client.host_port, None)
    self.device.adb.mock_forward_func.assert_called_once_with(
        ['--remove', 'tcp:12345'])
    self.assertIsNone(self.client._event_client)

  @mock.patch('mobly.utils.stop_standing_subprocess')
  def test_stop_when_server_is_already_cleaned(self,
                                               mock_stop_standing_subprocess):
    """Tests that stop server process when subprocess is already cleaned."""
    self._make_client()
    self.client._proc = None
    mock_conn = mock.Mock()
    self.client._conn = mock_conn
    self.client.host_port = 12345

    self.client.stop()

    self.assertIs(self.client._proc, None)
    mock_stop_standing_subprocess.assert_not_called()
    self.adb.assert_called_once_with(
        f'am instrument --user {MOCK_USER_ID} -w -e action stop '
        f'{MOCK_SERVER_PATH}')
    self.assertFalse(self.client.is_alive)
    self.assertIs(self.client._conn, None)
    mock_conn.close.assert_called_once_with()
    self.assertIs(self.client.host_port, None)
    self.device.adb.mock_forward_func.assert_called_once_with(
        ['--remove', 'tcp:12345'])

  @mock.patch('mobly.utils.stop_standing_subprocess')
  def test_stop_when_conn_is_already_cleaned(self,
                                             mock_stop_standing_subprocess):
    """Tests that stop server process when the connection is already closed."""
    self._make_client()
    mock_proc = mock.Mock()
    self.client._proc = mock_proc
    self.client._conn = None
    self.client.host_port = 12345

    self.client.stop()

    self.assertIs(self.client._proc, None)
    mock_stop_standing_subprocess.assert_called_once_with(mock_proc)
    self.adb.assert_called_once_with(
        f'am instrument --user {MOCK_USER_ID} -w -e action stop '
        f'{MOCK_SERVER_PATH}')
    self.assertFalse(self.client.is_alive)
    self.assertIs(self.client._conn, None)
    self.assertIs(self.client.host_port, None)
    self.device.adb.mock_forward_func.assert_called_once_with(
        ['--remove', 'tcp:12345'])

  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(_MockAdbProxy, 'shell', return_value=b'Closed with error.')
  def test_stop_with_device_side_error(self, mock_adb_shell,
                                       mock_stop_standing_subprocess):
    """Tests all resources will be cleaned when server stop throws an error."""
    self._make_client()
    mock_proc = mock.Mock()
    self.client._proc = mock_proc
    mock_conn = mock.Mock()
    self.client._conn = mock_conn
    self.client.host_port = 12345
    with self.assertRaisesRegex(android_device_lib_errors.DeviceError,
                                'Closed with error'):
      self.client.stop()

    self.assertIs(self.client._proc, None)
    mock_stop_standing_subprocess.assert_called_once_with(mock_proc)
    mock_adb_shell.assert_called_once_with(
        f'am instrument --user {MOCK_USER_ID} -w -e action stop '
        f'{MOCK_SERVER_PATH}')
    self.assertFalse(self.client.is_alive)
    self.assertIs(self.client._conn, None)
    mock_conn.close.assert_called_once_with()
    self.assertIs(self.client.host_port, None)
    self.device.adb.mock_forward_func.assert_called_once_with(
        ['--remove', 'tcp:12345'])

  @mock.patch('mobly.utils.stop_standing_subprocess')
  def test_stop_with_conn_close_error(self, mock_stop_standing_subprocess):
    """Tests port resource will be cleaned when socket close throws an error."""
    del mock_stop_standing_subprocess
    self._make_client()
    mock_proc = mock.Mock()
    self.client._proc = mock_proc
    mock_conn = mock.Mock()
    # The deconstructor will call this mock function again after tests, so
    # only throw this error when it is called the first time.
    mock_conn.close.side_effect = (OSError('Closed with error'), None)
    self.client._conn = mock_conn
    self.client.host_port = 12345
    with self.assertRaisesRegex(OSError, 'Closed with error'):
      self.client.stop()

    self.device.adb.mock_forward_func.assert_called_once_with(
        ['--remove', 'tcp:12345'])

  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(snippet_client_v2.SnippetClientV2,
                     'create_socket_connection')
  @mock.patch.object(snippet_client_v2.SnippetClientV2,
                     'send_handshake_request')
  def test_stop_with_event_client(self, mock_send_handshake_func,
                                  mock_create_socket_conn_func,
                                  mock_stop_standing_subprocess):
    """Tests that stopping with an event client works normally."""
    del mock_send_handshake_func
    del mock_create_socket_conn_func
    del mock_stop_standing_subprocess
    self._make_client()
    self.client.host_port = 12345
    self.client.device_port = 45678
    snippet_client_conn = mock.Mock()
    self.client._conn = snippet_client_conn
    self.client._create_event_client()
    event_client = self.client._event_client
    event_client_conn = mock.Mock()
    event_client._conn = event_client_conn

    self.client.stop()

    # The snippet client called close method once
    snippet_client_conn.close.assert_called_once_with()
    # The event client called close method once
    event_client_conn.close.assert_called_once_with()
    self.assertIsNone(event_client._conn)
    self.assertIsNone(event_client.host_port)
    self.assertIsNone(event_client.device_port)
    self.assertIsNone(self.client._event_client)
    self.assertIs(self.client.host_port, None)
    self.device.adb.mock_forward_func.assert_called_once_with(
        ['--remove', 'tcp:12345'])

  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(snippet_client_v2.SnippetClientV2,
                     'create_socket_connection')
  @mock.patch.object(snippet_client_v2.SnippetClientV2,
                     'send_handshake_request')
  def test_stop_with_event_client_stops_port_forwarding_once(
      self, mock_send_handshake_func, mock_create_socket_conn_func,
      mock_stop_standing_subprocess):
    """Tests that client with an event client stops port forwarding once."""
    del mock_send_handshake_func
    del mock_create_socket_conn_func
    del mock_stop_standing_subprocess
    self._make_client()
    self.client.host_port = 12345
    self.client.device_port = 45678
    self.client._create_event_client()
    event_client = self.client._event_client

    self.client.stop()
    event_client.__del__()
    self.client.__del__()

    self.assertIsNone(self.client._event_client)
    self.device.adb.mock_forward_func.assert_called_once_with(
        ['--remove', 'tcp:12345'])

  def test_close_connection_normally(self):
    """Tests that closing connection works normally."""
    self._make_client()
    mock_conn = mock.Mock()
    self.client._conn = mock_conn
    self.client.host_port = 123

    self.client.close_connection()

    self.assertIs(self.client._conn, None)
    self.assertIs(self.client.host_port, None)
    mock_conn.close.assert_called_once_with()
    self.device.adb.mock_forward_func.assert_called_once_with(
        ['--remove', 'tcp:123'])

  def test_close_connection_when_host_port_has_been_released(self):
    """Tests that close connection when the host port has been released."""
    self._make_client()
    mock_conn = mock.Mock()
    self.client._conn = mock_conn
    self.client.host_port = None

    self.client.close_connection()

    self.assertIs(self.client._conn, None)
    self.assertIs(self.client.host_port, None)
    mock_conn.close.assert_called_once_with()
    self.device.adb.mock_forward_func.assert_not_called()

  def test_close_connection_when_conn_have_been_closed(self):
    """Tests that close connection when the connection has been closed."""
    self._make_client()
    self.client._conn = None
    self.client.host_port = 123

    self.client.close_connection()

    self.assertIs(self.client._conn, None)
    self.assertIs(self.client.host_port, None)
    self.device.adb.mock_forward_func.assert_called_once_with(
        ['--remove', 'tcp:123'])

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port',
              return_value=12345)
  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_send_sync_rpc_normally(self, mock_start_subprocess,
                                  mock_socket_create_conn, mock_get_port):
    """Tests that sending a sync RPC works normally."""
    del mock_get_port
    socket_resp = [
        b'{"status": true, "uid": 1}',
        b'{"id": 0, "result": 123, "error": null, "callback": null}',
    ]
    self._make_client_and_mock_socket_conn(mock_socket_create_conn, socket_resp)
    self._mock_server_process_starting_response(mock_start_subprocess)

    self.client.make_connection()
    rpc_result = self.client.some_rpc(1, 2, 'hello')

    self.assertEqual(rpc_result, 123)
    self.mock_socket_file.write.assert_called_with(
        b'{"id": 0, "method": "some_rpc", "params": [1, 2, "hello"]}\n')

  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  @mock.patch('mobly.snippet.general_callback_handler.GeneralCallbackHandler')
  def test_async_rpc_start_event_client(self, mock_callback_class,
                                        mock_start_subprocess,
                                        mock_socket_create_conn):
    """Tests that sending an async RPC starts the event client."""
    socket_resp = [
        b'{"status": true, "uid": 1}',
        b'{"id": 0, "result": 123, "error": null, "callback": "1-0"}',
        b'{"status": true, "uid": 1}',
        b'{"id":1,"result":"async-rpc-event","callback":null,"error":null}',
    ]
    socket_write_expected = [
        mock.call(b'{"cmd": "initiate", "uid": -1}\n'),
        mock.call(b'{"id": 0, "method": "some_async_rpc", '
                  b'"params": [1, 2, "hello"]}\n'),
        mock.call(b'{"cmd": "continue", "uid": 1}\n'),
        mock.call(b'{"id": 1, "method": "eventGetAll", '
                  b'"params": ["1-0", "eventName"]}\n'),
    ]
    self._make_client_and_mock_socket_conn(mock_socket_create_conn,
                                           socket_resp,
                                           set_counter=True)
    self._mock_server_process_starting_response(mock_start_subprocess)

    self.client.host_port = 12345
    self.client.make_connection()
    rpc_result = self.client.some_async_rpc(1, 2, 'hello')

    mock_callback_class.assert_called_with(
        callback_id='1-0',
        event_client=self.client._event_client,
        ret_value=123,
        method_name='some_async_rpc',
        device=self.device,
        rpc_max_timeout_sec=snippet_client_v2._SOCKET_READ_TIMEOUT,
        default_timeout_sec=snippet_client_v2._CALLBACK_DEFAULT_TIMEOUT_SEC)
    self.assertIs(rpc_result, mock_callback_class.return_value)

    # Ensure the event client is alive
    self.assertTrue(self.client._event_client.is_alive)

    # Ensure the event client shared the same ports and uid with main client
    self.assertEqual(self.client._event_client.host_port, 12345)
    self.assertEqual(self.client._event_client.device_port, MOCK_DEVICE_PORT)
    self.assertEqual(self.client._event_client.uid, self.client.uid)

    # Ensure the event client has reset its own RPC id counter
    self.assertEqual(next(self.client._counter), 1)
    self.assertEqual(next(self.client._event_client._counter), 0)

    # Ensure that event client can send RPCs
    event_string = self.client._event_client.eventGetAll('1-0', 'eventName')
    self.assertEqual(event_string, 'async-rpc-event')
    self.assertListEqual(
        self.mock_socket_file.write.call_args_list,
        socket_write_expected,
    )

  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port')
  def test_initialize_client_normally(self, mock_get_port,
                                      mock_start_subprocess,
                                      mock_socket_create_conn):
    """Tests that initializing the client works normally."""
    mock_get_port.return_value = 12345
    socket_resp = [b'{"status": true, "uid": 1}']
    self._make_client_and_mock_socket_conn(mock_socket_create_conn,
                                           socket_resp,
                                           set_counter=True)
    self._mock_server_process_starting_response(mock_start_subprocess)

    self.client.initialize()
    self.assertTrue(self.client.is_alive)
    self.assertEqual(self.client.uid, 1)
    self.assertEqual(self.client.host_port, 12345)
    self.assertEqual(self.client.device_port, MOCK_DEVICE_PORT)
    self.assertEqual(next(self.client._counter), 0)

  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port')
  def test_restore_event_client(self, mock_get_port, mock_start_subprocess,
                                mock_socket_create_conn):
    """Tests restoring the event client."""
    mock_get_port.return_value = 12345
    socket_resp = [
        # response of handshake when initializing the client
        b'{"status": true, "uid": 1}',
        # response of an async RPC
        b'{"id": 0, "result": 123, "error": null, "callback": "1-0"}',
        # response of starting event client
        b'{"status": true, "uid": 1}',
        # response of restoring server connection
        b'{"status": true, "uid": 2}',
        # response of restoring event client
        b'{"status": true, "uid": 3}',
        # response of restoring server connection
        b'{"status": true, "uid": 4}',
        # response of restoring event client
        b'{"status": true, "uid": 5}',
    ]
    socket_write_expected = [
        # request of handshake when initializing the client
        mock.call(b'{"cmd": "initiate", "uid": -1}\n'),
        # request of an async RPC
        mock.call(b'{"id": 0, "method": "some_async_rpc", "params": []}\n'),
        # request of starting event client
        mock.call(b'{"cmd": "continue", "uid": 1}\n'),
        # request of restoring server connection
        mock.call(b'{"cmd": "initiate", "uid": -1}\n'),
        # request of restoring event client
        mock.call(b'{"cmd": "initiate", "uid": -1}\n'),
        # request of restoring server connection
        mock.call(b'{"cmd": "initiate", "uid": -1}\n'),
        # request of restoring event client
        mock.call(b'{"cmd": "initiate", "uid": -1}\n'),
    ]
    self._make_client_and_mock_socket_conn(mock_socket_create_conn, socket_resp)
    self._mock_server_process_starting_response(mock_start_subprocess)

    self.client.make_connection()
    callback = self.client.some_async_rpc()

    # before reconnect, clients use previously selected ports
    self.assertEqual(self.client.host_port, 12345)
    self.assertEqual(self.client.device_port, MOCK_DEVICE_PORT)
    self.assertEqual(callback._event_client.host_port, 12345)
    self.assertEqual(callback._event_client.device_port, MOCK_DEVICE_PORT)
    self.assertEqual(next(self.client._event_client._counter), 0)

    # after reconnect, if host port specified, clients use specified port
    self.client.restore_server_connection(port=54321)
    self.assertEqual(self.client.host_port, 54321)
    self.assertEqual(self.client.device_port, MOCK_DEVICE_PORT)
    self.assertEqual(callback._event_client.host_port, 54321)
    self.assertEqual(callback._event_client.device_port, MOCK_DEVICE_PORT)
    self.assertEqual(next(self.client._event_client._counter), 0)

    # after reconnect, if host port not specified, clients use selected
    # available port
    mock_get_port.return_value = 56789
    self.client.restore_server_connection()
    self.assertEqual(self.client.host_port, 56789)
    self.assertEqual(self.client.device_port, MOCK_DEVICE_PORT)
    self.assertEqual(callback._event_client.host_port, 56789)
    self.assertEqual(callback._event_client.device_port, MOCK_DEVICE_PORT)
    self.assertEqual(next(self.client._event_client._counter), 0)

    # if unable to reconnect for any reason, a
    # errors.ServerRestoreConnectionError is raised.
    mock_socket_create_conn.side_effect = IOError('socket timed out')
    with self.assertRaisesRegex(
        errors.ServerRestoreConnectionError,
        (f'Failed to restore server connection for {MOCK_PACKAGE_NAME} at '
         f'host port 56789, device port {MOCK_DEVICE_PORT}')):
      self.client.restore_server_connection()

    self.assertListEqual(self.mock_socket_file.write.call_args_list,
                         socket_write_expected)

  @mock.patch.object(snippet_client_v2.SnippetClientV2, '_make_connection')
  @mock.patch.object(snippet_client_v2.SnippetClientV2,
                     'send_handshake_request')
  @mock.patch.object(snippet_client_v2.SnippetClientV2,
                     'create_socket_connection')
  def test_restore_server_connection_with_event_client(
      self, mock_create_socket_conn_func, mock_send_handshake_func,
      mock_make_connection):
    """Tests restoring server connection when the event client is not None."""
    self._make_client()
    event_client = snippet_client_v2.SnippetClientV2('mock-package',
                                                     mock.Mock())
    self.client._event_client = event_client
    self.client.device_port = 54321
    self.client.uid = 5

    self.client.restore_server_connection(port=12345)

    mock_make_connection.assert_called_once_with()
    self.assertEqual(event_client.host_port, 12345)
    self.assertEqual(event_client.device_port, 54321)
    self.assertEqual(next(event_client._counter), 0)
    mock_create_socket_conn_func.assert_called_once_with()
    mock_send_handshake_func.assert_called_once_with(
        -1, snippet_client_v2.ConnectionHandshakeCommand.INIT)

  @mock.patch('builtins.print')
  def test_help_rpc_when_printing_by_default(self, mock_print):
    """Tests the `help` method when it prints the output by default."""
    self._make_client()
    mock_rpc = mock.MagicMock()
    self.client._rpc = mock_rpc

    result = self.client.help()
    mock_rpc.assert_called_once_with('help')
    self.assertIsNone(result)
    mock_print.assert_called_once_with(mock_rpc.return_value)

  @mock.patch('builtins.print')
  def test_help_rpc_when_not_printing(self, mock_print):
    """Tests the `help` method when it was set not to print the output."""
    self._make_client()
    mock_rpc = mock.MagicMock()
    self.client._rpc = mock_rpc

    result = self.client.help(print_output=False)
    mock_rpc.assert_called_once_with('help')
    self.assertEqual(mock_rpc.return_value, result)
    mock_print.assert_not_called()

  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port',
              return_value=12345)
  def test_make_connection_normally(self, mock_get_port, mock_start_subprocess,
                                    mock_socket_create_conn):
    """Tests that making a connection works normally."""
    del mock_get_port
    socket_resp = [b'{"status": true, "uid": 1}']
    self._make_client_and_mock_socket_conn(mock_socket_create_conn, socket_resp)
    self._mock_server_process_starting_response(mock_start_subprocess)

    self.client.make_connection()
    self.assertEqual(self.client.uid, 1)
    self.assertEqual(self.client.device_port, MOCK_DEVICE_PORT)
    self.adb.mock_forward_func.assert_called_once_with(
        ['tcp:12345', f'tcp:{MOCK_DEVICE_PORT}'])
    mock_socket_create_conn.assert_called_once_with(
        ('localhost', 12345), snippet_client_v2._SOCKET_CONNECTION_TIMEOUT)
    self.socket_conn.settimeout.assert_called_once_with(
        snippet_client_v2._SOCKET_READ_TIMEOUT)

  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port',
              return_value=12345)
  def test_make_connection_with_preset_host_port(self, mock_get_port,
                                                 mock_start_subprocess,
                                                 mock_socket_create_conn):
    """Tests that make a connection with the preset host port."""
    del mock_get_port
    socket_resp = [b'{"status": true, "uid": 1}']
    self._make_client_and_mock_socket_conn(mock_socket_create_conn, socket_resp)
    self._mock_server_process_starting_response(mock_start_subprocess)

    self.client.host_port = 23456
    self.client.make_connection()
    self.assertEqual(self.client.uid, 1)
    self.assertEqual(self.client.device_port, MOCK_DEVICE_PORT)
    # Test that the host port for forwarding is 23456 instead of 12345
    self.adb.mock_forward_func.assert_called_once_with(
        ['tcp:23456', f'tcp:{MOCK_DEVICE_PORT}'])
    mock_socket_create_conn.assert_called_once_with(
        ('localhost', 23456), snippet_client_v2._SOCKET_CONNECTION_TIMEOUT)
    self.socket_conn.settimeout.assert_called_once_with(
        snippet_client_v2._SOCKET_READ_TIMEOUT)

  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port',
              return_value=12345)
  def test_make_connection_with_ip(self, mock_get_port, mock_start_subprocess,
                                   mock_socket_create_conn):
    """Tests that make a connection with 127.0.0.1 instead of localhost."""
    del mock_get_port
    socket_resp = [b'{"status": true, "uid": 1}']
    self._make_client_and_mock_socket_conn(mock_socket_create_conn, socket_resp)
    self._mock_server_process_starting_response(mock_start_subprocess)

    mock_conn = mock_socket_create_conn.return_value

    # Refuse creating socket connection with 'localhost', only accept
    # '127.0.0.1' as address
    def _mock_create_conn_side_effect(address, *args, **kwargs):
      del args, kwargs
      if address[0] == '127.0.0.1':
        return mock_conn
      raise ConnectionRefusedError(f'Refusing connection to {address[0]}.')

    mock_socket_create_conn.side_effect = _mock_create_conn_side_effect

    self.client.make_connection()
    self.assertEqual(self.client.uid, 1)
    self.assertEqual(self.client.device_port, MOCK_DEVICE_PORT)
    self.adb.mock_forward_func.assert_called_once_with(
        ['tcp:12345', f'tcp:{MOCK_DEVICE_PORT}'])
    mock_socket_create_conn.assert_any_call(
        ('127.0.0.1', 12345), snippet_client_v2._SOCKET_CONNECTION_TIMEOUT)
    self.socket_conn.settimeout.assert_called_once_with(
        snippet_client_v2._SOCKET_READ_TIMEOUT)

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port',
              return_value=12345)
  @mock.patch('socket.create_connection')
  def test_make_connection_io_error(self, mock_socket_create_conn,
                                    mock_get_port):
    """Tests IOError occurred trying to create a socket connection."""
    del mock_get_port
    mock_socket_create_conn.side_effect = IOError()
    with self.assertRaises(IOError):
      self._make_client()
      self.client.device_port = 123
      self.client.make_connection()

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port',
              return_value=12345)
  @mock.patch('socket.create_connection')
  def test_make_connection_timeout(self, mock_socket_create_conn,
                                   mock_get_port):
    """Tests timeout occurred trying to create a socket connection."""
    del mock_get_port
    mock_socket_create_conn.side_effect = socket.timeout
    with self.assertRaises(socket.timeout):
      self._make_client()
      self.client.device_port = 123
      self.client.make_connection()

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port',
              return_value=12345)
  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_make_connection_receives_none_handshake_response(
      self, mock_start_subprocess, mock_socket_create_conn, mock_get_port):
    """Tests make_connection receives None as the handshake response."""
    del mock_get_port
    socket_resp = [None]
    self._make_client_and_mock_socket_conn(mock_socket_create_conn, socket_resp)
    self._mock_server_process_starting_response(mock_start_subprocess)

    with self.assertRaisesRegex(
        errors.ProtocolError, errors.ProtocolError.NO_RESPONSE_FROM_HANDSHAKE):
      self.client.make_connection()

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port',
              return_value=12345)
  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_make_connection_receives_empty_handshake_response(
      self, mock_start_subprocess, mock_socket_create_conn, mock_get_port):
    """Tests make_connection receives an empty handshake response."""
    del mock_get_port
    socket_resp = [b'']
    self._make_client_and_mock_socket_conn(mock_socket_create_conn, socket_resp)
    self._mock_server_process_starting_response(mock_start_subprocess)

    with self.assertRaisesRegex(
        errors.ProtocolError, errors.ProtocolError.NO_RESPONSE_FROM_HANDSHAKE):
      self.client.make_connection()

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port',
              return_value=12345)
  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_make_connection_receives_invalid_handshake_response(
      self, mock_start_subprocess, mock_socket_create_conn, mock_get_port):
    """Tests make_connection receives an invalid handshake response."""
    del mock_get_port
    socket_resp = [b'{"status": false, "uid": 1}']
    self._make_client_and_mock_socket_conn(mock_socket_create_conn, socket_resp)
    self._mock_server_process_starting_response(mock_start_subprocess)

    self.client.make_connection()
    self.assertEqual(self.client.uid, -1)

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port',
              return_value=12345)
  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_make_connection_send_handshake_request_error(self,
                                                        mock_start_subprocess,
                                                        mock_socket_create_conn,
                                                        mock_get_port):
    """Tests that an error occurred trying to send a handshake request."""
    del mock_get_port
    self._make_client_and_mock_socket_conn(mock_socket_create_conn)
    self._mock_server_process_starting_response(mock_start_subprocess)
    self.mock_socket_file.write.side_effect = socket.error('Socket write error')

    with self.assertRaisesRegex(errors.Error, 'Socket write error'):
      self.client.make_connection()

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port',
              return_value=12345)
  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_make_connection_receive_handshake_response_error(
      self, mock_start_subprocess, mock_socket_create_conn, mock_get_port):
    """Tests that an error occurred trying to receive a handshake response."""
    del mock_get_port
    self._make_client_and_mock_socket_conn(mock_socket_create_conn)
    self._mock_server_process_starting_response(mock_start_subprocess)
    self.mock_socket_file.readline.side_effect = socket.error(
        'Socket read error')

    with self.assertRaisesRegex(errors.Error, 'Socket read error'):
      self.client.make_connection()

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port',
              return_value=12345)
  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_make_connection_decode_handshake_response_bytes_error(
      self, mock_start_subprocess, mock_socket_create_conn, mock_get_port):
    """Tests that an error occurred trying to decode a handshake response."""
    del mock_get_port
    self._make_client_and_mock_socket_conn(mock_socket_create_conn)
    self._mock_server_process_starting_response(mock_start_subprocess)
    self.client.log = mock.Mock()
    socket_response = bytes('{"status": false, "uid": 1}', encoding='cp037')
    self.mock_socket_file.readline.side_effect = [socket_response]

    with self.assertRaises(UnicodeError):
      self.client.make_connection()

    self.client.log.error.assert_has_calls([
        mock.call(
            'Failed to decode socket response bytes using encoding utf8: %s',
            socket_response)
    ])

  def test_rpc_sending_and_receiving(self):
    """Test RPC sending and receiving.

    Tests that when sending and receiving an RPC the correct data is used.
    """
    self._make_client()
    rpc_request = '{"id": 0, "method": "some_rpc", "params": []}'
    rpc_response_expected = ('{"id": 0, "result": 123, "error": null, '
                             '"callback": null}')

    socket_write_expected = [
        mock.call(b'{"id": 0, "method": "some_rpc", "params": []}\n')
    ]
    socket_response = (b'{"id": 0, "result": 123, "error": null, '
                       b'"callback": null}')

    mock_socket_file = mock.Mock()
    mock_socket_file.readline.return_value = socket_response
    self.client._client = mock_socket_file

    rpc_response = self.client.send_rpc_request(rpc_request)

    self.assertEqual(rpc_response, rpc_response_expected)
    self.assertEqual(mock_socket_file.write.call_args_list,
                     socket_write_expected)

  def test_rpc_send_socket_write_error(self):
    """Tests that an error occurred trying to write the socket file."""
    self._make_client()
    self.client._client = mock.Mock()
    self.client._client.write.side_effect = socket.error('Socket write error')

    rpc_request = '{"id": 0, "method": "some_rpc", "params": []}'
    with self.assertRaisesRegex(errors.Error, 'Socket write error'):
      self.client.send_rpc_request(rpc_request)

  def test_rpc_send_socket_read_error(self):
    """Tests that an error occurred trying to read the socket file."""
    self._make_client()
    self.client._client = mock.Mock()
    self.client._client.readline.side_effect = socket.error('Socket read error')

    rpc_request = '{"id": 0, "method": "some_rpc", "params": []}'
    with self.assertRaisesRegex(errors.Error, 'Socket read error'):
      self.client.send_rpc_request(rpc_request)

  def test_rpc_send_decode_socket_response_bytes_error(self):
    """Tests that an error occurred trying to decode the socket response."""
    self._make_client()
    self.client.log = mock.Mock()
    self.client._client = mock.Mock()
    socket_response = bytes(
        '{"id": 0, "result": 123, "error": null, "callback": null}',
        encoding='cp037')
    self.client._client.readline.return_value = socket_response

    rpc_request = '{"id": 0, "method": "some_rpc", "params": []}'
    with self.assertRaises(UnicodeError):
      self.client.send_rpc_request(rpc_request)

    self.client.log.error.assert_has_calls([
        mock.call(
            'Failed to decode socket response bytes using encoding utf8: %s',
            socket_response)
    ])

  @mock.patch.object(snippet_client_v2.SnippetClientV2,
                     'send_handshake_request')
  @mock.patch.object(snippet_client_v2.SnippetClientV2,
                     'create_socket_connection')
  def test_make_conn_with_forwarded_port_init(self,
                                              mock_create_socket_conn_func,
                                              mock_send_handshake_func):
    """Tests make_connection_with_forwarded_port initiates a new session."""
    self._make_client()
    self.client._counter = None
    self.client.make_connection_with_forwarded_port(12345, 54321)

    self.assertEqual(self.client.host_port, 12345)
    self.assertEqual(self.client.device_port, 54321)
    self.assertEqual(next(self.client._counter), 0)
    mock_create_socket_conn_func.assert_called_once_with()
    mock_send_handshake_func.assert_called_once_with(
        -1, snippet_client_v2.ConnectionHandshakeCommand.INIT)

  @mock.patch.object(snippet_client_v2.SnippetClientV2,
                     'send_handshake_request')
  @mock.patch.object(snippet_client_v2.SnippetClientV2,
                     'create_socket_connection')
  def test_make_conn_with_forwarded_port_continue(self,
                                                  mock_create_socket_conn_func,
                                                  mock_send_handshake_func):
    """Tests make_connection_with_forwarded_port continues current session."""
    self._make_client()
    self.client._counter = None
    self.client.make_connection_with_forwarded_port(
        12345, 54321, 3, snippet_client_v2.ConnectionHandshakeCommand.CONTINUE)

    self.assertEqual(self.client.host_port, 12345)
    self.assertEqual(self.client.device_port, 54321)
    self.assertEqual(next(self.client._counter), 0)
    mock_create_socket_conn_func.assert_called_once_with()
    mock_send_handshake_func.assert_called_once_with(
        3, snippet_client_v2.ConnectionHandshakeCommand.CONTINUE)


if __name__ == '__main__':
  unittest.main()
