# Copyright 2018 Google Inc.
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
import mock
import unittest

from mobly.controllers.android_device_lib.services import sl4a_service
from mobly.controllers.android_device_lib import service_manager


@mock.patch('mobly.controllers.android_device_lib.sl4a_client.Sl4aClient')
class Sl4aServiceTest(unittest.TestCase):
  """Tests for the sl4a service."""

  def test_instantiation(self, _):
    service = sl4a_service.Sl4aService(mock.MagicMock())
    self.assertFalse(service.is_alive)

  def test_start(self, mock_sl4a_client_class):
    mock_client = mock_sl4a_client_class.return_value
    service = sl4a_service.Sl4aService(mock.MagicMock())
    service.start()
    mock_client.start_app_and_connect.assert_called_once_with()
    self.assertTrue(service.is_alive)

  def test_stop(self, mock_sl4a_client_class):
    mock_client = mock_sl4a_client_class.return_value
    service = sl4a_service.Sl4aService(mock.MagicMock())
    service.start()
    service.stop()
    mock_client.stop_app.assert_called_once_with()
    self.assertFalse(service.is_alive)

  def test_pause(self, mock_sl4a_client_class):
    mock_client = mock_sl4a_client_class.return_value
    service = sl4a_service.Sl4aService(mock.MagicMock())
    service.start()
    service.pause()
    mock_client.stop_event_dispatcher.assert_called_once_with()
    mock_client.clear_host_port.assert_called_once_with()

  def test_resume(self, mock_sl4a_client_class):
    mock_client = mock_sl4a_client_class.return_value
    service = sl4a_service.Sl4aService(mock.MagicMock())
    service.start()
    service.pause()
    service.resume()
    mock_client.restore_app_connection.assert_called_once_with()

  def test_register_with_service_manager(self, _):
    mock_device = mock.MagicMock()
    manager = service_manager.ServiceManager(mock_device)
    manager.register('sl4a', sl4a_service.Sl4aService)
    self.assertTrue(manager.sl4a)


if __name__ == '__main__':
  unittest.main()
