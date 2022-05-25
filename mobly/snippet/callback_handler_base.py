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

import abc
import time

from mobly.snippet import errors
from mobly.snippet import snippet_event


# TODO: modify all the docstring
class CallbackHandlerBase(abc.ABC):
  """The class used to handle a specific group of callback events.

  All the events handled by a CallbackHandler are originally triggered by one
  async Rpc call. All the events are tagged with a callback_id specific to a
  call to an AsyncRpc method defined on the server side.

  The raw message representing an event looks like:

  .. code-block:: python

    {
      'callbackId': <string, callbackId>,
      'name': <string, name of the event>,
      'time': <long, epoch time of when the event was created on the
        server side>,
      'data': <dict, extra data from the callback on the server side>
    }

  Each message is then used to create a SnippetEvent object on the client
  side.

  Attributes:
    ret_value: The direct return value of the async RPC call.
    method_name: The name of the async RPC function.
  """

  def __init__(self, callback_id, event_client, ret_value, method_name, device,
               rpc_max_timeout_sec, default_timeout_sec=120):
    self._id = callback_id
    self._event_client = event_client
    self.ret_value = ret_value
    self.method_name = method_name
    self._device = device

    if rpc_max_timeout_sec < default_timeout_sec:
      raise ValueError('The max timeout of single RPC must be no smaller than '
                       'the default timeout of the callback handler. '
                       f'Got rpc_max_timeout_sec={rpc_max_timeout_sec}, '
                       f'default_timeout_sec={default_timeout_sec}.')
    self._rpc_max_timeout_sec = rpc_max_timeout_sec
    self._default_timeout_sec = default_timeout_sec

  @property
  def rpc_max_timeout_sec(self):
    return self._rpc_max_timeout_sec

  @property
  def default_timeout_sec(self):
    return self._default_timeout_sec

  @property
  def callback_id(self):
    return self._id

  @abc.abstractmethod
  def callEventWaitAndGetRpc(self, callback_id, event_name, timeout_sec):
    """Calls snippet lib's eventWaitAndGet.

    Override this method to use this class with various snippet lib
    implementations.

    Args:
      callback_id: The callback identifier.
      event_name: The callback name.
      timeout_sec: The number of seconds to wait for the event.

    Returns:
      The event dictionary.
    """

  @abc.abstractmethod
  def callEventGetAllRpc(self, callback_id, event_name):
    """Calls snippet lib's eventGetAll.

    Override this method to use this class with various snippet lib
    implementations.

    Args:
      callback_id: The callback identifier.
      event_name: The callback name.

    Returns:
      A list of event dictionaries.
    """

  def waitAndGet(self, event_name, timeout=None):
    """Blocks until an event of the specified name has been received and
    return the event, or timeout.

    Args:
      event_name: string, name of the event to get.
      timeout: float, the number of seconds to wait before giving up.

    Returns:
      SnippetEvent, the oldest entry of the specified event.

    Raises:
      errors.CallbackHandlerBaseError: If the specified timeout is longer than the max timeout
        supported.
     errors.CallbackHandlerTimeoutError: The expected event does not occur within time limit.
    """
    if timeout is None:
      timeout = self.default_timeout_sec

    if timeout:
      if timeout > self.rpc_max_timeout_sec:
        raise errors.CallbackHandlerBaseError(
            self._device,
            f'Specified timeout {timeout} is longer than max timeout '
            f'{self.rpc_max_timeout_sec}.')

    raw_event = self.callEventWaitAndGetRpc(self._id, event_name, timeout)
    return snippet_event.from_dict(raw_event)

  def waitForEvent(self, event_name, predicate, timeout=None):
    """Wait for an event of a specific name that satisfies the predicate.

    This call will block until the expected event has been received or time
    out.

    The predicate function defines the condition the event is expected to
    satisfy. It takes an event and returns True if the condition is
    satisfied, False otherwise.

    Note all events of the same name that are received but don't satisfy
    the predicate will be discarded and not be available for further
    consumption.

    Args:
      event_name: string, the name of the event to wait for.
      predicate: function, a function that takes an event (dictionary) and
        returns a bool.
      timeout: float, will be set to self.default_timeout_sec if None .

    Returns:
      dictionary, the event that satisfies the predicate if received.

    Raises:
     errors.CallbackHandlerTimeoutError: raised if no event that satisfies the predicate is
        received after timeout seconds.
    """
    if timeout is None:
      timeout = self.default_timeout_sec

    deadline = time.perf_counter() + timeout
    while (single_rpc_timeout := deadline - time.perf_counter()) > 0:
      # A single RPC call cannot exceed the max timeout of a single rpc.
      single_rpc_timeout = min(single_rpc_timeout, self.rpc_max_timeout_sec)
      try:
        event = self.waitAndGet(event_name, single_rpc_timeout)
      except errors.CallbackHandlerTimeoutError:
        # Ignoring errors.CallbackHandlerTimeoutError since we need to throw one with a more
        # specific message.
        break
      if predicate(event):
        return event

    raise errors.CallbackHandlerTimeoutError(
        self._device,
        f'Timed out after {timeout}s waiting for an "{event_name}" event that '
        f'satisfies the predicate "{predicate.__name__}".')

  def getAll(self, event_name):
    """Gets all the events of a certain name that have been received so
    far. This is a non-blocking call.

    Args:
      callback_id: The id of the callback.
      event_name: string, the name of the event to get.

    Returns:
      A list of SnippetEvent, each representing an event from the Java
      side.
    """
    raw_events = self.callEventGetAllRpc(self._id, event_name)
    return [snippet_event.from_dict(msg) for msg in raw_events]
