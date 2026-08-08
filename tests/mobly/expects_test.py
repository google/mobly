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

import unittest

from mobly import expects
from mobly import records


class ExpectsTest(unittest.TestCase):
  """Unit tests for the mobly.expects module."""

  def setUp(self):
    self.record = records.TestResultRecord('test_foo', 'TestClass')
    expects.recorder.reset_internal_states(self.record)

  def test_expect_true_pass(self):
    expects.expect_true(True, 'Should pass')
    self.assertFalse(expects.recorder.has_error)
    self.assertEqual(expects.recorder.error_count, 0)

  def test_expect_true_fail(self):
    expects.expect_true(False, 'Expected true', extras='extra_info')
    self.assertTrue(expects.recorder.has_error)
    self.assertEqual(expects.recorder.error_count, 1)
    err = list(self.record.extra_errors.values())[0]
    self.assertEqual(err.extras, 'extra_info')
    self.assertIn('Expected true', err.details)

  def test_expect_false_pass(self):
    expects.expect_false(False, 'Should pass')
    self.assertFalse(expects.recorder.has_error)
    self.assertEqual(expects.recorder.error_count, 0)

  def test_expect_false_fail(self):
    expects.expect_false(True, 'Expected false', extras='extra_info')
    self.assertTrue(expects.recorder.has_error)
    self.assertEqual(expects.recorder.error_count, 1)
    err = list(self.record.extra_errors.values())[0]
    self.assertEqual(err.extras, 'extra_info')
    self.assertIn('Expected false', err.details)

  def test_expect_equal_pass(self):
    expects.expect_equal(1, 1, 'Should pass')
    self.assertFalse(expects.recorder.has_error)
    self.assertEqual(expects.recorder.error_count, 0)

  def test_expect_equal_fail(self):
    expects.expect_equal(1, 2, 'Values not equal', extras='extra_info')
    self.assertTrue(expects.recorder.has_error)
    self.assertEqual(expects.recorder.error_count, 1)
    err = list(self.record.extra_errors.values())[0]
    self.assertEqual(err.extras, 'extra_info')
    self.assertIn('Values not equal', err.details)

  def test_expect_no_raises_context_manager_pass(self):
    with expects.expect_no_raises():
      _ = 1 + 1
    self.assertFalse(expects.recorder.has_error)
    self.assertEqual(expects.recorder.error_count, 0)

  def test_expect_no_raises_context_manager_fail(self):
    with expects.expect_no_raises(message='Context error', extras='extra_info'):
      raise ValueError('something went wrong')
    self.assertTrue(expects.recorder.has_error)
    self.assertEqual(expects.recorder.error_count, 1)
    err = list(self.record.extra_errors.values())[0]
    self.assertEqual(err.extras, 'extra_info')
    self.assertIn('Context error', err.details)
    self.assertIn('something went wrong', err.details)

  def test_expect_no_raises_bare_decorator_on_arbitrary_function(self):
    """Verifies @expects.expect_no_raises on any arbitrary function."""

    @expects.expect_no_raises
    def arbitrary_helper(a, b, fail=False):
      if fail:
        raise RuntimeError('Helper failed')
      return a + b

    # Success case on arbitrary function
    result = arbitrary_helper(3, 4, fail=False)
    self.assertEqual(result, 7)
    self.assertFalse(expects.recorder.has_error)

    # Failure case on arbitrary function
    result = arbitrary_helper(3, 4, fail=True)
    self.assertIsNone(result)
    self.assertTrue(expects.recorder.has_error)
    self.assertEqual(expects.recorder.error_count, 1)

  def test_expect_no_raises_parameterized_decorator_on_arbitrary_function(self):
    """Verifies @expects.expect_no_raises(...) on any arbitrary function."""

    @expects.expect_no_raises(message='Custom step error', extras={'step': 1})
    def custom_calculation(x, y):
      if y == 0:
        raise ZeroDivisionError('divide by zero')
      return x / y

    # Success case
    self.assertEqual(custom_calculation(10, 2), 5)
    self.assertFalse(expects.recorder.has_error)

    # Failure case
    self.assertIsNone(custom_calculation(10, 0))
    self.assertTrue(expects.recorder.has_error)
    self.assertEqual(expects.recorder.error_count, 1)
    err = list(self.record.extra_errors.values())[0]
    self.assertEqual(err.extras, {'step': 1})
    self.assertIn('Custom step error', err.details)

  def test_expect_no_raises_decorator_preserves_function_metadata(self):
    """Verifies that docstrings, __name__, and metadata are preserved."""

    @expects.expect_no_raises
    def sample_func(x):
      """Sample documentation."""
      return x

    self.assertEqual(sample_func.__name__, 'sample_func')
    self.assertEqual(sample_func.__doc__, 'Sample documentation.')


if __name__ == '__main__':
  unittest.main()
