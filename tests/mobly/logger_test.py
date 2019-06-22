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
import unittest

from mobly import logger


class LoggerTest(unittest.TestCase):
    """Verifies code in mobly.logger module.
    """

    def test_epoch_to_log_line_timestamp(self):
        actual_stamp = logger.epoch_to_log_line_timestamp(
            1469134262116, time_zone=pytz.utc)
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
        logger.create_latest_log_alias('fake_path')
        mock_create_alias.assert_called_with('fake_path', 'latest')

    @mock.patch('mobly.utils.create_alias')
    @mock.patch('mobly.logger.LATEST_LOG_ALIAS', None)
    def test_create_latest_log_alias_when_none(self, mock_create_alias):
        logger.create_latest_log_alias('fake_path')
        mock_create_alias.assert_not_called()

    @mock.patch('mobly.utils.create_alias')
    @mock.patch('mobly.logger.LATEST_LOG_ALIAS', '')
    def test_create_latest_log_alias_when_empty(self, mock_create_alias):
        logger.create_latest_log_alias('fake_path')
        mock_create_alias.assert_not_called()

    @mock.patch('mobly.utils.create_alias')
    @mock.patch('mobly.logger.LATEST_LOG_ALIAS', 'history')
    def test_create_latest_log_alias_when_custom_value(self,
                                                       mock_create_alias):
        logger.create_latest_log_alias('fake_path')
        mock_create_alias.assert_called_with('fake_path', 'history')


if __name__ == "__main__":
    unittest.main()
