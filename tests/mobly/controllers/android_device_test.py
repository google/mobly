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

import logging
import mock
import os
import shutil
import sys
import tempfile
import yaml

from future.tests.base import unittest

from mobly import utils
from mobly.controllers import android_device
from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import snippet_client

from tests.lib import mock_android_device

# Mock log path for a test run.
MOCK_LOG_PATH = '/tmp/logs/MockTest/xx-xx-xx_xx-xx-xx/'
# The expected result of the cat adb operation.
MOCK_ADB_LOGCAT_CAT_RESULT = [
    '02-29 14:02:21.456  4454  Something\n',
    '02-29 14:02:21.789  4454  Something again\n'
]
# A mockd piece of adb logcat output.
MOCK_ADB_LOGCAT = ('02-29 14:02:19.123  4454  Nothing\n'
                   '%s'
                   '02-29 14:02:22.123  4454  Something again and again\n'
                   ) % ''.join(MOCK_ADB_LOGCAT_CAT_RESULT)
# Mock start and end time of the adb cat.
MOCK_ADB_LOGCAT_BEGIN_TIME = '02-29 14:02:20.123'
MOCK_ADB_LOGCAT_END_TIME = '02-29 14:02:22.000'
MOCK_SNIPPET_PACKAGE_NAME = 'com.my.snippet'

# A mock SnippetClient used for testing snippet management logic.
MockSnippetClient = mock.MagicMock()
MockSnippetClient.package = MOCK_SNIPPET_PACKAGE_NAME

# Mock AdbError for missing logpersist scripts
MOCK_LOGPERSIST_STOP_MISSING_ADB_ERROR = adb.AdbError(
    'logpersist.stop --clear', '',
    '/system/bin/sh: logpersist.stop: not found', 0)
MOCK_LOGPERSIST_START_MISSING_ADB_ERROR = adb.AdbError(
    'logpersist.start --clear', '',
    '/system/bin/sh: logpersist.stop: not found', 0)


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

    @mock.patch.object(
        android_device,
        'get_all_instances',
        new=mock_android_device.get_all_instances)
    @mock.patch.object(
        android_device,
        'list_adb_devices',
        new=mock_android_device.list_adb_devices)
    @mock.patch.object(
        android_device,
        'list_adb_devices_by_usb_id',
        new=mock_android_device.list_adb_devices)
    def test_create_with_pickup_all(self):
        pick_all_token = android_device.ANDROID_DEVICE_PICK_ALL_TOKEN
        actual_ads = android_device.create(pick_all_token)
        for actual, expected in zip(actual_ads,
                                    mock_android_device.get_mock_ads(5)):
            self.assertEqual(actual.serial, expected.serial)

    @mock.patch.object(
        android_device, 'get_instances', new=mock_android_device.get_instances)
    @mock.patch.object(
        android_device,
        'list_adb_devices',
        new=mock_android_device.list_adb_devices)
    @mock.patch.object(
        android_device,
        'list_adb_devices_by_usb_id',
        new=mock_android_device.list_adb_devices)
    def test_create_with_string_list(self):
        string_list = [u'1', '2']
        actual_ads = android_device.create(string_list)
        for actual_ad, expected_serial in zip(actual_ads, ['1', '2']):
            self.assertEqual(actual_ad.serial, expected_serial)

    @mock.patch.object(
        android_device,
        'get_instances_with_configs',
        new=mock_android_device.get_instances_with_configs)
    @mock.patch.object(
        android_device,
        'list_adb_devices',
        new=mock_android_device.list_adb_devices)
    @mock.patch.object(
        android_device,
        'list_adb_devices_by_usb_id',
        new=mock_android_device.list_adb_devices)
    def test_create_with_dict_list(self):
        string_list = [{'serial': '1'}, {'serial': '2'}]
        actual_ads = android_device.create(string_list)
        for actual_ad, expected_serial in zip(actual_ads, ['1', '2']):
            self.assertEqual(actual_ad.serial, expected_serial)

    @mock.patch.object(
        android_device,
        'get_instances_with_configs',
        new=mock_android_device.get_instances_with_configs)
    @mock.patch.object(
        android_device,
        'list_adb_devices',
        new=mock_android_device.list_adb_devices)
    @mock.patch.object(
        android_device, 'list_adb_devices_by_usb_id', return_value=['usb:1'])
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
        ad = android_device.get_device(
            ads, serial=expected_serial, h_port=expected_h_port)
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
        expected_msg = "More than one device matched: \['0', '0'\]"
        with self.assertRaisesRegex(android_device.Error, expected_msg):
            android_device.get_device(ads, serial=target_serial)

    def test_start_services_on_ads(self):
        """Makes sure when an AndroidDevice fails to start some services, all
        AndroidDevice objects get cleaned up.
        """
        msg = 'Some error happened.'
        ads = mock_android_device.get_mock_ads(3)
        ads[0].start_services = mock.MagicMock()
        ads[0].stop_services = mock.MagicMock()
        ads[1].start_services = mock.MagicMock()
        ads[1].stop_services = mock.MagicMock()
        ads[2].start_services = mock.MagicMock(
            side_effect=android_device.Error(msg))
        ads[2].stop_services = mock.MagicMock()
        with self.assertRaisesRegex(android_device.Error, msg):
            android_device._start_services_on_ads(ads)
        ads[0].stop_services.assert_called_once_with()
        ads[1].stop_services.assert_called_once_with()
        ads[2].stop_services.assert_called_once_with()

    def test_start_services_on_ads_skip_logcat(self):
        ads = mock_android_device.get_mock_ads(3)
        ads[0].start_services = mock.MagicMock()
        ads[1].start_services = mock.MagicMock()
        ads[2].start_services = mock.MagicMock(
            side_effect=Exception('Should not have called this.'))
        ads[2].skip_logcat = True
        android_device._start_services_on_ads(ads)

    # Tests for android_device.AndroidDevice class.
    # These tests mock out any interaction with the OS and real android device
    # in AndroidDeivce.

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    def test_AndroidDevice_instantiation(self, MockFastboot, MockAdbProxy):
        """Verifies the AndroidDevice object's basic attributes are correctly
        set after instantiation.
        """
        mock_serial = 1
        ad = android_device.AndroidDevice(serial=mock_serial)
        self.assertEqual(ad.serial, '1')
        self.assertEqual(ad.model, 'fakemodel')
        self.assertIsNone(ad._adb_logcat_process)
        self.assertIsNone(ad.adb_logcat_file_path)
        expected_lp = os.path.join(logging.log_path,
                                   'AndroidDevice%s' % mock_serial)
        self.assertEqual(ad.log_path, expected_lp)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    def test_AndroidDevice_build_info(self, MockFastboot, MockAdbProxy):
        """Verifies the AndroidDevice object's basic attributes are correctly
        set after instantiation.
        """
        ad = android_device.AndroidDevice(serial='1')
        build_info = ad.build_info
        self.assertEqual(build_info['build_id'], 'AB42')
        self.assertEqual(build_info['build_type'], 'userdebug')

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
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

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    def test_AndroidDevice_serial_is_valid(self, MockFastboot, MockAdbProxy):
        """Verifies that the serial is a primitive string type and serializable.
        """
        ad = android_device.AndroidDevice(serial=1)
        # In py2, checks that ad.serial is not the backported py3 str type,
        # which is not dumpable by yaml in py2.
        # In py3, new_str is equivalent to str, so this check is not
        # appropirate in py3.
        if sys.version_info < (3, 0):
            self.assertFalse(isinstance(ad.serial, new_str))
        self.assertTrue(isinstance(ad.serial, str))
        yaml.safe_dump(ad.serial)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy(1))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy(1))
    @mock.patch('mobly.utils.create_dir')
    def test_AndroidDevice_take_bug_report(self, create_dir_mock,
                                           FastbootProxy, MockAdbProxy):
        """Verifies AndroidDevice.take_bug_report calls the correct adb command
        and writes the bugreport file to the correct path.
        """
        mock_serial = '1'
        ad = android_device.AndroidDevice(serial=mock_serial)
        ad.take_bug_report('test_something', 'sometime')
        expected_path = os.path.join(
            logging.log_path, 'AndroidDevice%s' % ad.serial, 'BugReports')
        create_dir_mock.assert_called_with(expected_path)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1', fail_br=True))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
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
            ad.take_bug_report('test_something', 'sometime')

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch('mobly.utils.create_dir')
    def test_AndroidDevice_take_bug_report_with_destination(
            self, create_dir_mock, FastbootProxy, MockAdbProxy):
        mock_serial = '1'
        ad = android_device.AndroidDevice(serial=mock_serial)
        dest = tempfile.gettempdir()
        ad.take_bug_report("test_something", "sometime", destination=dest)
        expected_path = os.path.join(dest)
        create_dir_mock.assert_called_with(expected_path)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy(
            '1', fail_br_before_N=True))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch('mobly.utils.create_dir')
    def test_AndroidDevice_take_bug_report_fallback(
            self, create_dir_mock, FastbootProxy, MockAdbProxy):
        """Verifies AndroidDevice.take_bug_report falls back to traditional
        bugreport on builds that do not have bugreportz.
        """
        mock_serial = '1'
        ad = android_device.AndroidDevice(serial=mock_serial)
        ad.take_bug_report('test_something', 'sometime')
        expected_path = os.path.join(
            logging.log_path, 'AndroidDevice%s' % ad.serial, 'BugReports')
        create_dir_mock.assert_called_with(expected_path)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch('mobly.utils.create_dir')
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_AndroidDevice_take_logcat(self, stop_proc_mock, start_proc_mock,
                                       creat_dir_mock, FastbootProxy,
                                       MockAdbProxy):
        """Verifies the steps of collecting adb logcat on an AndroidDevice
        object, including various function calls and the expected behaviors of
        the calls.
        """
        mock_serial = '1'
        ad = android_device.AndroidDevice(serial=mock_serial)
        expected_msg = '.* No ongoing adb logcat collection found.'
        # Expect error if stop is called before start.
        with self.assertRaisesRegex(android_device.Error, expected_msg):
            ad.stop_adb_logcat()
        ad.start_adb_logcat()
        # Verify start did the correct operations.
        self.assertTrue(ad._adb_logcat_process)
        expected_log_path = os.path.join(logging.log_path,
                                         'AndroidDevice%s' % ad.serial,
                                         'adblog,fakemodel,%s.txt' % ad.serial)
        creat_dir_mock.assert_called_with(os.path.dirname(expected_log_path))
        adb_cmd = '"adb" -s %s logcat -v threadtime  >> %s'
        start_proc_mock.assert_called_with(
            adb_cmd % (ad.serial, '"%s"' % expected_log_path), shell=True)
        self.assertEqual(ad.adb_logcat_file_path, expected_log_path)
        expected_msg = (
            'Logcat thread is already running, cannot start another'
            ' one.')
        # Expect error if start is called back to back.
        with self.assertRaisesRegex(android_device.Error, expected_msg):
            ad.start_adb_logcat()
        # Verify stop did the correct operations.
        ad.stop_adb_logcat()
        stop_proc_mock.assert_called_with('process')
        self.assertIsNone(ad._adb_logcat_process)
        self.assertEqual(ad.adb_logcat_file_path, expected_log_path)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch('mobly.utils.create_dir')
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_AndroidDevice_take_logcat_with_user_param(
            self, stop_proc_mock, start_proc_mock, creat_dir_mock,
            FastbootProxy, MockAdbProxy):
        """Verifies the steps of collecting adb logcat on an AndroidDevice
        object, including various function calls and the expected behaviors of
        the calls.
        """
        mock_serial = '1'
        ad = android_device.AndroidDevice(serial=mock_serial)
        ad.adb_logcat_param = '-b radio'
        expected_msg = '.* No ongoing adb logcat collection found.'
        # Expect error if stop is called before start.
        with self.assertRaisesRegex(android_device.Error, expected_msg):
            ad.stop_adb_logcat()
        ad.start_adb_logcat()
        # Verify start did the correct operations.
        self.assertTrue(ad._adb_logcat_process)
        expected_log_path = os.path.join(logging.log_path,
                                         'AndroidDevice%s' % ad.serial,
                                         'adblog,fakemodel,%s.txt' % ad.serial)
        creat_dir_mock.assert_called_with(os.path.dirname(expected_log_path))
        adb_cmd = '"adb" -s %s logcat -v threadtime -b radio >> %s'
        start_proc_mock.assert_called_with(
            adb_cmd % (ad.serial, '"%s"' % expected_log_path), shell=True)
        self.assertEqual(ad.adb_logcat_file_path, expected_log_path)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_AndroidDevice_change_log_path(self, stop_proc_mock,
                                           start_proc_mock, FastbootProxy,
                                           MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        ad.start_adb_logcat()
        ad.stop_adb_logcat()
        old_path = ad.log_path
        new_log_path = tempfile.mkdtemp()
        ad.log_path = new_log_path
        self.assertTrue(os.path.exists(new_log_path))
        self.assertFalse(os.path.exists(old_path))

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_AndroidDevice_change_log_path_no_log_exists(
            self, stop_proc_mock, start_proc_mock, FastbootProxy,
            MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        old_path = ad.log_path
        new_log_path = tempfile.mkdtemp()
        ad.log_path = new_log_path
        self.assertTrue(os.path.exists(new_log_path))
        self.assertFalse(os.path.exists(old_path))

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch('mobly.utils.create_dir')
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_AndroidDevice_change_log_path_with_service(
            self, stop_proc_mock, start_proc_mock, creat_dir_mock,
            FastbootProxy, MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        ad.start_adb_logcat()
        new_log_path = tempfile.mkdtemp()
        expected_msg = '.* Cannot change `log_path` when there is service running.'
        with self.assertRaisesRegex(android_device.Error, expected_msg):
            ad.log_path = new_log_path

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch('mobly.utils.create_dir')
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_AndroidDevice_change_log_path_with_existing_file(
            self, stop_proc_mock, start_proc_mock, creat_dir_mock,
            FastbootProxy, MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        new_log_path = tempfile.mkdtemp()
        with open(os.path.join(new_log_path, 'file.txt'), 'w') as f:
            f.write('hahah.')
        expected_msg = '.* Logs already exist .*'
        with self.assertRaisesRegex(android_device.Error, expected_msg):
            ad.log_path = new_log_path

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch('mobly.utils.create_dir')
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
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

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch('mobly.utils.create_dir')
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_AndroidDevice_update_serial_with_service_running(
            self, stop_proc_mock, start_proc_mock, creat_dir_mock,
            FastbootProxy, MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        ad.start_adb_logcat()
        expected_msg = '.* Cannot change device serial number when there is service running.'
        with self.assertRaisesRegex(android_device.Error, expected_msg):
            ad.update_serial('2')

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.utils.start_standing_subprocess', return_value='process')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    @mock.patch(
        'mobly.logger.get_log_line_timestamp',
        return_value=MOCK_ADB_LOGCAT_END_TIME)
    def test_AndroidDevice_cat_adb_log(self, mock_timestamp_getter,
                                       stop_proc_mock, start_proc_mock,
                                       FastbootProxy, MockAdbProxy):
        """Verifies that AndroidDevice.cat_adb_log loads the correct adb log
        file, locates the correct adb log lines within the given time range,
        and writes the lines to the correct output file.
        """
        mock_serial = '1'
        ad = android_device.AndroidDevice(serial=mock_serial)
        # Direct the log path of the ad to a temp dir to avoid racing.
        ad._log_path_base = self.tmp_dir
        # Expect error if attempted to cat adb log before starting adb logcat.
        expected_msg = ('.* Attempting to cat adb log when none'
                        ' has been collected.')
        with self.assertRaisesRegex(android_device.Error, expected_msg):
            ad.cat_adb_log('some_test', MOCK_ADB_LOGCAT_BEGIN_TIME)
        ad.start_adb_logcat()
        utils.create_dir(ad.log_path)
        mock_adb_log_path = os.path.join(ad.log_path, 'adblog,%s,%s.txt' %
                                         (ad.model, ad.serial))
        with open(mock_adb_log_path, 'w') as f:
            f.write(MOCK_ADB_LOGCAT)
        ad.cat_adb_log('some_test', MOCK_ADB_LOGCAT_BEGIN_TIME)
        cat_file_path = os.path.join(
            ad.log_path, 'AdbLogExcerpts',
            ('some_test,02-29 14-02-20.123,%s,%s.txt') % (ad.model, ad.serial))
        with open(cat_file_path, 'r') as f:
            actual_cat = f.read()
        self.assertEqual(actual_cat, ''.join(MOCK_ADB_LOGCAT_CAT_RESULT))
        # Stops adb logcat.
        ad.stop_adb_logcat()

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock.MagicMock())
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    def test_AndroidDevice__enable_logpersist_with_logpersist(
            self, MockFastboot, MockAdbProxy):
        mock_serial = '1'
        mock_adb_proxy = MockAdbProxy.return_value
        mock_adb_proxy.getprop.return_value = 'userdebug'
        mock_adb_proxy.has_shell_command.side_effect = lambda command: {
            'logpersist.start': True,
            'logpersist.stop': True, }[command]
        ad = android_device.AndroidDevice(serial=mock_serial)
        ad._enable_logpersist()
        mock_adb_proxy.shell.assert_has_calls([
            mock.call('logpersist.stop --clear'),
            mock.call('logpersist.start'),
        ])

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock.MagicMock())
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    def test_AndroidDevice__enable_logpersist_with_missing_all_logpersist(
            self, MockFastboot, MockAdbProxy):
        def adb_shell_helper(command):
            if command == 'logpersist.start':
                raise MOCK_LOGPERSIST_START_MISSING_ADB_ERROR
            elif command == 'logpersist.stop --clear':
                raise MOCK_LOGPERSIST_STOP_MISSING_ADB_ERROR
            else:
                return ''

        mock_serial = '1'
        mock_adb_proxy = MockAdbProxy.return_value
        mock_adb_proxy.getprop.return_value = 'userdebug'
        mock_adb_proxy.has_shell_command.side_effect = lambda command: {
            'logpersist.start': False,
            'logpersist.stop': False, }[command]
        mock_adb_proxy.shell.side_effect = adb_shell_helper
        ad = android_device.AndroidDevice(serial=mock_serial)
        ad._enable_logpersist()

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock.MagicMock())
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    def test_AndroidDevice__enable_logpersist_with_missing_logpersist_stop(
            self, MockFastboot, MockAdbProxy):
        def adb_shell_helper(command):
            if command == 'logpersist.stop --clear':
                raise MOCK_LOGPERSIST_STOP_MISSING_ADB_ERROR
            else:
                return ''

        mock_serial = '1'
        mock_adb_proxy = MockAdbProxy.return_value
        mock_adb_proxy.getprop.return_value = 'userdebug'
        mock_adb_proxy.has_shell_command.side_effect = lambda command: {
            'logpersist.start': True,
            'logpersist.stop': False, }[command]
        mock_adb_proxy.shell.side_effect = adb_shell_helper
        ad = android_device.AndroidDevice(serial=mock_serial)
        ad._enable_logpersist()

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock.MagicMock())
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_AndroidDevice__enable_logpersist_with_missing_logpersist_start(
            self, MockFastboot, MockAdbProxy):
        def adb_shell_helper(command):
            if command == 'logpersist.start':
                raise MOCK_LOGPERSIST_START_MISSING_ADB_ERROR
            else:
                return ''

        mock_serial = '1'
        mock_adb_proxy = MockAdbProxy.return_value
        mock_adb_proxy.getprop.return_value = 'userdebug'
        mock_adb_proxy.has_shell_command.side_effect = lambda command: {
            'logpersist.start': False,
            'logpersist.stop': True, }[command]
        mock_adb_proxy.shell.side_effect = adb_shell_helper
        ad = android_device.AndroidDevice(serial=mock_serial)
        ad._enable_logpersist()

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient')
    @mock.patch('mobly.utils.get_available_host_port')
    def test_AndroidDevice_load_snippet(self, MockGetPort, MockSnippetClient,
                                        MockFastboot, MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
        self.assertTrue(hasattr(ad, 'snippet'))

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient')
    @mock.patch('mobly.utils.get_available_host_port')
    def test_AndroidDevice_load_snippet_failure(
            self, MockGetPort, MockSnippetClient, MockFastboot, MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        client = mock.MagicMock()
        client.start_app_and_connect.side_effect = Exception(
            'Something went wrong.')
        MockSnippetClient.return_value = client
        with self.assertRaisesRegex(Exception, 'Something went wrong.'):
            ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
        client.stop_app.assert_called_once_with()

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient')
    @mock.patch('mobly.utils.get_available_host_port')
    def test_AndroidDevice_load_snippet_precheck_failure(
            self, MockGetPort, MockSnippetClient, MockFastboot, MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        client = mock.MagicMock()
        client.start_app_and_connect.side_effect = snippet_client.AppStartPreCheckError(
            mock.MagicMock, 'Something went wrong in precheck.')
        MockSnippetClient.return_value = client
        with self.assertRaisesRegex(snippet_client.AppStartPreCheckError,
                                    'Something went wrong in precheck.'):
            ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
        client.stop_app.assert_not_called()

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient')
    @mock.patch('mobly.utils.get_available_host_port')
    def test_AndroidDevice_load_snippet_fail_cleanup_also_fail(
            self, MockGetPort, MockSnippetClient, MockFastboot, MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        client = mock.MagicMock()
        client.start_app_and_connect.side_effect = Exception(
            'Something went wrong in start app.')
        client.stop_app.side_effect = Exception('Stop app also failed.')
        MockSnippetClient.return_value = client
        with self.assertRaisesRegex(Exception,
                                    'Something went wrong in start app.'):
            ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
        client.stop_app.assert_called_once_with()

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient',
        return_value=MockSnippetClient)
    @mock.patch('mobly.utils.get_available_host_port')
    def test_AndroidDevice_load_snippet_dup_package(
            self, MockGetPort, MockSnippetClient, MockFastboot, MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
        expected_msg = ('Snippet package "%s" has already been loaded under '
                        'name "snippet".') % MOCK_SNIPPET_PACKAGE_NAME
        with self.assertRaisesRegex(android_device.Error, expected_msg):
            ad.load_snippet('snippet2', MOCK_SNIPPET_PACKAGE_NAME)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient',
        return_value=MockSnippetClient)
    @mock.patch('mobly.utils.get_available_host_port')
    def test_AndroidDevice_load_snippet_dup_snippet_name(
            self, MockGetPort, MockSnippetClient, MockFastboot, MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
        expected_msg = ('Attribute "%s" is already registered with package '
                        '"%s", it cannot be used again.') % (
                            'snippet', MOCK_SNIPPET_PACKAGE_NAME)
        with self.assertRaisesRegex(android_device.Error, expected_msg):
            ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME + 'haha')

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
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

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient')
    @mock.patch('mobly.utils.get_available_host_port')
    def test_AndroidDevice_load_snippet_start_app_fails(
            self, MockGetPort, MockSnippetClient, MockFastboot, MockAdbProxy):
        """Verifies that the correct exception is raised if start app failed.

        It's possible that the `stop_app` call as part of the start app failure
        teardown also fails. So we want the exception from the start app
        failure.
        """
        expected_e = Exception('start failed.')
        MockSnippetClient.start_app_and_connect = mock.Mock(
            side_effect=expected_e)
        MockSnippetClient.stop_app = mock.Mock(
            side_effect=Exception('stop failed.'))
        ad = android_device.AndroidDevice(serial='1')
        try:
            ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
        except Exception as e:
            assertIs(e, expected_e)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient')
    @mock.patch('mobly.utils.get_available_host_port')
    def test_AndroidDevice_snippet_cleanup(
            self, MockGetPort, MockSnippetClient, MockFastboot, MockAdbProxy):
        ad = android_device.AndroidDevice(serial='1')
        ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
        ad.stop_services()
        self.assertFalse(hasattr(ad, 'snippet'))

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy('1'))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy('1'))
    def test_AndroidDevice_debug_tag(self, MockFastboot, MockAdbProxy):
        mock_serial = '1'
        ad = android_device.AndroidDevice(serial=mock_serial)
        self.assertEqual(ad.debug_tag, '1')
        try:
            raise android_device.DeviceError(ad, 'Something')
        except android_device.DeviceError as e:
            self.assertEqual('<AndroidDevice|1> Something', str(e))
        # Verify that debug tag's setter updates the debug prefix correctly.
        ad.debug_tag = 'Mememe'
        try:
            raise android_device.DeviceError(ad, 'Something')
        except android_device.DeviceError as e:
            self.assertEqual('<AndroidDevice|Mememe> Something', str(e))
        # Verify that repr is changed correctly.
        try:
            raise Exception(ad, 'Something')
        except Exception as e:
            self.assertEqual("(<AndroidDevice|Mememe>, 'Something')", str(e))


if __name__ == '__main__':
    unittest.main()
