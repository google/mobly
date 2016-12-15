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

from future import standard_library
standard_library.install_aliases()

import argparse
import copy
import importlib
import inspect
import logging
import os
import pkgutil
import sys

from mobly import base_test
from mobly import config_parser
from mobly import keys
from mobly import logger
from mobly import records
from mobly import signals
from mobly import utils


def main(argv=None):
    """Execute the test class in a test module.

    This is the default entry point for running a test script file directly.
    In this case, only one test class in a test script is allowed.

    To make your test script executable, add the following to your file:

        from mobly import test_runner
        ...
        if __name__ == "__main__":
            test_runner.main()

    If you want to implement your own cli entry point, you could use function
    execute_one_test_class(test_class, test_config, test_identifier)

    Args:
        argv: A list that is then parsed as cli args. If None, defaults to cli
              input.
    """
    # Parse cli args.
    parser = argparse.ArgumentParser(description="Mobly Test Executable.")
    parser.add_argument(
        '-c',
        '--config',
        nargs=1,
        type=str,
        required=True,
        metavar="<PATH>",
        help="Path to the test configuration file.")
    parser.add_argument(
        '--test_case',
        nargs='+',
        type=str,
        metavar="[test_a test_b...]",
        help="A list of test case names in the test script.")
    parser.add_argument(
        '-tb',
        '--test_bed',
        nargs='+',
        type=str,
        metavar="[<TEST BED NAME1> <TEST BED NAME2> ...]",
        help="Specify which test beds to run tests on.")
    if not argv:
        argv = sys.argv[1:]
    args = parser.parse_args(argv)
    # Load test config file.
    test_configs = config_parser.load_test_config_file(args.config[0],
                                                       args.test_bed)
    # Find the test class in the test script.
    test_class = _find_test_class()
    test_class_name = test_class.__name__
    # Parse test case specifiers if exist.
    test_case_names = None
    if args.test_case:
        test_case_names = args.test_case
    test_identifier = [(test_class_name, test_case_names)]
    # Execute the test class with configs.
    ok = True
    for config in test_configs:
        try:
            result = execute_one_test_class(test_class, config,
                                            test_identifier)
            ok = result and ok
        except signals.TestAbortAll:
            pass
        except:
            logging.exception("Error occurred when executing test bed %s",
                              config[keys.Config.key_testbed.value])
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
    main_module_members = sys.modules["__main__"]
    for _, module_member in main_module_members.__dict__.items():
        if inspect.isclass(module_member):
            if issubclass(module_member, base_test.BaseTestClass):
                test_classes.append(module_member)
    if len(test_classes) != 1:
        logging.error("Expected 1 test class per file, found %s.",
                      [t.__name__ for t in test_classes])
        sys.exit(1)
    return test_classes[0]


def execute_one_test_class(test_class, test_config, test_identifier):
    """Executes one specific test class.

    You could call this function in your own cli test entry point if you choose
    to implement your own entry point.

    Args:
        test_class: A subclass of mobly.base_test.BaseTestClass that has the test
                    logic to be executed.
        test_config: A dict representing one set of configs for a test run.
        test_identifier: A list of tuples specifying which test cases to run in
                         the test class.

    Returns:
        True if all tests passed without any error, False otherwise.

    Raises:
        If signals.TestAbortAll is raised by a test run, pipe it through.
    """
    tr = TestRunner(test_config, test_identifier)
    try:
        tr.run([test_class])
        return tr.results.is_all_pass
    except signals.TestAbortAll:
        raise
    except:
        logging.exception("Exception when executing %s.", tr.testbed_name)
    finally:
        tr.stop()


class TestRunner(object):
    """The class that instantiates test classes, executes test cases, and
    report results.

    Attributes:
        self.test_run_info: A dictionary containing the information needed by
                            test classes for this test run, including params,
                            controllers, and other objects. All of these will
                            be passed to test classes.
        self.test_configs: A dictionary that is the original test configuration
                           passed in by user.
        self.id: A string that is the unique identifier of this test run.
        self.log_path: A string representing the path of the dir under which
                       all logs from this test run should be written.
        self.log: The logger object used throughout this test run.
        self.controller_registry: A dictionary that holds the controller
                                  objects used in a test run.
        self.controller_destructors: A dictionary that holds the controller
                                     distructors. Keys are controllers' names.
        self.test_classes: A dictionary where we can look up the test classes
                           by name to instantiate.
        self.run_list: A list of tuples specifying what tests to run.
        self.results: The test result object used to record the results of
                      this test run.
        self.running: A boolean signifies whether this test run is ongoing or
                      not.
    """

    def __init__(self, test_configs, run_list):
        self.test_run_info = {}
        self.test_configs = test_configs
        self.testbed_configs = self.test_configs[keys.Config.key_testbed.value]
        self.testbed_name = self.testbed_configs[
            keys.Config.key_testbed_name.value]
        start_time = logger.get_log_file_timestamp()
        self.id = "{}@{}".format(self.testbed_name, start_time)
        # log_path should be set before parsing configs.
        l_path = os.path.join(
            self.test_configs[keys.Config.key_log_path.value],
            self.testbed_name, start_time)
        self.log_path = os.path.abspath(l_path)
        logger.setup_test_logger(self.log_path, self.testbed_name)
        self.log = logging.getLogger()
        self.controller_registry = {}
        self.controller_destructors = {}
        self.run_list = run_list
        self.results = records.TestResult()
        self.running = False
        self.test_classes = {}

    @staticmethod
    def verify_controller_module(module):
        """Verifies a module object follows the required interface for
        controllers.

        Args:
            module: An object that is a controller module. This is usually
                    imported with import statements or loaded by importlib.

        Raises:
            ControllerError is raised if the module does not match the Mobly
            controller interface, or one of the required members is null.
        """
        required_attributes = ("create", "destroy",
                               "MOBLY_CONTROLLER_CONFIG_NAME")
        for attr in required_attributes:
            if not hasattr(module, attr):
                raise signals.ControllerError(
                    ("Module %s missing required "
                     "controller module attribute %s.") % (module.__name__,
                                                           attr))
            if not getattr(module, attr):
                raise signals.ControllerError(
                    ("Controller interface %s in %s cannot be null.") % (
                     attr, module.__name__))

    def register_controller(self, module, required=True, min_number=1):
        """Registers an Mobly controller module for a test run.

        An Mobly controller module is a Python lib that can be used to control
        a device, service, or equipment. To be Mobly compatible, a controller
        module needs to have the following members:

            def create(configs):
                [Required] Creates controller objects from configurations.
                Args:
                    configs: A list of serialized data like string/dict. Each
                             element of the list is a configuration for a
                             controller object.
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
                run. The info will be included in test_result_summary.json under
                the key "ControllerInfo". Such information could include unique
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
            module: A module that follows the controller module interface.
            required: A bool. If True, failing to register the specified
                      controller module raises exceptions. If False, the objects
                      failed to instantiate will be skipped.
            min_number: An integer that is the minimum number of controller
                        objects to be created. Default is one, since you should
                        not register a controller module without expecting at
                        least one object.

        Returns:
            A list of controller objects instantiated from controller_module, or
            None.

        Raises:
            When required is True, ControllerError is raised if no corresponding
            config can be found.
            Regardless of the value of "required", ControllerError is raised if
            the controller module has already been registered or any other error
            occurred in the registration process.
            If the actual number of objects instantiated is less than the
            min_number, ControllerError is raised.
        """
        TestRunner.verify_controller_module(module)
        # Use the module's name as the ref name
        module_ref_name = module.__name__.split('.')[-1]
        if module_ref_name in self.controller_registry:
            raise signals.ControllerError(
                ("Controller module %s has already been registered. It cannot "
                 "be registered again.") % module_ref_name)
        # Create controller objects.
        create = module.create
        module_config_name = module.MOBLY_CONTROLLER_CONFIG_NAME
        if module_config_name not in self.testbed_configs:
            if required:
                raise signals.ControllerError(
                    "No corresponding config found for %s" %
                    module_config_name)
            self.log.warning(
                "No corresponding config found for optional controller %s",
                module_config_name)
            return None
        try:
            # Make a deep copy of the config to pass to the controller module,
            # in case the controller module modifies the config internally.
            original_config = self.testbed_configs[module_config_name]
            controller_config = copy.deepcopy(original_config)
            objects = create(controller_config)
        except:
            self.log.exception(
                "Failed to initialize objects for controller %s, abort!",
                module_config_name)
            raise
        if not isinstance(objects, list):
            raise signals.ControllerError(
                "Controller module %s did not return a list of objects, abort."
                % module_ref_name)
        # Check we got enough controller objects to continue.
        actual_number = len(objects)
        if actual_number < min_number:
            module.destroy(objects)
            raise signals.ControllerError(
                "Expected to get at least %d controller objects, got %d." %
                (min_number, actual_number))
        self.controller_registry[module_ref_name] = objects
        # Collect controller information and write to test result.
        # Implementation of "get_info" is optional for a controller module.
        if hasattr(module, "get_info"):
            controller_info = module.get_info(objects)
            logging.debug("Controller %s: %s", module_config_name,
                          controller_info)
            self.results.add_controller_info(module_config_name,
                                             controller_info)
        else:
            self.log.warning("No controller info obtained for %s",
                             module_config_name)
        self.log.debug("Found %d objects for controller %s", len(objects),
                      module_config_name)
        destroy_func = module.destroy
        self.controller_destructors[module_ref_name] = destroy_func
        return objects

    def unregister_controllers(self):
        """Destroy controller objects and clear internal registry.

        This will be called at the end of each TestRunner.run call.
        """
        for name, destroy in self.controller_destructors.items():
            try:
                self.log.debug("Destroying %s.", name)
                destroy(self.controller_registry[name])
            except:
                self.log.exception("Exception occurred destroying %s.", name)
        self.controller_registry = {}
        self.controller_destructors = {}

    def _parse_config(self, test_configs):
        """Parses the test configuration and unpacks objects and parameters
        into a dictionary to be passed to test classes.

        Args:
            test_configs: A json object representing the test configurations.
        """
        self.test_run_info[
            keys.Config.ikey_testbed_name.value] = self.testbed_name
        # Unpack other params.
        self.test_run_info["register_controller"] = self.register_controller
        self.test_run_info[keys.Config.ikey_logpath.value] = self.log_path
        self.test_run_info[keys.Config.ikey_logger.value] = self.log
        cli_args = test_configs.get(keys.Config.ikey_cli_args.value)
        self.test_run_info[keys.Config.ikey_cli_args.value] = cli_args
        user_param_pairs = []
        for item in test_configs.items():
            if item[0] not in keys.Config.reserved_keys.value:
                user_param_pairs.append(item)
        self.test_run_info[keys.Config.ikey_user_param.value] = copy.deepcopy(
            dict(user_param_pairs))

    def _run_test_class(self, test_cls_name, test_cases=None):
        """Instantiates and executes a test class.

        If test_cases is None, the test cases listed by self.tests will be
        executed instead. If self.tests is empty as well, no test case in this
        test class will be executed.

        Args:
            test_cls_name: Name of the test class to execute.
            test_cases: List of test case names to execute within the class.

        Raises:
            ValueError is raised if the requested test class could not be found
            in the test_paths directories.
        """
        try:
            test_cls = self.test_classes[test_cls_name]
        except KeyError:
            raise ValueError(("Test class %s is not found, did you add it to "
                              "this TestRunner?") % test_cls_name)
        with test_cls(self.test_run_info) as test_cls_instance:
            try:
                cls_result = test_cls_instance.run(test_cases)
                self.results += cls_result
            except signals.TestAbortAll as e:
                self.results += e.results
                raise e

    def run(self, test_classes):
        """Executes test cases.

        This will instantiate controller and test classes, and execute test
        classes. This can be called multiple times to repeatly execute the
        requested test cases.

        A call to TestRunner.stop should eventually happen to conclude the life
        cycle of a TestRunner.

        Args:
            test_classes: A list of test classes. They should be subclasses of
                          base_test.BaseTestClass
        """
        if not self.running:
            self.running = True
        for tc in test_classes:
            self.test_classes[tc.__name__] = tc
        # Initialize controller objects and pack appropriate objects/params
        # to be passed to test class.
        self._parse_config(self.test_configs)
        self.log.debug("Executing run list %s.", self.run_list)
        for test_cls_name, test_case_names in self.run_list:
            if not self.running:
                break
            if test_case_names:
                self.log.debug("Executing test cases %s in test class %s.",
                               test_case_names, test_cls_name)
            else:
                self.log.debug("Executing test class %s", test_cls_name)
            try:
                self._run_test_class(test_cls_name, test_case_names)
            except signals.TestAbortAll as e:
                self.log.warning(
                    "Abort all subsequent test classes. Reason: %s", e)
                raise
            finally:
                self.unregister_controllers()

    def stop(self):
        """Releases resources from test run. Should always be called after
        TestRunner.run finishes.

        This function concludes a test run and writes out a test report.
        """
        if self.running:
            msg = "\nSummary for test run %s: %s\n" % (
                self.id, self.results.summary_str())
            self._write_results_json_str()
            self.log.info(msg.strip())
            logger.kill_test_logger(self.log)
            self.running = False

    def _write_results_json_str(self):
        """Writes out a json file with the test result info for easy parsing.

        TODO(angli): This should be replaced by standard log record mechanism.
        """
        path = os.path.join(self.log_path, "test_run_summary.json")
        with open(path, 'w') as f:
            f.write(self.results.json_str())
