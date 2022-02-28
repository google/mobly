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
import enum
import time
import contextlib

from mobly.controllers.android_device_lib import jsonrpc_client_base

# Maximum logging length of Rpc response in DEBUG level when verbose logging is
# off.
_MAX_RPC_RESP_LOGGING_LENGTH = 1024

# The required filed names of Rpc response.
RPC_RESPONSE_REQUIRED_FIELDS = ['id', 'error', 'result', 'callback']


class StartServerStages(enum.Enum):
  """The stages for the starting server process."""
  BEFORE_STARTING_SERVER = 1
  DO_START_SERVER = 2
  BUILD_CONNECTION = 3
  AFTER_STARTING_SERVER = 4


class ClientBase(abc.ABC):
  """Base class for Json Rpc clients that connect to remote servers.

  Connects to a remote device running a jsonrpc-compatible server. Call the
  function `start_server` to start the server on remote device before sending
  any rpc.  After sending all rpcs, call the function `stop_server` to stop
  all the running instances.

  Attributes:
    package: (str) The user-visible name of the snippet library being
      communicated with.
    host_port: (int) The host port of this RPC client.
    device_port: (int) The device port of this RPC client.
    log: (Logger) The logger of the corresponding device controller.
    verbose_logging: (bool) If True, prints more detailed log
      information. Default is False.
  """

  def __init__(self, package, device):
    """
    Args:
      package: (str) The user-visible name of the snippet library being
        communicated with.
      device: (DeviceController) The device object associated with a client.
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

  @contextlib.contextmanager
  def _execute_one_stage(self, stage, log_prefix, stop_server_if_failed):
    """Context manager for executing one stage.

    This context manager is responsible for logging stage information
    and stopping server if specified.

    Args:
      stage: (StartServerStages) The stage which is running under this
        context manager.
      log_prefix: (str) The prefix string of log information.
      stop_server_if_failed: (bool) Whether to stop server if this context
        manager catches an Exception.
    """
    start_stage_msg = f'{log_prefix}Running the stage %s.'
    finish_stage_msg = f'{log_prefix}Finished the stage %s.'
    error_msg = f'{log_prefix}Error in stage %s.'
    error_stop_server_msg = (f'{log_prefix}Failed to stop server after'
                             f'failure in stage %s.')

    self.log.debug(start_stage_msg, stage.name)
    try:
      yield
    except Exception:
      self.log.error(error_msg, stage.name)
      if stop_server_if_failed:
        try:
          self.stop_server()
        except Exception:
          self.log.exception(error_stop_server_msg, stage)

      raise

    self.log.debug(finish_stage_msg, stage.name)

  def start_server(self):
    """Starts the server on the remote device and connects to it.

    This process contains four stages:
      - before_starting_server: prepares for starting the server.
      - do_start_server: starts the server on the remote device.
      - build_connection: builds a connection with the server.
      - after_starting_server: does the things after the server is available.

    After this, the self.host_port and self.device_port attributes must be
    set.

    Raises:
      snippet_client.ProtocolVersionError: When the server's protocol is
        unknown.
      snippet_client.AppStartPreCheckError: When the precheck fails.
      jsonrpc_client_base.ProtocolError: When there's some error in
        the sending the handshake.
    """
    self.log.debug('Starting the server.')
    start_time = time.perf_counter()
    log_prefix = '[START_SERVER]'

    with self._execute_one_stage(StartServerStages.BEFORE_STARTING_SERVER,
                                 log_prefix, False):
      self.before_starting_server()

    with self._execute_one_stage(StartServerStages.DO_START_SERVER, log_prefix,
                                 True):
      self.do_start_server()

    with self._execute_one_stage(StartServerStages.BUILD_CONNECTION, log_prefix,
                                 True):
      self._build_connection()

    with self._execute_one_stage(StartServerStages.AFTER_STARTING_SERVER,
                                 log_prefix, True):
      self.after_starting_server()

    self.log.debug('Snippet %s started after %.1fs on host port %d.',
                   self.package,
                   time.perf_counter() - start_time, self.host_port)

  def before_starting_server(self):
    """Prepares for starting the server.

    For example, subclass can check or modify the device settings at this
    stage.

    Must be implemented by subclasses.
    """

  def do_start_server(self):
    """Starts the server on the remote device.

    The client has completed the preparations, so the client calls this
    function to start the server.

    Must be implemented by subclasses.
    """

  def _build_connection(self):
    """Proxy function to guarantee the base implementation of
    _build_connection is called.

    This function resets the RPC id counter before calling `build_connection`.
    """
    self._counter = self._id_counter()
    self.build_connection()

  def build_connection(self):
    """Builds a connection with the server on the remote device.

    The command to start the server has been already sent before calling this
    function. So the client builds a connection to it and sends a handshake
    to ensure the server is available for upcoming rpcs.

    This function uses self.host_port for communicating with the server. If
    self.host_port is 0 or None, this function finds an available host port to
    build connection and set self.host_port to the found port.

    Must be implemented by subclasses.
    """

  def after_starting_server(self):
    """Does the things after the server is available.

    For example, subclass can get device information from the server.

    Must be implemented by subclasses.
    """

  def __getattr__(self, name):
    """Wrapper for python magic to turn method calls into RPC calls."""

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
    """Switches verbose logging. True for logging full RPC response.

    By default it will write full message returned from Rpc. Turning off the
    verbose logging will result in wrting _MAX_RPC_RESP_LOGGING_LENGTH
    characters of each Rpc returned string.

    _MAX_RPC_RESP_LOGGING_LENGTH will set to 1024 by default, the length
    contains full Rpc response in Json format, included 1st element "id".

    Args:
      verbose: (bool) If True, turns on verbose logging, if False turns off.
    """
    self.log.info('Sets verbose logging to %s.', verbose)
    self.verbose_logging = verbose

  def restore_server_connection(self, port=None):
    """Reconnects to the server after device was disconnected.

    Instead of creating new instance of the client:
      - Uses the given port (or finds a new available host_port if none is
      given).
      - Tries to connect to remote server with selected port.

    Must be implemented by subclasses.

    Args:
      port: (int) If given, this is the host port from which to connect to
        remote device port. If not provided, find a new available port as host
        port.

    Raises:
      jsonrpc_client_base.AppRestoreConnectionError: When the server was not
      able to be reconnected.
    """

  def _rpc(self, rpc_func_name, *args, **kwargs):
    """Sends an rpc to the server.

    Args:
      rpc_func_name: (str) The name of the snippet function to execute on the
        server.
      args: (any) The positional arguments of the rpc request.
      kwargs: (any) The keyword arguments of the rpc request.

    Returns:
      The result of the rpc.

    Raises:
      jsonrpc_client_base.ProtocolError: Something went wrong with the
        protocol.
      jsonrpc_client_base.ApiError: The rpc went through, however executed with
        errors.
    """
    try:
      self.check_server_proc_running()
    except Exception:
      self.log.exception(
          'Server process running check failed, skip sending rpc method(%s).',
          rpc_func_name)
      raise

    with self._lock:
      rpc_id = next(self._counter)
      request = self._gen_rpc_request(rpc_id, rpc_func_name, *args, **kwargs)

      self.log.debug('Sending rpc request %s.', request)
      response = self.send_rpc_request(request)
      self.log.debug('Rpc request sent.')

      if self.verbose_logging or _MAX_RPC_RESP_LOGGING_LENGTH >= len(response):
        self.log.debug('Snippet received: %s', response)
      else:
        self.log.debug('Snippet received: %s... %d chars are truncated',
                       response[:_MAX_RPC_RESP_LOGGING_LENGTH],
                       len(response) - _MAX_RPC_RESP_LOGGING_LENGTH)

    return self._parse_rpc_response(rpc_id, rpc_func_name, response)

  def check_server_proc_running(self):
    """Checks whether the server is still running.

    If the server is not running, throws an error. As this function is called
    each time the client tries to send an rpc, this should be a quick check
    without affecting performance. Otherwise it is fine to not check anything.

    Must be implemented by subclasses.
    """

  def _gen_rpc_request(self, rpc_id, rpc_func_name, *args, **kwargs):
    """Generates Json rpc request.

    Args:
      rpc_id: (int) The id of this rpc.
      rpc_func_name: (str) The name of the snippet function to execute
        on server.
      args: (any) The positional arguments of the rpc.
      kwargs: (any) The keyword arguments of the rpc.

    Returns:
      A string of the Json rpc request.
    """
    data = {'id': rpc_id, 'method': rpc_func_name, 'params': args}
    if kwargs:
      data['kwargs'] = kwargs
    request = json.dumps(data)
    return request

  def send_rpc_request(self, request):
    """Sends Json rpc request to the server and gets response.

    Note that the request and response are both in string format. So if the
    connection with server provides interfaces in bytes format, please
    transform them to string in the implementation of this funcion.

    Must be implemented by subclasses.

    Args:
      request: (str) A string of the rpc request.

    Returns:
      A string of the rpc response.
    """

  def _parse_rpc_response(self, rpc_id, rpc_func_name, response):
    """Parses the rpc response from the server.

    This function parses the response of the server and checks the response
    with the Mobly JSON RPC Protocol.

    Args:
      rpc_id: (int) The actual id of this rpc. It should be the same with the id
        in the response, otherwise throws an error.
      rpc_func_name: (str) The name of the function that this rpc triggered
        on the snippet server.
      response: (str) A string of the Json rpc response.

    Returns:
      The result of the rpc. If sync rpc, returns the result field of
      the response. If async rpc, returns the callback handler object.

    Raises:
      jsonrpc_client_base.ProtocolError: Something went wrong with the
        protocol.
    """
    if not response:
      raise jsonrpc_client_base.ProtocolError(
          self._device,
          jsonrpc_client_base.ProtocolError.NO_RESPONSE_FROM_SERVER)

    result = json.loads(response)
    for field_name in RPC_RESPONSE_REQUIRED_FIELDS:
      if field_name not in result:
        raise jsonrpc_client_base.ProtocolError(
            self._device,
            jsonrpc_client_base.ProtocolError.RESPONSE_MISS_FIELD % field_name)

    if result['error']:
      raise jsonrpc_client_base.ApiError(self._device, result['error'])
    if result['id'] != rpc_id:
      raise jsonrpc_client_base.ProtocolError(
          self._device, jsonrpc_client_base.ProtocolError.MISMATCHED_API_ID)
    if result['callback'] is not None:
      return self.handle_callback(result['callback'], result['result'], rpc_func_name)
    return result['result']

  def handle_callback(self, callback_id, ret_value, rpc_func_name):
    """Creates callback handler for an async rpc.

    Must be implemented by subclasses.

    Args:
      callback_id: (str) The callback ID for creating callback handler object.
      ret_value: (str) JSON Array string of the result field of the rpc
        response.
      rpc_func_name: (str) The name of the snippet function executed on the
        server.

    Returns:
      The callback handler object.
    """

  def stop_server(self):
    """Proxy function to guarantee the base implementation of
    do_stop_server is called.
    """
    self.log.debug('Stopping snippet %s.', self.package)
    self.do_stop_server()
    self.log.debug('Snippet %s stopped.', self.package)

  def do_stop_server(self):
    """Kills any running instance of the server.

    Must be implemented by subclasses.
    """

  def close_connection(self):
    """Closes the connection to the snippet server on the device.

    This is a unilateral closing from the client side, without tearing down
    the snippet server running on the device.

    The connection to the snippet server can be re-established by calling
    `restore_server_connection`.

    Must be implemented by subclasses.
    """
