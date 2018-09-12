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

from __future__ import print_function
from future import standard_library
standard_library.install_aliases()

import argparse
import inspect
import logging
import os
import sys

from mobly import base_test
from mobly import config_parser
from mobly import logger
from mobly import records
from mobly import signals


class Error(Exception):
    pass


def main(argv=None):
    """Execute the test class in a test module.

    This is the default entry point for running a test script file directly.
    In this case, only one test class in a test script is allowed.

    To make your test script executable, add the following to your file:

    .. code-block:: python

        from mobly import test_runner
        ...
        if __name__ == '__main__':
            test_runner.main()

    If you want to implement your own cli entry point, you could use function
    execute_one_test_class(test_class, test_config, test_identifier)

    Args:
        argv: A list that is then parsed as cli args. If None, defaults to cli
            input.
    """
    args = parse_mobly_cli_args(argv)
    # Find the test class in the test script.
    test_class = _find_test_class()
    if args.list_tests:
        _print_test_names(test_class)
        sys.exit(0)
    # Load test config file.
    test_configs = config_parser.load_test_config_file(args.config[0],
                                                       args.test_bed)
    # Parse test specifiers if exist.
    tests = None
    if args.tests:
        tests = args.tests
    # Execute the test class with configs.
    ok = True
    for config in test_configs:
        runner = TestRunner(
            log_dir=config.log_path, test_bed_name=config.test_bed_name)
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


def parse_mobly_cli_args(argv):
    """Parses cli args that are consumed by Mobly.

    This is the arg parsing logic for the default test_runner.main entry point.

    Multiple arg parsers can be applied to the same set of cli input. So you
    can use this logic in addition to any other args you want to parse. This
    function ignores the args that don't apply to default `test_runner.main`.

    Args:
        argv: A list that is then parsed as cli args. If None, defaults to cli
            input.

    Returns:
        Namespace containing the parsed args.
    """
    parser = argparse.ArgumentParser(description='Mobly Test Executable.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '-c',
        '--config',
        nargs=1,
        type=str,
        metavar='<PATH>',
        help='Path to the test configuration file.')
    group.add_argument(
        '-l',
        '--list_tests',
        action='store_true',
        help='Print the names of the tests defined in a script without '
        'executing them. If the script ')
    parser.add_argument(
        '--tests',
        '--test_case',
        nargs='+',
        type=str,
        metavar='[test_a test_b...]',
        help='A list of tests in the test class to execute.')
    parser.add_argument(
        '-tb',
        '--test_bed',
        nargs='+',
        type=str,
        metavar='[<TEST BED NAME1> <TEST BED NAME2> ...]',
        help='Specify which test beds to run tests on.')
    if not argv:
        argv = sys.argv[1:]
    return parser.parse_known_args(argv)[0]


def _find_test_class():
    """Finds the test class in a test script.

    Walk through module members and find the subclass of BaseTestClass. Only
    one subclass is allowed in a test script.

    Returns:
        The test class in the test module.
    """
    test_classes = []
    main_module_members = sys.modules['__main__']
    for _, module_member in main_module_members.__dict__.items():
        if inspect.isclass(module_member):
            if issubclass(module_member, base_test.BaseTestClass):
                test_classes.append(module_member)
    if len(test_classes) != 1:
        logging.error('Expected 1 test class per file, found %s.',
                      [t.__name__ for t in test_classes])
        sys.exit(1)
    return test_classes[0]


def _print_test_names(test_class):
    """Prints the names of all the tests in a test module.

    If the module has generated tests defined based on controller info, this
    may not be able to print the generated tests.

    Args:
        test_class: module, the test module to print names from.
    """
    cls = test_class(config_parser.TestRunConfig())
    try:
        cls.setup_generated_tests()
    except:
        logging.exception('Failed to retrieve generated tests.')
    print('==========> %s <==========' % cls.TAG)
    for name in cls.get_existing_test_names():
        print(name)


class TestRunner(object):
    """The class that instantiates test classes, executes tests, and
    report results.

    One TestRunner instance is associated with one specific output folder and
    testbed. TestRunner.run() will generate a single set of output files and
    results for all tests that have been added to this runner.

    Attributes:
        self.results: The test result object used to record the results of
            this test run.
    """

    class _TestRunInfo(object):
        """Identifies one test class to run, which tests to run, and config to
        run it with.
        """

        def __init__(self,
                     config,
                     test_class,
                     tests=None,
                     test_class_name_suffix=None):
            self.config = config
            self.test_class = test_class
            self.test_class_name_suffix = test_class_name_suffix
            self.tests = tests

    def __init__(self, log_dir, test_bed_name):
        """Constructor for TestRunner.

        Args:
            log_dir: string, root folder where to write logs
            test_bed_name: string, name of the testbed to run tests on
        """
        self._log_dir = log_dir
        self._test_bed_name = test_bed_name

        self.results = records.TestResult()
        self._test_run_infos = []

        self._log_path = None

    def setup_logger(self):
        """Sets up logging for the next test run.

        This is called automatically in 'run', so normally, this method doesn't
        need to be called. Only use this method if you want to use Mobly's
        logger before the test run starts.

        .. code-block:: python

            tr = TestRunner(...)
            tr.setup_logger()
            logging.info(...)
            tr.run()

        """
        if self._log_path is not None:
            return

        self._start_time = logger.get_log_file_timestamp()
        self._log_path = os.path.join(self._log_dir, self._test_bed_name,
                                      self._start_time)
        logger.setup_test_logger(self._log_path, self._test_bed_name)

    def _teardown_logger(self):
        """Tears down logging at the end of the test run.

        This is called automatically in 'run', so normally, this method doesn't
        need to be called. Only use this to change the logger teardown
        behaviour.

        Raises:
            Error: if this is called before the logger is setup.
        """
        if self._log_path is None:
            raise Error('TestRunner._teardown_logger() called before '
                        'TestRunner.setup_logger()!')

        logger.kill_test_logger(logging.getLogger())
        self._log_path = None

    def add_test_class(self, config, test_class, tests=None, name_suffix=None):
        """Adds tests to the execution plan of this TestRunner.

        Args:
            config: config_parser.TestRunConfig, configuration to execute this
                test class with.
            test_class: class, test class to execute.
            tests: list of strings, optional list of test names within the
                class to execute.
            name_suffix: string, suffix to append to the class name for
                reporting. This is used for differentiating the same class
                executed with different parameters in a suite.

        Raises:
            Error: if the provided config has a log_path or test_bed_name which
                differs from the arguments provided to this TestRunner's
                constructor.
        """
        if self._log_dir != config.log_path:
            raise Error(
                'TestRunner\'s log folder is "%s", but a test config with a '
                'different log folder ("%s") was added.' % (self._log_dir,
                                                            config.log_path))
        if self._test_bed_name != config.test_bed_name:
            raise Error(
                'TestRunner\'s test bed is "%s", but a test config with a '
                'different test bed ("%s") was added.' %
                (self._test_bed_name, config.test_bed_name))
        self._test_run_infos.append(
            TestRunner._TestRunInfo(
                config=config,
                test_class=test_class,
                tests=tests,
                test_class_name_suffix=name_suffix))

    def _run_test_class(self, config, test_class, tests=None):
        """Instantiates and executes a test class.

        If tests is None, the tests listed in self.tests will be executed
        instead. If self.tests is empty as well, every test in this test class
        will be executed.

        Args:
            config: A config_parser.TestRunConfig object.
            test_class: class, test class to execute.
            tests: Optional list of test names within the class to execute.
        """
        with test_class(config) as test_instance:
            logging.debug('Executing test class "%s" with config: %s',
                          test_class.__name__, config)
            try:
                cls_result = test_instance.run(tests)
                self.results += cls_result
            except signals.TestAbortAll as e:
                self.results += e.results
                raise e

    def run(self):
        """Executes tests.

        This will instantiate controller and test classes, execute tests, and
        print a summary.

        Raises:
            Error: if no tests have previously been added to this runner using
                add_test_class(...).
        """
        if not self._test_run_infos:
            raise Error('No tests to execute.')

        self.setup_logger()
        summary_writer = records.TestSummaryWriter(
            os.path.join(self._log_path, records.OUTPUT_FILE_SUMMARY))
        try:
            for test_run_info in self._test_run_infos:
                # Set up the test-specific config
                test_config = test_run_info.config.copy()
                test_config.log_path = self._log_path
                test_config.summary_writer = summary_writer
                test_config.test_class_name_suffix = test_run_info.test_class_name_suffix
                try:
                    self._run_test_class(
                        config=test_config,
                        test_class=test_run_info.test_class,
                        tests=test_run_info.tests)
                except signals.TestAbortAll as e:
                    logging.warning(
                        'Abort all subsequent test classes. Reason: %s', e)
                    raise
        finally:
            summary_writer.dump(self.results.summary_dict(),
                                records.TestSummaryEntryType.SUMMARY)
            # Stop and show summary.
            msg = '\nSummary for test run %s@%s: %s\n' % (
                self._test_bed_name, self._start_time,
                self.results.summary_str())
            logging.info(msg.strip())
            self._teardown_logger()
