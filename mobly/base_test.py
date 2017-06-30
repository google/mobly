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

import collections
import functools
import inspect
import logging

from mobly import logger
from mobly import records
from mobly import signals
from mobly import utils

# Macro strings for test result reporting
TEST_CASE_TOKEN = '[Test]'
RESULT_LINE_TEMPLATE = TEST_CASE_TOKEN + ' %s %s'


class Error(Exception):
    """Raised for exceptions that occured in BaseTestClass."""


class BaseTestClass(object):
    """Base class for all test classes to inherit from.

    This class gets all the controller objects from test_runner and executes
    the tests requested within itself.

    Most attributes of this class are set at runtime based on the configuration
    provided.

    The default logger in logging module is set up for each test run. If you
    want to log info to the test run output file, use `logging` directly, like
    `logging.info`.

    Attributes:
        tests: A list of strings, each representing a test method name.
        TAG: A string used to refer to a test class. Default is the test class
             name.
        results: A records.TestResult object for aggregating test results from
                 the execution of tests.
        current_test_name: A string that's the name of the test method currently
                           being executed. If no test is executing, this should
                           be None.
        log_path: string, specifies the root directory for all logs written
                  by a test run.
        test_bed_name: string, the name of the test bed used by a test run.
        controller_configs: dict, configs used for instantiating controller
                            objects.
        user_params: dict, custom parameters from user, to be consumed by
                     the test logic.
        register_controller: func, used by test classes to register
                             controller modules.
    """

    TAG = None

    def __init__(self, configs):
        """Constructor of BaseTestClass.

        The constructor takes a config_parser.TestRunConfig object and which has
        all the information needed to execute this test class, like log_path
        and controller configurations. For details, see the definition of class
        config_parser.TestRunConfig.

        Args:
            configs: A config_parser.TestRunConfig object.
        """
        self.tests = []
        if not self.TAG:
            self.TAG = self.__class__.__name__
        # Set params.
        self.log_path = configs.log_path
        self.controller_configs = configs.controller_configs
        self.test_bed_name = configs.test_bed_name
        self.user_params = configs.user_params
        self.register_controller = configs.register_controller
        self.results = records.TestResult()
        self.current_test_name = None
        self._generated_test_table = collections.OrderedDict()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._safe_exec_func(self.clean_up)

    def unpack_userparams(self,
                          req_param_names=None,
                          opt_param_names=None,
                          **kwargs):
        """An optional function that unpacks user defined parameters into
        individual variables.

        After unpacking, the params can be directly accessed with self.xxx.

        If a required param is not provided, an exception is raised. If an
        optional param is not provided, a warning line will be logged.

        To provide a param, add it in the config file or pass it in as a kwarg.
        If a param appears in both the config file and kwarg, the value in the
        config file is used.

        User params from the config file can also be directly accessed in
        self.user_params.

        Args:
            req_param_names: A list of names of the required user params.
            opt_param_names: A list of names of the optional user params.
            **kwargs: Arguments that provide default values.
                e.g. unpack_userparams(required_list, opt_list, arg_a='hello')
                     self.arg_a will be 'hello' unless it is specified again in
                     required_list or opt_list.

        Raises:
            Error is raised if a required user params is not provided.
        """
        req_param_names = req_param_names or []
        opt_param_names = opt_param_names or []
        for k, v in kwargs.items():
            if k in self.user_params:
                v = self.user_params[k]
            setattr(self, k, v)
        for name in req_param_names:
            if hasattr(self, name):
                continue
            if name not in self.user_params:
                raise Error('Missing required user param "%s" in test '
                            'configuration.' % name)
            setattr(self, name, self.user_params[name])
        for name in opt_param_names:
            if hasattr(self, name):
                continue
            if name in self.user_params:
                setattr(self, name, self.user_params[name])
            else:
                logging.warning('Missing optional user param "%s" in '
                                'configuration, continue.', name)

    def setup_generated_tests(self):
        """Preprocesses that need to be done before setup_class.

        This phase is used to do pre-test processes like generating tests.
        This is the only place `self.generate_tests` should be called.

        If this function throws an error, the test class will be marked failure
        and the "Requested" field will be 0 because the number of tests
        requested is unknown at this point.
        """

    def _setup_class(self):
        """Proxy function to guarantee the base implementation of setup_class
        is called.
        """
        self.setup_class()

    def setup_class(self):
        """Setup function that will be called before executing any test in the
        class.

        To signal setup failure, use asserts or raise your own exception.

        Implementation is optional.
        """

    def teardown_class(self):
        """Teardown function that will be called after all the selected tests in
        the test class have been executed.

        Implementation is optional.
        """

    def _setup_test(self, test_name):
        """Proxy function to guarantee the base implementation of setup_test is
        called.
        """
        self.current_test_name = test_name
        try:
            # Write test start token to adb log if android device is attached.
            for ad in self.android_devices:
                ad.sl4a.logV('%s BEGIN %s' % (TEST_CASE_TOKEN, test_name))
        except:
            pass
        self.setup_test()

    def setup_test(self):
        """Setup function that will be called every time before executing each
        test method in the test class.

        To signal setup failure, use asserts or raise your own exception.

        Implementation is optional.
        """

    def _teardown_test(self, test_name):
        """Proxy function to guarantee the base implementation of teardown_test
        is called.
        """
        try:
            # Write test end token to adb log if android device is attached.
            for ad in self.android_devices:
                ad.sl4a.logV('%s END %s' % (TEST_CASE_TOKEN, test_name))
        except:
            pass
        try:
            self.teardown_test()
        finally:
            self.current_test_name = None

    def teardown_test(self):
        """Teardown function that will be called every time a test method has
        been executed.

        Implementation is optional.
        """

    def _on_fail(self, record):
        """Proxy function to guarantee the base implementation of on_fail is
        called.

        Args:
            record: The records.TestResultRecord object for the failed test.
        """
        test_name = record.test_name
        if record.details:
            logging.error(record.details)
        begin_time = logger.epoch_to_log_line_timestamp(record.begin_time)
        logging.info(RESULT_LINE_TEMPLATE, test_name, record.result)
        self.on_fail(test_name, begin_time)

    def on_fail(self, test_name, begin_time):
        """A function that is executed upon a test failure.

        User implementation is optional.

        Args:
            test_name: Name of the test that triggered this function.
            begin_time: Logline format timestamp taken when the test started.
        """

    def _on_pass(self, record):
        """Proxy function to guarantee the base implementation of on_pass is
        called.

        Args:
            record: The records.TestResultRecord object for the passed test.
        """
        test_name = record.test_name
        begin_time = logger.epoch_to_log_line_timestamp(record.begin_time)
        msg = record.details
        if msg:
            logging.info(msg)
        logging.info(RESULT_LINE_TEMPLATE, test_name, record.result)
        self.on_pass(test_name, begin_time)

    def on_pass(self, test_name, begin_time):
        """A function that is executed upon a test passing.

        Implementation is optional.

        Args:
            test_name: Name of the test that triggered this function.
            begin_time: Logline format timestamp taken when the test started.
        """

    def _on_skip(self, record):
        """Proxy function to guarantee the base implementation of on_skip is
        called.

        Args:
            record: The records.TestResultRecord object for the skipped test.
        """
        test_name = record.test_name
        begin_time = logger.epoch_to_log_line_timestamp(record.begin_time)
        logging.info(RESULT_LINE_TEMPLATE, test_name, record.result)
        logging.info('Reason to skip: %s', record.details)
        self.on_skip(test_name, begin_time)

    def on_skip(self, test_name, begin_time):
        """A function that is executed upon a test being skipped.

        Implementation is optional.

        Args:
            test_name: Name of the test that triggered this function.
            begin_time: Logline format timestamp taken when the test started.
        """

    def _exec_procedure_func(self, func, tr_record):
        """Executes a procedure function like on_pass, on_fail etc.

        This function will alternate the 'Result' of the test's record if
        exceptions happened when executing the procedure function.

        This will let signals.TestAbortAll through so abort_all works in all
        procedure functions.

        Args:
            func: The procedure function to be executed.
            tr_record: The TestResultRecord object associated with the test
                       executed.
        """
        try:
            func(tr_record)
        except signals.TestAbortAll:
            raise
        except Exception as e:
            logging.exception('Exception happened when executing %s for %s.',
                              func.__name__, self.current_test_name)
            tr_record.add_error(func.__name__, e)

    def exec_one_test(self, test_name, test_method, args=(), **kwargs):
        """Executes one test and update test results.

        Executes setup_test, the test method, and teardown_test; then creates a
        records.TestResultRecord object with the execution information and adds
        the record to the test class's test results.

        Args:
            test_name: Name of the test.
            test_method: The test method.
            args: A tuple of params.
            kwargs: Extra kwargs.
        """
        is_generate_trigger = False
        tr_record = records.TestResultRecord(test_name, self.TAG)
        tr_record.test_begin()
        logging.info('%s %s', TEST_CASE_TOKEN, test_name)
        try:
            try:
                self._setup_test(test_name)
                if args or kwargs:
                    test_method(*args, **kwargs)
                else:
                    test_method()
            finally:
                try:
                    self._teardown_test(test_name)
                except signals.TestAbortAll:
                    raise
                except Exception as e:
                    logging.exception(e)
                    tr_record.add_error('teardown_test', e)
                    self._exec_procedure_func(self._on_fail, tr_record)
        except (signals.TestFailure, AssertionError) as e:
            logging.exception(e)
            tr_record.test_fail(e)
            self._exec_procedure_func(self._on_fail, tr_record)
        except signals.TestSkip as e:
            # Test skipped.
            tr_record.test_skip(e)
            self._exec_procedure_func(self._on_skip, tr_record)
        except (signals.TestAbortClass, signals.TestAbortAll) as e:
            # Abort signals, pass along.
            tr_record.test_fail(e)
            raise e
        except signals.TestPass as e:
            # Explicit test pass.
            tr_record.test_pass(e)
            self._exec_procedure_func(self._on_pass, tr_record)
        except signals.TestSilent as e:
            # This is a trigger test for generated tests, suppress reporting.
            is_generate_trigger = True
            self.results.requested.remove(test_name)
        except Exception as e:
            logging.exception(e)
            # Exception happened during test.
            tr_record.test_error(e)
            self._exec_procedure_func(self._on_fail, tr_record)
        else:
            tr_record.test_pass()
            self._exec_procedure_func(self._on_pass, tr_record)
        finally:
            if not is_generate_trigger:
                self.results.add_record(tr_record)

    def _assert_function_name_in_stack(self, expected_func_name):
        """Asserts that the current stack contains the given function name."""
        current_frame = inspect.currentframe()
        caller_frames = inspect.getouterframes(current_frame, 2)
        for caller_frame in caller_frames[2:]:
            if caller_frame[3] == expected_func_name:
                return
        raise Error('"%s" cannot be called outside of %s' %
                    (caller_frames[1][3], expected_func_name))

    def generate_tests(self, test_logic, name_func, arg_sets):
        """Generates tests in the test class.

        This function has to be called inside a test class's
        `self.setup_generated_tests` function.

        Generated tests are not written down as methods, but as a list of
        parameter sets. This way we reduce code repetition and improve test
        scalability.

        Args:
            test_logic: function, the common logic shared by all the generated
                        tests.
            name_func: function, generate a test name according to a set of
                       test arguments. This function should take the same
                       arguments as the test logic function. The test name
                       should be shorter than utils.MAX_FILENAME_LEN. Names
                       over the limit will be truncated.
            arg_sets: a list of tuples, each tuple is a set of arguments to be
                      passed to the test logic function and name function.
        """
        self._assert_function_name_in_stack('setup_generated_tests')
        for args in arg_sets:
            test_name = name_func(*args)
            if test_name in self._get_all_test_names():
                raise Error(
                    'Test name "%s" already exists, cannot be duplicated!' %
                    test_name)
            test_func = functools.partial(test_logic, *args)
            self._generated_test_table[test_name] = test_func

    def run_generated_testcases(self,
                                test_func,
                                settings,
                                args=None,
                                kwargs=None,
                                tag='',
                                name_func=None):
        """Runs generated test cases.

        !DEPRECATED! Use self.generate_tests instead.

        Generated test cases are not written down as functions, but as a list
        of parameter sets. This way we reduce code repetition and improve
        test case scalability.

        Args:
            test_func: The common logic shared by all these generated test
                       cases. This function should take at least one argument,
                       which is a parameter set.
            settings: A list of strings representing parameter sets. These are
                      usually json strings that get loaded in the test_func.
            args: Iterable of additional position args to be passed to
                  test_func.
            kwargs: Dict of additional keyword args to be passed to test_func
            tag: Name of this group of generated test cases. Ignored if
                 name_func is provided and operates properly.
            name_func: A function that takes a test setting and generates a
                       proper test name. The test name should be shorter than
                       utils.MAX_FILENAME_LEN. Names over the limit will be
                       truncated.

        Returns:
            A list of settings that did not pass.
        """
        logging.warning(
            '"run_generated_testcases" is deprecated and will be '
            'removed in Mobly 1.5, please use "generate_tests" instead.')
        args = args or ()
        kwargs = kwargs or {}
        failed_settings = []
        for s in settings:
            test_name = '%s %s' % (tag, s)
            if name_func:
                try:
                    test_name = name_func(s, *args, **kwargs)
                except:
                    logging.exception('Failed to get test name from test_func.'
                                      ' Fall back to default %s.', test_name)
            self.results.requested.append(test_name)
            if len(test_name) > utils.MAX_FILENAME_LEN:
                test_name = test_name[:utils.MAX_FILENAME_LEN]
            previous_success_cnt = len(self.results.passed)
            self.exec_one_test(test_name, test_func, (s, ) + args, **kwargs)
            if len(self.results.passed) - previous_success_cnt != 1:
                failed_settings.append(s)
        return failed_settings

    def _safe_exec_func(self, func, *args):
        """Executes a function with exception safeguard.

        This will let signals.TestAbortAll through so abort_all works in all
        procedure functions.

        Args:
            func: Function to be executed.
            args: Arguments to be passed to the function.

        Returns:
            Whatever the function returns.
        """
        try:
            return func(*args)
        except signals.TestAbortAll:
            raise
        except:
            logging.exception('Exception happened when executing %s in %s.',
                              func.__name__, self.TAG)

    def _get_all_test_names(self):
        """Finds all the method names that match the test method naming
        convention in this class.

        Returns:
            A list of strings, each is a test method name.
        """
        test_names = []
        for name, _ in inspect.getmembers(self, inspect.ismethod):
            if name.startswith('test_'):
                test_names.append(name)
        return test_names + list(self._generated_test_table.keys())

    def _get_test_methods(self, test_names):
        """Resolves test method names to bound test methods.

        Args:
            test_names: A list of strings, each string is a test method name.

        Returns:
            A list of tuples of (string, function). String is the test method
            name, function is the actual python method implementing its logic.

        Raises:
            Error is raised if the test name does not follow
            naming convention 'test_*'. This can only be caused by user input
            here.
        """
        test_methods = []
        for test_name in test_names:
            if not test_name.startswith('test_'):
                raise Error('Test method name %s does not follow naming '
                            'convention test_*, abort.' % test_name)
            if hasattr(self, test_name):
                test_method = getattr(self, test_name)
            elif test_name in self._generated_test_table:
                test_method = self._generated_test_table[test_name]
            else:
                raise Error('%s does not have test method %s.' % (self.TAG,
                                                                  test_name))
            test_methods.append((test_name, test_method))
        return test_methods

    def run(self, test_names=None):
        """Runs tests within a test class.

        One of these test method lists will be executed, shown here in priority
        order:
        1. The test_names list, which is passed from cmd line. Invalid names
           are guarded by cmd line arg parsing.
        2. The self.tests list defined in test class. Invalid names are
           ignored.
        3. All function that matches test method naming convention in the test
           class.

        Args:
            test_names: A list of string that are test method names requested in
                cmd line.

        Returns:
            The test results object of this class.
        """
        # Executes pre-setup procedures, like generating test methods.
        try:
            self.setup_generated_tests()
        except Exception as e:
            logging.exception('Pre-setup processes failed for %s.', self.TAG)
            class_record = records.TestResultRecord('setup_generated_tests',
                                                    self.TAG)
            class_record.test_begin()
            class_record.test_fail(e)
            self.results.fail_class(class_record)
            return self.results
        logging.info('==========> %s <==========', self.TAG)
        # Devise the actual test methods to run in the test class.
        if not test_names:
            if self.tests:
                # Specified by run list in class.
                test_names = list(self.tests)
            else:
                # No test method specified by user, execute all in test class.
                test_names = self._get_all_test_names()
        self.results.requested = test_names
        tests = self._get_test_methods(test_names)
        # Setup for the class.
        try:
            self._setup_class()
        except signals.TestAbortClass as e:
            # The test class is intentionally aborted.
            # Skip all tests peacefully.
            e.details = 'Test class aborted due to: %s' % e.details
            for test_name in self._get_all_test_names():
                test_record = records.TestResultRecord(test_name, self.TAG)
                test_record.test_skip(e)
                self.results.add_record(test_record)
            return self.results
        except Exception as e:
            # Setup class failed for unknown reasons.
            # Fail the class and skip all tests.
            logging.exception('Failed to setup %s.', self.TAG)
            class_record = records.TestResultRecord('setup_class', self.TAG)
            class_record.test_begin()
            class_record.test_fail(e)
            self._exec_procedure_func(self._on_fail, class_record)
            self.results.fail_class(class_record)
            for test_name in self._get_all_test_names():
                test_record = records.TestResultRecord(test_name, self.TAG)
                test_record.test_skip(e)
                self.results.add_record(test_record)
            return self.results
        finally:
            self._safe_exec_func(self.teardown_class)
        # Run tests in order.
        try:
            for test_name, test_method in tests:
                self.exec_one_test(test_name, test_method)
            return self.results
        except signals.TestAbortClass as e:
            e.details = 'Test class aborted due to: %s' % e.details
            for test_name in self._get_all_test_names():
                if not self.results.is_test_executed(test_name):
                    test_record = records.TestResultRecord(test_name, self.TAG)
                    test_record.test_skip(e)
                    self.results.add_record(test_record)
            return self.results
        except signals.TestAbortAll as e:
            # Piggy-back test results on this exception object so we don't lose
            # results from this test class.
            setattr(e, 'results', self.results)
            raise e
        finally:
            self._safe_exec_func(self.teardown_class)
            logging.info('Summary for test class %s: %s', self.TAG,
                         self.results.summary_str())

    def clean_up(self):
        """A function that is executed upon completion of all tests selected in
        the test class.

        This function should clean up objects initialized in the constructor by
        user.
        """
