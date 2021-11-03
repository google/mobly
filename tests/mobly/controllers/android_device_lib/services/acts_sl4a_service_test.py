# Copyright 2021 Google Inc.
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

import mock

from mobly.controllers.android_device_lib import service_manager
from mobly.controllers.android_device_lib.acts_sl4a_lib import sl4a_session
from mobly.controllers.android_device_lib.services import acts_sl4a_service


class MockSl4aSession(sl4a_session.Sl4aSession):
  """Mock Sl4aSession class."""

  def __init__(self):
    super().__init__(mock.MagicMock(), 0, 0, None, None)


class ActsSl4aServiceTest(unittest.TestCase):
  """Tests for the ACTS sl4a service."""

  def test_instantiation(self):
    service = acts_sl4a_service.ActsSl4aService(mock.MagicMock())
    self.assertIsNotNone(service.sl4a_manager)
    self.assertFalse(service.is_alive)

  @mock.patch('mobly.controllers.android_device_lib.acts_sl4a_lib.rpc_client.RpcClient')
  @mock.patch('mobly.controllers.android_device_lib.acts_sl4a_lib.event_dispatcher.EventDispatcher')
  @mock.patch('mobly.controllers.android_device_lib.acts_sl4a_lib.sl4a_session.Sl4aSession')
  def test_start(self, mock_sl4a_session, *_):
    mock_session = MockSl4aSession()
    mock_sl4a_session.return_value = mock_session
    service = acts_sl4a_service.ActsSl4aService(mock.MagicMock())
    service.start()
    self.assertEqual(service.sl4a_session, mock_session)
    self.assertEqual(service.ed, mock_session.get_event_dispatcher())
    service.ed.start.assert_called_once()
    self.assertTrue(service.is_alive)

  @mock.patch('mobly.controllers.android_device_lib.acts_sl4a_lib.rpc_client.RpcClient')
  @mock.patch('mobly.controllers.android_device_lib.acts_sl4a_lib.event_dispatcher.EventDispatcher')
  @mock.patch('mobly.controllers.android_device_lib.acts_sl4a_lib.sl4a_session.Sl4aSession')
  def test_stop(self, mock_sl4a_session, *_):
    mock_sl4a_session.return_value = MockSl4aSession()
    service = acts_sl4a_service.ActsSl4aService(mock.MagicMock())
    service.start()
    service.stop()
    self.assertFalse(service.is_alive)

  def test_register_with_service_manager(self):
    mock_device = mock.MagicMock()
    manager = service_manager.ServiceManager(mock_device)
    manager.register('sl4a', acts_sl4a_service.ActsSl4aService,
                     start_service=False)
    self.assertTrue(manager.sl4a)


if __name__ == '__main__':
  unittest.main()
