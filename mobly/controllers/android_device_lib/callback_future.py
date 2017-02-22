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

DEFAULT_TIMEOUT = 10


class Error(Exception):
    pass


class CallbackFuture(object):
    def __init__(self, callback_id, event_client):
        self._id = callback_id
        self._event_client = event_client

    def waitAndGet(self, event_name, timeout=DEFAULT_TIMEOUT):
        """Blocks until an event of the specified name has been received and
        return the event, or timeout.

        Args:
            event_name: string, ame of the event to get.
            timeout: float, the number of seconds to wait before giving up.

        Returns:
            The oldest entry of the specified event.
        """
        event = self._event_client.waitAndGet(self._id, event_name, int(timeout * 1000))
        if event is None:
            raise Error('Timeout after %ss waiting for event "%s" of callack %s' %
                        (timeout, event_name, self._id))
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
        return self._event_client.getAll(self._id, event_name)
