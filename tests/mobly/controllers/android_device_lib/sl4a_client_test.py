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
from mobly.controllers.android_device_lib import sl4a_client
from tests.lib import jsonrpc_client_test_base
from tests.lib import mock_android_device


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
    self._setup_mock_instrumentation_cmd(mock_start_standing_subprocess,
                                         resp_lines=[b'\n'])
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
    self._setup_mock_instrumentation_cmd(mock_start_standing_subprocess,
                                         resp_lines=[b'\n'])
    client = self._make_client(adb_proxy=mock_android_device.MockAdbProxy())
    with self.assertRaisesRegex(jsonrpc_client_base.AppStartError,
                                '.* SL4A is not installed on .*'):
      client.start_app_and_connect()

  def _make_client(self, adb_proxy=None):
    adb_proxy = adb_proxy or mock_android_device.MockAdbProxy(
        installed_packages=['com.googlecode.android_scripting'])
    ad = mock.Mock()
    ad.adb = adb_proxy
    ad.build_info = {
        'build_version_codename': ad.adb.getprop('ro.build.version.codename'),
        'build_version_sdk': ad.adb.getprop('ro.build.version.sdk'),
    }
    return sl4a_client.Sl4aClient(ad=ad)

  def _setup_mock_instrumentation_cmd(self, mock_start_standing_subprocess,
                                      resp_lines):
    mock_proc = mock_start_standing_subprocess()
    mock_proc.stdout.readline.side_effect = resp_lines


if __name__ == "__main__":
  unittest.main()
