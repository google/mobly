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
"""A general handler class for Mobly Snippet Lib's callback events."""
import re

from mobly.snippet import callback_handler_base
from mobly.snippet import errors

# TODO: make it a enum
# class SnippetTimeoutErrorMessagePattern(enum.Enum):
  # ANDROID = '.*EventSnippetException: timeout\\..*'
  # WINDOWS = '.*Timeout has been reached but no SnippetEvent occurred\\..*'

ANDROID_SNIPPET_TIMEOUT_MESSAGE_PATTERN = '.*EventSnippetException: timeout\\..*'


class GeneralCallbackHandler(callback_handler_base.CallbackHandlerBase):
  """A general handler class for Mobly Snippet Lib's callback events."""

  def __init__(self,
               callback_id,
               event_client,
               ret_value,
               method_name,
               device,
               rpc_max_timeout_sec,
               default_timeout_sec=120,
               timeout_msg_pattern=None):
    """Initializes a general callback handler object.

    Args:
      callback_id: str, the callback identifier.
      event_client: SnippetClientV2, The client object used to send RPC to the
        server and receive response.
      ret_value: any, the direct return value of the async RPC call.
      method_name: str, the name of the executed Async snippet function.
      device: DeviceController, the device object associated with this handler.
      rpc_max_timeout_sec: float, maximum time for sending a single RPC call.
      default_timeout_sec: float, the default timeout for this handler. It
        must be no longer than rpc_max_timeout_sec.
      timeout_msg_pattern: SnippetTimeoutErrorMessagePattern, the regex search pattern for timeout error
        message. When error occurs in the RPC for pulling events, this class uses
        this regex pattern to decide whether it is a timeout error. For
        a timeout error, we will raise a new error of specific error class.
    """
    super().__init__(callback_id, ret_value, device, rpc_max_timeout_sec,
                     default_timeout_sec)
    self._method_name = method_name
    self._event_client = event_client
    self._timeout_msg_pattern = timeout_msg_pattern

  def callEventWaitAndGetRpc(self, callback_id, event_name, timeout_sec):
    """Waits and returns an existing SnippetEvent for the specified identifier.

    This function calls snippet lib's eventWaitAndGet RPC.

    Args:
      callback_id: str, the callback identifier.
      event_name: str, the callback name.
      timeout_sec: float, the number of seconds to wait for the event.

    Returns:
      The event dictionary.

    Raises:
      errors.CallbackHandlerTimeoutError: The expected event does not occur
        within time limit.
    """
    timeout_ms = int(timeout_sec * 1000)
    try:
      return self._event_client.eventWaitAndGet(callback_id, event_name,
                                                timeout_ms)
    except Exception as e:
      if not self._timeout_msg_pattern:
        raise

      search_result = re.search(self._timeout_msg_pattern.value, str(e))
      if not search_result:
        raise

      raise errors.CallbackHandlerTimeoutError(
          self._device,
          f'Timed out after waiting {timeout_sec}s for event "{event_name}" '
          f'triggered by {self._method_name} ({self.callback_id}).',
      ) from e

  def callEventGetAllRpc(self, callback_id, event_name):
    """Gets all existing events for the specified identifier without waiting.

    This function calls snippet lib's eventGetAll RPC.

    Args:
      callback_id: str, the callback identifier.
      event_name: str, the callback name.

    Returns:
      A list of event dictionaries.
    """
    return self._event_client.eventGetAll(callback_id, event_name)