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
"""Unit tests for controller manager."""

import mock
import unittest

from mobly import controller_manager
from mobly import signals

from tests.lib import mock_controller


class ControllerManagerTest(unittest.TestCase):
  """Unit tests for Mobly's ControllerManager."""

  def test_verify_controller_module(self):
    controller_manager.verify_controller_module(mock_controller)

  def test_verify_controller_module_null_attr(self):
    try:
      tmp = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
      mock_controller.MOBLY_CONTROLLER_CONFIG_NAME = None
      msg = 'Controller interface .* in .* cannot be null.'
      with self.assertRaisesRegex(signals.ControllerError, msg):
        controller_manager.verify_controller_module(mock_controller)
    finally:
      mock_controller.MOBLY_CONTROLLER_CONFIG_NAME = tmp

  def test_verify_controller_module_missing_attr(self):
    try:
      tmp = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
      delattr(mock_controller, 'MOBLY_CONTROLLER_CONFIG_NAME')
      msg = 'Module .* missing required controller module attribute'
      with self.assertRaisesRegex(signals.ControllerError, msg):
        controller_manager.verify_controller_module(mock_controller)
    finally:
      setattr(mock_controller, 'MOBLY_CONTROLLER_CONFIG_NAME', tmp)

  def test_register_controller_no_config(self):
    c_manager = controller_manager.ControllerManager('SomeClass', {})
    with self.assertRaisesRegex(signals.ControllerError,
                                'No corresponding config found for'):
      c_manager.register_controller(mock_controller)

  def test_register_controller_no_config_for_not_required(self):
    c_manager = controller_manager.ControllerManager('SomeClass', {})
    self.assertIsNone(
        c_manager.register_controller(mock_controller, required=False))

  def test_register_controller_dup_register(self):
    """Verifies correctness of registration, internal tally of controllers
    objects, and the right error happen when a controller module is
    registered twice.
    """
    mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
    controller_configs = {mock_ctrlr_config_name: ['magic1', 'magic2']}
    c_manager = controller_manager.ControllerManager('SomeClass',
                                                     controller_configs)
    c_manager.register_controller(mock_controller)
    registered_name = 'mock_controller'
    self.assertTrue(registered_name in c_manager._controller_objects)
    mock_ctrlrs = c_manager._controller_objects[registered_name]
    self.assertEqual(mock_ctrlrs[0].magic, 'magic1')
    self.assertEqual(mock_ctrlrs[1].magic, 'magic2')
    self.assertTrue(c_manager._controller_modules[registered_name])
    expected_msg = 'Controller module .* has already been registered.'
    with self.assertRaisesRegex(signals.ControllerError, expected_msg):
      c_manager.register_controller(mock_controller)

  def test_register_controller_return_value(self):
    mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
    controller_configs = {mock_ctrlr_config_name: ['magic1', 'magic2']}
    c_manager = controller_manager.ControllerManager('SomeClass',
                                                     controller_configs)
    magic_devices = c_manager.register_controller(mock_controller)
    self.assertEqual(magic_devices[0].magic, 'magic1')
    self.assertEqual(magic_devices[1].magic, 'magic2')

  def test_register_controller_change_return_value(self):
    mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
    controller_configs = {mock_ctrlr_config_name: ['magic1', 'magic2']}
    c_manager = controller_manager.ControllerManager('SomeClass',
                                                     controller_configs)
    magic_devices = c_manager.register_controller(mock_controller)
    magic1 = magic_devices.pop(0)
    self.assertIs(magic1, c_manager._controller_objects['mock_controller'][0])
    self.assertEqual(len(c_manager._controller_objects['mock_controller']), 2)

  def test_register_controller_less_than_min_number(self):
    mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
    controller_configs = {mock_ctrlr_config_name: ['magic1', 'magic2']}
    c_manager = controller_manager.ControllerManager('SomeClass',
                                                     controller_configs)
    expected_msg = 'Expected to get at least 3 controller objects, got 2.'
    with self.assertRaisesRegex(signals.ControllerError, expected_msg):
      c_manager.register_controller(mock_controller, min_number=3)

  @mock.patch('yaml.dump', side_effect=TypeError('ha'))
  def test_get_controller_info_record_not_serializable(self, _):
    mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
    controller_configs = {mock_ctrlr_config_name: ['magic1', 'magic2']}
    c_manager = controller_manager.ControllerManager('SomeClass',
                                                     controller_configs)
    c_manager.register_controller(mock_controller)
    record = c_manager.get_controller_info_records()[0]
    actual_controller_info = record.controller_info
    self.assertEqual(actual_controller_info,
                     "[{'MyMagic': 'magic1'}, {'MyMagic': 'magic2'}]")

  def test_controller_record_exists_without_get_info(self):
    mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
    controller_configs = {mock_ctrlr_config_name: ['magic1', 'magic2']}
    c_manager = controller_manager.ControllerManager('SomeClass',
                                                     controller_configs)
    get_info = getattr(mock_controller, 'get_info')
    delattr(mock_controller, 'get_info')
    try:
      c_manager.register_controller(mock_controller)
      record = c_manager.get_controller_info_records()[0]
      self.assertIsNone(record.controller_info)
      self.assertEqual(record.test_class, 'SomeClass')
      self.assertEqual(record.controller_name, 'MagicDevice')
    finally:
      setattr(mock_controller, 'get_info', get_info)

  @mock.patch('tests.lib.mock_controller.get_info')
  def test_get_controller_info_records_empty(self, mock_get_info_func):
    mock_get_info_func.return_value = None
    mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
    controller_configs = {mock_ctrlr_config_name: ['magic1', 'magic2']}
    c_manager = controller_manager.ControllerManager('SomeClass',
                                                     controller_configs)
    c_manager.register_controller(mock_controller)
    record = c_manager.get_controller_info_records()[0]
    self.assertIsNone(record.controller_info)
    self.assertEqual(record.test_class, 'SomeClass')
    self.assertEqual(record.controller_name, 'MagicDevice')

  @mock.patch('mobly.expects._ExpectErrorRecorder.add_error')
  @mock.patch('tests.lib.mock_controller.get_info')
  def test_get_controller_info_records_error(self, mock_get_info_func,
                                             mock_add_error):
    mock_get_info_func.side_effect = Exception('Record info failed.')
    mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
    controller_configs = {mock_ctrlr_config_name: ['magic1', 'magic2']}
    c_manager = controller_manager.ControllerManager('SomeClass',
                                                     controller_configs)
    c_manager.register_controller(mock_controller)
    self.assertFalse(c_manager.get_controller_info_records())
    mock_add_error.assert_called_once()
    error_record = mock_add_error.call_args[0][0]
    self.assertIn('Record info failed.', error_record.stacktrace)

  def test_get_controller_info_records(self):
    mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
    controller_configs = {mock_ctrlr_config_name: ['magic1', 'magic2']}
    c_manager = controller_manager.ControllerManager('SomeClass',
                                                     controller_configs)
    c_manager.register_controller(mock_controller)
    record = c_manager.get_controller_info_records()[0]
    record_dict = record.to_dict()
    record_dict.pop('Timestamp')
    self.assertEqual(
        record_dict, {
            'Controller Info': [{
                'MyMagic': 'magic1'
            }, {
                'MyMagic': 'magic2'
            }],
            'Controller Name': 'MagicDevice',
            'Test Class': 'SomeClass'
        })

  def test_get_controller_info_without_registration(self):
    mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
    controller_configs = {mock_ctrlr_config_name: ['magic1', 'magic2']}
    c_manager = controller_manager.ControllerManager('SomeClass',
                                                     controller_configs)
    self.assertFalse(c_manager.get_controller_info_records())

  @mock.patch('tests.lib.mock_controller.destroy')
  def test_unregister_controller(self, mock_destroy_func):
    mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
    controller_configs = {mock_ctrlr_config_name: ['magic1', 'magic2']}
    c_manager = controller_manager.ControllerManager('SomeClass',
                                                     controller_configs)
    objects = c_manager.register_controller(mock_controller)
    c_manager.unregister_controllers()
    mock_destroy_func.assert_called_once_with(objects)
    self.assertFalse(c_manager._controller_objects)
    self.assertFalse(c_manager._controller_modules)

  @mock.patch('mobly.expects._ExpectErrorRecorder.add_error')
  @mock.patch('tests.lib.mock_controller.destroy')
  def test_unregister_controller_error(self, mock_destroy_func, mock_add_error):
    mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
    controller_configs = {mock_ctrlr_config_name: ['magic1', 'magic2']}
    c_manager = controller_manager.ControllerManager('SomeClass',
                                                     controller_configs)
    c_manager.register_controller(mock_controller)
    mock_destroy_func.side_effect = Exception('Failed in destroy.')
    c_manager.unregister_controllers()
    mock_add_error.assert_called_once()
    error_record = mock_add_error.call_args[0][0]
    self.assertIn('Failed in destroy.', error_record.stacktrace)
    self.assertFalse(c_manager._controller_objects)
    self.assertFalse(c_manager._controller_modules)

  @mock.patch('tests.lib.mock_controller.destroy')
  def test_unregister_controller_without_registration(self, mock_destroy_func):
    mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
    controller_configs = {mock_ctrlr_config_name: ['magic1', 'magic2']}
    c_manager = controller_manager.ControllerManager('SomeClass',
                                                     controller_configs)
    c_manager.unregister_controllers()
    mock_destroy_func.assert_not_called()
    self.assertFalse(c_manager._controller_objects)
    self.assertFalse(c_manager._controller_modules)


if __name__ == "__main__":
  unittest.main()
