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

import unittest
from unittest import mock
import socket
import contextlib
import json

from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import errors as android_device_lib_errors
from mobly.controllers.android_device_lib import snippet_client_v2
from mobly.controllers.android_device_lib import jsonrpc_client_base
from mobly.snippet import errors
from tests.lib import mock_android_device

MOCK_PACKAGE_NAME = 'some.package.name'
MOCK_SERVER_PATH = (f'{MOCK_PACKAGE_NAME}/'
                    f'{snippet_client_v2._INSTRUMENTATION_RUNNER_PACKAGE}')
MOCK_USER_ID = 0


def _get_mock_android_device(package_name=None,
                             snippet_runner=None,
                             adb_proxy=None,
                             mock_user_id=0):
  """Mock Android Device Controller used for testing snippet client."""
  return ad


class FakeClient(snippet_client_v2.SnippetClientV2):

  # TODO(mhaoli): These functions are temporally overridden and will be
  # deleted once the implementation of SnippetClientV2 finishes.
  def build_connection(self):
    pass

  def close_connection(self):
    pass

  def send_rpc_request(self, request):
    pass

  def check_server_proc_running(self):
    pass

  def handle_callback(self, callback_id, ret_value, rpc_func_name):
    pass

  def restore_server_connection(self, port=None):
    pass


class SnippetClientV2Test(unittest.TestCase):
  """Unit tests for SnippetClientV2."""

  def setUp(self):
    super().setUp()
    adb_proxy = mock_android_device.MockAdbProxy(
        instrumented_packages=[(
            MOCK_PACKAGE_NAME,
            snippet_client_v2._INSTRUMENTATION_RUNNER_PACKAGE,
            MOCK_PACKAGE_NAME)])

    ad = mock.Mock()
    ad.adb = adb_proxy
    ad.adb.current_user_id = MOCK_USER_ID
    ad.build_info = {
        'build_version_codename': ad.adb.getprop('ro.build.version.codename'),
        'build_version_sdk': ad.adb.getprop('ro.build.version.sdk'),
    }

    self.client = FakeClient(MOCK_PACKAGE_NAME, ad)

  def _set_adb_to_client(self, adb):
    self.client._adb = adb
    self.client._device.adb = adb
    self.client._device.build_info = {
        'build_version_codename': adb.getprop('ro.build.version.codename'),
        'build_version_sdk': adb.getprop('ro.build.version.sdk'),
    }

  def _mock_adb_with_extra_properties(self, extra_properties=None):
    mock_properties = mock_android_device.DEFAULT_MOCK_PROPERTIES.copy()
    if extra_properties:
      mock_properties.update(extra_properties)
    self._set_adb_to_client(
        mock_android_device.MockAdbProxy(mock_properties=mock_properties))

  def _mock_server_process_starting_response(self, mock_start_subprocess,
                                             resp_lines):
    mock_proc = mock_start_subprocess.return_value
    mock_proc.stdout.readline.side_effect = resp_lines

  def test_check_app_installed_normal(self):
    self.client._check_snippet_app_installed()

  def test_check_app_installed_fail_app_not_installed(self):
    self._set_adb_to_client(mock_android_device.MockAdbProxy())
    expected_msg = f'.* {MOCK_PACKAGE_NAME} is not installed.'
    with self.assertRaisesRegex(errors.ServerStartPreCheckError, expected_msg):
      self.client._check_snippet_app_installed()

  def test_check_app_installed_fail_not_instrumented(self):
    self._set_adb_to_client(
        mock_android_device.MockAdbProxy(
            installed_packages=[MOCK_PACKAGE_NAME]))
    expected_msg = (
        f'.* {MOCK_PACKAGE_NAME} is installed, but it is not instrumented.')
    with self.assertRaisesRegex(errors.ServerStartPreCheckError, expected_msg):
      self.client._check_snippet_app_installed()

  def test_check_app_installed_fail_target_not_installed(self):
    self._set_adb_to_client(
        mock_android_device.MockAdbProxy(instrumented_packages=[(
            MOCK_PACKAGE_NAME,
            snippet_client_v2._INSTRUMENTATION_RUNNER_PACKAGE,
            'not.installed')]))
    expected_msg = (
        f'.* Instrumentation target not.installed is not installed.'
    )
    with self.assertRaisesRegex(errors.ServerStartPreCheckError, expected_msg):
      self.client._check_snippet_app_installed()

  @mock.patch.object(mock_android_device.MockAdbProxy, 'shell')
  def test_disable_hidden_api_normal(self, mock_shell_func):
    self._mock_adb_with_extra_properties({
        'ro.build.version.codename': 'S',
        'ro.build.version.sdk': '31',
    })
    self.client._device.is_rootable = True
    self.client._disable_hidden_api_blacklist()
    mock_shell_func.assert_called_with(
        'settings put global hidden_api_blacklist_exemptions "*"')

  @mock.patch.object(mock_android_device.MockAdbProxy, 'shell')
  def test_disable_hidden_api_low_sdk(self, mock_shell_func):
    self._mock_adb_with_extra_properties({
        'ro.build.version.codename': 'O',
        'ro.build.version.sdk': '26',
    })
    self.client._device.is_rootable = True
    self.client._disable_hidden_api_blacklist()
    mock_shell_func.assert_not_called()

  @mock.patch.object(mock_android_device.MockAdbProxy, 'shell')
  def test_disable_hidden_api_low_sdk_with_android_P(self, mock_shell_func):
    self._mock_adb_with_extra_properties({
        'ro.build.version.codename': 'P',
        'ro.build.version.sdk': '27',
    })
    self.client._device.is_rootable = True
    self.client._disable_hidden_api_blacklist()
    mock_shell_func.assert_called_with(
        'settings put global hidden_api_blacklist_exemptions "*"')

  @mock.patch.object(mock_android_device.MockAdbProxy, 'shell')
  def test_disable_hidden_api_non_rootable(self, mock_shell_func):
    self._mock_adb_with_extra_properties({
        'ro.build.version.codename': 'S',
        'ro.build.version.sdk': '31',
    })
    self.client._device.is_rootable = False
    self.client._disable_hidden_api_blacklist()
    mock_shell_func.assert_not_called()

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  @mock.patch.object(
      mock_android_device.MockAdbProxy, 'shell', return_value=b'setsid')
  def test_do_start_server_with_user_id(self, mock_adb, mock_start_subprocess):
    """Checks that `--user` is added to starting command on SDK < 24."""
    self.client._device.build_info['build_version_sdk'] = 30
    self._mock_server_process_starting_response(
        mock_start_subprocess,
        resp_lines=[
            b'SNIPPET START, PROTOCOL 1 234', b'SNIPPET SERVING, PORT 1234'
        ])

    self.client.do_start_server()
    # Notes that --user should be added to the commandif SDK >= 24
    start_cmd_list = [
        'adb', 'shell',
        (f'setsid am instrument --user {MOCK_USER_ID} -w -e action start '
         f'{MOCK_PACKAGE_NAME}/'
         f'{snippet_client_v2._INSTRUMENTATION_RUNNER_PACKAGE}')
    ]
    self.assertListEqual(mock_start_subprocess.call_args_list,
                         [mock.call(start_cmd_list, shell=False)])
    self.assertEqual(self.client.device_port, 1234)
    mock_adb.assert_called_with(['which', 'setsid'])

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  @mock.patch.object(
      mock_android_device.MockAdbProxy, 'shell', return_value=b'setsid')
  def test_do_start_server_without_user_id(self, mock_adb,
                                           mock_start_subprocess):
    """Checks that `--user` is added to starting command on SDK < 24."""
    self.client._device.build_info['build_version_sdk'] = 21
    self._mock_server_process_starting_response(
        mock_start_subprocess,
        resp_lines=[
            b'SNIPPET START, PROTOCOL 1 234', b'SNIPPET SERVING, PORT 1234'
        ])

    self.client.do_start_server()
    # Notes that --user is not be added to the command if SDK >= 24
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
  @mock.patch.object(
      mock_android_device.MockAdbProxy,
      'shell',
      side_effect=adb.AdbError('cmd', 'stdout', 'stderr', 'ret_code'))
  def test_do_start_server_without_persistence(self, mock_adb,
                                               mock_start_subprocess):
    """Checks that if device does not support persistant commands."""
    self._mock_server_process_starting_response(
        mock_start_subprocess,
        resp_lines=[
            b'SNIPPET START, PROTOCOL 1 234', b'SNIPPET SERVING, PORT 1234'
        ])

    self.client.do_start_server()
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
  def test_do_start_server_with_nohup(self, mock_start_subprocess):
    """Checks that if device only supports nohup command for persistence."""
    self._mock_server_process_starting_response(
        mock_start_subprocess,
        resp_lines=[
            b'SNIPPET START, PROTOCOL 1 234', b'SNIPPET SERVING, PORT 1234'
        ])

    def _mocked_shell(arg):
      if 'setsid' in arg:
        raise adb.AdbError('cmd', 'stdout', 'stderr', 'ret_code')
      else:
        return b'nohup'

    self.client._adb.shell = _mocked_shell

    self.client.do_start_server()
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
  def test_do_start_server_with_setsid(self, mock_start_subprocess):
    """Checks that if device only supports setsid command for persistence."""
    self._mock_server_process_starting_response(
        mock_start_subprocess,
        resp_lines=[
            b'SNIPPET START, PROTOCOL 1 234', b'SNIPPET SERVING, PORT 1234'
        ])

    def _mocked_shell(arg):
      if 'setsid' in arg:
        return b'setsid'
      else:
        raise adb.AdbError('cmd', 'stdout', 'stderr', 'ret_code')

    self.client._adb.shell = _mocked_shell

    self.client.do_start_server()
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
  def test_do_start_server_server_crash(self, mock_start_standing_subprocess):
    self._mock_server_process_starting_response(
        mock_start_standing_subprocess,
        resp_lines=[b'INSTRUMENTATION_RESULT: shortMsg=Process crashed.\n'])
    with self.assertRaisesRegex(
        errors.ServerStartProtocolError,
        'INSTRUMENTATION_RESULT: shortMsg=Process crashed.'):
      self.client.do_start_server()

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_do_start_server_unknown_protocol(self,
                                            mock_start_standing_subprocess):
    self._mock_server_process_starting_response(
        mock_start_standing_subprocess,
        resp_lines=[b'SNIPPET START, PROTOCOL 99 0\n'])
    with self.assertRaisesRegex(errors.ServerStartProtocolError,
                                'SNIPPET START, PROTOCOL 99 0'):
      self.client.do_start_server()

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_do_start_server_header_junk(self, mock_start_standing_subprocess):
    self._mock_server_process_starting_response(
        mock_start_standing_subprocess,
        resp_lines=[
            b'This is some header junk\n',
            b'Some phones print arbitrary output\n',
            b'SNIPPET START, PROTOCOL 1 0\n',
            b'Maybe in the middle too\n',
            b'SNIPPET SERVING, PORT 123\n',
        ])
    self.client.do_start_server()
    self.assertEqual(123, self.client.device_port)

  @mock.patch('mobly.controllers.android_device_lib.snippet_client_v2.'
              'utils.start_standing_subprocess')
  def test_do_start_server_no_valid_line(self, mock_start_standing_subprocess):
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
      self.client.do_start_server()

  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(
      mock_android_device.MockAdbProxy, 'shell', return_value=b'OK (0 tests)')
  def test_stop_server_normal(self, mock_android_device,
                              mock_stop_standing_subprocess):
    mock_proc = mock.Mock()
    self.client._proc = mock_proc
    self.client.do_stop_server()
    self.assertIs(self.client._proc, None)
    mock_android_device.assert_called_once_with(
        f'am instrument --user {MOCK_USER_ID} -w -e action stop '
        f'{MOCK_SERVER_PATH}')
    mock_stop_standing_subprocess.assert_called_once_with(mock_proc)

  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(
      mock_android_device.MockAdbProxy, 'shell', return_value=b'OK (0 tests)')
  def test_stop_server_server_already_cleaned(self, mock_android_device,
                                              mock_stop_standing_subprocess):
    self.client._proc = None
    self.client.do_stop_server()
    self.assertIs(self.client._proc, None)
    mock_stop_standing_subprocess.assert_not_called()
    mock_android_device.assert_called_once_with(
        f'am instrument --user {MOCK_USER_ID} -w -e action stop '
        f'{MOCK_SERVER_PATH}')

  @mock.patch('mobly.utils.stop_standing_subprocess')
  @mock.patch.object(
      mock_android_device.MockAdbProxy,
      'shell',
      return_value=b'Closed with error.')
  def test_stop_server_server_already_cleaned(self, mock_android_device,
                                              mock_stop_standing_subprocess):
    mock_proc = mock.Mock()
    self.client._proc = mock_proc
    with self.assertRaisesRegex(android_device_lib_errors.DeviceError,
                                'Closed with error'):
      self.client.do_stop_server()

    self.assertIs(self.client._proc, None)
    mock_stop_standing_subprocess.assert_called_once_with(mock_proc)
    mock_android_device.assert_called_once_with(
        f'am instrument --user {MOCK_USER_ID} -w -e action stop '
        f'{MOCK_SERVER_PATH}')


if __name__ == '__main__':
  unittest.main()
