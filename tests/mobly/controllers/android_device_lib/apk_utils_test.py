# Copyright 2024 Google Inc.
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

import unittest
from unittest import mock

from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import apk_utils
from mobly.controllers.android_device_lib import errors


DEFAULT_INSTALL_TIMEOUT_SEC = 300
APK_PATH = 'some/apk/path'


class ApkUtilsTest(unittest.TestCase):

  def setUp(self):
    super(ApkUtilsTest, self).setUp()
    self.mock_device = mock.MagicMock()
    self.mock_device.adb.current_user_id = 0

  def test_install_default_version(self):
    apk_utils.install(self.mock_device, APK_PATH)
    self.mock_device.adb.install.assert_called_with(
        ['-r', '-t', APK_PATH],
        timeout=DEFAULT_INSTALL_TIMEOUT_SEC,
        stderr=mock.ANY,
    )

  def test_install_sdk17(self):
    self.mock_device.build_info = {'build_version_sdk': 17}
    self.mock_device.adb.getprop.return_value = 'none'
    apk_utils.install(self.mock_device, APK_PATH)
    self.mock_device.adb.install.assert_called_with(
        ['-r', '-t', '-d', APK_PATH],
        timeout=DEFAULT_INSTALL_TIMEOUT_SEC,
        stderr=mock.ANY,
    )

  def test_install_sdk23(self):
    self.mock_device.build_info = {'build_version_sdk': 23}
    self.mock_device.adb.getprop.return_value = 'none'
    apk_utils.install(self.mock_device, APK_PATH)
    self.mock_device.adb.install.assert_called_with(
        ['-r', '-t', '-g', '-d', APK_PATH],
        timeout=DEFAULT_INSTALL_TIMEOUT_SEC,
        stderr=mock.ANY,
    )

  def test_install_sdk25(self):
    self.mock_device.build_info = {'build_version_sdk': 25}
    apk_utils.install(self.mock_device, APK_PATH)
    self.mock_device.adb.install.assert_called_with(
        ['--user', '0', '-r', '-t', '-g', '-d', APK_PATH],
        timeout=DEFAULT_INSTALL_TIMEOUT_SEC,
        stderr=mock.ANY,
    )

  def test_install_with_user_id(self):
    self.mock_device.build_info = {'build_version_sdk': 25}
    apk_utils.install(self.mock_device, APK_PATH, user_id=123)
    self.mock_device.adb.install.assert_called_with(
        ['--user', '123', '-r', '-t', '-g', '-d', APK_PATH],
        timeout=DEFAULT_INSTALL_TIMEOUT_SEC,
        stderr=mock.ANY,
    )

  def test_install_with_params(self):
    param = '--force-queryable'
    apk_utils.install(self.mock_device, APK_PATH, params=[param])
    self.mock_device.adb.install.assert_called_with(
        ['-r', '-t', param, APK_PATH],
        timeout=DEFAULT_INSTALL_TIMEOUT_SEC,
        stderr=mock.ANY,
    )

  def test_install_with_user_id_sdk_too_low(self):
    self.mock_device.build_info = {'build_version_sdk': 21}
    with self.assertRaisesRegex(
        ValueError, 'Cannot specify `user_id` for device below SDK 24.'
    ):
      apk_utils.install(self.mock_device, APK_PATH, user_id=123)

  def test_install_adb_raise_error_no_retry(self):
    self.mock_device.adb.install.side_effect = adb.AdbError(
        cmd='adb install -s xxx', stdout='aaa', stderr='bbb', ret_code=1
    )
    with self.assertRaisesRegex(
        adb.AdbError,
        'Error executing adb cmd "adb install -s xxx".'
        ' ret: 1, stdout: aaa, stderr: bbb',
    ):
      apk_utils.install(self.mock_device, APK_PATH)
    self.mock_device.reboot.assert_not_called()
    self.mock_device.adb.install.assert_called_once_with(
        ['-r', '-t', APK_PATH],
        timeout=DEFAULT_INSTALL_TIMEOUT_SEC,
        stderr=mock.ANY,
    )

  def test_install_adb_fail_by_stdout_raise_no_retry(self):
    self.mock_device.adb.install.return_value = b'Failure'
    with self.assertRaisesRegex(
        adb.AdbError,
        '^Error executing adb cmd "adb -s .* some/apk/path". ret: 0, stdout:'
        ' .*Failure.*, stderr: $',
    ):
      apk_utils.install(self.mock_device, APK_PATH)
    self.mock_device.reboot.assert_not_called()
    self.mock_device.adb.install.assert_called_once_with(
        ['-r', '-t', APK_PATH],
        timeout=DEFAULT_INSTALL_TIMEOUT_SEC,
        stderr=mock.ANY,
    )

  @mock.patch('io.BytesIO')
  def test_install_adb_fail_by_stderr_raise_no_retry(self, mock_bytes_io):
    byte_io = mock.MagicMock()
    byte_io.getvalue.return_value = b'Some error'
    mock_bytes_io.return_value = byte_io
    self.mock_device.adb.install.return_value = b''
    with self.assertRaisesRegex(
        adb.AdbError,
        '^Error executing adb cmd "adb -s .* some/apk/path". ret: 0, '
        'stdout: .*, stderr: Some error',
    ):
      apk_utils.install(self.mock_device, APK_PATH)
    self.mock_device.reboot.assert_not_called()
    self.mock_device.adb.install.assert_called_once_with(
        ['-r', '-t', APK_PATH],
        timeout=DEFAULT_INSTALL_TIMEOUT_SEC,
        stderr=mock.ANY,
    )

  @mock.patch('io.BytesIO')
  def test_install_adb_pass_by_stderr_message(self, mock_bytes_io):
    byte_io = mock.MagicMock()
    byte_io.getvalue.return_value = b'Success'
    mock_bytes_io.return_value = byte_io
    self.mock_device.adb.install.return_value = b''
    apk_utils.install(self.mock_device, APK_PATH)
    self.mock_device.reboot.assert_not_called()
    self.mock_device.adb.install.assert_called_once_with(
        ['-r', '-t', APK_PATH],
        timeout=DEFAULT_INSTALL_TIMEOUT_SEC,
        stderr=mock.ANY,
    )

  def test_install_adb_raise_error_retry_also_fail(self):
    self.mock_device.adb.install.side_effect = adb.AdbError(
        cmd='adb install -s xxx',
        stdout='aaa',
        stderr='[INSTALL_FAILED_INSUFFICIENT_STORAGE]',
        ret_code=1,
    )
    with self.assertRaisesRegex(
        adb.AdbError,
        r'Error executing adb cmd "adb install -s xxx".'
        r' ret: 1, stdout: aaa, stderr:'
        r' \[INSTALL_FAILED_INSUFFICIENT_STORAGE\]',
    ):
      apk_utils.install(self.mock_device, APK_PATH)
    self.mock_device.reboot.assert_called_once_with()
    expected_call = mock.call(
        ['-r', '-t', APK_PATH],
        timeout=DEFAULT_INSTALL_TIMEOUT_SEC,
        stderr=mock.ANY,
    )
    self.mock_device.adb.install.assert_has_calls(
        [expected_call, expected_call]
    )

  def test_install_adb_fail_by_stdout_error_retry_also_fail(self):
    self.mock_device.adb.install.return_value = (
        b'Failure [INSTALL_FAILED_INSUFFICIENT_STORAGE]'
    )
    with self.assertRaisesRegex(
        adb.AdbError,
        r'^Error executing adb cmd "adb -s .* some/apk/path". ret: 0, '
        r'stdout: .*Failure \[INSTALL_FAILED_INSUFFICIENT_STORAGE\].*, '
        r'stderr: $',
    ):
      apk_utils.install(self.mock_device, APK_PATH)
    self.mock_device.reboot.assert_called_once_with()
    expected_call = mock.call(
        ['-r', '-t', APK_PATH],
        timeout=DEFAULT_INSTALL_TIMEOUT_SEC,
        stderr=mock.ANY,
    )
    self.mock_device.adb.install.assert_has_calls(
        [expected_call, expected_call]
    )

  def test_install_adb_raise_error_retry_pass(self):
    error = adb.AdbError(
        cmd='adb install -s xxx',
        stdout='aaa',
        stderr='[INSTALL_FAILED_INSUFFICIENT_STORAGE]',
        ret_code=1,
    )
    self.mock_device.adb.install.side_effect = [error, b'Success!']
    apk_utils.install(self.mock_device, APK_PATH)
    self.mock_device.reboot.assert_called_once_with()
    expected_call = mock.call(
        ['-r', '-t', APK_PATH],
        timeout=DEFAULT_INSTALL_TIMEOUT_SEC,
        stderr=mock.ANY,
    )
    self.mock_device.adb.install.assert_has_calls(
        [expected_call, expected_call]
    )

  def test_install_adb_fail_without_raise_retry_pass(self):
    self.mock_device.adb.install.side_effect = [
        b'Failure [INSTALL_FAILED_INSUFFICIENT_STORAGE]',
        b'Success!',
    ]
    apk_utils.install(self.mock_device, APK_PATH)
    self.mock_device.reboot.assert_called_once_with()
    expected_call = mock.call(
        ['-r', '-t', APK_PATH],
        timeout=DEFAULT_INSTALL_TIMEOUT_SEC,
        stderr=mock.ANY,
    )
    self.mock_device.adb.install.assert_has_calls(
        [expected_call, expected_call]
    )

  def test_uninstall_internal_error_no_retry(self):
    mock_apk_package = 'some.apk.package'
    self.mock_device.adb.shell.return_value = (
        b'package:some.apk.package\npackage:some.other.package\n'
    )
    self.mock_device.adb.uninstall.side_effect = [
        adb.AdbError(cmd=['uninstall'], stdout='', stderr='meh', ret_code=1),
        Exception('This should never be raised.'),
    ]
    with self.assertRaisesRegex(
        adb.AdbError, 'Error executing adb cmd "uninstall"'
    ):
      apk_utils.uninstall(self.mock_device, mock_apk_package)

  def test_uninstall_internal_error_retry_also_fail(self):
    mock_apk_package = 'some.apk.package'
    self.mock_device.adb.shell.side_effect = [
        b'package:some.apk.package\npackage:some.other.package\n',
        adb.AdbError(
            cmd=['pm', 'uninstall', '--pid', '0'],
            stdout='',
            stderr='',
            ret_code=1,
        ),
    ]
    self.mock_device.adb.uninstall.side_effect = adb.AdbError(
        cmd=['uninstall'],
        stdout=apk_utils.ADB_UNINSTALL_INTERNAL_ERROR_MSG,
        stderr='meh',
        ret_code=1,
    )
    with self.assertRaisesRegex(
        adb.AdbError, 'Error executing adb cmd "uninstall"'
    ):
      apk_utils.uninstall(self.mock_device, mock_apk_package)

  def test_apk_is_installed(self):
    self.mock_device.adb.shell.return_value = (
        b'package:some.apk.package\npackage:some.other.package\n'
    )
    self.assertTrue(
        apk_utils.is_apk_installed(self.mock_device, 'some.apk.package')
    )

  def test_apk_is_not_installed(self):
    self.mock_device.adb.shell.return_value = (
        b'package:some.apk.package\npackage:some.other.package\n'
    )
    self.assertFalse(
        apk_utils.is_apk_installed(self.mock_device, 'unknown.apk.package')
    )

  def test_apk_is_installed_error(self):
    self.mock_device.adb.shell.side_effect = adb.AdbError('pm', '', 'error', 1)
    with self.assertRaisesRegex(errors.DeviceError, 'Error executing adb cmd'):
      apk_utils.is_apk_installed(self.mock_device, 'some.apk.package')

  def create_mock_system_install_device(self, api_level, code_name='REL'):
    """Create a mock device with a particular API level.

    Args:
      api_level: A string reflecting the value of the ro.build.version.sdk
        property.
      code_name: The codename of the device's build, defaults to 'REL'

    Returns:
      A mock object for the AndroidDevice.
    """
    self.mock_device.build_info = {
        'build_version_sdk': bytearray(api_level, 'utf8'),
        'build_version_codename': code_name,
    }
    return self.mock_device

  def mock_apk_metadata(self):
    """Returns a mock metadata object."""
    mock_apk_metadata = mock.MagicMock()
    mock_apk_metadata.package_name = 'mock.package.name'
    return mock_apk_metadata


if __name__ == '__main__':
  unittest.main()
