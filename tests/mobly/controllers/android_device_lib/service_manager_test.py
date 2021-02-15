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

import importlib
import mock
import unittest

from mobly import expects
from mobly.controllers.android_device_lib import service_manager
from mobly.controllers.android_device_lib.services import base_service


class MockService(base_service.BaseService):

  def __init__(self, device, configs=None):
    self._device = device
    self._configs = configs
    self._alive = False
    self.start_func = mock.MagicMock()
    self.stop_func = mock.MagicMock()
    self.pause_func = mock.MagicMock()
    self.resume_func = mock.MagicMock()

  @property
  def is_alive(self):
    return self._alive

  def start(self, configs=None):
    self.start_func(configs)
    self._alive = True

  def stop(self):
    self.stop_func()
    self._alive = False

  def pause(self):
    self.pause_func()
    self._alive = False

  def resume(self):
    self.resume_func()
    self._alive = True


class ServiceManagerTest(unittest.TestCase):

  def setUp(self):
    # Reset hidden global `expects` state.
    importlib.reload(expects)

  def assert_recorded_one_error(self, message):
    self.assertEqual(expects.recorder.error_count, 1)
    for _, error in (expects.DEFAULT_TEST_RESULT_RECORD.extra_errors.items()):
      self.assertIn(message, error.details)

  def test_service_manager_instantiation(self):
    manager = service_manager.ServiceManager(mock.MagicMock())

  def test_register(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service', MockService)
    service = manager.mock_service
    self.assertTrue(service)
    self.assertTrue(service.is_alive)
    self.assertTrue(manager.is_any_alive)
    self.assertEqual(service.alias, 'mock_service')
    self.assertEqual(service.start_func.call_count, 1)

  def test_register_with_configs(self):
    mock_configs = mock.MagicMock()
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service', MockService, configs=mock_configs)
    service = manager.mock_service
    self.assertTrue(service)
    self.assertEqual(service._configs, mock_configs)
    self.assertEqual(service.start_func.call_count, 1)

  def test_register_do_not_start_service(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service', MockService, start_service=False)
    service = manager.mock_service
    self.assertTrue(service)
    self.assertFalse(service.is_alive)
    self.assertFalse(manager.is_any_alive)
    self.assertEqual(service.start_func.call_count, 0)

  def test_register_not_a_class(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    with self.assertRaisesRegex(service_manager.Error, '.* is not a class!'):
      manager.register('mock_service', base_service)

  def test_register_wrong_subclass_type(self):

    class MyClass:
      pass

    manager = service_manager.ServiceManager(mock.MagicMock())
    with self.assertRaisesRegex(service_manager.Error,
                                '.* is not a subclass of BaseService!'):
      manager.register('mock_service', MyClass)

  def test_register_dup_alias(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service', MockService)
    msg = '.* A service is already registered with alias "mock_service"'
    with self.assertRaisesRegex(service_manager.Error, msg):
      manager.register('mock_service', MockService)

  def test_for_each(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service1', MockService)
    manager.register('mock_service2', MockService)
    service1 = manager.mock_service1
    service2 = manager.mock_service2
    service1.ha = mock.MagicMock()
    service2.ha = mock.MagicMock()
    manager.for_each(lambda service: service.ha())
    service1.ha.assert_called_with()
    service2.ha.assert_called_with()

  def test_for_each_modify_during_iteration(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service1', MockService)
    manager.register('mock_service2', MockService)
    service1 = manager.mock_service1
    service2 = manager.mock_service2
    service1.ha = mock.MagicMock()
    service2.ha = mock.MagicMock()
    manager.for_each(
        lambda service: manager._service_objects.pop(service.alias))
    self.assertFalse(manager._service_objects)

  def test_for_each_one_fail(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service1', MockService)
    manager.register('mock_service2', MockService)
    service1 = manager.mock_service1
    service2 = manager.mock_service2
    service1.ha = mock.MagicMock()
    service1.ha.side_effect = Exception('Failure in service1.')
    service2.ha = mock.MagicMock()
    manager.for_each(lambda service: service.ha())
    service1.ha.assert_called_with()
    service2.ha.assert_called_with()
    self.assert_recorded_one_error('Failure in service1.')

  def test_create_output_excerpts_all(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service1', MockService)
    manager.register('mock_service2', MockService)
    manager.register('mock_service3', MockService)
    service1 = manager.mock_service1
    service2 = manager.mock_service2
    service3 = manager.mock_service3
    service1.create_output_excerpts = mock.MagicMock()
    service2.create_output_excerpts = mock.MagicMock()
    service3.create_output_excerpts = mock.MagicMock()
    service1.create_output_excerpts.return_value = ['path/to/1.txt']
    service2.create_output_excerpts.return_value = [
        'path/to/2-1.txt', 'path/to/2-2.txt'
    ]
    service3.create_output_excerpts.return_value = []
    mock_test_info = mock.MagicMock(output_path='path/to')
    result = manager.create_output_excerpts_all(mock_test_info)
    self.assertEqual(result['mock_service1'], ['path/to/1.txt'])
    self.assertEqual(result['mock_service2'],
                     ['path/to/2-1.txt', 'path/to/2-2.txt'])
    self.assertEqual(result['mock_service3'], [])

  def test_unregister(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service', MockService)
    service = manager.mock_service
    manager.unregister('mock_service')
    self.assertFalse(manager.is_any_alive)
    self.assertFalse(service.is_alive)
    self.assertEqual(service.stop_func.call_count, 1)

  def test_unregister_not_started_service(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service', MockService, start_service=False)
    service = manager.mock_service
    manager.unregister('mock_service')
    self.assertFalse(manager.is_any_alive)
    self.assertFalse(service.is_alive)
    self.assertEqual(service.stop_func.call_count, 0)

  def test_unregister_non_existent(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    with self.assertRaisesRegex(
        service_manager.Error,
        '.* No service is registered with alias "mock_service"'):
      manager.unregister('mock_service')

  def test_unregister_handle_error_from_stop(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service', MockService)
    service = manager.mock_service
    service.stop_func.side_effect = Exception('Something failed in stop.')
    manager.unregister('mock_service')
    self.assert_recorded_one_error(
        'Failed to stop service instance "mock_service".')

  def test_unregister_all(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service1', MockService)
    manager.register('mock_service2', MockService)
    service1 = manager.mock_service1
    service2 = manager.mock_service2
    manager.unregister_all()
    self.assertFalse(manager.is_any_alive)
    self.assertFalse(service1.is_alive)
    self.assertFalse(service2.is_alive)
    self.assertEqual(service1.stop_func.call_count, 1)
    self.assertEqual(service2.stop_func.call_count, 1)

  def test_unregister_all_with_some_failed(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service1', MockService)
    manager.register('mock_service2', MockService)
    service1 = manager.mock_service1
    service1.stop_func.side_effect = Exception('Something failed in stop.')
    service2 = manager.mock_service2
    manager.unregister_all()
    self.assertFalse(manager.is_any_alive)
    self.assertTrue(service1.is_alive)
    self.assertFalse(service2.is_alive)
    self.assert_recorded_one_error(
        'Failed to stop service instance "mock_service1".')

  def test_start_all(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service1', MockService, start_service=False)
    manager.register('mock_service2', MockService, start_service=False)
    service1 = manager.mock_service1
    service2 = manager.mock_service2
    mock_call_tracker = mock.Mock()
    mock_call_tracker.start1 = service1.start_func
    mock_call_tracker.start2 = service2.start_func
    manager.start_all()
    self.assertTrue(service1.is_alive)
    self.assertTrue(service2.is_alive)
    self.assertEqual(service1.start_func.call_count, 1)
    self.assertEqual(service2.start_func.call_count, 1)
    self.assertEqual(
        mock_call_tracker.mock_calls,
        [mock.call.start1(None), mock.call.start2(None)])

  def test_start_all_with_already_started_services(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service1', MockService)
    manager.register('mock_service2', MockService, start_service=False)
    service1 = manager.mock_service1
    service2 = manager.mock_service2
    manager.start_all()
    manager.start_all()
    self.assertTrue(service1.is_alive)
    self.assertTrue(service2.is_alive)
    self.assertEqual(service1.start_func.call_count, 1)
    self.assertEqual(service2.start_func.call_count, 1)

  def test_start_all_with_some_failed(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service1', MockService, start_service=False)
    manager.register('mock_service2', MockService, start_service=False)
    service1 = manager.mock_service1
    service1.start_func.side_effect = Exception('Something failed in start.')
    service2 = manager.mock_service2
    manager.start_all()
    self.assertFalse(service1.is_alive)
    self.assertTrue(service2.is_alive)
    self.assert_recorded_one_error('Failed to start service "mock_service1"')

  def test_stop_all(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service1', MockService)
    manager.register('mock_service2', MockService)
    service1 = manager.mock_service1
    service2 = manager.mock_service2
    mock_call_tracker = mock.Mock()
    mock_call_tracker.stop1 = service1.stop_func
    mock_call_tracker.stop2 = service2.stop_func
    manager.stop_all()
    self.assertFalse(service1.is_alive)
    self.assertFalse(service2.is_alive)
    self.assertEqual(mock_call_tracker.mock_calls,
                     [mock.call.stop2(), mock.call.stop1()])
    self.assertEqual(service1.start_func.call_count, 1)
    self.assertEqual(service2.start_func.call_count, 1)
    self.assertEqual(service1.stop_func.call_count, 1)
    self.assertEqual(service2.stop_func.call_count, 1)

  def test_stop_all_with_already_stopped_services(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service1', MockService)
    manager.register('mock_service2', MockService, start_service=False)
    service1 = manager.mock_service1
    service2 = manager.mock_service2
    manager.stop_all()
    manager.stop_all()
    self.assertFalse(service1.is_alive)
    self.assertFalse(service2.is_alive)
    self.assertEqual(service1.start_func.call_count, 1)
    self.assertEqual(service2.start_func.call_count, 0)
    self.assertEqual(service1.stop_func.call_count, 1)
    self.assertEqual(service2.stop_func.call_count, 0)

  def test_stop_all_with_some_failed(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service1', MockService)
    manager.register('mock_service2', MockService)
    service1 = manager.mock_service1
    service1.stop_func.side_effect = Exception('Something failed in start.')
    service2 = manager.mock_service2
    manager.stop_all()
    self.assertTrue(service1.is_alive)
    self.assertFalse(service2.is_alive)
    self.assert_recorded_one_error('Failed to stop service "mock_service1"')

  def test_start_all_and_stop_all_serveral_times(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service1', MockService)
    manager.register('mock_service2', MockService, start_service=False)
    service1 = manager.mock_service1
    service2 = manager.mock_service2
    manager.stop_all()
    manager.start_all()
    manager.stop_all()
    manager.start_all()
    manager.stop_all()
    manager.start_all()
    self.assertTrue(service1.is_alive)
    self.assertTrue(service2.is_alive)
    self.assertEqual(service1.start_func.call_count, 4)
    self.assertEqual(service2.start_func.call_count, 3)
    self.assertEqual(service1.stop_func.call_count, 3)
    self.assertEqual(service2.stop_func.call_count, 2)

  def test_pause_all(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service1', MockService)
    manager.register('mock_service2', MockService)
    service1 = manager.mock_service1
    service2 = manager.mock_service2
    mock_call_tracker = mock.Mock()
    mock_call_tracker.pause1 = service1.pause_func
    mock_call_tracker.pause2 = service2.pause_func
    manager.pause_all()
    self.assertEqual(
        mock_call_tracker.mock_calls,
        [mock.call.pause2(), mock.call.pause1()])
    self.assertEqual(service1.pause_func.call_count, 1)
    self.assertEqual(service2.pause_func.call_count, 1)
    self.assertEqual(service1.resume_func.call_count, 0)
    self.assertEqual(service2.resume_func.call_count, 0)

  def test_pause_all_with_some_failed(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service1', MockService)
    manager.register('mock_service2', MockService)
    service1 = manager.mock_service1
    service1.pause_func.side_effect = Exception('Something failed in pause.')
    service2 = manager.mock_service2
    manager.pause_all()
    self.assertEqual(service1.pause_func.call_count, 1)
    self.assertEqual(service2.pause_func.call_count, 1)
    self.assertEqual(service1.resume_func.call_count, 0)
    self.assertEqual(service2.resume_func.call_count, 0)
    self.assert_recorded_one_error('Failed to pause service "mock_service1".')

  def test_resume_all(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service1', MockService)
    manager.register('mock_service2', MockService)
    service1 = manager.mock_service1
    service2 = manager.mock_service2
    mock_call_tracker = mock.Mock()
    mock_call_tracker.resume1 = service1.resume_func
    mock_call_tracker.resume2 = service2.resume_func
    manager.pause_all()
    manager.resume_all()
    self.assertEqual(
        mock_call_tracker.mock_calls,
        [mock.call.resume1(), mock.call.resume2()])
    self.assertEqual(service1.pause_func.call_count, 1)
    self.assertEqual(service2.pause_func.call_count, 1)
    self.assertEqual(service1.resume_func.call_count, 1)
    self.assertEqual(service2.resume_func.call_count, 1)

  def test_resume_all_with_some_failed(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service1', MockService)
    manager.register('mock_service2', MockService)
    service1 = manager.mock_service1
    service1.resume_func.side_effect = Exception('Something failed in resume.')
    service2 = manager.mock_service2
    manager.pause_all()
    manager.resume_all()
    self.assertEqual(service1.pause_func.call_count, 1)
    self.assertEqual(service2.pause_func.call_count, 1)
    self.assertEqual(service1.resume_func.call_count, 1)
    self.assertEqual(service2.resume_func.call_count, 1)
    self.assert_recorded_one_error('Failed to resume service "mock_service1".')

  def test_list_live_services(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service1', MockService, start_service=False)
    manager.register('mock_service2', MockService)
    aliases = manager.list_live_services()
    self.assertEqual(aliases, ['mock_service2'])
    manager.stop_all()
    aliases = manager.list_live_services()
    self.assertEqual(aliases, [])

  def test_start_services(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service1', MockService, start_service=False)
    manager.register('mock_service2', MockService, start_service=False)
    manager.start_services(['mock_service2'])
    aliases = manager.list_live_services()
    self.assertEqual(aliases, ['mock_service2'])

  def test_start_services_non_existent(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    msg = ('.* No service is registered under the name "mock_service", '
           'cannot start.')
    with self.assertRaisesRegex(service_manager.Error, msg):
      manager.start_services(['mock_service'])

  def test_resume_services(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    manager.register('mock_service1', MockService)
    manager.register('mock_service2', MockService)
    manager.pause_all()
    aliases = manager.list_live_services()
    self.assertEqual(aliases, [])
    manager.resume_services(['mock_service2'])
    aliases = manager.list_live_services()
    self.assertEqual(aliases, ['mock_service2'])

  def test_resume_services_non_existent(self):
    manager = service_manager.ServiceManager(mock.MagicMock())
    msg = ('.* No service is registered under the name "mock_service", '
           'cannot resume.')
    with self.assertRaisesRegex(service_manager.Error, msg):
      manager.resume_services(['mock_service'])


if __name__ == '__main__':
  unittest.main()
