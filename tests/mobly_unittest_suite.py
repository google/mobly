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

import sys
import unittest

import mobly_android_device_test
import mobly_asserts_test
import mobly_base_class_test
import mobly_logger_test
import mobly_records_test
import mobly_sl4a_client_test
import mobly_test_runner_test
import mobly_utils_test


def compile_suite():
    test_classes_to_run = [
        mobly_asserts_test.MoblyAssertsTest,
        mobly_base_class_test.MoblyBaseClassTest,
        mobly_test_runner_test.MoblyTestRunnerTest,
        mobly_android_device_test.MoblyAndroidDeviceTest,
        mobly_records_test.MoblyRecordsTest,
        mobly_sl4a_client_test.MoblySl4aClientTest,
        mobly_utils_test.MoblyUtilsTest,
        mobly_logger_test.MoblyLoggerTest
    ]

    loader = unittest.TestLoader()

    suites_list = []
    for test_class in test_classes_to_run:
        suite = loader.loadTestsFromTestCase(test_class)
        suites_list.append(suite)

    big_suite = unittest.TestSuite(suites_list)
    return big_suite


if __name__ == "__main__":
    # This is the entry point for running all Mobly unit tests.
    runner = unittest.TextTestRunner()
    results = runner.run(compile_suite())
    sys.exit(not results.wasSuccessful())
