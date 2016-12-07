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

from tests.mobly import asserts_test
from tests.mobly import base_test_test
from tests.mobly import logger_test
from tests.mobly import records_test
from tests.mobly import test_runner_test
from tests.mobly import utils_test
from tests.mobly.controllers import android_device_test
from tests.mobly.controllers.android_device_lib import sl4a_client_test

def compile_suite():
    test_classes_to_run = [
        android_device_test.AndroidDeviceTest,
        asserts_test.AssertsTest,
        base_test_test.BaseTestTest,
        logger_test.LoggerTest,
        records_test.RecordsTest,
        sl4a_client_test.Sl4aClientTest,
        test_runner_test.TestRunnerTest,
        utils_test.UtilsTest,
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
