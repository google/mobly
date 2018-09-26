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
"""Unit tests for Mobly's ServiceManager."""
import mock

from future.tests.base import unittest

from mobly.controllers.android_device_lib import service_manager
from mobly.controllers.android_device_lib.services import base_service


class MockService(base_service.BaseService):
    def __init__(self, device, configs=None):
        self._device = device
        self._configs = configs
        self._alive = False

    @property
    def is_alive(self):
        return self._alive

    def start(self, configs=None):
        self._alive = True
        self._device.start()

    def stop(self):
        self._alive = False
        self._device.stop()


class ServiceManagerTest(unittest.TestCase):
    def test_service_manager_instantiation(self):
        mock_device = mock.MagicMock()
        manager = service_manager.ServiceManager(mock_device)

    def test_register(self):
        mock_device = mock.MagicMock()
        manager = service_manager.ServiceManager(mock_device)
        manager.register('mock_service', MockService)
        service = manager.mock_service
        self.assertTrue(service)
        self.assertTrue(service.is_alive)
        self.assertTrue(manager.is_any_alive)

    def test_register_dup_alias(self):
        mock_device = mock.MagicMock()
        manager = service_manager.ServiceManager(mock_device)
        manager.register('mock_service', MockService)
        with self.assertRaisesRegex(
                service_manager.Error,
                '.* A service is already registered with alias "mock_service"'
        ):
            manager.register('mock_service', MockService)

    def test_unregister(self):
        mock_device = mock.MagicMock()
        manager = service_manager.ServiceManager(mock_device)
        manager.register('mock_service', MockService)
        service = manager.mock_service
        manager.unregister('mock_service')
        self.assertFalse(manager.is_any_alive)
        self.assertFalse(service.is_alive)

    def test_unregister_non_existent(self):
        mock_device = mock.MagicMock()
        manager = service_manager.ServiceManager(mock_device)
        with self.assertRaisesRegex(
                service_manager.Error,
                '.* No service is registered with alias "mock_service"'):
            manager.unregister('mock_service')

    @mock.patch('mobly.expects.expect_no_raises')
    def test_unregister_handle_error_from_stop(self, mock_expect_func):
        mock_device = mock.MagicMock()
        manager = service_manager.ServiceManager(mock_device)
        manager.register('mock_service', MockService)
        service = manager.mock_service
        service._device.stop.side_deffect = Exception(
            'Something failed in stop.')
        manager.unregister('mock_service')
        mock_expect_func.assert_called_once_with(
            'Failed to stop service instance "mock_service".')

    def test_unregister_all(self):
        mock_device = mock.MagicMock()
        manager = service_manager.ServiceManager(mock_device)
        manager.register('mock_service1', MockService)
        manager.register('mock_service2', MockService)
        service1 = manager.mock_service1
        service2 = manager.mock_service2
        manager.unregister_all()
        self.assertFalse(manager.is_any_alive)
        self.assertFalse(service1.is_alive)
        self.assertFalse(service2.is_alive)

    def test_unregister_all(self):
        mock_device = mock.MagicMock()
        manager = service_manager.ServiceManager(mock_device)
        manager.register('mock_service1', MockService)
        manager.register('mock_service2', MockService)
        service1 = manager.mock_service1
        service2 = manager.mock_service2
        manager.unregister_all()
        self.assertFalse(manager.is_any_alive)
        self.assertFalse(service1.is_alive)
        self.assertFalse(service2.is_alive)

    def test_unregister_all_with_some_failed(self):
        mock_device = mock.MagicMock()
        manager = service_manager.ServiceManager(mock_device)
        manager.register('mock_service1', MockService)
        manager.register('mock_service2', MockService)
        service1 = manager.mock_service1
        service1._device.stop.side_deffect = Exception(
            'Something failed in stop.')
        service2 = manager.mock_service2
        manager.unregister_all()
        self.assertFalse(manager.is_any_alive)
        self.assertFalse(service1.is_alive)
        self.assertFalse(service2.is_alive)

    def test_pause_all(self):
        mock_device = mock.MagicMock()
        manager = service_manager.ServiceManager(mock_device)
        manager.register('mock_service1', MockService)
        manager.register('mock_service2', MockService)
        service1 = manager.mock_service1
        service2 = manager.mock_service2
        manager.pause_all()
        self.assertFalse(manager.is_any_alive)
        self.assertFalse(service1.is_alive)
        self.assertFalse(service2.is_alive)

    def test_pause_all_with_some_failed(self):
        mock_device = mock.MagicMock()
        manager = service_manager.ServiceManager(mock_device)
        manager.register('mock_service1', MockService)
        manager.register('mock_service2', MockService)
        service1 = manager.mock_service1
        service1._device.pause.side_deffect = Exception(
            'Something failed in stop.')
        service2 = manager.mock_service2
        manager.pause_all()
        self.assertFalse(manager.is_any_alive)
        # state of service1 is undefined
        # verify state of service2
        self.assertFalse(service2.is_alive)

    def test_resume_all(self):
        mock_device = mock.MagicMock()
        manager = service_manager.ServiceManager(mock_device)
        manager.register('mock_service1', MockService)
        manager.register('mock_service2', MockService)
        service1 = manager.mock_service1
        service2 = manager.mock_service2
        manager.pause_all()
        manager.resume_all()
        self.assertTrue(manager.is_any_alive)
        self.assertTrue(service1.is_alive)
        self.assertTrue(service2.is_alive)

    def test_resume_all_with_some_failed(self):
        mock_device = mock.MagicMock()
        manager = service_manager.ServiceManager(mock_device)
        manager.register('mock_service1', MockService)
        manager.register('mock_service2', MockService)
        service1 = manager.mock_service1
        service1._device.resume.side_deffect = Exception(
            'Something failed in stop.')
        service2 = manager.mock_service2
        manager.pause_all()
        manager.resume_all()
        self.assertTrue(manager.is_any_alive)
        # state of service1 is undefined
        # verify state of service2
        self.assertTrue(service2.is_alive)


if __name__ == '__main__':
    unittest.main()
