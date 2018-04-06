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
"""This module has classes for test result collection, and test result output.
"""

import collections
import itertools
import copy
import enum
import json
import logging
import pprint
import sys
import threading
import traceback
import yaml

from mobly import signals
from mobly import utils

# File names for the output files.
OUTPUT_FILE_INFO_LOG = 'test_log.INFO'
OUTPUT_FILE_DEBUG_LOG = 'test_log.DEBUG'
OUTPUT_FILE_SUMMARY = 'test_summary.yaml'


class TestSummaryEntryType(enum.Enum):
    """Constants used to identify the type of entries in test summary file.

    Test summary file contains multiple yaml documents. In order to parse this
    file efficiently, the write adds the type of each entry when it writes the
    entry to the file.

    The idea is similar to how `TestResult.json_str` categorizes different
    sections of a `TestResult` object in the serialized format.
    """
    # A list of all the tests requested for a test run.
    # This is dumped at the beginning of a summary file so we know what was
    # requested in case the test is interrupted and the final summary is not
    # created.
    TEST_NAME_LIST = 'TestNameList'
    # Records of test results.
    RECORD = 'Record'
    # A summary of the test run stats, e.g. how many test failed.
    SUMMARY = 'Summary'
    # Information on the controllers used in the test.
    CONTROLLER_INFO = 'ControllerInfo'
    # Additional data added by users during test.
    # This can be added at any point in the test, so do not assume the location
    # of these entries in the summary file.
    USER_DATA = 'UserData'


class Error(Exception):
    """Raised for errors in records."""


class TestSummaryWriter(object):
    """Writer for the test result summary file of a test run.

    For each test run, a writer is created to stream test results to the
    summary file on disk.

    The serialization and writing of the `TestResult` object is intentionally
    kept out of `TestResult` class and put in this class. Because `TestResult`
    can be operated on by suites, like `+` operation, and it is difficult to
    guarantee the consistency between `TestResult` in memory and the files on
    disk. Also, this separation makes it easier to provide a more generic way
    for users to consume the test summary, like via a database instead of a
    file.
    """

    def __init__(self, path):
        self._path = path
        self._lock = threading.Lock()

    def __copy__(self):
        """Make a "copy" of the object.

        The writer is merely a wrapper object for a path with a global lock for
        write operation. So we simply return the object itself for copy
        operations.
        """
        return self

    def __deepcopy__(self, *args):
        return self.__copy__()

    def dump(self, content, entry_type):
        """Dumps a dictionary as a yaml document to the summary file.

        Each call to this method dumps a separate yaml document to the same
        summary file associated with a test run.

        The content of the dumped dictionary has an extra field `TYPE` that
        specifies the type of each yaml document, which is the flag for parsers
        to identify each document.

        Args:
            content: dictionary, the content to serialize and write.
            entry_type: a member of enum TestSummaryEntryType.

        Raises:
            recoreds.Error: An invalid entry type is passed in.
        """
        new_content = copy.deepcopy(content)
        new_content['Type'] = entry_type.value
        # Both user code and Mobly code can trigger this dump, hence the lock.
        with self._lock:
            # Use safe_dump here to avoid language-specific tags in final output.
            with open(self._path, 'a') as f:
                yaml.safe_dump(
                    new_content,
                    f,
                    explicit_start=True,
                    allow_unicode=True,
                    indent=4)


class TestResultEnums(object):
    """Enums used for TestResultRecord class.

    Includes the tokens to mark test result with, and the string names for each
    field in TestResultRecord.
    """

    RECORD_NAME = 'Test Name'
    RECORD_CLASS = 'Test Class'
    RECORD_BEGIN_TIME = 'Begin Time'
    RECORD_END_TIME = 'End Time'
    RECORD_RESULT = 'Result'
    RECORD_UID = 'UID'
    RECORD_EXTRAS = 'Extras'
    RECORD_EXTRA_ERRORS = 'Extra Errors'
    RECORD_DETAILS = 'Details'
    RECORD_STACKTRACE = 'Stacktrace'
    RECORD_POSITION = 'Position'
    TEST_RESULT_PASS = 'PASS'
    TEST_RESULT_FAIL = 'FAIL'
    TEST_RESULT_SKIP = 'SKIP'
    TEST_RESULT_ERROR = 'ERROR'


class ExceptionRecord(object):
    """A wrapper class for representing exception objects in TestResultRecord.

    Attributes:
        exception: Exception object, the original Exception.
        stacktrace: string, stacktrace of the Exception.
        extras: optional serializable, this corresponds to the
            `TestSignal.extras` field.
        position: string, an optional label specifying the position where the
            Exception ocurred.
    """

    def __init__(self, e, position=None):
        self.exception = e
        self.stacktrace = None
        self.extras = None
        self.position = position
        self.is_test_signal = isinstance(e, signals.TestSignal)
        # Record stacktrace of the exception.
        # This check cannot be based on try...except, which messes up
        # `exc_info`.
        if hasattr(e, '__traceback__'):
            exc_traceback = e.__traceback__
        else:
            # In py2, exception objects don't have built-in traceback, so we
            # have to immediately retrieve stacktrace from `sys.exc_info`.
            _, _, exc_traceback = sys.exc_info()
        if exc_traceback:
            self.stacktrace = ''.join(
                traceback.format_exception(e.__class__, e, exc_traceback))
        # Populate fields based on the type of the termination signal.
        if self.is_test_signal:
            self._set_details(e.details)
            self.extras = e.extras
        else:
            self._set_details(e)

    def _set_details(self, content):
        """Sets the `details` field.

        Args:
            content: the content to extract details from.
        """
        try:
            self.details = str(content)
        except UnicodeEncodeError:
            if sys.version_info < (3, 0):
                # If Py2 threw encode error, convert to unicode.
                self.details = unicode(content)
            else:
                # We should never hit this in Py3, if this happens, record
                # an encoded version of the content for users to handle.
                logging.error(
                    'Unable to decode "%s" in Py3, encoding in utf-8.',
                    content)
                self.details = content.encode('utf-8')

    def to_dict(self):
        result = {}
        result[TestResultEnums.RECORD_DETAILS] = self.details
        result[TestResultEnums.RECORD_POSITION] = self.position
        result[TestResultEnums.RECORD_STACKTRACE] = self.stacktrace
        result[TestResultEnums.RECORD_EXTRAS] = copy.deepcopy(self.extras)
        return result

    def __deepcopy__(self, memo):
        """Overrides deepcopy for the class.

        If the exception object has a constructor that takes extra args, deep
        copy won't work. So we need to have a custom logic for deepcopy.
        """
        try:
            exception = copy.deepcopy(self.exception)
        except TypeError:
            # If the exception object cannot be copied, use the original
            # exception object.
            exception = self.exception
        result = ExceptionRecord(exception, self.position)
        result.stacktrace = self.stacktrace
        result.details = self.details
        result.extras = self.extras
        result.position = self.position
        return result


class TestResultRecord(object):
    """A record that holds the information of a single test.

    The record object holds all information of a test, including all the
    exceptions occurred during the test.

    A test can terminate for two reasons:
      1. the test function executes to the end and completes naturally.
      2. the test is terminated by an exception, which we call
         "termination signal".

    The termination signal is treated differently. Its content are extracted
    into first-tier attributes of the record object, like `details` and
    `stacktrace`, for easy consumption.

    Note the termination signal is not always an error, it can also be explicit
    pass signal or abort/skip signals.

    Attributes:
        test_name: string, the name of the test.
        begin_time: Epoch timestamp of when the test started.
        end_time: Epoch timestamp of when the test ended.
        uid: Unique identifier of a test.
        termination_signal: ExceptionRecord, the main exception of the test.
        extra_errors: OrderedDict, all exceptions occurred during the entire
            test lifecycle. The order of occurrence is preserved.
        result: TestResultEnum.TEAT_RESULT_*, PASS/FAIL/SKIP.
    """

    def __init__(self, t_name, t_class=None):
        self.test_name = t_name
        self.test_class = t_class
        self.begin_time = None
        self.end_time = None
        self.uid = None
        self.termination_signal = None
        self.extra_errors = collections.OrderedDict()
        self.result = None

    @property
    def details(self):
        """String description of the cause of the test's termination.

        Note a passed test can have this as well due to the explicit pass
        signal. If the test passed implicitly, this field would be None.
        """
        if self.termination_signal:
            return self.termination_signal.details

    @property
    def stacktrace(self):
        """The stacktrace string for the exception that terminated the test.
        """
        if self.termination_signal:
            return self.termination_signal.stacktrace

    @property
    def extras(self):
        """User defined extra information of the test result.

        Must be serializable.
        """
        if self.termination_signal:
            return self.termination_signal.extras

    def test_begin(self):
        """Call this when the test begins execution.

        Sets the begin_time of this record.
        """
        self.begin_time = utils.get_current_epoch_time()

    def _test_end(self, result, e):
        """Marks the end of the test logic.

        Args:
            result: One of the TEST_RESULT enums in TestResultEnums.
            e: A test termination signal (usually an exception object). It can
                be any exception instance or of any subclass of
                mobly.signals.TestSignal.
        """
        if self.begin_time is not None:
            self.end_time = utils.get_current_epoch_time()
        self.result = result
        if e:
            self.termination_signal = ExceptionRecord(e)

    def update_record(self):
        """Updates the content of a record.

        Several display fields like "details" and "stacktrace" need to be
        updated based on the content of the record object.

        As the content of the record change, call this method to update all
        the appropirate fields.
        """
        if self.extra_errors:
            if self.result != TestResultEnums.TEST_RESULT_FAIL:
                self.result = TestResultEnums.TEST_RESULT_ERROR
        # If no termination signal is provided, use the first exception
        # occurred as the termination signal.
        if not self.termination_signal and self.extra_errors:
            _, self.termination_signal = self.extra_errors.popitem(last=False)

    def test_pass(self, e=None):
        """To mark the test as passed in this record.

        Args:
            e: An instance of mobly.signals.TestPass.
        """
        self._test_end(TestResultEnums.TEST_RESULT_PASS, e)

    def test_fail(self, e=None):
        """To mark the test as failed in this record.

        Only test_fail does instance check because we want 'assert xxx' to also
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

    def add_error(self, position, e):
        """Add extra error happened during a test.

        If the test has passed or skipped, this will mark the test result as
        ERROR.

        If an error is added the test record, the record's result is equivalent
        to the case where an uncaught exception happened.

        If the test record has not recorded any error, the newly added error
        would be the main error of the test record. Otherwise the newly added
        error is added to the record's extra errors.

        Args:
            position: string, where this error occurred, e.g. 'teardown_test'.
            e: An exception or a `signals.ExceptionRecord` object.
        """
        if self.result != TestResultEnums.TEST_RESULT_FAIL:
            self.result = TestResultEnums.TEST_RESULT_ERROR
        if position in self.extra_errors:
            raise Error('An exception is already recorded with position "%s",'
                        ' cannot reuse.' % position)
        if isinstance(e, ExceptionRecord):
            self.extra_errors[position] = e
        else:
            self.extra_errors[position] = ExceptionRecord(e, position=position)

    def __str__(self):
        d = self.to_dict()
        l = ['%s = %s' % (k, v) for k, v in d.items()]
        s = ', '.join(l)
        return s

    def __repr__(self):
        """This returns a short string representation of the test record."""
        t = utils.epoch_to_human_time(self.begin_time)
        return '%s %s %s' % (t, self.test_name, self.result)

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
        d[TestResultEnums.RECORD_EXTRA_ERRORS] = {
            key: value.to_dict()
            for (key, value) in self.extra_errors.items()
        }
        d[TestResultEnums.RECORD_STACKTRACE] = self.stacktrace
        return d


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
            raise TypeError('Operand %s of type %s is not a TestResult.' %
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
                # TODO(xpconanfan): have a better way to validate this situation.
                setattr(sum_result, name, l_value)
        return sum_result

    def add_record(self, record):
        """Adds a test record to test result.

        A record is considered executed once it's added to the test result.

        Adding the record finalizes the content of a record, so no change
        should be made to the record afterwards.

        Args:
            record: A test record object to add.
        """
        record.update_record()
        if record.result == TestResultEnums.TEST_RESULT_SKIP:
            self.skipped.append(record)
            return
        self.executed.append(record)
        if record.result == TestResultEnums.TEST_RESULT_FAIL:
            self.failed.append(record)
        elif record.result == TestResultEnums.TEST_RESULT_PASS:
            self.passed.append(record)
        else:
            self.error.append(record)

    def add_controller_info(self, name, info):
        try:
            yaml.dump(info)
        except TypeError:
            logging.warning('Controller info for %s is not YAML serializable!'
                            ' Coercing it to string.' % name)
            self.controller_info[name] = str(info)
            return
        self.controller_info[name] = info

    def add_class_error(self, test_record):
        """Add a record to indicate a test class has failed before any test
        could execute.

        This is only called before any test is actually executed. So it only
        adds an error entry that describes why the class failed to the tally
        and does not affect the total number of tests requrested or exedcuted.

        Args:
            test_record: A TestResultRecord object for the test class.
        """
        test_record.update_record()
        self.error.append(test_record)

    def is_test_executed(self, test_name):
        """Checks if a specific test has been executed.

        Args:
            test_name: string, the name of the test to check.

        Returns:
            True if the test has been executed according to the test result,
            False otherwise.
        """
        for record in self.executed:
            if record.test_name == test_name:
                return True
        return False

    @property
    def is_all_pass(self):
        """True if no tests failed or threw errors, False otherwise."""
        num_of_failures = len(self.failed) + len(self.error)
        if num_of_failures == 0:
            return True
        return False

    def requested_test_names_dict(self):
        """Gets the requested test names of a test run in a dict format.

        Note a test can be requested multiple times, so there can be duplicated
        values

        Returns:
            A dict with a key and the list of strings.
        """
        return {'Requested Tests': copy.deepcopy(self.requested)}

    def summary_str(self):
        """Gets a string that summarizes the stats of this test result.

        The summary provides the counts of how many tests fall into each
        category, like 'Passed', 'Failed' etc.

        Format of the string is:
            Requested <int>, Executed <int>, ...

        Returns:
            A summary string of this test result.
        """
        l = ['%s %d' % (k, v) for k, v in self.summary_dict().items()]
        # Sort the list so the order is the same every time.
        msg = ', '.join(sorted(l))
        return msg

    def summary_dict(self):
        """Gets a dictionary that summarizes the stats of this test result.

        The summary provides the counts of how many tests fall into each
        category, like 'Passed', 'Failed' etc.

        Returns:
            A dictionary with the stats of this test result.
        """
        d = {}
        d['Requested'] = len(self.requested)
        d['Executed'] = len(self.executed)
        d['Passed'] = len(self.passed)
        d['Failed'] = len(self.failed)
        d['Skipped'] = len(self.skipped)
        d['Error'] = len(self.error)
        return d
