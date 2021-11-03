#!/usr/bin/env python3
#
#   Copyright 2018 - Google Inc.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
import threading
import time

from mobly.controllers.android_device_lib.acts_sl4a_lib import error_reporter
from mobly.controllers.android_device_lib.acts_sl4a_lib import logger
from mobly.controllers.android_device_lib.acts_sl4a_lib import rpc_client
from mobly.controllers.android_device_lib.acts_sl4a_lib import sl4a_session

ATTEMPT_INTERVAL = .25
MAX_WAIT_ON_SERVER_SECONDS = 5

SL4A_PKG_NAME = 'com.googlecode.android_scripting'

_SL4A_LAUNCH_SERVER_CMD = (
  'am startservice -a com.googlecode.android_scripting.action.LAUNCH_SERVER '
  '--ei com.googlecode.android_scripting.extra.USE_SERVICE_PORT %s '
  'com.googlecode.android_scripting/.service.ScriptingLayerService')

_SL4A_CLOSE_SERVER_CMD = (
  'am startservice -a com.googlecode.android_scripting.action.KILL_PROCESS '
  '--ei com.googlecode.android_scripting.extra.PROXY_PORT %s '
  'com.googlecode.android_scripting/.service.ScriptingLayerService')

# The command for finding SL4A's server port as root.
_SL4A_ROOT_FIND_PORT_CMD = (
  # Get all open, listening ports, and their process names
  'ss -l -p -n | '
  # Find all open TCP ports for SL4A
  'grep "tcp.*droid_scripting" | '
  # Shorten all whitespace to a single space character
  'tr -s " " | '
  # Grab the 5th column (which is server:port)
  'cut -d " " -f 5 |'
  # Only grab the port
  'sed s/.*://g')

# The command for finding SL4A's server port without root.
_SL4A_USER_FIND_PORT_CMD = (
  # Get all open, listening ports, and their process names
  'ss -l -p -n | '
  # Find all open ports exposed to the public. This can produce false
  # positives since users cannot read the process associated with the port.
  'grep -e "tcp.*::ffff:127\.0\.0\.1:" | '
  # Shorten all whitespace to a single space character
  'tr -s " " | '
  # Grab the 5th column (which is server:port)
  'cut -d " " -f 5 |'
  # Only grab the port
  'sed s/.*://g')

# The command that begins the SL4A ScriptingLayerService.
_SL4A_START_SERVICE_CMD = (
  'am startservice '
  'com.googlecode.android_scripting/.service.ScriptingLayerService')

# Maps device serials to their SL4A Manager. This is done to prevent multiple
# Sl4aManagers from existing for the same device.
_all_sl4a_managers = {}


def create_sl4a_manager(adb):
  """Creates and returns an SL4AManager for the given device.

  Args:
      adb: A reference to the device's AdbProxy.
  """
  if adb.serial in _all_sl4a_managers:
    _all_sl4a_managers[adb.serial].log.warning(
      'Attempted to return multiple SL4AManagers on the same device. '
      'Returning pre-existing SL4AManager instead.')
    return _all_sl4a_managers[adb.serial]
  else:
    manager = Sl4aManager(adb)
    _all_sl4a_managers[adb.serial] = manager
    return manager


class Sl4aManager(object):
  """A manager for SL4A Clients to a given AndroidDevice.

  SL4A is a single APK that can host multiple RPC servers at a time. This
  class manages each server connection over ADB, and will gracefully
  terminate the apk during cleanup.

  Attributes:
      _listen_for_port_lock: A lock for preventing multiple threads from
          potentially mixing up requested ports.
      _sl4a_ports: A set of all known SL4A server ports in use.
      adb: A reference to the AndroidDevice's AdbProxy.
      log: The logger for this object.
      sessions: A dictionary of session_ids to sessions.
  """

  def __init__(self, adb):
    self._listen_for_port_lock = threading.Lock()
    self._sl4a_ports = set()
    self.adb = adb
    self.log = logger.create_tagged_logger('SL4A Manager|%s' % adb.serial)
    self.sessions = {}
    self._started = False
    self.error_reporter = error_reporter.ErrorReporter(
      'SL4A %s' % adb.serial)

  @property
  def sl4a_ports_in_use(self):
    """Returns a list of all server ports used by SL4A servers."""
    return set([session.server_port for session in self.sessions.values()])

  def diagnose_failure(self, session, connection):
    """Diagnoses all potential known reasons SL4A can fail.

    Assumes the failure happened on an RPC call, which verifies the state
    of ADB/device."""
    self.error_reporter.create_error_report(self, session, connection)

  def start_sl4a_server(self, device_port, try_interval=ATTEMPT_INTERVAL):
    """Opens a server socket connection on SL4A.

    Args:
        device_port: The expected port for SL4A to open on. Note that in
            many cases, this will be different than the port returned by
            this method.
        try_interval: The amount of seconds between attempts at finding an
            opened port on the AndroidDevice.

    Returns:
        The port number on the device the SL4A server is open on.

    Raises:
        Sl4aConnectionError if SL4A's opened port cannot be found.
    """
    # Launch a server through SL4A.
    self.adb.shell(_SL4A_LAUNCH_SERVER_CMD % device_port)

    # There is a chance that the server has not come up yet by the time the
    # launch command has finished. Try to read get the listening port again
    # after a small amount of time.
    time_left = MAX_WAIT_ON_SERVER_SECONDS
    while time_left > 0:
      port = self._get_open_listening_port()
      if port is None:
        time.sleep(try_interval)
        time_left -= try_interval
      else:
        return port

    raise rpc_client.Sl4aConnectionError(
      'Unable to find a valid open port for a new server connection. '
      'Expected port: %s. Open ports: %s' % (device_port,
                                             self._sl4a_ports))

  def _get_all_ports_command(self):
    """Returns the list of all ports from the command to get ports."""
    is_root = True
    if not self.adb.is_root():
      is_root = self.adb.ensure_root()

    if is_root:
      return _SL4A_ROOT_FIND_PORT_CMD
    else:
      # TODO(markdr): When root is unavailable, search logcat output for
      #               the port the server has opened.
      self.log.warning('Device cannot be put into root mode. SL4A '
                       'server connections cannot be verified.')
      return _SL4A_USER_FIND_PORT_CMD

  def _get_all_ports(self):
    return self.adb.shell(self._get_all_ports_command()).split()

  def _get_open_listening_port(self):
    """Returns any open, listening port found for SL4A.

    Will return none if no port is found.
    """
    possible_ports = self._get_all_ports()
    self.log.debug('SL4A Ports found: %s' % possible_ports)

    # Acquire the lock. We lock this method because if multiple threads
    # attempt to get a server at the same time, they can potentially find
    # the same port as being open, and both attempt to connect to it.
    with self._listen_for_port_lock:
      for port in possible_ports:
        if port not in self._sl4a_ports:
          self._sl4a_ports.add(port)
          return int(port)
    return None

  def is_sl4a_installed(self):
    """Returns True if SL4A is installed on the AndroidDevice."""
    return bool(
      self.adb.shell('pm path %s' % SL4A_PKG_NAME, ignore_status=True))

  def start_sl4a_service(self):
    """Starts the SL4A Service on the device.

    For starting an RPC server, use start_sl4a_server() instead.
    """
    # Verify SL4A is installed.
    if not self._started:
      self._started = True
      if not self.is_sl4a_installed():
        raise rpc_client.Sl4aNotInstalledError(
          'SL4A is not installed on device %s' % self.adb.serial)
      if self.adb.shell('(ps | grep "S %s") || true' % SL4A_PKG_NAME):
        # Close all SL4A servers not opened by this manager.
        # TODO(markdr): revert back to closing all ports after
        # b/76147680 is resolved.
        self.adb.shell('kill -9 $(pidof %s)' % SL4A_PKG_NAME)
      self.adb.shell(
        'settings put global hidden_api_blacklist_exemptions "*"')
      # Start the service if it is not up already.
      self.adb.shell(_SL4A_START_SERVICE_CMD)

  def obtain_sl4a_server(self, server_port):
    """Obtain an SL4A server port.

    If the port is open and valid, return it. Otherwise, open an new server
    with the hinted server_port.
    """
    if server_port not in self.sl4a_ports_in_use:
      return self.start_sl4a_server(server_port)
    else:
      return server_port

  def create_session(self,
                     max_connections=None,
                     client_port=0,
                     server_port=None):
    """Creates an SL4A server with the given ports if possible.

    The ports are not guaranteed to be available for use. If the port
    asked for is not available, this will be logged, and the port will
    be randomized.

    Args:
        client_port: The port on the host machine
        server_port: The port on the Android device.
        max_connections: The max number of client connections for the
            session.

    Returns:
        A new Sl4aServer instance.
    """
    if server_port is None:
      # If a session already exists, use the same server.
      if len(self.sessions) > 0:
        server_port = self.sessions[sorted(
          self.sessions.keys())[0]].server_port
      # Otherwise, open a new server on a random port.
      else:
        server_port = 0
    self.start_sl4a_service()
    session = sl4a_session.Sl4aSession(
      self.adb,
      client_port,
      server_port,
      self.obtain_sl4a_server,
      self.diagnose_failure,
      max_connections=max_connections)
    self.sessions[session.uid] = session
    return session

  def stop_service(self):
    """Stops The SL4A Service. Force-stops the SL4A apk."""
    try:
      self.adb.shell(
        'am force-stop %s' % SL4A_PKG_NAME, ignore_status=True)
    except Exception as e:
      self.log.warning("Fail to stop package %s: %s", SL4A_PKG_NAME, e)
    self._started = False

  def terminate_all_sessions(self):
    """Terminates all SL4A sessions gracefully."""
    self.error_reporter.finalize_reports()
    for _, session in self.sessions.items():
      session.terminate()
    self.sessions = {}
    self._close_all_ports()

  def _close_all_ports(self, try_interval=ATTEMPT_INTERVAL):
    """Closes all ports opened on SL4A."""
    ports = self._get_all_ports()
    for port in set.union(self._sl4a_ports, ports):
      self.adb.shell(_SL4A_CLOSE_SERVER_CMD % port)
    time_left = MAX_WAIT_ON_SERVER_SECONDS
    while time_left > 0 and self._get_open_listening_port():
      time.sleep(try_interval)
      time_left -= try_interval

    if time_left <= 0:
      self.log.warning(
        'Unable to close all un-managed servers! Server ports that are '
        'still open are %s' % self._get_open_listening_port())
    self._sl4a_ports = set()
