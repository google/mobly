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
import logging
import mock
import shutil
import tempfile
import threading

from dateutil.parser import parse as parse_date
from future.tests.base import unittest
from mobly import utils
from mobly.controllers import android_device
from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib.services import logcat_pubsub
from tests.lib import mock_android_device


MOCK_SERIAL = '012345678'
MOCK_LOG_LINES = [
    '--------- beginning of system\n',
    '01-02 03:45:01.100  1000  1001 I MockManager: Starting service.\n',
    '01-02 03:45:01.200  1000  1001 I MockManager: Init complete.\n',
    '--------- beginning of main\n',
    '01-02 03:45:02.300  2000  2001 I MockService: a=0 b=1 c=2.\n',
    '01-02 03:45:02.400  2000  2001 I MockService: a=4 b=5 c=6.\n',
    '01-02 03:45:02.500  1000  1010 E MockManager: error_code=\xcf\x80.\n',
]


def mock_process():
    """Create a mock process with a mock stdout stream."""
    process = mock.MagicMock()
    process.stdout = MockStream()
    return process


class MockStream(object):
    """Mock I/O stream."""

    def __init__(self):
        self._buffer = []
        self._read_ready = threading.Semaphore(0)

    def writeline(self, line):
        self._buffer.append(line)
        self._read_ready.release()

    def readline(self):
        self._read_ready.acquire()
        return self._buffer.pop(0)


class LogcatPubsubTest(unittest.TestCase):
    """Tests for Logcat publisher/subscriber service."""

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy(MOCK_SERIAL))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy(MOCK_SERIAL))
    @mock.patch('mobly.utils.start_standing_subprocess')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_logcat_event_pattern(self, stop_standing_subprocess,
                                  start_standing_subprocess,
                                  FastbootProxy, AdbProxy):
        """A test case the checks the logcat event pattern matching."""
        process = mock_process()
        start_standing_subprocess.return_value = process
        ad = android_device.AndroidDevice(serial=MOCK_SERIAL)
        ad.services.register('publisher', logcat_pubsub.LogcatPublisher)
        with ad.services.publisher.event(pattern='Init complete.') as event:
            list(map(process.stdout.writeline, MOCK_LOG_LINES))
            self.assertTrue(event.wait(1), 'Event never detected.')

        self.assert_event(
            event.trigger, time=parse_date('01-02 03:45:01.200'), level='I',
            pid=1000, tid=1001, tag='MockManager', message='Init complete.')

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy(MOCK_SERIAL))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy(MOCK_SERIAL))
    @mock.patch('mobly.utils.start_standing_subprocess')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_logcat_event_tag(self, stop_standing_subprocess,
                              start_standing_subprocess, FastbootProxy,
                              AdbProxy):
        """A test case that checks the logcat event tag matching."""
        process = mock_process()
        start_standing_subprocess.return_value = process
        ad = android_device.AndroidDevice(serial=MOCK_SERIAL)
        ad.services.register('publisher', logcat_pubsub.LogcatPublisher)
        with ad.services.publisher.event(tag='*Serv*') as event:
            list(map(process.stdout.writeline, MOCK_LOG_LINES))
            self.assertTrue(event.wait(1), 'Event never detected.')

        self.assert_event(
            event.trigger, time=parse_date('01-02 03:45:02.300'), level='I',
            pid=2000, tid=2001, tag='MockService', message='a=0 b=1 c=2.')

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy(MOCK_SERIAL))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy(MOCK_SERIAL))
    @mock.patch('mobly.utils.start_standing_subprocess')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_logcat_event_level(self, stop_standing_subprocess,
                                start_standing_subprocess, FastbootProxy,
                                AdbProxy):
        """A test case that checks the logcat event level matching."""
        process = mock_process()
        start_standing_subprocess.return_value = process
        ad = android_device.AndroidDevice(serial=MOCK_SERIAL)
        ad.services.register('publisher', logcat_pubsub.LogcatPublisher)
        with ad.services.publisher.event(level='E') as event:
            list(map(process.stdout.writeline, MOCK_LOG_LINES))
            self.assertTrue(event.wait(1), 'Event never detected.')

        self.assert_event(
            event.trigger, time=parse_date('01-02 03:45:02.500'), level='E',
            pid=1000, tid=1010, tag='MockManager',
            message='error_code=\xcf\x80.')

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.AdbProxy',
        return_value=mock_android_device.MockAdbProxy(MOCK_SERIAL))
    @mock.patch(
        'mobly.controllers.android_device_lib.fastboot.FastbootProxy',
        return_value=mock_android_device.MockFastbootProxy(MOCK_SERIAL))
    @mock.patch('mobly.utils.start_standing_subprocess')
    @mock.patch('mobly.utils.stop_standing_subprocess')
    def test_logcat_event_regex(self, stop_standing_subprocess,
                                start_standing_subprocess, FastbootProxy,
                                AdbProxy):
        """A test case that checks the logcat event regex matching."""
        process = mock_process()
        start_standing_subprocess.return_value = process
        ad = android_device.AndroidDevice(serial=MOCK_SERIAL)
        ad.services.register('publisher', logcat_pubsub.LogcatPublisher)
        pattern = 'a=(?P<a>\d+) b=(?P<b>\d+) c=(?P<c>\d+)'
        with ad.services.publisher.event(pattern=pattern) as event:
            list(map(process.stdout.writeline, MOCK_LOG_LINES))
            self.assertTrue(event.wait(1), 'Event never detected.')

        self.assert_event(
            event.trigger, time=parse_date('01-02 03:45:02.300'), level='I',
            pid=2000, tid=2001, tag='MockService', message='a=0 b=1 c=2.')
        match_dict = event.match.groupdict()
        for value, key in enumerate('abc'):
            self.assertEqual(
                int(match_dict[key]), value,
                'Regex match failed. Expected {}={} but got {}.'.format(
                    key, value, match_dict[key]))

    def assert_event(self, actual_trigger, **expected_trigger_dict):
        """Check that the actual trigger values match the expected values.

        Args:
            actual_trigger: Actual trigger.
            exepcted_event_dict: A dictionary of the expected values.
        """
        for key, expected_value in expected_trigger_dict.items():
            actual_value = getattr(actual_trigger, key)
            error_msg = 'Expected value {} but actual value'.format(
                expected_value, actual_value)
            self.assertEqual(expected_value, actual_value, error_msg)


if __name__ == '__main__':
    unittest.main()
