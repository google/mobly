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
        expected_msg = '%s is not installed on .*' % MOCK_PACKAGE_NAME
        with self.assertRaisesRegexp(jsonrpc_client_base.AppStartError,
                                     expected_msg):
            sc._check_app_installed()

    def test_check_app_installed_fail_not_instrumented(self):
        sc = self._make_client(MockAdbProxy(apk_not_instrumented=True))
        expected_msg = '%s is installed on .*, but it is not instrumented.' % MOCK_PACKAGE_NAME
        with self.assertRaisesRegexp(jsonrpc_client_base.AppStartError,
                                     expected_msg):
            sc._check_app_installed()

    def test_check_app_installed_fail_target_not_installed(self):
        sc = self._make_client(MockAdbProxy(target_not_installed=True))
        expected_msg = 'Instrumentation target %s is not installed on .*' % MOCK_MISSING_PACKAGE_NAME
        with self.assertRaisesRegexp(jsonrpc_client_base.AppStartError,
                                     expected_msg):
            sc._check_app_installed()

    @mock.patch('socket.create_connection')
    def test_snippet_start(self, mock_create_connection):
        import pudb
        pudb.set_trace()
        self.setup_mock_socket_file(mock_create_connection)
        client = self._make_client()
        client.connect()
        result = client.testSnippetCall()
        self.assertEqual(123, result)

    @mock.patch('socket.create_connection')
    def test_snippet_start_event_client(self, mock_create_connection):
        import pudb
        pudb.set_trace()
        fake_file = self.setup_mock_socket_file(mock_create_connection)
        client = self._make_client()
        client.connect()
        fake_file.resp = self.MOCK_RESP_WITH_CALLBACK
        result = client.testSnippetCall()
        self.assertEqual(123, result)

    def _make_client(self, adb_proxy=MockAdbProxy()):
        return snippet_client.SnippetClient(
            package=MOCK_PACKAGE_NAME, adb_proxy=adb_proxy)


if __name__ == "__main__":
    unittest.main()
