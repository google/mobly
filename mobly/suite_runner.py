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
"""Runner for Mobly test suites.

To create a test suite, call suite_runner.run_suite() with one or more
individual test classes. For example:

.. code-block:: python

  from mobly import suite_runner

  from my.test.lib import foo_test
  from my.test.lib import bar_test
  ...
  if __name__ == '__main__':
    suite_runner.run_suite(foo_test.FooTest, bar_test.BarTest)
"""

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
  """Executes multiple test classes as a suite.

  This is the default entry point for running a test suite script file
  directly.

  Args:
    test_classes: List of python classes containing Mobly tests.
    argv: A list that is then parsed as cli args. If None, defaults to cli
      input.
  """
  # Parse cli args.
  parser = argparse.ArgumentParser(description='Mobly Suite Executable.')
  parser.add_argument('-c',
                      '--config',
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
  test_configs = config_parser.load_test_config_file(args.config)

  # Check the classes that were passed in
  for test_class in test_classes:
    if not issubclass(test_class, base_test.BaseTestClass):
      logging.error(
          'Test class %s does not extend '
          'mobly.base_test.BaseTestClass', test_class)
      sys.exit(1)

  # Find the full list of tests to execute
  selected_tests = compute_selected_tests(test_classes, args.tests)

  # Execute the suite
  ok = True
  for config in test_configs:
    runner = test_runner.TestRunner(config.log_path, config.testbed_name)
    with runner.mobly_logger():
      for (test_class, tests) in selected_tests.items():
        runner.add_test_class(config, test_class, tests)
      try:
        runner.run()
        ok = runner.results.is_all_pass and ok
      except signals.TestAbortAll:
        pass
      except Exception:
        logging.exception('Exception when executing %s.', config.testbed_name)
        ok = False
  if not ok:
    sys.exit(1)


def compute_selected_tests(test_classes, selected_tests):
  """Computes tests to run for each class from selector strings.

  This function transforms a list of selector strings (such as FooTest or
  FooTest.test_method_a) to a dict where keys are test_name classes, and
  values are lists of selected tests in those classes. None means all tests in
  that class are selected.

  Args:
    test_classes: list of strings, names of all the classes that are part
      of a suite.
    selected_tests: list of strings, list of tests to execute. If empty,
      all classes `test_classes` are selected. E.g.

      .. code-block:: python

        [
          'FooTest',
          'BarTest',
          'BazTest.test_method_a',
          'BazTest.test_method_b'
        ]

  Returns:
    dict: Identifiers for TestRunner. Keys are test class names; valures
      are lists of test names within class. E.g. the example in
      `selected_tests` would translate to:

      .. code-block:: python

        {
          FooTest: None,
          BarTest: None,
          BazTest: ['test_method_a', 'test_method_b']
        }

      This dict is easy to consume for `TestRunner`.
  """
  class_to_tests = collections.OrderedDict()
  if not selected_tests:
    # No selection is needed; simply run all tests in all classes.
    for test_class in test_classes:
      class_to_tests[test_class] = None
    return class_to_tests

  # The user is selecting some tests to run. Parse the selectors.
  # Dict from test_name class name to list of tests to execute (or None for all
  # tests).
  test_class_name_to_tests = collections.OrderedDict()
  for test_name in selected_tests:
    if '.' in test_name:  # Has a test method
      (test_class_name, test_name) = test_name.split('.')
      if test_class_name not in test_class_name_to_tests:
        # Never seen this class before
        test_class_name_to_tests[test_class_name] = [test_name]
      elif test_class_name_to_tests[test_class_name] is None:
        # Already running all tests in this class, so ignore this extra
        # test.
        pass
      else:
        test_class_name_to_tests[test_class_name].append(test_name)
    else:  # No test method; run all tests in this class.
      test_class_name_to_tests[test_name] = None

  # Now transform class names to class objects.
  # Dict from test_name class name to instance.
  class_name_to_class = {cls.__name__: cls for cls in test_classes}
  for test_class_name, tests in test_class_name_to_tests.items():
    test_class = class_name_to_class.get(test_class_name)
    if not test_class:
      raise Error('Unknown test_name class %s' % test_class_name)
    class_to_tests[test_class] = tests

  return class_to_tests
