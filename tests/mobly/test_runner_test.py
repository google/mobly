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

import mock
import shutil
import tempfile
import unittest

from mobly import keys
from mobly import signals
from mobly import test_runner

from tests.lib import mock_android_device
from tests.lib import mock_controller
from tests.lib import IntegrationTest


class Integration2Test(IntegrationTest.IntegrationTest):
    """Same as the IntegrationTest class, created this so we have two
    'different' test classes to use in unit tests.
    """


class TestRunnerTest(unittest.TestCase):
    """This test class has unit tests for the implementation of everything
    under mobly.test_runner.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.base_mock_test_config = {
            "testbed": {
                "name": "SampleTestBed",
            },
            "logpath": self.tmp_dir,
            "cli_args": None,
            "testpaths": ["./"],
            "icecream": 42,
            "extra_param": "haha"
        }
        self.mock_run_list = [('SampleTest', None)]

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_register_controller_no_config(self):
        tr = test_runner.TestRunner(self.base_mock_test_config,
                                    self.mock_run_list)
        with self.assertRaisesRegexp(signals.ControllerError,
                                     "No corresponding config found for"):
            tr.register_controller(mock_controller)

    def test_register_controller_no_config(self):
        tr = test_runner.TestRunner(self.base_mock_test_config,
                                    self.mock_run_list)
        self.assertIsNone(tr.register_controller(mock_controller,
                                                 required=False))

    def test_register_controller_dup_register(self):
        """Verifies correctness of registration, internal tally of controllers
        objects, and the right error happen when a controller module is
        registered twice.
        """
        mock_test_config = dict(self.base_mock_test_config)
        tb_key = keys.Config.key_testbed.value
        mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
        mock_test_config[tb_key][mock_ctrlr_config_name] = ["magic1", "magic2"]
        tr = test_runner.TestRunner(mock_test_config, self.mock_run_list)
        tr.register_controller(mock_controller)
        registered_name = "mock_controller"
        self.assertTrue(registered_name in tr.controller_registry)
        mock_ctrlrs = tr.controller_registry[registered_name]
        self.assertEqual(mock_ctrlrs[0].magic, "magic1")
        self.assertEqual(mock_ctrlrs[1].magic, "magic2")
        self.assertTrue(tr.controller_destructors[registered_name])
        expected_msg = "Controller module .* has already been registered."
        with self.assertRaisesRegexp(signals.ControllerError, expected_msg):
            tr.register_controller(mock_controller)

    def test_register_controller_no_get_info(self):
        mock_test_config = dict(self.base_mock_test_config)
        tb_key = keys.Config.key_testbed.value
        mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
        mock_ref_name = "haha"
        get_info = getattr(mock_controller, "get_info")
        delattr(mock_controller, "get_info")
        try:
            mock_test_config[tb_key][mock_ctrlr_config_name] = ["magic1",
                                                                "magic2"]
            tr = test_runner.TestRunner(mock_test_config, self.mock_run_list)
            tr.register_controller(mock_controller)
            self.assertEqual(tr.results.controller_info, {})
        finally:
            setattr(mock_controller, "get_info", get_info)

    def test_register_controller_return_value(self):
        mock_test_config = dict(self.base_mock_test_config)
        tb_key = keys.Config.key_testbed.value
        mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
        mock_test_config[tb_key][mock_ctrlr_config_name] = ["magic1", "magic2"]
        tr = test_runner.TestRunner(mock_test_config, self.mock_run_list)
        magic_devices = tr.register_controller(mock_controller)
        self.assertEqual(magic_devices[0].magic, "magic1")
        self.assertEqual(magic_devices[1].magic, "magic2")

    def test_register_controller_less_than_min_number(self):
        mock_test_config = dict(self.base_mock_test_config)
        tb_key = keys.Config.key_testbed.value
        mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
        mock_test_config[tb_key][mock_ctrlr_config_name] = ["magic1", "magic2"]
        tr = test_runner.TestRunner(mock_test_config, self.mock_run_list)
        expected_msg = "Expected to get at least 3 controller objects, got 2."
        with self.assertRaisesRegexp(signals.ControllerError, expected_msg):
            tr.register_controller(mock_controller, min_number=3)

    def test_run_twice(self):
        """Verifies that:
        1. Repeated run works properly.
        2. The original configuration is not altered if a test controller
           module modifies configuration.
        """
        mock_test_config = dict(self.base_mock_test_config)
        tb_key = keys.Config.key_testbed.value
        mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
        my_config = [{"serial": "xxxx",
                      "magic": "Magic1"}, {"serial": "xxxx",
                                           "magic": "Magic2"}]
        mock_test_config[tb_key][mock_ctrlr_config_name] = my_config
        tr = test_runner.TestRunner(mock_test_config, [('IntegrationTest',
                                                        None)])
        tr.run([IntegrationTest.IntegrationTest])
        self.assertFalse(tr.controller_registry)
        self.assertFalse(tr.controller_destructors)
        self.assertTrue(mock_test_config[tb_key][mock_ctrlr_config_name][0])
        tr.run([IntegrationTest.IntegrationTest])
        tr.stop()
        self.assertFalse(tr.controller_registry)
        self.assertFalse(tr.controller_destructors)
        results = tr.results.summary_dict()
        self.assertEqual(results["Requested"], 2)
        self.assertEqual(results["Executed"], 2)
        self.assertEqual(results["Passed"], 2)
        expected_info = {'MagicDevice': [{'MyMagic': {'magic': 'Magic1'}},
                                         {'MyMagic': {'magic': 'Magic2'}}]}
        self.assertEqual(tr.results.controller_info, expected_info)

    @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
                return_value=mock_android_device.MockAdbProxy(1))
    @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
                return_value=mock_android_device.MockFastbootProxy(1))
    @mock.patch('mobly.controllers.android_device.list_adb_devices',
                return_value=["1"])
    @mock.patch('mobly.controllers.android_device.get_all_instances',
                return_value=mock_android_device.get_mock_ads(1))
    def test_run_two_test_classes(self, mock_get_all, mock_list_adb,
                                  mock_fastboot, mock_adb,):
        """Verifies that runing more than one test class in one test run works
        proerly.

        This requires using a built-in controller module. Using AndroidDevice
        module since it has all the mocks needed already.
        """
        mock_test_config = dict(self.base_mock_test_config)
        tb_key = keys.Config.key_testbed.value
        mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
        my_config = [{"serial": "xxxx", "magic": "Magic1"},
                     {"serial": "xxxx", "magic": "Magic2"}]
        mock_test_config[tb_key][mock_ctrlr_config_name] = my_config
        mock_test_config[tb_key]["AndroidDevice"] = [
            {"serial": "1",
             "skip_sl4a": True}
        ]
        tr = test_runner.TestRunner(mock_test_config,
                                    [('Integration2Test', None),
                                     ('IntegrationTest', None)])
        tr.run([IntegrationTest.IntegrationTest,
                Integration2Test])
        tr.stop()
        self.assertFalse(tr.controller_registry)
        self.assertFalse(tr.controller_destructors)
        results = tr.results.summary_dict()
        self.assertEqual(results["Requested"], 2)
        self.assertEqual(results["Executed"], 2)
        self.assertEqual(results["Passed"], 2)

    def test_verify_controller_module(self):
        test_runner.TestRunner.verify_controller_module(mock_controller)

    def test_verify_controller_module_null_attr(self):
        try:
            tmp = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
            mock_controller.MOBLY_CONTROLLER_CONFIG_NAME = None
            msg = "Controller interface .* in .* cannot be null."
            with self.assertRaisesRegexp(signals.ControllerError, msg):
                test_runner.TestRunner.verify_controller_module(
                    mock_controller)
        finally:
            mock_controller.MOBLY_CONTROLLER_CONFIG_NAME = tmp

    def test_verify_controller_module_missing_attr(self):
        try:
            tmp = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
            delattr(mock_controller, "MOBLY_CONTROLLER_CONFIG_NAME")
            msg = "Module .* missing required controller module attribute"
            with self.assertRaisesRegexp(signals.ControllerError, msg):
                test_runner.TestRunner.verify_controller_module(
                    mock_controller)
        finally:
            setattr(mock_controller, "MOBLY_CONTROLLER_CONFIG_NAME", tmp)


if __name__ == "__main__":
    unittest.main()
