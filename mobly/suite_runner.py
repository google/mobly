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
        '--test_case',
        nargs='+',
        type=str,
        metavar='[ClassA[.test_a] ClassB[.test_b] ...]',
        help='A list of test classes and optional test methods to execute.')
    if not argv:
        argv = sys.argv[1:]
    args = parser.parse_args(argv)
    # Load test config file.
    test_configs = config_parser.load_test_config_file(args.config[0])

    # Check the classes that were passed in
    for cls in test_classes:
        if not issubclass(cls, base_test.BaseTestClass):
            logging.error('Test class %s does not extend '
                          'mobly.base_test.BaseTestClass', cls)
            sys.exit(1)

    # Find the full list of testcases to execute
    selected_testcases = _compute_selected_testcases(test_classes,
                                                     args.test_case)

    # Execute the suite
    ok = True
    for config in test_configs:
        runner = test_runner.TestRunner(config.log_path, config.test_bed_name)
        for (cls, methods) in selected_testcases.items():
            runner.add_test_case(config, cls, methods)
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


def _compute_selected_testcases(test_classes, selected_test_cases):
    """Computes test methods to run for each class from selector strings.

    This method transforms a list of selector strings (such as FooTest or
    FooTest.test_method_a) to a dict where keys are test classes, and values are
    lists of selected test methods in those classes. None means all test methods
    in that class are selected.

    Args:
        test_classes: (list of class) all classes that are part of this suite.
        selected_test_cases: (list of string) list of testcases to execute, eg:
             ['FooTest', 'BarTest',
              'BazTest.test_method_a', 'BazTest.test_method_b'].
             May be empty, in which case all test classes are selected.

    Returns:
        dict: test class -> list(str, test methods) or None:
        identifiers for TestRunner. For the above example:
        {
            FooTest: None,
            BarTest: None,
            BazTest: ['test_method_a', 'test_method_b'],
        }
    """
    class_to_methods = collections.OrderedDict()
    if not selected_test_cases:
        # No selection is needed; simply run all methods in all classes.
        for test_class in test_classes:
            class_to_methods[test_class] = None
        return class_to_methods

    # The user is selecting some methods to run. Parse the selectors.
    # Dict from test class name to list of test methods to execute (or None for
    # all methods).
    name_to_methods = collections.OrderedDict()
    for test_case in selected_test_cases:
        if '.' in test_case:  # Has a test method
            (class_name, test_method) = test_case.split('.')
            if class_name not in name_to_methods:
                # Never seen this class before
                name_to_methods[class_name] = [test_method]
            elif name_to_methods[class_name] is None:
                # Already running all test methods in this class, so ignore
                # this extra testcase.
                pass
            else:
                name_to_methods[class_name].append(test_method)
        else:  # No test method; run all tests in this class.
            name_to_methods[test_case] = None

    # Now transform class names to class objects.
    # Dict from test class name to instance.
    class_name_lookup = {cls.__name__: cls for cls in test_classes}
    for class_name, test_methods in name_to_methods.items():
        test_class = class_name_lookup.get(class_name)
        if not test_class:
            raise Error('Unknown test class %s' % class_name)
        class_to_methods[test_class] = test_methods

    return class_to_methods
