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

import unittest
from unittest import mock
import socket
import contextlib
import json

from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import snippet_client_v2
from mobly.snippet import client_base
from mobly.tests.lib.snippet import utils as snippet_test_utils
from mobly.tests.lib.snippet import constants
from mobly.tests.lib.snippet import mock_socket_file
from mobly.tests.lib import mock_android_device

MOCK_PACKAGE_NAME = 'some.package.name'
MOCK_MISSING_PACKAGE_NAME = 'not.installed'
MOCK_USER_ID = 0
DISABLE_HIDDEN_API_SHELL_CMD = 'settings put global hidden_api_blacklist_exemptions "*"'
MOCK_DEVICE_PORT = 123
MOCK_HOST_PORT = 456


class SnippetClientV2Test(unittest.TestCase):
  """Unit tests for mobly.controllers.android_device_lib.snippet_client_v2.
  """

  def test_check_app_installed_normal(self):
    sc = self._make_client()
    sc._check_app_installed()

  def test_check_app_installed_fail_app_not_installed(self):
    sc = self._make_client(mock_android_device.MockAdbProxy())
    expected_msg = '.* %s is not installed.' % MOCK_PACKAGE_NAME
    with self.assertRaisesRegex(snippet_client_v2.AppStartPreCheckError,
                                expected_msg):
      sc._check_app_installed()

  def test_check_app_installed_fail_not_instrumented(self):
    sc = self._make_client(
        mock_android_device.MockAdbProxy(
            installed_packages=[MOCK_PACKAGE_NAME]))
    expected_msg = ('.* %s is installed, but it is not instrumented.' %
                    MOCK_PACKAGE_NAME)
    with self.assertRaisesRegex(snippet_client_v2.AppStartPreCheckError,
                                expected_msg):
      sc._check_app_installed()

  def test_check_app_installed_fail_target_not_installed(self):
    sc = self._make_client(
        mock_android_device.MockAdbProxy(instrumented_packages=[(
            MOCK_PACKAGE_NAME, snippet_client_v2._INSTRUMENTATION_RUNNER_PACKAGE,
            MOCK_MISSING_PACKAGE_NAME)]))
    expected_msg = ('.* Instrumentation target %s is not installed.' %
                    MOCK_MISSING_PACKAGE_NAME)
    with self.assertRaisesRegex(snippet_client_v2.AppStartPreCheckError,
                                expected_msg):
      sc._check_app_installed()

  @mock.patch.object(mock_android_device.MockAdbProxy, 'shell')
  def test_disable_hidden_api_normal(self, mock_shell_func):
    mock_properties = mock_android_device.DEFAULT_MOCK_PROPERTIES
    mock_properties.update({
        'ro.build.version.codename': 'S',
        'ro.build.version.sdk': '31',
    })
    sc = self._make_client(
        mock_android_device.MockAdbProxy(
            mock_properties=mock_properties))
    sc._device.is_rootable = True
    sc._disable_hidden_api_blacklist()
    mock_shell_func.assert_called_with(DISABLE_HIDDEN_API_SHELL_CMD)

  @mock.patch.object(mock_android_device.MockAdbProxy, 'shell')
  def test_disable_hidden_api_low_sdk(self, mock_shell_func):
    mock_properties = mock_android_device.DEFAULT_MOCK_PROPERTIES
    mock_properties.update({
        'ro.build.version.codename': 'O',
        'ro.build.version.sdk': '26',
    })
    sc = self._make_client(
        mock_android_device.MockAdbProxy(
            mock_properties=mock_properties))
    sc._device.is_rootable = True
    sc._disable_hidden_api_blacklist()
    mock_shell_func.assert_not_called()

  @mock.patch.object(mock_android_device.MockAdbProxy, 'shell')
  def test_disable_hidden_api_low_sdk_with_android_P(self, mock_shell_func):
    mock_properties = mock_android_device.DEFAULT_MOCK_PROPERTIES
    mock_properties.update({
        'ro.build.version.codename': 'P',
        'ro.build.version.sdk': '27',
    })
    sc = self._make_client(
        mock_android_device.MockAdbProxy(
            mock_properties=mock_properties))
    sc._device.is_rootable = True
    sc._disable_hidden_api_blacklist()
    mock_shell_func.assert_called_with(DISABLE_HIDDEN_API_SHELL_CMD)

  @mock.patch.object(mock_android_device.MockAdbProxy, 'shell')
  def test_disable_hidden_api_non_rootable(self, mock_shell_func):
    mock_properties = mock_android_device.DEFAULT_MOCK_PROPERTIES
    mock_properties.update({
        'ro.build.version.codename': 'S',
        'ro.build.version.sdk': '31',
    })
    sc = self._make_client(
        mock_android_device.MockAdbProxy(
            mock_properties=mock_properties))
    sc._device.is_rootable = False
    sc._disable_hidden_api_blacklist()
    mock_shell_func.assert_not_called()

  def test_rpc_normal(self):
    """Test sending rpc.

    Test that after mocking the process of building connection, the client can send rpc normally.
    """
    with self._make_client_and_connect() as cxt:
      client, _, _ = cxt
      result = client.testSnippetCall()
      self.assertEqual(123, result)

  # @mock.patch('socket.create_connection')
  def test_snippet_start_event_client(self):
    """Test starting event client to handle async rpc

    Test that after mocking the process of building connection, the client can start event client
    to handle async rpc.
    """
    # fake_file = mock_socket_file.setup_mock_socket_file(mock_create_connection)
    with self._make_client_and_connect() as cxt:
      client, fake_file, _ = cxt
      client.host_port = MOCK_HOST_PORT

      fake_file.resp = constants.MOCK_RESP_WITH_CALLBACK
      callback = client.testSnippetCall()
      self.assertEqual(123, callback.ret_value)
      self.assertEqual('1-0', callback._id)

      # Ensure the event clietn share the same port with main client
      self.assertEqual(MOCK_HOST_PORT, callback._event_client.host_port)
      self.assertEqual(MOCK_DEVICE_PORT, callback._event_client.device_port)

      # Ensure that the event_client can get rpc response normally.
      # We just make the response indicate error and omit
      # mocking eventGetAll rpc function here.
      fake_file.resp = constants.MOCK_RESP_WITH_ERROR
      with self.assertRaisesRegex(client_base.ApiError, '1'):
        callback.getAll('eventName')

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port')
  def test_snippet_restore_event_client(self, mock_get_port):
    mock_get_port.return_value = 123
    with self._make_client_and_connect(device_port=456) as cxt:
      client, fake_file, mock_create_connection = cxt
      fake_file.resp = constants.MOCK_RESP_WITH_CALLBACK
      callback = client.testSnippetCall()

      # before reconnect, clients use previously selected ports
      self.assertEqual(123, client.host_port)
      self.assertEqual(456, client.device_port)
      self.assertEqual(123, callback._event_client.host_port)
      self.assertEqual(456, callback._event_client.device_port)

      # after reconnect, if host port specified, clients use specified port
      client.restore_server_connection(port=321)
      self.assertEqual(321, client.host_port)
      self.assertEqual(456, client.device_port)
      self.assertEqual(321, callback._event_client.host_port)
      self.assertEqual(456, callback._event_client.device_port)

      # after reconnect, if host port not specified, clients use selected
      # available port
      mock_get_port.return_value = 789
      client.restore_server_connection()
      self.assertEqual(789, client.host_port)
      self.assertEqual(456, client.device_port)
      self.assertEqual(789, callback._event_client.host_port)
      self.assertEqual(456, callback._event_client.device_port)

      # if unable to reconnect for any reason, a
      # client_base.AppRestoreConnectionError is raised.
      mock_create_connection.side_effect = IOError('socket timed out')
      with self.assertRaisesRegex(
          client_base.AppRestoreConnectionError,
          ('Failed to restore app connection for %s at host port %s, '
           'device port %s') % (MOCK_PACKAGE_NAME, 789, 456)):
        client.restore_server_connection()

  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port')
  def test_snippet_start_app_and_connect(self, mock_get_port,
                                         mock_start_standing_subprocess,
                                         mock_create_connection):
    mock_socket_file.setup_mock_socket_file(mock_create_connection)
    self._setup_mock_instrumentation_cmd(mock_start_standing_subprocess,
                                         resp_lines=[
                                             b'SNIPPET START, PROTOCOL 1 0\n',
                                             b'SNIPPET SERVING, PORT 123\n',
                                         ])
    client = self._make_client()
    client.start_server()
    self.assertEqual(123, client.device_port)
    self.assertTrue(client.is_alive)

  @mock.patch('socket.create_connection')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  def test_snippet_stop_app(self, mock_stop_standing_subprocess,
                            mock_create_connection):
    adb_proxy = mock.MagicMock()
    adb_proxy.shell.return_value = b'OK (0 tests)'
    client = self._make_client(adb_proxy)
    client.stop_server()
    self.assertFalse(client.is_alive)

  def test_snippet_stop_app_raises(self):
    adb_proxy = mock.MagicMock()
    adb_proxy.shell.return_value = b'OK (0 tests)'
    client = self._make_client(adb_proxy)
    client.host_port = 1
    client._conn = mock.MagicMock()
    # Explicitly making the second side_effect noop to avoid uncaught exception
    # when `__del__` is called after the test is done, which triggers
    # `disconnect`.
    client._conn.close.side_effect = [Exception('ha'), None]
    with self.assertRaisesRegex(Exception, 'ha'):
      client.stop_server()
    adb_proxy.forward.assert_called_once_with(['--remove', 'tcp:1'])

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'SnippetClientV2._run_abd_cmd')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'SnippetClientV2._check_app_installed')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'SnippetClientV2._read_protocol_line')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'SnippetClientV2.build_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port')
  def test_snippet_start_on_sdk_21(self, mock_get_port, mock_build_conn,
                                   mock_read_protocol_line,
                                   mock_check_app_installed, mock_run_adb_cmd):
    """Check that `--user` is not added to start command on SDK < 24."""

    def _mocked_shell(arg):
      if 'setsid' in arg:
        raise adb.AdbError('cmd', 'stdout', 'stderr', 'ret_code')
      else:
        return b'nohup'

    mock_get_port.return_value = 123
    mock_read_protocol_line.side_effect = [
        'SNIPPET START, PROTOCOL 1 234',
        'SNIPPET SERVING, PORT 1234',
        'SNIPPET START, PROTOCOL 1 234',
        'SNIPPET SERVING, PORT 1234',
        'SNIPPET START, PROTOCOL 1 234',
        'SNIPPET SERVING, PORT 1234',
    ]

    # Test 'setsid' exists
    client = self._make_client()
    client._device.build_info['build_version_sdk'] = 21
    client._adb.shell = mock.Mock(return_value=b'setsid')
    client.start_server()
    cmd_setsid = '%s am instrument  -w -e action start %s/%s' % (
        snippet_client_v2._SETSID_COMMAND, MOCK_PACKAGE_NAME,
        snippet_client_v2._INSTRUMENTATION_RUNNER_PACKAGE)
    mock_run_adb_cmd.assert_has_calls([mock.call(cmd_setsid)])

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'SnippetClientV2._run_abd_cmd')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'SnippetClientV2._check_app_installed')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'SnippetClientV2._read_protocol_line')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'SnippetClientV2.build_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port')
  def test_snippet_start_server_persistent_session(
      self, mock_get_port, mock_build_conn, mock_read_protocol_line,
      mock_check_app_installed, mock_run_adb_cmd):

    def _mocked_shell(arg):
      if 'setsid' in arg:
        raise adb.AdbError('cmd', 'stdout', 'stderr', 'ret_code')
      else:
        return b'nohup'

    mock_get_port.return_value = 123
    mock_read_protocol_line.side_effect = [
        'SNIPPET START, PROTOCOL 1 234',
        'SNIPPET SERVING, PORT 1234',
        'SNIPPET START, PROTOCOL 1 234',
        'SNIPPET SERVING, PORT 1234',
        'SNIPPET START, PROTOCOL 1 234',
        'SNIPPET SERVING, PORT 1234',
    ]

    # Test 'setsid' exists
    client = self._make_client()
    client._adb = mock.MagicMock()
    client._adb.shell.return_value = b'setsid'
    client._adb.current_user_id = MOCK_USER_ID
    client.start_server()
    cmd_setsid = '%s am instrument --user %s -w -e action start %s/%s' % (
        snippet_client_v2._SETSID_COMMAND, MOCK_USER_ID, MOCK_PACKAGE_NAME,
        snippet_client_v2._INSTRUMENTATION_RUNNER_PACKAGE)
    mock_run_adb_cmd.assert_has_calls([mock.call(cmd_setsid)])

    # Test 'setsid' does not exist, but 'nohup' exsits
    client = self._make_client()
    client._adb.shell = _mocked_shell
    client.start_server()
    cmd_nohup = '%s am instrument --user %s -w -e action start %s/%s' % (
        snippet_client_v2._NOHUP_COMMAND, MOCK_USER_ID, MOCK_PACKAGE_NAME,
        snippet_client_v2._INSTRUMENTATION_RUNNER_PACKAGE)
    mock_run_adb_cmd.assert_has_calls(
        [mock.call(cmd_setsid), mock.call(cmd_nohup)])

    # Test both 'setsid' and 'nohup' do not exist
    client._adb.shell = mock.Mock(
        side_effect=adb.AdbError('cmd', 'stdout', 'stderr', 'ret_code'))
    client = self._make_client()
    client.start_server()
    cmd_not_persist = ' am instrument --user %s -w -e action start %s/%s' % (
        MOCK_USER_ID, MOCK_PACKAGE_NAME,
        snippet_client_v2._INSTRUMENTATION_RUNNER_PACKAGE)
    mock_run_adb_cmd.assert_has_calls([
        mock.call(cmd_setsid),
        mock.call(cmd_nohup),
        mock.call(cmd_not_persist)
    ])

  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port')
  def test_snippet_start_server_crash(self, mock_get_port,
                                   mock_start_standing_subprocess,
                                   mock_create_connection):
    mock_get_port.return_value = 456
    mock_socket_file.setup_mock_socket_file(mock_create_connection)
    self._setup_mock_instrumentation_cmd(
        mock_start_standing_subprocess,
        resp_lines=[b'INSTRUMENTATION_RESULT: shortMsg=Process crashed.\n'])
    client = self._make_client()
    with self.assertRaisesRegex(
        snippet_client_v2.ProtocolVersionError,
        'INSTRUMENTATION_RESULT: shortMsg=Process crashed.'):
      client.start_server()

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port')
  def test_snippet_start_server_unknown_protocol(
      self, mock_get_port, mock_start_standing_subprocess):
    mock_get_port.return_value = 789
    self._setup_mock_instrumentation_cmd(
        mock_start_standing_subprocess,
        resp_lines=[b'SNIPPET START, PROTOCOL 99 0\n'])
    client = self._make_client()
    with self.assertRaisesRegex(snippet_client_v2.ProtocolVersionError,
                                'SNIPPET START, PROTOCOL 99 0'):
      client.start_server()

  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port')
  def test_snippet_start_server_header_junk(
      self, mock_get_port, mock_start_standing_subprocess,
      mock_create_connection):
    mock_socket_file.setup_mock_socket_file(mock_create_connection)
    self._setup_mock_instrumentation_cmd(
        mock_start_standing_subprocess,
        resp_lines=[
            b'This is some header junk\n',
            b'Some phones print arbitrary output\n',
            b'SNIPPET START, PROTOCOL 1 0\n',
            b'Maybe in the middle too\n',
            b'SNIPPET SERVING, PORT 123\n',
        ])
    client = self._make_client()
    client.start_server()
    self.assertEqual(123, client.device_port)

  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.get_available_host_port')
  def test_snippet_start_app_and_connect_no_valid_line(
      self, mock_get_port, mock_start_standing_subprocess,
      mock_create_connection):
    mock_get_port.return_value = 456
    mock_socket_file.setup_mock_socket_file(mock_create_connection)
    self._setup_mock_instrumentation_cmd(
        mock_start_standing_subprocess,
        resp_lines=[
            b'This is some header junk\n',
            b'Some phones print arbitrary output\n',
            b'',  # readline uses '' to mark EOF
        ])
    client = self._make_client()
    with self.assertRaisesRegex(client_base.AppStartError,
                                'Unexpected EOF waiting for app to start'):
      client.start_server()

  @mock.patch('builtins.print')
  def test_help_rpc_when_printing_by_default(self, mock_print):
    client = self._make_client()
    mock_rpc = mock.MagicMock()
    client._rpc = mock_rpc

    result = client.help()
    mock_rpc.assert_called_once_with('help')
    self.assertEqual(None, result)
    mock_print.assert_called_once_with(mock_rpc.return_value)

  @mock.patch('builtins.print')
  def test_help_rpc_when_not_printing(self, mock_print):
    client = self._make_client()
    mock_rpc = mock.MagicMock()
    client._rpc = mock_rpc

    result = client.help(print_output=False)
    mock_rpc.assert_called_once_with('help')
    self.assertEqual(mock_rpc.return_value, result)
    mock_print.assert_not_called()

  @mock.patch('socket.create_connection')
  def test_open_timeout_io_error(self, mock_create_connection):
    mock_create_connection.side_effect = IOError()
    with self.assertRaises(IOError):
      client = self._make_client()
      client.device_port = 123
      client.build_connection()

  @mock.patch('socket.create_connection')
  def test_connect_timeout(self, mock_create_connection):
    """Test socket timeout

    Test that a timeout exception will be raised if the socket gives a
    timeout.
    """
    mock_create_connection.side_effect = socket.timeout
    with self.assertRaises(socket.timeout):
      client = self._make_client()
      client.device_port = 456
      client.build_connection()

  @mock.patch('socket.create_connection')
  def test_handshake_error(self, mock_create_connection):
    """Test error in jsonrpc handshake

    Test that if there is an error in the jsonrpc handshake then a protocol
    error will be raised.
    """
    mock_socket_file.setup_mock_socket_file(mock_create_connection, resp=None)
    client = self._make_client()
    client.device_port = 456
    with self.assertRaisesRegex(
        client_base.ProtocolError,
        client_base.ProtocolError.NO_RESPONSE_FROM_HANDSHAKE):
      client.build_connection()

  def test_disconnect(self):
    client = self._make_client()
    client.device_port = 456
    mock_conn = mock.MagicMock()
    client._stop_port_forwarding = mock.MagicMock()
    client._conn = mock_conn
    client.disconnect()
    self.assertIsNone(client._conn)
    mock_conn.close.assert_called_once_with()
    client._stop_port_forwarding.assert_called_once_with()

  def test_disconnect_raises(self):
    client = self._make_client()
    client.device_port = 456
    mock_conn = mock.MagicMock()
    client._stop_port_forwarding = mock.MagicMock()
    client._conn = mock_conn
    # Explicitly making the second side_effect noop to avoid uncaught exception
    # when `__del__` is called after the test is done, which triggers
    # `disconnect`.
    mock_conn.close.side_effect = [Exception('ha'), None]
    with self.assertRaisesRegex(Exception, 'ha'):
      client.disconnect()
    client._stop_port_forwarding.assert_called_once_with()

  def test_clear_host_port_positive(self):
    client = self._make_client(adb_proxy=mock.Mock())
    client.device_port = 456
    client.host_port = 1
    client._stop_port_forwarding()
    client._device.adb.forward.assert_called_once_with(['--remove', 'tcp:1'])
    self.assertIsNone(client.host_port)

  def test_clear_host_port_negative(self):
    client = self._make_client(adb_proxy=mock.Mock())
    client.device_port = 456
    client.host_port = None
    client._stop_port_forwarding()
    client._device.adb.forward.assert_not_called()

  @mock.patch('socket.create_connection')
  def test_connect_handshake(self, mock_create_connection):
    """Test client handshake

    Test that at the end of a handshake with no errors the client object
    has the correct parameters.
    """
    mock_socket_file.setup_mock_socket_file(mock_create_connection)
    client = self._make_client()
    client.device_port = 456
    client.build_connection()
    self.assertEqual(client.uid, 1)

  @mock.patch('socket.create_connection')
  def test_connect_handshake_unknown_status(self, mock_create_connection):
    """Test handshake with unknown status response

    Test that when the handshake is given an unknown status then the client
    will not be given a uid.
    """
    mock_socket_file.setup_mock_socket_file(mock_create_connection,
                                resp=constants.MOCK_CMD_RESP_UNKNOWN_STATUS)
    client = self._make_client()
    client.device_port = 456
    client.build_connection()
    self.assertEqual(client.uid, snippet_client_v2.UNKNOWN_UID)

  @mock.patch('socket.create_connection')
  def test_rpc_error_response(self, mock_create_connection):
    """Test rpc that is given an error response

    Test that when an rpc receives a response with an error will raised
    an api error.
    """
    fake_file = mock_socket_file.setup_mock_socket_file(mock_create_connection)

    client = self._make_client()
    client.device_port = 456
    client.build_connection()

    fake_file.resp = constants.MOCK_RESP_WITH_ERROR

    with self.assertRaisesRegex(client_base.ApiError, '1'):
      client.some_rpc(1, 2, 3)

  @mock.patch('socket.create_connection')
  def test_rpc_callback_response(self, mock_create_connection):
    """Test rpc that is given a callback response.

    Test that when an rpc receives a callback response, a callback object is
    created correctly.
    """
    fake_file = mock_socket_file.setup_mock_socket_file(mock_create_connection)

    client = self._make_client()
    client.device_port = 456
    client.build_connection()

    fake_file.resp = constants.MOCK_RESP_WITH_CALLBACK
    client._event_client = mock.Mock()

    callback = client.some_rpc(1, 2, 3)
    self.assertEqual(callback.ret_value, 123)
    self.assertEqual(callback._id, '1-0')

  @mock.patch('socket.create_connection')
  def test_rpc_id_mismatch(self, mock_create_connection):
    """Test rpc that returns a different id than expected

    Test that if an rpc returns with an id that is different than what
    is expected will give a protocl error.
    """
    fake_file = mock_socket_file.setup_mock_socket_file(mock_create_connection)

    client = self._make_client()
    client.device_port = 456
    client.build_connection()

    fake_file.resp = (constants.MOCK_RESP_TEMPLATE % 52).encode('utf8')

    with self.assertRaisesRegex(
        client_base.ProtocolError,
        client_base.ProtocolError.MISMATCHED_API_ID):
      client.some_rpc(1, 2, 3)

  @mock.patch('socket.create_connection')
  def test_rpc_no_response(self, mock_create_connection):
    """Test rpc that does not get a response

    Test that when an rpc does not get a response it throws a protocol
    error.
    """
    fake_file = mock_socket_file.setup_mock_socket_file(mock_create_connection)

    client = self._make_client()
    client.device_port = 456
    client.build_connection()

    fake_file.resp = None

    with self.assertRaisesRegex(
        client_base.ProtocolError,
        client_base.ProtocolError.NO_RESPONSE_FROM_SERVER):
      client.some_rpc(1, 2, 3)

  @mock.patch('socket.create_connection')
  def test_rpc_send_to_socket_no_args(self, mock_create_connection):
    """Test rpc sending and recieving

    Tests that when an rpc is sent and received the corrent data
    is used. The rpc doesn't have any arguments.
    """
    fake_file = mock_socket_file.setup_mock_socket_file(mock_create_connection)

    client = self._make_client()
    client.device_port = 456
    client.build_connection()

    result = client.some_rpc()
    self.assertEqual(result, 123)

    expected = {'id': 0, 'method': 'some_rpc', 'params': []}
    actual = json.loads(fake_file.last_write.decode('utf-8'))

    self.assertEqual(expected, actual)

  @mock.patch('socket.create_connection')
  def test_rpc_send_to_socket_no_kwargs(self, mock_create_connection):
    """Test rpc sending and recieving

    Tests that when an rpc is sent and received the corrent data
    is used. The rpc only has positional arguments.
    """
    fake_file = mock_socket_file.setup_mock_socket_file(mock_create_connection)

    client = self._make_client()
    client.device_port = 456
    client.build_connection()

    result = client.some_rpc(1, 2, 3)
    self.assertEqual(result, 123)

    expected = {'id': 0, 'method': 'some_rpc', 'params': [1, 2, 3]}
    actual = json.loads(fake_file.last_write.decode('utf-8'))

    self.assertEqual(expected, actual)

  @mock.patch('socket.create_connection')
  def test_rpc_send_to_socket_with_kwargs(self, mock_create_connection):
    """Test rpc sending and recieving

    Tests that when an rpc is sent and received the corrent data
    is used. The rpc only has positional arguments and keyword
    arguments.
    """
    fake_file = mock_socket_file.setup_mock_socket_file(mock_create_connection)

    client = self._make_client()
    client.device_port = 456
    client.build_connection()

    result = client.some_rpc(1, 2, 3, test_key=5)
    self.assertEqual(result, 123)

    expected = {'id': 0, 'method': 'some_rpc', 'params': [1, 2, 3], 'kwargs': {'test_key': 5}}
    actual = json.loads(fake_file.last_write.decode('utf-8'))

    self.assertEqual(expected, actual)

  @mock.patch('socket.create_connection')
  def test_rpc_send_to_socket_without_callback_field(self, mock_create_connection):
    """Test rpc sending and recieving with Rpc protocol before callback was
    added to the resp message.

    Logic is the same as test_rpc_send_to_socket.
    """
    fake_file = mock_socket_file.setup_mock_socket_file(
        mock_create_connection, resp=constants.MOCK_RESP_WITHOUT_CALLBACK)

    client = self._make_client()
    client.device_port = 456
    client.build_connection()

    with self.assertRaisesRegex(client_base.ProtocolError,
																client_base.ProtocolError.RESPONSE_MISS_FIELD % 'callback'):

    	result = client.some_rpc(1, 2, 3, test_key=5)

  @mock.patch('socket.create_connection')
  def test_rpc_call_increment_counter(self, mock_create_connection):
    """Test rpc counter

    Test that with each rpc call the counter is incremented by 1.
    """
    fake_file = mock_socket_file.setup_mock_socket_file(mock_create_connection)

    client = self._make_client()
    client.device_port = 456
    client.build_connection()

    for i in range(0, 10):
      fake_file.resp = (constants.MOCK_RESP_TEMPLATE % i).encode('utf-8')
      client.some_rpc()

    self.assertEqual(next(client._counter), 10)

  def _make_client(self, adb_proxy=None):
    """Make a snippet client object for testing."""
    device = snippet_test_utils.mock_android_device_for_client_test(MOCK_PACKAGE_NAME, snippet_client_v2._INSTRUMENTATION_RUNNER_PACKAGE, adb_proxy)
    return snippet_client_v2.SnippetClientV2(MOCK_PACKAGE_NAME, device)

  @contextlib.contextmanager
  def _make_client_and_connect(self, adb_proxy=None, device_port=MOCK_DEVICE_PORT):
    client = self._make_client(adb_proxy)
    try:
      with mock.patch('socket.create_connection') as mock_create_connection:
        # Instead of starting server, We mock socket connection
        fake_file = mock_socket_file.setup_mock_socket_file(mock_create_connection)
        # self.device_port is set in the function of starting server,
        # and is used in the building connection function, so we need
        # to mock it here
        client.device_port = device_port
        client.build_connection()
        yield (client, fake_file, mock_create_connection)

    finally:
      pass


  def _setup_mock_instrumentation_cmd(self, mock_start_standing_subprocess,
                                      resp_lines):
    mock_proc = mock_start_standing_subprocess()
    mock_proc.stdout.readline.side_effect = resp_lines


if __name__ == "__main__":
  unittest.main()
