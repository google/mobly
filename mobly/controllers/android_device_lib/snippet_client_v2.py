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

# When the Python library `socket.create_connection` call is made, it indirectly
# calls `import encodings.idna` through the `socket.getaddrinfo` method.
# However, this chain of function calls is apparently not thread-safe in
# embedded Python environments. So, pre-emptively import and cache the encoder.
# See https://bugs.python.org/issue17305 for more details.
try:
  import encodings.idna
except ImportError:
  # Some implementations of Python (e.g. IronPython) do not support the`idna`
  # encoding, so ignore import failures based on that.
  pass

import json
import re
import socket
import time

from mobly import utils
from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import errors as android_device_lib_errors
from mobly.controllers.android_device_lib import callback_handler
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
# Android system, try to use them only if exists.
_SETSID_COMMAND = 'setsid'

_NOHUP_COMMAND = 'nohup'


class SnippetClientV2(client_base.ClientBase):
  """Snippet Client V2 for interacting with snippet server on Android Device.

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

  @property
  def user_id(self):
    """The user id to use for this snippet client.

    All the operations of the snippet client should be used for a particular
    user. For more details, see the Android documentation of testing
    multiple users.

    Thus this value is cached and, once set, does not change through the
    lifecycle of this snippet client object. This caching also reduces the
    number of adb calls needed.

    Returns:
      An integer of the user id.
    """
    if self._user_id is None:
      self._user_id = self._adb.current_user_id
    return self._user_id

  def before_starting_server(self):
    """Prepares for starting the server.

    Raises:
      errors.ServerStartPreCheckError: if the server app is not installed or
        recognized for the current user.
    """
    self._check_snippet_app_installed()
    self._disable_hidden_api_blacklist()

  def _check_snippet_app_installed(self):
    """Checks that the Mobly Snippet app is installed for the current user.

    Raises:
      errors.ServerStartPreCheckError: if the server app is not installed or
        recognized for the current user.
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
    match = re.search(r'^instrumentation:(.*)\/(.*) \(target=(.*)\)$',
                      matched_out[0])

    target_name = match.group(3)

    # Check that the instrumentation target is installed if it's not the
    # same as the snippet package.
    if target_name != self.package:
      out = self._adb.shell(f'pm list package --user {self.user_id}')
      if not utils.grep(f'^package:{target_name}$', out):
        raise errors.ServerStartPreCheckError(
            self._device,
            f'Instrumentation target {target_name} is not installed for user '
            f'{self.user_id}.')

  def _disable_hidden_api_blacklist(self):
    """If necessary and possible, disables hidden api blacklist."""
    # Check version_codename in addition to sdk_version because Android P builds
    # in development report sdk_version 27, but still enforce the blacklist.
    if self._device.is_rootable and (
        int(self._device.build_info['build_version_sdk']) >= 28 or
        self._device.build_info['build_version_codename'] == 'P'):
      self._device.adb.shell(
          'settings put global hidden_api_blacklist_exemptions "*"')

  def do_start_server(self):
    """Starts the snippet server.

    This function starts the snippet server with adb command, checks the
    protocol version of the server, parses device port from the server
    output and sets it to self.device_port.

    Raises:
      errors.ServerStartProtocolError: if the protocol reported by the server
        starting process is unknown.
    """
    persists_shell_cmd = self._get_persist_command()
    # Use log.info here so people can follow along with the snippet startup
    # process. Starting snippets can be slow, especially if there are
    # multiple, and this avoids the perception that the framework is hanging
    # for a long time doing nothing.
    self.log.info('Launching snippet package %s with protocol %d.%d',
                  self.package, _PROTOCOL_MAJOR_VERSION,
                  _PROTOCOL_MINOR_VERSION)
    cmd = _LAUNCH_CMD.format(
        shell_cmd=persists_shell_cmd,
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
    """Starts a long-running ADB subprocess and returns it immediately."""
    adb_cmd = [adb.ADB]
    if self._adb.serial:
      adb_cmd += ['-s', self._adb.serial]
    adb_cmd += ['shell', cmd]
    return utils.start_standing_subprocess(adb_cmd, shell=False)

  def _get_persist_command(self):
    """Checks availability and returns path of persist command if available."""
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

  # TODO(mhaoli): Modify docstring
  def _get_user_command_string(self):
    """Gets the appropriate command argument for specifying user IDs.

    By default, `SnippetClient` operates within the current user.
    We don't add the `--user {ID}` arg when Android's SDK is below 24,
    where multi-user support is not well implemented.

    Returns:
      String, the command param section to be formatted into the adb
      commands.
    """
    sdk_int = int(self._device.build_info['build_version_sdk'])
    if sdk_int < 24:
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

  def do_stop_server(self):
    """Stops the snippet server and cleans allocated resources."""
    # Although killing the snippet server would abort this process anyway, we
    # want to call stop_standing_subprocess() to perform a health check,
    # print the failure stack trace if there was any, and reap it from the
    # process table. Note that it's much more important to ensure that the
    # allocated resources on the host side are cleaned.
    self._kill_server_subprocess()
    self._kill_server()

  def after_starting_server(self):
    """See base class."""
    # This client does nothing at this stage.

  def _kill_server_subprocess(self):
    """Kills the long running server subprocess running on host side."""
    if self._proc:
      utils.stop_standing_subprocess(self._proc)
      self._proc = None

  def _kill_server(self):
    """Sends the stop singal to remote server.

    Raises:
      android_device_lib_errors.DeviceError: if the server exited with errors.
    """
    out = self._adb.shell(
        _STOP_CMD.format(snippet_package=self.package,
                         user=self._get_user_command_string())).decode('utf-8')

    if 'OK (0 tests)' not in out:
      raise android_device_lib_errors.DeviceError(
          self._device,
          f'Failed to stop existing server. Unexpected output: {out}')
