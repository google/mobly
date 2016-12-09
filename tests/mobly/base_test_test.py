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
import unittest

from mobly import asserts
from mobly import base_test
from mobly import signals
from mobly import test_runner

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
        self.mock_test_cls_configs = {
            'reporter': mock.MagicMock(),
            'log': mock.MagicMock(),
            'log_path': '/tmp',
            'cli_args': None,
            'user_params': {"some_param": "hahaha"}
        }
        self.mock_test_name = "test_something"

    def test_current_test_case_name(self):
        class MockBaseTest(base_test.BaseTestClass):
            def test_func(self):
                asserts.assert_true(self.current_test_name == "test_func", ("Got "
                                 "unexpected test name %s."
                                 ) % self.current_test_name)
        bt_cls = MockBaseTest(self.mock_test_cls_configs)
        bt_cls.run(test_names=["test_func"])
        actual_record = bt_cls.results.passed[0]
        self.assertEqual(actual_record.test_name, "test_func")
        self.assertIsNone(actual_record.details)
        self.assertIsNone(actual_record.extras)

    def test_self_tests_list(self):
        class MockBaseTest(base_test.BaseTestClass):
            def __init__(self, controllers):
                super(MockBaseTest, self).__init__(controllers)
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
                super(MockBaseTest, self).__init__(controllers)
                self.tests = ("not_a_test_something",)
            def not_a_test_something(self):
                pass
            def test_never(self):
                # This should not execute it's not on default test list.
                never_call()
        bt_cls = MockBaseTest(self.mock_test_cls_configs)
        expected_msg = ("Test case name not_a_test_something does not follow "
                        "naming convention test_\*, abort.")
        with self.assertRaisesRegexp(base_test.Error,
                                     expected_msg):
            bt_cls.run()

    def test_cli_test_selection_override_self_tests_list(self):
        class MockBaseTest(base_test.BaseTestClass):
            def __init__(self, controllers):
                super(MockBaseTest, self).__init__(controllers)
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
                super(MockBaseTest, self).__init__(controllers)
                self.tests = ("not_a_test_something",)
            def not_a_test_something(self):
                pass
            def test_never(self):
                # This should not execute it's not selected by cmd line input.
                never_call()
        bt_cls = MockBaseTest(self.mock_test_cls_configs)
        expected_msg = ("Test case name not_a_test_something does not follow "
                        "naming convention test_*, abort.")
        with self.assertRaises(base_test.Error, msg=expected_msg):
            bt_cls.run(test_names=["not_a_test_something"])

    def test_default_execution_of_all_tests(self):
        class MockBaseTest(base_test.BaseTestClass):
            def test_something(self):
                pass
            def not_a_test(self):
                # This should not execute its name doesn't follow test case
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
        expected_msg = ".* does not have test case test_something"
        with self.assertRaisesRegexp(base_test.Error, expected_msg):
            bt_cls.run(test_names=["test_something"])
        self.assertFalse(bt_cls.results.executed)

    def test_setup_class_fail_by_exception(self):
        call_check = mock.MagicMock()
        class MockBaseTest(base_test.BaseTestClass):
            def setup_class(self):
                raise Exception(MSG_EXPECTED_EXCEPTION)
            def test_something(self):
                # This should not execute because setup_class failed.
                never_call()
            def on_fail(self, test_name, begin_time):
                call_check("haha")
        bt_cls = MockBaseTest(self.mock_test_cls_configs)
        bt_cls.run()
        actual_record = bt_cls.results.failed[0]
        self.assertEqual(actual_record.test_name, "setup_class")
        self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
        self.assertIsNone(actual_record.extras)
        expected_summary = ("Error 0, Executed 1, Failed 1, Passed 0, "
                            "Requested 1, Skipped 0")
        self.assertEqual(bt_cls.results.summary_str(), expected_summary)
        call_check.assert_called_once_with("haha")

    def test_setup_test_fail_by_exception(self):
        class MockBaseTest(base_test.BaseTestClass):
            def setup_test(self):
                raise Exception(MSG_EXPECTED_EXCEPTION)
            def test_something(self):
                # This should not execute because setup_test failed.
                never_call()
        bt_cls = MockBaseTest(self.mock_test_cls_configs)
        bt_cls.run(test_names=["test_something"])
        actual_record = bt_cls.results.error[0]
        self.assertEqual(actual_record.test_name, self.mock_test_name)
        self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
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
        actual_record = bt_cls.results.failed[0]
        self.assertEqual(actual_record.test_name, self.mock_test_name)
        self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
        self.assertIsNone(actual_record.extras)
        expected_summary = ("Error 0, Executed 1, Failed 1, Passed 0, "
                            "Requested 1, Skipped 0")
        self.assertEqual(bt_cls.results.summary_str(), expected_summary)

    def test_teardown_test_assert_fail(self):
        class MockBaseTest(base_test.BaseTestClass):
            def teardown_test(self):
                asserts.assert_true(False, MSG_EXPECTED_EXCEPTION)
            def test_something(self):
                pass
        bt_cls = MockBaseTest(self.mock_test_cls_configs)
        bt_cls.run()
        actual_record = bt_cls.results.error[0]
        self.assertEqual(actual_record.test_name, self.mock_test_name)
        self.assertIsNone(actual_record.details)
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
        self.assertIsNone(actual_record.details)
        self.assertIsNone(actual_record.extras)
        expected_extra_error = {"teardown_test": MSG_EXPECTED_EXCEPTION}
        self.assertEqual(actual_record.extra_errors, expected_extra_error)
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
        expected_summary = ("Error 1, Executed 1, Failed 0, Passed 0, "
                            "Requested 1, Skipped 0")
        self.assertEqual(bt_cls.results.summary_str(), expected_summary)

    def test_teardown_test_executed_if_test_fails(self):
        my_mock = mock.MagicMock()
        class MockBaseTest(base_test.BaseTestClass):
            def teardown_test(self):
                my_mock("teardown_test")
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
            def on_fail(self, test_name, begin_time):
                my_mock("on_fail")
            def teardown_test(self):
                raise Exception(MSG_EXPECTED_EXCEPTION)
            def test_something(self):
                pass
        bt_cls = MockBaseTest(self.mock_test_cls_configs)
        bt_cls.run()
        my_mock.assert_called_once_with("on_fail")
        actual_record = bt_cls.results.error[0]
        self.assertEqual(actual_record.test_name, self.mock_test_name)
        self.assertIsNone(actual_record.details)
        self.assertIsNone(actual_record.extras)
        expected_summary = ("Error 1, Executed 1, Failed 0, Passed 0, "
                            "Requested 1, Skipped 0")
        self.assertEqual(bt_cls.results.summary_str(), expected_summary)

    def test_on_fail_executed_if_test_fails(self):
        my_mock = mock.MagicMock()
        class MockBaseTest(base_test.BaseTestClass):
            def on_fail(self, test_name, begin_time):
                my_mock("on_fail")
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

    def test_on_fail_executed_if_test_setup_fails_by_exception(self):
        my_mock = mock.MagicMock()
        class MockBaseTest(base_test.BaseTestClass):
            def setup_test(self):
                raise Exception(MSG_EXPECTED_EXCEPTION)
            def on_fail(self, test_name, begin_time):
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
        actual_record = bt_cls.results.error[0]
        self.assertIn('_on_fail', actual_record.extra_errors)
        self.assertEqual(actual_record.test_name, self.mock_test_name)
        self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
        self.assertIsNone(actual_record.extras)
        expected_summary = ("Error 1, Executed 1, Failed 0, Passed 0, "
                            "Requested 1, Skipped 0")
        self.assertEqual(bt_cls.results.summary_str(), expected_summary)

    def test_failure_in_procedure_functions_is_recorded(self):
        expected_msg = "Something failed in on_pass."
        class MockBaseTest(base_test.BaseTestClass):
            def on_pass(self, test_name, begin_time):
                raise Exception(expected_msg)
            def test_something(self):
                asserts.explicit_pass(MSG_EXPECTED_EXCEPTION)
        bt_cls = MockBaseTest(self.mock_test_cls_configs)
        bt_cls.run()
        actual_record = bt_cls.results.error[0]
        expected_extra_error = {'_on_pass': expected_msg}
        self.assertEqual(actual_record.extra_errors, expected_extra_error)
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
        self.assertEqual(actual_record.extra_errors["teardown_test"],
                         "Details=This is an expected exception., Extras=None")
        expected_summary = ("Error 1, Executed 1, Failed 0, Passed 0, "
                            "Requested 1, Skipped 0")
        self.assertEqual(bt_cls.results.summary_str(), expected_summary)

    def test_explicit_pass_but_teardown_test_raises_an_exception(self):
        """Test record result should be marked as ERROR as opposed to PASS.
        """
        class MockBaseTest(base_test.BaseTestClass):
            def teardown_test(self):
                asserts.assert_true(False, MSG_EXPECTED_EXCEPTION)
            def test_something(self):
                asserts.explicit_pass("Test Passed!")
        bt_cls = MockBaseTest(self.mock_test_cls_configs)
        bt_cls.run()
        actual_record = bt_cls.results.error[0]
        self.assertEqual(actual_record.test_name, self.mock_test_name)
        self.assertEqual(actual_record.details, "Test Passed!")
        self.assertIsNone(actual_record.extras)
        self.assertEqual(actual_record.extra_errors["teardown_test"],
                         "Details=This is an expected exception., Extras=None")
        expected_summary = ("Error 1, Executed 1, Failed 0, Passed 0, "
                            "Requested 1, Skipped 0")
        self.assertEqual(bt_cls.results.summary_str(), expected_summary)

    def test_on_pass_raise_exception(self):
        class MockBaseTest(base_test.BaseTestClass):
            def on_pass(self, test_name, begin_time):
                raise Exception(MSG_EXPECTED_EXCEPTION)
            def test_something(self):
                asserts.explicit_pass(MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
        bt_cls = MockBaseTest(self.mock_test_cls_configs)
        bt_cls.run()
        actual_record = bt_cls.results.error[0]
        self.assertEqual(actual_record.test_name, self.mock_test_name)
        self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
        self.assertEqual(actual_record.extras, MOCK_EXTRA)
        self.assertEqual(actual_record.extra_errors,
                         {'_on_pass': MSG_EXPECTED_EXCEPTION})
        expected_summary = ("Error 1, Executed 1, Failed 0, Passed 0, "
                            "Requested 1, Skipped 0")
        self.assertEqual(bt_cls.results.summary_str(), expected_summary)

    def test_on_fail_raise_exception(self):
        class MockBaseTest(base_test.BaseTestClass):
            def on_fail(self, test_name, begin_time):
                raise Exception(MSG_EXPECTED_EXCEPTION)
            def test_something(self):
                asserts.fail(MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
        bt_cls = MockBaseTest(self.mock_test_cls_configs)
        bt_cls.run()
        actual_record = bt_cls.results.error[0]
        self.assertEqual(bt_cls.results.failed, [])
        self.assertEqual(actual_record.test_name, self.mock_test_name)
        self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
        self.assertEqual(actual_record.extras, MOCK_EXTRA)
        self.assertEqual(actual_record.extra_errors,
                         {'_on_fail': MSG_EXPECTED_EXCEPTION})
        expected_summary = ("Error 1, Executed 1, Failed 0, Passed 0, "
                            "Requested 1, Skipped 0")
        self.assertEqual(bt_cls.results.summary_str(), expected_summary)

    def test_abort_class(self):
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
        self.assertEqual(bt_cls.results.passed[0].test_name,
                         "test_1")
        self.assertEqual(bt_cls.results.failed[0].details,
                         MSG_EXPECTED_EXCEPTION)
        self.assertEqual(bt_cls.results.summary_str(),
                         ("Error 0, Executed 2, Failed 1, Passed 1, "
                          "Requested 3, Skipped 0"))

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
                asserts.assert_true(False, MSG_EXPECTED_EXCEPTION,
                                 extras=MOCK_EXTRA)
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
                asserts.assert_equal(1, 2, msg=MSG_EXPECTED_EXCEPTION,
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

    def test_assert_raises_fail_with_noop(self):
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

    def test_assert_raises_fail_with_wrong_error(self):
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
                asserts.explicit_pass(MSG_EXPECTED_EXCEPTION,
                                      extras=MOCK_EXTRA)
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
        self.assertEqual(actual_record.test_name, "test_func")
        self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
        self.assertEqual(actual_record.extras, MOCK_EXTRA)

    def test_skip_if(self):
        class MockBaseTest(base_test.BaseTestClass):
            def test_func(self):
                asserts.skip_if(False, MSG_UNEXPECTED_EXCEPTION)
                asserts.skip_if(True, MSG_EXPECTED_EXCEPTION,
                                extras=MOCK_EXTRA)
                never_call()
        bt_cls = MockBaseTest(self.mock_test_cls_configs)
        bt_cls.run(test_names=["test_func"])
        actual_record = bt_cls.results.skipped[0]
        self.assertEqual(actual_record.test_name, "test_func")
        self.assertEqual(actual_record.details, MSG_EXPECTED_EXCEPTION)
        self.assertEqual(actual_record.extras, MOCK_EXTRA)

    def test_unpack_userparams_required(self):
        """Missing a required param should raise an error."""
        required = ["some_param"]
        bc = base_test.BaseTestClass(self.mock_test_cls_configs)
        bc.unpack_userparams(required)
        expected_value = self.mock_test_cls_configs["user_params"]["some_param"]
        self.assertEqual(bc.some_param, expected_value)

    def test_unpack_userparams_required_missing(self):
        """Missing a required param should raise an error."""
        required = ["something"]
        bc = base_test.BaseTestClass(self.mock_test_cls_configs)
        expected_msg = ("Missing required user param '%s' in test "
                        "configuration.") % required[0]
        with self.assertRaises(base_test.Error, msg=expected_msg):
            bc.unpack_userparams(required)

    def test_unpack_userparams_optional(self):
        """If an optional param is specified, the value should be what's in the
        config.
        """
        opt = ["some_param"]
        bc = base_test.BaseTestClass(self.mock_test_cls_configs)
        bc.unpack_userparams(opt_param_names=opt)
        expected_value = self.mock_test_cls_configs["user_params"]["some_param"]
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
        expected_value = self.mock_test_cls_configs["user_params"]["some_param"]
        self.assertEqual(bc.some_param, expected_value)

    def test_unpack_userparams_default_overwrite_by_required_param_list(self):
        """If an optional param is specified in kwargs, the param is in the
        required param list, and the param is not specified in the config, the
        param's alue should be the default value and there should be no error
        thrown.
        """
        bc = base_test.BaseTestClass(self.mock_test_cls_configs)
        bc.unpack_userparams(req_param_names=['a_kwarg_param'], a_kwarg_param="whatever")
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
        configs = dict(self.mock_test_cls_configs)
        configs["user_params"]["something"] = 42
        configs["user_params"]["something_else"] = 53
        bc = base_test.BaseTestClass(configs)
        bc.unpack_userparams(req_param_names=required,
                             opt_param_names=optional)
        self.assertEqual(bc.something, 42)
        self.assertEqual(bc.something_else, 53)

    def test_unpack_userparams_default_overwrite(self):
        default_arg_val = "haha"
        actual_arg_val = "wawa"
        arg_name = "arg1"
        configs = dict(self.mock_test_cls_configs)
        configs["user_params"][arg_name] = actual_arg_val
        bc = base_test.BaseTestClass(configs)
        bc.unpack_userparams(opt_param_names=[arg_name],
                             arg1=default_arg_val)
        self.assertEqual(bc.arg1, actual_arg_val)

    def test_unpack_userparams_default_None(self):
        bc = base_test.BaseTestClass(self.mock_test_cls_configs)
        bc.unpack_userparams(arg1="haha")
        self.assertEqual(bc.arg1, "haha")

    def test_generated_tests(self):
        """Execute code paths for generated test cases.

        Three test cases are generated, each of them produces a different
        result: one pass, one fail, and one skip.

        This test verifies that the exact three tests are executed and their
        results are reported correctly.
        """
        static_arg = "haha"
        static_kwarg = "meh"
        itrs = ["pass", "fail", "skip"]
        class MockBaseTest(base_test.BaseTestClass):
            def name_gen(self, setting, arg, special_arg=None):
                return "test_%s_%s" % (setting, arg)
            def logic(self, setting, arg, special_arg=None):
                asserts.assert_true(setting in itrs,
                                 ("%s is not in acceptable settings range %s"
                                 ) % (setting, itrs))
                asserts.assert_true(arg == static_arg,
                                 "Expected %s, got %s" % (static_arg, arg))
                asserts.assert_true(arg == static_arg,
                                 "Expected %s, got %s" % (static_kwarg,
                                                          special_arg))
                if setting == "pass":
                    asserts.explicit_pass(MSG_EXPECTED_EXCEPTION,
                                          extras=MOCK_EXTRA)
                elif setting == "fail":
                    asserts.fail(MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
                elif setting == "skip":
                    asserts.skip(MSG_EXPECTED_EXCEPTION, extras=MOCK_EXTRA)
            @signals.generated_test
            def test_func(self):
                self.run_generated_testcases(
                    test_func=self.logic,
                    settings=itrs,
                    args=(static_arg,),
                    name_func=self.name_gen
                )
        bt_cls = MockBaseTest(self.mock_test_cls_configs)
        bt_cls.run(test_names=["test_func"])
        self.assertEqual(len(bt_cls.results.requested), 3)
        pass_record = bt_cls.results.passed[0]
        self.assertEqual(pass_record.test_name, "test_pass_%s" % static_arg)
        self.assertEqual(pass_record.details, MSG_EXPECTED_EXCEPTION)
        self.assertEqual(pass_record.extras, MOCK_EXTRA)
        skip_record = bt_cls.results.skipped[0]
        self.assertEqual(skip_record.test_name, "test_skip_%s" % static_arg)
        self.assertEqual(skip_record.details, MSG_EXPECTED_EXCEPTION)
        self.assertEqual(skip_record.extras, MOCK_EXTRA)
        fail_record = bt_cls.results.failed[0]
        self.assertEqual(fail_record.test_name, "test_fail_%s" % static_arg)
        self.assertEqual(fail_record.details, MSG_EXPECTED_EXCEPTION)
        self.assertEqual(fail_record.extras, MOCK_EXTRA)

if __name__ == "__main__":
   unittest.main()