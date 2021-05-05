# Copyright 2016 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from builtins import str

import copy
import io
import mock
import os
import shutil
import tempfile
import threading
import unittest
import yaml

from mobly import records
from mobly import signals

from tests.lib import utils


class RecordTestError(Exception):
  """Error class with constructors that take extra args.

  Used for ExceptionRecord tests.
  """

  def __init__(self, something):
    self._something = something


class RecordsTest(unittest.TestCase):
  """This test class tests the implementation of classes in mobly.records.
  """

  def setUp(self):
    self.tn = 'test_name'
    self.details = 'Some details about the test execution.'
    self.float_extra = 12345.56789
    self.json_extra = {'ha': 'whatever'}
    self.tmp_path = tempfile.mkdtemp()

  def tearDown(self):
    shutil.rmtree(self.tmp_path)

  def verify_record(self, record, result, details, extras, stacktrace=None):
    record.update_record()
    # Verify each field.
    self.assertEqual(record.test_name, self.tn)
    self.assertEqual(record.result, result)
    self.assertEqual(record.details, details)
    self.assertEqual(record.extras, extras)
    self.assertTrue(record.begin_time, 'begin time should not be empty.')
    self.assertTrue(record.end_time, 'end time should not be empty.')
    # UID is not used at the moment, should always be None.
    self.assertIsNone(record.uid)
    # Verify to_dict.
    d = {}
    d[records.TestResultEnums.RECORD_NAME] = self.tn
    d[records.TestResultEnums.RECORD_RESULT] = result
    d[records.TestResultEnums.RECORD_DETAILS] = details
    d[records.TestResultEnums.RECORD_EXTRAS] = extras
    d[records.TestResultEnums.RECORD_BEGIN_TIME] = record.begin_time
    d[records.TestResultEnums.RECORD_END_TIME] = record.end_time
    d[records.TestResultEnums.
      RECORD_SIGNATURE] = f'{self.tn}-{record.begin_time}'
    d[records.TestResultEnums.RECORD_UID] = None
    d[records.TestResultEnums.RECORD_RETRY_PARENT] = None
    d[records.TestResultEnums.RECORD_CLASS] = None
    d[records.TestResultEnums.RECORD_EXTRA_ERRORS] = {}
    d[records.TestResultEnums.RECORD_STACKTRACE] = stacktrace
    actual_d = record.to_dict()
    # Verify stacktrace partially match as stacktraces often have file path
    # in them.
    if stacktrace:
      stacktrace_key = records.TestResultEnums.RECORD_STACKTRACE
      self.assertIn(d.pop(stacktrace_key), actual_d.pop(stacktrace_key))
    self.assertDictEqual(actual_d, d)
    # Verify that these code paths do not cause crashes and yield non-empty
    # results.
    self.assertTrue(str(record), 'str of the record should not be empty.')
    self.assertTrue(repr(record), "the record's repr shouldn't be empty.")

  def test_result_record_pass_none(self):
    record = records.TestResultRecord(self.tn)
    record.test_begin()
    record.test_pass()
    self.verify_record(record=record,
                       result=records.TestResultEnums.TEST_RESULT_PASS,
                       details=None,
                       extras=None)

  def test_result_record_pass_with_float_extra(self):
    record = records.TestResultRecord(self.tn)
    record.test_begin()
    s = signals.TestPass(self.details, self.float_extra)
    record.test_pass(s)
    self.verify_record(record=record,
                       result=records.TestResultEnums.TEST_RESULT_PASS,
                       details=self.details,
                       extras=self.float_extra)

  def test_result_record_pass_with_json_extra(self):
    record = records.TestResultRecord(self.tn)
    record.test_begin()
    s = signals.TestPass(self.details, self.json_extra)
    record.test_pass(s)
    self.verify_record(record=record,
                       result=records.TestResultEnums.TEST_RESULT_PASS,
                       details=self.details,
                       extras=self.json_extra)

  def test_result_record_fail_none(self):
    record = records.TestResultRecord(self.tn)
    record.test_begin()
    record.test_fail()
    self.verify_record(record=record,
                       result=records.TestResultEnums.TEST_RESULT_FAIL,
                       details=None,
                       extras=None)

  def test_result_record_fail_stacktrace(self):
    record = records.TestResultRecord(self.tn)
    record.test_begin()
    try:
      raise Exception('Something failed.')
    except Exception as e:
      record.test_fail(e)
    # Verify stacktrace separately if we expect a non-None value.
    # Because stacktrace includes file names and line numbers, we can't do
    # a simple equality check.
    self.verify_record(record=record,
                       result=records.TestResultEnums.TEST_RESULT_FAIL,
                       details='Something failed.',
                       extras=None,
                       stacktrace='in test_result_record_fail_stacktrace\n    '
                       'raise Exception(\'Something failed.\')\nException: '
                       'Something failed.\n')

  def test_result_record_fail_with_float_extra(self):
    record = records.TestResultRecord(self.tn)
    record.test_begin()
    s = signals.TestFailure(self.details, self.float_extra)
    record.test_fail(s)
    self.verify_record(record=record,
                       result=records.TestResultEnums.TEST_RESULT_FAIL,
                       details=self.details,
                       extras=self.float_extra)

  def test_result_record_fail_with_unicode_test_signal(self):
    record = records.TestResultRecord(self.tn)
    record.test_begin()
    details = u'\u2022'
    s = signals.TestFailure(details, self.float_extra)
    record.test_fail(s)
    self.verify_record(record=record,
                       result=records.TestResultEnums.TEST_RESULT_FAIL,
                       details=details,
                       extras=self.float_extra)

  def test_result_record_fail_with_unicode_exception(self):
    record = records.TestResultRecord(self.tn)
    record.test_begin()
    details = u'\u2022'
    s = Exception(details)
    record.test_fail(s)
    self.verify_record(record=record,
                       result=records.TestResultEnums.TEST_RESULT_FAIL,
                       details=details,
                       extras=None)

  def test_result_record_fail_with_json_extra(self):
    record = records.TestResultRecord(self.tn)
    record.test_begin()
    s = signals.TestFailure(self.details, self.json_extra)
    record.test_fail(s)
    self.verify_record(record=record,
                       result=records.TestResultEnums.TEST_RESULT_FAIL,
                       details=self.details,
                       extras=self.json_extra)

  def test_result_record_skip_none(self):
    record = records.TestResultRecord(self.tn)
    record.test_begin()
    record.test_skip()
    self.verify_record(record=record,
                       result=records.TestResultEnums.TEST_RESULT_SKIP,
                       details=None,
                       extras=None)

  def test_result_record_skip_with_float_extra(self):
    record = records.TestResultRecord(self.tn)
    record.test_begin()
    s = signals.TestSkip(self.details, self.float_extra)
    record.test_skip(s)
    self.verify_record(record=record,
                       result=records.TestResultEnums.TEST_RESULT_SKIP,
                       details=self.details,
                       extras=self.float_extra)

  def test_result_record_skip_with_json_extra(self):
    record = records.TestResultRecord(self.tn)
    record.test_begin()
    s = signals.TestSkip(self.details, self.json_extra)
    record.test_skip(s)
    self.verify_record(record=record,
                       result=records.TestResultEnums.TEST_RESULT_SKIP,
                       details=self.details,
                       extras=self.json_extra)

  def test_result_add_operator_success(self):
    record1 = records.TestResultRecord(self.tn)
    record1.test_begin()
    s = signals.TestPass(self.details, self.float_extra)
    record1.test_pass(s)
    tr1 = records.TestResult()
    tr1.add_record(record1)
    controller_info = records.ControllerInfoRecord('SomeClass', 'MockDevice',
                                                   ['magicA', 'magicB'])
    tr1.add_controller_info_record(controller_info)
    record2 = records.TestResultRecord(self.tn)
    record2.test_begin()
    s = signals.TestPass(self.details, self.json_extra)
    record2.test_pass(s)
    tr2 = records.TestResult()
    tr2.add_record(record2)
    controller_info = records.ControllerInfoRecord('SomeClass', 'MockDevice',
                                                   ['magicC'])
    tr2.add_controller_info_record(controller_info)
    tr2 += tr1
    self.assertTrue(tr2.passed, [tr1, tr2])
    self.assertTrue(tr2.controller_info, {'MockDevice': ['magicC']})

  def test_result_add_operator_type_mismatch(self):
    record1 = records.TestResultRecord(self.tn)
    record1.test_begin()
    s = signals.TestPass(self.details, self.float_extra)
    record1.test_pass(s)
    tr1 = records.TestResult()
    tr1.add_record(record1)
    expected_msg = 'Operand .* of type .* is not a TestResult.'
    with self.assertRaisesRegex(TypeError, expected_msg):
      tr1 += 'haha'

  def test_result_add_class_error_with_test_signal(self):
    record1 = records.TestResultRecord(self.tn)
    record1.test_begin()
    s = signals.TestPass(self.details, self.float_extra)
    record1.test_pass(s)
    tr = records.TestResult()
    tr.add_record(record1)
    s = signals.TestFailure(self.details, self.float_extra)
    record2 = records.TestResultRecord('SomeTest', s)
    tr.add_class_error(record2)
    self.assertEqual(len(tr.passed), 1)
    self.assertEqual(len(tr.error), 1)
    self.assertEqual(len(tr.executed), 1)

  def test_result_add_class_error_with_special_error(self):
    """Call TestResult.add_class_error with an error class that requires more
    than one arg to instantiate.
    """
    record1 = records.TestResultRecord(self.tn)
    record1.test_begin()
    s = signals.TestPass(self.details, self.float_extra)
    record1.test_pass(s)
    tr = records.TestResult()
    tr.add_record(record1)

    class SpecialError(Exception):

      def __init__(self, arg1, arg2):
        self.msg = '%s %s' % (arg1, arg2)

    se = SpecialError('haha', 42)
    record2 = records.TestResultRecord('SomeTest', se)
    tr.add_class_error(record2)
    self.assertEqual(len(tr.passed), 1)
    self.assertEqual(len(tr.error), 1)
    self.assertEqual(len(tr.executed), 1)

  def test_is_all_pass(self):
    s = signals.TestPass(self.details, self.float_extra)
    record1 = records.TestResultRecord(self.tn)
    record1.test_begin()
    record1.test_pass(s)
    s = signals.TestSkip(self.details, self.float_extra)
    record2 = records.TestResultRecord(self.tn)
    record2.test_begin()
    record2.test_skip(s)
    tr = records.TestResult()
    tr.add_record(record1)
    tr.add_record(record2)
    tr.add_record(record1)
    self.assertEqual(len(tr.passed), 2)
    self.assertTrue(tr.is_all_pass)

  def test_is_all_pass_negative(self):
    s = signals.TestFailure(self.details, self.float_extra)
    record1 = records.TestResultRecord(self.tn)
    record1.test_begin()
    record1.test_fail(s)
    record2 = records.TestResultRecord(self.tn)
    record2.test_begin()
    record2.test_error(s)
    tr = records.TestResult()
    tr.add_record(record1)
    tr.add_record(record2)
    utils.validate_test_result(tr)
    self.assertFalse(tr.is_all_pass)

  def test_is_all_pass_with_add_class_error(self):
    """Verifies that is_all_pass yields correct value when add_class_error is
    used.
    """
    record1 = records.TestResultRecord(self.tn)
    record1.test_begin()
    record1.test_fail(Exception('haha'))
    tr = records.TestResult()
    tr.add_class_error(record1)
    self.assertFalse(tr.is_all_pass)

  def test_is_test_executed(self):
    record1 = records.TestResultRecord(self.tn)
    record1.test_begin()
    record1.test_fail(Exception('haha'))
    tr = records.TestResult()
    tr.add_record(record1)
    self.assertTrue(tr.is_test_executed(record1.test_name))
    self.assertFalse(tr.is_test_executed(self.tn + 'ha'))

  def test_summary_write_dump(self):
    s = signals.TestFailure(self.details, self.float_extra)
    record1 = records.TestResultRecord(self.tn)
    record1.test_begin()
    record1.test_fail(s)
    dump_path = os.path.join(self.tmp_path, 'ha.yaml')
    writer = records.TestSummaryWriter(dump_path)
    writer.dump(record1.to_dict(), records.TestSummaryEntryType.RECORD)
    with io.open(dump_path, 'r', encoding='utf-8') as f:
      content = yaml.safe_load(f)
      self.assertEqual(content['Type'],
                       records.TestSummaryEntryType.RECORD.value)
      self.assertEqual(content[records.TestResultEnums.RECORD_DETAILS],
                       self.details)
      self.assertEqual(content[records.TestResultEnums.RECORD_EXTRAS],
                       self.float_extra)

  def test_summary_write_dump_with_unicode(self):
    unicode_details = u'\u901a'  # utf-8 -> b'\xe9\x80\x9a'
    unicode_extras = u'\u8fc7'  # utf-8 -> b'\xe8\xbf\x87'
    s = signals.TestFailure(unicode_details, unicode_extras)
    record1 = records.TestResultRecord(self.tn)
    record1.test_begin()
    record1.test_fail(s)
    dump_path = os.path.join(self.tmp_path, 'ha.yaml')
    writer = records.TestSummaryWriter(dump_path)
    writer.dump(record1.to_dict(), records.TestSummaryEntryType.RECORD)
    with io.open(dump_path, 'r', encoding='utf-8') as f:
      content = yaml.safe_load(f)
      self.assertEqual(content['Type'],
                       records.TestSummaryEntryType.RECORD.value)
      self.assertEqual(content[records.TestResultEnums.RECORD_DETAILS],
                       unicode_details)
      self.assertEqual(content[records.TestResultEnums.RECORD_EXTRAS],
                       unicode_extras)

  @mock.patch('mobly.utils.get_current_epoch_time')
  def test_signature(self, mock_time_src):
    mock_time_src.return_value = 12345
    record = records.TestResultRecord(self.tn)
    record.test_begin()
    self.assertEqual(record.signature, 'test_name-12345')

  def test_summary_user_data(self):
    user_data1 = {'a': 1}
    user_data2 = {'b': 1}
    user_data = [user_data1, user_data2]
    dump_path = os.path.join(self.tmp_path, 'ha.yaml')
    writer = records.TestSummaryWriter(dump_path)
    for data in user_data:
      writer.dump(data, records.TestSummaryEntryType.USER_DATA)
    with io.open(dump_path, 'r', encoding='utf-8') as f:
      contents = []
      for c in yaml.safe_load_all(f):
        contents.append(c)
    for content in contents:
      self.assertEqual(content['Type'],
                       records.TestSummaryEntryType.USER_DATA.value)
    self.assertEqual(contents[0]['a'], user_data1['a'])
    self.assertEqual(contents[1]['b'], user_data2['b'])

  def test_exception_record_deepcopy(self):
    """Makes sure ExceptionRecord wrapper handles deep copy properly."""
    try:
      raise RecordTestError('Oh ha!')
    except RecordTestError as e:
      er = records.ExceptionRecord(e)
    new_er = copy.deepcopy(er)
    self.assertIsNot(er, new_er)
    self.assertDictEqual(er.to_dict(), new_er.to_dict())

  def test_add_controller_info_record(self):
    tr = records.TestResult()
    self.assertFalse(tr.controller_info)
    controller_info = records.ControllerInfoRecord('SomeClass', 'MockDevice',
                                                   ['magicA', 'magicB'])
    tr.add_controller_info_record(controller_info)
    self.assertTrue(tr.controller_info[0])
    self.assertEqual(tr.controller_info[0].controller_name, 'MockDevice')
    self.assertEqual(tr.controller_info[0].controller_info,
                     ['magicA', 'magicB'])

  def test_uid(self):

    @records.uid('some-uuid')
    def test_uid_helper():
      """Dummy test used by `test_uid` for testing the uid decorator."""

    self.assertEqual(test_uid_helper.uid, 'some-uuid')


if __name__ == '__main__':
  unittest.main()
