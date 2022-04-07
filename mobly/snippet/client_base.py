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
"""The JSON RPC client base for communicating with snippet servers.

The JSON RPC protocol expected by this module is:

.. code-block:: json

  Request:
  {
    'id': <Required. Monotonically increasing integer containing the ID of this
          request.>,
    'method': <Required. String containing the name of the method to execute.>,
    'params': <Required. JSON array containing the arguments to the method,
              `null` if no positional arguments for the RPC method.>,
    'kwargs': <Optional. JSON dict containing the keyword arguments for the
              method, `null` if no positional arguments for the RPC method.>,
  }

  Response:
  {
    'error': <Required. String containing the error thrown by executing the
             method, `null` if no error occurred.>,
    'id': <Required. Int id of request that this response maps to.>,
    'result': <Required. Arbitrary JSON object containing the result of
              executing the method, `null` if the method could not be executed
              or returned void.>,
    'callback': <Required. String that represents a callback ID used to
                identify events associated with a particular CallbackHandler
                object, `null` if this is not a async RPC.>,
  }
"""

import abc
import json
import threading
import time

from mobly.snippet import errors

# Maximum logging length of RPC response in DEBUG level when verbose logging is
# off.
_MAX_RPC_RESP_LOGGING_LENGTH = 1024

# The required field names of RPC response.
RPC_RESPONSE_REQUIRED_FIELDS = ('id', 'error', 'result', 'callback')


class ClientBase(abc.ABC):
  """Base class for JSON RPC clients that connect to snippet servers.

  Connects to a remote device running a JSON RPC compatible server. Users call
  the function `start_server` to start the server on the remote device before
  sending any RPC. After sending all RPCs, users call the function `stop_server`
  to stop all the running instances.

  Attributes:
    package: str, the user-visible name of the snippet library being
      communicated with.
    host_port: int, the host port of this RPC client.
    device_port: int, the device port of this RPC client.
    log: Logger, the logger of the corresponding device controller.
    verbose_logging: bool, if True, prints more detailed log
      information. Default is True.
  """

  def __init__(self, package, device):
    """Initializes the instance of ClientBase.

    Args:
      package: str, the user-visible name of the snippet library being
        communicated with.
      device: DeviceController, the device object associated with a client.
    """

    self.package = package
    self.host_port = None
    self.device_port = None
    self.log = device.log
    self.verbose_logging = True
    self._device = device
    self._counter = None
    self._lock = threading.Lock()
    self._event_client = None

  def __del__(self):
    self.close_connection()

  def initialize(self):
    """Initializes the snippet client to interact with the remote device.

    This function contains following stages:
      1. preparing to start the snippet server.
      2. starting the snippet server on the remote device.
      3. making a connection to the snippet server.

    After this, the self.host_port and self.device_port attributes must be
    set.

    Raises:
      errors.ProtocolError: something went wrong when exchanging data with the
        server.
      errors.ServerStartPreCheckError: when prechecks for starting the server
        failed.
      errors.ServerStartError: when failed to start the snippet server.
    """

    self.log.debug('Initializing the snippet package %s.', self.package)
    start_time = time.perf_counter()

    self.log.debug('Preparing to start the snippet server of %s.',
                   self.package)
    self.before_starting_server()

    try:
      self.log.debug('Starting the snippet server of %s.', self.package)
      self.start_server()

      self.log.debug('Making a connection to the snippet server of %s.',
                     self.package)
      self._make_connection()

    except Exception:
      self.log.error(
          'Error occurs when initializing the snippet server of %s.',
          self.package)
      try:
        self.stop_server()
      except Exception:  # pylint: disable=broad-except
        # Only prints this exception and re-raises the original exception
        self.log.exception(
            'Failed to stop the snippet server of %s because of new exception.',
            self.package)

      raise

    self.log.debug('Snippet package %s initialized after %.1fs on host port %d.',
                   self.package,
                   time.perf_counter() - start_time, self.host_port)

  @abc.abstractmethod
  def before_starting_server(self):
    """Performs the preparation steps before starting the remote server.

    For example, subclass can check or modify the device settings at this
    stage.

    Raises:
      errors.ServerStartPreCheckError: when prechecks for starting the server
        failed.
    """

  @abc.abstractmethod
  def start_server(self):
    """Starts the server on the remote device.

    The client has completed the preparations, so the client calls this
    function to start the server.
    """

  def _make_connection(self):
    """Proxy function of make_connection.

    This function resets the RPC id counter before calling `make_connection`.
    """
    self._counter = self._id_counter()
    self.make_connection()

  @abc.abstractmethod
  def make_connection(self):
    """Makes a connection to the server on the remote device.

    This function makes a connection to the server and sends a handshake
    request to ensure the server is available for upcoming RPCs.

    There are two types of connections used by snippet clients:
    * the client builds a connection each time it wants to send a RPC,
    * the client builds a connection in this stage and uses it for all the RPCs.
      In this way, the client should implement `close_connection` to close
      the connection.

    This function uses self.host_port for communicating with the server. If
    self.host_port is 0 or None, this function finds an available host port to
    make the connection and set self.host_port to the found port.

    Raises:
      errors.ProtocolError: something went wrong when exchanging data with the
        server.
    """

  def __getattr__(self, name):
    """Wrapper for python magic to turn method calls into RPCs."""

    def rpc_call(*args, **kwargs):
      return self._rpc(name, *args, **kwargs)

    return rpc_call

  def _id_counter(self):
    """Returns an id generator."""
    i = 0
    while True:
      yield i
      i += 1

  def set_snippet_client_verbose_logging(self, verbose):
    """Switches verbose logging. True for logging full RPC responses.

    By default it will write full messages returned from RPCs. Turning off the
    verbose logging will result in writing no more than
    _MAX_RPC_RESP_LOGGING_LENGTH characters per RPC returned string.

    _MAX_RPC_RESP_LOGGING_LENGTH will be set to 1024 by default. The length
    contains the full RPC response in JSON format, not just the RPC result
    field.

    Args:
      verbose: bool, if True, turns on verbose logging, otherwise turns off.
    """
    self.log.info('Sets verbose logging to %s.', verbose)
    self.verbose_logging = verbose

  @abc.abstractmethod
  def restore_server_connection(self, port=None):
    """Reconnects to the server after the device was disconnected.

    Instead of creating a new instance of the client:
      - Uses the given port (or finds a new available host_port if 0 or None is
      given).
      - Tries to connect to the remote server with the selected port.

    Args:
      port: int, if given, this is the host port from which to connect to the
        remote device port. Otherwise, finds a new available port as host
        port.

    Raises:
      errors.ServerRestoreConnectionError: when failed to restore the connection
        to the snippet server.
    """

  def _rpc(self, rpc_func_name, *args, **kwargs):
    """Sends a RPC to the server.

    Args:
      rpc_func_name: str, the name of the snippet function to execute on the
        server.
      *args: any, the positional arguments of the RPC request.
      **kwargs: any, the keyword arguments of the RPC request.

    Returns:
      The result of the RPC.

    Raises:
      errors.ProtocolError: something went wrong when exchanging data with the
        server.
      errors.ApiError: the RPC went through, however executed with errors.
    """
    try:
      self.check_server_proc_running()
    except Exception:
      self.log.error(
          'Server process running check failed, skip sending RPC method(%s).',
          rpc_func_name)
      raise

    with self._lock:
      rpc_id = next(self._counter)
      request = self._gen_rpc_request(rpc_id, rpc_func_name, *args, **kwargs)

      self.log.debug('Sending RPC request %s.', request)
      response = self.send_rpc_request(request)
      self.log.debug('RPC request sent.')

      if self.verbose_logging or _MAX_RPC_RESP_LOGGING_LENGTH >= len(response):
        self.log.debug('Snippet received: %s', response)
      else:
        self.log.debug('Snippet received: %s... %d chars are truncated',
                       response[:_MAX_RPC_RESP_LOGGING_LENGTH],
                       len(response) - _MAX_RPC_RESP_LOGGING_LENGTH)

    response_decoded = self._decode_response_string_and_validate_format(
        rpc_id, response)
    return self._handle_rpc_response(rpc_func_name, response_decoded)

  @abc.abstractmethod
  def check_server_proc_running(self):
    """Checks whether the server is still running.

    If the server is not running, it throws an error. As this function is called
    each time the client tries to send a RPC, this should be a quick check
    without affecting performance. Otherwise it is fine to not check anything.

    Raises:
      errors.ServerDiedError: if the server died.
    """

  def _gen_rpc_request(self, rpc_id, rpc_func_name, *args, **kwargs):
    """Generates the JSON RPC request.

    In the generated JSON string, the fields are sorted by keys in ascending
    order.

    Args:
      rpc_id: int, the id of this RPC.
      rpc_func_name: str, the name of the snippet function to execute
        on the server.
      *args: any, the positional arguments of the RPC.
      **kwargs: any, the keyword arguments of the RPC.

    Returns:
      A string of the JSON RPC request.
    """
    data = {'id': rpc_id, 'method': rpc_func_name, 'params': args}
    if kwargs:
      data['kwargs'] = kwargs
    return json.dumps(data, sort_keys=True)

  @abc.abstractmethod
  def send_rpc_request(self, request):
    """Sends the JSON RPC request to the server and gets a response.

    Note that the request and response are both in string format. So if the
    connection with server provides interfaces in bytes format, please
    transform them to string in the implementation of this function.

    Args:
      request: str, a string of the RPC request.

    Returns:
      A string of the RPC response.

    Raises:
      errors.ProtocolError: something went wrong when exchanging data with the
        server.
    """

  def _decode_response_string_and_validate_format(self, rpc_id, response):
    """Decodes response JSON string to python dict and validates its format.

    Args:
      rpc_id: int, the actual id of this RPC. It should be the same with the id
        in the response, otherwise throws an error.
      response: str, the JSON string of the RPC response.

    Returns:
      A dict decoded from the response JSON string.

    Raises:
      errors.ProtocolError: if the response format is invalid.
    """
    if not response:
      raise errors.ProtocolError(self._device,
                                 errors.ProtocolError.NO_RESPONSE_FROM_SERVER)

    result = json.loads(response)
    for field_name in RPC_RESPONSE_REQUIRED_FIELDS:
      if field_name not in result:
        raise errors.ProtocolError(
            self._device,
            errors.ProtocolError.RESPONSE_MISSING_FIELD % field_name)

    if result['id'] != rpc_id:
      raise errors.ProtocolError(self._device,
                                 errors.ProtocolError.MISMATCHED_API_ID)

    return result

  def _handle_rpc_response(self, rpc_func_name, response):
    """Handles the content of RPC response.

    If the RPC response contains error information, it throws an error. If the
    RPC is asynchronous, it creates and returns a callback handler
    object. Otherwise, it returns the result field of the response.

    Args:
      rpc_func_name: str, the name of the snippet function that this RPC
        triggered on the snippet server.
      response: dict, the object decoded from the response JSON string.

    Returns:
      The result of the RPC. If synchronous RPC, it is the result field of the
      response. If asynchronous RPC, it is the callback handler object.

    Raises:
      errors.ApiError: if the snippet function executed with errors.
    """

    if response['error']:
      raise errors.ApiError(self._device, response['error'])
    if response['callback'] is not None:
      return self.handle_callback(response['callback'], response['result'],
                                  rpc_func_name)
    return response['result']

  @abc.abstractmethod
  def handle_callback(self, callback_id, ret_value, rpc_func_name):
    """Creates a callback handler for the asynchronous RPC.

    Args:
      callback_id: str, the callback ID for creating a callback handler object.
      ret_value: any, the result field of the RPC response.
      rpc_func_name: str, the name of the snippet function executed on the
        server.

    Returns:
      The callback handler object.
    """

  def stop_server(self):
    """Proxy function of do_stop_server."""
    self.log.debug('Stopping snippet %s.', self.package)
    self.do_stop_server()
    self.log.debug('Snippet %s stopped.', self.package)

  @abc.abstractmethod
  def do_stop_server(self):
    """Kills any running instance of the server."""

  @abc.abstractmethod
  def close_connection(self):
    """Closes the connection to the snippet server on the device.

    This is a unilateral closing from the client side, without tearing down
    the snippet server running on the device.

    The connection to the snippet server can be re-established by calling
    `restore_server_connection`.
    """
