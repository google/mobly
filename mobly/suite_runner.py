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

These is just example code to help users run a collection of Mobly test
classes. Users can use it as is or customize it based on their requirements.

There are two ways to use this runner.

1. Call suite_runner.run_suite() with one or more individual test classes. This
is for users who just need to execute a collection of test classes without any
additional steps.

.. code-block:: python

  from mobly import suite_runner

  from my.test.lib import foo_test
  from my.test.lib import bar_test
  ...
  if __name__ == '__main__':
    suite_runner.run_suite(foo_test.FooTest, bar_test.BarTest)

2. Create a subclass of base_suite.BaseSuite and add the individual test
classes. Using the BaseSuite class allows users to define their own setup
and teardown steps on the suite level as well as custom config for each test
class.

.. code-block:: python

  from mobly import base_suite
  from mobly import suite_runner

  from my.path import MyFooTest
  from my.path import MyBarTest


  class MySuite(base_suite.BaseSuite):

    def setup_suite(self, config):
      # Add a class with default config.
      self.add_test_class(MyFooTest)
      # Add a class with test selection.
      self.add_test_class(MyBarTest,
                          tests=['test_a', 'test_b'])
      # Add the same class again with a custom config and suffix.
      my_config = some_config_logic(config)
      self.add_test_class(MyBarTest,
                          config=my_config,
                          name_suffix='WithCustomConfig')


  if __name__ == '__main__':
    suite_runner.run_suite_class()
"""
import argparse
import collections
import inspect
import logging
import sys

from mobly import base_test
from mobly import base_suite
from mobly import config_parser
from mobly import signals
from mobly import test_runner


class Error(Exception):
  pass


def _parse_cli_args(argv):
  """Parses cli args that are consumed by Mobly.

  Args:
    argv: A list that is then parsed as cli args. If None, defaults to cli
      input.

  Returns:
    Namespace containing the parsed args.
  """
  parser = argparse.ArgumentParser(description='Mobly Suite Executable.')
  group = parser.add_mutually_exclusive_group(required=True)
  group.add_argument('-c',
                     '--config',
                     type=str,
                     metavar='<PATH>',
                     help='Path to the test configuration file.')
  group.add_argument(
      '-l',
      '--list_tests',
      action='store_true',
      help='Print the names of the tests defined in a script without '
      'executing them.')
  parser.add_argument('--tests',
                      '--test_case',
                      nargs='+',
                      type=str,
                      metavar='[ClassA[.test_a] ClassB[.test_b] ...]',
                      help='A list of test classes and optional tests to execute.')
  parser.add_argument('-tb',
                      '--test_bed',
                      nargs='+',
                      type=str,
                      metavar='[<TEST BED NAME1> <TEST BED NAME2> ...]',
                      help='Specify which test beds to run tests on.')

  parser.add_argument('-v',
                      '--verbose',
                      action='store_true',
                      help='Set console logger level to DEBUG')
  if not argv:
    argv = sys.argv[1:]
  return parser.parse_known_args(argv)[0]


def _find_suite_class():
  """Finds the test suite class in the current module.

  Walk through module members and find the subclass of BaseSuite. Only
  one subclass is allowed in a module.

  Returns:
      The test suite class in the test module.
  """
  test_suites = []
  main_module_members = sys.modules['__main__']
  for _, module_member in main_module_members.__dict__.items():
    if inspect.isclass(module_member):
      if issubclass(module_member, base_suite.BaseSuite):
        test_suites.append(module_member)
  if len(test_suites) != 1:
    logging.error('Expected 1 test class per file, found %s.',
                  [t.__name__ for t in test_suites])
    sys.exit(1)
  return test_suites[0]


def _print_test_names(test_classes):
  """Prints the names of all the tests in all test classes.
  If the class has generated tests defined based on controller info, this
  may not be able to print the generated tests.
  Args:
    test_classes: classes, the test classes to print names from.
  """
  for test_class in test_classes:
    cls = test_class(config_parser.TestRunConfig())
    test_names = []
    try:
      test_names = cls.get_test_names()
    except Exception:
      logging.exception('Failed to retrieve generated tests.')
    print('==========> %s <==========' % cls.TAG)
    for name in test_names:
      print(f"{cls.TAG}.{name}")


def run_suite_class(argv=None):
  """Executes tests in the test suite.

  Args:
    argv: A list that is then parsed as CLI args. If None, defaults to sys.argv.
  """
  cli_args = _parse_cli_args(argv)
  suite_class = _find_suite_class()
  if cli_args.list_tests:
    _print_test_names([suite_class])
    sys.exit(0)
  test_configs = config_parser.load_test_config_file(cli_args.config,
                                                     cli_args.test_bed)
  config_count = len(test_configs)
  if config_count != 1:
    logging.error('Expect exactly one test config, found %d', config_count)
  config = test_configs[0]
  runner = test_runner.TestRunner(
      log_dir=config.log_path, testbed_name=config.testbed_name)
  suite = suite_class(runner, config)
  console_level = logging.DEBUG if cli_args.verbose else logging.INFO
  ok = False
  with runner.mobly_logger(console_level=console_level):
    try:
      suite.setup_suite(config.copy())
      try:
        runner.run()
        ok = runner.results.is_all_pass
        print(ok)
      except signals.TestAbortAll:
        pass
    finally:
      suite.teardown_suite()
  if not ok:
    sys.exit(1)


def run_suite(test_classes, argv=None):
  """Executes multiple test classes as a suite.

  This is the default entry point for running a test suite script file
  directly.

  Args:
    test_classes: List of python classes containing Mobly tests.
    argv: A list that is then parsed as cli args. If None, defaults to cli
      input.
  """
  args = _parse_cli_args(argv)

  # Check the classes that were passed in
  for test_class in test_classes:
    if not issubclass(test_class, base_test.BaseTestClass):
      logging.error(
          'Test class %s does not extend '
          'mobly.base_test.BaseTestClass', test_class)
      sys.exit(1)

  if args.list_tests:
    _print_test_names(test_classes)
    sys.exit(0)

  # Load test config file.
  test_configs = config_parser.load_test_config_file(args.config,
                                                     args.test_bed)
  # Find the full list of tests to execute
  selected_tests = compute_selected_tests(test_classes, args.tests)

  console_level = logging.DEBUG if args.verbose else logging.INFO
  # Execute the suite
  ok = True
  for config in test_configs:
    runner = test_runner.TestRunner(config.log_path, config.testbed_name)
    with runner.mobly_logger(console_level=console_level):
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
      (test_class_name, test_name) = test_name.split('.', maxsplit=1)
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
