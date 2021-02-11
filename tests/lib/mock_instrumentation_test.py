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

import mock

from mobly import base_instrumentation_test
from mobly import config_parser
from mobly.controllers import android_device
from mobly.controllers.android_device_lib import adb

# A mock test package for instrumentation.
MOCK_TEST_PACKAGE = 'com.my.package.test'


class MockInstrumentationTest(
    base_instrumentation_test.BaseInstrumentationTestClass):

  def __init__(self, tmp_dir, user_params={}):
    mock_test_run_configs = config_parser.TestRunConfig()
    mock_test_run_configs.summary_writer = mock.Mock()
    mock_test_run_configs.log_path = tmp_dir
    mock_test_run_configs.user_params = user_params
    mock_test_run_configs.reporter = mock.MagicMock()
    super().__init__(mock_test_run_configs)

  def run_mock_instrumentation_test(self, instrumentation_output, prefix):

    def fake_instrument(package, options=None, runner=None, handler=None):
      for line in instrumentation_output.splitlines():
        handler(line)
      return instrumentation_output

    mock_device = mock.Mock(spec=android_device.AndroidDevice)
    mock_device.adb = mock.Mock(spec=adb.AdbProxy)
    mock_device.adb.instrument = fake_instrument
    return self.run_instrumentation_test(mock_device,
                                         MOCK_TEST_PACKAGE,
                                         prefix=prefix)
