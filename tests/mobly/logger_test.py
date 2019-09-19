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
import os
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

    def test_sanitize_filename_when_valid(self):
        fake_filename = 'logcat.txt'
        expected_filename = 'logcat.txt'
        self.assertEqual(logger.sanitize_filename(fake_filename),
                         expected_filename)

    def test_sanitize_filename_when_valid_with_path(self):
        fake_filename = os.path.join('dir', 'logs', 'logcat.txt')
        expected_filename = os.path.join('dir', 'logs', 'logcat.txt')
        self.assertEqual(logger.sanitize_filename(fake_filename),
                         expected_filename)

    def test_sanitize_filename_when_random_spaces(self):
        fake_filename = 'log cat file.txt'
        expected_filename = 'log_cat_file.txt'
        self.assertEqual(logger.sanitize_filename(fake_filename),
                         expected_filename)

    def test_sanitize_filename_when_over_260_characters(self):
        fake_filename = 'l' * 300
        expected_filename = 'l' * 260
        self.assertEqual(len(logger.sanitize_filename(fake_filename)), 260)
        self.assertEqual(logger.sanitize_filename(fake_filename),
                         expected_filename)

    def test__sanitize_windows_filename_when_path_characters(self):
        fake_filename = '/\\'
        expected_filename = '__'
        self.assertEqual(logger._sanitize_windows_filename(fake_filename),
                         expected_filename)

    def test_sanitize_filename_when_specical_characters(self):
        fake_filename = '<>:"|?*\x00'
        expected_filename = '---_,,,0'
        self.assertEqual(logger.sanitize_filename(fake_filename),
                         expected_filename)

    def test_sanitize_filename_when_con(self):
        fake_filename = 'con'
        expected_filename = '__con__'
        self.assertEqual(logger.sanitize_filename(fake_filename),
                         expected_filename)

    def test_sanitize_filename_when_prn(self):
        fake_filename = 'PRN'
        expected_filename = '__PRN__'
        self.assertEqual(logger.sanitize_filename(fake_filename),
                         expected_filename)

    def test_sanitize_filename_when_aux(self):
        fake_filename = 'aux'
        expected_filename = '__aux__'
        self.assertEqual(logger.sanitize_filename(fake_filename),
                         expected_filename)

    def test_sanitize_filename_when_nul(self):
        fake_filename = 'NUL'
        expected_filename = '__NUL__'
        self.assertEqual(logger.sanitize_filename(fake_filename),
                         expected_filename)

    def test_sanitize_filename_when_com(self):
        for fake_filename, expected_filename in [
            ('com', 'com'),
            ('COM0', '__COM0__'),
            ('com1', '__com1__'),
            ('COM2', '__COM2__'),
            ('com3', '__com3__'),
            ('COM4', '__COM4__'),
            ('com5', '__com5__'),
            ('COM6', '__COM6__'),
            ('com7', '__com7__'),
            ('COM8', '__COM8__'),
            ('com9', '__com9__'),
        ]:
            self.assertEqual(logger.sanitize_filename(fake_filename),
                             expected_filename)

    def test_sanitize_filename_when_lpt(self):
        for fake_filename, expected_filename in [
            ('lpt', 'lpt'),
            ('LPT0', '__LPT0__'),
            ('lpt1', '__lpt1__'),
            ('LPT2', '__LPT2__'),
            ('lpt3', '__lpt3__'),
            ('LPT4', '__LPT4__'),
            ('lpt5', '__lpt5__'),
            ('LPT6', '__LPT6__'),
            ('lpt7', '__lpt7__'),
            ('LPT8', '__LPT8__'),
            ('lpt9', '__lpt9__'),
        ]:
            self.assertEqual(logger.sanitize_filename(fake_filename),
                             expected_filename)

    def test_sanitize_filename_when_ends_with_space(self):
        fake_filename = 'logcat.txt '
        expected_filename = 'logcat.txt_'
        self.assertEqual(logger.sanitize_filename(fake_filename),
                         expected_filename)

    def test_sanitize_filename_when_ends_with_period(self):
        fake_filename = 'logcat.txt.'
        expected_filename = 'logcat.txt_'
        self.assertEqual(logger.sanitize_filename(fake_filename),
                         expected_filename)


if __name__ == "__main__":
    unittest.main()
