#!/usr/bin/env python3.4
#
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

import logging
import mock
import os
import shutil
import tempfile
import unittest

from mobly.controllers import android_device

from tests.lib import mock_android_device

# Mock log path for a test run.
MOCK_LOG_PATH = "/tmp/logs/MockTest/xx-xx-xx_xx-xx-xx/"
# The expected result of the cat adb operation.
MOCK_ADB_LOGCAT_CAT_RESULT = [
    "02-29 14:02:21.456  4454  Something\n",
    "02-29 14:02:21.789  4454  Something again\n"
]
# A mockd piece of adb logcat output.
MOCK_ADB_LOGCAT = ("02-29 14:02:19.123  4454  Nothing\n"
                   "%s"
                   "02-29 14:02:22.123  4454  Something again and again\n"
                   ) % ''.join(MOCK_ADB_LOGCAT_CAT_RESULT)
# Mock start and end time of the adb cat.
MOCK_ADB_LOGCAT_BEGIN_TIME = "02-29 14:02:20.123"
MOCK_ADB_LOGCAT_END_TIME = "02-29 14:02:22.000"
MOCK_SNIPPET_PACKAGE_NAME = "com.my.snippet"

# A mock SnippetClient used for testing snippet management logic.
MockSnippetClient = mock.MagicMock()
MockSnippetClient.package = MOCK_SNIPPET_PACKAGE_NAME


class AndroidDeviceTest(unittest.TestCase):
    """This test class has unit tests for the implementation of everything
    under mobly.controllers.android_device.
    """

    def setUp(self):
        # Set log_path to logging since mobly logger setup is not called.
        if not hasattr(logging, "log_path"):
            setattr(logging, "log_path", "/tmp/logs")
        # Creates a temp dir to be used by tests in this test class.
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Removes the temp dir.
        """
        shutil.rmtree(self.tmp_dir)

    # Tests for android_device module functions.
    # These tests use mock AndroidDevice instances.

    @mock.patch.object(android_device,
                       "get_all_instances",
                       new=mock_android_device.get_all_instances)
    @mock.patch.object(android_device,
                       "list_adb_devices",
                       new=mock_android_device.list_adb_devices)
    def test_create_with_pickup_all(self):
        pick_all_token = android_device.ANDROID_DEVICE_PICK_ALL_TOKEN
        actual_ads = android_device.create(pick_all_token)
        for actual, expected in zip(actual_ads, mock_android_device.get_mock_ads(5)):
            self.assertEqual(actual.serial, expected.serial)

    def test_create_with_empty_config(self):
        expected_msg = android_device.ANDROID_DEVICE_EMPTY_CONFIG_MSG
        with self.assertRaisesRegexp(android_device.Error,
                                     expected_msg):
            android_device.create([])

    def test_create_with_not_list_config(self):
        expected_msg = android_device.ANDROID_DEVICE_NOT_LIST_CONFIG_MSG
        with self.assertRaisesRegexp(android_device.Error,
                                     expected_msg):
            android_device.create("HAHA")

    def test_get_device_success_with_serial(self):
        ads = mock_android_device.get_mock_ads(5)
        expected_serial = 0
        ad = android_device.get_device(ads, serial=expected_serial)
        self.assertEqual(ad.serial, expected_serial)

    def test_get_device_success_with_serial_and_extra_field(self):
        ads = mock_android_device.get_mock_ads(5)
        expected_serial = 1
        expected_h_port = 5555
        ads[1].h_port = expected_h_port
        ad = android_device.get_device(ads,
                                       serial=expected_serial,
                                       h_port=expected_h_port)
        self.assertEqual(ad.serial, expected_serial)
        self.assertEqual(ad.h_port, expected_h_port)

    def test_get_device_no_match(self):
        ads = mock_android_device.get_mock_ads(5)
        expected_msg = ("Could not find a target device that matches condition"
                        ": {'serial': 5}.")
        with self.assertRaisesRegexp(android_device.Error,
                                     expected_msg):
            ad = android_device.get_device(ads, serial=len(ads))

    def test_get_device_too_many_matches(self):
        ads = mock_android_device.get_mock_ads(5)
        target_serial = ads[1].serial = ads[0].serial
        expected_msg = "More than one device matched: \[0, 0\]"
        with self.assertRaisesRegexp(android_device.Error,
                                     expected_msg):
            android_device.get_device(ads, serial=target_serial)

    def test_start_services_on_ads(self):
        """Makes sure when an AndroidDevice fails to start some services, all
        AndroidDevice objects get cleaned up.
        """
        msg = "Some error happened."
        ads = mock_android_device.get_mock_ads(3)
        ads[0].start_services = mock.MagicMock()
        ads[0].stop_services = mock.MagicMock()
        ads[1].start_services = mock.MagicMock()
        ads[1].stop_services = mock.MagicMock()
        ads[2].start_services = mock.MagicMock(
            side_effect=android_device.Error(msg))
        ads[2].stop_services = mock.MagicMock()
        with self.assertRaisesRegexp(android_device.Error, msg):
            android_device._start_services_on_ads(ads)
        ads[0].stop_services.assert_called_once_with()
        ads[1].stop_services.assert_called_once_with()
        ads[2].stop_services.assert_called_once_with()

    # Tests for android_device.AndroidDevice class.
    # These tests mock out any interaction with the OS and real android device
    # in AndroidDeivce.

    @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy', return_value=mock_android_device.MockAdbProxy(1))
    @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
                return_value=mock_android_device.MockFastbootProxy(1))
    def test_AndroidDevice_instantiation(self, MockFastboot, MockAdbProxy):
        """Verifies the AndroidDevice object's basic attributes are correctly
        set after instantiation.
        """
        mock_serial = 1
        ad = android_device.AndroidDevice(serial=mock_serial)
        self.assertEqual(ad.serial, 1)
        self.assertEqual(ad.model, "fakemodel")
        self.assertIsNone(ad._adb_logcat_process)
        self.assertIsNone(ad.adb_logcat_file_path)
        expected_lp = os.path.join(logging.log_path,
                                   "AndroidDevice%s" % mock_serial)
        self.assertEqual(ad.log_path, expected_lp)

    @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy', return_value=mock_android_device.MockAdbProxy(1))
    @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
                return_value=mock_android_device.MockFastbootProxy(1))
    def test_AndroidDevice_build_info(self, MockFastboot, MockAdbProxy):
        """Verifies the AndroidDevice object's basic attributes are correctly
        set after instantiation.
        """
        ad = android_device.AndroidDevice(serial=1)
        build_info = ad.build_info
        self.assertEqual(build_info["build_id"], "AB42")
        self.assertEqual(build_info["build_type"], "userdebug")

    @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy', return_value=mock_android_device.MockAdbProxy(1))
    @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
                return_value=mock_android_device.MockFastbootProxy(1))
    @mock.patch('mobly.utils.create_dir')
    @mock.patch('mobly.utils.exe_cmd')
    def test_AndroidDevice_take_bug_report(self, exe_mock, create_dir_mock,
                                           FastbootProxy, MockAdbProxy):
        """Verifies AndroidDevice.take_bug_report calls the correct adb command
        and writes the bugreport file to the correct path.
        """
        mock_serial = 1
        ad = android_device.AndroidDevice(serial=mock_serial)
        ad.take_bug_report("test_something", "sometime")
        expected_path = os.path.join(logging.log_path, "AndroidDevice%s" %
                                     ad.serial, "BugReports")
        create_dir_mock.assert_called_with(expected_path)

    @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
                return_value=mock_android_device.MockAdbProxy(1, fail_br=True))
    @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
                return_value=mock_android_device.MockFastbootProxy(1))
    @mock.patch('mobly.utils.create_dir')
    @mock.patch('mobly.utils.exe_cmd')
    def test_AndroidDevice_take_bug_report_fail(self, exe_mock, create_dir_mock,
                                                FastbootProxy, MockAdbProxy):
        """Verifies AndroidDevice.take_bug_report writes out the correct message
        when taking bugreport fails.
        """
        mock_serial = 1
        ad = android_device.AndroidDevice(serial=mock_serial)
        expected_msg = "Failed to take bugreport on 1: OMG I died!"
        with self.assertRaisesRegexp(android_device.Error,
                                     expected_msg):
            ad.take_bug_report("test_something", "sometime")

    @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
                return_value=mock_android_device.MockAdbProxy(1, fail_br_before_N=True))
    @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
                return_value=mock_android_device.MockFastbootProxy(1))
    @mock.patch('mobly.utils.create_dir')
    @mock.patch('mobly.utils.exe_cmd')
    def test_AndroidDevice_take_bug_report_fallback(self, exe_mock,
        create_dir_mock, FastbootProxy, MockAdbProxy):
        """Verifies AndroidDevice.take_bug_report falls back to traditional
        bugreport on builds that do not have bugreportz.
        """
        mock_serial = 1
        ad = android_device.AndroidDevice(serial=mock_serial)
        ad.take_bug_report("test_something", "sometime")
        expected_path = os.path.join(logging.log_path, "AndroidDevice%s" %
                                     ad.serial, "BugReports")
        create_dir_mock.assert_called_with(expected_path)

    @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy', return_value=mock_android_device.MockAdbProxy(1))
    @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
                return_value=mock_android_device.MockFastbootProxy(1))
    @mock.patch('mobly.utils.create_dir')
    @mock.patch('mobly.utils.start_standing_subprocess', return_value="process")
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_AndroidDevice_take_logcat(self, stop_proc_mock, start_proc_mock,
                                       creat_dir_mock, FastbootProxy,
                                       MockAdbProxy):
        """Verifies the steps of collecting adb logcat on an AndroidDevice
        object, including various function calls and the expected behaviors of
        the calls.
        """
        mock_serial = 1
        ad = android_device.AndroidDevice(serial=mock_serial)
        expected_msg = ("Android device .* does not have an ongoing adb logcat"
                        " collection.")
        # Expect error if stop is called before start.
        with self.assertRaisesRegexp(android_device.Error,
                                     expected_msg):
            ad.stop_adb_logcat()
        ad.start_adb_logcat()
        # Verify start did the correct operations.
        self.assertTrue(ad._adb_logcat_process)
        expected_log_path = os.path.join(logging.log_path,
                                         "AndroidDevice%s" % ad.serial,
                                         "adblog,fakemodel,%s.txt" % ad.serial)
        creat_dir_mock.assert_called_with(os.path.dirname(expected_log_path))
        adb_cmd = 'adb -s %s logcat -v threadtime -b all >> %s'
        start_proc_mock.assert_called_with(adb_cmd % (ad.serial,
                                                      expected_log_path))
        self.assertEqual(ad.adb_logcat_file_path, expected_log_path)
        expected_msg = ("Android device .* already has an adb logcat thread "
                        "going on. Cannot start another one.")
        # Expect error if start is called back to back.
        with self.assertRaisesRegexp(android_device.Error,
                                     expected_msg):
            ad.start_adb_logcat()
        # Verify stop did the correct operations.
        ad.stop_adb_logcat()
        stop_proc_mock.assert_called_with("process")
        self.assertIsNone(ad._adb_logcat_process)
        self.assertEqual(ad.adb_logcat_file_path, expected_log_path)

    @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy', return_value=mock_android_device.MockAdbProxy(1))
    @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
                return_value=mock_android_device.MockFastbootProxy(1))
    @mock.patch('mobly.utils.create_dir')
    @mock.patch('mobly.utils.start_standing_subprocess', return_value="process")
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_AndroidDevice_take_logcat_with_user_param(
            self, stop_proc_mock, start_proc_mock, creat_dir_mock,
            FastbootProxy, MockAdbProxy):
        """Verifies the steps of collecting adb logcat on an AndroidDevice
        object, including various function calls and the expected behaviors of
        the calls.
        """
        mock_serial = 1
        ad = android_device.AndroidDevice(serial=mock_serial)
        ad.adb_logcat_param = "-b radio"
        expected_msg = ("Android device .* does not have an ongoing adb logcat"
                        " collection.")
        # Expect error if stop is called before start.
        with self.assertRaisesRegexp(android_device.Error,
                                     expected_msg):
            ad.stop_adb_logcat()
        ad.start_adb_logcat()
        # Verify start did the correct operations.
        self.assertTrue(ad._adb_logcat_process)
        expected_log_path = os.path.join(logging.log_path,
                                         "AndroidDevice%s" % ad.serial,
                                         "adblog,fakemodel,%s.txt" % ad.serial)
        creat_dir_mock.assert_called_with(os.path.dirname(expected_log_path))
        adb_cmd = 'adb -s %s logcat -v threadtime -b radio >> %s'
        start_proc_mock.assert_called_with(adb_cmd % (ad.serial,
                                                      expected_log_path))
        self.assertEqual(ad.adb_logcat_file_path, expected_log_path)

    @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy', return_value=mock_android_device.MockAdbProxy(1))
    @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
                return_value=mock_android_device.MockFastbootProxy(1))
    @mock.patch('mobly.utils.start_standing_subprocess', return_value="process")
    @mock.patch('mobly.utils.stop_standing_subprocess')
    @mock.patch('mobly.logger.get_log_line_timestamp',
                return_value=MOCK_ADB_LOGCAT_END_TIME)
    def test_AndroidDevice_cat_adb_log(self, mock_timestamp_getter,
                                       stop_proc_mock, start_proc_mock,
                                       FastbootProxy, MockAdbProxy):
        """Verifies that AndroidDevice.cat_adb_log loads the correct adb log
        file, locates the correct adb log lines within the given time range,
        and writes the lines to the correct output file.
        """
        mock_serial = 1
        ad = android_device.AndroidDevice(serial=mock_serial)
        # Expect error if attempted to cat adb log before starting adb logcat.
        expected_msg = ("Attempting to cat adb log when none has been "
                        "collected on Android device .*")
        with self.assertRaisesRegexp(android_device.Error,
                                     expected_msg):
            ad.cat_adb_log("some_test", MOCK_ADB_LOGCAT_BEGIN_TIME)
        ad.start_adb_logcat()
        # Direct the log path of the ad to a temp dir to avoid racing.
        ad.log_path = os.path.join(self.tmp_dir, ad.log_path)
        mock_adb_log_path = os.path.join(ad.log_path, "adblog,%s,%s.txt" %
                                         (ad.model, ad.serial))
        with open(mock_adb_log_path, 'w') as f:
            f.write(MOCK_ADB_LOGCAT)
        ad.cat_adb_log("some_test", MOCK_ADB_LOGCAT_BEGIN_TIME)
        cat_file_path = os.path.join(ad.log_path, "AdbLogExcerpts", (
            "some_test,02-29 14:02:20.123,%s,%s.txt") % (ad.model, ad.serial))
        with open(cat_file_path, 'r') as f:
            actual_cat = f.read()
        self.assertEqual(actual_cat, ''.join(MOCK_ADB_LOGCAT_CAT_RESULT))
        # Stops adb logcat.
        ad.stop_adb_logcat()

    @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
                return_value=mock_android_device.MockAdbProxy(1))
    @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
                return_value=mock_android_device.MockFastbootProxy(1))
    @mock.patch('mobly.controllers.android_device_lib.snippet_client.SnippetClient')
    @mock.patch('mobly.utils.get_available_host_port')
    def test_AndroidDevice_load_snippet(
        self, MockGetPort, MockSnippetClient, MockFastboot, MockAdbProxy):
        ad = android_device.AndroidDevice(serial=1)
        ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
        self.assertTrue(hasattr(ad, 'snippet'))

    @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
                return_value=mock_android_device.MockAdbProxy(1))
    @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
                return_value=mock_android_device.MockFastbootProxy(1))
    @mock.patch('mobly.controllers.android_device_lib.snippet_client.SnippetClient',
                return_value=MockSnippetClient)
    @mock.patch('mobly.utils.get_available_host_port')
    def test_AndroidDevice_load_snippet_dup_package(
        self, MockGetPort, MockSnippetClient, MockFastboot, MockAdbProxy):
        ad = android_device.AndroidDevice(serial=1)
        ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
        expected_msg = ('Snippet package "%s" has already been loaded under '
                        'name "snippet".') % MOCK_SNIPPET_PACKAGE_NAME
        with self.assertRaisesRegexp(android_device.SnippetError,
                                     expected_msg):
            ad.load_snippet('snippet2', MOCK_SNIPPET_PACKAGE_NAME)

    @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
                return_value=mock_android_device.MockAdbProxy(1))
    @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
                return_value=mock_android_device.MockFastbootProxy(1))
    @mock.patch('mobly.controllers.android_device_lib.snippet_client.SnippetClient',
                return_value=MockSnippetClient)
    @mock.patch('mobly.utils.get_available_host_port')
    def test_AndroidDevice_load_snippet_dup_snippet_name(
        self, MockGetPort, MockSnippetClient, MockFastboot, MockAdbProxy):
        ad = android_device.AndroidDevice(serial=1)
        ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
        expected_msg = ('Attribute "%s" is already registered with package '
                        '"%s", it cannot be used again.') % (
                        'snippet', MOCK_SNIPPET_PACKAGE_NAME)
        with self.assertRaisesRegexp(android_device.SnippetError,
                                     expected_msg):
            ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME + 'haha')

    @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
                return_value=mock_android_device.MockAdbProxy(1))
    @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
                return_value=mock_android_device.MockFastbootProxy(1))
    @mock.patch('mobly.controllers.android_device_lib.snippet_client.SnippetClient')
    @mock.patch('mobly.utils.get_available_host_port')
    def test_AndroidDevice_load_snippet_dup_attribute_name(
        self, MockGetPort, MockSnippetClient, MockFastboot, MockAdbProxy):
        ad = android_device.AndroidDevice(serial=1)
        expected_msg = ('Attribute "%s" already exists, please use a different'
                        ' name') % 'adb'
        with self.assertRaisesRegexp(android_device.SnippetError,
                                     expected_msg):
            ad.load_snippet('adb', MOCK_SNIPPET_PACKAGE_NAME)

    @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
                return_value=mock_android_device.MockAdbProxy(1))
    @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
                return_value=mock_android_device.MockFastbootProxy(1))
    @mock.patch('mobly.controllers.android_device_lib.snippet_client.SnippetClient')
    @mock.patch('mobly.utils.get_available_host_port')
    def test_AndroidDevice_snippet_cleanup(self, MockGetPort, MockSnippetClient,
                                           MockFastboot, MockAdbProxy):
        ad = android_device.AndroidDevice(serial=1)
        ad.load_snippet('snippet', MOCK_SNIPPET_PACKAGE_NAME)
        ad.stop_services()
        self.assertFalse(hasattr(ad, 'snippet'))


if __name__ == "__main__":
    unittest.main()
