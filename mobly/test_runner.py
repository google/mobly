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
import collections
import copy
import functools
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
    # Parse cli args.
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
    args = parser.parse_known_args(argv)[0]
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


def _find_test_class():
    """Finds the test class in a test script.

    Walk through module memebers and find the subclass of BaseTestClass. Only
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


def _compute_selected_tests(selected_tests):
    """Computes tests to run for each class from selector strings.

    This function transforms a list of selector strings (such as FooTest or
    FooTest.test_method_a) to an ordered dict where keys are test classes (strings), and
    values are lists of selected test methods (strings) in those classes. 
    None means all methods in that class are selected.

    Args:
        selected_tests: (list of string) list of tests to execute, eg:
            [
                'FooTest',
                'BarTest',
                'BazTest.test_method_a',
                'BazTest.test_method_b'
            ].
            May be empty, in which case all tests in the class are selected.

    Returns:
        dict: str class -> list(str method).
        For above example: 
        {
            'FooTest': None,
            'BarTest': None,
            'BazTest': ['test_method_a', 'test_method_b'],
        }
    """
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
    return test_class_name_to_tests


def _get_all_tests(test_class, config):
    """Returns all test methods (including generated ones) belonging to  test_class(config)."""
    config_copy = config.copy()  # just in case.
    test_instance = test_class(config_copy)
    test_instance.setup_generated_tests
    return test_instance.get_existing_test_names()


def verify_controller_module(module):
    """Verifies a module object follows the required interface for
    controllers.

    A Mobly controller module is a Python lib that can be used to control
    a device, service, or equipment. To be Mobly compatible, a controller
    module needs to have the following members:

        def create(configs):
            [Required] Creates controller objects from configurations.

            Args:
                configs: A list of serialized data like string/dict. Each
                    element of the list is a configuration for a controller
                    object.
            Returns:
                A list of objects.

        def destroy(objects):
            [Required] Destroys controller objects created by the create
            function. Each controller object shall be properly cleaned up
            and all the resources held should be released, e.g. memory
            allocation, sockets, file handlers etc.

            Args:
                A list of controller objects created by the create function.

        def get_info(objects):
            [Optional] Gets info from the controller objects used in a test
            run. The info will be included in test_summary.yaml under
            the key 'ControllerInfo'. Such information could include unique
            ID, version, or anything that could be useful for describing the
            test bed and debugging.

            Args:
                objects: A list of controller objects created by the create
                    function.
            Returns:
                A list of json serializable objects, each represents the
                info of a controller object. The order of the info object
                should follow that of the input objects.

    Registering a controller module declares a test class's dependency the
    controller. If the module config exists and the module matches the
    controller interface, controller objects will be instantiated with
    corresponding configs. The module should be imported first.

    Args:
        module: An object that is a controller module. This is usually
            imported with import statements or loaded by importlib.

    Raises:
        ControllerError: if the module does not match the Mobly controller
            interface, or one of the required members is null.
    """
    required_attributes = ('create', 'destroy', 'MOBLY_CONTROLLER_CONFIG_NAME')
    for attr in required_attributes:
        if not hasattr(module, attr):
            raise signals.ControllerError(
                'Module %s missing required controller module attribute'
                ' %s.' % (module.__name__, attr))
        if not getattr(module, attr):
            raise signals.ControllerError(
                'Controller interface %s in %s cannot be null.' %
                (attr, module.__name__))


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

        def __init__(self, config, test_class, tests=None):
            self.config = config
            self.test_class = test_class
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

        # Controller management. These members will be updated for each class.
        self._controller_registry = {}
        self._controller_destructors = {}

    def add_test_class(self, config, test_class, tests=None):
        """Adds tests to the execution plan of this TestRunner.

        Args:
            config: config_parser.TestRunConfig, configuration to execute this
                test class with.
            test_class: class, test class to execute.
            tests: list of strings, optional list of test names within the
                class to execute.

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

        if not issubclass(test_class, base_test.BaseTestClass):
            raise Error('Test class %s does not extend '
                        'mobly.base_test.BaseTestClass' % test_class.__name__)

        self._test_run_infos.append(
            TestRunner._TestRunInfo(
                config=config, test_class=test_class, tests=tests))

    def select_test_methods(self, test_selections):
        """Edits the execution plan of this TestRunner from selector strings.

        This function take a list of selector strings (such as FooTest or
        FooTest.test_method_a) and edits the execution plan of this TestRunner to 
        run only the selected tests. Note that all specified test classes must have 
        been previously added to this TestRunner before this selection can be made.

        Args:
            test_selections: (list of string) list of tests to execute, eg:
                [
                    'FooTest',
                    'BarTest',
                    'BazTest.test_method_a',
                    'BazTest.test_method_b'
                ].
                May be empty, in which case all tests in the class are selected.
            }
        """
        if not test_selections:
            # if not selecting tests, don't do anything.
            return
        test_selector = _compute_selected_tests(test_selections)

        new_test_run_infos = []
        for test_run_info in self._test_run_infos:
            test_class_name = test_run_info.test_class.__name__
            if test_class_name in test_selector:
                selected_test_methods = test_selector.pop(test_class_name)

                if selected_test_methods:
                    # verify that the selected test methods exist.
                    existing_test_methods = _get_all_tests(
                        test_run_info.test_class, test_run_info.config)
                    nonexistent_methods = [
                        selected_method
                        for selected_method in selected_test_methods
                        if selected_method not in existing_test_methods
                    ]
                    if nonexistent_methods:
                        raise Error(
                            'Trying to selected nonexistent test methods %s from test class %s'
                            % (nonexistent_methods, test_class_name))

                # class and method selections are valid. Add new test_run_info to plan.
                test_run_info.tests = selected_test_methods
                new_test_run_infos.append(test_run_info)
        if test_selector:
            raise Error('Trying to select test methods from classes %s '
                        'that have not been added to TestRunner.' %
                        [item[0] for item in test_selector.items()])
        self._test_run_infos = new_test_run_infos

    def print_all_test_methods(self):
        """Prints all test methods in this TestRunner's execution plan. 

        Prints the test methods that this TestRunner will execute in the following format: 
            FooTest.test_method_a
            FooTest.test_method_b
            BarTest.test_method_a
        """
        test_names_to_print = []
        for test_run_info in self._test_run_infos:
            existing_test_names = _get_all_tests(test_run_info.test_class,
                                                 test_run_info.config)
            prefix = test_run_info.test_class.__name__ + '.'
            if test_run_info.tests:
                assert all(
                    test in existing_test_names for test in test_run_info.tests
                ), 'No method should be specified in test_run_info.tests that is not part of the corresponding class/config\'s existing tess'
                test_names_to_print += [
                    prefix + test for test in test_run_info.tests
                ]
            else:
                test_names_to_print += [
                    prefix + test for test in existing_test_names
                ]
        header = '==========> Preview of Test Execution Plan. <=========='
        print(header)
        print('\n'.join(test_names_to_print))
        print('=' * len(header))

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
        start_time = logger.get_log_file_timestamp()
        log_path = os.path.join(self._log_dir, self._test_bed_name, start_time)
        summary_writer = records.TestSummaryWriter(
            os.path.join(log_path, records.OUTPUT_FILE_SUMMARY))
        logger.setup_test_logger(log_path, self._test_bed_name)
        try:
            for test_run_info in self._test_run_infos:
                # Set up the test-specific config
                test_config = test_run_info.config.copy()
                test_config.log_path = log_path
                test_config.register_controller = functools.partial(
                    self._register_controller, test_config)
                test_config.summary_writer = summary_writer
                try:
                    self._run_test_class(test_config, test_run_info.test_class,
                                         test_run_info.tests)
                except signals.TestAbortAll as e:
                    logging.warning(
                        'Abort all subsequent test classes. Reason: %s', e)
                    raise
                finally:
                    self._unregister_controllers()
        finally:
            # Write controller info and summary to summary file.
            summary_writer.dump(self.results.controller_info,
                                records.TestSummaryEntryType.CONTROLLER_INFO)
            summary_writer.dump(self.results.summary_dict(),
                                records.TestSummaryEntryType.SUMMARY)
            # Stop and show summary.
            msg = '\nSummary for test run %s@%s: %s\n' % (
                self._test_bed_name, start_time, self.results.summary_str())
            self._write_results_json_str(log_path)
            logging.info(msg.strip())
            logger.kill_test_logger(logging.getLogger())

    def _register_controller(self, config, module, required=True,
                             min_number=1):
        """Loads a controller module and returns its loaded devices.

        See the docstring of verify_controller_module() for a description of
        what API a controller module must implement to be compatible with this
        method.

        Args:
            config: A config_parser.TestRunConfig object.
            module: A module that follows the controller module interface.
            required: A bool. If True, failing to register the specified
                controller module raises exceptions. If False, the objects
                failed to instantiate will be skipped.
            min_number: An integer that is the minimum number of controller
                objects to be created. Default is one, since you should not
                register a controller module without expecting at least one
                object.

        Returns:
            A list of controller objects instantiated from controller_module, or
            None if no config existed for this controller and it was not a
            required controller.

        Raises:
            ControllerError:
                * The controller module has already been registered.
                * The actual number of objects instantiated is less than the `min_number`.
                * `required` is True and no corresponding config can be found.
                * Any other error occurred in the registration process.

        """
        verify_controller_module(module)
        # Use the module's name as the ref name
        module_ref_name = module.__name__.split('.')[-1]
        if module_ref_name in self._controller_registry:
            raise signals.ControllerError(
                'Controller module %s has already been registered. It cannot '
                'be registered again.' % module_ref_name)
        # Create controller objects.
        create = module.create
        module_config_name = module.MOBLY_CONTROLLER_CONFIG_NAME
        if module_config_name not in config.controller_configs:
            if required:
                raise signals.ControllerError(
                    'No corresponding config found for %s' %
                    module_config_name)
            logging.warning(
                'No corresponding config found for optional controller %s',
                module_config_name)
            return None
        try:
            # Make a deep copy of the config to pass to the controller module,
            # in case the controller module modifies the config internally.
            original_config = config.controller_configs[module_config_name]
            controller_config = copy.deepcopy(original_config)
            objects = create(controller_config)
        except:
            logging.exception(
                'Failed to initialize objects for controller %s, abort!',
                module_config_name)
            raise
        if not isinstance(objects, list):
            raise signals.ControllerError(
                'Controller module %s did not return a list of objects, abort.'
                % module_ref_name)
        # Check we got enough controller objects to continue.
        actual_number = len(objects)
        if actual_number < min_number:
            module.destroy(objects)
            raise signals.ControllerError(
                'Expected to get at least %d controller objects, got %d.' %
                (min_number, actual_number))
        # Save a shallow copy of the list for internal usage, so tests can't
        # affect internal registry by manipulating the object list.
        self._controller_registry[module_ref_name] = copy.copy(objects)
        # Collect controller information and write to test result.
        # Implementation of 'get_info' is optional for a controller module.
        if hasattr(module, 'get_info'):
            controller_info = module.get_info(copy.copy(objects))
            logging.debug('Controller %s: %s', module_config_name,
                          controller_info)
            self.results.add_controller_info(module_config_name,
                                             controller_info)
        else:
            logging.warning('No optional debug info found for controller %s. '
                            'To provide it, implement get_info in this '
                            'controller module.', module_config_name)
        logging.debug('Found %d objects for controller %s',
                      len(objects), module_config_name)
        destroy_func = module.destroy
        self._controller_destructors[module_ref_name] = destroy_func
        return objects

    def _unregister_controllers(self):
        """Destroy controller objects and clear internal registry.

        This will be called after each test class.
        """
        for name, destroy in self._controller_destructors.items():
            try:
                logging.debug('Destroying %s.', name)
                destroy(self._controller_registry[name])
            except:
                logging.exception('Exception occurred destroying %s.', name)
        self._controller_registry = {}
        self._controller_destructors = {}

    def _write_results_json_str(self, log_path):
        """Writes out a json file with the test result info for easy parsing.

        TODO(#270): Deprecate with old output format.
        """
        path = os.path.join(log_path, 'test_run_summary.json')
        with open(path, 'w') as f:
            f.write(self.results.json_str())
