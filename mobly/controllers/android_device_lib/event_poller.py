#!/usr/bin/env python3.4
#
# Copyright 2016 Google Inc.
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

from concurrent import futures

import logging
import queue
import threading
import time

EVENT_QUEUE_ID_TEMPLATE = "%s|%s"


class Error(Exception):
    """Raise when user tries to put event_dispatcher into an illegal state.
    """


def _split_queue_id(queue_id):
    callback_id, rpc_id = queue_id.split('|')
    return callback_id, rpc_id


class EventPoller(object):

    DEFAULT_TIMEOUT = 60

    def __init__(self, rpc_client):
        self._client = rpc_client
        self.started = False
        self._executor = None
        self._poller = None
        self._event_queues = {}
        self._lock = threading.RLock()

    def start(self):
        """Starts the event dispatcher.

        Initiates executor and start polling events.

        Raises:
            Error is raised if polling has already started.
        """
        if not self.started:
            self.started = True
            self._executor = futures.ThreadPoolExecutor(max_workers=32)
            self._poller = self._executor.submit(self._poll_events)
        else:
            raise Error("Already started.")

    def stop(self):
        """Stops polling and clear all cached events.
        """
        if not self.started:
            return
        self.started = False
        self._poller.set_result("Done")
        # The polling thread is guaranteed to finish after a max of 60 seconds,
        # so we don't wait here.
        self._executor.shutdown(wait=False)
        self._client.close()
        self.clear_all()

    def _poll_events(self):
        """Continuously polls events from the server side.

        Events are store in separate queues. The queues are held by a dict where
        the keys are queue IDs and values are queues.
        """
        while self.started:
            event_obj = None
            try:
                event_obj = self._client.eventWait(5000)
            except:
                # Only raise if the poll loop is running.
                if self.started:
                    logging.exception('Exception happened during polling.')
                    raise
            if not event_obj:
                continue
            if event_obj['name'] == 'EventDispatcherShutdown':
                break
            else:
                q_id = EVENT_QUEUE_ID_TEMPLATE % (event_obj['callbackId'],
                                                  event_obj['name'])
                # Cache event
                with self._lock:
                    if q_id in self._event_queues:
                        self._event_queues[q_id].put(event_obj)
                        logging.info("Enqueue %s in %s.", event_obj, q_id)
                    else:
                        q = queue.Queue()
                        q.put(event_obj)
                        self._event_queues[q_id] = q
                        logging.info("New Q, then enqueue %s in %s.",
                                     event_obj, q_id)

    def get_event_queue(self, q_id):
        """Get a specific event queue.

        If no queue for the given id exists yet, create the queue.

        Args:
            q_id: The id for the queue to get.

        Returns:
            A queue storing all the events of the specified queue ID.

        Raises:
            Error is raised if this is called before polling starts.
        """
        if not self.started:
            raise Error('No operation is allowed until polling has started.')
        with self._lock:
            if (q_id not in self._event_queues) or (
                    self._event_queues[q_id] is None):
                self._event_queues[q_id] = queue.Queue()
            event_queue = self._event_queues[q_id]
        return event_queue

    def get_callback_queues(self, callback_id):
        """Get all queues that is tagged with the same callback ID.

        Args:
            callback_id: string, The ID for a CallbackFuture object whose queues
                         to be retrieved.

        Returns:
            A list of queues that supply events to the same CallbackFuture
            object.

        Raises:
            Error is raised if this is called before polling starts.
        """
        if not self.started:
            raise Error('No operation is allowed until polling has started.')
        event_queues = []
        with self._lock:
            for q_id, q in self._event_queues.items():
                q_callback_id, _ = _split_queue_id(q_id)
                if q_callback_id == callback_id:
                    event_queues.append(q)
        return event_queues

    def clear_all(self):
        """Clear all event queues and their cached events."""
        with self._lock:
            self._event_queues.clear()
