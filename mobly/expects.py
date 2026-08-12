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

import contextlib
import functools
import logging
import time

from mobly import asserts
from mobly import records
from mobly import signals

# When used outside of a `base_test.BaseTestClass` context, such as when using
# the `android_device` controller directly, the `expects.recorder`
# `TestResultRecord` isn't set, which causes `expects` module methods to fail
# from the missing record, so this provides a default, globally accessible
# record for `expects` module to use as well as providing a way to get the
# globally recorded errors.
DEFAULT_TEST_RESULT_RECORD = records.TestResultRecord('mobly', 'global')


class _ExpectErrorRecorder:
  """Singleton used to store errors caught via `expect_*` functions in test.

  This class is only instantiated once as a singleton. It holds a reference
  to the record object for the test currently executing.
  """

  def __init__(self, record=None):
    self.reset_internal_states(record=record)

  def reset_internal_states(self, record=None):
    """Resets the internal state of the recorder.

    Args:
      record: records.TestResultRecord, the test record for a test.
    """
    self._record = None
    self._count = 0
    self._record = record

  @property
  def has_error(self):
    """If any error has been recorded since the last reset."""
    return self._count > 0

  @property
  def error_count(self):
    """The number of errors that have been recorded since last reset."""
    return self._count

  def add_error(self, error):
    """Record an error from expect APIs.

    This method generates a position stamp for the expect. The stamp is
    composed of a timestamp and the number of errors recorded so far.

    Args:
      error: Exception or signals.ExceptionRecord, the error to add.
    """
    self._count += 1
    self._record.add_error('expect@%s+%s' % (time.time(), self._count), error)


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
    logging.exception('Expected a `True` value, got `False`.')
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
    logging.exception('Expected a `False` value, got `True`.')
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
    logging.exception(
        'Expected %s equals to %s, but they are not.', first, second
    )
    recorder.add_error(e)


class expect_no_raises(contextlib.ContextDecorator):
  """Expects no exception is raised in a context or a decorated function.

  If the expectation is not met, the test is marked as fail after its
  execution finishes.

  Can be used as a context manager:
    with expects.expect_no_raises(message='Custom message'):
      do_something()

  Or as a function decorator:
    @expects.expect_no_raises(message='Custom message')
    def helper_function(arg):
      do_something(arg)

    @expects.expect_no_raises
    def bare_decorated_function():
      do_something()

  Args:
    message: An optional custom message to add to the exception's `details`.
    extras: An optional field for extra information to be included in test
      result.
  """

  def __new__(cls, *args, **kwargs):
    if len(args) == 1 and callable(args[0]) and not kwargs:
      # Used as bare decorator: @expects.expect_no_raises
      func = args[0]
      instance = super().__new__(cls)
      instance.__init__()

      @functools.wraps(func)
      def wrapped(*f_args, **f_kwargs):
        with instance:
          return func(*f_args, **f_kwargs)

      return wrapped
    return super().__new__(cls)

  def __init__(self, message=None, extras=None):
    self._message = message
    self._extras = extras

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    if exc_type is not None and issubclass(exc_type, Exception):
      e_record = records.ExceptionRecord(exc_val)
      if self._extras:
        e_record.extras = self._extras
      msg = self._message or 'Got an unexpected exception'
      details = '%s: %s' % (msg, e_record.details)
      logging.exception(details)
      e_record.details = details
      recorder.add_error(e_record)
      return True
    return False


recorder = _ExpectErrorRecorder(DEFAULT_TEST_RESULT_RECORD)
