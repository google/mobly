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

from builtins import str
from builtins import bytes

import mock
import unittest

from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import jsonrpc_client_base
from mobly.controllers.android_device_lib import snippet_client
from tests.lib import jsonrpc_client_test_base
from tests.lib import mock_android_device

MOCK_PACKAGE_NAME = 'some.package.name'
MOCK_MISSING_PACKAGE_NAME = 'not.installed'
JSONRPC_BASE_CLASS = 'mobly.controllers.android_device_lib.jsonrpc_client_base.JsonRpcClientBase'
MOCK_USER_ID = 0


class SnippetClientTest(jsonrpc_client_test_base.JsonRpcClientTestBase):
  """Unit tests for mobly.controllers.android_device_lib.snippet_client.
  """

  def test_check_app_installed_normal(self):
    sc = self._make_client()
    sc._check_app_installed()

  def test_check_app_installed_fail_app_not_installed(self):
    sc = self._make_client(mock_android_device.MockAdbProxy())
    expected_msg = '.* %s is not installed.' % MOCK_PACKAGE_NAME
    with self.assertRaisesRegex(snippet_client.AppStartPreCheckError,
                                expected_msg):
      sc._check_app_installed()

  def test_check_app_installed_fail_not_instrumented(self):
    sc = self._make_client(
        mock_android_device.MockAdbProxy(
            installed_packages=[MOCK_PACKAGE_NAME]))
    expected_msg = ('.* %s is installed, but it is not instrumented.' %
                    MOCK_PACKAGE_NAME)
    with self.assertRaisesRegex(snippet_client.AppStartPreCheckError,
                                expected_msg):
      sc._check_app_installed()

  def test_check_app_installed_fail_target_not_installed(self):
    sc = self._make_client(
        mock_android_device.MockAdbProxy(instrumented_packages=[(
            MOCK_PACKAGE_NAME, snippet_client._INSTRUMENTATION_RUNNER_PACKAGE,
            MOCK_MISSING_PACKAGE_NAME)]))
    expected_msg = ('.* Instrumentation target %s is not installed.' %
                    MOCK_MISSING_PACKAGE_NAME)
    with self.assertRaisesRegex(snippet_client.AppStartPreCheckError,
                                expected_msg):
      sc._check_app_installed()

  @mock.patch('socket.create_connection')
  def test_snippet_start(self, mock_create_connection):
    self.setup_mock_socket_file(mock_create_connection)
    client = self._make_client()
    client.connect()
    result = client.testSnippetCall()
    self.assertEqual(123, result)

  @mock.patch('socket.create_connection')
  def test_snippet_start_event_client(self, mock_create_connection):
    fake_file = self.setup_mock_socket_file(mock_create_connection)
    client = self._make_client()
    client.host_port = 123  # normally picked by start_app_and_connect
    client.connect()
    fake_file.resp = self.MOCK_RESP_WITH_CALLBACK
    callback = client.testSnippetCall()
    self.assertEqual(123, callback.ret_value)
    self.assertEqual('1-0', callback._id)

    # Check to make sure the event client is using the same port as the
    # main client.
    self.assertEqual(123, callback._event_client.host_port)

    fake_file.resp = self.MOCK_RESP_WITH_ERROR
    with self.assertRaisesRegex(jsonrpc_client_base.ApiError, '1'):
      callback.getAll('eventName')

  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'utils.get_available_host_port')
  def test_snippet_restore_event_client(self, mock_get_port,
                                        mock_create_connection):
    mock_get_port.return_value = 789
    fake_file = self.setup_mock_socket_file(mock_create_connection)
    client = self._make_client()
    client.host_port = 123  # normally picked by start_app_and_connect
    client.device_port = 456
    client.connect()
    fake_file.resp = self.MOCK_RESP_WITH_CALLBACK
    callback = client.testSnippetCall()

    # before reconnect, clients use previously selected ports
    self.assertEqual(123, client.host_port)
    self.assertEqual(456, client.device_port)
    self.assertEqual(123, callback._event_client.host_port)
    self.assertEqual(456, callback._event_client.device_port)

    # after reconnect, if host port specified, clients use specified port
    client.restore_app_connection(port=321)
    self.assertEqual(321, client.host_port)
    self.assertEqual(456, client.device_port)
    self.assertEqual(321, callback._event_client.host_port)
    self.assertEqual(456, callback._event_client.device_port)

    # after reconnect, if host port not specified, clients use selected
    # available port
    client.restore_app_connection()
    self.assertEqual(789, client.host_port)
    self.assertEqual(456, client.device_port)
    self.assertEqual(789, callback._event_client.host_port)
    self.assertEqual(456, callback._event_client.device_port)

    # if unable to reconnect for any reason, a
    # jsonrpc_client_base.AppRestoreConnectionError is raised.
    mock_create_connection.side_effect = IOError('socket timed out')
    with self.assertRaisesRegex(
        jsonrpc_client_base.AppRestoreConnectionError,
        ('Failed to restore app connection for %s at host port %s, '
         'device port %s') % (MOCK_PACKAGE_NAME, 789, 456)):
      client.restore_app_connection()

  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'utils.start_standing_subprocess')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'utils.get_available_host_port')
  def test_snippet_start_app_and_connect(self, mock_get_port,
                                         mock_start_standing_subprocess,
                                         mock_create_connection):
    self.setup_mock_socket_file(mock_create_connection)
    self._setup_mock_instrumentation_cmd(mock_start_standing_subprocess,
                                         resp_lines=[
                                             b'SNIPPET START, PROTOCOL 1 0\n',
                                             b'SNIPPET SERVING, PORT 123\n',
                                         ])
    client = self._make_client()
    client.start_app_and_connect()
    self.assertEqual(123, client.device_port)
    self.assertTrue(client.is_alive)

  @mock.patch('socket.create_connection')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  def test_snippet_stop_app(self, mock_stop_standing_subprocess,
                            mock_create_connection):
    adb_proxy = mock.MagicMock()
    adb_proxy.shell.return_value = b'OK (0 tests)'
    client = self._make_client(adb_proxy)
    client.stop_app()
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
      client.stop_app()
    adb_proxy.forward.assert_called_once_with(['--remove', 'tcp:1'])

  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'utils.start_standing_subprocess')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'utils.get_available_host_port')
  @mock.patch(
      'mobly.controllers.android_device_lib.snippet_client.SnippetClient.'
      'disable_hidden_api_blacklist')
  @mock.patch(
      'mobly.controllers.android_device_lib.snippet_client.SnippetClient.'
      'stop_app')
  def test_start_app_and_connect_precheck_fail(self, mock_stop, mock_precheck,
                                               mock_get_port,
                                               mock_start_standing_subprocess,
                                               mock_create_connection):
    self.setup_mock_socket_file(mock_create_connection)
    self._setup_mock_instrumentation_cmd(mock_start_standing_subprocess,
                                         resp_lines=[
                                             b'SNIPPET START, PROTOCOL 1 0\n',
                                             b'SNIPPET SERVING, PORT 123\n',
                                         ])
    client = self._make_client()
    mock_precheck.side_effect = snippet_client.AppStartPreCheckError(
        client.ad, 'ha')
    with self.assertRaisesRegex(snippet_client.AppStartPreCheckError, 'ha'):
      client.start_app_and_connect()
    mock_stop.assert_not_called()
    self.assertFalse(client.is_alive)

  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'utils.start_standing_subprocess')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'utils.get_available_host_port')
  @mock.patch(
      'mobly.controllers.android_device_lib.snippet_client.SnippetClient._start_app_and_connect'
  )
  @mock.patch(
      'mobly.controllers.android_device_lib.snippet_client.SnippetClient.stop_app'
  )
  def test_start_app_and_connect_generic_error(self, mock_stop, mock_start,
                                               mock_get_port,
                                               mock_start_standing_subprocess,
                                               mock_create_connection):
    self.setup_mock_socket_file(mock_create_connection)
    self._setup_mock_instrumentation_cmd(mock_start_standing_subprocess,
                                         resp_lines=[
                                             b'SNIPPET START, PROTOCOL 1 0\n',
                                             b'SNIPPET SERVING, PORT 123\n',
                                         ])
    client = self._make_client()
    mock_start.side_effect = Exception('ha')
    with self.assertRaisesRegex(Exception, 'ha'):
      client.start_app_and_connect()
    mock_stop.assert_called_once_with()
    self.assertFalse(client.is_alive)

  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'utils.start_standing_subprocess')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'utils.get_available_host_port')
  @mock.patch(
      'mobly.controllers.android_device_lib.snippet_client.SnippetClient._start_app_and_connect'
  )
  @mock.patch(
      'mobly.controllers.android_device_lib.snippet_client.SnippetClient.stop_app'
  )
  def test_start_app_and_connect_fail_stop_also_fail(
      self, mock_stop, mock_start, mock_get_port,
      mock_start_standing_subprocess, mock_create_connection):
    self.setup_mock_socket_file(mock_create_connection)
    self._setup_mock_instrumentation_cmd(mock_start_standing_subprocess,
                                         resp_lines=[
                                             b'SNIPPET START, PROTOCOL 1 0\n',
                                             b'SNIPPET SERVING, PORT 123\n',
                                         ])
    client = self._make_client()
    mock_start.side_effect = Exception('Some error')
    mock_stop.side_effect = Exception('Another error')
    with self.assertRaisesRegex(Exception, 'Some error'):
      client.start_app_and_connect()
    mock_stop.assert_called_once_with()
    self.assertFalse(client.is_alive)

  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'SnippetClient._do_start_app')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'SnippetClient._check_app_installed')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'SnippetClient._read_protocol_line')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'SnippetClient.connect')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'utils.get_available_host_port')
  def test_snippet_start_on_sdk_21(self, mock_get_port, mock_connect,
                                   mock_read_protocol_line,
                                   mock_check_app_installed, mock_do_start_app):
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
    client._ad.build_info['build_version_sdk'] = 21
    client._adb.shell = mock.Mock(return_value=b'setsid')
    client.start_app_and_connect()
    cmd_setsid = '%s am instrument  -w -e action start %s/%s' % (
        snippet_client._SETSID_COMMAND, MOCK_PACKAGE_NAME,
        snippet_client._INSTRUMENTATION_RUNNER_PACKAGE)
    mock_do_start_app.assert_has_calls([mock.call(cmd_setsid)])

  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'SnippetClient._do_start_app')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'SnippetClient._check_app_installed')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'SnippetClient._read_protocol_line')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'SnippetClient.connect')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'utils.get_available_host_port')
  def test_snippet_start_app_and_connect_persistent_session(
      self, mock_get_port, mock_connect, mock_read_protocol_line,
      mock_check_app_installed, mock_do_start_app):

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
    client.start_app_and_connect()
    cmd_setsid = '%s am instrument --user %s -w -e action start %s/%s' % (
        snippet_client._SETSID_COMMAND, MOCK_USER_ID, MOCK_PACKAGE_NAME,
        snippet_client._INSTRUMENTATION_RUNNER_PACKAGE)
    mock_do_start_app.assert_has_calls([mock.call(cmd_setsid)])

    # Test 'setsid' does not exist, but 'nohup' exsits
    client = self._make_client()
    client._adb.shell = _mocked_shell
    client.start_app_and_connect()
    cmd_nohup = '%s am instrument --user %s -w -e action start %s/%s' % (
        snippet_client._NOHUP_COMMAND, MOCK_USER_ID, MOCK_PACKAGE_NAME,
        snippet_client._INSTRUMENTATION_RUNNER_PACKAGE)
    mock_do_start_app.assert_has_calls(
        [mock.call(cmd_setsid), mock.call(cmd_nohup)])

    # Test both 'setsid' and 'nohup' do not exist
    client._adb.shell = mock.Mock(
        side_effect=adb.AdbError('cmd', 'stdout', 'stderr', 'ret_code'))
    client = self._make_client()
    client.start_app_and_connect()
    cmd_not_persist = ' am instrument --user %s -w -e action start %s/%s' % (
        MOCK_USER_ID, MOCK_PACKAGE_NAME,
        snippet_client._INSTRUMENTATION_RUNNER_PACKAGE)
    mock_do_start_app.assert_has_calls([
        mock.call(cmd_setsid),
        mock.call(cmd_nohup),
        mock.call(cmd_not_persist)
    ])

  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'utils.start_standing_subprocess')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'utils.get_available_host_port')
  def test_snippet_start_app_crash(self, mock_get_port,
                                   mock_start_standing_subprocess,
                                   mock_create_connection):
    mock_get_port.return_value = 456
    self.setup_mock_socket_file(mock_create_connection)
    self._setup_mock_instrumentation_cmd(
        mock_start_standing_subprocess,
        resp_lines=[b'INSTRUMENTATION_RESULT: shortMsg=Process crashed.\n'])
    client = self._make_client()
    with self.assertRaisesRegex(
        snippet_client.ProtocolVersionError,
        'INSTRUMENTATION_RESULT: shortMsg=Process crashed.'):
      client.start_app_and_connect()

  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'utils.start_standing_subprocess')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'utils.get_available_host_port')
  def test_snippet_start_app_and_connect_unknown_protocol(
      self, mock_get_port, mock_start_standing_subprocess):
    mock_get_port.return_value = 789
    self._setup_mock_instrumentation_cmd(
        mock_start_standing_subprocess,
        resp_lines=[b'SNIPPET START, PROTOCOL 99 0\n'])
    client = self._make_client()
    with self.assertRaisesRegex(snippet_client.ProtocolVersionError,
                                'SNIPPET START, PROTOCOL 99 0'):
      client.start_app_and_connect()

  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'utils.start_standing_subprocess')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'utils.get_available_host_port')
  def test_snippet_start_app_and_connect_header_junk(
      self, mock_get_port, mock_start_standing_subprocess,
      mock_create_connection):
    self.setup_mock_socket_file(mock_create_connection)
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
    client.start_app_and_connect()
    self.assertEqual(123, client.device_port)

  @mock.patch('socket.create_connection')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'utils.start_standing_subprocess')
  @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
              'utils.get_available_host_port')
  def test_snippet_start_app_and_connect_no_valid_line(
      self, mock_get_port, mock_start_standing_subprocess,
      mock_create_connection):
    mock_get_port.return_value = 456
    self.setup_mock_socket_file(mock_create_connection)
    self._setup_mock_instrumentation_cmd(
        mock_start_standing_subprocess,
        resp_lines=[
            b'This is some header junk\n',
            b'Some phones print arbitrary output\n',
            b'',  # readline uses '' to mark EOF
        ])
    client = self._make_client()
    with self.assertRaisesRegex(jsonrpc_client_base.AppStartError,
                                'Unexpected EOF waiting for app to start'):
      client.start_app_and_connect()

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

  def _make_client(self, adb_proxy=None):
    adb_proxy = adb_proxy or mock_android_device.MockAdbProxy(
        instrumented_packages=[(MOCK_PACKAGE_NAME,
                                snippet_client._INSTRUMENTATION_RUNNER_PACKAGE,
                                MOCK_PACKAGE_NAME)])
    ad = mock.Mock()
    ad.adb = adb_proxy
    ad.adb.current_user_id = MOCK_USER_ID
    ad.build_info = {
        'build_version_codename': ad.adb.getprop('ro.build.version.codename'),
        'build_version_sdk': ad.adb.getprop('ro.build.version.sdk'),
    }
    return snippet_client.SnippetClient(package=MOCK_PACKAGE_NAME, ad=ad)

  def _setup_mock_instrumentation_cmd(self, mock_start_standing_subprocess,
                                      resp_lines):
    mock_proc = mock_start_standing_subprocess()
    mock_proc.stdout.readline.side_effect = resp_lines


if __name__ == "__main__":
  unittest.main()
