# Copyright 2016 Google Inc.
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

from builtins import str as new_str

import io
import logging
import mock
import os
import shutil
import sys
import tempfile
import unittest
import yaml

from mobly import runtime_test_info
from mobly.controllers import android_device
from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import errors
from mobly.controllers.android_device_lib import snippet_client
from mobly.controllers.android_device_lib.services import base_service
from mobly.controllers.android_device_lib.services import logcat

from tests.lib import mock_android_device

MOCK_SNIPPET_PACKAGE_NAME = 'com.my.snippet'

# A mock SnippetClient used for testing snippet management logic.
MockSnippetClient = mock.MagicMock()
MockSnippetClient.package = MOCK_SNIPPET_PACKAGE_NAME


class AndroidDeviceTest(unittest.TestCase):
  """This test class has unit tests for the implementation of everything
  under mobly.controllers.android_device.
  """

  def setUp(self):
    # Set log_path to logging since mobly logger setup is not called.
    if not hasattr(logging, 'log_path'):
      setattr(logging, 'log_path', '/tmp/logs')
    # Creates a temp dir to be used by tests in this test class.
    self.tmp_dir = tempfile.mkdtemp()

  def tearDown(self):
    """Removes the temp dir.
    """
    shutil.rmtree(self.tmp_dir)

  # Tests for android_device module functions.
  # These tests use mock AndroidDevice instances.

  @mock.patch.object(android_device,
                     'get_all_instances',
                     new=mock_android_device.get_all_instances)
  @mock.patch.object(android_device,
                     'list_adb_devices',
                     new=mock_android_device.list_adb_devices)
  @mock.patch.object(android_device,
                     'list_adb_devices_by_usb_id',
                     new=mock_android_device.list_adb_devices)
  def test_create_with_pickup_all(self):
    pick_all_token = android_device.ANDROID_DEVICE_PICK_ALL_TOKEN
    actual_ads = android_device.create(pick_all_token)
    for actual, expected in zip(actual_ads,
                                mock_android_device.get_mock_ads(5)):
      self.assertEqual(actual.serial, expected.serial)

  @mock.patch.object(android_device,
                     'get_instances',
                     new=mock_android_device.get_instances)
  @mock.patch.object(android_device,
                     'list_adb_devices',
                     new=mock_android_device.list_adb_devices)
  @mock.patch.object(android_device,
                     'list_adb_devices_by_usb_id',
                     new=mock_android_device.list_adb_devices)
  def test_create_with_string_list(self):
    string_list = [u'1', '2']
    actual_ads = android_device.create(string_list)
    for actual_ad, expected_serial in zip(actual_ads, ['1', '2']):
      self.assertEqual(actual_ad.serial, expected_serial)

  @mock.patch.object(android_device,
                     'get_instances_with_configs',
                     new=mock_android_device.get_instances_with_configs)
  @mock.patch.object(android_device,
                     'list_adb_devices',
                     new=mock_android_device.list_adb_devices)
  @mock.patch.object(android_device,
                     'list_adb_devices_by_usb_id',
                     new=mock_android_device.list_adb_devices)
  def test_create_with_dict_list(self):
    string_list = [{'serial': '1'}, {'serial': '2'}]
    actual_ads = android_device.create(string_list)
    for actual_ad, expected_serial in zip(actual_ads, ['1', '2']):
      self.assertEqual(actual_ad.serial, expected_serial)

  @mock.patch.object(android_device,
                     'get_instances_with_configs',
                     new=mock_android_device.get_instances_with_configs)
  @mock.patch.object(android_device,
                     'list_adb_devices',
                     new=mock_android_device.list_adb_devices)
  @mock.patch.object(android_device,
                     'list_adb_devices_by_usb_id',
                     return_value=['usb:1'])
  def test_create_with_usb_id(self, mock_list_adb_devices_by_usb_id):
    string_list = [{'serial': '1'}, {'serial': '2'}, {'serial': 'usb:1'}]
    actual_ads = android_device.create(string_list)
    for actual_ad, expected_serial in zip(actual_ads, ['1', '2', 'usb:1']):
      self.assertEqual(actual_ad.serial, expected_serial)

  def test_create_with_empty_config(self):
    expected_msg = android_device.ANDROID_DEVICE_EMPTY_CONFIG_MSG
    with self.assertRaisesRegex(android_device.Error, expected_msg):
      android_device.create([])

  def test_create_with_not_list_config(self):
    expected_msg = android_device.ANDROID_DEVICE_NOT_LIST_CONFIG_MSG
    with self.assertRaisesRegex(android_device.Error, expected_msg):
      android_device.create('HAHA')

  def test_create_with_no_valid_config(self):
    expected_msg = 'No valid config found in: .*'
    with self.assertRaisesRegex(android_device.Error, expected_msg):
      android_device.create([1])

  @mock.patch('mobly.controllers.android_device.list_adb_devices')
  @mock.patch('mobly.controllers.android_device.list_adb_devices_by_usb_id')
  @mock.patch('mobly.controllers.android_device.AndroidDevice')
  def test_get_instances(self, mock_ad_class, mock_list_adb_usb, mock_list_adb):
    mock_list_adb.return_value = ['1']
    mock_list_adb_usb.return_value = []
    android_device.get_instances(['1'])
    mock_ad_class.assert_called_with('1')

  @mock.patch('mobly.controllers.android_device.list_adb_devices')
  @mock.patch('mobly.controllers.android_device.list_adb_devices_by_usb_id')
  @mock.patch('mobly.controllers.android_device.AndroidDevice')
  def test_get_instances_do_not_exist(self, mock_ad_class, mock_list_adb_usb,
                                      mock_list_adb):
    mock_list_adb.return_value = []
    mock_list_adb_usb.return_value = []
    with self.assertRaisesRegex(
        errors.Error,
        'Android device serial "1" is specified in config but is not reachable'
    ):
      android_device.get_instances(['1'])

  @mock.patch('mobly.controllers.android_device.list_adb_devices')
  @mock.patch('mobly.controllers.android_device.list_adb_devices_by_usb_id')
  @mock.patch('mobly.controllers.android_device.AndroidDevice')
  def test_get_instances_with_configs(self, mock_ad_class, mock_list_adb_usb,
                                      mock_list_adb):
    mock_list_adb.return_value = ['1', '2']
    mock_list_adb_usb.return_value = []
    configs = [{'serial': '1'}, {'serial': '2'}]
    android_device.get_instances_with_configs(configs)
    mock_ad_class.assert_any_call('1')
    mock_ad_class.assert_any_call('2')

  def test_get_instances_with_configs_invalid_config(self):
    config = {'something': 'random'}
    with self.assertRaisesRegex(
        errors.Error,
        f'Required value "serial" is missing in AndroidDevice config {config}'):
      android_device.get_instances_with_configs([config])

  @mock.patch('mobly.controllers.android_device.list_adb_devices')
  @mock.patch('mobly.controllers.android_device.list_adb_devices_by_usb_id')
  @mock.patch('mobly.controllers.android_device.AndroidDevice')
  def test_get_instances_with_configsdo_not_exist(self, mock_ad_class,
                                                  mock_list_adb_usb,
                                                  mock_list_adb):
    mock_list_adb.return_value = []
    mock_list_adb_usb.return_value = []
    config = {'serial': '1'}
    with self.assertRaisesRegex(
        errors.Error,
        'Android device serial "1" is specified in config but is not reachable'
    ):
      android_device.get_instances_with_configs([config])

  def test_get_devices_success_with_extra_field(self):
    ads = mock_android_device.get_mock_ads(5)
    expected_label = 'selected'
    expected_count = 2
    for ad in ads[:expected_count]:
      ad.label = expected_label
    selected_ads = android_device.get_devices(ads, label=expected_label)
    self.assertEqual(expected_count, len(selected_ads))
    for ad in selected_ads:
      self.assertEqual(ad.label, expected_label)

  def test_get_devices_no_match(self):
    ads = mock_android_device.get_mock_ads(5)
    expected_msg = ('Could not find a target device that matches condition'
                    ": {'label': 'selected'}.")
    with self.assertRaisesRegex(android_device.Error, expected_msg):
      selected_ads = android_device.get_devices(ads, label='selected')

  def test_get_device_success_with_serial(self):
    ads = mock_android_device.get_mock_ads(5)
    expected_serial = '0'
    ad = android_device.get_device(ads, serial=expected_serial)
    self.assertEqual(ad.serial, expected_serial)

  def test_get_device_success_with_serial_and_extra_field(self):
    ads = mock_android_device.get_mock_ads(5)
    expected_serial = '1'
    expected_h_port = 5555
    ads[1].h_port = expected_h_port
    ad = android_device.get_device(ads,
                                   serial=expected_serial,
                                   h_port=expected_h_port)
    self.assertEqual(ad.serial, expected_serial)
    self.assertEqual(ad.h_port, expected_h_port)

  def test_get_device_no_match(self):
    ads = mock_android_device.get_mock_ads(5)
    expected_msg = ('Could not find a target device that matches condition'
                    ": {'serial': 5}.")
    with self.assertRaisesRegex(android_device.Error, expected_msg):
      ad = android_device.get_device(ads, serial=len(ads))

  def test_get_device_too_many_matches(self):
    ads = mock_android_device.get_mock_ads(5)
    target_serial = ads[1].serial = ads[0].serial
    expected_msg = r"More than one device matched: \['0', '0'\]"
    with self.assertRaisesRegex(android_device.Error, expected_msg):
      android_device.get_device(ads, serial=target_serial)

  def test_start_services_on_ads(self):
    """Makes sure when an AndroidDevice fails to start some services, all
    AndroidDevice objects get cleaned up.
    """
    msg = 'Some error happened.'
    ads = mock_android_device.get_mock_ads(3)
    for ad in ads:
      ad.services.logcat.start = mock.MagicMock()
      ad.services.stop_all = mock.MagicMock()
      ad.skip_logcat = False
      ad.is_required = True
    ads[1].services.logcat.start = mock.MagicMock(
        side_effect=android_device.Error(msg))
    with self.assertRaisesRegex(android_device.Error, msg):
      android_device._start_services_on_ads(ads)
    ads[0].services.stop_all.assert_called_once_with()
    ads[1].services.stop_all.assert_called_once_with()
    ads[2].services.stop_all.assert_called_once_with()

  def test_start_services_on_ads_skip_logcat(self):
    ads = mock_android_device.get_mock_ads(3)
    ads[0].services.logcat.start = mock.MagicMock()
    ads[1].services.logcat.start = mock.MagicMock()
    ads[2].services.logcat.start = mock.MagicMock(
        side_effect=Exception('Should not have called this.'))
    ads[2].skip_logcat = True
    android_device._start_services_on_ads(ads)

  def test_take_bug_reports(self):
    ads = mock_android_device.get_mock_ads(3)
    android_device.take_bug_reports(ads, 'test_something', 'sometime')
    ads[0].take_bug_report.assert_called_once_with(test_name='test_something',
                                                   begin_time='sometime',
                                                   destination=None)
    ads[1].take_bug_report.assert_called_once_with(test_name='test_something',
                                                   begin_time='sometime',
                                                   destination=None)
    ads[2].take_bug_report.assert_called_once_with(test_name='test_something',
                                                   begin_time='sometime',
                                                   destination=None)

  def test_take_bug_reports_with_int_begin_time(self):
    ads = mock_android_device.get_mock_ads(3)
    android_device.take_bug_reports(ads, 'test_something', 123)
    ads[0].take_bug_report.assert_called_once_with(test_name='test_something',
                                                   begin_time='123',
                                                   destination=None)
    ads[1].take_bug_report.assert_called_once_with(test_name='test_something',
                                                   begin_time='123',
                                                   destination=None)
    ads[2].take_bug_report.assert_called_once_with(test_name='test_something',
                                                   begin_time='123',
                                                   destination=None)

  @mock.patch('mobly.logger.get_log_file_timestamp')
  def test_take_bug_reports_with_none_values(self, get_log_file_timestamp_mock):
    mock_timestamp = '07-22-2019_17-55-30-765'
    get_log_file_timestamp_mock.return_value = mock_timestamp
    ads = mock_android_device.get_mock_ads(3)
    android_device.take_bug_reports(ads)
    ads[0].take_bug_report.assert_called_once_with(test_name=None,
                                                   begin_time=mock_timestamp,
                                                   destination=None)
    ads[1].take_bug_report.assert_called_once_with(test_name=None,
                                                   begin_time=mock_timestamp,
                                                   destination=None)
    ads[2].take_bug_report.assert_called_once_with(test_name=None,
                                                   begin_time=mock_timestamp,
                                                   destination=None)

  # Tests for android_device.AndroidDevice class.
  # These tests mock out any interaction with the OS and real android device
  # in AndroidDeivce.

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  def test_AndroidDevice_instantiation(self, MockFastboot, MockAdbProxy):
    """Verifies the AndroidDevice object's basic attributes are correctly
    set after instantiation.
    """
    mock_serial = 1
    ad = android_device.AndroidDevice(serial=mock_serial)
    self.assertEqual(ad.serial, '1')
    self.assertEqual(ad.model, 'fakemodel')
    expected_lp = os.path.join(logging.log_path,
                               'AndroidDevice%s' % mock_serial)
    self.assertEqual(ad.log_path, expected_lp)
    self.assertIsNotNone(ad.services.logcat)
    self.assertIsNotNone(ad.services.snippets)

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy(1))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy(1))
  @mock.patch('mobly.utils.create_dir')
  def test_AndroidDevice_load_config(self, create_dir_mock, FastbootProxy,
                                     MockAdbProxy):
    mock_serial = '1'
    config = {'space': 'the final frontier', 'number': 1, 'debug_tag': 'my_tag'}
    ad = android_device.AndroidDevice(serial=mock_serial)
    ad.load_config(config)
    self.assertEqual(ad.space, 'the final frontier')
    self.assertEqual(ad.number, 1)
    self.assertEqual(ad.debug_tag, 'my_tag')

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy(1))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy(1))
  @mock.patch('mobly.utils.create_dir')
  def test_AndroidDevice_load_config_dup(self, create_dir_mock, FastbootProxy,
                                         MockAdbProxy):
    mock_serial = '1'
    config = {'serial': 'new_serial'}
    ad = android_device.AndroidDevice(serial=mock_serial)
    with self.assertRaisesRegex(android_device.DeviceError,
                                'Attribute serial already exists with'):
      ad.load_config(config)

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  def test_AndroidDevice_build_info(self, MockFastboot, MockAdbProxy):
    """Verifies the AndroidDevice object's basic attributes are correctly
    set after instantiation.
    """
    ad = android_device.AndroidDevice(serial='1')
    build_info = ad.build_info
    self.assertEqual(build_info['build_id'], 'AB42')
    self.assertEqual(build_info['build_type'], 'userdebug')
    self.assertEqual(build_info['build_version_codename'], 'Z')
    self.assertEqual(build_info['build_version_sdk'], '28')
    self.assertEqual(build_info['build_product'], 'FakeModel')
    self.assertEqual(build_info['build_characteristics'], 'emulator,phone')
    self.assertEqual(build_info['product_name'], 'FakeModel')
    self.assertEqual(build_info['debuggable'], '1')
    self.assertEqual(build_info['hardware'], 'marlin')
    self.assertEqual(len(build_info), len(android_device.CACHED_SYSTEM_PROPS))

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy(
                  '1',
                  mock_properties={
                      'ro.build.id': 'AB42',
                      'ro.build.type': 'userdebug',
                  }))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  def test_AndroidDevice_build_info_with_minimal_properties(
      self, MockFastboot, MockAdbProxy):
    ad = android_device.AndroidDevice(serial='1')
    build_info = ad.build_info
    self.assertEqual(build_info['build_id'], 'AB42')
    self.assertEqual(build_info['build_type'], 'userdebug')
    self.assertEqual(build_info['build_version_codename'], '')
    self.assertEqual(build_info['build_version_sdk'], '')
    self.assertEqual(build_info['build_product'], '')
    self.assertEqual(build_info['build_characteristics'], '')
    self.assertEqual(build_info['product_name'], '')
    self.assertEqual(build_info['debuggable'], '')
    self.assertEqual(build_info['hardware'], '')

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  def test_AndroidDevice_build_info_cached(self, MockFastboot, MockAdbProxy):
    """Verifies the AndroidDevice object's basic attributes are correctly
    set after instantiation.
    """
    ad = android_device.AndroidDevice(serial='1')
    _ = ad.build_info
    _ = ad.build_info
    _ = ad.build_info
    self.assertEqual(ad.adb.getprops_call_count, 1)

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy(
                  '1',
                  mock_properties={
                      'ro.build.id': 'AB42',
                      'ro.build.type': 'userdebug',
                      'ro.debuggable': '1',
                  }))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  def test_AndroidDevice_is_rootable_when_userdebug_device(
      self, MockFastboot, MockAdbProxy):
    ad = android_device.AndroidDevice(serial='1')
    self.assertTrue(ad.is_rootable)

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy(
                  '1',
                  mock_properties={
                      'ro.build.id': 'AB42',
                      'ro.build.type': 'user',
                      'ro.debuggable': '0',
                  }))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  def test_AndroidDevice_is_rootable_when_user_device(self, MockFastboot,
                                                      MockAdbProxy):
    ad = android_device.AndroidDevice(serial='1')
    self.assertFalse(ad.is_rootable)

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  def test_AndroidDevice_device_info(self, MockFastboot, MockAdbProxy):
    ad = android_device.AndroidDevice(serial=1)
    device_info = ad.device_info
    self.assertEqual(device_info['serial'], '1')
    self.assertEqual(device_info['model'], 'fakemodel')
    self.assertEqual(device_info['build_info']['build_id'], 'AB42')
    self.assertEqual(device_info['build_info']['build_type'], 'userdebug')
    ad.add_device_info('sim_type', 'Fi')
    ad.add_device_info('build_id', 'CD42')
    device_info = ad.device_info
    self.assertEqual(device_info['user_added_info']['sim_type'], 'Fi')
    self.assertEqual(device_info['user_added_info']['build_id'], 'CD42')

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  def test_AndroidDevice_serial_is_valid(self, MockFastboot, MockAdbProxy):
    """Verifies that the serial is a primitive string type and serializable.
    """
    ad = android_device.AndroidDevice(serial=1)
    self.assertTrue(isinstance(ad.serial, str))
    yaml.safe_dump(ad.serial)

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  def test_AndroidDevice_is_emulator_when_realish_device(
      self, MockFastboot, MockAdbProxy):
    ad = android_device.AndroidDevice(serial='1')
    self.assertFalse(ad.is_emulator)

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('localhost:123'))
  @mock.patch(
      'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
      return_value=mock_android_device.MockFastbootProxy('localhost:123'))
  def test_AndroidDevice_is_emulator_when_local_networked_device(
      self, MockFastboot, MockAdbProxy):
    # Although these devices are usually emulators, there might be a reason
    # to do this with a real device.
    ad = android_device.AndroidDevice(serial='localhost:123')
    self.assertFalse(ad.is_emulator)

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('example.com:123'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('example:123'))
  def test_AndroidDevice_is_emulator_when_remote_networked_device(
      self, MockFastboot, MockAdbProxy):
    ad = android_device.AndroidDevice(serial='example.com:123')
    self.assertFalse(ad.is_emulator)

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy(
                  'localhost:5554',
                  mock_properties={
                      'ro.hardware': 'ranchu',
                      'ro.build.id': 'AB42',
                      'ro.build.type': 'userdebug',
                  }))
  @mock.patch(
      'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
      return_value=mock_android_device.MockFastbootProxy('localhost:5554'))
  def test_AndroidDevice_is_emulator_when_ranchu_device(self, MockFastboot,
                                                        MockAdbProxy):
    ad = android_device.AndroidDevice(serial='localhost:5554')
    self.assertTrue(ad.is_emulator)

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy(
                  '1',
                  mock_properties={
                      'ro.build.id': 'AB42',
                      'ro.build.type': 'userdebug',
                      'ro.hardware': 'goldfish',
                  }))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  def test_AndroidDevice_is_emulator_when_goldfish_device(
      self, MockFastboot, MockAdbProxy):
    ad = android_device.AndroidDevice(serial='1')
    self.assertTrue(ad.is_emulator)

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy(
                  'example.com:123',
                  mock_properties={
                      'ro.build.id': 'AB42',
                      'ro.build.type': 'userdebug',
                      'ro.build.characteristics': 'emulator',
                  }))
  @mock.patch(
      'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
      return_value=mock_android_device.MockFastbootProxy('example.com:123'))
  def test_AndroidDevice_is_emulator_when_emulator_characteristic(
      self, MockFastboot, MockAdbProxy):
    ad = android_device.AndroidDevice(serial='example.com:123')
    self.assertTrue(ad.is_emulator)

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('emulator-5554'))
  @mock.patch(
      'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
      return_value=mock_android_device.MockFastbootProxy('emulator-5554'))
  def test_AndroidDevice_is_emulator_when_emulator_serial(
      self, MockFastboot, MockAdbProxy):
    ad = android_device.AndroidDevice(serial='emulator-5554')
    self.assertTrue(ad.is_emulator)

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.logger.get_log_file_timestamp')
  def test_AndroidDevice_generate_filename_default(self,
                                                   get_log_file_timestamp_mock,
                                                   MockFastboot, MockAdbProxy):
    mock_serial = 1
    ad = android_device.AndroidDevice(serial=mock_serial)
    get_log_file_timestamp_mock.return_value = '07-22-2019_17-53-34-450'
    filename = ad.generate_filename('MagicLog')
    self.assertEqual(filename, 'MagicLog,1,fakemodel,07-22-2019_17-53-34-450')

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.logger.get_log_file_timestamp')
  @mock.patch('mobly.logger.sanitize_filename')
  def test_AndroidDevice_generate_filename_assert_sanitation(
      self, sanitize_filename_mock, get_log_file_timestamp_mock, MockFastboot,
      MockAdbProxy):
    mock_serial = 1
    ad = android_device.AndroidDevice(serial=mock_serial)
    get_log_file_timestamp_mock.return_value = '07-22-2019_17-53-34-450'
    filename = ad.generate_filename('MagicLog')
    sanitize_filename_mock.assert_called_with(
        'MagicLog,1,fakemodel,07-22-2019_17-53-34-450')

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.logger.get_log_file_timestamp')
  def test_AndroidDevice_generate_filename_with_ext(self,
                                                    get_log_file_timestamp_mock,
                                                    MockFastboot, MockAdbProxy):
    mock_serial = 1
    ad = android_device.AndroidDevice(serial=mock_serial)
    get_log_file_timestamp_mock.return_value = '07-22-2019_17-53-34-450'
    filename = ad.generate_filename('MagicLog', extension_name='log')
    self.assertEqual(filename,
                     'MagicLog,1,fakemodel,07-22-2019_17-53-34-450.log')

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.logger.get_log_file_timestamp')
  def test_AndroidDevice_generate_filename_with_debug_tag(
      self, get_log_file_timestamp_mock, MockFastboot, MockAdbProxy):
    mock_serial = 1
    ad = android_device.AndroidDevice(serial=mock_serial)
    get_log_file_timestamp_mock.return_value = '07-22-2019_17-53-34-450'
    ad.debug_tag = 'RoleX'
    filename = ad.generate_filename('MagicLog')
    self.assertEqual(filename,
                     'MagicLog,RoleX,1,fakemodel,07-22-2019_17-53-34-450')

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.logger.get_log_file_timestamp')
  def test_AndroidDevice_generate_filename_with_runtime_info(
      self, get_log_file_timestamp_mock, MockFastboot, MockAdbProxy):
    mock_serial = 1
    ad = android_device.AndroidDevice(serial=mock_serial)
    get_log_file_timestamp_mock.return_value = '07-22-2019_17-53-34-450'
    mock_record = mock.MagicMock(test_name='test_xyz',
                                 begin_time='1234567',
                                 signature='test_xyz-1234567')
    mock_test_info = runtime_test_info.RuntimeTestInfo(mock_record.test_name,
                                                       '/tmp/blah/',
                                                       mock_record)
    filename = ad.generate_filename('MagicLog', time_identifier=mock_test_info)
    self.assertEqual(filename, 'MagicLog,1,fakemodel,test_xyz-1234567')

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.logger.get_log_file_timestamp')
  def test_AndroidDevice_generate_filename_with_custom_timestamp(
      self, get_log_file_timestamp_mock, MockFastboot, MockAdbProxy):
    mock_serial = 1
    ad = android_device.AndroidDevice(serial=mock_serial)
    get_log_file_timestamp_mock.return_value = '07-22-2019_17-53-34-450'
    filename = ad.generate_filename('MagicLog',
                                    time_identifier='my_special_time')
    self.assertEqual(filename, 'MagicLog,1,fakemodel,my_special_time')

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy(1))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy(1))
  @mock.patch('mobly.utils.create_dir')
  def test_AndroidDevice_take_bug_report(self, create_dir_mock, FastbootProxy,
                                         MockAdbProxy):
    """Verifies AndroidDevice.take_bug_report calls the correct adb command
    and writes the bugreport file to the correct path.
    """
    mock_serial = '1'
    ad = android_device.AndroidDevice(serial=mock_serial)
    output_path = ad.take_bug_report(test_name='test_something',
                                     begin_time='sometime')
    expected_path = os.path.join(logging.log_path,
                                 'AndroidDevice%s' % ad.serial, 'BugReports')
    create_dir_mock.assert_called_with(expected_path)
    self.assertEqual(
        output_path,
        os.path.join(expected_path,
                     'bugreport,test_something,1,fakemodel,sometime.zip'))

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1', fail_br=True))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.utils.create_dir')
  def test_AndroidDevice_take_bug_report_fail(self, create_dir_mock,
                                              FastbootProxy, MockAdbProxy):
    """Verifies AndroidDevice.take_bug_report writes out the correct message
    when taking bugreport fails.
    """
    mock_serial = '1'
    ad = android_device.AndroidDevice(serial=mock_serial)
    expected_msg = '.* Failed to take bugreport.'
    with self.assertRaisesRegex(android_device.Error, expected_msg):
      ad.take_bug_report(test_name='test_something', begin_time='sometime')

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.utils.create_dir')
  @mock.patch('mobly.logger.get_log_file_timestamp')
  def test_AndroidDevice_take_bug_report_without_args(
      self, get_log_file_timestamp_mock, create_dir_mock, FastbootProxy,
      MockAdbProxy):
    get_log_file_timestamp_mock.return_value = '07-22-2019_17-53-34-450'
    mock_serial = '1'
    ad = android_device.AndroidDevice(serial=mock_serial)
    output_path = ad.take_bug_report()
    expected_path = os.path.join(logging.log_path,
                                 'AndroidDevice%s' % ad.serial, 'BugReports')
    self.assertEqual(
        output_path,
        os.path.join(expected_path,
                     'bugreport,1,fakemodel,07-22-2019_17-53-34-450.zip'))

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.utils.create_dir')
  @mock.patch('mobly.logger.get_log_file_timestamp')
  def test_AndroidDevice_take_bug_report_with_only_test_name(
      self, get_log_file_timestamp_mock, create_dir_mock, FastbootProxy,
      MockAdbProxy):
    get_log_file_timestamp_mock.return_value = '07-22-2019_17-53-34-450'
    mock_serial = '1'
    ad = android_device.AndroidDevice(serial=mock_serial)
    output_path = ad.take_bug_report(test_name='test_something')
    expected_path = os.path.join(logging.log_path,
                                 'AndroidDevice%s' % ad.serial, 'BugReports')
    create_dir_mock.assert_called_with(expected_path)
    self.assertEqual(
        output_path,
        os.path.join(
            expected_path,
            'bugreport,test_something,1,fakemodel,07-22-2019_17-53-34-450.zip'))

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy(1))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy(1))
  @mock.patch('mobly.utils.create_dir')
  def test_AndroidDevice_take_bug_report_with_only_begin_time(
      self, create_dir_mock, FastbootProxy, MockAdbProxy):
    mock_serial = '1'
    ad = android_device.AndroidDevice(serial=mock_serial)
    output_path = ad.take_bug_report(begin_time='sometime')
    expected_path = os.path.join(logging.log_path,
                                 'AndroidDevice%s' % ad.serial, 'BugReports')
    create_dir_mock.assert_called_with(expected_path)
    self.assertEqual(
        output_path,
        os.path.join(expected_path, 'bugreport,1,fakemodel,sometime.zip'))

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy(1))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy(1))
  @mock.patch('mobly.utils.create_dir')
  def test_AndroidDevice_take_bug_report_with_int_begin_time(
      self, create_dir_mock, FastbootProxy, MockAdbProxy):
    mock_serial = '1'
    ad = android_device.AndroidDevice(serial=mock_serial)
    output_path = ad.take_bug_report(begin_time=123)
    expected_path = os.path.join(logging.log_path,
                                 'AndroidDevice%s' % ad.serial, 'BugReports')
    create_dir_mock.assert_called_with(expected_path)
    self.assertEqual(
        output_path, os.path.join(expected_path,
                                  'bugreport,1,fakemodel,123.zip'))

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy(1))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy(1))
  @mock.patch('mobly.utils.create_dir')
  def test_AndroidDevice_take_bug_report_with_positional_args(
      self, create_dir_mock, FastbootProxy, MockAdbProxy):
    mock_serial = '1'
    ad = android_device.AndroidDevice(serial=mock_serial)
    output_path = ad.take_bug_report('test_something', 'sometime')
    expected_path = os.path.join(logging.log_path,
                                 'AndroidDevice%s' % ad.serial, 'BugReports')
    create_dir_mock.assert_called_with(expected_path)
    self.assertEqual(
        output_path,
        os.path.join(expected_path,
                     'bugreport,test_something,1,fakemodel,sometime.zip'))

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.utils.create_dir')
  def test_AndroidDevice_take_bug_report_with_destination(
      self, create_dir_mock, FastbootProxy, MockAdbProxy):
    mock_serial = '1'
    ad = android_device.AndroidDevice(serial=mock_serial)
    dest = tempfile.gettempdir()
    output_path = ad.take_bug_report(test_name="test_something",
                                     begin_time="sometime",
                                     destination=dest)
    expected_path = os.path.join(dest)
    create_dir_mock.assert_called_with(expected_path)
    self.assertEqual(
        output_path,
        os.path.join(expected_path,
                     'bugreport,test_something,1,fakemodel,sometime.zip'))

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy(
                  '1', fail_br_before_N=True))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.utils.create_dir')
  def test_AndroidDevice_take_bug_report_fallback(self, create_dir_mock,
                                                  FastbootProxy, MockAdbProxy):
    """Verifies AndroidDevice.take_bug_report falls back to traditional
    bugreport on builds that do not have bugreportz.
    """
    mock_serial = '1'
    ad = android_device.AndroidDevice(serial=mock_serial)
    output_path = ad.take_bug_report(test_name='test_something',
                                     begin_time='sometime')
    expected_path = os.path.join(logging.log_path,
                                 'AndroidDevice%s' % ad.serial, 'BugReports')
    create_dir_mock.assert_called_with(expected_path)
    self.assertEqual(
        output_path,
        os.path.join(expected_path,
                     'bugreport,test_something,1,fakemodel,sometime.txt'))

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.utils.create_dir')
  @mock.patch('mobly.logger.get_log_file_timestamp')
  def test_AndroidDevice_take_screenshot(self, get_log_file_timestamp_mock,
                                         create_dir_mock, FastbootProxy,
                                         MockAdbProxy):
    get_log_file_timestamp_mock.return_value = '07-22-2019_17-53-34-450'
    mock_serial = '1'
    ad = android_device.AndroidDevice(serial=mock_serial)
    full_pic_path = ad.take_screenshot(self.tmp_dir)
    self.assertEqual(
        full_pic_path,
        os.path.join(self.tmp_dir,
                     'screenshot,1,fakemodel,07-22-2019_17-53-34-450.png'))

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.utils.create_dir')
  @mock.patch('mobly.logger.get_log_file_timestamp')
  def test_AndroidDevice_take_screenshot_with_prefix(
    self, get_log_file_timestamp_mock, create_dir_mock,
    FastbootProxy, MockAdbProxy):
    get_log_file_timestamp_mock.return_value = '07-22-2019_17-53-34-450'
    mock_serial = '1'
    ad = android_device.AndroidDevice(serial=mock_serial)

    full_pic_path = ad.take_screenshot(self.tmp_dir, 'page_a')

    self.assertEqual(
        full_pic_path,
        os.path.join(self.tmp_dir,
                     'page_a,1,fakemodel,07-22-2019_17-53-34-450.png'))

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  def test_AndroidDevice_change_log_path(self, stop_proc_mock, start_proc_mock,
                                         FastbootProxy, MockAdbProxy):
    ad = android_device.AndroidDevice(serial='1')
    old_path = ad.log_path
    new_log_path = tempfile.mkdtemp()
    ad.log_path = new_log_path
    self.assertTrue(os.path.exists(new_log_path))
    self.assertFalse(os.path.exists(old_path))

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  def test_AndroidDevice_change_log_path_no_log_exists(self, stop_proc_mock,
                                                       start_proc_mock,
                                                       FastbootProxy,
                                                       MockAdbProxy):
    ad = android_device.AndroidDevice(serial='1')
    old_path = ad.log_path
    new_log_path = tempfile.mkdtemp()
    ad.log_path = new_log_path
    self.assertTrue(os.path.exists(new_log_path))
    self.assertFalse(os.path.exists(old_path))

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('127.0.0.1:5557'))
  @mock.patch(
      'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
      return_value=mock_android_device.MockFastbootProxy('127.0.0.1:5557'))
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  def test_AndroidDevice_with_reserved_character_in_serial_log_path(
      self, stop_proc_mock, start_proc_mock, FastbootProxy, MockAdbProxy):
    ad = android_device.AndroidDevice(serial='127.0.0.1:5557')
    base_log_path = os.path.basename(ad.log_path)
    self.assertEqual(base_log_path, 'AndroidDevice127.0.0.1-5557')

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.utils.create_dir')
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(logcat.Logcat, '_open_logcat_file')
  def test_AndroidDevice_change_log_path_with_service(
      self, open_logcat_mock, stop_proc_mock, start_proc_mock, creat_dir_mock,
      FastbootProxy, MockAdbProxy):
    ad = android_device.AndroidDevice(serial='1')
    ad.services.logcat.start()
    new_log_path = tempfile.mkdtemp()
    expected_msg = '.* Cannot change `log_path` when there is service running.'
    with self.assertRaisesRegex(android_device.Error, expected_msg):
      ad.log_path = new_log_path

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.utils.create_dir')
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  def test_AndroidDevice_change_log_path_with_existing_file(
      self, stop_proc_mock, start_proc_mock, creat_dir_mock, FastbootProxy,
      MockAdbProxy):
    ad = android_device.AndroidDevice(serial='1')
    new_log_path = tempfile.mkdtemp()
    new_file_path = os.path.join(new_log_path, 'file.txt')
    with io.open(new_file_path, 'w', encoding='utf-8') as f:
      f.write(u'hahah.')
    expected_msg = '.* Logs already exist .*'
    with self.assertRaisesRegex(android_device.Error, expected_msg):
      ad.log_path = new_log_path

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.utils.create_dir')
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  def test_AndroidDevice_update_serial(self, stop_proc_mock, start_proc_mock,
                                       creat_dir_mock, FastbootProxy,
                                       MockAdbProxy):
    ad = android_device.AndroidDevice(serial='1')
    ad.update_serial('2')
    self.assertEqual(ad.serial, '2')
    self.assertEqual(ad.debug_tag, ad.serial)
    self.assertEqual(ad.adb.serial, ad.serial)
    self.assertEqual(ad.fastboot.serial, ad.serial)

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.utils.create_dir')
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(logcat.Logcat, '_open_logcat_file')
  def test_AndroidDevice_update_serial_with_service_running(
      self, open_logcat_mock, stop_proc_mock, start_proc_mock, creat_dir_mock,
      FastbootProxy, MockAdbProxy):
    ad = android_device.AndroidDevice(serial='1')
    ad.services.logcat.start()
    expected_msg = '.* Cannot change device serial number when there is service running.'
    with self.assertRaisesRegex(android_device.Error, expected_msg):
      ad.update_serial('2')

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch(
      'mobly.controllers.android_device_lib.snippet_client.SnippetClient')
  @mock.patch('mobly.utils.get_available_host_port')
  def test_AndroidDevice_load_snippet(self, MockGetPort, MockSnippetClient,
                                      MockFastboot, MockAdbProxy):
    ad = android_device.AndroidDevice(serial='1')
    ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
    self.assertTrue(hasattr(ad, 'snippet'))

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch(
      'mobly.controllers.android_device_lib.snippet_client.SnippetClient')
  @mock.patch('mobly.utils.get_available_host_port')
  def test_AndroidDevice_getattr(self, MockGetPort, MockSnippetClient,
                                 MockFastboot, MockAdbProxy):
    ad = android_device.AndroidDevice(serial='1')
    ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
    value = {'value': 42}
    actual_value = getattr(ad, 'some_attr', value)
    self.assertEqual(actual_value, value)

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch(
      'mobly.controllers.android_device_lib.snippet_client.SnippetClient',
      return_value=MockSnippetClient)
  @mock.patch('mobly.utils.get_available_host_port')
  def test_AndroidDevice_load_snippet_dup_package(self, MockGetPort,
                                                  MockSnippetClient,
                                                  MockFastboot, MockAdbProxy):
    ad = android_device.AndroidDevice(serial='1')
    ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
    expected_msg = ('Snippet package "%s" has already been loaded under '
                    'name "snippet".') % MOCK_SNIPPET_PACKAGE_NAME
    with self.assertRaisesRegex(android_device.Error, expected_msg):
      ad.load_snippet('snippet2', MOCK_SNIPPET_PACKAGE_NAME)

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch(
      'mobly.controllers.android_device_lib.snippet_client.SnippetClient',
      return_value=MockSnippetClient)
  @mock.patch('mobly.utils.get_available_host_port')
  def test_AndroidDevice_load_snippet_dup_snippet_name(self, MockGetPort,
                                                       MockSnippetClient,
                                                       MockFastboot,
                                                       MockAdbProxy):
    ad = android_device.AndroidDevice(serial='1')
    ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
    expected_msg = ('.* Attribute "snippet" already exists, please use a '
                    'different name.')
    with self.assertRaisesRegex(android_device.Error, expected_msg):
      ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME + 'haha')

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch(
      'mobly.controllers.android_device_lib.snippet_client.SnippetClient')
  @mock.patch('mobly.utils.get_available_host_port')
  def test_AndroidDevice_load_snippet_dup_attribute_name(
      self, MockGetPort, MockSnippetClient, MockFastboot, MockAdbProxy):
    ad = android_device.AndroidDevice(serial='1')
    expected_msg = ('Attribute "%s" already exists, please use a different'
                    ' name') % 'adb'
    with self.assertRaisesRegex(android_device.Error, expected_msg):
      ad.load_snippet('adb', MOCK_SNIPPET_PACKAGE_NAME)

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch(
      'mobly.controllers.android_device_lib.snippet_client.SnippetClient')
  @mock.patch('mobly.utils.get_available_host_port')
  def test_AndroidDevice_load_snippet_start_app_fails(self, MockGetPort,
                                                      MockSnippetClient,
                                                      MockFastboot,
                                                      MockAdbProxy):
    """Verifies that the correct exception is raised if start app failed.

    It's possible that the `stop_app` call as part of the start app failure
    teardown also fails. So we want the exception from the start app
    failure.
    """
    expected_e = Exception('start failed.')
    MockSnippetClient.start_app_and_connect = mock.Mock(side_effect=expected_e)
    MockSnippetClient.stop_app = mock.Mock(
        side_effect=Exception('stop failed.'))
    ad = android_device.AndroidDevice(serial='1')
    try:
      ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
    except Exception as e:
      assertIs(e, expected_e)

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch(
      'mobly.controllers.android_device_lib.snippet_client.SnippetClient')
  @mock.patch('mobly.utils.get_available_host_port')
  def test_AndroidDevice_unload_snippet(self, MockGetPort, MockSnippetClient,
                                        MockFastboot, MockAdbProxy):
    ad = android_device.AndroidDevice(serial='1')
    ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
    ad.unload_snippet('snippet')
    self.assertFalse(hasattr(ad, 'snippet'))
    with self.assertRaisesRegex(
        android_device.SnippetError,
        '<AndroidDevice|1> No snippet registered with name "snippet"'):
      ad.unload_snippet('snippet')
    # Loading the same snippet again should succeed
    ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
    self.assertTrue(hasattr(ad, 'snippet'))

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch(
      'mobly.controllers.android_device_lib.snippet_client.SnippetClient')
  @mock.patch('mobly.utils.get_available_host_port')
  @mock.patch.object(logcat.Logcat, '_open_logcat_file')
  def test_AndroidDevice_snippet_cleanup(self, open_logcat_mock, MockGetPort,
                                         MockSnippetClient, MockFastboot,
                                         MockAdbProxy):
    ad = android_device.AndroidDevice(serial='1')
    ad.services.start_all()
    ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
    ad.unload_snippet('snippet')
    self.assertFalse(hasattr(ad, 'snippet'))

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  def test_AndroidDevice_debug_tag(self, MockFastboot, MockAdbProxy):
    mock_serial = '1'
    ad = android_device.AndroidDevice(serial=mock_serial)
    self.assertEqual(ad.debug_tag, '1')
    with self.assertRaisesRegex(
        android_device.DeviceError,
        r'<AndroidDevice\|1> Something'):
      raise android_device.DeviceError(ad, 'Something')

    # Verify that debug tag's setter updates the debug prefix correctly.
    ad.debug_tag = 'Mememe'
    with self.assertRaisesRegex(
        android_device.DeviceError,
        r'<AndroidDevice\|Mememe> Something'):
      raise android_device.DeviceError(ad, 'Something')

    # Verify that repr is changed correctly.
    with self.assertRaisesRegex(
        Exception,
        r'(<AndroidDevice\|Mememe>, \'Something\')'):
      raise Exception(ad, 'Something')

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(logcat.Logcat, '_open_logcat_file')
  def test_AndroidDevice_handle_usb_disconnect(self, open_logcat_mock,
                                               stop_proc_mock, start_proc_mock,
                                               FastbootProxy, MockAdbProxy):

    class MockService(base_service.BaseService):

      def __init__(self, device, configs=None):
        self._alive = False
        self.pause_called = False
        self.resume_called = False

      @property
      def is_alive(self):
        return self._alive

      def start(self, configs=None):
        self._alive = True

      def stop(self):
        self._alive = False

      def pause(self):
        self._alive = False
        self.pause_called = True

      def resume(self):
        self._alive = True
        self.resume_called = True

    ad = android_device.AndroidDevice(serial='1')
    ad.services.start_all()
    ad.services.register('mock_service', MockService)
    with ad.handle_usb_disconnect():
      self.assertFalse(ad.services.is_any_alive)
      self.assertTrue(ad.services.mock_service.pause_called)
      self.assertFalse(ad.services.mock_service.resume_called)
    self.assertTrue(ad.services.is_any_alive)
    self.assertTrue(ad.services.mock_service.resume_called)

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(logcat.Logcat, '_open_logcat_file')
  def test_AndroidDevice_handle_reboot(self, open_logcat_mock, stop_proc_mock,
                                       start_proc_mock, FastbootProxy,
                                       MockAdbProxy):

    class MockService(base_service.BaseService):

      def __init__(self, device, configs=None):
        self._alive = False
        self.pause_called = False
        self.resume_called = False

      @property
      def is_alive(self):
        return self._alive

      def start(self, configs=None):
        self._alive = True

      def stop(self):
        self._alive = False

      def pause(self):
        self._alive = False
        self.pause_called = True

      def resume(self):
        self._alive = True
        self.resume_called = True

    ad = android_device.AndroidDevice(serial='1')
    ad.services.start_all()
    ad.services.register('mock_service', MockService)
    with ad.handle_reboot():
      self.assertFalse(ad.services.is_any_alive)
      self.assertFalse(ad.services.mock_service.pause_called)
      self.assertFalse(ad.services.mock_service.resume_called)
    self.assertTrue(ad.services.is_any_alive)
    self.assertFalse(ad.services.mock_service.resume_called)

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(logcat.Logcat, '_open_logcat_file')
  def test_AndroidDevice_handle_reboot_changes_build_info(
      self, open_logcat_mock, stop_proc_mock, start_proc_mock, FastbootProxy,
      MockAdbProxy):
    ad = android_device.AndroidDevice(serial='1')
    with ad.handle_reboot():
      ad.adb.mock_properties['ro.build.type'] = 'user'
      ad.adb.mock_properties['ro.debuggable'] = '0'
    self.assertEqual(ad.build_info['build_type'], 'user')
    self.assertEqual(ad.build_info['debuggable'], '0')
    self.assertFalse(ad.is_rootable)
    self.assertEqual(ad.adb.getprops_call_count, 2)

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch('mobly.utils.start_standing_subprocess', return_value='process')
  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(logcat.Logcat, '_open_logcat_file')
  def test_AndroidDevice_handle_reboot_changes_build_info_with_caching(
      self, open_logcat_mock, stop_proc_mock, start_proc_mock, FastbootProxy,
      MockAdbProxy):
    ad = android_device.AndroidDevice(serial='1')  # Call getprops 1.
    rootable_states = [ad.is_rootable]
    with ad.handle_reboot():
      rootable_states.append(ad.is_rootable)  # Call getprops 2.
      ad.adb.mock_properties['ro.debuggable'] = '0'
      rootable_states.append(ad.is_rootable)  # Call getprops 3.
    # Call getprops 4, on context manager end.
    rootable_states.append(ad.is_rootable)  # Cached call.
    rootable_states.append(ad.is_rootable)  # Cached call.
    self.assertEqual(ad.adb.getprops_call_count, 4)
    self.assertEqual(rootable_states, [True, True, False, False, False])

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch(
      'mobly.controllers.android_device.AndroidDevice.is_boot_completed',
      side_effect=[
          False, False,
          adb.AdbTimeoutError(['adb', 'shell', 'getprop sys.boot_completed'],
                              timeout=5,
                              serial=1), True
      ])
  @mock.patch('time.sleep', return_value=None)
  @mock.patch('time.time', side_effect=[0, 5, 10, 15, 20, 25, 30])
  def test_AndroidDevice_wait_for_completion_completed(self, MockTime,
                                                       MockSleep,
                                                       MockIsBootCompleted,
                                                       FastbootProxy,
                                                       MockAdbProxy):
    ad = android_device.AndroidDevice(serial='1')
    raised = False
    try:
      ad.wait_for_boot_completion()
    except (adb.AdbError, adb.AdbTimeoutError):
      raised = True
    self.assertFalse(
        raised,
        'adb.AdbError or adb.AdbTimeoutError exception raised but not handled.')

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy('1'))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy('1'))
  @mock.patch(
      'mobly.controllers.android_device.AndroidDevice.is_boot_completed',
      side_effect=[
          False, False,
          adb.AdbTimeoutError(['adb', 'shell', 'getprop sys.boot_completed'],
                              timeout=5,
                              serial=1), False, False, False, False
      ])
  @mock.patch('time.sleep', return_value=None)
  @mock.patch('time.perf_counter', side_effect=[0, 5, 10, 15, 20, 25, 30])
  def test_AndroidDevice_wait_for_completion_never_boot(self, MockTime,
                                                        MockSleep,
                                                        MockIsBootCompleted,
                                                        FastbootProxy,
                                                        MockAdbProxy):
    ad = android_device.AndroidDevice(serial='1')
    raised = False
    try:
      with self.assertRaises(android_device.DeviceError):
        ad.wait_for_boot_completion(timeout=20)
    except (adb.AdbError, adb.AdbTimeoutError):
      raised = True
    self.assertFalse(
        raised,
        'adb.AdbError or adb.AdbTimeoutError exception raised but not handled.')

  def test_AndroidDevice_parse_device_list_when_decode_error(self):
    gbk_str = b'\xc4\xe3\xba\xc3'
    raised = False
    try:
      android_device.parse_device_list(gbk_str, 'some_key')
    except UnicodeDecodeError:
      raised = True
    self.assertTrue(raised, 'did not raise an exception when parsing gbk bytes')


if __name__ == '__main__':
  unittest.main()
