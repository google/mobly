# Copyright 2024 Google Inc.
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

import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from mobly import base_suite
from mobly import base_test
from mobly import suite_runner
from mobly import test_runner
from mobly import config_parser
from tests.lib import integration2_test
from tests.lib import integration_test


class FakeTest1(base_test.BaseTestClass):

  def test_a(self):
    pass

  def test_b(self):
    pass

  def test_c(self):
    pass


class FakeTest2(base_test.BaseTestClass):

  def test_2(self):
    pass


class FakeTestSuite(base_suite.BaseSuite):

  def setup_suite(self, config):
    self.add_test_class(FakeTest1, config)
    self.add_test_class(FakeTest2, config)


class FakeTestSuiteWithFilteredTests(base_suite.BaseSuite):

  def setup_suite(self, config):
    self.add_test_class(FakeTest1, config, ['test_a', 'test_b'])
    self.add_test_class(FakeTest2, config, ['test_2'])


class BaseSuiteTest(unittest.TestCase):

  def setUp(self):
    super().setUp()
    self.mock_config = mock.Mock(autospec=config_parser.TestRunConfig)
    self.mock_test_runner = mock.Mock(autospec=test_runner.TestRunner)

  def test_setup_suite(self):
    suite = FakeTestSuite(self.mock_test_runner, self.mock_config)
    suite.set_test_selector(None)

    suite.setup_suite(self.mock_config)

    self.mock_test_runner.add_test_class.assert_has_calls(
        [
            mock.call(self.mock_config, FakeTest1, mock.ANY, mock.ANY),
            mock.call(self.mock_config, FakeTest2, mock.ANY, mock.ANY),
        ],
    )

  def test_setup_suite_with_test_selector(self):
    suite = FakeTestSuite(self.mock_test_runner, self.mock_config)
    test_selector = {
        'FakeTest1': ['test_a', 'test_b'],
        'FakeTest2': None,
    }

    suite.set_test_selector(test_selector)
    suite.setup_suite(self.mock_config)

    self.mock_test_runner.add_test_class.assert_has_calls(
        [
            mock.call(
                self.mock_config, FakeTest1, ['test_a', 'test_b'], mock.ANY
            ),
            mock.call(self.mock_config, FakeTest2, None, mock.ANY),
        ],
    )

  def test_setup_suite_test_selector_takes_precedence(self):
    suite = FakeTestSuiteWithFilteredTests(
        self.mock_test_runner, self.mock_config
    )
    test_selector = {
        'FakeTest1': ['test_a', 'test_c'],
        'FakeTest2': None,
    }

    suite.set_test_selector(test_selector)
    suite.setup_suite(self.mock_config)

    self.mock_test_runner.add_test_class.assert_has_calls(
        [
            mock.call(
                self.mock_config, FakeTest1, ['test_a', 'test_c'], mock.ANY
            ),
            mock.call(self.mock_config, FakeTest2, None, mock.ANY),
        ],
    )

  def test_setup_suite_with_skip_test_class(self):
    suite = FakeTestSuite(self.mock_test_runner, self.mock_config)
    test_selector = {'FakeTest1': None}

    suite.set_test_selector(test_selector)
    suite.setup_suite(self.mock_config)

    self.mock_test_runner.add_test_class.assert_has_calls(
        [
            mock.call(self.mock_config, FakeTest1, None, mock.ANY),
        ],
    )


if __name__ == '__main__':
  unittest.main()
