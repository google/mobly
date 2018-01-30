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
        self._test_run_infos.append(
            TestRunner._TestRunInfo(
                config=config, test_class=test_class, tests=tests))

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
                * The actual number of objects instantiated is less than the
                * `min_number`.
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
        logging.debug('Found %d objects for controller %s', len(objects),
                      module_config_name)
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
