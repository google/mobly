import re

from mobly.snippet import errors
from mobly.snippet import callback_handler_base

ANDROID_SNIPPET_TIMEOUT_MESSAGE_PATTERN = '.*EventSnippetException: timeout\\..*'


class GeneralCallbackHandler(callback_handler_base.CallbackHandlerBase):

  def __init__(self, callback_id, event_client, ret_value, method_name, device,
               rpc_max_timeout_sec=None, default_timeout_sec=120,
               timeout_msg_pattern=None):
    super().__init__(callback_id, event_client, ret_value, method_name, device,
                     rpc_max_timeout_sec, default_timeout_sec)
    self._timeout_msg_pattern = timeout_msg_pattern

  # TODO: Raises in docstring
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
    timeout_ms = int(timeout_sec * 1000)
    try:
      return self._event_client.eventWaitAndGet(callback_id,
                                                event_name,
                                                timeout_ms)
    except Exception as e:
      if (self._timeout_msg_pattern and
          re.match(self._timeout_msg_pattern, str(e))):
        raise errors.CallbackHandlerTimeoutError(
            self._device,
            f'Timed out after waiting {timeout_sec}s for event "{event_name}" '
            f'triggered by {self.method_name} ({self.callback_id}).',
        ) from e
      raise

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
    return self._event_client.eventGetAll(callback_id, event_name)
