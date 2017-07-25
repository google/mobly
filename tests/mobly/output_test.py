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
import shutil
import tempfile
import unittest
import yaml

from mobly import config_parser
from mobly import records
from mobly import test_runner

from tests.lib import mock_controller
from tests.lib import integration_test


class OutputTest(unittest.TestCase):
    """This test class has unit tests for the implementation of Mobly's output
    files.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.base_mock_test_config = config_parser.TestRunConfig()
        self.base_mock_test_config.test_bed_name = 'SampleTestBed'
        self.base_mock_test_config.controller_configs = {}
        self.base_mock_test_config.user_params = {
            'icecream': 42,
            'extra_param': 'haha'
        }
        self.base_mock_test_config.log_path = self.tmp_dir
        self.log_dir = self.base_mock_test_config.log_path
        self.test_bed_name = self.base_mock_test_config.test_bed_name

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_output(self):
        """Verifies the expected output files from a test run.

        * Files are correctly created.
        * Basic sanity checks of each output file.
        """
        mock_test_config = self.base_mock_test_config.copy()
        mock_ctrlr_config_name = mock_controller.MOBLY_CONTROLLER_CONFIG_NAME
        my_config = [{
            'serial': 'xxxx',
            'magic': 'Magic1'
        }, {
            'serial': 'xxxx',
            'magic': 'Magic2'
        }]
        mock_test_config.controller_configs[mock_ctrlr_config_name] = my_config
        tr = test_runner.TestRunner(self.log_dir, self.test_bed_name)
        tr.add_test_class(mock_test_config, integration_test.IntegrationTest)
        tr.run()
        output_dir = os.path.join(self.log_dir, self.test_bed_name, 'latest')
        summary_file_path = os.path.join(output_dir,
                                         records.OUTPUT_FILE_SUMMARY)
        debug_log_path = os.path.join(output_dir,
                                      records.OUTPUT_FILE_DEBUG_LOG)
        info_log_path = os.path.join(output_dir, records.OUTPUT_FILE_INFO_LOG)
        self.assertTrue(os.path.isfile(summary_file_path))
        self.assertTrue(os.path.isfile(debug_log_path))
        self.assertTrue(os.path.isfile(info_log_path))
        summary_entries = []
        with open(summary_file_path) as f:
            for entry in yaml.load_all(f):
                self.assertTrue(entry['Type'])
                summary_entries.append(entry)
        with open(debug_log_path, 'r') as f:
            content = f.read()
            self.assertIn('DEBUG', content)
            self.assertIn('INFO', content)
        with open(info_log_path, 'r') as f:
            content = f.read()
            self.assertIn('INFO', content)
            self.assertNotIn('DEBUG', content)


if __name__ == "__main__":
    unittest.main()
