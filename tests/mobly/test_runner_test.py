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
import os
import shutil
import tempfile
import yaml
from future.tests.base import unittest

from mobly import config_parser
from mobly import records
from mobly import signals
from mobly import test_runner

from tests.lib import mock_android_device
from tests.lib import mock_controller
from tests.lib import integration_test
from tests.lib import integration2_test


class TestRunnerTest(unittest.TestCase):
    """This test class has unit tests for the implementation of everything
    under mobly.test_runner.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.base_mock_test_config = config_parser.TestRunConfig()
        self.base_mock_test_config.test_bed_name = 'SampleTestBed'
        self.base_mock_test_config.controller_configs = {}
        self.base_mock_test_config.user_params = {
            'icecream': 42,
            'extra_param': 'haha'
        }
        self.base_mock_test_config.log_path = self.tmp_dir
        self.log_dir = self.base_mock_test_config.log_path
        self.test_bed_name = self.base_mock_test_config.test_bed_name

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_register_controller_no_config(self):
        tr = test_runner.TestRunner(self.log_dir, self.test_bed_name)
        with self.assertRaisesRegex(signals.ControllerError,
                                    'No corresponding config found for'):
            tr._register_controller(self.base_mock_test_config,
                                    mock_controller)

    def test_register_controller_no_config_no_register(self):
        tr = test_runner.TestRunner(self.log_dir, self.test_bed_name)
        self.assertIsNone(
            tr._register_controller(
                self.base_mock_test_config, mock_controller, required=False))

    def test_register_controller_dup_register(self):
        """Verifies correctness of registration, internal tally of controllers
        objects, and the right error happen when a controller module is
        registered twice.
        """
        mock_test_config = self.base_mock_test_config.copy()
        mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
        mock_test_config.controller_configs = {
            mock_ctrlr_config_name: ['magic1', 'magic2']
        }
        tr = test_runner.TestRunner(self.log_dir, self.test_bed_name)
        tr._register_controller(mock_test_config, mock_controller)
        registered_name = 'mock_controller'
        self.assertTrue(registered_name in tr._controller_registry)
        mock_ctrlrs = tr._controller_registry[registered_name]
        self.assertEqual(mock_ctrlrs[0].magic, 'magic1')
        self.assertEqual(mock_ctrlrs[1].magic, 'magic2')
        self.assertTrue(tr._controller_destructors[registered_name])
        expected_msg = 'Controller module .* has already been registered.'
        with self.assertRaisesRegex(signals.ControllerError, expected_msg):
            tr._register_controller(mock_test_config, mock_controller)

    def test_register_controller_no_get_info(self):
        mock_test_config = self.base_mock_test_config.copy()
        mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
        get_info = getattr(mock_controller, 'get_info')
        delattr(mock_controller, 'get_info')
        try:
            mock_test_config.controller_configs = {
                mock_ctrlr_config_name: ['magic1', 'magic2']
            }
            tr = test_runner.TestRunner(self.log_dir, self.test_bed_name)
            tr._register_controller(mock_test_config, mock_controller)
            self.assertEqual(tr.results.controller_info, {})
        finally:
            setattr(mock_controller, 'get_info', get_info)

    def test_register_controller_return_value(self):
        mock_test_config = self.base_mock_test_config.copy()
        mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
        mock_test_config.controller_configs = {
            mock_ctrlr_config_name: ['magic1', 'magic2']
        }
        tr = test_runner.TestRunner(self.log_dir, self.test_bed_name)
        magic_devices = tr._register_controller(mock_test_config,
                                                mock_controller)
        self.assertEqual(magic_devices[0].magic, 'magic1')
        self.assertEqual(magic_devices[1].magic, 'magic2')

    def test_register_controller_change_return_value(self):
        mock_test_config = self.base_mock_test_config.copy()
        mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
        mock_test_config.controller_configs = {
            mock_ctrlr_config_name: ['magic1', 'magic2']
        }
        tr = test_runner.TestRunner(self.log_dir, self.test_bed_name)
        magic_devices = tr._register_controller(mock_test_config,
                                                mock_controller)
        magic1 = magic_devices.pop(0)
        self.assertIs(magic1, tr._controller_registry['mock_controller'][0])
        self.assertEqual(len(tr._controller_registry['mock_controller']), 2)

    def test_register_controller_less_than_min_number(self):
        mock_test_config = self.base_mock_test_config.copy()
        mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
        mock_test_config.controller_configs = {
            mock_ctrlr_config_name: ['magic1', 'magic2']
        }
        tr = test_runner.TestRunner(self.log_dir, self.test_bed_name)
        expected_msg = 'Expected to get at least 3 controller objects, got 2.'
        with self.assertRaisesRegex(signals.ControllerError, expected_msg):
            tr._register_controller(
                mock_test_config, mock_controller, min_number=3)

    def test_run_twice(self):
        """Verifies that:
        1. Repeated run works properly.
        2. The original configuration is not altered if a test controller
           module modifies configuration.
        """
        mock_test_config = self.base_mock_test_config.copy()
        mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
        my_config = [{
            'serial': 'xxxx',
            'magic': 'Magic1'
        }, {
            'serial': 'xxxx',
            'magic': 'Magic2'
        }]
        mock_test_config.controller_configs[mock_ctrlr_config_name] = my_config
        tr = test_runner.TestRunner(self.log_dir, self.test_bed_name)
        tr.add_test_class(mock_test_config, integration_test.IntegrationTest)
        tr.run()
        self.assertFalse(tr._controller_registry)
        self.assertFalse(tr._controller_destructors)
        self.assertTrue(
            mock_test_config.controller_configs[mock_ctrlr_config_name][0])
        tr.run()
        self.assertFalse(tr._controller_registry)
        self.assertFalse(tr._controller_destructors)
        results = tr.results.summary_dict()
        self.assertEqual(results['Requested'], 2)
        self.assertEqual(results['Executed'], 2)
        self.assertEqual(results['Passed'], 2)
        expected_info = {
            'MagicDevice': [{
                'MyMagic': {
                    'magic': 'Magic1'
                }
            }, {
                'MyMagic': {
                    'magic': 'Magic2'
                }
            }]
        }
        self.assertEqual(tr.results.controller_info, expected_info)

    def test_summary_file_entries(self):
        """Verifies the output summary's file format.

        This focuses on the format of the file instead of the content of
        entries, which is covered in base_test_test.
        """
        mock_test_config = self.base_mock_test_config.copy()
        mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
        my_config = [{
            'serial': 'xxxx',
            'magic': 'Magic1'
        }, {
            'serial': 'xxxx',
            'magic': 'Magic2'
        }]
        mock_test_config.controller_configs[mock_ctrlr_config_name] = my_config
        tr = test_runner.TestRunner(self.log_dir, self.test_bed_name)
        tr.add_test_class(mock_test_config, integration_test.IntegrationTest)
        tr.run()
        summary_path = os.path.join(mock_test_config.log_path,
                                    mock_test_config.test_bed_name, 'latest',
                                    records.OUTPUT_FILE_SUMMARY)
        with open(summary_path, 'r') as f:
            summary_entries = list(yaml.load_all(f))
        self.assertEqual(len(summary_entries), 4)
        # Verify the first entry is the list of test names.
        self.assertEqual(summary_entries[0]['Type'],
                         records.TestSummaryEntryType.TEST_NAME_LIST.value)
        self.assertEqual(summary_entries[1]['Type'],
                         records.TestSummaryEntryType.RECORD.value)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy(1))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy(1))
    @mock.patch(
        'mobly.controllers.android_device.list_adb_devices',
        return_value=['1'])
    @mock.patch(
        'mobly.controllers.android_device.get_all_instances',
        return_value=mock_android_device.get_mock_ads(1))
    def test_run_two_test_classes(self, mock_get_all, mock_list_adb,
                                  mock_fastboot, mock_adb):
        """Verifies that running more than one test class in one test run works
        properly.

        This requires using a built-in controller module. Using AndroidDevice
        module since it has all the mocks needed already.
        """
        mock_test_config = self.base_mock_test_config.copy()
        mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
        my_config = [{
            'serial': 'xxxx',
            'magic': 'Magic1'
        }, {
            'serial': 'xxxx',
            'magic': 'Magic2'
        }]
        mock_test_config.controller_configs[mock_ctrlr_config_name] = my_config
        mock_test_config.controller_configs['AndroidDevice'] = [{
            'serial': '1'
        }]
        tr = test_runner.TestRunner(self.log_dir, self.test_bed_name)
        tr.add_test_class(mock_test_config, integration2_test.Integration2Test)
        tr.add_test_class(mock_test_config, integration_test.IntegrationTest)
        tr.run()
        self.assertFalse(tr._controller_registry)
        self.assertFalse(tr._controller_destructors)
        results = tr.results.summary_dict()
        self.assertEqual(results['Requested'], 2)
        self.assertEqual(results['Executed'], 2)
        self.assertEqual(results['Passed'], 2)

    def test_run_two_test_classes_different_configs(self):
        """Verifies that running more than one test class in one test run with
        different configs works properly.
        """
        config1 = self.base_mock_test_config.copy()
        config1.controller_configs[
            mock_controller.MOBLY_CONTROLLER_CONFIG_NAME] = [{
                'serial': 'xxxx'
            }]
        config2 = config1.copy()
        config2.user_params['icecream'] = 10
        tr = test_runner.TestRunner(self.log_dir, self.test_bed_name)
        tr.add_test_class(config1, integration_test.IntegrationTest)
        tr.add_test_class(config2, integration_test.IntegrationTest)
        tr.run()
        results = tr.results.summary_dict()
        self.assertEqual(results['Requested'], 2)
        self.assertEqual(results['Executed'], 2)
        self.assertEqual(results['Passed'], 1)
        self.assertEqual(results['Failed'], 1)
        self.assertEqual(tr.results.failed[0].details, '10 != 42')

    def test_add_test_class_mismatched_log_path(self):
        tr = test_runner.TestRunner('/different/log/dir', self.test_bed_name)
        with self.assertRaisesRegex(
                test_runner.Error,
                'TestRunner\'s log folder is "/different/log/dir", but a test '
                r'config with a different log folder \("%s"\) was added.' %
                self.log_dir):
            tr.add_test_class(self.base_mock_test_config,
                              integration_test.IntegrationTest)

    def test_add_test_class_mismatched_test_bed_name(self):
        tr = test_runner.TestRunner(self.log_dir, 'different_test_bed')
        with self.assertRaisesRegex(
                test_runner.Error,
                'TestRunner\'s test bed is "different_test_bed", but a test '
                r'config with a different test bed \("%s"\) was added.' %
                self.test_bed_name):
            tr.add_test_class(self.base_mock_test_config,
                              integration_test.IntegrationTest)

    def test_run_no_tests(self):
        tr = test_runner.TestRunner(self.log_dir, self.test_bed_name)
        with self.assertRaisesRegex(test_runner.Error, 'No tests to execute.'):
            tr.run()

    def test_verify_controller_module(self):
        test_runner.verify_controller_module(mock_controller)

    def test_verify_controller_module_null_attr(self):
        try:
            tmp = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
            mock_controller.MOBLY_CONTROLLER_CONFIG_NAME = None
            msg = 'Controller interface .* in .* cannot be null.'
            with self.assertRaisesRegex(signals.ControllerError, msg):
                test_runner.verify_controller_module(mock_controller)
        finally:
            mock_controller.MOBLY_CONTROLLER_CONFIG_NAME = tmp

    def test_verify_controller_module_missing_attr(self):
        try:
            tmp = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
            delattr(mock_controller, 'MOBLY_CONTROLLER_CONFIG_NAME')
            msg = 'Module .* missing required controller module attribute'
            with self.assertRaisesRegex(signals.ControllerError, msg):
                test_runner.verify_controller_module(mock_controller)
        finally:
            setattr(mock_controller, 'MOBLY_CONTROLLER_CONFIG_NAME', tmp)

    @mock.patch(
        'mobly.test_runner._find_test_class',
        return_value=type('SampleTest', (), {}))
    @mock.patch(
        'mobly.test_runner.config_parser.load_test_config_file',
        return_value=[config_parser.TestRunConfig()])
    @mock.patch('mobly.test_runner.TestRunner', return_value=mock.MagicMock())
    def test_main_parse_args(self, mock_test_runner, mock_config,
                             mock_find_test):
        test_runner.main(['-c', 'some/path/foo.yaml', '-b', 'hello'])
        mock_config.assert_called_with('some/path/foo.yaml', None)


if __name__ == "__main__":
    unittest.main()
