# Copyright 2019 Google Inc.
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

import os
import mock
import unittest

from mobly.controllers import android_device
from mobly.controllers.android_device_lib import jsonrpc_shell_base


class JsonRpcClientBaseTest(unittest.TestCase):
  """Unit tests for mobly.controllers.android_device_lib.jsonrpc_shell_base."""

  @mock.patch.object(android_device, 'list_adb_devices')
  @mock.patch.object(android_device, 'get_instances')
  @mock.patch.object(os, 'environ', new={})
  def test_load_device(self, mock_get_instances, mock_list_adb_devices):
    mock_list_adb_devices.return_value = ['1234', '4312']
    mock_device = mock.MagicMock(spec=android_device.AndroidDevice)
    mock_get_instances.return_value = [mock_device]
    json_shell = jsonrpc_shell_base.JsonRpcShellBase()
    json_shell.load_device(serial='1234')
    self.assertEqual(json_shell._ad, mock_device)

  @mock.patch.object(android_device, 'list_adb_devices')
  @mock.patch.object(android_device, 'get_instances')
  @mock.patch.object(os, 'environ', new={})
  def test_load_device_when_one_device(self, mock_get_instances,
                                       mock_list_adb_devices):
    mock_list_adb_devices.return_value = ['1234']
    mock_device = mock.MagicMock(spec=android_device.AndroidDevice)
    mock_get_instances.return_value = [mock_device]
    json_shell = jsonrpc_shell_base.JsonRpcShellBase()
    json_shell.load_device()
    self.assertEqual(json_shell._ad, mock_device)

  @mock.patch.object(android_device, 'list_adb_devices')
  @mock.patch.object(android_device, 'get_instances')
  @mock.patch.object(os, 'environ', new={'ANDROID_SERIAL': '1234'})
  def test_load_device_when_android_serial(self, mock_get_instances,
                                           mock_list_adb_devices):
    mock_list_adb_devices.return_value = ['1234', '4321']
    mock_device = mock.MagicMock(spec=android_device.AndroidDevice)
    mock_get_instances.return_value = [mock_device]
    json_shell = jsonrpc_shell_base.JsonRpcShellBase()
    json_shell.load_device()
    self.assertEqual(json_shell._ad, mock_device)

  @mock.patch.object(android_device, 'list_adb_devices')
  def test_load_device_when_no_devices(self, mock_list_adb_devices):
    mock_list_adb_devices.return_value = []
    json_shell = jsonrpc_shell_base.JsonRpcShellBase()
    with self.assertRaisesRegex(jsonrpc_shell_base.Error,
                                'No adb device found!'):
      json_shell.load_device()

  @mock.patch.object(android_device, 'list_adb_devices')
  @mock.patch.object(os, 'environ', new={})
  def test_load_device_when_unspecified_device(self, mock_list_adb_devices):
    mock_list_adb_devices.return_value = ['1234', '4321']
    json_shell = jsonrpc_shell_base.JsonRpcShellBase()
    with self.assertRaisesRegex(jsonrpc_shell_base.Error,
                                'Expected one phone.*'):
      json_shell.load_device()

  @mock.patch.object(android_device, 'list_adb_devices')
  @mock.patch.object(os, 'environ', new={})
  def test_load_device_when_device_not_found(self, mock_list_adb_devices):
    mock_list_adb_devices.return_value = ['4321']
    json_shell = jsonrpc_shell_base.JsonRpcShellBase()
    with self.assertRaisesRegex(jsonrpc_shell_base.Error,
                                'Device "1234" is not found by adb.'):
      json_shell.load_device(serial='1234')


if __name__ == '__main__':
  unittest.main()
