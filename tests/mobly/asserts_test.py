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

import unittest

from mobly import asserts
from mobly import signals

MSG_EXPECTED_EXCEPTION = 'This is an expected exception.'
_OBJECT_1 = object()
_OBJECT_2 = object()


class AssertsTest(unittest.TestCase):
  """Verifies that asserts.xxx functions raise the correct test signals."""

  def test_assert_false(self):
    asserts.assert_false(False, MSG_EXPECTED_EXCEPTION)
    with self.assertRaisesRegex(signals.TestFailure, MSG_EXPECTED_EXCEPTION):
      asserts.assert_false(True, MSG_EXPECTED_EXCEPTION)

  def test_assert_not_equal_pass(self):
    asserts.assert_not_equal(1, 2)

  def test_assert_not_equal_pass_with_msg_and_extras(self):
    asserts.assert_not_equal(1, 2, msg='Message', extras='Extras')

  def test_assert_not_equal_fail(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_not_equal(1, 1)
    self.assertEqual(cm.exception.details, '1 == 1')

  def test_assert_not_equal_fail_with_msg_and_extras(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_not_equal(1, 1, msg='Message', extras='Extras')
    self.assertEqual(cm.exception.details, '1 == 1 Message')
    self.assertEqual(cm.exception.extras, 'Extras')

  def test_assert_almost_equal_pass(self):
    asserts.assert_almost_equal(1.000001, 1.000002, places=3)
    asserts.assert_almost_equal(1.0, 1.05, delta=0.1)

  def test_assert_almost_equal_fail(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_almost_equal(1, 1.0005, places=7)
    self.assertRegex(cm.exception.details, r'1 != 1\.0005 within 7 places')

  def test_assert_almost_equal_fail_with_msg_and_extras(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_almost_equal(
          1, 2, delta=0.1, msg='Message', extras='Extras'
      )
    self.assertRegex(cm.exception.details, r'1 != 2 within 0\.1 delta.*Message')
    self.assertEqual(cm.exception.extras, 'Extras')

  def test_assert_not_almost_equal_pass(self):
    asserts.assert_not_almost_equal(1.001, 1.002, places=3)
    asserts.assert_not_almost_equal(1.0, 1.05, delta=0.01)

  def test_assert_not_almost_equal_fail(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_not_almost_equal(1, 1.0005, places=3)
    self.assertRegex(cm.exception.details, r'1 == 1\.0005 within 3 places')

  def test_assert_not_almost_equal_fail_with_msg_and_extras(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_not_almost_equal(
          1, 2, delta=1, msg='Message', extras='Extras'
      )
    self.assertRegex(cm.exception.details, r'1 == 2 within 1 delta.*Message')
    self.assertEqual(cm.exception.extras, 'Extras')

  def test_assert_in_pass(self):
    asserts.assert_in(1, [1, 2, 3])
    asserts.assert_in(1, (1, 2, 3))
    asserts.assert_in(1, {1: 2, 3: 4})
    asserts.assert_in('a', 'abcd')

  def test_assert_in_fail(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_in(4, [1, 2, 3])
    self.assertEqual(cm.exception.details, '4 not found in [1, 2, 3]')

  def test_assert_in_fail_with_msg_and_extras(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_in(4, [1, 2, 3], msg='Message', extras='Extras')
    self.assertEqual(cm.exception.details, '4 not found in [1, 2, 3] Message')
    self.assertEqual(cm.exception.extras, 'Extras')

  def test_assert_not_in_pass(self):
    asserts.assert_not_in(4, [1, 2, 3])
    asserts.assert_not_in(4, (1, 2, 3))
    asserts.assert_not_in(4, {1: 2, 3: 4})
    asserts.assert_not_in('e', 'abcd')

  def test_assert_not_in_fail(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_not_in(1, [1, 2, 3])
    self.assertEqual(cm.exception.details, '1 unexpectedly found in [1, 2, 3]')

  def test_assert_not_in_fail_with_msg_and_extras(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_not_in(1, [1, 2, 3], msg='Message', extras='Extras')
    self.assertEqual(
        cm.exception.details, '1 unexpectedly found in [1, 2, 3] Message'
    )
    self.assertEqual(cm.exception.extras, 'Extras')

  def test_assert_is_pass(self):
    asserts.assert_is(_OBJECT_1, _OBJECT_1)

  def test_assert_is_fail(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_is(_OBJECT_1, _OBJECT_2)
    self.assertEqual(cm.exception.details, f'{_OBJECT_1} is not {_OBJECT_2}')

  def test_assert_is_fail_with_msg_and_extras(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_is(_OBJECT_1, _OBJECT_2, msg='Message', extras='Extras')
    self.assertEqual(
        cm.exception.details, f'{_OBJECT_1} is not {_OBJECT_2} Message'
    )
    self.assertEqual(cm.exception.extras, 'Extras')

  def test_assert_is_not_pass(self):
    asserts.assert_is_not(_OBJECT_1, _OBJECT_2)

  def test_assert_is_not_fail(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_is_not(_OBJECT_1, _OBJECT_1)
    self.assertEqual(
        cm.exception.details, f'unexpectedly identical: {_OBJECT_1}'
    )

  def test_assert_is_not_fail_with_msg_and_extras(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_is_not(
          _OBJECT_1, _OBJECT_1, msg='Message', extras='Extras'
      )
    self.assertEqual(
        cm.exception.details, f'unexpectedly identical: {_OBJECT_1} Message'
    )
    self.assertEqual(cm.exception.extras, 'Extras')

  def test_assert_count_equal_pass(self):
    asserts.assert_count_equal((1, 3, 3), [3, 1, 3])

  def test_assert_count_equal_fail(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_count_equal([3, 3], [3])
    self.assertEqual(
        cm.exception.details,
        'Element counts were not equal:\nFirst has 2, Second has 1:  3',
    )

  def test_assert_count_equal_fail_with_msg_and_extras(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_count_equal((3, 3), (4, 4), msg='Message', extras='Extras')
    self.assertEqual(
        cm.exception.details,
        (
            'Element counts were not equal:\n'
            'First has 2, Second has 0:  3\n'
            'First has 0, Second has 2:  4 Message'
        ),
    )
    self.assertEqual(cm.exception.extras, 'Extras')

  def test_assert_less_pass(self):
    asserts.assert_less(1.0, 2)

  def test_assert_less_fail(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_less(1, 1)
    self.assertEqual(cm.exception.details, '1 not less than 1')

  def test_assert_less_fail_with_msg_and_extras(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_less(2, 1, msg='Message', extras='Extras')
    self.assertEqual(cm.exception.details, '2 not less than 1 Message')
    self.assertEqual(cm.exception.extras, 'Extras')

  def test_assert_less_equal_pass(self):
    asserts.assert_less_equal(1.0, 2)
    asserts.assert_less_equal(1, 1)

  def test_assert_less_equal_fail(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_less_equal(2, 1)
    self.assertEqual(cm.exception.details, '2 not less than or equal to 1')

  def test_assert_less_equal_fail_with_msg_and_extras(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_less_equal(2, 1, msg='Message', extras='Extras')
    self.assertEqual(
        cm.exception.details, '2 not less than or equal to 1 Message'
    )
    self.assertEqual(cm.exception.extras, 'Extras')

  def test_assert_greater_pass(self):
    asserts.assert_greater(2, 1.0)

  def test_assert_greater_fail(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_greater(1, 1)
    self.assertEqual(cm.exception.details, '1 not greater than 1')

  def test_assert_greater_fail_with_msg_and_extras(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_greater(1, 2, msg='Message', extras='Extras')
    self.assertEqual(cm.exception.details, '1 not greater than 2 Message')
    self.assertEqual(cm.exception.extras, 'Extras')

  def test_assert_greater_equal_pass(self):
    asserts.assert_greater_equal(2, 1.0)
    asserts.assert_greater_equal(1, 1)

  def test_assert_greater_equal_fail(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_greater_equal(1, 2)
    self.assertEqual(cm.exception.details, '1 not greater than or equal to 2')

  def test_assert_greater_equal_fail_with_msg_and_extras(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_greater_equal(1, 2, msg='Message', extras='Extras')
    self.assertEqual(
        cm.exception.details, '1 not greater than or equal to 2 Message'
    )
    self.assertEqual(cm.exception.extras, 'Extras')

  def test_assert_is_none_pass(self):
    asserts.assert_is_none(None)

  def test_assert_is_none_fail(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_is_none(1)
    self.assertEqual(cm.exception.details, '1 is not None')

  def test_assert_is_none_fail_with_msg_and_extras(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_is_none(1, msg='Message', extras='Extras')
    self.assertEqual(cm.exception.details, '1 is not None Message')
    self.assertEqual(cm.exception.extras, 'Extras')

  def test_assert_is_not_none_pass(self):
    asserts.assert_is_not_none(1)

  def test_assert_is_not_none_fail(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_is_not_none(None)
    self.assertEqual(cm.exception.details, 'unexpectedly None')

  def test_assert_is_none_not_fail_with_msg_and_extras(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_is_not_none(None, msg='Message', extras='Extras')
    self.assertEqual(cm.exception.details, 'unexpectedly None Message')
    self.assertEqual(cm.exception.extras, 'Extras')

  def test_assert_is_instance_pass(self):
    asserts.assert_is_instance('foo', str)
    asserts.assert_is_instance(1, int)
    asserts.assert_is_instance(1.0, float)

  def test_assert_is_instance_fail(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_is_instance(1, str)
    self.assertEqual(cm.exception.details, f'1 is not an instance of {str}')

  def test_assert_is_instance_fail_with_msg_and_extras(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_is_instance(1.0, int, msg='Message', extras='Extras')
    self.assertEqual(
        cm.exception.details, f'1.0 is not an instance of {int} Message'
    )
    self.assertEqual(cm.exception.extras, 'Extras')

  def test_assert_not_is_instance_pass(self):
    asserts.assert_not_is_instance('foo', int)
    asserts.assert_not_is_instance(1, float)
    asserts.assert_not_is_instance(1.0, int)

  def test_assert_not_is_instance_fail(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_not_is_instance(1, int)
    self.assertEqual(cm.exception.details, f'1 is an instance of {int}')

  def test_assert_not_is_instance_fail_with_msg_and_extras(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_not_is_instance('foo', str, msg='Message', extras='Extras')
    self.assertEqual(
        cm.exception.details, f"'foo' is an instance of {str} Message"
    )
    self.assertEqual(cm.exception.extras, 'Extras')

  def test_assert_regex_pass(self):
    asserts.assert_regex('Big rocks', r'(r|m)ocks')

  def test_assert_regex_fail(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_regex('Big socks', r'(r|m)ocks')
    self.assertEqual(
        cm.exception.details,
        "Regex didn't match: '(r|m)ocks' not found in 'Big socks'",
    )

  def test_assert_regex_fail_with_msg_and_extras(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_regex(
          'Big socks', r'(r|m)ocks', msg='Message', extras='Extras'
      )
    self.assertEqual(
        cm.exception.details,
        "Regex didn't match: '(r|m)ocks' not found in 'Big socks' Message",
    )
    self.assertEqual(cm.exception.extras, 'Extras')

  def test_assert_not_regex_pass(self):
    asserts.assert_not_regex('Big socks', r'(r|m)ocks')

  def test_assert_not_regex_fail(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_not_regex('Big rocks', r'(r|m)ocks')
    self.assertEqual(
        cm.exception.details,
        "Regex matched: 'rocks' matches '(r|m)ocks' in 'Big rocks'",
    )

  def test_assert_not_regex_fail_with_msg_and_extras(self):
    with self.assertRaises(signals.TestFailure) as cm:
      asserts.assert_not_regex(
          'Big mocks', r'(r|m)ocks', msg='Message', extras='Extras'
      )
    self.assertEqual(
        cm.exception.details,
        "Regex matched: 'mocks' matches '(r|m)ocks' in 'Big mocks' Message",
    )
    self.assertEqual(cm.exception.extras, 'Extras')


if __name__ == '__main__':
  unittest.main()
