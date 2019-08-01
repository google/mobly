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

import mock
import pytz
import shutil
import tempfile
import unittest

from mobly import logger


class LoggerTest(unittest.TestCase):
    """Verifies code in mobly.logger module.
    """
    def setUp(self):
        self.log_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.log_dir)

    def test_epoch_to_log_line_timestamp(self):
        actual_stamp = logger.epoch_to_log_line_timestamp(1469134262116,
                                                          time_zone=pytz.utc)
        self.assertEqual("07-21 20:51:02.116", actual_stamp)

    def test_is_valid_logline_timestamp(self):
        self.assertTrue(
            logger.is_valid_logline_timestamp("06-21 17:44:42.336"))

    def test_is_valid_logline_timestamp_when_wrong_length(self):
        self.assertFalse(
            logger.is_valid_logline_timestamp("  06-21 17:44:42.336"))

    def test_is_valid_logline_timestamp_when_invalid_content(self):
        self.assertFalse(
            logger.is_valid_logline_timestamp("------------------"))

    @mock.patch('mobly.utils.create_alias')
    def test_create_latest_log_alias(self, mock_create_alias):
        logger.create_latest_log_alias('fake_path', alias='latest')
        mock_create_alias.assert_called_once_with('fake_path', 'latest')

    @mock.patch('mobly.logger._setup_test_logger')
    @mock.patch('mobly.logger.create_latest_log_alias')
    def test_setup_test_logger_creates_log_alias(self,
                                                 mock_create_latest_log_alias,
                                                 mock__setup_test_logger):
        logger.setup_test_logger(self.log_dir)
        mock__setup_test_logger.assert_called_once_with(self.log_dir, None)
        mock_create_latest_log_alias.assert_called_once_with(self.log_dir,
                                                             alias='latest')

    @mock.patch('mobly.logger._setup_test_logger')
    @mock.patch('mobly.logger.create_latest_log_alias')
    def test_setup_test_logger_creates_log_alias_with_custom_value(
            self, mock_create_latest_log_alias, mock__setup_test_logger):
        mock_alias = mock.MagicMock()
        logger.setup_test_logger(self.log_dir, alias=mock_alias)

        mock_create_latest_log_alias.assert_called_once_with(self.log_dir,
                                                             alias=mock_alias)


if __name__ == "__main__":
    unittest.main()
