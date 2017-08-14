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

import sys

from future.tests.base import unittest

from mobly.controllers.android_device_lib import adb


class AdbTest(unittest.TestCase):
    """Unit tests for mobly.controllers.android_device_lib.adb.
    """

    PYTHON_PATH = sys.executable

    def test_exec_cmd_no_timeout_success(self):
        reply = adb.AdbProxy()._exec_cmd(
            ["echo", "test"], shell=False, timeout=None)
        self.assertEqual("test\n", reply.decode('utf-8'))

    def test_exec_cmd_error_no_timeout(self):
        with self.assertRaisesRegex(adb.AdbError,
                                    "Error executing adb cmd .*"):
            adb.AdbProxy()._exec_cmd(["false"], shell=False, timeout=None)

    def test_exec_cmd_with_timeout_success(self):
        reply = adb.AdbProxy()._exec_cmd(
            ["echo", "test;", self.PYTHON_PATH, "-c",
             "'import time; time.sleep(0.1)'"], shell=False, timeout=1)
        self.assertEqual(
            "test; " + self.PYTHON_PATH
            + " -c 'import time; time.sleep(0.1)'\n", reply.decode('utf-8'))

    def test_exec_cmd_timed_out(self):
        with self.assertRaisesRegex(
            adb.AdbTimeoutError, "Timed out Adb cmd .*"):
            adb.AdbProxy()._exec_cmd(
                [self.PYTHON_PATH, "-c", "import time; time.sleep(0.2)"],
                shell=False, timeout=0.1)

    def test_exec_cmd_timed_negative_error(self):
        with self.assertRaisesRegex(
                adb.AdbError, "Timeout is a negative value: .*"):
            adb.AdbProxy()._exec_cmd(
                    [self.PYTHON_PATH, "-c", "import time; time.sleep(0.2)"],
                    shell=False, timeout=-1)


if __name__ == "__main__":
    unittest.main()
