#!/usr/bin/env python3.4
#
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

import json
import mock
import socket
import unittest

from mobly.controllers.android_device_lib import jsonrpc_client_base
from mobly.controllers.android_device_lib import snippet_client
from tests.lib import mock_android_device

MOCK_PACKAGE_NAME = 'some.package.name'
MOCK_MISSING_PACKAGE_NAME = 'not.installed'
JSONRPC_BASE_PACKAGE = 'mobly.controllers.android_device_lib.jsonrpc_client_base.JsonRpcClientBase'

class MockAdbProxy(object):
    def __init__(self, **kwargs):
        self.apk_not_installed = kwargs.get('apk_not_installed', False)
        self.apk_not_instrumented = kwargs.get('apk_not_instrumented', False)
        self.target_not_installed = kwargs.get('target_not_installed', False)

    def shell(self, params, shell):
        if not shell:
            raise AssertionError('Shell has to be true for grep cmds.')
        if 'pm list package' in params:
            if self.apk_not_installed:
                return b''
            if self.target_not_installed and MOCK_MISSING_PACKAGE_NAME in params:
                return b''
            return bytes(r'package:%s\r' % MOCK_PACKAGE_NAME, 'utf-8')
        elif 'pm list instrumentation' in params:
            if self.apk_not_instrumented:
                return b''
            if self.target_not_installed:
                return bytes(r'instrumentation:{p}\r/{r} (target={mp})'.format(
                    p=MOCK_PACKAGE_NAME,
                    r=snippet_client._INSTRUMENTATION_RUNNER_PACKAGE,
                    mp=MOCK_MISSING_PACKAGE_NAME), 'utf-8')
            return bytes(r'instrumentation:{p}\r/{r} (target={p})'.format(
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


class JsonRpcClientBaseTest(unittest.TestCase):
    """Unit tests for mobly.controllers.android_device_lib.snippet_client.
    """

    @mock.patch('socket.create_connection')
    @mock.patch(JSONRPC_BASE_PACKAGE)
    def test_check_app_installed_normal(self, mock_create_connection,
                                        mock_client_base):
        sc = snippet_client.SnippetClient(MOCK_PACKAGE_NAME, 42,
                                          MockAdbProxy())
        sc.check_app_installed()

    @mock.patch('socket.create_connection')
    @mock.patch(JSONRPC_BASE_PACKAGE)
    def test_check_app_installed_fail_app_not_installed(
            self, mock_create_connection, mock_client_base):
        sc = snippet_client.SnippetClient(
            MOCK_PACKAGE_NAME, 42, MockAdbProxy(apk_not_installed=True))
        expected_msg = '%s is not installed on .*' % MOCK_PACKAGE_NAME
        with self.assertRaisesRegexp(jsonrpc_client_base.AppStartError,
                                     expected_msg):
            sc.check_app_installed()

    @mock.patch('socket.create_connection')
    @mock.patch(JSONRPC_BASE_PACKAGE)
    def test_check_app_installed_fail_not_instrumented(
            self, mock_create_connection, mock_client_base):
        sc = snippet_client.SnippetClient(
            MOCK_PACKAGE_NAME, 42, MockAdbProxy(apk_not_instrumented=True))
        expected_msg = '%s is installed on .*, but it is not instrumented.' % MOCK_PACKAGE_NAME
        with self.assertRaisesRegexp(jsonrpc_client_base.AppStartError,
                                     expected_msg):
            sc.check_app_installed()

    @mock.patch('socket.create_connection')
    @mock.patch(JSONRPC_BASE_PACKAGE)
    def test_check_app_installed_fail_target_not_installed(
            self, mock_create_connection, mock_client_base):
        sc = snippet_client.SnippetClient(
            MOCK_PACKAGE_NAME, 42, MockAdbProxy(target_not_installed=True))
        expected_msg = 'Instrumentation target %s is not installed on .*' % MOCK_MISSING_PACKAGE_NAME
        with self.assertRaisesRegexp(jsonrpc_client_base.AppStartError,
                                     expected_msg):
            sc.check_app_installed()


if __name__ == "__main__":
    unittest.main()
