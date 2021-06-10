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

import copy
import functools
import io
import os
import mock
import re
import shutil
import tempfile
import unittest
import yaml

from mobly import asserts
from mobly import base_test
from mobly import config_parser
from mobly import expects
from mobly import records
from mobly import signals

from tests.lib import utils
from tests.lib import mock_controller
from tests.lib import mock_second_controller

MSG_EXPECTED_EXCEPTION = "This is an expected exception."
MSG_EXPECTED_TEST_FAILURE = "This is an expected test failure."
MSG_UNEXPECTED_EXCEPTION = "Unexpected exception!"

MOCK_EXTRA = {"key": "value", "answer_to_everything": 42}


def never_call():
  raise Exception(MSG_UNEXPECTED_EXCEPTION)


class SomeError(Exception):
  """A custom exception class used for tests in this module."""


class BaseTestTest(unittest.TestCase):

  def setUp(self):
    self.tmp_dir = tempfile.mkdtemp()
    self.mock_test_cls_configs = config_parser.TestRunConfig()
    self.summary_file = os.path.join(self.tmp_dir, 'summary.yaml')
    self.mock_test_cls_configs.summary_writer = records.TestSummaryWriter(
        self.summary_file)
    self.mock_test_cls_configs.controller_configs = {}
    self.mock_test_cls_configs.log_path = self.tmp_dir
    self.mock_test_cls_configs.user_params = {"some_param": "hahaha"}
    self.mock_test_cls_configs.reporter = mock.MagicMock()
    self.mock_test_name = "test_something"

  def tearDown(self):
    shutil.rmtree(self.tmp_dir)

  def test_paths(self):
    '''Checks the output paths set in `BaseTestClass`.'''
    path_checker = mock.MagicMock()

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        path_checker.log_path = self.log_path
        path_checker.root_output_path = self.root_output_path

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=["test_func"])
    self.assertEqual(path_checker.root_output_path, self.tmp_dir)
    self.assertTrue(os.path.exists(path_checker.root_output_path))
    expected_log_path = os.path.join(self.tmp_dir, 'MockBaseTest')
    self.assertEqual(path_checker.log_path, expected_log_path)
    self.assertTrue(os.path.exists(path_checker.log_path))

  def test_current_test_name(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        asserts.assert_true(self.current_test_info.name == "test_func",
                            ("Got "
                             "unexpected test name %s.") %
                            self.current_test_info.name)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=["test_func"])
    actual_record = bt_cls.results.passed[0]
    self.assertEqual(actual_record.test_name, "test_func")
    self.assertIsNone(actual_record.details)
    self.assertIsNone(actual_record.extras)

  def test_current_test_info(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        asserts.assert_true(
            self.current_test_info.name == 'test_func',
            'Got unexpected test name %s.' % self.current_test_info.name)
        output_path = self.current_test_info.output_path
        asserts.assert_true(os.path.exists(output_path),
                            'test output path missing')

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=['test_func'])
    actual_record = bt_cls.results.passed[0]
    self.assertEqual(actual_record.test_name, 'test_func')
    self.assertIsNone(actual_record.details)
    self.assertIsNone(actual_record.extras)

  def test_current_test_info_in_setup_class(self):

    class MockBaseTest(base_test.BaseTestClass):

      def setup_class(self):
        asserts.assert_true(
            self.current_test_info.name == 'setup_class',
            'Got unexpected test name %s.' % self.current_test_info.name)
        output_path = self.current_test_info.output_path
        asserts.assert_true(os.path.exists(output_path),
                            'test output path missing')
        raise Exception(MSG_EXPECTED_EXCEPTION)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.error[0]
    self.assertEqual(actual_record.test_name, 'setup_class')
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertIsNone(actual_record.extras)

  def test_self_tests_list(self):

    class MockBaseTest(base_test.BaseTestClass):

      def __init__(self, controllers):
        super().__init__(controllers)
        self.tests = ("test_something",)

      def test_something(self):
        pass

      def test_never(self):
        # This should not execute it's not on default test list.
        never_call()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.passed[0]
    self.assertEqual(actual_record.test_name, "test_something")

  def test_self_tests_list_fail_by_convention(self):

    class MockBaseTest(base_test.BaseTestClass):

      def __init__(self, controllers):
        super().__init__(controllers)
        self.tests = ("not_a_test_something",)

      def not_a_test_something(self):
        pass

      def test_never(self):
        # This should not execute it's not on default test list.
        never_call()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    expected_msg = (r'Test method name not_a_test_something does not follow '
                    r'naming convention test_\*, abort.')
    with self.assertRaisesRegex(base_test.Error, expected_msg):
      bt_cls.run()

  def test_cli_test_selection_override_self_tests_list(self):

    class MockBaseTest(base_test.BaseTestClass):

      def __init__(self, controllers):
        super().__init__(controllers)
        self.tests = ("test_never",)

      def test_something(self):
        pass

      def test_never(self):
        # This should not execute it's not selected by cmd line input.
        never_call()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=["test_something"])
    actual_record = bt_cls.results.passed[0]
    self.assertEqual(actual_record.test_name, "test_something")

  def test_cli_test_selection_fail_by_convention(self):

    class MockBaseTest(base_test.BaseTestClass):

      def __init__(self, controllers):
        super().__init__(controllers)
        self.tests = ("not_a_test_something",)

      def not_a_test_something(self):
        pass

      def test_never(self):
        # This should not execute it's not selected by cmd line input.
        never_call()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    expected_msg = (r'Test method name not_a_test_something does not follow '
                    r'naming convention test_\*, abort.')
    with self.assertRaisesRegex(base_test.Error, expected_msg):
      bt_cls.run(test_names=["not_a_test_something"])

  def test_default_execution_of_all_tests(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_something(self):
        pass

      def not_a_test(self):
        # This should not execute its name doesn't follow test method
        # naming convention.
        never_call()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.passed[0]
    self.assertEqual(actual_record.test_name, "test_something")

  def test_default_execution_skip_noncallable_tests(self):
    mock_decorated = mock.MagicMock()
    mock_undecorated = mock.MagicMock()

    class TestDecorator:

      def __init__(self, func):
        self.func = func

      def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

      def __get__(self, instance, owner):
        return functools.partial(self.__call__, instance)

    class MockBaseTest(base_test.BaseTestClass):

      def __init__(self, controllers):
        super().__init__(controllers)
        self.test_noncallable = None

      @TestDecorator
      def test_decorated(self):
        mock_decorated('test_decorated')

      def test_undecorated(self):
        mock_undecorated('test_undecorated')

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    self.assertNotIn('test_noncallable',
                     [test.test_name for test in bt_cls.results.executed])
    mock_decorated.assert_called_once_with('test_decorated')
    mock_undecorated.assert_called_once_with('test_undecorated')

  def test_missing_requested_test_func(self):

    class MockBaseTest(base_test.BaseTestClass):
      pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    expected_msg = ".* does not have test method test_something"
    with self.assertRaisesRegex(base_test.Error, expected_msg):
      bt_cls.run(test_names=["test_something"])
    self.assertFalse(bt_cls.results.executed)

  def test_setup_class_fail_by_exception(self):
    teardown_class_call_check = mock.MagicMock()
    on_fail_call_check = mock.MagicMock()

    class MockBaseTest(base_test.BaseTestClass):

      def setup_class(self):
        raise Exception(MSG_EXPECTED_EXCEPTION)

      def test_something(self):
        # This should not execute because setup_class failed.
        never_call()

      def test_something2(self):
        # This should not execute because setup_class failed.
        never_call()

      def teardown_class(self):
        # This should execute because the setup_class failure should
        # have already been recorded.
        if not self.results.is_all_pass:
          teardown_class_call_check("heehee")

      def on_fail(self, record):
        on_fail_call_check("haha")

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.error[0]
    skipped_record = bt_cls.results.skipped[0]
    self.assertIsNone(skipped_record.begin_time)
    self.assertIsNone(skipped_record.end_time)
    utils.validate_test_result(bt_cls.results)
    self.assertEqual(actual_record.test_name, "setup_class")
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertIsNone(actual_record.extras)
    expected_summary = ("Error 1, Executed 0, Failed 0, Passed 0, "
                        "Requested 2, Skipped 2")
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)
    teardown_class_call_check.assert_called_once_with("heehee")
    on_fail_call_check.assert_called_once_with("haha")

  def test_teardown_class_fail_by_exception(self):
    mock_test_config = self.mock_test_cls_configs.copy()
    mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
    mock_ctrlr_2_config_name = mock_second_controller.MOBLY_CONTROLLER_CONFIG_NAME
    my_config = [{'serial': 'xxxx', 'magic': 'Magic'}]
    mock_test_config.controller_configs[mock_ctrlr_config_name] = my_config
    mock_test_config.controller_configs[mock_ctrlr_2_config_name] = copy.copy(
        my_config)

    class MockBaseTest(base_test.BaseTestClass):

      def setup_class(self):
        self.register_controller(mock_controller)

      def test_something(self):
        pass

      def teardown_class(self):
        raise Exception(MSG_EXPECTED_EXCEPTION)

    bt_cls = MockBaseTest(mock_test_config)
    bt_cls.run()
    test_record = bt_cls.results.passed[0]
    class_record = bt_cls.results.error[0]
    self.assertFalse(bt_cls.results.is_all_pass)
    self.assertEqual(class_record.test_name, 'teardown_class')
    self.assertEqual(class_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertIsNotNone(class_record.begin_time)
    self.assertIsNotNone(class_record.end_time)
    self.assertIsNone(class_record.extras)
    expected_summary = ('Error 1, Executed 1, Failed 0, Passed 1, '
                        'Requested 1, Skipped 0')
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)
    # Verify the controller info is recorded correctly.
    info = bt_cls.results.controller_info[0]
    self.assertEqual(info.test_class, 'MockBaseTest')
    self.assertEqual(info.controller_name, 'MagicDevice')
    self.assertEqual(info.controller_info, [{'MyMagic': {'magic': 'Magic'}}])

  def test_teardown_class_raise_abort_all(self):
    mock_test_config = self.mock_test_cls_configs.copy()
    mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
    mock_ctrlr_2_config_name = mock_second_controller.MOBLY_CONTROLLER_CONFIG_NAME
    my_config = [{'serial': 'xxxx', 'magic': 'Magic'}]
    mock_test_config.controller_configs[mock_ctrlr_config_name] = my_config
    mock_test_config.controller_configs[mock_ctrlr_2_config_name] = copy.copy(
        my_config)

    class MockBaseTest(base_test.BaseTestClass):

      def setup_class(self):
        self.register_controller(mock_controller)

      def test_something(self):
        pass

      def teardown_class(self):
        raise asserts.abort_all(MSG_EXPECTED_EXCEPTION)

    bt_cls = MockBaseTest(mock_test_config)
    with self.assertRaisesRegex(signals.TestAbortAll, MSG_EXPECTED_EXCEPTION):
      bt_cls.run()
    test_record = bt_cls.results.passed[0]
    self.assertTrue(bt_cls.results.is_all_pass)
    expected_summary = ('Error 0, Executed 1, Failed 0, Passed 1, '
                        'Requested 1, Skipped 0')
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)
    # Verify the controller info is recorded correctly.
    info = bt_cls.results.controller_info[0]
    self.assertEqual(info.test_class, 'MockBaseTest')
    self.assertEqual(info.controller_name, 'MagicDevice')
    self.assertEqual(info.controller_info, [{'MyMagic': {'magic': 'Magic'}}])

  def test_setup_test_fail_by_exception(self):
    mock_on_fail = mock.Mock()

    class MockBaseTest(base_test.BaseTestClass):

      def on_fail(self, *args):
        mock_on_fail('on_fail')

      def setup_test(self):
        raise Exception(MSG_EXPECTED_EXCEPTION)

      def test_something(self):
        # This should not execute because setup_test failed.
        never_call()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=["test_something"])
    mock_on_fail.assert_called_once_with('on_fail')
    actual_record = bt_cls.results.error[0]
    self.assertEqual(actual_record.test_name, self.mock_test_name)
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertIn(
        'in setup_test\n    '
        'raise Exception(MSG_EXPECTED_EXCEPTION)\n'
        'Exception: This is an expected exception.\n', actual_record.stacktrace)
    self.assertIsNone(actual_record.extras)
    expected_summary = ("Error 1, Executed 1, Failed 0, Passed 0, "
                        "Requested 1, Skipped 0")
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)

  def test_setup_test_fail_by_test_signal(self):

    class MockBaseTest(base_test.BaseTestClass):

      def setup_test(self):
        raise signals.TestFailure(MSG_EXPECTED_EXCEPTION)

      def test_something(self):
        # This should not execute because setup_test failed.
        never_call()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=["test_something"])
    actual_record = bt_cls.results.error[0]
    self.assertEqual(actual_record.test_name, self.mock_test_name)
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    # Make sure the full stacktrace of `setup_test` is preserved.
    self.assertTrue('self.setup_test()' in actual_record.stacktrace)
    self.assertIsNone(actual_record.extras)
    self.assertTrue(actual_record.end_time)
    expected_summary = ("Error 1, Executed 1, Failed 0, Passed 0, "
                        "Requested 1, Skipped 0")
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)

  def test_teardown_test_assert_fail(self):

    class MockBaseTest(base_test.BaseTestClass):

      def teardown_test(self):
        asserts.fail(MSG_EXPECTED_EXCEPTION)

      def test_something(self):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.error[0]
    self.assertEqual(actual_record.test_name, self.mock_test_name)
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertTrue(actual_record.end_time)
    self.assertIsNone(actual_record.extras)
    expected_summary = ("Error 1, Executed 1, Failed 0, Passed 0, "
                        "Requested 1, Skipped 0")
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)

  def test_teardown_test_raise_exception(self):

    class MockBaseTest(base_test.BaseTestClass):

      def teardown_test(self):
        raise Exception(MSG_EXPECTED_EXCEPTION)

      def test_something(self):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.error[0]
    self.assertEqual(actual_record.test_name, self.mock_test_name)
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertIsNone(actual_record.extras)
    self.assertFalse(actual_record.extra_errors)
    expected_summary = ("Error 1, Executed 1, Failed 0, Passed 0, "
                        "Requested 1, Skipped 0")
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)

  def test_teardown_test_executed_if_test_pass(self):
    my_mock = mock.MagicMock()

    class MockBaseTest(base_test.BaseTestClass):

      def teardown_test(self):
        my_mock("teardown_test")

      def test_something(self):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.passed[0]
    my_mock.assert_called_once_with("teardown_test")
    self.assertEqual(actual_record.test_name, self.mock_test_name)
    self.assertIsNone(actual_record.details)
    self.assertIsNone(actual_record.extras)
    self.assertTrue(actual_record.end_time)
    expected_summary = ("Error 0, Executed 1, Failed 0, Passed 1, "
                        "Requested 1, Skipped 0")
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)

  def test_teardown_test_executed_if_setup_test_fails(self):
    my_mock = mock.MagicMock()

    class MockBaseTest(base_test.BaseTestClass):

      def setup_test(self):
        raise Exception(MSG_EXPECTED_EXCEPTION)

      def teardown_test(self):
        my_mock("teardown_test")

      def test_something(self):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.error[0]
    my_mock.assert_called_once_with("teardown_test")
    self.assertEqual(actual_record.test_name, self.mock_test_name)
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertIsNone(actual_record.extras)
    self.assertTrue(actual_record.end_time)
    expected_summary = ("Error 1, Executed 1, Failed 0, Passed 0, "
                        "Requested 1, Skipped 0")
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)

  def test_teardown_test_executed_if_test_fails(self):
    my_mock = mock.MagicMock()

    class MockBaseTest(base_test.BaseTestClass):

      def teardown_test(self):
        my_mock("teardown_test")

      def on_pass(self, record):
        never_call()

      def test_something(self):
        raise Exception(MSG_EXPECTED_EXCEPTION)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.error[0]
    my_mock.assert_called_once_with("teardown_test")
    self.assertEqual(actual_record.test_name, self.mock_test_name)
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertIsNone(actual_record.extras)
    expected_summary = ("Error 1, Executed 1, Failed 0, Passed 0, "
                        "Requested 1, Skipped 0")
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)

  def test_on_fail_executed_if_teardown_test_fails(self):
    my_mock = mock.MagicMock()

    class MockBaseTest(base_test.BaseTestClass):

      def on_fail(self, record):
        my_mock("on_fail")

      def on_pass(self, record):
        never_call()

      def teardown_test(self):
        raise Exception(MSG_EXPECTED_EXCEPTION)

      def test_something(self):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    my_mock.assert_called_once_with('on_fail')
    actual_record = bt_cls.results.error[0]
    self.assertEqual(actual_record.test_name, self.mock_test_name)
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertIsNone(actual_record.extras)
    expected_summary = ("Error 1, Executed 1, Failed 0, Passed 0, "
                        "Requested 1, Skipped 0")
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)

  def test_on_fail_executed_if_test_fails(self):
    my_mock = mock.MagicMock()

    class MockBaseTest(base_test.BaseTestClass):

      def on_fail(self, record):
        assert self.current_test_info.name == 'test_something'
        my_mock("on_fail")

      def on_pass(self, record):
        never_call()

      def test_something(self):
        asserts.assert_true(False, MSG_EXPECTED_EXCEPTION)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    my_mock.assert_called_once_with("on_fail")
    actual_record = bt_cls.results.failed[0]
    self.assertEqual(actual_record.test_name, self.mock_test_name)
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertIsNone(actual_record.extras)
    expected_summary = ("Error 0, Executed 1, Failed 1, Passed 0, "
                        "Requested 1, Skipped 0")
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)

  def test_procedure_function_gets_correct_record(self):
    on_fail_mock = mock.MagicMock()

    class MockBaseTest(base_test.BaseTestClass):

      def on_fail(self, record):
        on_fail_mock.record = record

      def test_something(self):
        asserts.fail(MSG_EXPECTED_EXCEPTION)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.failed[0]
    self.assertEqual(actual_record.test_name, 'test_something')
    self.assertEqual(on_fail_mock.record.test_name, actual_record.test_name)
    self.assertEqual(on_fail_mock.record.begin_time, actual_record.begin_time)
    self.assertEqual(on_fail_mock.record.end_time, actual_record.end_time)
    self.assertEqual(on_fail_mock.record.stacktrace, actual_record.stacktrace)
    self.assertEqual(on_fail_mock.record.extras, actual_record.extras)
    self.assertEqual(on_fail_mock.record.extra_errors,
                     actual_record.extra_errors)
    # But they are not the same object.
    self.assertIsNot(on_fail_mock.record, actual_record)

  def test_on_fail_cannot_modify_original_record(self):

    class MockBaseTest(base_test.BaseTestClass):

      def on_fail(self, record):
        record.test_name = 'blah'

      def test_something(self):
        asserts.assert_true(False, MSG_EXPECTED_EXCEPTION)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.failed[0]
    self.assertEqual(actual_record.test_name, 'test_something')

  def test_on_fail_executed_if_both_test_and_teardown_test_fails(self):
    on_fail_mock = mock.MagicMock()

    class MockBaseTest(base_test.BaseTestClass):

      def on_fail(self, record):
        on_fail_mock("on_fail")

      def on_pass(self, record):
        never_call()

      def teardown_test(self):
        raise Exception(MSG_EXPECTED_EXCEPTION + 'ha')

      def test_something(self):
        raise Exception(MSG_EXPECTED_EXCEPTION)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    on_fail_mock.assert_called_once_with("on_fail")
    actual_record = bt_cls.results.error[0]
    self.assertEqual(actual_record.test_name, self.mock_test_name)
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertEqual(actual_record.extra_errors['teardown_test'].details,
                     'This is an expected exception.ha')
    self.assertIsNone(actual_record.extras)
    expected_summary = ("Error 1, Executed 1, Failed 0, Passed 0, "
                        "Requested 1, Skipped 0")
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)

  def test_on_fail_executed_if_setup_test_fails_by_exception(self):
    my_mock = mock.MagicMock()

    class MockBaseTest(base_test.BaseTestClass):

      def setup_test(self):
        raise Exception(MSG_EXPECTED_EXCEPTION)

      def on_fail(self, record):
        my_mock("on_fail")

      def test_something(self):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    my_mock.assert_called_once_with("on_fail")
    actual_record = bt_cls.results.error[0]
    self.assertEqual(actual_record.test_name, self.mock_test_name)
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertIsNone(actual_record.extras)
    expected_summary = ("Error 1, Executed 1, Failed 0, Passed 0, "
                        "Requested 1, Skipped 0")
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)

  def test_on_fail_executed_if_setup_class_fails_by_exception(self):
    my_mock = mock.MagicMock()

    class MockBaseTest(base_test.BaseTestClass):

      def setup_class(self):
        raise Exception(MSG_EXPECTED_EXCEPTION)

      def on_fail(self, record):
        my_mock("on_fail")

      def test_something(self):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    my_mock.assert_called_once_with("on_fail")
    actual_record = bt_cls.results.error[0]
    self.assertEqual(actual_record.test_name, 'setup_class')
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertIsNone(actual_record.extras)
    expected_summary = ("Error 1, Executed 0, Failed 0, Passed 0, "
                        "Requested 1, Skipped 1")
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)

  def test_on_fail_triggered_by_setup_class_failure_then_fail_too(self):
    """Errors thrown from on_fail should be captured."""

    class MockBaseTest(base_test.BaseTestClass):

      def setup_class(self):
        raise Exception(MSG_EXPECTED_EXCEPTION)

      def on_fail(self, record):
        raise Exception('Failure in on_fail.')

      def test_something(self):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    setup_class_record = bt_cls.results.error[0]
    self.assertEqual(setup_class_record.test_name, 'setup_class')
    self.assertEqual(setup_class_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertEqual(setup_class_record.extra_errors['on_fail'].details,
                     'Failure in on_fail.')
    expected_summary = ("Error 1, Executed 0, Failed 0, Passed 0, "
                        "Requested 1, Skipped 1")
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)

  def test_failure_to_call_procedure_function_is_recorded(self):

    class MockBaseTest(base_test.BaseTestClass):

      def on_fail(self):
        pass

      def test_something(self):
        asserts.assert_true(False, MSG_EXPECTED_EXCEPTION)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.failed[0]
    self.assertIn('on_fail', actual_record.extra_errors)
    self.assertEqual(actual_record.test_name, self.mock_test_name)
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertIsNone(actual_record.extras)
    expected_summary = ("Error 0, Executed 1, Failed 1, Passed 0, "
                        "Requested 1, Skipped 0")
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)

  def test_failure_in_procedure_functions_is_recorded(self):
    expected_msg = "Something failed in on_pass."

    class MockBaseTest(base_test.BaseTestClass):

      def on_pass(self, record):
        raise Exception(expected_msg)

      def test_something(self):
        asserts.explicit_pass(MSG_EXPECTED_EXCEPTION)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.error[0]
    self.assertEqual(actual_record.extra_errors['on_pass'].details,
                     expected_msg)
    self.assertEqual(actual_record.test_name, self.mock_test_name)
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertIsNone(actual_record.extras)
    expected_summary = ("Error 1, Executed 1, Failed 0, Passed 0, "
                        "Requested 1, Skipped 0")
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)

  def test_both_teardown_and_test_body_raise_exceptions(self):

    class MockBaseTest(base_test.BaseTestClass):

      def teardown_test(self):
        asserts.assert_true(False, MSG_EXPECTED_EXCEPTION)

      def test_something(self):
        raise Exception("Test Body Exception.")

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.error[0]
    self.assertEqual(actual_record.test_name, self.mock_test_name)
    self.assertEqual(actual_record.details, "Test Body Exception.")
    self.assertIsNone(actual_record.extras)
    self.assertEqual(actual_record.extra_errors['teardown_test'].details,
                     MSG_EXPECTED_EXCEPTION)
    self.assertIsNone(actual_record.extra_errors['teardown_test'].extras)
    expected_summary = ("Error 1, Executed 1, Failed 0, Passed 0, "
                        "Requested 1, Skipped 0")
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)

  def test_exception_objects_in_record(self):
    """Checks that the exception objects are correctly tallied.
    """
    expected_termination_signal = Exception('Test Body Exception.')
    expected_extra_error = Exception('teardown_test Exception.')

    class MockBaseTest(base_test.BaseTestClass):

      def teardown_test(self):
        raise expected_extra_error

      def test_something(self):
        raise expected_termination_signal

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.error[0]
    self.assertIs(actual_record.termination_signal.exception,
                  expected_termination_signal)
    self.assertIsNotNone(actual_record.termination_signal.stacktrace)
    self.assertEqual(len(actual_record.extra_errors), 1)
    extra_error = actual_record.extra_errors['teardown_test']
    self.assertIs(extra_error.exception, expected_extra_error)
    self.assertIsNotNone(extra_error.stacktrace)
    self.assertIsNone(actual_record.extras)

  def test_promote_extra_errors_to_termination_signal(self):
    """If no termination signal is specified, use the first extra error as
    the termination signal.
    """
    expected_extra_error = Exception('teardown_test Exception.')

    class MockBaseTest(base_test.BaseTestClass):

      def teardown_test(self):
        raise expected_extra_error

      def test_something(self):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.error[0]
    self.assertFalse(actual_record.extra_errors)
    self.assertEqual(actual_record.details, 'teardown_test Exception.')
    self.assertIsNotNone(actual_record.stacktrace)

  def test_explicit_pass_but_teardown_test_raises_an_exception(self):
    """Test record result should be marked as ERROR as opposed to PASS.
    """

    class MockBaseTest(base_test.BaseTestClass):

      def teardown_test(self):
        asserts.assert_true(False, MSG_EXPECTED_EXCEPTION)

      def test_something(self):
        asserts.explicit_pass('Test Passed!')

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.error[0]
    self.assertEqual(actual_record.test_name, self.mock_test_name)
    self.assertEqual(actual_record.details, 'Test Passed!')
    self.assertIsNone(actual_record.extras)
    self.assertEqual(actual_record.extra_errors['teardown_test'].details,
                     MSG_EXPECTED_EXCEPTION)
    self.assertIsNone(actual_record.extra_errors['teardown_test'].extras)
    expected_summary = ("Error 1, Executed 1, Failed 0, Passed 0, "
                        "Requested 1, Skipped 0")
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)

  def test_on_pass_cannot_modify_original_record(self):

    class MockBaseTest(base_test.BaseTestClass):

      def on_pass(self, record):
        record.test_name = 'blah'

      def test_something(self):
        asserts.explicit_pass('Extra pass!')

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.passed[0]
    self.assertEqual(actual_record.test_name, 'test_something')

  def test_on_pass_raise_exception(self):

    class MockBaseTest(base_test.BaseTestClass):

      def on_pass(self, record):
        raise Exception(MSG_EXPECTED_EXCEPTION)

      def test_something(self):
        asserts.explicit_pass(MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.error[0]
    self.assertEqual(actual_record.test_name, self.mock_test_name)
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertEqual(actual_record.extras, MOCK_EXTRA)
    self.assertEqual(actual_record.extra_errors['on_pass'].details,
                     MSG_EXPECTED_EXCEPTION)
    expected_summary = ("Error 1, Executed 1, Failed 0, Passed 0, "
                        "Requested 1, Skipped 0")
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)

  def test_on_fail_raise_exception(self):

    class MockBaseTest(base_test.BaseTestClass):

      def on_fail(self, record):
        raise Exception(MSG_EXPECTED_EXCEPTION)

      def test_something(self):
        asserts.fail(MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.failed[0]
    self.assertEqual(actual_record.test_name, self.mock_test_name)
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertEqual(actual_record.extras, MOCK_EXTRA)
    self.assertEqual(actual_record.extra_errors['on_fail'].details,
                     MSG_EXPECTED_EXCEPTION)
    expected_summary = ("Error 0, Executed 1, Failed 1, Passed 0, "
                        "Requested 1, Skipped 0")
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)

  def test_abort_class_setup_class(self):
    """A class was intentionally aborted by the test.

    This is not considered an error as the abort class is used as a skip
    signal for the entire class, which is different from raising other
    exceptions in `setup_class`.
    """

    class MockBaseTest(base_test.BaseTestClass):

      def setup_class(self):
        asserts.abort_class(MSG_EXPECTED_EXCEPTION)

      def test_1(self):
        never_call()

      def test_2(self):
        never_call()

      def test_3(self):
        never_call()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=["test_1", "test_2", "test_3"])
    self.assertEqual(len(bt_cls.results.skipped), 3)
    self.assertEqual(bt_cls.results.summary_str(),
                     ("Error 0, Executed 0, Failed 0, Passed 0, "
                      "Requested 3, Skipped 3"))

  def test_abort_class_in_setup_test(self):

    class MockBaseTest(base_test.BaseTestClass):

      def setup_test(self):
        asserts.abort_class(MSG_EXPECTED_EXCEPTION)

      def test_1(self):
        never_call()

      def test_2(self):
        never_call()

      def test_3(self):
        never_call()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=["test_1", "test_2", "test_3"])
    self.assertEqual(len(bt_cls.results.skipped), 2)
    self.assertEqual(bt_cls.results.summary_str(),
                     ("Error 0, Executed 1, Failed 1, Passed 0, "
                      "Requested 3, Skipped 2"))

  def test_abort_class_in_on_fail(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_1(self):
        asserts.fail(MSG_EXPECTED_EXCEPTION)

      def test_2(self):
        never_call()

      def test_3(self):
        never_call()

      def on_fail(self, record):
        asserts.abort_class(MSG_EXPECTED_EXCEPTION)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=["test_1", "test_2", "test_3"])
    self.assertEqual(len(bt_cls.results.skipped), 2)
    self.assertEqual(bt_cls.results.summary_str(),
                     ("Error 0, Executed 1, Failed 1, Passed 0, "
                      "Requested 3, Skipped 2"))

  def test_setup_and_teardown_execution_count(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        pass

      def test_func2(self):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.setup_class = mock.Mock()
    bt_cls.teardown_class = mock.Mock()
    bt_cls.setup_test = mock.Mock()
    bt_cls.teardown_test = mock.Mock()
    bt_cls.run()
    self.assertEqual(bt_cls.setup_class.call_count, 1)
    self.assertEqual(bt_cls.teardown_class.call_count, 1)
    self.assertEqual(bt_cls.setup_test.call_count, 2)
    self.assertEqual(bt_cls.teardown_test.call_count, 2)

  def test_abort_class_in_test(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_1(self):
        pass

      def test_2(self):
        asserts.abort_class(MSG_EXPECTED_EXCEPTION)
        never_call()

      def test_3(self):
        never_call()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=["test_1", "test_2", "test_3"])
    self.assertEqual(bt_cls.results.passed[0].test_name, "test_1")
    self.assertEqual(bt_cls.results.failed[0].details, MSG_EXPECTED_EXCEPTION)
    self.assertEqual(bt_cls.results.summary_str(),
                     ("Error 0, Executed 2, Failed 1, Passed 1, "
                      "Requested 3, Skipped 1"))

  def test_abort_all_in_setup_class(self):

    class MockBaseTest(base_test.BaseTestClass):

      def setup_class(self):
        asserts.abort_all(MSG_EXPECTED_EXCEPTION)

      def test_1(self):
        never_call()

      def test_2(self):
        never_call()

      def test_3(self):
        never_call()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    with self.assertRaisesRegex(signals.TestAbortAll,
                                MSG_EXPECTED_EXCEPTION) as context:
      bt_cls.run(test_names=["test_1", "test_2", "test_3"])
    self.assertTrue(hasattr(context.exception, 'results'))
    self.assertEqual(bt_cls.results.summary_str(),
                     ("Error 0, Executed 0, Failed 0, Passed 0, "
                      "Requested 3, Skipped 3"))

  def test_abort_all_in_teardown_class(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_1(self):
        pass

      def test_2(self):
        pass

      def teardown_class(self):
        asserts.abort_all(MSG_EXPECTED_EXCEPTION)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    with self.assertRaisesRegex(signals.TestAbortAll,
                                MSG_EXPECTED_EXCEPTION) as context:
      bt_cls.run(test_names=["test_1", "test_2"])
    self.assertTrue(hasattr(context.exception, 'results'))
    self.assertEqual(bt_cls.results.summary_str(),
                     ("Error 0, Executed 2, Failed 0, Passed 2, "
                      "Requested 2, Skipped 0"))

  def test_abort_all_in_setup_test(self):

    class MockBaseTest(base_test.BaseTestClass):

      def setup_test(self):
        asserts.abort_all(MSG_EXPECTED_EXCEPTION)

      def test_1(self):
        never_call()

      def test_2(self):
        never_call()

      def test_3(self):
        never_call()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    with self.assertRaisesRegex(signals.TestAbortAll,
                                MSG_EXPECTED_EXCEPTION) as context:
      bt_cls.run(test_names=["test_1", "test_2", "test_3"])
    self.assertTrue(hasattr(context.exception, 'results'))
    self.assertEqual(bt_cls.results.summary_str(),
                     ("Error 0, Executed 1, Failed 1, Passed 0, "
                      "Requested 3, Skipped 2"))

  def test_abort_all_in_on_fail(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_1(self):
        asserts.fail(MSG_EXPECTED_EXCEPTION)

      def test_2(self):
        never_call()

      def test_3(self):
        never_call()

      def on_fail(self, record):
        asserts.abort_all(MSG_EXPECTED_EXCEPTION)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    with self.assertRaisesRegex(signals.TestAbortAll,
                                MSG_EXPECTED_EXCEPTION) as context:
      bt_cls.run(test_names=["test_1", "test_2", "test_3"])
    self.assertTrue(hasattr(context.exception, 'results'))
    self.assertEqual(bt_cls.results.summary_str(),
                     ("Error 0, Executed 1, Failed 1, Passed 0, "
                      "Requested 3, Skipped 2"))

  def test_abort_all_in_on_fail_from_setup_class(self):

    class MockBaseTest(base_test.BaseTestClass):

      def setup_class(self):
        asserts.fail(MSG_UNEXPECTED_EXCEPTION)

      def test_1(self):
        never_call()

      def test_2(self):
        never_call()

      def test_3(self):
        never_call()

      def on_fail(self, record):
        asserts.abort_all(MSG_EXPECTED_EXCEPTION)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    with self.assertRaisesRegex(signals.TestAbortAll,
                                MSG_EXPECTED_EXCEPTION) as context:
      bt_cls.run(test_names=["test_1", "test_2", "test_3"])
    setup_class_record = bt_cls.results.error[0]
    self.assertEqual(setup_class_record.test_name, 'setup_class')
    self.assertTrue(hasattr(context.exception, 'results'))
    self.assertEqual(bt_cls.results.summary_str(),
                     ("Error 1, Executed 0, Failed 0, Passed 0, "
                      "Requested 3, Skipped 3"))

  def test_abort_all_in_test(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_1(self):
        pass

      def test_2(self):
        asserts.abort_all(MSG_EXPECTED_EXCEPTION)
        never_call()

      def test_3(self):
        never_call()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    with self.assertRaisesRegex(signals.TestAbortAll,
                                MSG_EXPECTED_EXCEPTION) as context:
      bt_cls.run(test_names=["test_1", "test_2", "test_3"])
    self.assertTrue(hasattr(context.exception, 'results'))
    self.assertEqual(bt_cls.results.passed[0].test_name, "test_1")
    self.assertEqual(bt_cls.results.failed[0].details, MSG_EXPECTED_EXCEPTION)
    self.assertEqual(bt_cls.results.summary_str(),
                     ("Error 0, Executed 2, Failed 1, Passed 1, "
                      "Requested 3, Skipped 1"))

  def test_uncaught_exception(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        raise Exception(MSG_EXPECTED_EXCEPTION)
        never_call()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=["test_func"])
    actual_record = bt_cls.results.error[0]
    self.assertEqual(actual_record.test_name, "test_func")
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertIsNone(actual_record.extras)
    # Stacktraces can vary. Just check for key words
    self.assertIn('test_method()', actual_record.stacktrace)
    self.assertIn('raise Exception(MSG_EXPECTED_EXCEPTION)',
                  actual_record.stacktrace)
    self.assertIn('Exception: This is an expected exception.',
                  actual_record.stacktrace)

  def test_fail(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        asserts.fail(MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
        never_call()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=["test_func"])
    actual_record = bt_cls.results.failed[0]
    self.assertEqual(actual_record.test_name, "test_func")
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertEqual(actual_record.extras, MOCK_EXTRA)

  def test_assert_true(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        asserts.assert_true(False, MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
        never_call()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=["test_func"])
    actual_record = bt_cls.results.failed[0]
    self.assertEqual(actual_record.test_name, "test_func")
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertEqual(actual_record.extras, MOCK_EXTRA)

  def test_assert_equal_pass(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        asserts.assert_equal(1, 1, extras=MOCK_EXTRA)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.passed[0]
    self.assertEqual(actual_record.test_name, "test_func")
    self.assertIsNone(actual_record.details)
    self.assertIsNone(actual_record.extras)

  def test_assert_equal_fail(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        asserts.assert_equal(1, 2, extras=MOCK_EXTRA)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.failed[0]
    self.assertEqual(actual_record.test_name, "test_func")
    self.assertEqual(actual_record.details, "1 != 2")
    self.assertEqual(actual_record.extras, MOCK_EXTRA)

  def test_assert_equal_fail_with_msg(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        asserts.assert_equal(1,
                             2,
                             msg=MSG_EXPECTED_EXCEPTION,
                             extras=MOCK_EXTRA)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.failed[0]
    self.assertEqual(actual_record.test_name, "test_func")
    expected_msg = "1 != 2 " + MSG_EXPECTED_EXCEPTION
    self.assertEqual(actual_record.details, expected_msg)
    self.assertEqual(actual_record.extras, MOCK_EXTRA)

  def test_assert_raises_pass(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        with asserts.assert_raises(SomeError, extras=MOCK_EXTRA):
          raise SomeError(MSG_EXPECTED_EXCEPTION)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.passed[0]
    self.assertEqual(actual_record.test_name, "test_func")
    self.assertIsNone(actual_record.details)
    self.assertIsNone(actual_record.extras)

  def test_assert_raises_fail_with_noop(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        with asserts.assert_raises(SomeError, extras=MOCK_EXTRA):
          pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.failed[0]
    self.assertEqual(actual_record.test_name, "test_func")
    self.assertEqual(actual_record.details, "SomeError not raised")
    self.assertEqual(actual_record.extras, MOCK_EXTRA)

  def test_assert_raises_fail_with_wrong_error(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        with asserts.assert_raises(SomeError, extras=MOCK_EXTRA):
          raise AttributeError(MSG_UNEXPECTED_EXCEPTION)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.error[0]
    self.assertEqual(actual_record.test_name, "test_func")
    self.assertEqual(actual_record.details, MSG_UNEXPECTED_EXCEPTION)
    self.assertIsNone(actual_record.extras)

  def test_assert_raises_regex_pass(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        with asserts.assert_raises_regex(SomeError,
                                         expected_regex=MSG_EXPECTED_EXCEPTION,
                                         extras=MOCK_EXTRA):
          raise SomeError(MSG_EXPECTED_EXCEPTION)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.passed[0]
    self.assertEqual(actual_record.test_name, "test_func")
    self.assertIsNone(actual_record.details)
    self.assertIsNone(actual_record.extras)

  def test_assert_raises_regex_fail_with_noop(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        with asserts.assert_raises_regex(SomeError,
                                         expected_regex=MSG_EXPECTED_EXCEPTION,
                                         extras=MOCK_EXTRA):
          pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.failed[0]
    self.assertEqual(actual_record.test_name, "test_func")
    self.assertEqual(actual_record.details, "SomeError not raised")
    self.assertEqual(actual_record.extras, MOCK_EXTRA)

  def test_assert_raises_fail_with_wrong_regex(self):
    wrong_msg = "ha"

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        with asserts.assert_raises_regex(SomeError,
                                         expected_regex=MSG_EXPECTED_EXCEPTION,
                                         extras=MOCK_EXTRA):
          raise SomeError(wrong_msg)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.failed[0]
    self.assertEqual(actual_record.test_name, "test_func")
    expected_details = ('"This is an expected exception." does not match '
                        '"%s"') % wrong_msg
    self.assertEqual(actual_record.details, expected_details)
    self.assertEqual(actual_record.extras, MOCK_EXTRA)

  def test_assert_raises_regex_fail_with_wrong_error(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        with asserts.assert_raises_regex(SomeError,
                                         expected_regex=MSG_EXPECTED_EXCEPTION,
                                         extras=MOCK_EXTRA):
          raise AttributeError(MSG_UNEXPECTED_EXCEPTION)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.error[0]
    self.assertEqual(actual_record.test_name, "test_func")
    self.assertEqual(actual_record.details, MSG_UNEXPECTED_EXCEPTION)
    self.assertIsNone(actual_record.extras)

  def test_explicit_pass(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        asserts.explicit_pass(MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
        never_call()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=["test_func"])
    actual_record = bt_cls.results.passed[0]
    self.assertEqual(actual_record.test_name, "test_func")
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertEqual(actual_record.extras, MOCK_EXTRA)

  def test_implicit_pass(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=["test_func"])
    actual_record = bt_cls.results.passed[0]
    self.assertEqual(actual_record.test_name, "test_func")
    self.assertIsNone(actual_record.details)
    self.assertIsNone(actual_record.extras)

  def test_skip(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        asserts.skip(MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
        never_call()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=["test_func"])
    actual_record = bt_cls.results.skipped[0]
    self.assertIsNotNone(actual_record.begin_time)
    self.assertIsNotNone(actual_record.end_time)
    self.assertEqual(actual_record.test_name, "test_func")
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertEqual(actual_record.extras, MOCK_EXTRA)

  def test_skip_if(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        asserts.skip_if(False, MSG_UNEXPECTED_EXCEPTION)
        asserts.skip_if(True, MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
        never_call()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=["test_func"])
    actual_record = bt_cls.results.skipped[0]
    self.assertIsNotNone(actual_record.begin_time)
    self.assertIsNotNone(actual_record.end_time)
    self.assertEqual(actual_record.test_name, "test_func")
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertEqual(actual_record.extras, MOCK_EXTRA)

  def test_skip_in_setup_test(self):

    class MockBaseTest(base_test.BaseTestClass):

      def setup_test(self):
        asserts.skip(MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)

      def test_func(self):
        never_call()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=["test_func"])
    actual_record = bt_cls.results.skipped[0]
    self.assertIsNotNone(actual_record.begin_time)
    self.assertIsNotNone(actual_record.end_time)
    self.assertEqual(actual_record.test_name, "test_func")
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertEqual(actual_record.extras, MOCK_EXTRA)

  def test_expect_true(self):
    must_call = mock.Mock()
    must_call2 = mock.Mock()

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        expects.expect_true(False, MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
        must_call('ha')

      def on_fail(self, record):
        must_call2('on_fail')

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=['test_func'])
    must_call.assert_called_once_with('ha')
    must_call2.assert_called_once_with('on_fail')
    actual_record = bt_cls.results.failed[0]
    self.assertEqual(actual_record.test_name, 'test_func')
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertEqual(actual_record.extras, MOCK_EXTRA)

  def test_expect_multiple_fails(self):
    must_call = mock.Mock()
    must_call2 = mock.Mock()

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        expects.expect_true(False, 'msg 1', extras='1')
        expects.expect_true(False, 'msg 2', extras='2')
        must_call('ha')

      def on_fail(self, record):
        must_call2('on_fail')

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=['test_func'])
    must_call.assert_called_once_with('ha')
    must_call2.assert_called_once_with('on_fail')
    actual_record = bt_cls.results.failed[0]
    self.assertEqual(actual_record.test_name, 'test_func')
    self.assertEqual(actual_record.details, 'msg 1')
    self.assertEqual(actual_record.extras, '1')
    self.assertEqual(len(actual_record.extra_errors), 1)
    second_error = list(actual_record.extra_errors.values())[0]
    self.assertEqual(second_error.details, 'msg 2')
    self.assertEqual(second_error.extras, '2')

  def test_expect_two_tests(self):
    """Errors in `expect` should not leak across tests.
    """
    must_call = mock.Mock()

    class MockBaseTest(base_test.BaseTestClass):

      def test_1(self):
        expects.expect_true(False, MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
        must_call('ha')

      def test_2(self):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=['test_1', 'test_2'])
    must_call.assert_called_once_with('ha')
    actual_record = bt_cls.results.failed[0]
    self.assertEqual(actual_record.test_name, 'test_1')
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertEqual(actual_record.extras, MOCK_EXTRA)
    another_record = bt_cls.results.passed[0]
    self.assertEqual(another_record.test_name, 'test_2')

  def test_expect_no_op(self):
    """Tests don't fail when expect is not triggered.
    """
    must_call = mock.Mock()

    class MockBaseTest(base_test.BaseTestClass):

      def test_1(self):
        expects.expect_true(True, MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
        must_call('ha')

      def test_2(self):
        expects.expect_false(False, MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
        must_call('ha')

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=['test_1', 'test_2'])
    must_call.assert_called_with('ha')
    self.assertEqual(len(bt_cls.results.passed), 2)

  @mock.patch('mobly.records.TestSummaryWriter.dump')
  def test_expect_in_setup_class(self, mock_dump):
    must_call = mock.Mock()
    must_call2 = mock.Mock()

    class MockBaseTest(base_test.BaseTestClass):

      def setup_class(self):
        expects.expect_true(False, MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
        must_call('ha')

      def test_func(self):
        pass

      def on_fail(self, record):
        must_call2('on_fail')

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    must_call.assert_called_once_with('ha')
    must_call2.assert_called_once_with('on_fail')
    actual_record = bt_cls.results.error[0]
    self.assertEqual(actual_record.test_name, 'setup_class')
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertEqual(actual_record.extras, MOCK_EXTRA)
    # Verify the class record is written out correctly.
    setup_class_dict = mock_dump.call_args_list[1][0][0]
    self.assertIsNotNone(setup_class_dict['Begin Time'])
    self.assertIsNotNone(setup_class_dict['End Time'])
    self.assertEqual(setup_class_dict['Test Name'], 'setup_class')

  @mock.patch('mobly.records.TestSummaryWriter.dump')
  def test_expect_in_setup_class_and_on_fail(self, mock_dump):
    must_call = mock.Mock()
    must_call2 = mock.Mock()

    class MockBaseTest(base_test.BaseTestClass):

      def setup_class(self):
        expects.expect_true(False, 'Failure in setup_class', extras=MOCK_EXTRA)
        must_call('ha')

      def test_func(self):
        pass

      def on_fail(self, record):
        expects.expect_true(False, 'Failure in on_fail', extras=MOCK_EXTRA)
        must_call2('on_fail')

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    must_call.assert_called_once_with('ha')
    must_call2.assert_called_once_with('on_fail')
    actual_record = bt_cls.results.error[0]
    self.assertEqual(actual_record.test_name, 'setup_class')
    self.assertEqual(actual_record.details, 'Failure in setup_class')
    self.assertEqual(actual_record.extras, MOCK_EXTRA)
    on_fail_error = next(iter(actual_record.extra_errors.values()))
    self.assertEqual(on_fail_error.details, 'Failure in on_fail')
    self.assertEqual(on_fail_error.extras, MOCK_EXTRA)
    # Verify the class record is written out correctly.
    setup_class_dict = mock_dump.call_args_list[1][0][0]
    self.assertIsNotNone(setup_class_dict['Begin Time'])
    self.assertIsNotNone(setup_class_dict['End Time'])
    self.assertEqual(setup_class_dict['Test Name'], 'setup_class')
    # Verify the on_fail error is recorded in summary result.
    extra_error_dict = next(iter(setup_class_dict['Extra Errors'].values()))
    self.assertEqual(extra_error_dict['Details'], 'Failure in on_fail')

  def test_expect_in_teardown_class(self):
    must_call = mock.Mock()

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        pass

      def teardown_class(self):
        expects.expect_true(False, MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
        must_call('ha')

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    must_call.assert_called_once_with('ha')
    actual_record = bt_cls.results.error[0]
    self.assertEqual(actual_record.test_name, 'teardown_class')
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertEqual(actual_record.extras, MOCK_EXTRA)

  def test_expect_in_setup_test(self):
    must_call = mock.Mock()
    must_call2 = mock.Mock()

    class MockBaseTest(base_test.BaseTestClass):

      def setup_test(self):
        expects.expect_true(False, MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
        must_call('ha')

      def test_func(self):
        pass

      def on_fail(self, record):
        must_call2('on_fail')

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    must_call.assert_called_once_with('ha')
    must_call2.assert_called_once_with('on_fail')
    actual_record = bt_cls.results.failed[0]
    self.assertEqual(actual_record.test_name, 'test_func')
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertEqual(actual_record.extras, MOCK_EXTRA)

  def test_expect_in_teardown_test(self):
    must_call = mock.Mock()
    must_call2 = mock.Mock()

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        pass

      def teardown_test(self):
        expects.expect_true(False, MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
        must_call('ha')

      def on_fail(self, record):
        must_call2('on_fail')

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=['test_func'])
    must_call.assert_called_once_with('ha')
    must_call2.assert_called_once_with('on_fail')
    actual_record = bt_cls.results.error[0]
    self.assertEqual(actual_record.test_name, 'test_func')
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertEqual(actual_record.extras, MOCK_EXTRA)

  def test_expect_false(self):
    must_call = mock.Mock()

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        expects.expect_false(True, MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
        must_call('ha')

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=['test_func'])
    must_call.assert_called_once_with('ha')
    actual_record = bt_cls.results.failed[0]
    self.assertEqual(actual_record.test_name, 'test_func')
    self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
    self.assertEqual(actual_record.extras, MOCK_EXTRA)

  def test_expect_equal(self):
    must_call = mock.Mock()

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        expects.expect_equal(1, 2, MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
        must_call('ha')

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=['test_func'])
    must_call.assert_called_once_with('ha')
    actual_record = bt_cls.results.failed[0]
    self.assertEqual(actual_record.test_name, 'test_func')
    self.assertEqual(actual_record.details, '1 != 2 ' + MSG_EXPECTED_EXCEPTION)
    self.assertEqual(actual_record.extras, MOCK_EXTRA)

  def test_expect_no_raises_default_msg(self):
    must_call = mock.Mock()

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        with expects.expect_no_raises(extras=MOCK_EXTRA):
          raise Exception(MSG_EXPECTED_EXCEPTION)
        must_call('ha')

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=['test_func'])
    must_call.assert_called_once_with('ha')
    actual_record = bt_cls.results.failed[0]
    self.assertEqual(actual_record.test_name, 'test_func')
    self.assertEqual(actual_record.details,
                     'Got an unexpected exception: %s' % MSG_EXPECTED_EXCEPTION)
    self.assertEqual(actual_record.extras, MOCK_EXTRA)

  def test_expect_no_raises_custom_msg(self):
    must_call = mock.Mock()
    msg = 'Some step unexpected failed'

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        with expects.expect_no_raises(message=msg, extras=MOCK_EXTRA):
          raise Exception(MSG_EXPECTED_EXCEPTION)
        must_call('ha')

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=['test_func'])
    must_call.assert_called_once_with('ha')
    actual_record = bt_cls.results.failed[0]
    self.assertEqual(actual_record.test_name, 'test_func')
    self.assertEqual(actual_record.details,
                     '%s: %s' % (msg, MSG_EXPECTED_EXCEPTION))
    self.assertEqual(actual_record.extras, MOCK_EXTRA)

  def test_expect_true_and_assert_true(self):
    """Error thrown by assert_true should be considered the termination.
    """
    must_call = mock.Mock()

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        expects.expect_true(False, MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
        must_call('ha')
        asserts.assert_true(False, 'failed from assert_true')

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=['test_func'])
    must_call.assert_called_once_with('ha')
    actual_record = bt_cls.results.failed[0]
    self.assertEqual(actual_record.test_name, 'test_func')
    self.assertEqual(actual_record.details, 'failed from assert_true')
    self.assertIsNone(actual_record.extras)

  def test_unpack_userparams_required(self):
    """Missing a required param should raise an error."""
    required = ["some_param"]
    bc = base_test.BaseTestClass(self.mock_test_cls_configs)
    bc.unpack_userparams(required)
    expected_value = self.mock_test_cls_configs.user_params["some_param"]
    self.assertEqual(bc.some_param, expected_value)

  def test_unpack_userparams_required_missing(self):
    """Missing a required param should raise an error."""
    required = ["something"]
    bc = base_test.BaseTestClass(self.mock_test_cls_configs)
    expected_msg = ('Missing required user param "%s" in test '
                    'configuration.') % required[0]
    with self.assertRaisesRegex(base_test.Error, expected_msg):
      bc.unpack_userparams(required)

  def test_unpack_userparams_optional(self):
    """If an optional param is specified, the value should be what's in the
    config.
    """
    opt = ["some_param"]
    bc = base_test.BaseTestClass(self.mock_test_cls_configs)
    bc.unpack_userparams(opt_param_names=opt)
    expected_value = self.mock_test_cls_configs.user_params["some_param"]
    self.assertEqual(bc.some_param, expected_value)

  def test_unpack_userparams_optional_with_default(self):
    """If an optional param is specified with a default value, and the
    param is not in the config, the value should be the default value.
    """
    bc = base_test.BaseTestClass(self.mock_test_cls_configs)
    bc.unpack_userparams(optional_thing="whatever")
    self.assertEqual(bc.optional_thing, "whatever")

  def test_unpack_userparams_default_overwrite_by_optional_param_list(self):
    """If an optional param is specified in kwargs, and the param is in the
    config, the value should be the one in the config.
    """
    bc = base_test.BaseTestClass(self.mock_test_cls_configs)
    bc.unpack_userparams(some_param="whatever")
    expected_value = self.mock_test_cls_configs.user_params["some_param"]
    self.assertEqual(bc.some_param, expected_value)

  def test_unpack_userparams_default_overwrite_by_required_param_list(self):
    """If an optional param is specified in kwargs, the param is in the
    required param list, and the param is not specified in the config, the
    param's alue should be the default value and there should be no error
    thrown.
    """
    bc = base_test.BaseTestClass(self.mock_test_cls_configs)
    bc.unpack_userparams(req_param_names=['a_kwarg_param'],
                         a_kwarg_param="whatever")
    self.assertEqual(bc.a_kwarg_param, "whatever")

  def test_unpack_userparams_optional_missing(self):
    """Missing an optional param should not raise an error."""
    opt = ["something"]
    bc = base_test.BaseTestClass(self.mock_test_cls_configs)
    bc.unpack_userparams(opt_param_names=opt)

  def test_unpack_userparams_basic(self):
    """Required and optional params are unpacked properly."""
    required = ["something"]
    optional = ["something_else"]
    configs = self.mock_test_cls_configs.copy()
    configs.user_params["something"] = 42
    configs.user_params["something_else"] = 53
    bc = base_test.BaseTestClass(configs)
    bc.unpack_userparams(req_param_names=required, opt_param_names=optional)
    self.assertEqual(bc.something, 42)
    self.assertEqual(bc.something_else, 53)

  def test_unpack_userparams_default_overwrite(self):
    default_arg_val = "haha"
    actual_arg_val = "wawa"
    arg_name = "arg1"
    configs = self.mock_test_cls_configs.copy()
    configs.user_params[arg_name] = actual_arg_val
    bc = base_test.BaseTestClass(configs)
    bc.unpack_userparams(opt_param_names=[arg_name], arg1=default_arg_val)
    self.assertEqual(bc.arg1, actual_arg_val)

  def test_unpack_userparams_default_None(self):
    bc = base_test.BaseTestClass(self.mock_test_cls_configs)
    bc.unpack_userparams(arg1="haha")
    self.assertEqual(bc.arg1, "haha")

  def test_setup_generated_tests_failure(self):
    """Test code path for setup_generated_tests failure.

    When setup_generated_tests fails, pre-execution calculation is
    incomplete and the number of tests requested is unknown. This is a
    fatal issue that blocks any test execution in a class.

    A class level error record is generated.
    Unlike `setup_class` failure, no test is considered "skipped" in this
    case as execution stage never started.
    """

    class MockBaseTest(base_test.BaseTestClass):

      def setup_generated_tests(self):
        raise Exception(MSG_EXPECTED_EXCEPTION)

      def logic(self, a, b):
        pass

      def test_foo(self):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    self.assertEqual(len(bt_cls.results.requested), 0)
    class_record = bt_cls.results.error[0]
    self.assertEqual(class_record.test_name, 'setup_generated_tests')
    self.assertEqual(bt_cls.results.skipped, [])

  def test_generate_tests_run(self):

    class MockBaseTest(base_test.BaseTestClass):

      def setup_generated_tests(self):
        self.generate_tests(test_logic=self.logic,
                            name_func=self.name_gen,
                            arg_sets=[(1, 2), (3, 4)])

      def name_gen(self, a, b):
        return 'test_%s_%s' % (a, b)

      def logic(self, a, b):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    self.assertEqual(len(bt_cls.results.requested), 2)
    self.assertEqual(len(bt_cls.results.passed), 2)
    self.assertIsNone(bt_cls.results.passed[0].uid)
    self.assertIsNone(bt_cls.results.passed[1].uid)
    self.assertEqual(bt_cls.results.passed[0].test_name, 'test_1_2')
    self.assertEqual(bt_cls.results.passed[1].test_name, 'test_3_4')

  def test_generate_tests_with_uid(self):

    class MockBaseTest(base_test.BaseTestClass):

      def setup_generated_tests(self):
        self.generate_tests(test_logic=self.logic,
                            name_func=self.name_gen,
                            uid_func=self.uid_logic,
                            arg_sets=[(1, 2), (3, 4)])

      def name_gen(self, a, b):
        return 'test_%s_%s' % (a, b)

      def uid_logic(self, a, b):
        return 'uid-%s-%s' % (a, b)

      def logic(self, a, b):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    self.assertEqual(bt_cls.results.passed[0].uid, 'uid-1-2')
    self.assertEqual(bt_cls.results.passed[1].uid, 'uid-3-4')

  def test_generate_tests_with_none_uid(self):

    class MockBaseTest(base_test.BaseTestClass):

      def setup_generated_tests(self):
        self.generate_tests(test_logic=self.logic,
                            name_func=self.name_gen,
                            uid_func=self.uid_logic,
                            arg_sets=[(1, 2), (3, 4)])

      def name_gen(self, a, b):
        return 'test_%s_%s' % (a, b)

      def uid_logic(self, a, b):
        if a == 1:
          return None
        return 'uid-3-4'

      def logic(self, a, b):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    self.assertIsNone(bt_cls.results.passed[0].uid)
    self.assertEqual(bt_cls.results.passed[1].uid, 'uid-3-4')

  def test_generate_tests_selected_run(self):

    class MockBaseTest(base_test.BaseTestClass):

      def setup_generated_tests(self):
        self.generate_tests(test_logic=self.logic,
                            name_func=self.name_gen,
                            arg_sets=[(1, 2), (3, 4)])

      def name_gen(self, a, b):
        return 'test_%s_%s' % (a, b)

      def logic(self, a, b):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=['test_3_4'])
    self.assertEqual(len(bt_cls.results.requested), 1)
    self.assertEqual(len(bt_cls.results.passed), 1)
    self.assertEqual(bt_cls.results.passed[0].test_name, 'test_3_4')

  def test_generate_tests_call_outside_of_setup_generated_tests(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_ha(self):
        self.generate_tests(test_logic=self.logic,
                            name_func=self.name_gen,
                            arg_sets=[(1, 2), (3, 4)])

      def name_gen(self, a, b):
        return 'test_%s_%s' % (a, b)

      def logic(self, a, b):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.error[0]
    utils.validate_test_result(bt_cls.results)
    self.assertEqual(actual_record.test_name, "test_ha")
    self.assertEqual(
        actual_record.details,
        '"generate_tests" cannot be called outside of setup_generated_tests')
    expected_summary = ("Error 1, Executed 1, Failed 0, Passed 0, "
                        "Requested 1, Skipped 0")
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)

  def test_generate_tests_dup_test_name(self):

    class MockBaseTest(base_test.BaseTestClass):

      def setup_generated_tests(self):
        self.generate_tests(test_logic=self.logic,
                            name_func=self.name_gen,
                            arg_sets=[(1, 2), (3, 4)])

      def name_gen(self, a, b):
        return 'ha'

      def logic(self, a, b):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.error[0]
    self.assertEqual(actual_record.test_name, "setup_generated_tests")
    self.assertEqual(
        actual_record.details,
        'During test generation of "logic": Test name "ha" already exists'
        ', cannot be duplicated!')
    expected_summary = ("Error 1, Executed 0, Failed 0, Passed 0, "
                        "Requested 0, Skipped 0")
    self.assertEqual(bt_cls.results.summary_str(), expected_summary)

  def test_write_user_data(self):
    content = {'a': 1}

    class MockBaseTest(base_test.BaseTestClass):

      def test_something(self):
        self.record_data(content)

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run(test_names=["test_something"])
    actual_record = bt_cls.results.passed[0]
    self.assertEqual(actual_record.test_name, "test_something")
    hit = False
    with io.open(self.summary_file, 'r', encoding='utf-8') as f:
      for c in yaml.safe_load_all(f):
        if c['Type'] != records.TestSummaryEntryType.USER_DATA.value:
          continue
        hit = True
        self.assertEqual(c['a'], content['a'])
        self.assertIsNotNone(c['timestamp'])
    self.assertTrue(hit)

  def test_record_controller_info(self):
    """Verifies that controller info is correctly recorded.

    1. Info added in test is recorded.
    2. Info of multiple controller types are recorded.
    """
    mock_test_config = self.mock_test_cls_configs.copy()
    mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
    mock_ctrlr_2_config_name = mock_second_controller.MOBLY_CONTROLLER_CONFIG_NAME
    my_config = [{'serial': 'xxxx', 'magic': 'Magic'}]
    mock_test_config.controller_configs[mock_ctrlr_config_name] = my_config
    mock_test_config.controller_configs[mock_ctrlr_2_config_name] = copy.copy(
        my_config)

    class ControllerInfoTest(base_test.BaseTestClass):
      """Registers two different controller types and modifies controller
      info at runtime.
      """

      def setup_class(self):
        self.register_controller(mock_controller)
        second_controller = self.register_controller(mock_second_controller)[0]
        # This should appear in recorded controller info.
        second_controller.set_magic('haha')

      def test_func(self):
        pass

    bt_cls = ControllerInfoTest(mock_test_config)
    bt_cls.run()
    info1 = bt_cls.results.controller_info[0]
    info2 = bt_cls.results.controller_info[1]
    self.assertNotEqual(info1, info2)
    self.assertEqual(info1.test_class, 'ControllerInfoTest')
    self.assertEqual(info1.controller_name, 'MagicDevice')
    self.assertEqual(info1.controller_info, [{'MyMagic': {'magic': 'Magic'}}])
    self.assertEqual(info2.test_class, 'ControllerInfoTest')
    self.assertEqual(info2.controller_name, 'AnotherMagicDevice')
    self.assertEqual(info2.controller_info, [{
        'MyOtherMagic': {
            'magic': 'Magic',
            'extra_magic': 'haha'
        }
    }])

  def test_record_controller_info_fail(self):
    mock_test_config = self.mock_test_cls_configs.copy()
    mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
    mock_ctrlr_2_config_name = mock_second_controller.MOBLY_CONTROLLER_CONFIG_NAME
    my_config = [{'serial': 'xxxx', 'magic': 'Magic'}]
    mock_test_config.controller_configs[mock_ctrlr_config_name] = my_config
    mock_test_config.controller_configs[mock_ctrlr_2_config_name] = copy.copy(
        my_config)

    class ControllerInfoTest(base_test.BaseTestClass):
      """Registers two different controller types and modifies controller
      info at runtime.
      """

      def setup_class(self):
        device = self.register_controller(mock_controller)[0]
        device.who_am_i = mock.MagicMock()
        device.who_am_i.side_effect = Exception('Some failure')
        second_controller = self.register_controller(mock_second_controller)[0]
        # This should appear in recorded controller info.
        second_controller.set_magic('haha')

      def test_func(self):
        pass

    bt_cls = ControllerInfoTest(mock_test_config)
    bt_cls.run()
    info = bt_cls.results.controller_info[0]
    self.assertEqual(len(bt_cls.results.controller_info), 1)
    self.assertEqual(info.test_class, 'ControllerInfoTest')
    self.assertEqual(info.controller_name, 'AnotherMagicDevice')
    self.assertEqual(info.controller_info, [{
        'MyOtherMagic': {
            'magic': 'Magic',
            'extra_magic': 'haha'
        }
    }])
    record = bt_cls.results.error[0]
    print(record.to_dict())
    self.assertEqual(record.test_name, 'clean_up')
    self.assertIsNotNone(record.begin_time)
    self.assertIsNotNone(record.end_time)
    expected_msg = ('Failed to collect controller info from '
                    'mock_controller: Some failure')
    self.assertEqual(record.details, expected_msg)

  def test_repeat_invalid_count(self):

    with self.assertRaisesRegex(
        ValueError, 'The `count` for `repeat` must be larger than 1, got "1".'):

      class MockBaseTest(base_test.BaseTestClass):

        @base_test.repeat(count=1)
        def test_something(self):
          pass

  def test_repeat_invalid_max_consec_error(self):

    with self.assertRaisesRegex(
        ValueError,
        re.escape('The `max_consecutive_error` (4) for `repeat` must be '
                  'smaller than `count` (3).')):

      class MockBaseTest(base_test.BaseTestClass):

        @base_test.repeat(count=3, max_consecutive_error=4)
        def test_something(self):
          pass

  def test_repeat(self):
    repeat_count = 3

    class MockBaseTest(base_test.BaseTestClass):

      @base_test.repeat(count=repeat_count)
      def test_something(self):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    self.assertEqual(repeat_count, len(bt_cls.results.passed))
    for i, record in enumerate(bt_cls.results.passed):
      self.assertEqual(record.test_name, f'test_something_{i}')

  def test_repeat_with_failures(self):
    repeat_count = 3
    mock_action = mock.MagicMock()
    mock_action.side_effect = [None, Exception('Something failed'), None]

    class MockBaseTest(base_test.BaseTestClass):

      @base_test.repeat(count=repeat_count)
      def test_something(self):
        mock_action()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    self.assertEqual(repeat_count, len(bt_cls.results.executed))
    self.assertEqual(1, len(bt_cls.results.error))
    self.assertEqual(2, len(bt_cls.results.passed))
    iter_2 = bt_cls.results.error[0]
    iter_1, iter_3 = bt_cls.results.passed
    self.assertEqual(iter_2.test_name, 'test_something_1')
    self.assertEqual(iter_1.test_name, 'test_something_0')
    self.assertEqual(iter_3.test_name, 'test_something_2')

  @mock.patch('logging.error')
  def test_repeat_with_consec_error_at_the_beginning_aborts_repeat(
      self, mock_logging_error):
    repeat_count = 5
    max_consec_error = 2
    mock_action = mock.MagicMock()
    mock_action.side_effect = [
        Exception('Error 1'),
        Exception('Error 2'),
        Exception('Error 3'),
    ]

    class MockBaseTest(base_test.BaseTestClass):

      @base_test.repeat(count=repeat_count,
                        max_consecutive_error=max_consec_error)
      def test_something(self):
        mock_action()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    mock_logging_error.assert_called_with(
        'Repeated test case "%s" has consecutively failed %d iterations, aborting'
        ' the remaining %d iterations.', 'test_something', 2, 3)
    self.assertEqual(max_consec_error, len(bt_cls.results.executed))
    self.assertEqual(max_consec_error, len(bt_cls.results.error))
    for i, record in enumerate(bt_cls.results.error):
      self.assertEqual(record.test_name, f'test_something_{i}')

  @mock.patch('logging.error')
  def test_repeat_with_consec_error_in_the_middle_aborts_repeat(
      self, mock_logging_error):
    repeat_count = 5
    max_consec_error = 2
    mock_action = mock.MagicMock()
    mock_action.side_effect = [
        None,
        None,
        Exception('Error 1'),
        Exception('Error 2'),
        Exception('Error 3'),
    ]

    class MockBaseTest(base_test.BaseTestClass):

      @base_test.repeat(count=repeat_count,
                        max_consecutive_error=max_consec_error)
      def test_something(self):
        mock_action()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    mock_logging_error.assert_called_with(
        'Repeated test case "%s" has consecutively failed %d iterations, aborting'
        ' the remaining %d iterations.', 'test_something', 2, 1)
    self.assertEqual(4, len(bt_cls.results.executed))
    self.assertEqual(2, len(bt_cls.results.error))
    self.assertEqual(2, len(bt_cls.results.passed))
    for i, record in enumerate(bt_cls.results.passed):
      self.assertEqual(record.test_name, f'test_something_{i}')

  def test_repeat_with_consec_error_does_not_abort_repeat(self):
    repeat_count = 5
    max_consec_error = 2
    mock_action = mock.MagicMock()
    mock_action.side_effect = [
        Exception('Error 1'),
        None,
        Exception('Error 2'),
        None,
        Exception('Error 3'),
    ]

    class MockBaseTest(base_test.BaseTestClass):

      @base_test.repeat(count=repeat_count,
                        max_consecutive_error=max_consec_error)
      def test_something(self):
        mock_action()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    self.assertEqual(repeat_count, len(bt_cls.results.executed))
    self.assertEqual(3, len(bt_cls.results.error))

  def test_retry_invalid_count(self):

    with self.assertRaisesRegex(
        ValueError,
        'The `max_count` for `retry` must be larger than 1, got "1".'):

      class MockBaseTest(base_test.BaseTestClass):

        @base_test.retry(max_count=1)
        def test_something(self):
          pass

  def test_retry_first_pass(self):
    max_count = 3
    mock_action = mock.MagicMock()

    class MockBaseTest(base_test.BaseTestClass):

      @base_test.retry(max_count=max_count)
      def test_something(self):
        mock_action()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    self.assertTrue(bt_cls.results.is_all_pass,
                    'This test run should be considered pass.')
    self.assertEqual(1, len(bt_cls.results.executed))
    self.assertEqual(1, len(bt_cls.results.passed))
    pass_record = bt_cls.results.passed[0]
    self.assertEqual(pass_record.test_name, f'test_something')
    self.assertEqual(0, len(bt_cls.results.error))

  def test_retry_last_pass(self):
    max_count = 3
    mock_action = mock.MagicMock()
    mock_action.side_effect = [Exception('Fail 1'), Exception('Fail 2'), None]

    class MockBaseTest(base_test.BaseTestClass):

      @base_test.retry(max_count=max_count)
      def test_something(self):
        mock_action()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    self.assertTrue(bt_cls.results.is_all_pass,
                    'This test run should be considered pass.')
    self.assertEqual(3, len(bt_cls.results.executed))
    self.assertEqual(1, len(bt_cls.results.passed))
    pass_record = bt_cls.results.passed[0]
    self.assertEqual(pass_record.test_name, f'test_something_retry_2')
    self.assertEqual(2, len(bt_cls.results.error))
    error_record_1, error_record_2 = bt_cls.results.error
    self.assertEqual(error_record_1.test_name, 'test_something')
    self.assertEqual(error_record_2.test_name, 'test_something_retry_1')
    self.assertIs(error_record_1, error_record_2.retry_parent)
    self.assertIs(error_record_2, pass_record.retry_parent)

  def test_retry_all_fail(self):
    max_count = 3
    mock_action = mock.MagicMock()
    mock_action.side_effect = [
        Exception('Fail 1'),
        Exception('Fail 2'),
        Exception('Fail 3')
    ]

    class MockBaseTest(base_test.BaseTestClass):

      @base_test.retry(max_count=max_count)
      def test_something(self):
        mock_action()

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    self.assertFalse(bt_cls.results.is_all_pass,
                     'This test run should be considered fail.')
    self.assertEqual(3, len(bt_cls.results.executed))
    self.assertEqual(3, len(bt_cls.results.error))
    error_record_1, error_record_2, error_record_3 = bt_cls.results.error
    self.assertEqual(error_record_1.test_name, 'test_something')
    self.assertEqual(error_record_2.test_name, 'test_something_retry_1')
    self.assertEqual(error_record_3.test_name, 'test_something_retry_2')
    self.assertIs(error_record_1, error_record_2.retry_parent)
    self.assertIs(error_record_2, error_record_3.retry_parent)

  def test_uid(self):

    class MockBaseTest(base_test.BaseTestClass):

      @records.uid('some-uid')
      def test_func(self):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.passed[0]
    self.assertEqual(actual_record.uid, 'some-uid')

  def test_uid_not_specified(self):

    class MockBaseTest(base_test.BaseTestClass):

      def test_func(self):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    actual_record = bt_cls.results.passed[0]
    self.assertIsNone(actual_record.uid)

  def test_uid_is_none(self):
    with self.assertRaisesRegex(ValueError, 'UID cannot be None.'):

      class MockBaseTest(base_test.BaseTestClass):

        @records.uid(None)
        def not_a_test(self):
          pass

  def test_repeat_with_uid(self):
    repeat_count = 3

    class MockBaseTest(base_test.BaseTestClass):

      @base_test.repeat(count=repeat_count)
      @records.uid('some-uid')
      def test_something(self):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    self.assertEqual(repeat_count, len(bt_cls.results.passed))
    for i, record in enumerate(bt_cls.results.passed):
      self.assertEqual(record.test_name, f'test_something_{i}')
      self.assertEqual(record.uid, 'some-uid')

  def test_uid_with_repeat(self):
    repeat_count = 3

    class MockBaseTest(base_test.BaseTestClass):

      @records.uid('some-uid')
      @base_test.repeat(count=repeat_count)
      def test_something(self):
        pass

    bt_cls = MockBaseTest(self.mock_test_cls_configs)
    bt_cls.run()
    self.assertEqual(repeat_count, len(bt_cls.results.passed))
    for i, record in enumerate(bt_cls.results.passed):
      self.assertEqual(record.test_name, f'test_something_{i}')
      self.assertEqual(record.uid, 'some-uid')

  def test_log_stage_always_logs_end_statement(self):
    instance = base_test.BaseTestClass(self.mock_test_cls_configs)
    instance.current_test_info = mock.Mock()
    instance.current_test_info.name = 'TestClass'

    class RecoverableError(Exception):
      pass

    with mock.patch('mobly.base_test.logging') as logging_patch:
      try:
        with instance._log_test_stage('stage'):
          raise RecoverableError('Force stage to fail.')
      except RecoverableError:
        pass

    logging_patch.debug.assert_called_with('[TestClass]#stage <<< END <<<')


if __name__ == "__main__":
  unittest.main()
