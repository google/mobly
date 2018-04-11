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

import datetime
import unittest
import pytz
import mock

from mobly import logger

MOCK_DATETIME_NOW_YEAR = 2016
MOCK_DATETIME_NOW = datetime.datetime(MOCK_DATETIME_NOW_YEAR, 2, 29, 14, 35,
                                      57, 888000)


class LoggerTest(unittest.TestCase):
    """Verifies code in mobly.logger module.
    """

    def test_epoch_to_log_line_timestamp(self):
        actual_stamp = logger.epoch_to_log_line_timestamp(
            1469134262116, time_zone=pytz.utc)
        self.assertEqual("07-21 20:51:02.116", actual_stamp)

    @mock.patch(
        'mobly.logger._get_datetime_now', return_value=MOCK_DATETIME_NOW)
    def test_log_line_to_log_file_timestamp(self, mock_datetime_now):
        log_line_timestamp = logger.get_log_line_timestamp()
        log_file_timestamp = logger.get_log_file_timestamp()
        converted_log_file_timestamp = logger.log_line_to_log_file_timestamp(
            log_line_timestamp, MOCK_DATETIME_NOW_YEAR)
        self.assertEqual(converted_log_file_timestamp, log_file_timestamp)


if __name__ == "__main__":
    unittest.main()
