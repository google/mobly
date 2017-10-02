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

import collections
import contextlib
import time

from mobly import asserts
from mobly import records
from mobly import signals


class _ExpectErrorRecorder(object):
    """Singleton used to store errors caught via `expect_*` functions in test.

    This class is only instantiated once as a singleton. It holds a reference
    to the record object for the test currently executing.
    """

    def __init__(self):
        self._reset_internal_states()

    def _reset_internal_states(self):
        """Resets the internal state of the recorder."""
        self._has_error = False
        self._count = 0

    @property
    def has_error(self):
        """If any error has been recorded since the last reset."""
        return self._has_error

    @property
    def error_count(self):
        """The number of errors that have been recorded since last reset."""
        return self._count

    def add_error(self, error):
        """Record an error from expect APIs.

        Args:
            error: Exception or signals.ExceptionRecord, the error to add.
        """
        self._has_error = True
        self._count += 1
        self._record.add_error('expect@%s' % time.time(), error)

    def reset_with_record(self, record):
        """Resets the state of the cache.

        Args:
            record: records.TestResultRecord, the test record for a test.
        """
        self._reset_internal_states()
        self._record = record


def expect_true(condition, msg, extras=None):
    """Expects an expression evaluates to True.

    If the expectation is not met, the test is marked as fail after its
    execution finishes.

    Args:
        expr: The expression that is evaluated.
        msg: A string explaining the details in case of failure.
        extras: An optional field for extra information to be included in test
            result.
    """
    try:
        asserts.assert_true(condition, msg, extras)
    except signals.TestSignal as e:
        recorder.add_error(e)


def expect_false(condition, msg, extras=None):
    """Expects an expression evaluates to False.

    If the expectation is not met, the test is marked as fail after its
    execution finishes.

    Args:
        expr: The expression that is evaluated.
        msg: A string explaining the details in case of failure.
        extras: An optional field for extra information to be included in test
            result.
    """
    try:
        asserts.assert_false(condition, msg, extras)
    except signals.TestSignal as e:
        recorder.add_error(e)


def expect_equal(first, second, msg=None, extras=None):
    """Expects the equality of objects, otherwise fail the test.

    If the expectation is not met, the test is marked as fail after its
    execution finishes.

    Error message is "first != second" by default. Additional explanation can
    be supplied in the message.

    Args:
        first: The first object to compare.
        second: The second object to compare.
        msg: A string that adds additional info about the failure.
        extras: An optional field for extra information to be included in test
            result.
    """
    try:
        asserts.assert_equal(first, second, msg, extras)
    except signals.TestSignal as e:
        recorder.add_error(e)


@contextlib.contextmanager
def expect_no_raises(message=None, extras=None):
    """Expects no exception is raised in a context.

    If the expectation is not met, the test is marked as fail after its
    execution finishes.

    A default message is added to the exception `details`.

    Args:
        message: string, custom message to add to exception's `details`.
        extras: An optional field for extra information to be included in test
            result.
    """
    try:
        yield
    except Exception as e:
        e_record = records.ExceptionRecord(e)
        if extras:
            e_record.extras = extras
        msg = message or 'Got unexpected exception'
        e_record.details = '%s: %s' % (msg, e_record.details)
        recorder.add_error(e_record)


recorder = _ExpectErrorRecorder()
