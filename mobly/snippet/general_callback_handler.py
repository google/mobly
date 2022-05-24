from mobly.snippet import callback_handler_base

# TODO: put the RPC protocol for pulling events

class GeneralCallbackHandler(callback_handler_base.CallbackHandlerBase):

  # TODO: rename this function with suffix RPC, and make it public
  def _callEventWaitAndGet(self, callback_id, event_name, timeout):
    """Calls snippet lib's eventWaitAndGet.

    Override this method to use this class with various snippet lib
    implementations.

    Args:
      callback_id: The callback identifier.
      event_name: The callback name.
      timeout: The number of seconds to wait for the event.

    Returns:
      The event dictionary.
    """
    timeout_ms = int(timeout * 1000)
    return self._event_client.eventWaitAndGet(callback_id, event_name,
                                              timeout_ms)

  # TODO: rename this function with suffix RPC, and make it public
  def _callEventGetAll(self, callback_id, event_name):
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
