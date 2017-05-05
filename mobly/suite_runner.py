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
import collections
import logging
import sys

from mobly import base_test
from mobly import config_parser
from mobly import signals
from mobly import test_runner


class Error(Exception):
    pass


def run_suite(test_classes, argv=None):
    """Execute the test suite in a module.

    This is the default entry point for running a test suite script file
    directly.

    To make your test suite executable, add the following to your file:

        from mobly import suite_runner

        from my.test.lib import foo_test
        from my.test.lib import bar_test
        ...
        if __name__ == '__main__':
            suite_runner.run(foo_test.FooTest, bar_test.BarTest)

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
        '--tests',
        '--test_case',
        nargs='+',
        type=str,
        metavar='[ClassA[.test_a] ClassB[.test_b] ...]',
        help='A list of test classes and optional tests to execute.')
    if not argv:
        argv = sys.argv[1:]
    args = parser.parse_args(argv)
    # Load test config file.
    test_configs = config_parser.load_test_config_file(args.config[0])

    # Check the classes that were passed in
    for test_class in test_classes:
        if not issubclass(test_class, base_test.BaseTestClass):
            logging.error('Test class %s does not extend '
                          'mobly.base_test.BaseTestClass', test_class)
            sys.exit(1)

    # Find the full list of tests to execute
    selected_tests = _compute_selected_tests(test_classes, args.tests)

    # Execute the suite
    ok = True
    for config in test_configs:
        runner = test_runner.TestRunner(config.log_path, config.test_bed_name)
        for (test_class, tests) in selected_tests.items():
            runner.add_test_class(config, test_class, tests)
        try:
            runner.run()
            ok = runner.results.is_all_pass and ok
        except signals.TestAbortAll:
            pass
        except:
            logging.exception('Exception when executing %s.',
                              config.test_bed_name)
            ok = False
    if not ok:
        sys.exit(1)


def _compute_selected_tests(test_classes, selected_tests):
    """Computes class_to_test_name to run for each class from selector strings.

    Args:
        test_classes: (list of class) all classes that are part of this suite.
        selected_tests: (list of string) list of class_to_test_name to execute, eg:
             ['FooTest', 'BarTest',
              'BazTest.test_method_a', 'BazTest.test_method_b'].
             May be empty, in which case all class_to_test_name are selected.

    Returns:
        dict: test class -> list(test name):
        identifiers for TestRunner. For the above example:
        {
            FooTest: None,
            BarTest: None,
            BazTest: ['test_method_a', 'test_method_b'],
        }
    """
    # Map from test class name to instance.
    class_name_lookup = {cls.__name__: cls for cls in test_classes}

    # Map from test class to list of class_to_test_name to execute.
    class_to_test_name = collections.OrderedDict()
    if selected_tests:
        for test in selected_tests:
            if '.' in test:  # Has a test method
                (test_class_name, test_name) = test.split('.')
            else:
                (test_class_name, test_name) = (test, None)
            test_class = class_name_lookup.get(test_class_name)
            if not test_class:
                raise Error('Unknown test class %s' % test_class_name)
            if test_name and test_class not in class_to_test_name:
                # Never seen this class before
                class_to_test_name[test_class] = [test_name]
            elif test_name and class_to_test_name[test_class] is None:
                # Already running all tests in this class, so ignore this extra
                # test.
                pass
            elif test_name:
                class_to_test_name[test_class].append(test_name)
            else:  # No test method; run all class_to_test_name in this class.
                class_to_test_name[test_class] = None
    else:
        for test_class in test_classes:
            class_to_test_name[test_class] = None
    return class_to_test_name
