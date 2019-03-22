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

import io
import mock
import os
import platform
import shutil
import socket
import subprocess
import tempfile
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
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def sleep_cmd(self, wait_secs):
        if platform.system() == 'Windows':
            python_code = ['import time', 'time.sleep(%s)' % wait_secs]
            return ['python', '-c', 'exec("%s")' % r'\r\n'.join(python_code)]
        else:
            return ['sleep', str(wait_secs)]

    def test_run_command(self):
        (ret, out, err) = utils.run_command(self.sleep_cmd(0.01))
        self.assertEqual(ret, 0)

    def test_run_command_with_timeout(self):
        (ret, out, err) = utils.run_command(self.sleep_cmd(0.01), timeout=4)
        self.assertEqual(ret, 0)

    def test_run_command_with_timeout_expired(self):
        with self.assertRaises(psutil.TimeoutExpired):
            _ = utils.run_command(self.sleep_cmd(4), timeout=0.01)

    @mock.patch('threading.Timer')
    @mock.patch('psutil.Popen')
    def test_run_command_with_default_params(self, mock_Popen, mock_Timer):
        mock_command = mock.MagicMock(spec=dict)
        mock_proc = mock_Popen.return_value
        mock_proc.communicate.return_value = ('fake_out', 'fake_err')
        mock_proc.returncode = 0
        out = utils.run_command(mock_command)
        self.assertEqual(out, (0, 'fake_out', 'fake_err'))
        mock_Popen.assert_called_with(
            mock_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            cwd=None,
            env=None,
        )
        mock_Timer.assert_not_called()

    @mock.patch('threading.Timer')
    @mock.patch('psutil.Popen')
    def test_run_command_with_custom_params(self, mock_Popen, mock_Timer):
        mock_command = mock.MagicMock(spec=dict)
        mock_stdout = mock.MagicMock(spec=int)
        mock_stderr = mock.MagicMock(spec=int)
        mock_shell = mock.MagicMock(spec=bool)
        mock_timeout = 1234
        mock_env = mock.MagicMock(spec=dict)
        mock_proc = mock_Popen.return_value
        mock_proc.communicate.return_value = ('fake_out', 'fake_err')
        mock_proc.returncode = 127
        out = utils.run_command(
            mock_command,
            stdout=mock_stdout,
            stderr=mock_stderr,
            shell=mock_shell,
            timeout=mock_timeout,
            env=mock_env)
        self.assertEqual(out, (127, 'fake_out', 'fake_err'))
        mock_Popen.assert_called_with(
            mock_command,
            stdout=mock_stdout,
            stderr=mock_stderr,
            shell=mock_shell,
            cwd=None,
            env=mock_env,
        )
        mock_Timer.assert_called_with(1234, mock.ANY)

    def test_start_standing_subproc(self):
        try:
            p = utils.start_standing_subprocess(self.sleep_cmd(0.01))
            p1 = psutil.Process(p.pid)
            self.assertTrue(p1.is_running())
        finally:
            p.stdout.close()
            p.stderr.close()
            p.wait()

    @mock.patch('subprocess.Popen')
    def test_start_standing_subproc_without_env(self, mock_Popen):
        p = utils.start_standing_subprocess(self.sleep_cmd(0.01))
        mock_Popen.assert_called_with(
            self.sleep_cmd(0.01),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            env=None,
        )

    @mock.patch('subprocess.Popen')
    def test_start_standing_subproc_with_custom_env(self, mock_Popen):
        mock_env = mock.MagicMock(spec=dict)
        p = utils.start_standing_subprocess(self.sleep_cmd(0.01), env=mock_env)
        mock_Popen.assert_called_with(
            self.sleep_cmd(0.01),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            env=mock_env,
        )

    def test_stop_standing_subproc(self):
        p = utils.start_standing_subprocess(self.sleep_cmd(4))
        p1 = psutil.Process(p.pid)
        utils.stop_standing_subprocess(p)
        self.assertFalse(p1.is_running())

    def test_stop_standing_subproc_wihtout_pipe(self):
        p = subprocess.Popen(self.sleep_cmd(4))
        self.assertIsNone(p.stdout)
        p1 = psutil.Process(p.pid)
        utils.stop_standing_subprocess(p)
        self.assertFalse(p1.is_running())

    def test_create_dir(self):
        new_path = os.path.join(self.tmp_dir, 'haha')
        self.assertFalse(os.path.exists(new_path))
        utils.create_dir(new_path)
        self.assertTrue(os.path.exists(new_path))

    def test_create_dir_already_exists(self):
        self.assertTrue(os.path.exists(self.tmp_dir))
        utils.create_dir(self.tmp_dir)
        self.assertTrue(os.path.exists(self.tmp_dir))

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

    def test_load_file_to_base64_str_reads_bytes_file_as_base64_string(self):
        tmp_file_path = os.path.join(self.tmp_dir, 'b64.bin')
        expected_base64_encoding = u'SGVsbG93IHdvcmxkIQ=='
        with io.open(tmp_file_path, 'wb') as f:
            f.write(b'Hellow world!')
        self.assertEqual(
            utils.load_file_to_base64_str(tmp_file_path),
            expected_base64_encoding)

    def test_load_file_to_base64_str_reads_text_file_as_base64_string(self):
        tmp_file_path = os.path.join(self.tmp_dir, 'b64.bin')
        expected_base64_encoding = u'SGVsbG93IHdvcmxkIQ=='
        with io.open(tmp_file_path, 'w', encoding='utf-8') as f:
            f.write(u'Hellow world!')
        self.assertEqual(
            utils.load_file_to_base64_str(tmp_file_path),
            expected_base64_encoding)

    def test_load_file_to_base64_str_reads_unicode_file_as_base64_string(self):
        tmp_file_path = os.path.join(self.tmp_dir, 'b64.bin')
        expected_base64_encoding = u'6YCa'
        with io.open(tmp_file_path, 'w', encoding='utf-8') as f:
            f.write(u'\u901a')
        self.assertEqual(
            utils.load_file_to_base64_str(tmp_file_path),
            expected_base64_encoding)

    def test_cli_cmd_to_string(self):
        cmd = ['"adb"', 'a b', 'c//']
        self.assertEqual(utils.cli_cmd_to_string(cmd), '\'"adb"\' \'a b\' c//')
        cmd = 'adb -s meme do something ab_cd'
        self.assertEqual(utils.cli_cmd_to_string(cmd), cmd)


if __name__ == '__main__':
    unittest.main()
