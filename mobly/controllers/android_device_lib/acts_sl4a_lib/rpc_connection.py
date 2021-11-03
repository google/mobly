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
import json
import socket
import threading

from mobly.controllers.android_device_lib.acts_sl4a_lib import logger
from mobly.controllers.android_device_lib.acts_sl4a_lib import rpc_client

# The Session UID when a UID has not been received yet.
UNKNOWN_UID = -1


class Sl4aConnectionCommand(object):
  """Commands that can be invoked on the sl4a client.

  INIT: Initializes a new sessions in sl4a.
  CONTINUE: Creates a connection.
  """
  INIT = 'initiate'
  CONTINUE = 'continue'


class RpcConnection(object):
  """A single RPC Connection thread.

  Attributes:
      _client_socket: The socket this connection uses.
      _socket_file: The file created over the _client_socket.
      _ticket_counter: The counter storing the current ticket number.
      _ticket_lock: A lock on the ticket counter to prevent ticket collisions.
      adb: A reference to the AdbProxy of the AndroidDevice. Used for logging.
      log: The logger for this RPC Client.
      ports: The Sl4aPorts object that stores the ports this connection uses.
      uid: The SL4A session ID.
  """

  def __init__(self, adb, ports, client_socket, socket_fd, uid=UNKNOWN_UID):
    self._client_socket = client_socket
    self._socket_file = socket_fd
    self._ticket_counter = 0
    self._ticket_lock = threading.Lock()
    self.adb = adb
    self.uid = uid
    self.ports = ports

    self.log = logger.create_tagged_logger(
      'SL4A Client|%s|%s|%s' % (self.adb.serial, self.ports.client_port,
                                self.uid))

    self.set_timeout(rpc_client.SOCKET_TIMEOUT)

  def open(self):
    if self.uid != UNKNOWN_UID:
      start_command = Sl4aConnectionCommand.CONTINUE
    else:
      start_command = Sl4aConnectionCommand.INIT

    self._initiate_handshake(start_command)

  def _initiate_handshake(self, start_command):
    """Establishes a connection with the SL4A server.

    Args:
        start_command: The command to send. See Sl4aConnectionCommand.
    """
    try:
      resp = self._cmd(start_command)
    except socket.timeout as e:
      self.log.error('Failed to open socket connection: %s', e)
      raise
    if not resp:
      raise rpc_client.Sl4aProtocolError(
        rpc_client.Sl4aProtocolError.NO_RESPONSE_FROM_HANDSHAKE)
    result = json.loads(str(resp, encoding='utf8'))
    if result['status']:
      self.uid = result['uid']
    else:
      self.log.warning(
        'UID not received for connection %s.' % self.ports)
      self.uid = UNKNOWN_UID
    self.log.debug('Created connection over: %s.' % self.ports)

  def _cmd(self, command):
    """Sends an session protocol command to SL4A to establish communication.

    Args:
        command: The name of the command to execute.

    Returns:
        The line that was written back.
    """
    self.send_request(json.dumps({'cmd': command, 'uid': self.uid}))
    return self.get_response()

  def get_new_ticket(self):
    """Returns a ticket for a new request."""
    with self._ticket_lock:
      self._ticket_counter += 1
      ticket = self._ticket_counter
    return ticket

  def set_timeout(self, timeout):
    """Sets the socket's wait for response timeout."""
    self._client_socket.settimeout(timeout)

  def send_request(self, request):
    """Sends a request over the connection."""
    self._socket_file.write(request.encode('utf8') + b'\n')
    self._socket_file.flush()
    self.log.debug('Sent: ' + request)

  def get_response(self):
    """Returns the first response sent back to the client."""
    data = self._socket_file.readline()
    self.log.debug('Received: ' + data.decode('utf8', errors='replace'))
    return data

  def close(self):
    """Closes the connection gracefully."""
    self._client_socket.close()
    self.adb.remove_tcp_forward(self.ports.forwarded_port)
