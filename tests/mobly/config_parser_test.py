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

import io
import os
import shutil
import tempfile
import unittest

from mobly import config_parser


class OutputTest(unittest.TestCase):
  """This test class has unit tests for the implementation of Mobly's output
  files.
  """

  def setUp(self):
    self.tmp_dir = tempfile.mkdtemp()

  def tearDown(self):
    shutil.rmtree(self.tmp_dir)

  def test__load_config_file(self):
    tmp_file_path = os.path.join(self.tmp_dir, 'config.yml')
    with io.open(tmp_file_path, 'w', encoding='utf-8') as f:
      f.write(u'TestBeds:\n')
      f.write(u'  # A test bed where adb will find Android devices.\n')
      f.write(u'  - Name: SampleTestBed\n')
      f.write(u'    Controllers:\n')
      f.write(u'        AndroidDevice: \'*\'\n')

    config = config_parser._load_config_file(tmp_file_path)
    self.assertEqual(config['TestBeds'][0]['Name'], u'SampleTestBed')

  def test__load_config_file_with_unicode(self):
    tmp_file_path = os.path.join(self.tmp_dir, 'config.yml')
    with io.open(tmp_file_path, 'w', encoding='utf-8') as f:
      f.write(u'TestBeds:\n')
      f.write(u'  # A test bed where adb will find Android devices.\n')
      f.write(u'  - Name: \u901a\n')
      f.write(u'    Controllers:\n')
      f.write(u'        AndroidDevice: \'*\'\n')

    config = config_parser._load_config_file(tmp_file_path)
    self.assertEqual(config['TestBeds'][0]['Name'], u'\u901a')

  def test_run_config_type(self):
    config = config_parser.TestRunConfig()
    self.assertNotIn('summary_writer', str(config))
    self.assertNotIn('register_controller', str(config))

  def test_run_config_controller_configs_is_already_initialized(self):
    config = config_parser.TestRunConfig()
    expected_value = 'SOME_VALUE'
    self.assertEqual(
        config.controller_configs.get('NON_EXISTENT_KEY', expected_value),
        expected_value)

  def test_run_config_user_params_is_already_initialized(self):
    config = config_parser.TestRunConfig()
    expected_value = 'SOME_VALUE'
    self.assertEqual(config.user_params.get('NON_EXISTENT_KEY', expected_value),
                     expected_value)


if __name__ == '__main__':
  unittest.main()
