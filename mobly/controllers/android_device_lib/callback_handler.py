# Copyright 2017 Google Inc.
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

import time

from mobly.controllers.android_device_lib import errors
from mobly.controllers.android_device_lib import snippet_event

# The max timeout cannot be larger than the max time the socket waits for a
# response message. Otherwise, the socket would timeout before the Rpc call
# does, leaving both server and client in unknown states.
MAX_TIMEOUT = 60 * 10
DEFAULT_TIMEOUT = 120  # two minutes


class Error(errors.DeviceError):
    pass


class TimeoutError(Error):
    pass


class CallbackHandler(object):
    """The class used to handle a specific group of callback events.

    All the events handled by a CallbackHandler are originally triggered by one
    async Rpc call. All the events are tagged with a callback_id specific to a
    call to an AsyncRpc method defined on the server side.

    The raw message representing an event looks like:
    {
        'callbackId': <string, callbackId>,
        'name': <string, name of the event>,
        'time': <long, epoch time of when the event was created on the server
            side>,
        'data': <dict, extra data from the callback on the server side>
    }

    Each message is then used to create a SnippetEvent object on the client
    side.

    Attributes:
        ret_value: The direct return value of the async Rpc call.
    """

    def __init__(self, callback_id, event_client, ret_value, method_name, ad):
        self._id = callback_id
        self._event_client = event_client
        self.ret_value = ret_value
        self._method_name = method_name
        self._ad = ad

    @property
    def callback_id(self):
        return self._id

    def waitAndGet(self, event_name, timeout=DEFAULT_TIMEOUT):
        """Blocks until an event of the specified name has been received and
        return the event, or timeout.

        Args:
            event_name: string, name of the event to get.
            timeout: float, the number of seconds to wait before giving up.

        Returns:
            SnippetEvent, the oldest entry of the specified event.

        Raises:
            Error: If the specified timeout is longer than the max timeout
                supported.
            TimeoutError: The expected event does not occur within time limit.
        """
        if timeout:
            if timeout > MAX_TIMEOUT:
                raise Error(self._ad,
                    'Specified timeout %s is longer than max timeout %s.' %
                    (timeout, MAX_TIMEOUT))
        # Convert to milliseconds for java side.
        timeout_ms = int(timeout * 1000)
        try:
            raw_event = self._event_client.eventWaitAndGet(
                self._id, event_name, timeout_ms)
        except Exception as e:
            if 'EventSnippetException: timeout.' in str(e):
                raise TimeoutError(self._ad,
                    'Timed out after waiting %ss for event "%s" triggered by'
                    ' %s (%s).' % (timeout, event_name, self._method_name,
                                   self._id))
            raise
        return snippet_event.from_dict(raw_event)

    def waitForEvent(self, event_name, predicate, timeout=DEFAULT_TIMEOUT):
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
            timeout: float, default is 120s.

        Returns:
            dictionary, the event that satisfies the predicate if received.

        Raises:
            TimeoutError: raised if no event that satisfies the predicate is
                received after timeout seconds.
        """
        deadline = time.time() + timeout
        while time.time() <= deadline:
            # Calculate the max timeout for the next event rpc call.
            rpc_timeout = deadline - time.time()
            if rpc_timeout < 0:
                break
            try:
                event = self.waitAndGet(event_name, rpc_timeout)
            except TimeoutError:
                # Ignoring TimeoutError since we need to throw one with a more
                # specific message.
                break
            if predicate(event):
                return event
        raise TimeoutError(self._ad,
            'Timed out after %ss waiting for an "%s" event that satisfies the '
            'predicate "%s".' % (timeout, event_name, predicate.__name__))

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
        raw_events = self._event_client.eventGetAll(self._id, event_name)
        return [snippet_event.from_dict(msg) for msg in raw_events]
