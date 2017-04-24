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
import socket
import time
import unittest

import portpicker
from mobly import utils

AVAILABLE_PORT = 5


class UtilsTest(unittest.TestCase):
    """This test class has unit tests for the implementation of everything
    under mobly.utils.
    """

    def test_start_standing_subproc(self):
        with self.assertRaisesRegexp(utils.Error, 'Process .* has terminated'):
            utils.start_standing_subprocess(
                ['sleep', '0'], check_health_delay=0.5)

    def test_stop_standing_subproc(self):
        p = utils.start_standing_subprocess(['sleep', '5'])
        utils.stop_standing_subprocess(p)
        self.assertIsNotNone(p.poll())

    def test_stop_standing_subproc_already_dead(self):
        p = utils.start_standing_subprocess(['sleep', '0'])
        time.sleep(0.5)
        with self.assertRaisesRegexp(utils.Error, 'Process .* has terminated'):
            utils.stop_standing_subprocess(p)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.list_occupied_adb_ports')
    @mock.patch('portpicker.PickUnusedPort', return_value=AVAILABLE_PORT)
    def test_get_available_port_positive(self, mock_list_occupied_adb_ports,
                                         mock_pick_unused_port):
        self.assertEqual(utils.get_available_host_port(), AVAILABLE_PORT)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.list_occupied_adb_ports',
        return_value=[AVAILABLE_PORT])
    @mock.patch('portpicker.PickUnusedPort', return_value=AVAILABLE_PORT)
    def test_get_available_port_negative(self, mock_list_occupied_adb_ports,
                                         mock_pick_unused_port):
        with self.assertRaisesRegexp(utils.Error, 'Failed to find.* retries'):
            utils.get_available_host_port()

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.list_occupied_adb_ports')
    def test_get_available_port_returns_free_port(
            self, mock_list_occupied_adb_ports):
        port = utils.get_available_host_port()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(('localhost', port))
        finally:
            s.close()


if __name__ == '__main__':
    unittest.main()
