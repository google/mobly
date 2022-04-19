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
import json
import socket

from mobly import utils
from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import callback_handler
from mobly.controllers.android_device_lib import errors as android_device_lib_errors
from mobly.snippet import client_base
from mobly.snippet import errors

# TODO: check that better to use server to replace some occurrences of app

# TODO: check typo in function/variable/class name

# The package of the instrumentation runner used for mobly snippet
_INSTRUMENTATION_RUNNER_PACKAGE = 'com.google.android.mobly.snippet.SnippetRunner'

# The command template to start the snippet server
_LAUNCH_CMD = (
    '{shell_cmd} am instrument {user} -w -e action start {snippet_package}/'
    f'{_INSTRUMENTATION_RUNNER_PACKAGE}')

# The command template to stop the snippet server
_STOP_CMD = ('am instrument {user} -w -e action stop {snippet_package}/'
             f'{_INSTRUMENTATION_RUNNER_PACKAGE}')

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

# UID of the 'unknown' jsonrpc session. Will cause creation of a new session.
UNKNOWN_UID = -1

# Maximum time to wait for the socket to open on the device.
_SOCKET_CONNECTION_TIMEOUT = 60

# Maximum time to wait for a response message on the socket.
_SOCKET_READ_TIMEOUT = callback_handler.MAX_TIMEOUT


# Rename it to MakeConnectionCommand
class JsonRpcCommand:
  """Commands that can be invoked on all jsonrpc clients.

  INIT: Initializes a new session and makes a connection.
  CONTINUE: Makes a connection with current session.
  """
  INIT = 'initiate'
  CONTINUE = 'continue'


class SnippetClientV2(client_base.ClientBase):
  """Snippet client V2 for interacting with snippet server on Android Device.

  For a description of the launch protocols, see the documentation in
  mobly-snippet-lib, SnippetRunner.java.

  We only list the public attributes introduced in this class. See base class
  documentation for other public attributes and communication protocols.

  Attributes:
    host_port: int, the host port used for communicating with the snippet
      server.
    device_port: int, the device port listened by the snippet server.
  """

  def __init__(self, package, ad):
    """Initializes the instance of Snippet Client V2.

    Args:
      package: str, see base class.
      ad: AndroidDevice, the android device object associated with this client.
    """
    super().__init__(package=package, device=ad)
    self.host_port = None
    self.device_port = None
    self._adb = ad.adb
    self._user_id = None
    self._proc = None
    # TODO: polish following comment
    self._client = None  # keep it to prevent close errors on connect failure
    self._conn = None
    self._event_client = None

  @property
  def user_id(self):
    """The user id to use for this snippet client.

    All the operations of the snippet client should be used for a particular
    user. For more details, see the Android documentation of testing
    multiple users.

    Thus this value is cached and, once set, does not change through the
    lifecycles of this snippet client object. This caching also reduces the
    number of adb calls needed.

    Although for now self._user_id won't be modified once set, we use
    `property` to avoid issuing adb commands in the constructor.

    Returns:
      An integer of the user id.
    """
    if self._user_id is None:
      self._user_id = self._adb.current_user_id
    return self._user_id

  @property
  def is_alive(self):
    """Does the client have an active connection to the snippet server."""
    return self._conn is not None

  def before_starting_server(self):
    """Performs the preparation steps before starting the remote server.

    This function performs following preparation steps:
    * Validate that the Mobly Snippet app is available on the device.
    * Disable hidden api blocklist if necessary and possible.

    Raises:
      errors.ServerStartPreCheckError: if the server app is not installed
        for the current user.
    """
    self._validate_snippet_app_on_device()
    self._disable_hidden_api_blocklist()

  def _validate_snippet_app_on_device(self):
    """Validates the Mobly Snippet app is available on the device.

    To run as an instrumentation test, the Mobly Snippet app must already be
    installed and instrumented on the Android device.

    Raises:
      errors.ServerStartPreCheckError: if the server app is not installed
        for the current user.
    """
    # Validate that the Mobly Snippet app is installed for the current user.
    out = self._adb.shell(f'pm list package --user {self.user_id}')
    if not utils.grep(f'^package:{self.package}$', out):
      raise errors.ServerStartPreCheckError(
          self._device,
          f'{self.package} is not installed for user {self.user_id}.')

    # Validate that the app is instrumented.
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
    # Validate that the instrumentation target is installed if it's not the
    # same as the snippet package.
    if target_name != self.package:
      out = self._adb.shell(f'pm list package --user {self.user_id}')
      if not utils.grep(f'^package:{target_name}$', out):
        raise errors.ServerStartPreCheckError(
            self._device,
            f'Instrumentation target {target_name} is not installed for user '
            f'{self.user_id}.')

  def _disable_hidden_api_blocklist(self):
    """If necessary and possible, disables hidden api blocklist."""
    sdk_version = int(self._device.build_info['build_version_sdk'])
    if self._device.is_rootable and sdk_version >= 28:
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
    persisting_shell_cmd = self._get_persisting_command()
    self.log.debug('Snippet server for package %s is using protocol %d.%d',
                   self.package, _PROTOCOL_MAJOR_VERSION,
                   _PROTOCOL_MINOR_VERSION)
    cmd = _LAUNCH_CMD.format(shell_cmd=persisting_shell_cmd,
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

  # TODO: add the information of close_connection to docstring
  def stop(self):
    """Releases all the resources acquired in `initialize`.

    This function releases following resources:
    * Stop the standing server subprocess running on the host side.
    * Stop the snippet server running on the device side.

    Raises:
      android_device_lib_errors.DeviceError: if the server exited with errors on
        the device side.
    """
    self.log.debug('Stopping snippet package %s.', self.package)
    self.close_connection()
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

    # Stop the standing server subprocess running on the host side.
    if self._proc:
      utils.stop_standing_subprocess(self._proc)
      self._proc = None

    # Send the stop signal to the server running on the device side.
    out = self._adb.shell(
        _STOP_CMD.format(snippet_package=self.package,
                         user=self._get_user_command_string())).decode('utf-8')

    if 'OK (0 tests)' not in out:
      raise android_device_lib_errors.DeviceError(
          self._device,
          f'Failed to stop existing apk. Unexpected output: {out}.')

  def make_connection(self):
    self._forward_device_port()
    self._make_socket_connection()
    self._send_handshake_request()

  def _forward_device_port(self):
    """Forwards the device port to a new host port."""
    if not self.host_port:
      self.host_port = utils.get_available_host_port()
    self._adb.forward([f'tcp:{self.host_port}', f'tcp:{self.device_port}'])

  def _make_socket_connection(self):
    try:
      self._conn = socket.create_connection(('localhost', self.host_port),
                                            _SOCKET_CONNECTION_TIMEOUT)
    except ConnectionRefusedError as err:
      # Retry using '127.0.0.1' for IPv4 enabled machines that only resolve
      # 'localhost' to '[::1]'.
      self.log.debug(
          'Failed to connect to localhost, trying 127.0.0.1: %s', str(err))
      self._conn = socket.create_connection(('127.0.0.1', self.host_port),
                                            _SOCKET_CONNECTION_TIMEOUT)

    self._conn.settimeout(_SOCKET_READ_TIMEOUT)
    # TODO: Rename it, _stub
    self._client = self._conn.makefile(mode='brw')

  def _send_handshake_request(self, uid=None, cmd=None):
    # TODO: could we just use UNKNOWN_UID and INIT as default value
    if uid is None:
      uid = UNKNOWN_UID
    if not cmd:
      cmd = JsonRpcCommand.INIT
    try:
      request = json.dumps({'cmd': cmd, 'uid': uid})
      self.log.debug('Sending handshake request %s.', request)
      resp = self.send_rpc_request(request)
    # TODO: check all the used errors
    except errors.ProtocolError as e:
      if errors.ProtocolError.NO_RESPONSE_FROM_SERVER in str(e):
        raise errors.ProtocolError(
            self._device,
            errors.ProtocolError.NO_RESPONSE_FROM_HANDSHAKE)
      else:
        raise

    if not resp:
      raise errors.ProtocolError(
          self._device,
          errors.ProtocolError.NO_RESPONSE_FROM_HANDSHAKE)

    result = json.loads(resp)
    if result['status']:
      self.uid = result['uid']
    else:
      self.uid = UNKNOWN_UID

  def close_connection(self):
    try:
      if self._conn:
        self._conn.close()
        self._conn = None
    finally:
      # Always clear the host port as part of the disconnect step.
      self._stop_port_forwarding()

  def _stop_port_forwarding(self):
    """Stops the adb port forwarding of the host port used by this client."""
    if self.host_port:
      self._device.adb.forward(['--remove', f'tcp:{self.host_port}'])
      self.host_port = None

  def check_server_proc_running(self):
    pass

  def send_rpc_request(self, request):
    try:
      self._client.write(f'{request}\n'.encode('utf8'))
      self._client.flush()
    except socket.error as e:
      raise errors.Error(
          self._device,
          f'Encountered socket error "{e}" sending RPC message "{request}"')

    try:
      response = self._client.readline()
    except socket.error as e:
      raise errors.Error(self._device,
                         f'Encountered socket error "{e}" reading RPC response')

    if not response:
      raise errors.ProtocolError(
          self._device,
          errors.ProtocolError.NO_RESPONSE_FROM_SERVER)
    try:
      response = str(response, encoding='utf8')
    except UnicodeError:
      self.log.error(
          'Failed to decode the RPC response using encoding utf8: %s', response)
      raise
    return response

  def handle_callback(self, callback_id, ret_value, method_name):
    if self._event_client is None:
      self._event_client = self._start_event_client()
    return callback_handler.CallbackHandler(callback_id=callback_id,
                                            event_client=self._event_client,
                                            ret_value=ret_value,
                                            method_name=method_name,
                                            ad=self._device)

  def _start_event_client(self):
    """Overrides superclass."""
    event_client = SnippetClientV2(package=self.package,
                                   ad=self._device)
    event_client.host_port = self.host_port
    event_client.device_port = self.device_port
    event_client._counter = event_client._id_counter()
    event_client._make_socket_connection()
    event_client._send_handshake_request(self.uid, JsonRpcCommand.CONTINUE)
    return event_client

  def restore_server_connection(self, port=None):
    """Restores the server after device got reconnected.

    Instead of creating new instance of the client:
      - Uses the given port (or find a new available host_port if none is
      given).
      - Tries to connect to remote server with selected port.

    Args:
      port: If given, this is the host port from which to connect to remote
        device port. If not provided, find a new available port as host
        port.

    Raises:
      errors.ServerRestoreConnectionError: When the server was not able to be started.
    """
    try:
      # If self.host_port is None, self._make_connection finds an available
      # port.
      self.host_port = port
      self._make_connection()
    except Exception:
      # Log the original error and raise AppRestoreConnectionError.
      self.log.exception('Failed to re-connect to server.')
      raise errors.ServerRestoreConnectionError(
          self._device,
          (f'Failed to restore server connection for {self.package} at '
           f'host port {self.host_port}, device port {self.device_port}.')
      )

    # Because the previous connection was lost, update self._proc
    self._proc = None
    self._restore_event_client()

  def _restore_event_client(self):
    """Restores previously created event client."""
    if not self._event_client:
      self._event_client = self._start_event_client()
      return
    self._event_client.host_port = self.host_port
    self._event_client.device_port = self.device_port
    self._event_client._make_socket_connection()
    self._event_client._send_handshake_request()

  def help(self, print_output=True):
    """Calls the help RPC, which returns the list of RPC calls available.
    This RPC should normally be used in an interactive console environment
    where the output should be printed instead of returned. Otherwise,
    newlines will be escaped, which will make the output difficult to read.
    Args:
      print_output: A bool for whether the output should be printed.
    Returns:
      A str containing the help output otherwise None if print_output
        wasn't set.
    """
    help_text = self._rpc('help')
    if print_output:
      print(help_text)
    else:
      return help_text
