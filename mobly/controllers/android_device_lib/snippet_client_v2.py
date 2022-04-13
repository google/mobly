# Copyright 2022 Google Inc.
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
"""Snippet Client V2 for Interacting with Snippet Server on Android Device."""

import re

from mobly import utils
from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import (errors as
                                                  android_device_lib_errors)
from mobly.snippet import client_base
from mobly.snippet import errors

# The package of the instrumentation runner used for mobly snippet
_INSTRUMENTATION_RUNNER_PACKAGE = (
    'com.google.android.mobly.snippet.SnippetRunner')

# The command template to start the snippet server
_LAUNCH_CMD = (
    '{shell_cmd} am instrument {user} -w -e action start {snippet_package}/' +
    _INSTRUMENTATION_RUNNER_PACKAGE)

# The command template to stop the snippet server
_STOP_CMD = ('am instrument {user} -w -e action stop {snippet_package}/' +
             _INSTRUMENTATION_RUNNER_PACKAGE)

# Major version of the launch and communication protocol being used by this
# client.
# Incrementing this means that compatibility with clients using the older
# version is broken. Avoid breaking compatibility unless there is no other
# choice.
_PROTOCOL_MAJOR_VERSION = 1

# Minor version of the launch and communication protocol.
# Increment this when new features are added to the launch and communication
# protocol that are backwards compatible with the old protocol and don't break
# existing clients.
_PROTOCOL_MINOR_VERSION = 0

# Test that uses UiAutomation requires the shell session to be maintained while
# test is in progress. However, this requirement does not hold for the test that
# deals with device disconnection (Once device disconnects, the shell session
# that started the instrument ends, and UiAutomation fails with error:
# "UiAutomation not connected"). To keep the shell session and redirect
# stdin/stdout/stderr, use "setsid" or "nohup" while launching the
# instrumentation test. Because these commands may not be available in every
# Android system, try to use it only if at least one exists.
_SETSID_COMMAND = 'setsid'

_NOHUP_COMMAND = 'nohup'


class SnippetClientV2(client_base.ClientBase):
  """Snippet client V2 for interacting with snippet server on Android Device.

  See base class documentation for a list of public attributes and communication
  protocols.

  For a description of the launch protocols, see the documentation in
  mobly-snippet-lib, SnippetRunner.java.
  """

  def __init__(self, package, ad):
    """Initializes the instance of Snippet Client V2.

    Args:
      package: str, see base class.
      ad: AndroidDevice, the android device object associated with this client.
    """
    super().__init__(package=package, device=ad)
    self._adb = ad.adb
    self._user_id = None
    self._proc = None

  @property
  def user_id(self):
    """The user id to use for this snippet client.

    All the operations of the snippet client should be used for a particular
    user. For more details, see the Android documentation of testing
    multiple users.

    Thus this value is cached and, once set, does not change through the
    lifecycles of this snippet client object. This caching also reduces the
    number of adb calls needed.

    Returns:
      An integer of the user id.
    """
    if self._user_id is None:
      self._user_id = self._adb.current_user_id
    return self._user_id

  def before_starting_server(self):
    """See base class.

    This function performs following preparation steps:
    * Check that the Mobly Snippet app is installed on the remote device.
    * Disable hidden api blocklist if necessary and possible.

    Raises:
      errors.ServerStartPreCheckError: if the server app is not installed
        for the current user.
    """
    self._check_snippet_app_installed()
    self._disable_hidden_api_blocklist()

  def _check_snippet_app_installed(self):
    """Checks that the Mobly Snippet app is installed on the remote device.

    Raises:
      errors.ServerStartPreCheckError: if the server app is not installed
        for the current user.
    """
    out = self._adb.shell(f'pm list package --user {self.user_id}')
    if not utils.grep(f'^package:{self.package}$', out):
      raise errors.ServerStartPreCheckError(
          self._device,
          f'{self.package} is not installed for user {self.user_id}.')

    # Check that the app is instrumented.
    out = self._adb.shell('pm list instrumentation')
    matched_out = utils.grep(
        f'^instrumentation:{self.package}/{_INSTRUMENTATION_RUNNER_PACKAGE}',
        out)
    if not matched_out:
      raise errors.ServerStartPreCheckError(
          self._device,
          f'{self.package} is installed, but it is not instrumented.')

    # Check that the instrumentation target is installed if it's not the
    # same as the snippet package.
    match = re.search(r'^instrumentation:(.*)\/(.*) \(target=(.*)\)$',
                      matched_out[0])
    target_name = match.group(3)
    if target_name != self.package:
      out = self._adb.shell(f'pm list package --user {self.user_id}')
      if not utils.grep(f'^package:{target_name}$', out):
        raise errors.ServerStartPreCheckError(
            self._device,
            f'Instrumentation target {target_name} is not installed for user '
            f'{self.user_id}.')

  def _disable_hidden_api_blocklist(self):
    """If necessary and possible, disables hidden api blocklist."""
    version_codename = self._device.build_info['build_version_codename']
    sdk_version = int(self._device.build_info['build_version_sdk'])
    # Check version_codename in addition to sdk_version because Android P builds
    # in development report sdk_version 27, but still enforce the blocklist.
    if self._device.is_rootable and (sdk_version >= 28 or
                                     version_codename == 'P'):
      self._device.adb.shell(
          'settings put global hidden_api_blacklist_exemptions "*"')

  def start_server(self):
    """Starts the server on the remote device.

    This function starts the snippet server with adb command, checks the
    protocol version of the server, parses device port from the server
    output and sets it to self.device_port.

    Raises:
      errors.ServerStartProtocolError: if the protocol reported by the server
        startup process is unknown.
      errors.ServerStartError: if failed to start the server or process the
        server output.
    """
    persists_shell_cmd = self._get_persisting_command()
    self.log.debug('Snippet server for package %s is using protocol %d.%d',
                   self.package, _PROTOCOL_MAJOR_VERSION,
                   _PROTOCOL_MINOR_VERSION)
    cmd = _LAUNCH_CMD.format(shell_cmd=persists_shell_cmd,
                             user=self._get_user_command_string(),
                             snippet_package=self.package)
    self._proc = self._run_adb_cmd(cmd)

    # Check protocol version and get the device port
    line = self._read_protocol_line()
    match = re.match('^SNIPPET START, PROTOCOL ([0-9]+) ([0-9]+)$', line)
    if not match or int(match.group(1)) != _PROTOCOL_MAJOR_VERSION:
      raise errors.ServerStartProtocolError(self._device, line)

    line = self._read_protocol_line()
    match = re.match('^SNIPPET SERVING, PORT ([0-9]+)$', line)
    if not match:
      raise errors.ServerStartProtocolError(self._device, line)
    self.device_port = int(match.group(1))

  def _run_adb_cmd(self, cmd):
    """Starts a long-running adb subprocess and returns it immediately."""
    adb_cmd = [adb.ADB]
    if self._adb.serial:
      adb_cmd += ['-s', self._adb.serial]
    adb_cmd += ['shell', cmd]
    return utils.start_standing_subprocess(adb_cmd, shell=False)

  def _get_persisting_command(self):
    """Returns the path of a persisting command if available."""
    for command in [_SETSID_COMMAND, _NOHUP_COMMAND]:
      try:
        if command in self._adb.shell(['which', command]).decode('utf-8'):
          return command
      except adb.AdbError:
        continue

    self.log.warning(
        'No %s and %s commands available to launch instrument '
        'persistently, tests that depend on UiAutomator and '
        'at the same time perform USB disconnections may fail.',
        _SETSID_COMMAND, _NOHUP_COMMAND)
    return ''

  def _get_user_command_string(self):
    """Gets the appropriate command argument for specifying device user ID.

    By default, this client operates within the current user. We
    don't add the `--user {ID}` argument when Android's SDK is below 24,
    where multi-user support is not well implemented.

    Returns:
      A string of the command argument section to be formatted into
      adb commands.
    """
    sdk_version = int(self._device.build_info['build_version_sdk'])
    if sdk_version < 24:
      return ''
    return f'--user {self.user_id}'

  def _read_protocol_line(self):
    """Reads the next line of instrumentation output relevant to snippets.

    This method will skip over lines that don't start with 'SNIPPET ' or
    'INSTRUMENTATION_RESULT:'.

    Returns:
      A string for the next line of snippet-related instrumentation output,
        stripped.

    Raises:
      errors.ServerStartError: If EOF is reached without any protocol lines
        being read.
    """
    while True:
      line = self._proc.stdout.readline().decode('utf-8')
      if not line:
        raise errors.ServerStartError(
            self._device, 'Unexpected EOF when waiting for server to start.')

      # readline() uses an empty string to mark EOF, and a single newline
      # to mark regular empty lines in the output. Don't move the strip()
      # call above the truthiness check, or this method will start
      # considering any blank output line to be EOF.
      line = line.strip()
      if (line.startswith('INSTRUMENTATION_RESULT:') or
          line.startswith('SNIPPET ')):
        self.log.debug('Accepted line from instrumentation output: "%s"', line)
        return line

      self.log.debug('Discarded line from instrumentation output: "%s"', line)

  def stop(self):
    """See base class."""
    # TODO(mhaoli): This function is only partially implemented because we
    # have not implemented the functionality of making connections in this
    # class.
    self.log.debug('Stopping snippet package %s.', self.package)
    self._stop_server()
    self.log.debug('Snippet package %s stopped.', self.package)

  def _stop_server(self):
    """Releases all the resources acquired in `start_server`.

    Raises:
      android_device_lib_errors.DeviceError: if the server exited with errors on
        the device side.
    """
    # Although killing the snippet server would abort this subprocess anyway, we
    # want to call stop_standing_subprocess() to perform a health check,
    # print the failure stack trace if there was any, and reap it from the
    # process table. Note that it's much more important to ensure releasing all
    # the allocated resources on the host side than on the remote device side.

    # Stop the standing server subprocess, which is running on the host side.
    if self._proc:
      utils.stop_standing_subprocess(self._proc)
      self._proc = None

    # Send the stop signal to the server, which is running on the device side.
    out = self._adb.shell(
        _STOP_CMD.format(snippet_package=self.package,
                         user=self._get_user_command_string())).decode('utf-8')

    if 'OK (0 tests)' not in out:
      raise android_device_lib_errors.DeviceError(
          self._device,
          f'Failed to stop existing apk. Unexpected output: {out}.')

  # TODO(mhaoli): Temporally override these abstract methods so that we can
  # initialize the instances in unit tests. We are implementing these functions
  # in the next PR as soon as possible.
  def make_connection(self):
    raise NotImplementedError('To be implemented.')

  def close_connection(self):
    raise NotImplementedError('To be implemented.')

  def __del__(self):
    # Override the destructor to not call close_connection for now.
    pass

  def send_rpc_request(self, request):
    raise NotImplementedError('To be implemented.')

  def check_server_proc_running(self):
    raise NotImplementedError('To be implemented.')

  def handle_callback(self, callback_id, ret_value, rpc_func_name):
    raise NotImplementedError('To be implemented.')

  def restore_server_connection(self, port=None):
    raise NotImplementedError('To be implemented.')
