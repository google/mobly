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
import platform
import socket
import time
from future.tests.base import unittest

import portpicker
import psutil
from mobly import utils

MOCK_AVAILABLE_PORT = 5


class UtilsTest(unittest.TestCase):
    """This test class has unit tests for the implementation of everything
    under mobly.utils.
    """

    def setUp(self):
        system = platform.system()
        self.sleep_cmd = 'timeout' if system == 'Windows' else 'sleep'
    
    def test_start_standing_subproc(self):
        p = utils.start_standing_subprocess([self.sleep_cmd, '1'])
        p1 = psutil.Process(p.pid)
        self.assertTrue(p1.is_running())

    def test_stop_standing_subproc(self):
        p = utils.start_standing_subprocess([self.sleep_cmd, '4'])
        p1 = psutil.Process(p.pid)
        utils.stop_standing_subprocess(p)
        self.assertFalse(p1.is_running())

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.list_occupied_adb_ports')
    @mock.patch('portpicker.PickUnusedPort', return_value=MOCK_AVAILABLE_PORT)
    def test_get_available_port_positive(self, mock_list_occupied_adb_ports,
                                         mock_pick_unused_port):
        self.assertEqual(utils.get_available_host_port(), MOCK_AVAILABLE_PORT)

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.list_occupied_adb_ports',
        return_value=[MOCK_AVAILABLE_PORT])
    @mock.patch('portpicker.PickUnusedPort', return_value=MOCK_AVAILABLE_PORT)
    def test_get_available_port_negative(self, mock_list_occupied_adb_ports,
                                         mock_pick_unused_port):
        with self.assertRaisesRegex(utils.Error, 'Failed to find.* retries'):
            utils.get_available_host_port()

    @mock.patch(
        'mobly.controllers.android_device_lib.adb.list_occupied_adb_ports')
    def test_get_available_port_returns_free_port(
            self, mock_list_occupied_adb_ports):
        """Verifies logic to pick a free port on the host.

        Test checks we can bind to either an ipv4 or ipv6 socket on the port
        returned by get_available_host_port.
        """
        port = utils.get_available_host_port()
        got_socket = False
        for family in (socket.AF_INET, socket.AF_INET6):
            try:
                s = socket.socket(family, socket.SOCK_STREAM)
                got_socket = True
                break
            except socket.error:
                continue
        self.assertTrue(got_socket)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(('localhost', port))
        finally:
            s.close()


if __name__ == '__main__':
    unittest.main()
