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

import unittest

from mobly import records
from mobly import signals

class RecordsTest(unittest.TestCase):
    """This test class tests the implementation of classes in mobly.records.
    """

    def setUp(self):
        self.tn = "test_name"
        self.details = "Some details about the test execution."
        self.float_extra = 12345.56789
        self.json_extra = {"ha": "whatever"}

    def verify_record(self, record, result, details, extras):
        # Verify each field.
        self.assertEqual(record.test_name, self.tn)
        self.assertEqual(record.result, result)
        self.assertEqual(record.details, details)
        self.assertEqual(record.extras, extras)
        self.assertTrue(record.begin_time, "begin time should not be empty.")
        self.assertTrue(record.end_time, "end time should not be empty.")
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
        d[records.TestResultEnums.RECORD_UID] = None
        d[records.TestResultEnums.RECORD_CLASS] = None
        d[records.TestResultEnums.RECORD_EXTRA_ERRORS] = {}
        actual_d = record.to_dict()
        self.assertDictEqual(actual_d, d)
        # Verify that these code paths do not cause crashes and yield non-empty
        # results.
        self.assertTrue(str(record), "str of the record should not be empty.")
        self.assertTrue(repr(record), "the record's repr shouldn't be empty.")
        self.assertTrue(record.json_str(), ("json str of the record should "
                         "not be empty."))

    """ Begin of Tests """
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

    def test_result_record_fail_with_float_extra(self):
        record = records.TestResultRecord(self.tn)
        record.test_begin()
        s = signals.TestFailure(self.details, self.float_extra)
        record.test_fail(s)
        self.verify_record(record=record,
                           result=records.TestResultEnums.TEST_RESULT_FAIL,
                           details=self.details,
                           extras=self.float_extra)

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
        tr1.add_controller_info("MockDevice", ["magicA", "magicB"])
        record2 = records.TestResultRecord(self.tn)
        record2.test_begin()
        s = signals.TestPass(self.details, self.json_extra)
        record2.test_pass(s)
        tr2 = records.TestResult()
        tr2.add_record(record2)
        tr2.add_controller_info("MockDevice", ["magicC"])
        tr2 += tr1
        self.assertTrue(tr2.passed, [tr1, tr2])
        self.assertTrue(tr2.controller_info, {"MockDevice": ["magicC"]})

    def test_result_add_operator_type_mismatch(self):
        record1 = records.TestResultRecord(self.tn)
        record1.test_begin()
        s = signals.TestPass(self.details, self.float_extra)
        record1.test_pass(s)
        tr1 = records.TestResult()
        tr1.add_record(record1)
        expected_msg = "Operand .* of type .* is not a TestResult."
        with self.assertRaisesRegexp(TypeError, expected_msg):
            tr1 += "haha"

    def test_result_fail_class_with_test_signal(self):
        record1 = records.TestResultRecord(self.tn)
        record1.test_begin()
        s = signals.TestPass(self.details, self.float_extra)
        record1.test_pass(s)
        tr = records.TestResult()
        tr.add_record(record1)
        s = signals.TestFailure(self.details, self.float_extra)
        record2 = records.TestResultRecord("SomeTest", s)
        tr.fail_class(record2)
        self.assertEqual(len(tr.passed), 1)
        self.assertEqual(len(tr.failed), 1)
        self.assertEqual(len(tr.executed), 2)

    def test_result_fail_class_with_special_error(self):
        """Call TestResult.fail_class with an error class that requires more
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
                self.msg = "%s %s" % (arg1, arg2)
        se = SpecialError("haha", 42)
        record2 = records.TestResultRecord("SomeTest", se)
        tr.fail_class(record2)
        self.assertEqual(len(tr.passed), 1)
        self.assertEqual(len(tr.failed), 1)
        self.assertEqual(len(tr.executed), 2)

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
        self.assertFalse(tr.is_all_pass)

    def test_is_all_pass_with_fail_class(self):
        """Verifies that is_all_pass yields correct value when fail_class is
        used.
        """
        record1 = records.TestResultRecord(self.tn)
        record1.test_begin()
        record1.test_fail(Exception("haha"))
        tr = records.TestResult()
        tr.fail_class(record1)
        self.assertFalse(tr.is_all_pass)

if __name__ == "__main__":
   unittest.main()