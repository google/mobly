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

import os
import mock
import shutil
import tempfile
import unittest

from mobly.base_instrumentation_test import _InstrumentationBlock
from mobly.base_instrumentation_test import _InstrumentationKnownStatusKeys
from mobly.base_instrumentation_test import _InstrumentationStructurePrefixes
from mobly.base_instrumentation_test import BaseInstrumentationTestClass
from mobly import config_parser
from mobly import signals
from mobly.controllers import android_device
from mobly.controllers.android_device_lib import adb
from tests.lib import mock_instrumentation_test

# A random prefix to test that prefixes are added properly.
MOCK_PREFIX = 'my_prefix'
# A mock name for the instrumentation test subclass.
MOCK_INSTRUMENTATION_TEST_CLASS_NAME = 'MockInstrumentationTest'

MOCK_EMPTY_INSTRUMENTATION_TEST = """\
INSTRUMENTATION_RESULT: stream=

Time: 0.001

OK (0 tests)


INSTRUMENTATION_CODE: -1
"""


class InstrumentationResult:

  def __init__(self):
    self.error = None
    self.completed_and_passed = False
    self.executed = []
    self.skipped = []


class BaseInstrumentationTestTest(unittest.TestCase):

  def setUp(self):
    self.tmp_dir = tempfile.mkdtemp()

  def tearDown(self):
    shutil.rmtree(self.tmp_dir)

  def assert_parse_instrumentation_options(self, user_params,
                                           expected_instrumentation_options):
    mit = mock_instrumentation_test.MockInstrumentationTest(
        self.tmp_dir, user_params)
    instrumentation_options = mit.parse_instrumentation_options(mit.user_params)
    self.assertEqual(instrumentation_options, expected_instrumentation_options)

  def test_parse_instrumentation_options_with_no_user_params(self):
    self.assert_parse_instrumentation_options({}, {})

  def test_parse_instrumentation_options_with_no_instrumentation_params(self):
    self.assert_parse_instrumentation_options(
        {
            'param1': 'val1',
            'param2': 'val2',
        },
        {},
    )

  def test_parse_instrumentation_options_with_only_instrumentation_params(self):
    self.assert_parse_instrumentation_options(
        {
            'instrumentation_option_key1': 'value1',
            'instrumentation_option_key2': 'value2',
        },
        {
            'key1': 'value1',
            'key2': 'value2'
        },
    )

  def test_parse_instrumentation_options_with_mixed_user_params(self):
    self.assert_parse_instrumentation_options(
        {
            'param1': 'val1',
            'param2': 'val2',
            'instrumentation_option_key1': 'value1',
            'instrumentation_option_key2': 'value2',
        },
        {
            'key1': 'value1',
            'key2': 'value2'
        },
    )

  def run_instrumentation_test(self, instrumentation_output, prefix=None):
    mit = mock_instrumentation_test.MockInstrumentationTest(self.tmp_dir)
    result = InstrumentationResult()
    try:
      result.completed_and_passed = mit.run_mock_instrumentation_test(
          instrumentation_output, prefix=prefix)
    except signals.TestError as e:
      result.error = e
    result.executed = mit.results.executed
    result.skipped = mit.results.skipped
    return result

  def assert_equal_test(self, actual_test, expected_test):
    (expected_test_name, expected_signal) = expected_test
    self.assertEqual(actual_test.test_class,
                     MOCK_INSTRUMENTATION_TEST_CLASS_NAME)
    self.assertEqual(actual_test.test_name, expected_test_name)
    self.assertIsInstance(actual_test.termination_signal.exception,
                          expected_signal)

  def assert_run_instrumentation_test(self,
                                      instrumentation_output,
                                      expected_executed=[],
                                      expected_skipped=[],
                                      expected_completed_and_passed=False,
                                      expected_has_error=False,
                                      prefix=None,
                                      expected_executed_times=[]):
    result = self.run_instrumentation_test(bytes(instrumentation_output,
                                                 'utf-8'),
                                           prefix=prefix)
    if expected_has_error:
      self.assertIsInstance(result.error, signals.TestError)
    else:
      self.assertIsNone(result.error)
      self.assertEqual(result.completed_and_passed,
                       expected_completed_and_passed)
    self.assertEqual(len(result.executed), len(expected_executed))
    for actual_test, expected_test in zip(result.executed, expected_executed):
      self.assert_equal_test(actual_test, expected_test)
    self.assertEqual(len(result.skipped), len(expected_skipped))
    for actual_test, expected_test in zip(result.skipped, expected_skipped):
      self.assert_equal_test(actual_test, expected_test)
    if expected_executed_times:
      for actual_test, expected_time in zip(result.executed,
                                            expected_executed_times):
        (expected_begin_time, expected_end_time) = expected_time
        self.assertEqual(actual_test.begin_time, expected_begin_time)
        self.assertEqual(actual_test.end_time, expected_end_time)

  def test_run_instrumentation_test_with_invalid_syntax(self):
    instrumentation_output = """\
usage: am [subcommand] [options]
usage: am start [-D] [-N] [-W] [-P <FILE>] [--start-profiler <FILE>]
         [--sampling INTERVAL] [-R COUNT] [-S]

am start: start an Activity.  Options are:
  -D: enable debugging

am startservice: start a Service.  Options are:
  --user <USER_ID> | current: Specify which user to run as; if not
    specified then run as the current user.

am task lock: bring <TASK_ID> to the front and don't allow other tasks to run.

<INTENT> specifications include these flags and arguments:
  [-a <ACTION>] [-d <DATA_URI>] [-t <MIME_TYPE>]
  [-c <CATEGORY> [-c <CATEGORY>] ...]

Error: Bad component name: /
"""
    self.assert_run_instrumentation_test(instrumentation_output,
                                         expected_has_error=True)

  def test_run_instrumentation_test_with_no_output(self):
    instrumentation_output = """\
"""
    self.assert_run_instrumentation_test(instrumentation_output,
                                         expected_has_error=True)

  def test_run_instrumentation_test_with_missing_test_package(self):
    instrumentation_output = """\
android.util.AndroidException: INSTRUMENTATION_FAILED: com.my.package.test/com.my.package.test.runner.MyRunner
  at com.android.commands.am.Am.runInstrument(Am.java:897)
  at com.android.commands.am.Am.onRun(Am.java:405)
  at com.android.internal.os.BaseCommand.run(BaseCommand.java:51)
  at com.android.commands.am.Am.main(Am.java:124)
  at com.android.internal.os.RuntimeInit.nativeFinishInit(Native Method)
  at com.android.internal.os.RuntimeInit.main(RuntimeInit.java:262)
INSTRUMENTATION_STATUS: id=ActivityManagerService
INSTRUMENTATION_STATUS: Error=Unable to find instrumentation info for: ComponentInfo{com.my.package.test/com.my.package.test.runner.MyRunner}
INSTRUMENTATION_STATUS_CODE: -1"""
    self.assert_run_instrumentation_test(instrumentation_output,
                                         expected_has_error=True)

  def test_run_instrumentation_test_with_missing_runner(self):
    instrumentation_output = """\
android.util.AndroidException: INSTRUMENTATION_FAILED: com.my.package.test/com.my.package.test.runner
INSTRUMENTATION_STATUS: id=ActivityManagerService
INSTRUMENTATION_STATUS: Error=Unable to find instrumentation info for: ComponentInfo{com.my.package.test/com.my.package.test.runner}
INSTRUMENTATION_STATUS_CODE: -1
  at com.android.commands.am.Am.runInstrument(Am.java:897)
  at com.android.commands.am.Am.onRun(Am.java:405)
  at com.android.internal.os.BaseCommand.run(BaseCommand.java:51)
  at com.android.commands.am.Am.main(Am.java:124)
  at com.android.internal.os.RuntimeInit.nativeFinishInit(Native Method)
  at com.android.internal.os.RuntimeInit.main(RuntimeInit.java:262)"""
    self.assert_run_instrumentation_test(instrumentation_output,
                                         expected_has_error=True)

  def test_run_instrumentation_test_with_no_tests(self):
    instrumentation_output = MOCK_EMPTY_INSTRUMENTATION_TEST
    self.assert_run_instrumentation_test(instrumentation_output,
                                         expected_completed_and_passed=True)

  @mock.patch('logging.info')
  def test_run_instrumentation_test_logs_correctly(self, mock_info_logger):
    instrumentation_output = MOCK_EMPTY_INSTRUMENTATION_TEST
    self.assert_run_instrumentation_test(instrumentation_output,
                                         expected_completed_and_passed=True)
    for mock_call in mock_info_logger.mock_calls:
      logged_format = mock_call[1][0]
      self.assertIsInstance(logged_format, str)

  @mock.patch('mobly.utils.get_current_epoch_time')
  def test_run_instrumentation_test_with_passing_test(self, mock_get_time):
    instrumentation_output = """\
INSTRUMENTATION_STATUS: numtests=1
INSTRUMENTATION_STATUS: stream=
com.my.package.test.BasicTest:
INSTRUMENTATION_STATUS: id=AndroidJUnitRunner
INSTRUMENTATION_STATUS: test=basicTest
INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest
INSTRUMENTATION_STATUS: current=1
INSTRUMENTATION_STATUS_CODE: 1
INSTRUMENTATION_STATUS: numtests=1
INSTRUMENTATION_STATUS: stream=.
INSTRUMENTATION_STATUS: id=AndroidJUnitRunner
INSTRUMENTATION_STATUS: test=basicTest
INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest
INSTRUMENTATION_STATUS: current=1
INSTRUMENTATION_STATUS_CODE: 0
INSTRUMENTATION_RESULT: stream=

Time: 0.214

OK (1 test)


INSTRUMENTATION_CODE: -1
"""
    expected_executed = [
        ('com.my.package.test.BasicTest#basicTest', signals.TestPass),
    ]
    mock_get_time.side_effect = [13, 51]
    self.assert_run_instrumentation_test(instrumentation_output,
                                         expected_executed=expected_executed,
                                         expected_completed_and_passed=True,
                                         expected_executed_times=[(13, 51)])

  def test_run_instrumentation_test_with_random_whitespace(self):
    instrumentation_output = """\

INSTRUMENTATION_STATUS: numtests=1

INSTRUMENTATION_STATUS: stream=

com.my.package.test.BasicTest:

INSTRUMENTATION_STATUS: id=AndroidJUnitRunner

INSTRUMENTATION_STATUS: test=basicTest

INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest

INSTRUMENTATION_STATUS: current=1

INSTRUMENTATION_STATUS_CODE: 1

INSTRUMENTATION_STATUS: numtests=1

INSTRUMENTATION_STATUS: stream=.

INSTRUMENTATION_STATUS: id=AndroidJUnitRunner

INSTRUMENTATION_STATUS: test=basicTest

INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest

INSTRUMENTATION_STATUS: current=1

INSTRUMENTATION_STATUS_CODE: 0

INSTRUMENTATION_RESULT: stream=


Time: 0.214


OK (1 test)




INSTRUMENTATION_CODE: -1

"""
    expected_executed = [
        ('com.my.package.test.BasicTest#basicTest', signals.TestPass),
    ]
    self.assert_run_instrumentation_test(instrumentation_output,
                                         expected_executed=expected_executed,
                                         expected_completed_and_passed=True)

  def test_run_instrumentation_test_with_prefix_test(self):
    instrumentation_output = """\
INSTRUMENTATION_STATUS: numtests=1
INSTRUMENTATION_STATUS: stream=
com.my.package.test.BasicTest:
INSTRUMENTATION_STATUS: id=AndroidJUnitRunner
INSTRUMENTATION_STATUS: test=basicTest
INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest
INSTRUMENTATION_STATUS: current=1
INSTRUMENTATION_STATUS_CODE: 1
INSTRUMENTATION_STATUS: numtests=1
INSTRUMENTATION_STATUS: stream=.
INSTRUMENTATION_STATUS: id=AndroidJUnitRunner
INSTRUMENTATION_STATUS: test=basicTest
INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest
INSTRUMENTATION_STATUS: current=1
INSTRUMENTATION_STATUS_CODE: 0
INSTRUMENTATION_RESULT: stream=

Time: 0.214

OK (1 test)


INSTRUMENTATION_CODE: -1
"""
    expected_executed = [
        ('%s.com.my.package.test.BasicTest#basicTest' % MOCK_PREFIX,
         signals.TestPass),
    ]
    self.assert_run_instrumentation_test(instrumentation_output,
                                         expected_executed=expected_executed,
                                         expected_completed_and_passed=True,
                                         prefix=MOCK_PREFIX)

  def test_run_instrumentation_test_with_failing_test(self):
    instrumentation_output = """\
INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest
INSTRUMENTATION_STATUS: current=1
INSTRUMENTATION_STATUS: id=AndroidJUnitRunner
INSTRUMENTATION_STATUS: numtests=1
INSTRUMENTATION_STATUS: stream=
com.my.package.test.BasicTest:
INSTRUMENTATION_STATUS: test=failingTest
INSTRUMENTATION_STATUS_CODE: 1
INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest
INSTRUMENTATION_STATUS: current=1
INSTRUMENTATION_STATUS: id=AndroidJUnitRunner
INSTRUMENTATION_STATUS: numtests=1
INSTRUMENTATION_STATUS: stack=java.lang.UnsupportedOperationException: dummy failing test
  at com.my.package.test.BasicTest.failingTest(BasicTest.java:38)
  at java.lang.reflect.Method.invoke(Native Method)
  at org.junit.runners.model.FrameworkMethod$1.runReflectiveCall(FrameworkMethod.java:57)
  at org.junit.internal.runners.model.ReflectiveCallable.run(ReflectiveCallable.java:12)
  at org.junit.runners.model.FrameworkMethod.invokeExplosively(FrameworkMethod.java:59)
  at org.junit.internal.runners.statements.InvokeMethod.evaluate(InvokeMethod.java:17)
  at androidx.test.internal.runner.junit4.statement.RunBefores.evaluate(RunBefores.java:80)
  at androidx.test.internal.runner.junit4.statement.RunAfters.evaluate(RunAfters.java:61)
  at androidx.test.rule.ActivityTestRule$ActivityStatement.evaluate(ActivityTestRule.java:433)
  at com.my.package.test.BaseTest$3.evaluate(BaseTest.java:96)
  at com.my.package.test.BaseTest$4.evaluate(BaseTest.java:109)
  at com.my.package.test.BaseTest$2.evaluate(BaseTest.java:77)
  at org.junit.rules.TestWatcher$1.evaluate(TestWatcher.java:55)
  at org.junit.rules.TestWatcher$1.evaluate(TestWatcher.java:55)
  at org.junit.rules.RunRules.evaluate(RunRules.java:20)
  at org.junit.runners.BlockJUnit4ClassRunner$1.evaluate(BlockJUnit4ClassRunner.java:81)
  at org.junit.runners.ParentRunner.runLeaf(ParentRunner.java:327)
  at org.junit.runners.BlockJUnit4ClassRunner.runChild(BlockJUnit4ClassRunner.java:84)
  at org.junit.runners.BlockJUnit4ClassRunner.runChild(BlockJUnit4ClassRunner.java:57)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at androidx.test.runner.AndroidJUnit4.run(AndroidJUnit4.java:99)
  at org.junit.runners.Suite.runChild(Suite.java:128)
  at org.junit.runners.Suite.runChild(Suite.java:27)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at org.junit.runners.Suite.runChild(Suite.java:128)
  at org.junit.runners.Suite.runChild(Suite.java:27)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at org.junit.runner.JUnitCore.run(JUnitCore.java:137)
  at org.junit.runner.JUnitCore.run(JUnitCore.java:115)
  at androidx.test.internal.runner.TestExecutor.execute(TestExecutor.java:56)
  at com.my.package.test.BaseRunner.runTests(BaseRunner.java:344)
  at com.my.package.test.BaseRunner.onStart(BaseRunner.java:330)
  at com.my.package.test.runner.MyRunner.onStart(MyRunner.java:253)
  at android.app.Instrumentation$InstrumentationThread.run(Instrumentation.java:2074)

INSTRUMENTATION_STATUS: stream=
Error in failingTest(com.my.package.test.BasicTest):
java.lang.UnsupportedOperationException: dummy failing test
  at com.my.package.test.BasicTest.failingTest(BasicTest.java:38)
  at java.lang.reflect.Method.invoke(Native Method)
  at org.junit.runners.model.FrameworkMethod$1.runReflectiveCall(FrameworkMethod.java:57)
  at org.junit.internal.runners.model.ReflectiveCallable.run(ReflectiveCallable.java:12)
  at org.junit.runners.model.FrameworkMethod.invokeExplosively(FrameworkMethod.java:59)
  at org.junit.internal.runners.statements.InvokeMethod.evaluate(InvokeMethod.java:17)
  at androidx.test.internal.runner.junit4.statement.RunBefores.evaluate(RunBefores.java:80)
  at androidx.test.internal.runner.junit4.statement.RunAfters.evaluate(RunAfters.java:61)
  at androidx.test.rule.ActivityTestRule$ActivityStatement.evaluate(ActivityTestRule.java:433)
  at com.my.package.test.BaseTest$3.evaluate(BaseTest.java:96)
  at com.my.package.test.BaseTest$4.evaluate(BaseTest.java:109)
  at com.my.package.test.BaseTest$2.evaluate(BaseTest.java:77)
  at org.junit.rules.TestWatcher$1.evaluate(TestWatcher.java:55)
  at org.junit.rules.TestWatcher$1.evaluate(TestWatcher.java:55)
  at org.junit.rules.RunRules.evaluate(RunRules.java:20)
  at org.junit.runners.BlockJUnit4ClassRunner$1.evaluate(BlockJUnit4ClassRunner.java:81)
  at org.junit.runners.ParentRunner.runLeaf(ParentRunner.java:327)
  at org.junit.runners.BlockJUnit4ClassRunner.runChild(BlockJUnit4ClassRunner.java:84)
  at org.junit.runners.BlockJUnit4ClassRunner.runChild(BlockJUnit4ClassRunner.java:57)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at androidx.test.runner.AndroidJUnit4.run(AndroidJUnit4.java:99)
  at org.junit.runners.Suite.runChild(Suite.java:128)
  at org.junit.runners.Suite.runChild(Suite.java:27)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at org.junit.runners.Suite.runChild(Suite.java:128)
  at org.junit.runners.Suite.runChild(Suite.java:27)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at org.junit.runner.JUnitCore.run(JUnitCore.java:137)
  at org.junit.runner.JUnitCore.run(JUnitCore.java:115)
  at androidx.test.internal.runner.TestExecutor.execute(TestExecutor.java:56)
  at com.my.package.test.BaseRunner.runTests(BaseRunner.java:344)
  at com.my.package.test.BaseRunner.onStart(BaseRunner.java:330)
  at com.my.package.test.runner.MyRunner.onStart(MyRunner.java:253)
  at android.app.Instrumentation$InstrumentationThread.run(Instrumentation.java:2074)

INSTRUMENTATION_STATUS: test=failingTest
INSTRUMENTATION_STATUS_CODE: -2
INSTRUMENTATION_RESULT: stream=

Time: 1.92
There was 1 failure:
1) failingTest(com.my.package.test.BasicTest)
java.lang.UnsupportedOperationException: dummy failing test
  at com.my.package.test.BasicTest.failingTest(BasicTest.java:38)
  at java.lang.reflect.Method.invoke(Native Method)
  at org.junit.runners.model.FrameworkMethod$1.runReflectiveCall(FrameworkMethod.java:57)
  at org.junit.internal.runners.model.ReflectiveCallable.run(ReflectiveCallable.java:12)
  at org.junit.runners.model.FrameworkMethod.invokeExplosively(FrameworkMethod.java:59)
  at org.junit.internal.runners.statements.InvokeMethod.evaluate(InvokeMethod.java:17)
  at androidx.test.internal.runner.junit4.statement.RunBefores.evaluate(RunBefores.java:80)
  at androidx.test.internal.runner.junit4.statement.RunAfters.evaluate(RunAfters.java:61)
  at androidx.test.rule.ActivityTestRule$ActivityStatement.evaluate(ActivityTestRule.java:433)
  at com.my.package.test.BaseTest$3.evaluate(BaseTest.java:96)
  at com.my.package.test.BaseTest$4.evaluate(BaseTest.java:109)
  at com.my.package.test.BaseTest$2.evaluate(BaseTest.java:77)
  at org.junit.rules.TestWatcher$1.evaluate(TestWatcher.java:55)
  at org.junit.rules.TestWatcher$1.evaluate(TestWatcher.java:55)
  at org.junit.rules.RunRules.evaluate(RunRules.java:20)
  at org.junit.runners.BlockJUnit4ClassRunner$1.evaluate(BlockJUnit4ClassRunner.java:81)
  at org.junit.runners.ParentRunner.runLeaf(ParentRunner.java:327)
  at org.junit.runners.BlockJUnit4ClassRunner.runChild(BlockJUnit4ClassRunner.java:84)
  at org.junit.runners.BlockJUnit4ClassRunner.runChild(BlockJUnit4ClassRunner.java:57)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at androidx.test.runner.AndroidJUnit4.run(AndroidJUnit4.java:99)
  at org.junit.runners.Suite.runChild(Suite.java:128)
  at org.junit.runners.Suite.runChild(Suite.java:27)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at org.junit.runners.Suite.runChild(Suite.java:128)
  at org.junit.runners.Suite.runChild(Suite.java:27)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at org.junit.runner.JUnitCore.run(JUnitCore.java:137)
  at org.junit.runner.JUnitCore.run(JUnitCore.java:115)
  at androidx.test.internal.runner.TestExecutor.execute(TestExecutor.java:56)
  at com.my.package.test.BaseRunner.runTests(BaseRunner.java:344)
  at com.my.package.test.BaseRunner.onStart(BaseRunner.java:330)
  at com.my.package.test.runner.MyRunner.onStart(MyRunner.java:253)
  at android.app.Instrumentation$InstrumentationThread.run(Instrumentation.java:2074)

FAILURES!!!
Tests run: 1,  Failures: 1


INSTRUMENTATION_CODE: -1"""
    expected_executed = [
        ('com.my.package.test.BasicTest#failingTest', signals.TestFailure),
    ]
    self.assert_run_instrumentation_test(instrumentation_output,
                                         expected_executed=expected_executed)

  def test_run_instrumentation_test_with_assumption_failure_test(self):
    instrumentation_output = """\
INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest
INSTRUMENTATION_STATUS: current=1
INSTRUMENTATION_STATUS: id=AndroidJUnitRunner
INSTRUMENTATION_STATUS: numtests=1
INSTRUMENTATION_STATUS: stream=
com.my.package.test.BasicTest:
INSTRUMENTATION_STATUS: test=assumptionFailureTest
INSTRUMENTATION_STATUS_CODE: 1
INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest
INSTRUMENTATION_STATUS: current=1
INSTRUMENTATION_STATUS: id=AndroidJUnitRunner
INSTRUMENTATION_STATUS: numtests=1
INSTRUMENTATION_STATUS: stack=org.junit.AssumptionViolatedException: Assumption failure reason
  at org.junit.Assume.assumeTrue(Assume.java:59)
  at org.junit.Assume.assumeFalse(Assume.java:66)
  at com.my.package.test.BasicTest.assumptionFailureTest(BasicTest.java:63)
  at java.lang.reflect.Method.invoke(Native Method)
  at org.junit.runners.model.FrameworkMethod$1.runReflectiveCall(FrameworkMethod.java:57)
  at org.junit.internal.runners.model.ReflectiveCallable.run(ReflectiveCallable.java:12)
  at org.junit.runners.model.FrameworkMethod.invokeExplosively(FrameworkMethod.java:59)
  at org.junit.internal.runners.statements.InvokeMethod.evaluate(InvokeMethod.java:17)
  at androidx.test.internal.runner.junit4.statement.RunBefores.evaluate(RunBefores.java:80)
  at androidx.test.internal.runner.junit4.statement.RunAfters.evaluate(RunAfters.java:61)
  at androidx.test.rule.ActivityTestRule$ActivityStatement.evaluate(ActivityTestRule.java:433)
  at com.my.package.test.MyBaseTest$3.evaluate(MyBaseTest.java:96)
  at com.my.package.test.MyBaseTest$4.evaluate(MyBaseTest.java:109)
  at com.my.package.test.MyBaseTest$2.evaluate(MyBaseTest.java:77)
  at org.junit.rules.TestWatcher$1.evaluate(TestWatcher.java:55)
  at org.junit.rules.TestWatcher$1.evaluate(TestWatcher.java:55)
  at org.junit.rules.RunRules.evaluate(RunRules.java:20)
  at org.junit.runners.BlockJUnit4ClassRunner$1.evaluate(BlockJUnit4ClassRunner.java:81)
  at org.junit.runners.ParentRunner.runLeaf(ParentRunner.java:327)
  at org.junit.runners.BlockJUnit4ClassRunner.runChild(BlockJUnit4ClassRunner.java:84)
  at org.junit.runners.BlockJUnit4ClassRunner.runChild(BlockJUnit4ClassRunner.java:57)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at androidx.test.runner.AndroidJUnit4.run(AndroidJUnit4.java:99)
  at org.junit.runners.Suite.runChild(Suite.java:128)
  at org.junit.runners.Suite.runChild(Suite.java:27)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at org.junit.runners.Suite.runChild(Suite.java:128)
  at org.junit.runners.Suite.runChild(Suite.java:27)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at org.junit.runner.JUnitCore.run(JUnitCore.java:137)
  at org.junit.runner.JUnitCore.run(JUnitCore.java:115)
  at androidx.test.internal.runner.TestExecutor.execute(TestExecutor.java:56)
  at com.my.package.test.runner.BaseRunner.runTests(BaseRunner.java:344)
  at com.my.package.test.runner.BaseRunner.onStart(BaseRunner.java:330)
  at com.my.package.test.runner.BaseRunner.onStart(BaseRunner.java:253)
  at android.app.Instrumentation$InstrumentationThread.run(Instrumentation.java:2074)

INSTRUMENTATION_STATUS: stream=
com.my.package.test.BasicTest:
INSTRUMENTATION_STATUS: test=assumptionFailureTest
INSTRUMENTATION_STATUS_CODE: -4
INSTRUMENTATION_RESULT: stream=

Time: 3.139

OK (1 test)


INSTRUMENTATION_CODE: -1"""
    expected_skipped = [
        ('com.my.package.test.BasicTest#assumptionFailureTest',
         signals.TestSkip),
    ]
    self.assert_run_instrumentation_test(instrumentation_output,
                                         expected_skipped=expected_skipped,
                                         expected_completed_and_passed=True)

  def test_run_instrumentation_test_with_ignored_test(self):
    instrumentation_output = """\
INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest
INSTRUMENTATION_STATUS: current=1
INSTRUMENTATION_STATUS: id=AndroidJUnitRunner
INSTRUMENTATION_STATUS: numtests=1
INSTRUMENTATION_STATUS: stream=
com.my.package.test.BasicTest:
INSTRUMENTATION_STATUS: test=ignoredTest
INSTRUMENTATION_STATUS_CODE: 1
INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest
INSTRUMENTATION_STATUS: current=1
INSTRUMENTATION_STATUS: id=AndroidJUnitRunner
INSTRUMENTATION_STATUS: numtests=1
INSTRUMENTATION_STATUS: stream=
com.my.package.test.BasicTest:
INSTRUMENTATION_STATUS: test=ignoredTest
INSTRUMENTATION_STATUS_CODE: -3
INSTRUMENTATION_RESULT: stream=

Time: 0.007

OK (0 tests)


INSTRUMENTATION_CODE: -1"""
    expected_skipped = [
        ('com.my.package.test.BasicTest#ignoredTest', signals.TestSkip),
    ]
    self.assert_run_instrumentation_test(instrumentation_output,
                                         expected_skipped=expected_skipped,
                                         expected_completed_and_passed=True)

  @mock.patch('mobly.utils.get_current_epoch_time')
  def test_run_instrumentation_test_with_crashed_test(self, mock_get_time):
    instrumentation_output = """\
INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest
INSTRUMENTATION_STATUS: current=1
INSTRUMENTATION_STATUS: id=AndroidJUnitRunner
INSTRUMENTATION_STATUS: numtests=1
INSTRUMENTATION_STATUS: stream=
com.my.package.test.BasicTest:
INSTRUMENTATION_STATUS: test=crashTest
INSTRUMENTATION_STATUS_CODE: 1
INSTRUMENTATION_RESULT: shortMsg=Process crashed.
INSTRUMENTATION_CODE: 0"""
    expected_executed = [
        ('com.my.package.test.BasicTest#crashTest', signals.TestError),
    ]
    mock_get_time.side_effect = [67, 942]
    self.assert_run_instrumentation_test(instrumentation_output,
                                         expected_executed=expected_executed,
                                         expected_has_error=True,
                                         expected_executed_times=[(67, 942)])

  @mock.patch('mobly.utils.get_current_epoch_time')
  def test_run_instrumentation_test_with_crashing_test(self, mock_get_time):
    instrumentation_output = """\
INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest
INSTRUMENTATION_STATUS: current=1
INSTRUMENTATION_STATUS: id=AndroidJUnitRunner
INSTRUMENTATION_STATUS: numtests=2
INSTRUMENTATION_STATUS: stream=
com.my.package.test.BasicTest:
INSTRUMENTATION_STATUS: test=crashAndRecover1Test
INSTRUMENTATION_STATUS_CODE: 1
INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest
INSTRUMENTATION_STATUS: current=2
INSTRUMENTATION_STATUS: id=AndroidJUnitRunner
INSTRUMENTATION_STATUS: numtests=2
INSTRUMENTATION_STATUS: stream=
com.my.package.test.BasicTest:
INSTRUMENTATION_STATUS: test=crashAndRecover2Test
INSTRUMENTATION_STATUS_CODE: 1
INSTRUMENTATION_RESULT: stream=

Time: 6.342

OK (2 tests)


INSTRUMENTATION_CODE: -1"""
    expected_executed = [
        ('com.my.package.test.BasicTest#crashAndRecover1Test',
         signals.TestError),
        ('com.my.package.test.BasicTest#crashAndRecover2Test',
         signals.TestError),
    ]
    mock_get_time.side_effect = [16, 412, 4143, 6547]
    # TODO(winterfrosts): Fix this issue with overlapping timing
    self.assert_run_instrumentation_test(instrumentation_output,
                                         expected_executed=expected_executed,
                                         expected_completed_and_passed=True,
                                         expected_executed_times=[(16, 4143),
                                                                  (412, 6547)])

  def test_run_instrumentation_test_with_runner_setup_crash(self):
    instrumentation_output = """\
INSTRUMENTATION_RESULT: shortMsg=Process crashed.
INSTRUMENTATION_CODE: 0"""
    self.assert_run_instrumentation_test(instrumentation_output,
                                         expected_has_error=True)

  def test_run_instrumentation_test_with_runner_teardown_crash(self):
    instrumentation_output = """\
INSTRUMENTATION_STATUS: numtests=1
INSTRUMENTATION_STATUS: stream=
com.my.package.test.BasicTest:
INSTRUMENTATION_STATUS: id=AndroidJUnitRunner
INSTRUMENTATION_STATUS: test=basicTest
INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest
INSTRUMENTATION_STATUS: current=1
INSTRUMENTATION_STATUS_CODE: 1
INSTRUMENTATION_STATUS: numtests=1
INSTRUMENTATION_STATUS: stream=.
INSTRUMENTATION_STATUS: id=AndroidJUnitRunner
INSTRUMENTATION_STATUS: test=basicTest
INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest
INSTRUMENTATION_STATUS: current=1
INSTRUMENTATION_STATUS_CODE: 0
INSTRUMENTATION_RESULT: shortMsg=Process crashed.
INSTRUMENTATION_CODE: 0
"""
    expected_executed = [
        ('com.my.package.test.BasicTest#basicTest', signals.TestPass),
    ]
    self.assert_run_instrumentation_test(instrumentation_output,
                                         expected_executed=expected_executed,
                                         expected_has_error=True)

  @mock.patch('mobly.utils.get_current_epoch_time')
  def test_run_instrumentation_test_with_multiple_tests(self, mock_get_time):
    instrumentation_output = """\
INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest
INSTRUMENTATION_STATUS: current=1
INSTRUMENTATION_STATUS: id=AndroidJUnitRunner
INSTRUMENTATION_STATUS: numtests=4
INSTRUMENTATION_STATUS: stream=
com.my.package.test.BasicTest:
INSTRUMENTATION_STATUS: test=failingTest
INSTRUMENTATION_STATUS_CODE: 1
INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest
INSTRUMENTATION_STATUS: current=1
INSTRUMENTATION_STATUS: id=AndroidJUnitRunner
INSTRUMENTATION_STATUS: numtests=4
INSTRUMENTATION_STATUS: stack=java.lang.UnsupportedOperationException: dummy failing test
  at com.my.package.test.BasicTest.failingTest(BasicTest.java:40)
  at java.lang.reflect.Method.invoke(Native Method)
  at org.junit.runners.model.FrameworkMethod$1.runReflectiveCall(FrameworkMethod.java:57)
  at org.junit.internal.runners.model.ReflectiveCallable.run(ReflectiveCallable.java:12)
  at org.junit.runners.model.FrameworkMethod.invokeExplosively(FrameworkMethod.java:59)
  at org.junit.internal.runners.statements.InvokeMethod.evaluate(InvokeMethod.java:17)
  at androidx.test.internal.runner.junit4.statement.RunBefores.evaluate(RunBefores.java:80)
  at androidx.test.internal.runner.junit4.statement.RunAfters.evaluate(RunAfters.java:61)
  at androidx.test.rule.ActivityTestRule$ActivityStatement.evaluate(ActivityTestRule.java:433)
  at com.my.package.test.BaseTest$3.evaluate(BaseTest.java:96)
  at com.my.package.test.BaseTest$4.evaluate(BaseTest.java:109)
  at com.my.package.test.BaseTest$2.evaluate(BaseTest.java:77)
  at org.junit.rules.TestWatcher$1.evaluate(TestWatcher.java:55)
  at org.junit.rules.TestWatcher$1.evaluate(TestWatcher.java:55)
  at org.junit.rules.RunRules.evaluate(RunRules.java:20)
  at org.junit.runners.BlockJUnit4ClassRunner$1.evaluate(BlockJUnit4ClassRunner.java:81)
  at org.junit.runners.ParentRunner.runLeaf(ParentRunner.java:327)
  at org.junit.runners.BlockJUnit4ClassRunner.runChild(BlockJUnit4ClassRunner.java:84)
  at org.junit.runners.BlockJUnit4ClassRunner.runChild(BlockJUnit4ClassRunner.java:57)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at androidx.test.runner.AndroidJUnit4.run(AndroidJUnit4.java:99)
  at org.junit.runners.Suite.runChild(Suite.java:128)
  at org.junit.runners.Suite.runChild(Suite.java:27)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at org.junit.runners.Suite.runChild(Suite.java:128)
  at org.junit.runners.Suite.runChild(Suite.java:27)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at org.junit.runner.JUnitCore.run(JUnitCore.java:137)
  at org.junit.runner.JUnitCore.run(JUnitCore.java:115)
  at androidx.test.internal.runner.TestExecutor.execute(TestExecutor.java:56)
  at com.my.package.test.BaseRunner.runTests(BaseRunner.java:344)
  at com.my.package.test.BaseRunner.onStart(BaseRunner.java:330)
  at com.my.package.test.runner.MyRunner.onStart(MyRunner.java:253)
  at android.app.Instrumentation$InstrumentationThread.run(Instrumentation.java:2074)

INSTRUMENTATION_STATUS: stream=
Error in failingTest(com.my.package.test.BasicTest):
java.lang.UnsupportedOperationException: dummy failing test
  at com.my.package.test.BasicTest.failingTest(BasicTest.java:40)
  at java.lang.reflect.Method.invoke(Native Method)
  at org.junit.runners.model.FrameworkMethod$1.runReflectiveCall(FrameworkMethod.java:57)
  at org.junit.internal.runners.model.ReflectiveCallable.run(ReflectiveCallable.java:12)
  at org.junit.runners.model.FrameworkMethod.invokeExplosively(FrameworkMethod.java:59)
  at org.junit.internal.runners.statements.InvokeMethod.evaluate(InvokeMethod.java:17)
  at androidx.test.internal.runner.junit4.statement.RunBefores.evaluate(RunBefores.java:80)
  at androidx.test.internal.runner.junit4.statement.RunAfters.evaluate(RunAfters.java:61)
  at androidx.test.rule.ActivityTestRule$ActivityStatement.evaluate(ActivityTestRule.java:433)
  at com.my.package.test.BaseTest$3.evaluate(BaseTest.java:96)
  at com.my.package.test.BaseTest$4.evaluate(BaseTest.java:109)
  at com.my.package.test.BaseTest$2.evaluate(BaseTest.java:77)
  at org.junit.rules.TestWatcher$1.evaluate(TestWatcher.java:55)
  at org.junit.rules.TestWatcher$1.evaluate(TestWatcher.java:55)
  at org.junit.rules.RunRules.evaluate(RunRules.java:20)
  at org.junit.runners.BlockJUnit4ClassRunner$1.evaluate(BlockJUnit4ClassRunner.java:81)
  at org.junit.runners.ParentRunner.runLeaf(ParentRunner.java:327)
  at org.junit.runners.BlockJUnit4ClassRunner.runChild(BlockJUnit4ClassRunner.java:84)
  at org.junit.runners.BlockJUnit4ClassRunner.runChild(BlockJUnit4ClassRunner.java:57)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at androidx.test.runner.AndroidJUnit4.run(AndroidJUnit4.java:99)
  at org.junit.runners.Suite.runChild(Suite.java:128)
  at org.junit.runners.Suite.runChild(Suite.java:27)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at org.junit.runners.Suite.runChild(Suite.java:128)
  at org.junit.runners.Suite.runChild(Suite.java:27)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at org.junit.runner.JUnitCore.run(JUnitCore.java:137)
  at org.junit.runner.JUnitCore.run(JUnitCore.java:115)
  at androidx.test.internal.runner.TestExecutor.execute(TestExecutor.java:56)
  at com.my.package.test.BaseRunner.runTests(BaseRunner.java:344)
  at com.my.package.test.BaseRunner.onStart(BaseRunner.java:330)
  at com.my.package.test.runner.MyRunner.onStart(MyRunner.java:253)
  at android.app.Instrumentation$InstrumentationThread.run(Instrumentation.java:2074)

INSTRUMENTATION_STATUS: test=failingTest
INSTRUMENTATION_STATUS_CODE: -2
INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest
INSTRUMENTATION_STATUS: current=2
INSTRUMENTATION_STATUS: id=AndroidJUnitRunner
INSTRUMENTATION_STATUS: numtests=4
INSTRUMENTATION_STATUS: stream=
INSTRUMENTATION_STATUS: test=assumptionFailureTest
INSTRUMENTATION_STATUS_CODE: 1
INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest
INSTRUMENTATION_STATUS: current=2
INSTRUMENTATION_STATUS: id=AndroidJUnitRunner
INSTRUMENTATION_STATUS: numtests=4
INSTRUMENTATION_STATUS: stack=org.junit.AssumptionViolatedException: Assumption failure reason
  at org.junit.Assume.assumeTrue(Assume.java:59)
  at com.my.package.test.BasicTest.assumptionFailureTest(BasicTest.java:61)
  at java.lang.reflect.Method.invoke(Native Method)
  at org.junit.runners.model.FrameworkMethod$1.runReflectiveCall(FrameworkMethod.java:57)
  at org.junit.internal.runners.model.ReflectiveCallable.run(ReflectiveCallable.java:12)
  at org.junit.runners.model.FrameworkMethod.invokeExplosively(FrameworkMethod.java:59)
  at org.junit.internal.runners.statements.InvokeMethod.evaluate(InvokeMethod.java:17)
  at androidx.test.internal.runner.junit4.statement.RunBefores.evaluate(RunBefores.java:80)
  at androidx.test.internal.runner.junit4.statement.RunAfters.evaluate(RunAfters.java:61)
  at androidx.test.rule.ActivityTestRule$ActivityStatement.evaluate(ActivityTestRule.java:433)
  at com.my.package.test.BaseTest$3.evaluate(BaseTest.java:96)
  at com.my.package.test.BaseTest$4.evaluate(BaseTest.java:109)
  at com.my.package.test.BaseTest$2.evaluate(BaseTest.java:77)
  at org.junit.rules.TestWatcher$1.evaluate(TestWatcher.java:55)
  at org.junit.rules.TestWatcher$1.evaluate(TestWatcher.java:55)
  at org.junit.rules.RunRules.evaluate(RunRules.java:20)
  at org.junit.runners.BlockJUnit4ClassRunner$1.evaluate(BlockJUnit4ClassRunner.java:81)
  at org.junit.runners.ParentRunner.runLeaf(ParentRunner.java:327)
  at org.junit.runners.BlockJUnit4ClassRunner.runChild(BlockJUnit4ClassRunner.java:84)
  at org.junit.runners.BlockJUnit4ClassRunner.runChild(BlockJUnit4ClassRunner.java:57)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at androidx.test.runner.AndroidJUnit4.run(AndroidJUnit4.java:99)
  at org.junit.runners.Suite.runChild(Suite.java:128)
  at org.junit.runners.Suite.runChild(Suite.java:27)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at org.junit.runners.Suite.runChild(Suite.java:128)
  at org.junit.runners.Suite.runChild(Suite.java:27)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at org.junit.runner.JUnitCore.run(JUnitCore.java:137)
  at org.junit.runner.JUnitCore.run(JUnitCore.java:115)
  at androidx.test.internal.runner.TestExecutor.execute(TestExecutor.java:56)
  at com.my.package.test.BaseRunner.runTests(BaseRunner.java:344)
  at com.my.package.test.BaseRunner.onStart(BaseRunner.java:330)
  at com.my.package.test.runner.MyRunner.onStart(MyRunner.java:253)
  at android.app.Instrumentation$InstrumentationThread.run(Instrumentation.java:2074)

INSTRUMENTATION_STATUS: stream=
INSTRUMENTATION_STATUS: test=assumptionFailureTest
INSTRUMENTATION_STATUS_CODE: -4
INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest
INSTRUMENTATION_STATUS: current=3
INSTRUMENTATION_STATUS: id=AndroidJUnitRunner
INSTRUMENTATION_STATUS: numtests=4
INSTRUMENTATION_STATUS: stream=
INSTRUMENTATION_STATUS: test=ignoredTest
INSTRUMENTATION_STATUS_CODE: 1
INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest
INSTRUMENTATION_STATUS: current=3
INSTRUMENTATION_STATUS: id=AndroidJUnitRunner
INSTRUMENTATION_STATUS: numtests=4
INSTRUMENTATION_STATUS: stream=
INSTRUMENTATION_STATUS: test=ignoredTest
INSTRUMENTATION_STATUS_CODE: -3
INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest
INSTRUMENTATION_STATUS: current=4
INSTRUMENTATION_STATUS: id=AndroidJUnitRunner
INSTRUMENTATION_STATUS: numtests=4
INSTRUMENTATION_STATUS: stream=
INSTRUMENTATION_STATUS: test=passingTest
INSTRUMENTATION_STATUS_CODE: 1
INSTRUMENTATION_STATUS: class=com.my.package.test.BasicTest
INSTRUMENTATION_STATUS: current=4
INSTRUMENTATION_STATUS: id=AndroidJUnitRunner
INSTRUMENTATION_STATUS: numtests=4
INSTRUMENTATION_STATUS: stream=.
INSTRUMENTATION_STATUS: test=passingTest
INSTRUMENTATION_STATUS_CODE: 0
INSTRUMENTATION_RESULT: stream=

Time: 4.131
There was 1 failure:
1) failingTest(com.my.package.test.BasicTest)
java.lang.UnsupportedOperationException: dummy failing test
  at com.my.package.test.BasicTest.failingTest(BasicTest.java:40)
  at java.lang.reflect.Method.invoke(Native Method)
  at org.junit.runners.model.FrameworkMethod$1.runReflectiveCall(FrameworkMethod.java:57)
  at org.junit.internal.runners.model.ReflectiveCallable.run(ReflectiveCallable.java:12)
  at org.junit.runners.model.FrameworkMethod.invokeExplosively(FrameworkMethod.java:59)
  at org.junit.internal.runners.statements.InvokeMethod.evaluate(InvokeMethod.java:17)
  at androidx.test.internal.runner.junit4.statement.RunBefores.evaluate(RunBefores.java:80)
  at androidx.test.internal.runner.junit4.statement.RunAfters.evaluate(RunAfters.java:61)
  at androidx.test.rule.ActivityTestRule$ActivityStatement.evaluate(ActivityTestRule.java:433)
  at com.my.package.test.BaseTest$3.evaluate(BaseTest.java:96)
  at com.my.package.test.BaseTest$4.evaluate(BaseTest.java:109)
  at com.my.package.test.BaseTest$2.evaluate(BaseTest.java:77)
  at org.junit.rules.TestWatcher$1.evaluate(TestWatcher.java:55)
  at org.junit.rules.TestWatcher$1.evaluate(TestWatcher.java:55)
  at org.junit.rules.RunRules.evaluate(RunRules.java:20)
  at org.junit.runners.BlockJUnit4ClassRunner$1.evaluate(BlockJUnit4ClassRunner.java:81)
  at org.junit.runners.ParentRunner.runLeaf(ParentRunner.java:327)
  at org.junit.runners.BlockJUnit4ClassRunner.runChild(BlockJUnit4ClassRunner.java:84)
  at org.junit.runners.BlockJUnit4ClassRunner.runChild(BlockJUnit4ClassRunner.java:57)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at androidx.test.runner.AndroidJUnit4.run(AndroidJUnit4.java:99)
  at org.junit.runners.Suite.runChild(Suite.java:128)
  at org.junit.runners.Suite.runChild(Suite.java:27)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at org.junit.runners.Suite.runChild(Suite.java:128)
  at org.junit.runners.Suite.runChild(Suite.java:27)
  at org.junit.runners.ParentRunner$3.run(ParentRunner.java:292)
  at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:73)
  at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:290)
  at org.junit.runners.ParentRunner.access$000(ParentRunner.java:60)
  at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:270)
  at org.junit.runners.ParentRunner.run(ParentRunner.java:370)
  at org.junit.runner.JUnitCore.run(JUnitCore.java:137)
  at org.junit.runner.JUnitCore.run(JUnitCore.java:115)
  at androidx.test.internal.runner.TestExecutor.execute(TestExecutor.java:56)
  at com.my.package.test.BaseRunner.runTests(BaseRunner.java:344)
  at com.my.package.test.BaseRunner.onStart(BaseRunner.java:330)
  at com.my.package.test.runner.MyRunner.onStart(MyRunner.java:253)
  at android.app.Instrumentation$InstrumentationThread.run(Instrumentation.java:2074)

FAILURES!!!
Tests run: 3,  Failures: 1


INSTRUMENTATION_CODE: -1"""
    expected_executed = [
        ('com.my.package.test.BasicTest#failingTest', signals.TestFailure),
        ('com.my.package.test.BasicTest#passingTest', signals.TestPass),
    ]
    expected_skipped = [
        ('com.my.package.test.BasicTest#assumptionFailureTest',
         signals.TestSkip),
        ('com.my.package.test.BasicTest#ignoredTest', signals.TestSkip),
    ]
    mock_get_time.side_effect = [54, 64, -1, -1, -1, -1, 89, 94]
    self.assert_run_instrumentation_test(instrumentation_output,
                                         expected_executed=expected_executed,
                                         expected_skipped=expected_skipped,
                                         expected_executed_times=[(54, 64),
                                                                  (89, 94)])

  def test__Instrumentation_block_set_key_on_multiple_equals_sign(self):
    value = "blah=blah, blah2=blah2, blah=2=1=2"
    parsed_line = "INSTRUMENTATION_STATUS: stack=%s" % value
    block = _InstrumentationBlock()
    block.set_key(_InstrumentationStructurePrefixes.STATUS, parsed_line)
    self.assertIn(value,
                  block.known_keys[_InstrumentationKnownStatusKeys.STACK])


if __name__ == '__main__':
  unittest.main()
