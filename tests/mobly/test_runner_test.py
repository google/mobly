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

import io
import logging
import mock
import os
import re
import shutil
import tempfile
import unittest
import yaml

from mobly import config_parser
from mobly import records
from mobly import signals
from mobly import test_runner

from tests.lib import mock_android_device
from tests.lib import mock_controller
from tests.lib import integration_test
from tests.lib import integration2_test
from tests.lib import integration3_test
from tests.lib import multiple_subclasses_module


class TestRunnerTest(unittest.TestCase):
  """This test class has unit tests for the implementation of everything
  under mobly.test_runner.
  """

  def setUp(self):
    self.tmp_dir = tempfile.mkdtemp()
    self.base_mock_test_config = config_parser.TestRunConfig()
    self.base_mock_test_config.testbed_name = 'SampleTestBed'
    self.base_mock_test_config.controller_configs = {}
    self.base_mock_test_config.user_params = {
        'icecream': 42,
        'extra_param': 'haha'
    }
    self.base_mock_test_config.log_path = self.tmp_dir
    self.log_dir = self.base_mock_test_config.log_path
    self.testbed_name = self.base_mock_test_config.testbed_name

  def tearDown(self):
    shutil.rmtree(self.tmp_dir)

  def _assertControllerInfoEqual(self, info, expected_info_dict):
    self.assertEqual(expected_info_dict['Controller Name'],
                     info.controller_name)
    self.assertEqual(expected_info_dict['Test Class'], info.test_class)
    self.assertEqual(expected_info_dict['Controller Info'],
                     info.controller_info)

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
    tr = test_runner.TestRunner(self.log_dir, self.testbed_name)
    with tr.mobly_logger():
      tr.add_test_class(mock_test_config, integration_test.IntegrationTest)
      tr.run()
    self.assertTrue(
        mock_test_config.controller_configs[mock_ctrlr_config_name][0])
    with tr.mobly_logger():
      tr.run()
    results = tr.results.summary_dict()
    self.assertEqual(results['Requested'], 2)
    self.assertEqual(results['Executed'], 2)
    self.assertEqual(results['Passed'], 2)
    expected_info_dict = {
        'Controller Info': [{
            'MyMagic': {
                'magic': 'Magic1'
            }
        }, {
            'MyMagic': {
                'magic': 'Magic2'
            }
        }],
        'Controller Name': 'MagicDevice',
        'Test Class': 'IntegrationTest',
    }
    self._assertControllerInfoEqual(tr.results.controller_info[0],
                                    expected_info_dict)
    self._assertControllerInfoEqual(tr.results.controller_info[1],
                                    expected_info_dict)
    self.assertNotEqual(tr.results.controller_info[0],
                        tr.results.controller_info[1])

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
    tr = test_runner.TestRunner(self.log_dir, self.testbed_name)
    with tr.mobly_logger():
      tr.add_test_class(mock_test_config, integration_test.IntegrationTest)
      tr.run()
    summary_path = os.path.join(logging.root_output_path,
                                records.OUTPUT_FILE_SUMMARY)
    with io.open(summary_path, 'r', encoding='utf-8') as f:
      summary_entries = list(yaml.safe_load_all(f))
    self.assertEqual(len(summary_entries), 4)
    # Verify the first entry is the list of test names.
    self.assertEqual(summary_entries[0]['Type'],
                     records.TestSummaryEntryType.TEST_NAME_LIST.value)
    self.assertEqual(summary_entries[1]['Type'],
                     records.TestSummaryEntryType.RECORD.value)
    self.assertEqual(summary_entries[2]['Type'],
                     records.TestSummaryEntryType.CONTROLLER_INFO.value)
    self.assertEqual(summary_entries[3]['Type'],
                     records.TestSummaryEntryType.SUMMARY.value)

  def test_run(self):
    tr = test_runner.TestRunner(self.log_dir, self.testbed_name)
    self.base_mock_test_config.controller_configs[
        mock_controller.MOBLY_CONTROLLER_CONFIG_NAME] = '*'
    with tr.mobly_logger():
      tr.add_test_class(self.base_mock_test_config,
                        integration_test.IntegrationTest)
      tr.run()
    results = tr.results.summary_dict()
    self.assertEqual(results['Requested'], 1)
    self.assertEqual(results['Executed'], 1)
    self.assertEqual(results['Passed'], 1)
    self.assertEqual(len(tr.results.executed), 1)
    record = tr.results.executed[0]
    self.assertEqual(record.test_class, 'IntegrationTest')

  def test_run_without_mobly_logger_context(self):
    tr = test_runner.TestRunner(self.log_dir, self.testbed_name)
    self.base_mock_test_config.controller_configs[
        mock_controller.MOBLY_CONTROLLER_CONFIG_NAME] = '*'
    tr.add_test_class(self.base_mock_test_config,
                      integration_test.IntegrationTest)
    tr.run()
    results = tr.results.summary_dict()
    self.assertEqual(results['Requested'], 1)
    self.assertEqual(results['Executed'], 1)
    self.assertEqual(results['Passed'], 1)
    self.assertEqual(len(tr.results.executed), 1)
    record = tr.results.executed[0]
    self.assertEqual(record.test_class, 'IntegrationTest')

  @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy',
              return_value=mock_android_device.MockAdbProxy(1))
  @mock.patch('mobly.controllers.android_device_lib.fastboot.FastbootProxy',
              return_value=mock_android_device.MockFastbootProxy(1))
  @mock.patch('mobly.controllers.android_device.list_adb_devices',
              return_value=['1'])
  @mock.patch('mobly.controllers.android_device.get_all_instances',
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
    mock_test_config.controller_configs['AndroidDevice'] = [{'serial': '1'}]
    tr = test_runner.TestRunner(self.log_dir, self.testbed_name)
    with tr.mobly_logger():
      tr.add_test_class(mock_test_config, integration2_test.Integration2Test)
      tr.add_test_class(mock_test_config, integration_test.IntegrationTest)
      tr.run()
    results = tr.results.summary_dict()
    self.assertEqual(results['Requested'], 2)
    self.assertEqual(results['Executed'], 2)
    self.assertEqual(results['Passed'], 2)
    self.assertEqual(len(tr.results.executed), 2)
    # Tag of the test class defaults to the class name.
    record1 = tr.results.executed[0]
    record2 = tr.results.executed[1]
    self.assertEqual(record1.test_class, 'Integration2Test')
    self.assertEqual(record2.test_class, 'IntegrationTest')

  def test_run_two_test_classes_different_configs_and_aliases(self):
    """Verifies that running more than one test class in one test run with
    different configs works properly.
    """
    config1 = self.base_mock_test_config.copy()
    config1.controller_configs[mock_controller.MOBLY_CONTROLLER_CONFIG_NAME] = [
        {
            'serial': 'xxxx'
        }
    ]
    config2 = config1.copy()
    config2.user_params['icecream'] = 10
    tr = test_runner.TestRunner(self.log_dir, self.testbed_name)
    with tr.mobly_logger():
      tr.add_test_class(config1,
                        integration_test.IntegrationTest,
                        name_suffix='FirstConfig')
      tr.add_test_class(config2,
                        integration_test.IntegrationTest,
                        name_suffix='SecondConfig')
      tr.run()
    results = tr.results.summary_dict()
    self.assertEqual(results['Requested'], 2)
    self.assertEqual(results['Executed'], 2)
    self.assertEqual(results['Passed'], 1)
    self.assertEqual(results['Failed'], 1)
    self.assertEqual(tr.results.failed[0].details, '10 != 42')
    self.assertEqual(len(tr.results.executed), 2)
    record1 = tr.results.executed[0]
    record2 = tr.results.executed[1]
    self.assertEqual(record1.test_class, 'IntegrationTest_FirstConfig')
    self.assertEqual(record2.test_class, 'IntegrationTest_SecondConfig')

  def test_run_with_abort_all(self):
    mock_test_config = self.base_mock_test_config.copy()
    tr = test_runner.TestRunner(self.log_dir, self.testbed_name)
    with tr.mobly_logger():
      tr.add_test_class(mock_test_config, integration3_test.Integration3Test)
      with self.assertRaises(signals.TestAbortAll):
        tr.run()
    results = tr.results.summary_dict()
    self.assertEqual(results['Requested'], 1)
    self.assertEqual(results['Executed'], 0)
    self.assertEqual(results['Passed'], 0)
    self.assertEqual(results['Failed'], 0)

  def test_add_test_class_mismatched_log_path(self):
    tr = test_runner.TestRunner('/different/log/dir', self.testbed_name)
    with self.assertRaisesRegex(
        test_runner.Error,
        'TestRunner\'s log folder is "/different/log/dir", but a test '
        r'config with a different log folder \("%s"\) was added.' %
        re.escape(self.log_dir)):
      tr.add_test_class(self.base_mock_test_config,
                        integration_test.IntegrationTest)

  def test_add_test_class_mismatched_testbed_name(self):
    tr = test_runner.TestRunner(self.log_dir, 'different_test_bed')
    with self.assertRaisesRegex(
        test_runner.Error,
        'TestRunner\'s test bed is "different_test_bed", but a test '
        r'config with a different test bed \("%s"\) was added.' %
        self.testbed_name):
      tr.add_test_class(self.base_mock_test_config,
                        integration_test.IntegrationTest)

  def test_run_no_tests(self):
    tr = test_runner.TestRunner(self.log_dir, self.testbed_name)
    with self.assertRaisesRegex(test_runner.Error, 'No tests to execute.'):
      tr.run()

  @mock.patch('mobly.test_runner._find_test_class',
              return_value=type('SampleTest', (), {}))
  @mock.patch('mobly.test_runner.config_parser.load_test_config_file',
              return_value=[config_parser.TestRunConfig()])
  @mock.patch('mobly.test_runner.TestRunner', return_value=mock.MagicMock())
  def test_main_parse_args(self, mock_test_runner, mock_config, mock_find_test):
    test_runner.main(['-c', 'some/path/foo.yaml', '-b', 'hello'])
    mock_config.assert_called_with('some/path/foo.yaml', None)

  @mock.patch('mobly.test_runner._find_test_class',
              return_value=integration_test.IntegrationTest)
  @mock.patch('sys.exit')
  def test_main(self, mock_exit, mock_find_test):
    tmp_file_path = os.path.join(self.tmp_dir, 'config.yml')
    with io.open(tmp_file_path, 'w', encoding='utf-8') as f:
      f.write(u"""
        TestBeds:
          # A test bed where adb will find Android devices.
          - Name: SampleTestBed
            Controllers:
              MagicDevice: '*'
            TestParams:
              icecream: 42
              extra_param: 'haha'
      """)
    test_runner.main(['-c', tmp_file_path])
    mock_exit.assert_not_called()

  @mock.patch('mobly.test_runner._find_test_class',
              return_value=integration_test.IntegrationTest)
  @mock.patch('sys.exit')
  def test_main_with_failures(self, mock_exit, mock_find_test):
    tmp_file_path = os.path.join(self.tmp_dir, 'config.yml')
    with io.open(tmp_file_path, 'w', encoding='utf-8') as f:
      f.write(u"""
        TestBeds:
          # A test bed where adb will find Android devices.
          - Name: SampleTestBed
            Controllers:
              MagicDevice: '*'
      """)
    test_runner.main(['-c', tmp_file_path])
    mock_exit.assert_called_once_with(1)

  def test__find_test_class_when_one_test_class(self):
    with mock.patch.dict('sys.modules', __main__=integration_test):
      test_class = test_runner._find_test_class()
      self.assertEqual(test_class, integration_test.IntegrationTest)

  def test__find_test_class_when_no_test_class(self):
    with self.assertRaises(SystemExit):
      with mock.patch.dict('sys.modules', __main__=mock_controller):
        test_class = test_runner._find_test_class()

  def test__find_test_class_when_multiple_test_classes(self):
    with self.assertRaises(SystemExit):
      with mock.patch.dict('sys.modules', __main__=multiple_subclasses_module):
        test_class = test_runner._find_test_class()

  def test_print_test_names(self):
    mock_test_class = mock.MagicMock()
    mock_cls_instance = mock.MagicMock()
    mock_test_class.return_value = mock_cls_instance
    test_runner._print_test_names(mock_test_class)
    mock_cls_instance.setup_generated_tests.assert_called_once()
    mock_cls_instance.get_existing_test_names.assert_called_once()
    mock_cls_instance._controller_manager.unregister_controllers.assert_called_once(
    )

  def test_print_test_names_with_exception(self):
    mock_test_class = mock.MagicMock()
    mock_cls_instance = mock.MagicMock()
    mock_test_class.return_value = mock_cls_instance
    test_runner._print_test_names(mock_test_class)
    mock_cls_instance.setup_generated_tests.side_effect = Exception(
        'Something went wrong.')
    mock_cls_instance._controller_manager.unregister_controllers.assert_called_once(
    )


if __name__ == "__main__":
  unittest.main()
