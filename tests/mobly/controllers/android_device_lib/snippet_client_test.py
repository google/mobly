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
from future.tests.base import unittest

from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import jsonrpc_client_base
from mobly.controllers.android_device_lib import snippet_client
from tests.lib import jsonrpc_client_test_base

MOCK_PACKAGE_NAME = 'some.package.name'
MOCK_MISSING_PACKAGE_NAME = 'not.installed'
JSONRPC_BASE_CLASS = 'mobly.controllers.android_device_lib.jsonrpc_client_base.JsonRpcClientBase'


class MockAdbProxy(object):
    def __init__(self, **kwargs):
        self.apk_not_installed = kwargs.get('apk_not_installed', False)
        self.apk_not_instrumented = kwargs.get('apk_not_instrumented', False)
        self.target_not_installed = kwargs.get('target_not_installed', False)

    def shell(self, params, shell=False):
        if 'pm list package' in params:
            if self.apk_not_installed:
                return b''
            if self.target_not_installed and MOCK_MISSING_PACKAGE_NAME in params:
                return b''
            return bytes('package:%s' % MOCK_PACKAGE_NAME, 'utf-8')
        elif 'pm list instrumentation' in params:
            if self.apk_not_instrumented:
                return b''
            if self.target_not_installed:
                return bytes('instrumentation:{p}/{r} (target={mp})'.format(
                    p=MOCK_PACKAGE_NAME,
                    r=snippet_client._INSTRUMENTATION_RUNNER_PACKAGE,
                    mp=MOCK_MISSING_PACKAGE_NAME), 'utf-8')
            return bytes('instrumentation:{p}/{r} (target={p})'.format(
                p=MOCK_PACKAGE_NAME,
                r=snippet_client._INSTRUMENTATION_RUNNER_PACKAGE), 'utf-8')
        elif 'which' in params:
            return b''

    def __getattr__(self, name):
        """All calls to the none-existent functions in adb proxy would
        simply return the adb command string.
        """

        def adb_call(*args):
            arg_str = ' '.join(str(elem) for elem in args)
            return arg_str

        return adb_call


class SnippetClientTest(jsonrpc_client_test_base.JsonRpcClientTestBase):
    """Unit tests for mobly.controllers.android_device_lib.snippet_client.
    """

    def test_check_app_installed_normal(self):
        sc = self._make_client()
        sc._check_app_installed()

    def test_check_app_installed_fail_app_not_installed(self):
        sc = self._make_client(MockAdbProxy(apk_not_installed=True))
        expected_msg = '.* %s is not installed.' % MOCK_PACKAGE_NAME
        with self.assertRaisesRegex(jsonrpc_client_base.AppStartError,
                                    expected_msg):
            sc._check_app_installed()

    def test_check_app_installed_fail_not_instrumented(self):
        sc = self._make_client(MockAdbProxy(apk_not_instrumented=True))
        expected_msg = ('.* %s is installed, but it is not instrumented.' %
                        MOCK_PACKAGE_NAME)
        with self.assertRaisesRegex(jsonrpc_client_base.AppStartError,
                                    expected_msg):
            sc._check_app_installed()

    def test_check_app_installed_fail_target_not_installed(self):
        sc = self._make_client(MockAdbProxy(target_not_installed=True))
        expected_msg = ('.* Instrumentation target %s is not installed.' %
                        MOCK_MISSING_PACKAGE_NAME)
        with self.assertRaisesRegex(jsonrpc_client_base.AppStartError,
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

    @mock.patch('socket.create_connection')
    @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
                'utils.start_standing_subprocess')
    @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
                'utils.get_available_host_port')
    def test_snippet_start_app_and_connect(self, mock_get_port,
                                           mock_start_standing_subprocess,
                                           mock_create_connection):
        self.setup_mock_socket_file(mock_create_connection)
        self._setup_mock_instrumentation_cmd(
            mock_start_standing_subprocess,
            resp_lines=[
                b'SNIPPET START, PROTOCOL 1 0\n',
                b'SNIPPET SERVING, PORT 123\n',
            ])
        client = self._make_client()
        client.start_app_and_connect()
        self.assertEqual(123, client.device_port)

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
        client._adb.shell = mock.Mock(return_value=b'setsid')
        client.start_app_and_connect()
        cmd_setsid = '%s am instrument -w -e action start %s/%s' % (
            snippet_client._SETSID_COMMAND, MOCK_PACKAGE_NAME,
            snippet_client._INSTRUMENTATION_RUNNER_PACKAGE)
        mock_do_start_app.assert_has_calls(mock.call(cmd_setsid))

        # Test 'setsid' does not exist, but 'nohup' exsits
        client = self._make_client()
        client._adb.shell = _mocked_shell
        client.start_app_and_connect()
        cmd_nohup = '%s am instrument -w -e action start %s/%s' % (
            snippet_client._NOHUP_COMMAND, MOCK_PACKAGE_NAME,
            snippet_client._INSTRUMENTATION_RUNNER_PACKAGE)
        mock_do_start_app.assert_has_calls(
            [mock.call(cmd_setsid), mock.call(cmd_nohup)])

        # Test both 'setsid' and 'nohup' do not exist
        client._adb.shell = mock.Mock(side_effect=adb.AdbError(
            'cmd', 'stdout', 'stderr', 'ret_code'))
        client = self._make_client()
        client.start_app_and_connect()
        cmd_not_persist = ' am instrument -w -e action start %s/%s' % (
            MOCK_PACKAGE_NAME, snippet_client._INSTRUMENTATION_RUNNER_PACKAGE)
        mock_do_start_app.assert_has_calls([
            mock.call(cmd_setsid), mock.call(cmd_nohup),
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
            resp_lines=[
                b'INSTRUMENTATION_RESULT: shortMsg=Process crashed.\n'
            ])
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

    def _make_client(self, adb_proxy=None):
        adb_proxy = adb_proxy or MockAdbProxy()
        ad = mock.Mock()
        ad.adb = adb_proxy
        return snippet_client.SnippetClient(
            package=MOCK_PACKAGE_NAME, ad=ad)

    def _setup_mock_instrumentation_cmd(self, mock_start_standing_subprocess,
                                        resp_lines):
        mock_proc = mock_start_standing_subprocess()
        mock_proc.stdout.readline.side_effect = resp_lines


if __name__ == "__main__":
    unittest.main()
