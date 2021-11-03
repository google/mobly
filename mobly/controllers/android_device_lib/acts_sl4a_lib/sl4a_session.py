#!/usr/bin/env python3
#
#   Copyright 2018 - Google, Inc.
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
import errno
import socket
import threading

from mobly.controllers.android_device_lib.acts_sl4a_lib import event_dispatcher
from mobly.controllers.android_device_lib.acts_sl4a_lib import logger
from mobly.controllers.android_device_lib.acts_sl4a_lib import rpc_client
from mobly.controllers.android_device_lib.acts_sl4a_lib import rpc_connection
from mobly.controllers.android_device_lib.acts_sl4a_lib import sl4a_ports
from mobly.controllers.android_device_lib.adb import AdbError

SOCKET_TIMEOUT = 60

# The SL4A Session UID when a UID has not been received yet.
UNKNOWN_UID = -1


class Sl4aSession(object):
  """An object that tracks the state of an SL4A Session.

  Attributes:
      _event_dispatcher: The EventDispatcher instance, if any, for this
          session.
      _terminate_lock: A lock that prevents race conditions for multiple
          threads calling terminate()
      _terminated: A bool that stores whether or not this session has been
          terminated. Terminated sessions cannot be restarted.
      adb: A reference to the AndroidDevice's AdbProxy.
      log: The logger for this Sl4aSession
      server_port: The SL4A server port this session is established on.
      uid: The uid that corresponds the the SL4A Server's session id. This
          value is only unique during the lifetime of the SL4A apk.
  """

  def __init__(self,
               adb,
               host_port,
               device_port,
               get_server_port_func,
               on_error_callback,
               max_connections=None):
    """Creates an SL4A Session.

    Args:
        adb: A reference to the adb proxy
        get_server_port_func: A lambda (int) that returns the corrected
            server port. The int passed in hints at which port to use, if
            possible.
        host_port: The port the host machine uses to connect to the SL4A
            server for its first connection.
        device_port: The SL4A server port to be used as a hint for which
            SL4A server to connect to.
    """
    self._event_dispatcher = None
    self._terminate_lock = threading.Lock()
    self._terminated = False
    self.adb = adb

    self.server_port = device_port
    self.uid = UNKNOWN_UID
    self.obtain_server_port = get_server_port_func
    self._on_error_callback = on_error_callback

    self.log = logger.create_tagged_logger(
      'SL4A Session|%s|%s' % (self.adb.serial, self.uid))

    connection_creator = self._rpc_connection_creator(host_port)
    self.rpc_client = rpc_client.RpcClient(
      self.uid,
      self.adb.serial,
      self.diagnose_failure,
      connection_creator,
      max_connections=max_connections)

  def _rpc_connection_creator(self, host_port):
    def create_client(uid):
      return self._create_rpc_connection(
        ports=sl4a_ports.Sl4aPorts(host_port, 0, self.server_port),
        uid=uid)

    return create_client

  @property
  def is_alive(self):
    return not self._terminated

  def _create_forwarded_port(self, server_port, hinted_port=0):
    """Creates a forwarded port to the specified server port.

    Args:
        server_port: (int) The port to forward to.
        hinted_port: (int) The port to use for forwarding, if available.
                     Otherwise, the chosen port will be random.
    Returns:
        The chosen forwarded port.

    Raises AdbError if the version of ADB is too old, or the command fails.
    """
    if self.adb.get_version_number() < 37 and hinted_port == 0:
      self.log.error(
        'The current version of ADB does not automatically provide a '
        'port to forward. Please upgrade ADB to version 1.0.37 or '
        'higher.')
      raise rpc_client.Sl4aStartError('Unable to forward a port to the '
                                      'device.')
    else:
      try:
        return self.adb.tcp_forward(hinted_port, server_port)
      except AdbError as e:
        if 'cannot bind listener' in e.stderr:
          self.log.warning(
            'Unable to use %s to forward to device port %s due to: '
            '"%s". Attempting to choose a random port instead.' %
            (hinted_port, server_port, e.stderr))
          # Call this method again, but this time with no hinted port.
          return self._create_forwarded_port(server_port)
        raise e

  def _create_rpc_connection(self, ports=None, uid=UNKNOWN_UID):
    """Creates an RPC Connection with the specified ports.

    Args:
        ports: A Sl4aPorts object or a tuple of (host/client_port,
               forwarded_port, device/server_port). If any of these are
               zero, the OS will determine their values during connection.

               Note that these ports are only suggestions. If they are not
               available, the a different port will be selected.
        uid: The UID of the SL4A Session. To create a new session, use
             UNKNOWN_UID.
    Returns:
        An Sl4aClient.
    """
    if ports is None:
      ports = sl4a_ports.Sl4aPorts(0, 0, 0)
    # Open a new server if a server cannot be inferred.
    ports.server_port = self.obtain_server_port(ports.server_port)
    self.server_port = ports.server_port
    # Forward the device port to the host.
    ports.forwarded_port = self._create_forwarded_port(ports.server_port)
    client_socket, fd = self._create_client_side_connection(ports)
    client = rpc_connection.RpcConnection(
      self.adb, ports, client_socket, fd, uid=uid)
    client.open()
    if uid == UNKNOWN_UID:
      self.uid = client.uid
    return client

  def diagnose_failure(self, connection):
    """Diagnoses any problems related to the SL4A session."""
    self._on_error_callback(self, connection)

  def get_event_dispatcher(self):
    """Returns the EventDispatcher for this Sl4aSession."""
    if self._event_dispatcher is None:
      self._event_dispatcher = event_dispatcher.EventDispatcher(
        self.adb.serial, self.rpc_client)
    return self._event_dispatcher

  def _create_client_side_connection(self, ports):
    """Creates and connects the client socket to the forward device port.

    Args:
        ports: A Sl4aPorts object or a tuple of (host_port,
        forwarded_port, device_port).

    Returns:
        A tuple of (socket, socket_file_descriptor).
    """
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.settimeout(SOCKET_TIMEOUT)
    client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if ports.client_port != 0:
      try:
        client_socket.bind((socket.gethostname(), ports.client_port))
      except OSError as e:
        # If the port is in use, log and ask for any open port.
        if e.errno == errno.EADDRINUSE:
          self.log.warning(
            'Port %s is already in use on the host. '
            'Generating a random port.' % ports.client_port)
          ports.client_port = 0
          return self._create_client_side_connection(ports)
        raise

    # Verify and obtain the port opened by SL4A.
    try:
      # Connect to the port that has been forwarded to the device.
      client_socket.connect(('127.0.0.1', ports.forwarded_port))
    except socket.timeout:
      raise rpc_client.Sl4aConnectionError(
        'SL4A has not connected over the specified port within the '
        'timeout of %s seconds.' % SOCKET_TIMEOUT)
    except socket.error as e:
      # In extreme, unlikely cases, a socket error with
      # errno.EADDRNOTAVAIL can be raised when a desired host_port is
      # taken by a separate program between the bind and connect calls.
      # Note that if host_port is set to zero, there is no bind before
      # the connection is made, so this error will never be thrown.
      if e.errno == errno.EADDRNOTAVAIL:
        ports.client_port = 0
        return self._create_client_side_connection(ports)
      raise
    ports.client_port = client_socket.getsockname()[1]
    return client_socket, client_socket.makefile(mode='brw')

  def terminate(self):
    """Terminates the session.

    The return of process execution is blocked on completion of all events
    being processed by handlers in the Event Dispatcher.
    """
    with self._terminate_lock:
      if not self._terminated:
        self.log.debug('Terminating Session.')
        try:
          self.rpc_client.closeSl4aSession()
        except Exception as e:
          if "SL4A session has already been terminated" not in str(
              e):
            self.log.warning(e)
        # Must be set after closeSl4aSession so the rpc_client does not
        # think the session has closed.
        self._terminated = True
        if self._event_dispatcher:
          try:
            self._event_dispatcher.close()
          except Exception as e:
            self.log.warning(e)
        try:
          self.rpc_client.terminate()
        except Exception as e:
          self.log.warning(e)
