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
from mobly import test_runner
from mobly import utils
from tests.lib import integration2_test
from tests.lib import integration_test
from tests.lib import integration_test_suite
import yaml


class FakeTest1(base_test.BaseTestClass):
  pass

  def test_a(self):
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

      def set_test_selector(self, test_selector):
        mock_called.set_test_selector(test_selector)
        super().set_test_selector(test_selector)

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
    mock_called.set_test_selector.assert_called_once_with(None)

  @mock.patch('sys.exit')
  @mock.patch.object(records, 'TestSummaryWriter', autospec=True)
  @mock.patch.object(suite_runner, '_find_suite_class', autospec=True)
  @mock.patch.object(test_runner, 'TestRunner')
  def test_run_suite_class_with_test_selection_by_class(
      self, mock_test_runner_class, mock_find_suite_class, *_
  ):
    mock_test_runner = mock_test_runner_class.return_value
    mock_test_runner.results.is_all_pass = True
    tmp_file_path = self._gen_tmp_config_file()
    mock_cli_args = [
        'test_binary',
        f'--config={tmp_file_path}',
        '--tests',
        'FakeTest1',
        'FakeTest1_A',
    ]
    mock_called = mock.MagicMock()

    class FakeTestSuite(base_suite.BaseSuite):

      def set_test_selector(self, test_selector):
        mock_called.set_test_selector(test_selector)
        super().set_test_selector(test_selector)

      def setup_suite(self, config):
        self.add_test_class(FakeTest1)
        self.add_test_class(FakeTest1, name_suffix='A')
        self.add_test_class(FakeTest1, name_suffix='B')

    mock_find_suite_class.return_value = FakeTestSuite

    with mock.patch.object(sys, 'argv', new=mock_cli_args):
      suite_runner.run_suite_class()

    mock_called.set_test_selector.assert_called_once_with(
        {('FakeTest1', None): None, ('FakeTest1', 'A'): None},
    )

  @mock.patch('sys.exit')
  @mock.patch.object(records, 'TestSummaryWriter', autospec=True)
  @mock.patch.object(suite_runner, '_find_suite_class', autospec=True)
  @mock.patch.object(test_runner, 'TestRunner')
  def test_run_suite_class_with_test_selection_by_method(
      self, mock_test_runner_class, mock_find_suite_class, *_
  ):
    mock_test_runner = mock_test_runner_class.return_value
    mock_test_runner.results.is_all_pass = True
    tmp_file_path = self._gen_tmp_config_file()
    mock_cli_args = [
        'test_binary',
        f'--config={tmp_file_path}',
        '--tests',
        'FakeTest1.test_a',
        'FakeTest1_B.test_a',
    ]
    mock_called = mock.MagicMock()

    class FakeTestSuite(base_suite.BaseSuite):

      def set_test_selector(self, test_selector):
        mock_called.set_test_selector(test_selector)
        super().set_test_selector(test_selector)

      def setup_suite(self, config):
        self.add_test_class(FakeTest1)
        self.add_test_class(FakeTest1, name_suffix='B')
        self.add_test_class(FakeTest1, name_suffix='C')

    mock_find_suite_class.return_value = FakeTestSuite

    with mock.patch.object(sys, 'argv', new=mock_cli_args):
      suite_runner.run_suite_class()

    mock_called.set_test_selector.assert_called_once_with(
        {('FakeTest1', None): ['test_a'], ('FakeTest1', 'B'): ['test_a']},
    )

  @mock.patch.object(sys, 'exit')
  @mock.patch.object(suite_runner, '_find_suite_class', autospec=True)
  def test_run_suite_class_with_combined_test_selection(
      self, mock_find_suite_class, mock_exit
  ):
    mock_called = mock.MagicMock()

    class FakeTest2(base_test.BaseTestClass):

      def __init__(self, config):
        mock_called.suffix(config.test_class_name_suffix)
        super().__init__(config)

      def run(self, tests):
        mock_called.run(tests)
        return super().run(tests)

      def test_a(self):
        pass

      def test_b(self):
        pass

    class FakeTestSuite(base_suite.BaseSuite):

      def setup_suite(self, config):
        self.add_test_class(FakeTest2, name_suffix='A')
        self.add_test_class(FakeTest2, name_suffix='B')
        self.add_test_class(FakeTest2, name_suffix='C', tests=['test_a'])
        self.add_test_class(FakeTest2, name_suffix='D')
        self.add_test_class(FakeTest2)

    tmp_file_path = self._gen_tmp_config_file()
    mock_cli_args = [
        'test_binary',
        f'--config={tmp_file_path}',
        '--tests',
        'FakeTest2_A',
        'FakeTest2_B',
        'FakeTest2_C.test_a',
        'FakeTest2',
    ]

    mock_find_suite_class.return_value = FakeTestSuite
    with mock.patch.object(sys, 'argv', new=mock_cli_args):
      suite_runner.run_suite_class()

    mock_called.suffix.assert_has_calls(
        [mock.call('A'), mock.call('B'), mock.call('C'), mock.call(None)]
    )
    mock_called.run.assert_has_calls(
        [
            mock.call(None),
            mock.call(None),
            mock.call(['test_a']),
            mock.call(None),
        ]
    )
    mock_exit.assert_not_called()

  @mock.patch('sys.exit')
  @mock.patch.object(records, 'TestSummaryWriter', autospec=True)
  @mock.patch.object(test_runner, 'TestRunner')
  @mock.patch.object(
      integration_test_suite.IntegrationTestSuite, 'setup_suite', autospec=True
  )
  def test_run_suite_class_finds_suite_class_when_not_in_main_module(
      self, mock_setup_suite, mock_test_runner_class, *_
  ):
    mock_test_runner = mock_test_runner_class.return_value
    mock_test_runner.results.is_all_pass = True
    tmp_file_path = self._gen_tmp_config_file()
    mock_cli_args = ['test_binary', f'--config={tmp_file_path}']

    with mock.patch.object(sys, 'argv', new=mock_cli_args):
      integration_test_suite.main()

    mock_setup_suite.assert_called_once()

  @mock.patch('sys.exit')
  @mock.patch.object(
      utils, 'get_current_epoch_time', return_value=1733143236278
  )
  def test_run_suite_class_records_suite_info(self, mock_time, _):
    tmp_file_path = self._gen_tmp_config_file()
    mock_cli_args = ['test_binary', f'--config={tmp_file_path}']
    expected_record = suite_runner.SuiteInfoRecord(
        suite_class_name='FakeTestSuite'
    )
    expected_record.suite_begin()
    expected_record.suite_end()
    expected_record.suite_run_display_name = 'FakeTestSuite - Pixel'
    expected_record.extras = {'version': '1.0.0'}
    expected_summary_entry = expected_record.to_dict()
    expected_summary_entry['Type'] = (
        suite_runner.TestSummaryEntryType.SUITE_INFO.value
    )

    class FakeTestSuite(base_suite.BaseSuite):

      def setup_suite(self, config):
        super().setup_suite(config)
        self.add_test_class(FakeTest1)

      def teardown_suite(self):
        self.set_suite_run_display_name('FakeTestSuite - Pixel')
        self.set_suite_info({'version': '1.0.0'})

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

  @mock.patch('builtins.print')
  def test_print_test_names_for_suites(self, mock_print):
    class FakeTestSuite(base_suite.BaseSuite):

      def setup_suite(self, config):
        self.add_test_class(FakeTest1, name_suffix='A')
        self.add_test_class(FakeTest1, name_suffix='B')
        self.add_test_class(FakeTest1, name_suffix='C', tests=['test_a'])
        self.add_test_class(FakeTest1, name_suffix='D', tests=[])

    suite_runner._print_test_names_for_suite(FakeTestSuite)
    calls = [
        mock.call('==========> FakeTest1_A <=========='),
        mock.call('FakeTest1_A.test_a'),
        mock.call('==========> FakeTest1_B <=========='),
        mock.call('FakeTest1_B.test_a'),
        mock.call('==========> FakeTest1_C <=========='),
        mock.call('FakeTest1_C.test_a'),
    ]
    mock_print.assert_has_calls(calls)

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
    suite_run_display_name = 'FakeTestSuite - Pixel'
    suite_version = '1.2.3'
    record = suite_runner.SuiteInfoRecord(suite_class_name=suite_class_name)
    record.extras = {'version': suite_version}
    record.suite_begin()
    record.suite_end()
    record.suite_run_display_name = suite_run_display_name

    result = record.to_dict()

    self.assertIn(
        (suite_runner.SuiteInfoRecord.KEY_SUITE_CLASS_NAME, suite_class_name),
        result.items(),
    )
    self.assertIn(
        (suite_runner.SuiteInfoRecord.KEY_EXTRAS, {'version': suite_version}),
        result.items(),
    )
    self.assertIn(
        (
            suite_runner.SuiteInfoRecord.KEY_SUITE_RUN_DISPLAY_NAME,
            suite_run_display_name,
        ),
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
