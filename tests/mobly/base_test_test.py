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

import os
import mock
import shutil
import tempfile

from future.tests.base import unittest

from mobly import asserts
from mobly import base_test
from mobly import config_parser
from mobly import expects
from mobly import signals

from tests.lib import utils

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
        self.mock_test_cls_configs.summary_writer = mock.Mock()
        self.mock_test_cls_configs.log_path = self.tmp_dir
        self.mock_test_cls_configs.user_params = {"some_param": "hahaha"}
        self.mock_test_cls_configs.reporter = mock.MagicMock()
        self.mock_test_name = "test_something"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_current_test_name(self):
        class MockBaseTest(base_test.BaseTestClass):
            def test_func(self):
                asserts.assert_true(
                    self.current_test_name == "test_func",
                    ("Got "
                     "unexpected test name %s.") % self.current_test_name)

        bt_cls = MockBaseTest(self.mock_test_cls_configs)
        bt_cls.run(test_names=["test_func"])
        actual_record = bt_cls.results.passed[0]
        self.assertEqual(actual_record.test_name, "test_func")
        self.assertIsNone(actual_record.details)
        self.assertIsNone(actual_record.extras)

    def test_current_test_info(self):
        class MockBaseTest(base_test.BaseTestClass):
            def test_func(self):
                asserts.assert_true(self.current_test_info.name == 'test_func',
                                    'Got unexpected test name %s.' %
                                    self.current_test_info.name)
                output_path = self.current_test_info.output_path
                asserts.assert_true(
                    os.path.exists(output_path), 'test output path missing')

        bt_cls = MockBaseTest(self.mock_test_cls_configs)
        bt_cls.run(test_names=['test_func'])
        actual_record = bt_cls.results.passed[0]
        self.assertEqual(actual_record.test_name, 'test_func')
        self.assertIsNone(actual_record.details)
        self.assertIsNone(actual_record.extras)

    def test_self_tests_list(self):
        class MockBaseTest(base_test.BaseTestClass):
            def __init__(self, controllers):
                super(MockBaseTest, self).__init__(controllers)
                self.tests = ("test_something", )

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
                super(MockBaseTest, self).__init__(controllers)
                self.tests = ("not_a_test_something", )

            def not_a_test_something(self):
                pass

            def test_never(self):
                # This should not execute it's not on default test list.
                never_call()

        bt_cls = MockBaseTest(self.mock_test_cls_configs)
        expected_msg = (
            'Test method name not_a_test_something does not follow '
            'naming convention test_\*, abort.')
        with self.assertRaisesRegex(base_test.Error, expected_msg):
            bt_cls.run()

    def test_cli_test_selection_override_self_tests_list(self):
        class MockBaseTest(base_test.BaseTestClass):
            def __init__(self, controllers):
                super(MockBaseTest, self).__init__(controllers)
                self.tests = ("test_never", )

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
                super(MockBaseTest, self).__init__(controllers)
                self.tests = ("not_a_test_something", )

            def not_a_test_something(self):
                pass

            def test_never(self):
                # This should not execute it's not selected by cmd line input.
                never_call()

        bt_cls = MockBaseTest(self.mock_test_cls_configs)
        expected_msg = (
            'Test method name not_a_test_something does not follow '
            'naming convention test_\*, abort.')
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
        bt_cls.run(test_names=["test_something"])
        actual_record = bt_cls.results.passed[0]
        self.assertEqual(actual_record.test_name, "test_something")

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
        class MockBaseTest(base_test.BaseTestClass):
            def test_something(self):
                pass

            def teardown_class(self):
                raise Exception(MSG_EXPECTED_EXCEPTION)

        bt_cls = MockBaseTest(self.mock_test_cls_configs)
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
        self.assertTrue('in setup_test\n    '
                        'raise Exception(MSG_EXPECTED_EXCEPTION)\n'
                        'Exception: This is an expected exception.\n' in
                        actual_record.stacktrace)
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
                assert self.current_test_name == 'test_something'
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
        self.assertEqual(on_fail_mock.record.test_name,
                         actual_record.test_name)
        self.assertEqual(on_fail_mock.record.begin_time,
                         actual_record.begin_time)
        self.assertEqual(on_fail_mock.record.end_time, actual_record.end_time)
        self.assertEqual(on_fail_mock.record.stacktrace,
                         actual_record.stacktrace)
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

    def test_on_fail_executed_if_test_setup_fails_by_exception(self):
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

    def test_failure_to_call_procedure_function_is_recorded(self):
        class MockBaseTest(base_test.BaseTestClass):
            def on_fail(self):
                pass

            def test_something(self):
                asserts.assert_true(False, MSG_EXPECTED_EXCEPTION)

        bt_cls = MockBaseTest(self.mock_test_cls_configs)
        bt_cls.run()
        actual_record = bt_cls.results.failed[0]
        self.assertIn('_on_fail', actual_record.extra_errors)
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
        self.assertEqual(actual_record.extra_errors['_on_pass'].details,
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
        """If no termination singal is specified, use the first extra error as
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
                asserts.explicit_pass(
                    MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)

        bt_cls = MockBaseTest(self.mock_test_cls_configs)
        bt_cls.run()
        actual_record = bt_cls.results.error[0]
        self.assertEqual(actual_record.test_name, self.mock_test_name)
        self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
        self.assertEqual(actual_record.extras, MOCK_EXTRA)
        self.assertEqual(actual_record.extra_errors['_on_pass'].details,
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
        self.assertEqual(actual_record.extra_errors['_on_fail'].details,
                         MSG_EXPECTED_EXCEPTION)
        expected_summary = ("Error 0, Executed 1, Failed 1, Passed 0, "
                            "Requested 1, Skipped 0")
        self.assertEqual(bt_cls.results.summary_str(), expected_summary)

    def test_abort_setup_class(self):
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
        self.assertEqual(bt_cls.results.failed[0].details,
                         MSG_EXPECTED_EXCEPTION)
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
                asserts.assert_true(
                    False, MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
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
                asserts.assert_equal(
                    1, 2, msg=MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)

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
                with asserts.assert_raises_regex(
                        SomeError,
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
                with asserts.assert_raises_regex(
                        SomeError,
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
                with asserts.assert_raises_regex(
                        SomeError,
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
                with asserts.assert_raises_regex(
                        SomeError,
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
                asserts.explicit_pass(
                    MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
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
                asserts.skip_if(
                    True, MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
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
                expects.expect_true(
                    False, MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
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
                expects.expect_true(
                    False, MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
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
                expects.expect_true(
                    True, MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
                must_call('ha')

            def test_2(self):
                expects.expect_false(
                    False, MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
                must_call('ha')

        bt_cls = MockBaseTest(self.mock_test_cls_configs)
        bt_cls.run(test_names=['test_1', 'test_2'])
        must_call.assert_called_with('ha')
        self.assertEqual(len(bt_cls.results.passed), 2)

    def test_expect_in_teardown_test(self):
        must_call = mock.Mock()
        must_call2 = mock.Mock()

        class MockBaseTest(base_test.BaseTestClass):
            def test_func(self):
                pass

            def teardown_test(self):
                expects.expect_true(
                    False, MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
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
                expects.expect_false(
                    True, MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
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
                expects.expect_equal(
                    1, 2, MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
                must_call('ha')

        bt_cls = MockBaseTest(self.mock_test_cls_configs)
        bt_cls.run(test_names=['test_func'])
        must_call.assert_called_once_with('ha')
        actual_record = bt_cls.results.failed[0]
        self.assertEqual(actual_record.test_name, 'test_func')
        self.assertEqual(actual_record.details,
                         '1 != 2 ' + MSG_EXPECTED_EXCEPTION)
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
        self.assertEqual(
            actual_record.details,
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
                expects.expect_true(
                    False, MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
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
        bc.unpack_userparams(
            req_param_names=['a_kwarg_param'], a_kwarg_param="whatever")
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
        bc.unpack_userparams(
            req_param_names=required, opt_param_names=optional)
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

    def test_generate_tests_run(self):
        class MockBaseTest(base_test.BaseTestClass):
            def setup_generated_tests(self):
                self.generate_tests(
                    test_logic=self.logic,
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
        self.assertEqual(bt_cls.results.passed[0].test_name, 'test_1_2')
        self.assertEqual(bt_cls.results.passed[1].test_name, 'test_3_4')

    def test_generate_tests_selected_run(self):
        class MockBaseTest(base_test.BaseTestClass):
            def setup_generated_tests(self):
                self.generate_tests(
                    test_logic=self.logic,
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
                self.generate_tests(
                    test_logic=self.logic,
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
            '"generate_tests" cannot be called outside of setup_generated_tests'
        )
        expected_summary = ("Error 1, Executed 1, Failed 0, Passed 0, "
                            "Requested 1, Skipped 0")
        self.assertEqual(bt_cls.results.summary_str(), expected_summary)

    def test_generate_tests_dup_test_name(self):
        class MockBaseTest(base_test.BaseTestClass):
            def setup_generated_tests(self):
                self.generate_tests(
                    test_logic=self.logic,
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
            'Test name "ha" already exists, cannot be duplicated!')
        expected_summary = ("Error 1, Executed 0, Failed 0, Passed 0, "
                            "Requested 0, Skipped 0")
        self.assertEqual(bt_cls.results.summary_str(), expected_summary)


if __name__ == "__main__":
    unittest.main()
