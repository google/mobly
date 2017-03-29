#!/usr/bin/env python3.4
#
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

import argparse
import logging
import sys

from mobly import test_runner
from mobly import config_parser
from mobly import signals


def run_suite(test_classes, argv=None):
    """Execute the test suite in a module.

    This is the default entry point for running a test suite script file
    directly.

    To make your test suite executable, add the following to your file:

        from mobly import suite_runner
        ...
        if __name__ == '__main__':
            suite_runner.run(my_test_1.MyTest1, my_test_2.MyTest2)

    Args:
        test_classes: List of python classes containing Mobly tests.
        argv: A list that is then parsed as cli args. If None, defaults to cli
              input.
    """
    # Parse cli args.
    parser = argparse.ArgumentParser(description='Mobly Suite Executable.')
    parser.add_argument(
        '-c',
        '--config',
        nargs=1,
        type=str,
        required=True,
        metavar='<PATH>',
        help='Path to the test configuration file.')
    parser.add_argument(
        '--test_case',
        nargs='+',
        type=str,
        metavar='[ClassA[.test_a] ClassB[.test_b] ...]',
        help='A list of test classes and optional test methods to execute.')
    parser.add_argument(
        '-tb',
        '--test_bed',
        nargs='+',
        type=str,
        metavar='[<TEST BED NAME1> <TEST BED NAME2> ...]',
        help='Specify which test beds to run tests on.')
    if not argv:
        argv = sys.argv[1:]
    args = parser.parse_args(argv)
    # Load test config file.
    test_configs = config_parser.load_test_config_file(args.config[0],
                                                       args.test_bed)

    # Choose which tests to run
    test_identifiers = _compute_test_identifiers(test_classes, args.test_case)

    # Execute the suite
    ok = True
    for config in test_configs:
        runner = test_runner.TestRunner(config, test_identifiers)
        try:
            try:
                runner.run(test_classes)
                ok = runner.results.is_all_pass and ok
            except signals.TestAbortAll:
                pass
            except:
                logging.exception('Exception when executing %s.',
                                  runner.test_configs.test_bed_name)
                ok = False
        finally:
            runner.stop()
    if not ok:
        sys.exit(1)


def _compute_test_identifiers(test_classes, selected_test_cases):
    """Computes a list of test identifiers for TestRunner from list of strings.

    Args:
        test_classes: (list of class) all classes that are part of this suite.
        selected_test_cases: (list of string) list of testcases to execute, eg:
             ['Test1', 'Test2', 'Test3.test_method_a', 'Test3.test_method_b'].
             May be empty, in which case all test classes are selected.

    Returns:
        (list of tuple) identifiers for TestRunner. For the above example:
        [
            ('Test1', None),
            ('Test2', None),
            ('Test3', ['test_method_a', 'test_method_b']),
        ]
    """
    tests = {}  # map from test class name to list of methods
    if selected_test_cases:
        for test_case in selected_test_cases:
            if '.' in test_case:  # has a test method
                (test_class, test_method) = test_case.split('.')
                if test_class not in tests:
                    tests[test_class] = [test_method]
                elif tests[test_class] is None:
                    # Already running all test methods in this class, so ignore
                    # this extra testcase.
                    pass
                else:
                    tests[test_class].append(test_method)
            else:  # no test method; run all tests in this class.
                tests[test_case] = None
    else:
        for test_class in test_classes:
            tests[test_class.__name__] = None
    return tests.items()
