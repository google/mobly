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

"""This module is where all the record definitions and record containers live.
"""

import json
import logging
import pprint

from mobly import signals
from mobly import utils


class TestResultEnums(object):
    """Enums used for TestResultRecord class.

    Includes the tokens to mark test result with, and the string names for each
    field in TestResultRecord.
    """

    RECORD_NAME = "Test Name"
    RECORD_CLASS = "Test Class"
    RECORD_BEGIN_TIME = "Begin Time"
    RECORD_END_TIME = "End Time"
    RECORD_RESULT = "Result"
    RECORD_UID = "UID"
    RECORD_EXTRAS = "Extras"
    RECORD_EXTRA_ERRORS = "Extra Errors"
    RECORD_DETAILS = "Details"
    TEST_RESULT_PASS = "PASS"
    TEST_RESULT_FAIL = "FAIL"
    TEST_RESULT_SKIP = "SKIP"
    TEST_RESULT_ERROR = "ERROR"


class TestResultRecord(object):
    """A record that holds the information of a test case execution.

    Attributes:
        test_name: A string representing the name of the test case.
        begin_time: Epoch timestamp of when the test case started.
        end_time: Epoch timestamp of when the test case ended.
        self.uid: Unique identifier of a test case.
        self.result: Test result, PASS/FAIL/SKIP.
        self.extras: User defined extra information of the test result.
        self.details: A string explaining the details of the test case.
    """

    def __init__(self, t_name, t_class=None):
        self.test_name = t_name
        self.test_class = t_class
        self.begin_time = None
        self.end_time = None
        self.uid = None
        self.result = None
        self.extras = None
        self.details = None
        self.extra_errors = {}

    def test_begin(self):
        """Call this when the test case it records begins execution.

        Sets the begin_time of this record.
        """
        self.begin_time = utils.get_current_epoch_time()

    def _test_end(self, result, e):
        """Class internal function to signal the end of a test case execution.

        Args:
            result: One of the TEST_RESULT enums in TestResultEnums.
            e: A test termination signal (usually an exception object). It can
                be any exception instance or of any subclass of
                mobly.signals.TestSignal.
        """
        self.end_time = utils.get_current_epoch_time()
        self.result = result
        if self.extra_errors:
            self.result = TestResultEnums.TEST_RESULT_ERROR
        if isinstance(e, signals.TestSignal):
            self.details = e.details
            self.extras = e.extras
        elif e:
            self.details = str(e)

    def test_pass(self, e=None):
        """To mark the test as passed in this record.

        Args:
            e: An instance of mobly.signals.TestPass.
        """
        self._test_end(TestResultEnums.TEST_RESULT_PASS, e)

    def test_fail(self, e=None):
        """To mark the test as failed in this record.

        Only test_fail does instance check because we want "assert xxx" to also
        fail the test same way assert_true does.

        Args:
            e: An exception object. It can be an instance of AssertionError or
                mobly.base_test.TestFailure.
        """
        self._test_end(TestResultEnums.TEST_RESULT_FAIL, e)

    def test_skip(self, e=None):
        """To mark the test as skipped in this record.

        Args:
            e: An instance of mobly.signals.TestSkip.
        """
        self._test_end(TestResultEnums.TEST_RESULT_SKIP, e)

    def test_error(self, e=None):
        """To mark the test as error in this record.

        Args:
            e: An exception object.
        """
        self._test_end(TestResultEnums.TEST_RESULT_ERROR, e)

    def add_error(self, tag, e):
        """Add extra error happened during a test mark the test result as
        ERROR.

        If an error is added the test record, the record's result is equivalent
        to the case where an uncaught exception happened.

        Args:
            tag: A string describing where this error came from, e.g. 'on_pass'.
            e: An exception object.
        """
        self.result = TestResultEnums.TEST_RESULT_ERROR
        self.extra_errors[tag] = str(e)

    def __str__(self):
        d = self.to_dict()
        l = ["%s = %s" % (k, v) for k, v in d.items()]
        s = ', '.join(l)
        return s

    def __repr__(self):
        """This returns a short string representation of the test record."""
        t = utils.epoch_to_human_time(self.begin_time)
        return "%s %s %s" % (t, self.test_name, self.result)

    def to_dict(self):
        """Gets a dictionary representating the content of this class.

        Returns:
            A dictionary representating the content of this class.
        """
        d = {}
        d[TestResultEnums.RECORD_NAME] = self.test_name
        d[TestResultEnums.RECORD_CLASS] = self.test_class
        d[TestResultEnums.RECORD_BEGIN_TIME] = self.begin_time
        d[TestResultEnums.RECORD_END_TIME] = self.end_time
        d[TestResultEnums.RECORD_RESULT] = self.result
        d[TestResultEnums.RECORD_UID] = self.uid
        d[TestResultEnums.RECORD_EXTRAS] = self.extras
        d[TestResultEnums.RECORD_DETAILS] = self.details
        d[TestResultEnums.RECORD_EXTRA_ERRORS] = self.extra_errors
        return d

    def json_str(self):
        """Converts this test record to a string in json format.

        Format of the json string is:
            {
                'Test Name': <test name>,
                'Begin Time': <epoch timestamp>,
                'Details': <details>,
                ...
            }

        Returns:
            A json-format string representing the test record.
        """
        return json.dumps(self.to_dict())


class TestResult(object):
    """A class that contains metrics of a test run.

    This class is essentially a container of TestResultRecord objects.

    Attributes:
        self.requested: A list of strings, each is the name of a test requested
            by user.
        self.failed: A list of records for tests failed.
        self.executed: A list of records for tests that were actually executed.
        self.passed: A list of records for tests passed.
        self.skipped: A list of records for tests skipped.
        self.error: A list of records for tests with error result token.
    """

    def __init__(self):
        self.requested = []
        self.failed = []
        self.executed = []
        self.passed = []
        self.skipped = []
        self.error = []
        self.controller_info = {}

    def __add__(self, r):
        """Overrides '+' operator for TestResult class.

        The add operator merges two TestResult objects by concatenating all of
        their lists together.

        Args:
            r: another instance of TestResult to be added

        Returns:
            A TestResult instance that's the sum of two TestResult instances.
        """
        if not isinstance(r, TestResult):
            raise TypeError("Operand %s of type %s is not a TestResult." %
                            (r, type(r)))
        sum_result = TestResult()
        for name in sum_result.__dict__:
            r_value = getattr(r, name)
            l_value = getattr(self, name)
            if isinstance(r_value, list):
                setattr(sum_result, name, l_value + r_value)
            elif isinstance(r_value, dict):
                # '+' operator for TestResult is only valid when multiple
                # TestResult objs were created in the same test run, which means
                # the controller info would be the same across all of them.
                # TODO(angli): have a better way to validate this situation.
                setattr(sum_result, name, l_value)
        return sum_result

    def add_record(self, record):
        """Adds a test record to test result.

        A record is considered executed once it's added to the test result.

        Args:
            record: A test record object to add.
        """
        self.executed.append(record)
        if record.result == TestResultEnums.TEST_RESULT_FAIL:
            self.failed.append(record)
        elif record.result == TestResultEnums.TEST_RESULT_SKIP:
            self.skipped.append(record)
        elif record.result == TestResultEnums.TEST_RESULT_PASS:
            self.passed.append(record)
        else:
            self.error.append(record)

    def add_controller_info(self, name, info):
        try:
            json.dumps(info)
        except TypeError:
            logging.warning(("Controller info for %s is not JSON serializable!"
                             " Coercing it to string.") % name)
            self.controller_info[name] = str(info)
            return
        self.controller_info[name] = info

    def fail_class(self, test_record):
        """Add a record to indicate a test class setup has failed and no test
        in the class was executed.

        Args:
            test_record: A TestResultRecord object for the test class.
        """
        self.executed.append(test_record)
        self.failed.append(test_record)

    @property
    def is_all_pass(self):
        """True if no tests failed or threw errors, False otherwise."""
        num_of_failures = len(self.failed) + len(self.error)
        if num_of_failures == 0:
            return True
        return False

    def json_str(self):
        """Converts this test result to a string in json format.

        Format of the json string is:
            {
                "Results": [
                    {<executed test record 1>},
                    {<executed test record 2>},
                    ...
                ],
                "Summary": <summary dict>
            }

        Returns:
            A json-format string representing the test results.
        """
        d = {}
        d["ControllerInfo"] = self.controller_info
        d["Results"] = [record.to_dict() for record in self.executed]
        d["Summary"] = self.summary_dict()
        json_str = json.dumps(d, indent=4, sort_keys=True)
        return json_str

    def summary_str(self):
        """Gets a string that summarizes the stats of this test result.

        The summary rovides the counts of how many test cases fall into each
        category, like "Passed", "Failed" etc.

        Format of the string is:
            Requested <int>, Executed <int>, ...

        Returns:
            A summary string of this test result.
        """
        l = ["%s %d" % (k, v) for k, v in self.summary_dict().items()]
        # Sort the list so the order is the same every time.
        msg = ", ".join(sorted(l))
        return msg

    def summary_dict(self):
        """Gets a dictionary that summarizes the stats of this test result.

        The summary rovides the counts of how many test cases fall into each
        category, like "Passed", "Failed" etc.

        Returns:
            A dictionary with the stats of this test result.
        """
        d = {}
        d["Requested"] = len(self.requested)
        d["Executed"] = len(self.executed)
        d["Passed"] = len(self.passed)
        d["Failed"] = len(self.failed)
        d["Skipped"] = len(self.skipped)
        d["Error"] = len(self.error)
        return d
