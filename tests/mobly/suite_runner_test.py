# Copyright 2017 Google Inc.
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
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

from mobly import base_suite
from mobly import base_test
from mobly import records
from mobly import suite_runner
from mobly import utils
from tests.lib import integration2_test
from tests.lib import integration_test
import yaml


class FakeTest1(base_test.BaseTestClass):
  pass


class SuiteRunnerTest(unittest.TestCase):

  def setUp(self):
    self.tmp_dir = tempfile.mkdtemp()

  def tearDown(self):
    shutil.rmtree(self.tmp_dir)

  def test_select_no_args(self):
    identifiers = suite_runner.compute_selected_tests(
        test_classes=[
            integration_test.IntegrationTest,
            integration2_test.Integration2Test,
        ],
        selected_tests=None,
    )
    self.assertEqual(
        {
            integration_test.IntegrationTest: None,
            integration2_test.Integration2Test: None,
        },
        identifiers,
    )

  def test_select_by_class(self):
    identifiers = suite_runner.compute_selected_tests(
        test_classes=[
            integration_test.IntegrationTest,
            integration2_test.Integration2Test,
        ],
        selected_tests=['IntegrationTest'],
    )
    self.assertEqual({integration_test.IntegrationTest: None}, identifiers)

  def test_select_by_method(self):
    identifiers = suite_runner.compute_selected_tests(
        test_classes=[
            integration_test.IntegrationTest,
            integration2_test.Integration2Test,
        ],
        selected_tests=['IntegrationTest.test_a', 'IntegrationTest.test_b'],
    )
    self.assertEqual(
        {integration_test.IntegrationTest: ['test_a', 'test_b']}, identifiers
    )

  def test_select_all_clobbers_method(self):
    identifiers = suite_runner.compute_selected_tests(
        test_classes=[
            integration_test.IntegrationTest,
            integration2_test.Integration2Test,
        ],
        selected_tests=['IntegrationTest.test_a', 'IntegrationTest'],
    )
    self.assertEqual({integration_test.IntegrationTest: None}, identifiers)

    identifiers = suite_runner.compute_selected_tests(
        test_classes=[
            integration_test.IntegrationTest,
            integration2_test.Integration2Test,
        ],
        selected_tests=['IntegrationTest', 'IntegrationTest.test_a'],
    )
    self.assertEqual({integration_test.IntegrationTest: None}, identifiers)

  @mock.patch('sys.exit')
  def test_run_suite(self, mock_exit):
    tmp_file_path = os.path.join(self.tmp_dir, 'config.yml')
    with io.open(tmp_file_path, 'w', encoding='utf-8') as f:
      f.write(
          """
        TestBeds:
          # A test bed where adb will find Android devices.
          - Name: SampleTestBed
            Controllers:
              MagicDevice: '*'
            TestParams:
              icecream: 42
              extra_param: 'haha'
      """
      )
    suite_runner.run_suite(
        [integration_test.IntegrationTest], argv=['-c', tmp_file_path]
    )
    mock_exit.assert_not_called()

  @mock.patch('sys.exit')
  def test_run_suite_with_failures(self, mock_exit):
    tmp_file_path = os.path.join(self.tmp_dir, 'config.yml')
    with io.open(tmp_file_path, 'w', encoding='utf-8') as f:
      f.write(
          """
        TestBeds:
          # A test bed where adb will find Android devices.
          - Name: SampleTestBed
            Controllers:
              MagicDevice: '*'
      """
      )
    suite_runner.run_suite(
        [integration_test.IntegrationTest], argv=['-c', tmp_file_path]
    )
    mock_exit.assert_called_once_with(1)

  @mock.patch('sys.exit')
  def test_run_suite_class(self, mock_exit):
    tmp_file_path = self._gen_tmp_config_file()
    mock_cli_args = ['test_binary', f'--config={tmp_file_path}']
    mock_called = mock.MagicMock()

    class FakeTestSuite(base_suite.BaseSuite):

      def setup_suite(self, config):
        mock_called.setup_suite()
        super().setup_suite(config)
        self.add_test_class(FakeTest1)

      def teardown_suite(self):
        mock_called.teardown_suite()
        super().teardown_suite()

    sys.modules['__main__'].__dict__[FakeTestSuite.__name__] = FakeTestSuite

    with mock.patch.object(sys, 'argv', new=mock_cli_args):
      try:
        suite_runner.run_suite_class()
      finally:
        del sys.modules['__main__'].__dict__[FakeTestSuite.__name__]

    mock_called.setup_suite.assert_called_once_with()
    mock_called.teardown_suite.assert_called_once_with()
    mock_exit.assert_not_called()

  @mock.patch('sys.exit')
  @mock.patch.object(
      utils, 'get_current_epoch_time', return_value=1733143236278
  )
  def test_run_suite_class_records_suite_class_name(self, mock_time, _):
    tmp_file_path = self._gen_tmp_config_file()
    mock_cli_args = ['test_binary', f'--config={tmp_file_path}']
    expected_record = suite_runner.SuiteInfoRecord(
        test_suite_class='FakeTestSuite'
    )
    expected_record.suite_begin()
    expected_record.suite_end()
    expected_summary_entry = expected_record.to_dict()
    expected_summary_entry['Type'] = (
        records.TestSummaryEntryType.USER_DATA.value
    )

    class FakeTestSuite(base_suite.BaseSuite):

      def setup_suite(self, config):
        super().setup_suite(config)
        self.add_test_class(FakeTest1)

    sys.modules['__main__'].__dict__[FakeTestSuite.__name__] = FakeTestSuite

    with mock.patch.object(sys, 'argv', new=mock_cli_args):
      try:
        suite_runner.run_suite_class()
      finally:
        del sys.modules['__main__'].__dict__[FakeTestSuite.__name__]

    summary_path = os.path.join(
        logging.root_output_path, records.OUTPUT_FILE_SUMMARY
    )
    with io.open(summary_path, 'r', encoding='utf-8') as f:
      summary_entries = list(yaml.safe_load_all(f))

    self.assertIn(
        expected_summary_entry,
        summary_entries,
    )

  def test_print_test_names(self):
    mock_test_class = mock.MagicMock()
    mock_cls_instance = mock.MagicMock()
    mock_test_class.return_value = mock_cls_instance
    suite_runner._print_test_names([mock_test_class])
    mock_cls_instance._pre_run.assert_called_once()
    mock_cls_instance._clean_up.assert_called_once()

  def test_print_test_names_with_exception(self):
    mock_test_class = mock.MagicMock()
    mock_cls_instance = mock.MagicMock()
    mock_test_class.return_value = mock_cls_instance
    suite_runner._print_test_names([mock_test_class])
    mock_cls_instance._pre_run.side_effect = Exception('Something went wrong.')
    mock_cls_instance._clean_up.assert_called_once()

  def test_convert_suite_info_record_to_dict(self):
    suite_class_name = 'FakeTestSuite'
    suite_version = '1.2.3'
    record = suite_runner.SuiteInfoRecord(
        test_suite_class=suite_class_name, extras={'version': suite_version}
    )
    record.suite_begin()
    record.suite_end()

    result = record.to_dict()

    self.assertIn(
        (suite_runner.SuiteInfoRecord.KEY_TEST_SUITE_CLASS, suite_class_name),
        result.items(),
    )
    self.assertIn(
        (suite_runner.SuiteInfoRecord.KEY_EXTRAS, {'version': suite_version}),
        result.items(),
    )
    self.assertIn(suite_runner.SuiteInfoRecord.KEY_BEGIN_TIME, result)
    self.assertIn(suite_runner.SuiteInfoRecord.KEY_END_TIME, result)

  def _gen_tmp_config_file(self):
    tmp_file_path = os.path.join(self.tmp_dir, 'config.yml')
    with io.open(tmp_file_path, 'w', encoding='utf-8') as f:
      f.write(
          """
        TestBeds:
          # A test bed where adb will find Android devices.
          - Name: SampleTestBed
            Controllers:
              MagicDevice: '*'
      """
      )
    return tmp_file_path


if __name__ == '__main__':
  unittest.main()
