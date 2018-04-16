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
from mobly.controllers.android_device_lib import sl4a_client
from tests.lib import jsonrpc_client_test_base


class MockAdbProxy(object):
    def __init__(self, **kwargs):
        self.apk_not_installed = kwargs.get('apk_not_installed', False)

    def shell(self, params, shell=False):
        if 'pm list package' in params:
            if self.apk_not_installed:
                return bytes('', 'utf-8')
            return bytes('package:com.googlecode.android_scripting', 'utf-8')

    def getprop(self, params):
        if params == 'ro.build.version.codename':
            return 'Z'
        elif params == 'ro.build.version.sdk':
            return '28'

    def __getattr__(self, name):
        """All calls to the none-existent functions in adb proxy would
        simply return the adb command string.
        """

        def adb_call(*args):
            arg_str = ' '.join(str(elem) for elem in args)
            return arg_str

        return adb_call


class Sl4aClientTest(jsonrpc_client_test_base.JsonRpcClientTestBase):
    """Unit tests for mobly.controllers.android_device_lib.sl4a_client.
    """

    @mock.patch('socket.create_connection')
    @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
                'utils.start_standing_subprocess')
    @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
                'utils.get_available_host_port')
    def test_start_app_and_connect(self, mock_get_port,
                                   mock_start_standing_subprocess,
                                   mock_create_connection):
        self.setup_mock_socket_file(mock_create_connection)
        self._setup_mock_instrumentation_cmd(
            mock_start_standing_subprocess, resp_lines=[b'\n'])
        client = self._make_client()
        client.start_app_and_connect()
        self.assertEqual(8080, client.device_port)

    @mock.patch('socket.create_connection')
    @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
                'utils.start_standing_subprocess')
    @mock.patch('mobly.controllers.android_device_lib.snippet_client.'
                'utils.get_available_host_port')
    def test_app_not_installed(self, mock_get_port,
                               mock_start_standing_subprocess,
                               mock_create_connection):
        self.setup_mock_socket_file(mock_create_connection)
        self._setup_mock_instrumentation_cmd(
            mock_start_standing_subprocess, resp_lines=[b'\n'])
        client = self._make_client(adb_proxy=MockAdbProxy(
            apk_not_installed=True))
        with self.assertRaisesRegex(jsonrpc_client_base.AppStartError,
                                    '.* SL4A is not installed on .*'):
            client.start_app_and_connect()

    def _make_client(self, adb_proxy=None):
        adb_proxy = adb_proxy or MockAdbProxy()
        ad = mock.Mock()
        ad.adb = adb_proxy
        return sl4a_client.Sl4aClient(ad=ad)

    def _setup_mock_instrumentation_cmd(self, mock_start_standing_subprocess,
                                        resp_lines):
        mock_proc = mock_start_standing_subprocess()
        mock_proc.stdout.readline.side_effect = resp_lines


if __name__ == "__main__":
    unittest.main()
