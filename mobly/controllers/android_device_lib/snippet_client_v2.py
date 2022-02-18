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
"""JSON RPC Client for Android Devices."""

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

import re
import time
import socket
import json

from mobly import utils
from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import errors
from mobly.controllers.android_device_lib import callback_handler
from mobly.controllers.android_device_lib import jsonrpc_client_base
from mobly.snippet import client_base

_INSTRUMENTATION_RUNNER_PACKAGE = (
    'com.google.android.mobly.snippet.SnippetRunner')

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

_LAUNCH_CMD = (
    '{shell_cmd} am instrument {user} -w -e action start {snippet_package}/' +
    _INSTRUMENTATION_RUNNER_PACKAGE)

_STOP_CMD = ('am instrument {user} -w -e action stop {snippet_package}/' +
             _INSTRUMENTATION_RUNNER_PACKAGE)

# Test that uses UiAutomation requires the shell session to be maintained while
# test is in progress. However, this requirement does not hold for the test that
# deals with device USB disconnection (Once device disconnects, the shell
# session that started the instrument ends, and UiAutomation fails with error:
# "UiAutomation not connected"). To keep the shell session and redirect
# stdin/stdout/stderr, use "setsid" or "nohup" while launching the
# instrumentation test. Because these commands may not be available in every
# android system, try to use them only if exists.
_SETSID_COMMAND = 'setsid'

_NOHUP_COMMAND = 'nohup'

# UID of the 'unknown' jsonrpc session. Will cause creation of a new session.
UNKNOWN_UID = -1

# TODO: consider move this timeout config to general place

# Maximum time to wait for the socket to open on the device.
_SOCKET_CONNECTION_TIMEOUT = 60

# Maximum time to wait for a response message on the socket.
_SOCKET_READ_TIMEOUT = callback_handler.MAX_TIMEOUT

class JsonRpcCommand:
  """Commands that can be invoked on all jsonrpc clients.

  INIT: Initializes a new session.
  CONTINUE: Creates a connection.
  """
  INIT = 'initiate'
  CONTINUE = 'continue'


class AppStartPreCheckError(jsonrpc_client_base.Error):
  """Raised when pre checks for the snippet failed."""


class ProtocolVersionError(jsonrpc_client_base.AppStartError):
  """Raised when the protocol reported by the snippet is unknown."""


class SnippetClientV2(client_base.ClientBase):
  """A client for interacting with snippet APKs using Mobly Snippet Lib.

  See superclass documentation for a list of public attributes.

  For a description of the launch protocols, see the documentation in
  mobly-snippet-lib, SnippetRunner.java.
  """

  def __init__(self, package, device):
    """Initializes a SnippetClient.

    Args:
      snippet_name: (str) The package name of the apk where the snippets are
        defined.
      ad: (AndroidDevice) the device object associated with this client.
    """
    super().__init__(snippet_name=package, device=device)
    self.package = package
    self._adb = device.adb
    self._proc = None
    self._user_id = None
    self._client = None  # prevent close errors on connect failure
    self._conn = None
    self._event_client = None

  @property
  def is_alive(self):
    """Does the client have an active connection to the snippet server."""
    return self._conn is not None

  @property
  def user_id(self):
    """The user id to use for this snippet client.

    This value is cached and, once set, does not change through the lifecycles
    of this snippet client object. This caching also reduces the number of adb
    calls needed.

    Because all the operations of the snippet client should be done for a
    partucular user.
    """
    if self._user_id is None:
      self._user_id = self._adb.current_user_id
    return self._user_id

  def _before_starting_server(self):
    self._check_app_installed()
    self._disable_hidden_api_blacklist()

  def _do_start_server(self):
    """ Starts the snippet server.

    This function starts the snippet server with adb command, checks the
    protocol version of the server, and parses device port from the server
    output.
    """
    persists_shell_cmd = self._get_persist_command()
    # TODO: print protocol info into in base
    # Use info here so people can follow along with the snippet startup
    # process. Starting snippets can be slow, especially if there are
    # multiple, and this avoids the perception that the framework is hanging
    # for a long time doing nothing.
    self.log.info('Launching snippet apk %s with protocol %d.%d', self.snippet_name,
                  _PROTOCOL_MAJOR_VERSION, _PROTOCOL_MINOR_VERSION)
    cmd = _LAUNCH_CMD.format(shell_cmd=persists_shell_cmd,
                             user=self._get_user_command_string(),
                             snippet_package=self.snippet_name)
    self._proc = self._run_abd_cmd(cmd)

    # Check protocol version and get the device port
    line = self._read_protocol_line()
    match = re.match('^SNIPPET START, PROTOCOL ([0-9]+) ([0-9]+)$', line)
    if not match or match.group(1) != '1':
      raise ProtocolVersionError(self._device, line)

    line = self._read_protocol_line()
    match = re.match('^SNIPPET SERVING, PORT ([0-9]+)$', line)
    if not match:
      raise ProtocolVersionError(self._device, line)
    self.device_port = int(match.group(1))

  def _run_abd_cmd(self, cmd):
    adb_cmd = [adb.ADB]
    if self._adb.serial:
      adb_cmd += ['-s', self._adb.serial]
    adb_cmd += ['shell', cmd]
    return utils.start_standing_subprocess(adb_cmd, shell=False)

  def _build_connection(self, host_port=None):
    self._forward_device_port(host_port)
    self._build_socket_connection()
    self._send_handshake_request()

  def _forward_device_port(self, host_port=None):
    """Forwards the device port to a new host port."""
    self.host_port = host_port or utils.get_available_host_port()
    self._adb.forward(['tcp:%d' % self.host_port, 'tcp:%d' % self.device_port])

  def _build_socket_connection(self):
    self._counter = self._id_counter()
    try:
      self._conn = socket.create_connection(('localhost', self.host_port),
                                            _SOCKET_CONNECTION_TIMEOUT)
    except ConnectionRefusedError as err:
      # Retry using '127.0.0.1' for IPv4 enabled machines that only resolve
      # 'localhost' to '[::1]'.
      self.log.debug(
          'Failed to connect to localhost, trying 127.0.0.1: {}'.format(
              str(err)))
      self._conn = socket.create_connection(('127.0.0.1', self.host_port),
                                            _SOCKET_CONNECTION_TIMEOUT)

    self._conn.settimeout(_SOCKET_READ_TIMEOUT)
    self._client = self._conn.makefile(mode='brw')

  def _send_handshake_request(self, uid=None, cmd=None):
    if uid is None:
      uid = UNKNOWN_UID
    if not cmd:
      cmd = JsonRpcCommand.INIT
    try:
      resp = self._send_rpc_request(json.dumps({'cmd': cmd, 'uid': uid}))
    except jsonrpc_client_base.ProtocolError as e:
      if jsonrpc_client_base.ProtocolError.NO_RESPONSE_FROM_SERVER in str(e):
        raise jsonrpc_client_base.ProtocolError(self._device, jsonrpc_client_base.ProtocolError.NO_RESPONSE_FROM_HANDSHAKE)
      else:
        raise

    if not resp:
      raise jsonrpc_client_base.ProtocolError(self._device, jsonrpc_client_base.ProtocolError.NO_RESPONSE_FROM_HANDSHAKE)
    result = json.loads(resp)
    if result['status']:
      self.uid = result['uid']
    else:
      self.uid = UNKNOWN_UID

  def _check_app_installed(self):
    # Check that the Mobly Snippet app is installed for the current user.
    out = self._adb.shell(f'pm list package --user {self.user_id}')
    if not utils.grep('^package:%s$' % self.snippet_name, out):
      raise AppStartPreCheckError(
          self._device, f'{self.snippet_name} is not installed for user {self.user_id}.')
    # Check that the app is instrumented.
    out = self._adb.shell('pm list instrumentation')
    matched_out = utils.grep(
        f'^instrumentation:{self.snippet_name}/{_INSTRUMENTATION_RUNNER_PACKAGE}',
        out)
    if not matched_out:
      raise AppStartPreCheckError(
          self._device, f'{self.snippet_name} is installed, but it is not instrumented.')
    match = re.search(r'^instrumentation:(.*)\/(.*) \(target=(.*)\)$',
                      matched_out[0])
    target_name = match.group(3)
    # Check that the instrumentation target is installed if it's not the
    # same as the snippet package.
    if target_name != self.snippet_name:
      out = self._adb.shell(f'pm list package --user {self.user_id}')
      if not utils.grep('^package:%s$' % target_name, out):
        raise AppStartPreCheckError(
            self._device,
            f'Instrumentation target {target_name} is not installed for user '
            f'{self.user_id}.')

  def _disable_hidden_api_blacklist(self):
    """If necessary and possible, disables hidden api blacklist."""
    version_codename = self._device.build_info['build_version_codename']
    sdk_version = int(self._device.build_info['build_version_sdk'])
    # we check version_codename in addition to sdk_version because P builds
    # in development report sdk_version 27, but still enforce the blacklist.
    if self._device.is_rootable and (sdk_version >= 28 or version_codename == 'P'):
      self._device.adb.shell(
          'settings put global hidden_api_blacklist_exemptions "*"')

  def _send_rpc_request(self, request):
    try:
      self._client.write(request.encode("utf8") + b'\n')
      self._client.flush()
    except socket.error as e:
      raise Error(
          self._device,
          'Encountered socket error "%s" sending RPC message "%s"' % (e, request))

    try:
      response = self._client.readline()
      if not response:
        raise jsonrpc_client_base.ProtocolError(self._device, jsonrpc_client_base.ProtocolError.NO_RESPONSE_FROM_SERVER)
      response = str(response, encoding='utf8')
      return response
    except socket.error as e:
      raise Error(self._device,
                  'Encountered socket error reading RPC response "%s"' % e)

  def _handle_callback(self, callback_id, ret_value, method_name):
    if self._event_client is None:
      self._event_client = self._start_event_client()
    return callback_handler.CallbackHandler(callback_id=callback_id,
                                            event_client=self._event_client,
                                            ret_value=ret_value,
                                            method_name=method_name,
                                            ad=self._device)
  def _start_event_client(self):
    """Overrides superclass."""
    event_client = SnippetClientV2(snippet_name=self.snippet_name, device=self._device)
    event_client.host_port = self.host_port
    event_client.device_port = self.device_port
    event_client._build_socket_connection()
    event_client._send_handshake_request(self.uid, JsonRpcCommand.CONTINUE)
    return event_client

  def _stop_server(self):
    # Kill the pending 'adb shell am instrument -w' process if there is one.
    # Although killing the snippet apk would abort this process anyway, we
    # want to call stop_standing_subprocess() to perform a health check,
    # print the failure stack trace if there was any, and reap it from the
    # process table.

    # Close the socket connection.
    self._close_socket_connection()

    # kill the server subprocess
    self._kill_server_subprocess()

    # send a kill singal to the server running on the testing device
    self._kill_server()

  def _close_socket_connection(self):
    try:
      if self._conn:
        self._conn.close()
        self._conn = None
    finally:
      # Always clear the host port as part of the disconnect step.
      self._stop_port_forwarding()

  def _stop_port_forwarding(self):
    """Stops the adb port forwarding of the host port used by this client.
    """
    if self.host_port:
      self._device.adb.forward(['--remove', 'tcp:%d' % self.host_port])
      self.host_port = None


  def _kill_server_subprocess(self):
    if self._proc:
      utils.stop_standing_subprocess(self._proc)
      self._proc = None

  def _kill_server(self):
    out = self._adb.shell(
        _STOP_CMD.format(snippet_package=self.snippet_name,
                         user=self._get_user_command_string())).decode('utf-8')
    if 'OK (0 tests)' not in out:
      raise errors.DeviceError(
          self._device, 'Failed to stop existing apk. Unexpected output: %s' % out)

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

    This method will skip over lines that don't start with 'SNIPPET' or
    'INSTRUMENTATION_RESULT'.

    Returns:
      (str) Next line of snippet-related instrumentation output, stripped.

    Raises:
      jsonrpc_client_base.AppStartError: If EOF is reached without any
        protocol lines being read.
    """
    while True:
      line = self._proc.stdout.readline().decode('utf-8')
      if not line:
        raise jsonrpc_client_base.AppStartError(
            self._device, 'Unexpected EOF waiting for app to start')
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

  def _get_persist_command(self):
    """Check availability and return path of command if available."""
    for command in [_SETSID_COMMAND, _NOHUP_COMMAND]:
      try:
        if command in self._adb.shell(['which', command]).decode('utf-8'):
          return command
      except adb.AdbError:
        continue
    self.log.warning(
        'No %s and %s commands available to launch instrument '
        'persistently, tests that depend on UiAutomator and '
        'at the same time performs USB disconnection may fail', _SETSID_COMMAND,
        _NOHUP_COMMAND)
    return ''

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

  def restore_server_connection(self, port=None):
    """Restores the app after device got reconnected.

    Instead of creating new instance of the client:
      - Uses the given port (or find a new available host_port if none is
      given).
      - Tries to connect to remote server with selected port.

    Args:
      port: If given, this is the host port from which to connect to remote
        device port. If not provided, find a new available port as host
        port.

    Raises:
      AppRestoreConnectionError: When the app was not able to be started.
    """
    try:
      self._build_connection(port)
    except Exception:
      # Log the original error and raise AppRestoreConnectionError.
      self.log.exception('Failed to re-connect to app.')
      raise jsonrpc_client_base.AppRestoreConnectionError(
          self._device,
          ('Failed to restore app connection for %s at host port %s, '
           'device port %s') % (self.snippet_name, self.host_port, self.device_port))

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
    self._event_client._build_socket_connection()
    self._event_client._send_handshake_request()

  # Rest methods are for compatibility with the public interface of client v1.
  def disconnect(self):
    self._close_socket_connection()
