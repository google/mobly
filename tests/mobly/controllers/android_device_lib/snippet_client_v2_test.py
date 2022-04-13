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
"""Unit tests for mobly.controllers.android_device_lib.snippet_client_v2."""

import unittest
from unittest import mock

from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import (errors as
                                                  android_device_lib_errors)
from mobly.controllers.android_device_lib import snippet_client_v2
from mobly.snippet import errors
from tests.lib import mock_android_device

MOCK_PACKAGE_NAME = 'some.package.name'
MOCK_SERVER_PATH = (f'{MOCK_PACKAGE_NAME}/'
                    f'{snippet_client_v2._INSTRUMENTATION_RUNNER_PACKAGE}')
MOCK_USER_ID = 0


class SnippetClientV2Test(unittest.TestCase):
  """Unit tests for SnippetClientV2."""

  def _make_client(self, adb_proxy=None, mock_properties=None):
    adb_proxy = adb_proxy or mock_android_device.MockAdbProxy(
        instrumented_packages=[
            (MOCK_PACKAGE_NAME,
             snippet_client_v2._INSTRUMENTATION_RUNNER_PACKAGE,
             MOCK_PACKAGE_NAME)
        ],
        mock_properties=mock_properties)

    device = mock.Mock()
    device.adb = adb_proxy
    device.adb.current_user_id = MOCK_USER_ID
    device.build_info = {
        'build_version_codename':
            adb_proxy.getprop('ro.build.version.codename'),
        'build_version_sdk':
            adb_proxy.getprop('ro.build.version.sdk'),
    }

    self.client = snippet_client_v2.SnippetClientV2(MOCK_PACKAGE_NAME, device)

  def _make_client_with_extra_adb_properties(self, extra_properties):
    mock_properties = mock_android_device.DEFAULT_MOCK_PROPERTIES.copy()
    mock_properties.update(extra_properties)
    self._make_client(mock_properties=mock_properties)

  def _mock_server_process_starting_response(self, mock_start_subprocess,
                                             resp_lines):
    mock_proc = mock_start_subprocess.return_value
    mock_proc.stdout.readline.side_effect = resp_lines

  def test_check_app_installed_normally(self):
    """Tests that app checker runs normally when app installed correctly."""
    self._make_client()
    self.client._check_snippet_app_installed()

  def test_check_app_installed_fail_app_not_installed(self):
    """Tests that app checker fails without installing app."""
    self._make_client(mock_android_device.MockAdbProxy())
    expected_msg = f'.* {MOCK_PACKAGE_NAME} is not installed.'
    with self.assertRaisesRegex(errors.ServerStartPreCheckError, expected_msg):
      self.client._check_snippet_app_installed()

  def test_check_app_installed_fail_not_instrumented(self):
    """Tests that app checker fails without instrumenting app."""
    self._make_client(
        mock_android_device.MockAdbProxy(
            installed_packages=[MOCK_PACKAGE_NAME]))
    expected_msg = (
        f'.* {MOCK_PACKAGE_NAME} is installed, but it is not instrumented.')
    with self.assertRaisesRegex(errors.ServerStartPreCheckError, expected_msg):
      self.client._check_snippet_app_installed()

  def test_check_app_installed_fail_instrumentation_not_installed(self):
    """Tests that app checker fails without installing instrumentation."""
    self._make_client(
        mock_android_device.MockAdbProxy(instrumented_packages=[(
            MOCK_PACKAGE_NAME,
            snippet_client_v2._INSTRUMENTATION_RUNNER_PACKAGE,
            'not.installed')]))
    expected_msg = ('.* Instrumentation target not.installed is not installed.')
    with self.assertRaisesRegex(errors.ServerStartPreCheckError, expected_msg):
      self.client._check_snippet_app_installed()

  @mock.patch.object(mock_android_device.MockAdbProxy, 'shell')
  def test_disable_hidden_api_normally(self, mock_shell_func):
    """Tests the disabling hidden api process works normally."""
    self._make_client_with_extra_adb_properties({
        'ro.build.version.codename': 'S',
        'ro.build.version.sdk': '31',
    })
    self.client._device.is_rootable = True
    self.client._disable_hidden_api_blocklist()
    mock_shell_func.assert_called_with(
        'settings put global hidden_api_blacklist_exemptions "*"')

  @mock.patch.object(mock_android_device.MockAdbProxy, 'shell')
  def test_disable_hidden_api_low_sdk(self, mock_shell_func):
    """Tests it doesn't disable hidden api with low SDK."""
    self._make_client_with_extra_adb_properties({
        'ro.build.version.codename': 'O',
        'ro.build.version.sdk': '26',
    })
    self.client._device.is_rootable = True
    self.client._disable_hidden_api_blocklist()
    mock_shell_func.assert_not_called()

  @mock.patch.object(mock_android_device.MockAdbProxy, 'shell')
  def test_disable_hidden_api_sdk_27_and_android_p(self, mock_shell_func):
    """Tests it disables hidden api with SDK version 27 and Android P."""
    self._make_client_with_extra_adb_properties({
        'ro.build.version.codename': 'P',
        'ro.build.version.sdk': '27',
    })
    self.client._device.is_rootable = True
    self.client._disable_hidden_api_blocklist()
    mock_shell_func.assert_called_with(
        'settings put global hidden_api_blacklist_exemptions "*"')

  @mock.patch.object(mock_android_device.MockAdbProxy, 'shell')
  def test_disable_hidden_api_non_rootable(self, mock_shell_func):
    """Tests it doesn't disable hidden api with non-rootable device."""
    self._make_client_with_extra_adb_properties({
        'ro.build.version.codename': 'S',
        'ro.build.version.sdk': '31',
    })
    self.client._device.is_rootable = False
    self.client._disable_hidden_api_blocklist()
    mock_shell_func.assert_not_called()

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  @mock.patch.object(mock_android_device.MockAdbProxy,
                     'shell',
                     return_value=b'setsid')
  def test_start_server_with_user_id(self, mock_adb, mock_start_subprocess):
    """Tests that `--user` is added to starting command with SDK >= 24."""
    self._make_client_with_extra_adb_properties({'ro.build.version.sdk': '30'})
    self._mock_server_process_starting_response(
        mock_start_subprocess,
        resp_lines=[
            b'SNIPPET START, PROTOCOL 1 234', b'SNIPPET SERVING, PORT 1234'
        ])

    self.client.start_server()
    start_cmd_list = [
        'adb', 'shell',
        (f'setsid am instrument --user {MOCK_USER_ID} -w -e action start '
         f'{MOCK_SERVER_PATH}')
    ]
    self.assertListEqual(mock_start_subprocess.call_args_list,
                         [mock.call(start_cmd_list, shell=False)])
    self.assertEqual(self.client.device_port, 1234)
    mock_adb.assert_called_with(['which', 'setsid'])

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  @mock.patch.object(mock_android_device.MockAdbProxy,
                     'shell',
                     return_value=b'setsid')
  def test_start_server_without_user_id(self, mock_adb, mock_start_subprocess):
    """Tests that `--user` is not added to starting command on SDK < 24."""
    self._make_client_with_extra_adb_properties({'ro.build.version.sdk': '21'})
    self._mock_server_process_starting_response(
        mock_start_subprocess,
        resp_lines=[
            b'SNIPPET START, PROTOCOL 1 234', b'SNIPPET SERVING, PORT 1234'
        ])

    self.client.start_server()
    start_cmd_list = [
        'adb', 'shell',
        f'setsid am instrument  -w -e action start {MOCK_SERVER_PATH}'
    ]
    self.assertListEqual(mock_start_subprocess.call_args_list,
                         [mock.call(start_cmd_list, shell=False)])
    mock_adb.assert_called_with(['which', 'setsid'])
    self.assertEqual(self.client.device_port, 1234)

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  @mock.patch.object(mock_android_device.MockAdbProxy,
                     'shell',
                     side_effect=adb.AdbError('cmd', 'stdout', 'stderr',
                                              'ret_code'))
  def test_start_server_without_persisting_commands(self, mock_adb,
                                                    mock_start_subprocess):
    """Checks the starting server command without persisting commands."""
    self._make_client()
    self._mock_server_process_starting_response(
        mock_start_subprocess,
        resp_lines=[
            b'SNIPPET START, PROTOCOL 1 234', b'SNIPPET SERVING, PORT 1234'
        ])

    self.client.start_server()
    start_cmd_list = [
        'adb', 'shell',
        (f' am instrument --user {MOCK_USER_ID} -w -e action start '
         f'{MOCK_SERVER_PATH}')
    ]
    self.assertListEqual(mock_start_subprocess.call_args_list,
                         [mock.call(start_cmd_list, shell=False)])
    mock_adb.assert_has_calls(
        [mock.call(['which', 'setsid']),
         mock.call(['which', 'nohup'])])
    self.assertEqual(self.client.device_port, 1234)

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_start_server_with_nohup(self, mock_start_subprocess):
    """Checks the starting server command with nohup."""
    self._make_client()
    self._mock_server_process_starting_response(
        mock_start_subprocess,
        resp_lines=[
            b'SNIPPET START, PROTOCOL 1 234', b'SNIPPET SERVING, PORT 1234'
        ])

    def _mocked_shell(arg):
      if 'nohup' in arg:
        return b'nohup'
      raise adb.AdbError('cmd', 'stdout', 'stderr', 'ret_code')

    self.client._adb.shell = _mocked_shell

    self.client.start_server()
    start_cmd_list = [
        'adb', 'shell',
        (f'nohup am instrument --user {MOCK_USER_ID} -w -e action start '
         f'{MOCK_SERVER_PATH}')
    ]
    self.assertListEqual(mock_start_subprocess.call_args_list,
                         [mock.call(start_cmd_list, shell=False)])
    self.assertEqual(self.client.device_port, 1234)

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_start_server_with_setsid(self, mock_start_subprocess):
    """Checks the starting server command with setsid."""
    self._make_client()
    self._mock_server_process_starting_response(
        mock_start_subprocess,
        resp_lines=[
            b'SNIPPET START, PROTOCOL 1 234', b'SNIPPET SERVING, PORT 1234'
        ])

    def _mocked_shell(arg):
      if 'setsid' in arg:
        return b'setsid'
      raise adb.AdbError('cmd', 'stdout', 'stderr', 'ret_code')

    self.client._adb.shell = _mocked_shell
    self.client.start_server()
    start_cmd_list = [
        'adb', 'shell',
        (f'setsid am instrument --user {MOCK_USER_ID} -w -e action start '
         f'{MOCK_SERVER_PATH}')
    ]
    self.assertListEqual(mock_start_subprocess.call_args_list,
                         [mock.call(start_cmd_list, shell=False)])
    self.assertEqual(self.client.device_port, 1234)

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_start_server_server_crash(self, mock_start_standing_subprocess):
    """Tests that starting server process crashes."""
    self._make_client()
    self._mock_server_process_starting_response(
        mock_start_standing_subprocess,
        resp_lines=[b'INSTRUMENTATION_RESULT: shortMsg=Process crashed.\n'])
    with self.assertRaisesRegex(
        errors.ServerStartProtocolError,
        'INSTRUMENTATION_RESULT: shortMsg=Process crashed.'):
      self.client.start_server()

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_start_server_unknown_protocol_version(
      self, mock_start_standing_subprocess):
    """Tests that starting server process reports unknown protocol version."""
    self._make_client()
    self._mock_server_process_starting_response(
        mock_start_standing_subprocess,
        resp_lines=[b'SNIPPET START, PROTOCOL 99 0\n'])
    with self.assertRaisesRegex(errors.ServerStartProtocolError,
                                'SNIPPET START, PROTOCOL 99 0'):
      self.client.start_server()

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_start_server_invalid_device_port(self,
                                            mock_start_standing_subprocess):
    """Tests that starting server process reports invalid device port."""
    self._make_client()
    self._mock_server_process_starting_response(
        mock_start_standing_subprocess,
        resp_lines=[
            b'SNIPPET START, PROTOCOL 1 0\n', b'SNIPPET SERVING, PORT ABC\n'
        ])
    with self.assertRaisesRegex(errors.ServerStartProtocolError,
                                'SNIPPET SERVING, PORT ABC'):
      self.client.start_server()

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_start_server_with_junk(self, mock_start_standing_subprocess):
    """Tests that starting server process reports known protocol with junk."""
    self._make_client()
    self._mock_server_process_starting_response(
        mock_start_standing_subprocess,
        resp_lines=[
            b'This is some header junk\n',
            b'Some phones print arbitrary output\n',
            b'SNIPPET START, PROTOCOL 1 0\n',
            b'Maybe in the middle too\n',
            b'SNIPPET SERVING, PORT 123\n',
        ])
    self.client.start_server()
    self.assertEqual(123, self.client.device_port)

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_start_server_no_valid_line(self, mock_start_standing_subprocess):
    """Tests that starting server process reports unknown protocol message."""
    self._make_client()
    self._mock_server_process_starting_response(
        mock_start_standing_subprocess,
        resp_lines=[
            b'This is some header junk\n',
            b'Some phones print arbitrary output\n',
            b'',  # readline uses '' to mark EOF
        ])
    with self.assertRaisesRegex(
        errors.ServerStartError,
        'Unexpected EOF when waiting for server to start.'):
      self.client.start_server()

  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(mock_android_device.MockAdbProxy,
                     'shell',
                     return_value=b'OK (0 tests)')
  def test_stop_server_normally(self, mock_android_device_shell,
                                mock_stop_standing_subprocess):
    """Tests that stopping server process works normally."""
    self._make_client()
    mock_proc = mock.Mock()
    self.client._proc = mock_proc
    self.client.stop()
    self.assertIs(self.client._proc, None)
    mock_android_device_shell.assert_called_once_with(
        f'am instrument --user {MOCK_USER_ID} -w -e action stop '
        f'{MOCK_SERVER_PATH}')
    mock_stop_standing_subprocess.assert_called_once_with(mock_proc)

  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(mock_android_device.MockAdbProxy,
                     'shell',
                     return_value=b'OK (0 tests)')
  def test_stop_server_server_already_cleaned(self, mock_android_device_shell,
                                              mock_stop_standing_subprocess):
    """Tests stopping server process when subprocess is already cleaned."""
    self._make_client()
    self.client._proc = None
    self.client.stop()
    self.assertIs(self.client._proc, None)
    mock_stop_standing_subprocess.assert_not_called()
    mock_android_device_shell.assert_called_once_with(
        f'am instrument --user {MOCK_USER_ID} -w -e action stop '
        f'{MOCK_SERVER_PATH}')

  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(mock_android_device.MockAdbProxy,
                     'shell',
                     return_value=b'Closed with error.')
  def test_stop_server_stop_with_error(self, mock_android_device_shell,
                                       mock_stop_standing_subprocess):
    """Tests all resources are cleaned even if stopping server has error."""
    self._make_client()
    mock_proc = mock.Mock()
    self.client._proc = mock_proc
    with self.assertRaisesRegex(android_device_lib_errors.DeviceError,
                                'Closed with error'):
      self.client.stop()

    self.assertIs(self.client._proc, None)
    mock_stop_standing_subprocess.assert_called_once_with(mock_proc)
    mock_android_device_shell.assert_called_once_with(
        f'am instrument --user {MOCK_USER_ID} -w -e action stop '
        f'{MOCK_SERVER_PATH}')


if __name__ == '__main__':
  unittest.main()
