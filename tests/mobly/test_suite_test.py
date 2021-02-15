# Copyright 2018 Google Inc.
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

from mobly import base_test
from mobly import config_parser
from mobly import records
from mobly import test_runner

from tests.lib import mock_controller
from tests.lib import utils


class TestSuiteTest(unittest.TestCase):
  """Tests for use cases of creating Mobly test suites.

  Tests here target a combination of test_runner and base_test code.
  """

  def setUp(self):
    self.tmp_dir = tempfile.mkdtemp()
    self.mock_test_cls_configs = config_parser.TestRunConfig()
    self.summary_file = os.path.join(self.tmp_dir, 'summary.yaml')
    self.mock_test_cls_configs.summary_writer = records.TestSummaryWriter(
        self.summary_file)
    self.mock_test_cls_configs.log_path = self.tmp_dir
    self.mock_test_cls_configs.user_params = {"some_param": "hahaha"}
    self.mock_test_cls_configs.reporter = mock.MagicMock()
    self.base_mock_test_config = config_parser.TestRunConfig()
    self.base_mock_test_config.testbed_name = 'SampleTestBed'
    self.base_mock_test_config.controller_configs = {}
    self.base_mock_test_config.user_params = {
        'icecream': 42,
        'extra_param': 'haha'
    }
    self.base_mock_test_config.log_path = self.tmp_dir

  def tearDown(self):
    shutil.rmtree(self.tmp_dir)

  def test_controller_object_not_persistent_across_classes(self):
    test_run_config = self.base_mock_test_config.copy()
    test_run_config.controller_configs = {'MagicDevice': [{'serial': 1}]}

    class FooTest(base_test.BaseTestClass):

      def setup_class(cls1):
        self.controller1 = cls1.register_controller(mock_controller)[0]

    class BarTest(base_test.BaseTestClass):

      def setup_class(cls2):
        self.controller2 = cls2.register_controller(mock_controller)[0]

    tr = test_runner.TestRunner(self.tmp_dir, test_run_config.testbed_name)
    with tr.mobly_logger():
      tr.add_test_class(test_run_config, FooTest)
      tr.add_test_class(test_run_config, BarTest)
      tr.run()
    self.assertIsNot(self.controller1, self.controller2)


if __name__ == "__main__":
  unittest.main()
