#/usr/bin/env python3.4
#
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

import logging
import time

from mobly.controllers.android_device_lib import jsonrpc_client_base


class Error(Exception):
    pass


class TimeoutError(Error):
    pass


class CallbackHandler(object):
    """The class used to handle a specific group of callback events.

    All the events handled by a CallbackHandler are originally triggered by one
    async Rpc call. All the events are tagged with a callback_id specific to a call
    to an AsyncRpc method defined on the server side.

    The callback events are dictionaries that follow this schema:
    {
        'callbackId': <string, callbackId>,
        'name': <string, name of the event>,
        'time': <long, epoch time of when the event was created on the server side>,
        'data': <dict, extra data from the callback on the server side>
    }
    """

    def __init__(self, callback_id, event_client, ret_value):
        self._id = callback_id
        self._event_client = event_client
        self.ret_value = ret_value

    def waitAndGet(self, event_name, timeout=None):
        """Blocks until an event of the specified name has been received and
        return the event, or timeout.

        Args:
            event_name: string, name of the event to get.
            timeout: float, the number of seconds to wait before giving up.

        Returns:
            The oldest entry of the specified event.

        Raises:
            TimeoutError: The expected event does not occur within time limit.
        """
        if timeout:
            timeout *= 1000  # convert to milliseconds for java side
        try:
            event = self._event_client.eventWaitAndGet(self._id, event_name,
                                                       timeout)
        except jsonrpc_client_base.ApiError as e:
            if "EventSnippetException: timeout." in str(e):
                raise TimeoutError(
                    'Timeout after %sms waiting for event "%s" of callback %s'
                    % (timeout, event_name, self._id))
            raise
        return event

    def getAll(self, event_name):
        """Gets all the events of a certain name that have been received so far.
        This is a non-blocking call.

        Args:
            callback_id: The id of the callback.
            event_name: string, the name of the event to get.

        Returns:
            A list of dicts, each dict representing an event from the Java side.
        """
        return self._event_client.eventGetAll(self._id, event_name)
