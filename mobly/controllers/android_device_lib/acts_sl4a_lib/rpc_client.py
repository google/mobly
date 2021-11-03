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
import time
from concurrent import futures

from mobly.controllers.android_device_lib.acts_sl4a_lib import logger

# The default timeout value when no timeout is set.
SOCKET_TIMEOUT = 60

# The Session UID when a UID has not been received yet.
UNKNOWN_UID = -1


class Sl4aException(Exception):
  """The base class for all SL4A exceptions."""


class Sl4aStartError(Sl4aException):
  """Raised when sl4a is not able to be started."""


class Sl4aApiError(Sl4aException):
  """Raised when remote API reports an error.

  This error mirrors the JSON-RPC 2.0 spec for Error Response objects.

  Attributes:
      code: The error code returned by SL4A. Not to be confused with
          ActsError's error_code.
      message: The error message returned by SL4A.
      data: The extra data, if any, returned by SL4A.
  """

  def __init__(self, message, code=-1, data=None, rpc_name=''):
    super().__init__()
    self.message = message
    self.code = code
    if data is None:
      self.data = {}
    else:
      self.data = data
    self.rpc_name = rpc_name

  def __str__(self):
    if self.data:
      return 'Error in RPC %s %s:%s:%s' % (self.rpc_name, self.code,
                                           self.message, self.data)
    else:
      return 'Error in RPC %s %s:%s' % (self.rpc_name, self.code,
                                        self.message)


class Sl4aConnectionError(Sl4aException):
  """An error raised upon failure to connect to SL4A."""


class Sl4aProtocolError(Sl4aException):
  """Raised when there an error in exchanging data with server on device."""
  NO_RESPONSE_FROM_HANDSHAKE = 'No response from handshake.'
  NO_RESPONSE_FROM_SERVER = 'No response from server.'
  MISMATCHED_API_ID = 'Mismatched API id.'


class Sl4aNotInstalledError(Sl4aException):
  """An error raised when an Sl4aClient is created without SL4A installed."""


class Sl4aRpcTimeoutError(Sl4aException):
  """An error raised when an SL4A RPC has timed out."""


class RpcClient(object):
  """An RPC client capable of processing multiple RPCs concurrently.

  Attributes:
      _free_connections: A list of all idle RpcConnections.
      _working_connections: A list of all working RpcConnections.
      _lock: A lock used for accessing critical memory.
      max_connections: The maximum number of RpcConnections at a time.
          Increasing or decreasing the number of max connections does NOT
          modify the thread pool size being used for self.future RPC calls.
      _log: The logger for this RpcClient.
  """
  """The default value for the maximum amount of connections for a client."""
  DEFAULT_MAX_CONNECTION = 15

  class AsyncClient(object):
    """An object that allows RPC calls to be called asynchronously.

    Attributes:
        _rpc_client: The RpcClient to use when making calls.
        _executor: The ThreadPoolExecutor used to keep track of workers
    """

    def __init__(self, rpc_client):
      self._rpc_client = rpc_client
      self._executor = futures.ThreadPoolExecutor(
        max_workers=max(rpc_client.max_connections - 2, 1))

    def rpc(self, name, *args, **kwargs):
      future = self._executor.submit(name, *args, **kwargs)
      return future

    def __getattr__(self, name):
      """Wrapper for python magic to turn method calls into RPC calls."""

      def rpc_call(*args, **kwargs):
        future = self._executor.submit(
          self._rpc_client.__getattr__(name), *args, **kwargs)
        return future

      return rpc_call

  def __init__(self,
               uid,
               serial,
               on_error_callback,
               _create_connection_func,
               max_connections=None):
    """Creates a new RpcClient object.

    Args:
        uid: The session uid this client is a part of.
        serial: The serial of the Android device. Used for logging.
        on_error_callback: A callback for when a connection error is raised.
        _create_connection_func: A reference to the function that creates a
            new session.
        max_connections: The maximum number of connections the RpcClient
            can have.
    """
    self._serial = serial
    self.on_error = on_error_callback
    self._create_connection_func = _create_connection_func
    self._free_connections = [self._create_connection_func(uid)]

    self.uid = self._free_connections[0].uid
    self._lock = threading.Lock()

    self._log = logger.create_tagged_logger(
      'RPC Service|%s|%s' % (self._serial, self.uid))

    self._working_connections = []
    if max_connections is None:
      self.max_connections = RpcClient.DEFAULT_MAX_CONNECTION
    else:
      self.max_connections = max_connections

    self._async_client = RpcClient.AsyncClient(self)
    self.is_alive = True

  def terminate(self):
    """Terminates all connections to the SL4A server."""
    if len(self._working_connections) > 0:
      self._log.warning(
        '%s connections are still active, and waiting on '
        'responses.Closing these connections now.' % len(
          self._working_connections))
    connections = self._free_connections + self._working_connections
    for connection in connections:
      self._log.debug(
        'Closing connection over ports %s' % connection.ports)
      connection.close()
    self._free_connections = []
    self._working_connections = []
    self.is_alive = False

  def _get_free_connection(self):
    """Returns a free connection to be used for an RPC call.

    This function also adds the client to the working set to prevent
    multiple users from obtaining the same client.
    """
    while True:
      if len(self._free_connections) > 0:
        with self._lock:
          # Check if another thread grabbed the remaining connection.
          # while we were waiting for the lock.
          if len(self._free_connections) == 0:
            continue
          client = self._free_connections.pop()
          self._working_connections.append(client)
          return client

      client_count = (len(self._free_connections) +
                      len(self._working_connections))
      if client_count < self.max_connections:
        with self._lock:
          client_count = (len(self._free_connections) +
                          len(self._working_connections))
          if client_count < self.max_connections:
            client = self._create_connection_func(self.uid)
            self._working_connections.append(client)
            return client
      time.sleep(.01)

  def _release_working_connection(self, connection):
    """Marks a working client as free.

    Args:
        connection: The client to mark as free.
    Raises:
        A ValueError if the client is not a known working connection.
    """
    # We need to keep this code atomic because the client count is based on
    # the length of the free and working connection list lengths.
    with self._lock:
      self._working_connections.remove(connection)
      self._free_connections.append(connection)

  def rpc(self, method, *args, timeout=None, retries=3):
    """Sends an rpc to sl4a.

    Sends an rpc call to sl4a over this RpcClient's corresponding session.

    Args:
        method: str, The name of the method to execute.
        args: any, The args to send to sl4a.
        timeout: The amount of time to wait for a response.
        retries: Misnomer, is actually the number of tries.

    Returns:
        The result of the rpc.

    Raises:
        Sl4aProtocolError: Something went wrong with the sl4a protocol.
        Sl4aApiError: The rpc went through, however executed with errors.
    """
    connection = self._get_free_connection()
    ticket = connection.get_new_ticket()
    timed_out = False
    if timeout:
      connection.set_timeout(timeout)
    data = {'id': ticket, 'method': method, 'params': args}
    request = json.dumps(data)
    response = ''
    try:
      for i in range(1, retries + 1):
        connection.send_request(request)

        response = connection.get_response()
        if not response:
          if i < retries:
            self._log.warning(
              'No response for RPC method %s on iteration %s',
              method, i)
            continue
          else:
            self._log.exception(
              'No response for RPC method %s on iteration %s',
              method, i)
            self.on_error(connection)
            raise Sl4aProtocolError(
              Sl4aProtocolError.NO_RESPONSE_FROM_SERVER)
        else:
          break
    except BrokenPipeError as e:
      if self.is_alive:
        self._log.exception('The device disconnected during RPC call '
                            '%s. Please check the logcat for a crash '
                            'or disconnect.', method)
        self.on_error(connection)
      else:
        self._log.warning('The connection was killed during cleanup:')
        self._log.warning(e)
      raise Sl4aConnectionError(e)
    except socket.timeout as err:
      # If a socket connection has timed out, the socket can no longer be
      # used. Close it out and remove the socket from the connection pool.
      timed_out = True
      self._log.warning('RPC "%s" (id: %s) timed out after %s seconds.',
                        method, ticket, timeout or SOCKET_TIMEOUT)
      self._log.debug(
        'Closing timed out connection over %s' % connection.ports)
      connection.close()
      self._working_connections.remove(connection)
      # Re-raise the error as an SL4A Error so end users can process it.
      raise Sl4aRpcTimeoutError(err)
    finally:
      if not timed_out:
        if timeout:
          connection.set_timeout(SOCKET_TIMEOUT)
        self._release_working_connection(connection)
    result = json.loads(str(response, encoding='utf8'))

    if result['error']:
      error_object = result['error']
      if isinstance(error_object, dict):
        # Uses JSON-RPC 2.0 Format
        sl4a_api_error = Sl4aApiError(error_object.get('message', None),
                                      error_object.get('code', -1),
                                      error_object.get('data', {}),
                                      rpc_name=method)
      else:
        # Fallback on JSON-RPC 1.0 Format
        sl4a_api_error = Sl4aApiError(error_object, rpc_name=method)
      self._log.warning(sl4a_api_error)
      raise sl4a_api_error
    if result['id'] != ticket:
      self._log.error('RPC method %s with mismatched api id %s', method,
                      result['id'])
      raise Sl4aProtocolError(Sl4aProtocolError.MISMATCHED_API_ID)
    return result['result']

  @property
  def future(self):
    """Returns a magic function that returns a future running an RPC call.

    This function effectively allows the idiom:

    >>> rpc_client = RpcClient(...)
    >>> # returns after call finishes
    >>> rpc_client.someRpcCall()
    >>> # Immediately returns a reference to the RPC's future, running
    >>> # the lengthy RPC call on another thread.
    >>> future = rpc_client.future.someLengthyRpcCall()
    >>> rpc_client.doOtherThings()
    >>> ...
    >>> # Wait for and get the returned value of the lengthy RPC.
    >>> # Can specify a timeout as well.
    >>> value = future.result()

    The number of concurrent calls to this method is limited to
    (max_connections - 2), to prevent future calls from exhausting all free
    connections.
    """
    return self._async_client

  def __getattr__(self, name):
    """Wrapper for python magic to turn method calls into RPC calls."""

    def rpc_call(*args, **kwargs):
      return self.rpc(name, *args, **kwargs)

    if not self.is_alive:
      raise Sl4aStartError(
        'This SL4A session has already been terminated. You must '
        'create a new session to continue.')
    return rpc_call
