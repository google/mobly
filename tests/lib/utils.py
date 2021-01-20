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

# This module holds util functions that are used in more than one test module.

from mobly import records


def validate_test_result(result):
  """Validate basic properties of a test result.

  The records in each bucket of the test result should have the corresponding
  result enum.

  Args:
    result: The `records.TestResult` object to validate.
  """
  buckets = [
      (result.passed, records.TestResultEnums.TEST_RESULT_PASS),
      (result.failed, records.TestResultEnums.TEST_RESULT_FAIL),
      (result.error, records.TestResultEnums.TEST_RESULT_ERROR),
      (result.skipped, records.TestResultEnums.TEST_RESULT_SKIP),
  ]
  for bucket_list, expected_enum in buckets:
    for record in bucket_list:
      if record.result != expected_enum:
        raise AssertionError('Expected result %s, got %s.' %
                             (expected_enum, record.result))
