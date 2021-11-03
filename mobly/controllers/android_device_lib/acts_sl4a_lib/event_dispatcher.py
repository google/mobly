#!/usr/bin/env python3
#
#   Copyright 2016- Google, Inc.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
import queue
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from mobly.controllers.android_device_lib.acts_sl4a_lib import logger
from mobly.controllers.android_device_lib.acts_sl4a_lib import rpc_client


class EventDispatcherError(Exception):
  """The base class for all EventDispatcher exceptions."""


class IllegalStateError(EventDispatcherError):
  """Raise when user tries to put event_dispatcher into an illegal state."""


class DuplicateError(EventDispatcherError):
  """Raise when two event handlers have been assigned to an event name."""


class EventDispatcher:
  """A class for managing the events for an SL4A Session.

  Attributes:
      _serial: The serial of the device.
      _rpc_client: The rpc client for that session.
      _started: A bool that holds whether or not the event dispatcher is
                running.
      _executor: The thread pool executor for running event handlers and
                 polling.
      _event_dict: A dictionary of str eventName = Queue<Event> eventQueue
      _handlers: A dictionary of str eventName => (lambda, args) handler
      _lock: A lock that prevents multiple reads/writes to the event queues.
      log: The EventDispatcher's logger.
  """

  DEFAULT_TIMEOUT = 60

  def __init__(self, serial, rpc_client):
    self._serial = serial
    self._rpc_client = rpc_client
    self._started = False
    self._executor = None
    self._event_dict = {}
    self._handlers = {}
    self._lock = threading.RLock()

    self.log = logger.create_tagged_logger(
      'E Dispatcher|%s|%s' % (self._serial, self._rpc_client.uid))

  def poll_events(self):
    """Continuously polls all types of events from sl4a.

    Events are sorted by name and store in separate queues.
    If there are registered handlers, the handlers will be called with
    corresponding event immediately upon event discovery, and the event
    won't be stored. If exceptions occur, stop the dispatcher and return
    """
    while self._started:
      try:
        # 60000 in ms, timeout in second
        event_obj = self._rpc_client.eventWait(60000, timeout=120)
      except rpc_client.Sl4aConnectionError as e:
        if self._rpc_client.is_alive:
          self.log.warning('Closing due to closed session.')
          break
        else:
          self.log.warning('Closing due to error: %s.' % e)
          self.close()
          raise e
      if not event_obj:
        continue
      elif 'name' not in event_obj:
        self.log.error('Received Malformed event {}'.format(event_obj))
        continue
      else:
        event_name = event_obj['name']
      # if handler registered, process event
      if event_name == 'EventDispatcherShutdown':
        self.log.debug('Received shutdown signal.')
        # closeSl4aSession has been called, which closes the event
        # dispatcher. Stop execution on this polling thread.
        return
      if event_name in self._handlers:
        self.log.debug(
          'Using handler %s for event: %r' %
          (self._handlers[event_name].__name__, event_obj))
        self.handle_subscribed_event(event_obj, event_name)
      else:
        self.log.debug('Queuing event: %r' % event_obj)
        self._lock.acquire()
        if event_name in self._event_dict:  # otherwise, cache event
          self._event_dict[event_name].put(event_obj)
        else:
          q = queue.Queue()
          q.put(event_obj)
          self._event_dict[event_name] = q
        self._lock.release()

  def register_handler(self, handler, event_name, args):
    """Registers an event handler.

    One type of event can only have one event handler associated with it.

    Args:
        handler: The event handler function to be registered.
        event_name: Name of the event the handler is for.
        args: User arguments to be passed to the handler when it's called.

    Raises:
        IllegalStateError: Raised if attempts to register a handler after
            the dispatcher starts running.
        DuplicateError: Raised if attempts to register more than one
            handler for one type of event.
    """
    if self._started:
      raise IllegalStateError('Cannot register service after polling is '
                              'started.')
    self._lock.acquire()
    try:
      if event_name in self._handlers:
        raise DuplicateError(
          'A handler for {} already exists'.format(event_name))
      self._handlers[event_name] = (handler, args)
    finally:
      self._lock.release()

  def start(self):
    """Starts the event dispatcher.

    Initiates executor and start polling events.

    Raises:
        IllegalStateError: Can't start a dispatcher again when it's already
            running.
    """
    if not self._started:
      self._started = True
      self._executor = ThreadPoolExecutor(max_workers=32)
      self._executor.submit(self.poll_events)
    else:
      raise IllegalStateError("Dispatcher is already started.")

  def close(self):
    """Clean up and release resources.

    This function should only be called after a
    rpc_client.closeSl4aSession() call.
    """
    if not self._started:
      return
    self._started = False
    self._executor.shutdown(wait=True)
    self.clear_all_events()

  def pop_event(self, event_name, timeout=DEFAULT_TIMEOUT):
    """Pop an event from its queue.

    Return and remove the oldest entry of an event.
    Block until an event of specified name is available or
    times out if timeout is set.

    Args:
        event_name: Name of the event to be popped.
        timeout: Number of seconds to wait when event is not present.
            Never times out if None.

    Returns:
        event: The oldest entry of the specified event. None if timed out.

    Raises:
        IllegalStateError: Raised if pop is called before the dispatcher
            starts polling.
    """
    if not self._started:
      raise IllegalStateError(
        'Dispatcher needs to be started before popping.')

    e_queue = self.get_event_q(event_name)

    if not e_queue:
      raise IllegalStateError(
        'Failed to get an event queue for {}'.format(event_name))

    try:
      # Block for timeout
      if timeout:
        return e_queue.get(True, timeout)
      # Non-blocking poll for event
      elif timeout == 0:
        return e_queue.get(False)
      else:
        # Block forever on event wait
        return e_queue.get(True)
    except queue.Empty:
      msg = 'Timeout after {}s waiting for event: {}'.format(
        timeout, event_name)
      self.log.info(msg)
      raise queue.Empty(msg)

  def wait_for_event(self,
                     event_name,
                     predicate,
                     timeout=DEFAULT_TIMEOUT,
                     *args,
                     **kwargs):
    """Wait for an event that satisfies a predicate to appear.

    Continuously pop events of a particular name and check against the
    predicate until an event that satisfies the predicate is popped or
    timed out. Note this will remove all the events of the same name that
    do not satisfy the predicate in the process.

    Args:
        event_name: Name of the event to be popped.
        predicate: A function that takes an event and returns True if the
            predicate is satisfied, False otherwise.
        timeout: Number of seconds to wait.
        *args: Optional positional args passed to predicate().
        **kwargs: Optional keyword args passed to predicate().
            consume_ignored_events: Whether or not to consume events while
                searching for the desired event. Defaults to True if unset.

    Returns:
        The event that satisfies the predicate.

    Raises:
        queue.Empty: Raised if no event that satisfies the predicate was
            found before time out.
    """
    deadline = time.time() + timeout
    ignored_events = []
    consume_events = kwargs.pop('consume_ignored_events', True)
    while True:
      event = None
      try:
        event = self.pop_event(event_name, 1)
        if consume_events:
          self.log.debug('Consuming event: %r' % event)
        else:
          self.log.debug('Peeking at event: %r' % event)
          ignored_events.append(event)
      except queue.Empty:
        pass

      if event and predicate(event, *args, **kwargs):
        for ignored_event in ignored_events:
          self.get_event_q(event_name).put(ignored_event)
        self.log.debug('Matched event: %r with %s' %
                       (event, predicate.__name__))
        return event

      if time.time() > deadline:
        for ignored_event in ignored_events:
          self.get_event_q(event_name).put(ignored_event)
        msg = 'Timeout after {}s waiting for event: {}'.format(
          timeout, event_name)
        self.log.info(msg)
        raise queue.Empty(msg)

  def pop_events(self, regex_pattern, timeout, freq=1):
    """Pop events whose names match a regex pattern.

    If such event(s) exist, pop one event from each event queue that
    satisfies the condition. Otherwise, wait for an event that satisfies
    the condition to occur, with timeout.

    Results are sorted by timestamp in ascending order.

    Args:
        regex_pattern: The regular expression pattern that an event name
            should match in order to be popped.
        timeout: Number of seconds to wait for events in case no event
            matching the condition exits when the function is called.

    Returns:
        results: Pop events whose names match a regex pattern.
            Empty if none exist and the wait timed out.

    Raises:
        IllegalStateError: Raised if pop is called before the dispatcher
            starts polling.
        queue.Empty: Raised if no event was found before time out.
    """
    if not self._started:
      raise IllegalStateError(
        "Dispatcher needs to be started before popping.")
    deadline = time.time() + timeout
    while True:
      # TODO: fix the sleep loop
      results = self._match_and_pop(regex_pattern)
      if len(results) != 0 or time.time() > deadline:
        break
      time.sleep(freq)
    if len(results) == 0:
      msg = 'Timeout after {}s waiting for event: {}'.format(
        timeout, regex_pattern)
      self.log.error(msg)
      raise queue.Empty(msg)

    return sorted(results, key=lambda event: event['time'])

  def _match_and_pop(self, regex_pattern):
    """Pop one event from each of the event queues whose names
    match (in a sense of regular expression) regex_pattern.
    """
    results = []
    self._lock.acquire()
    for name in self._event_dict.keys():
      if re.match(regex_pattern, name):
        q = self._event_dict[name]
        if q:
          try:
            results.append(q.get(False))
          except queue.Empty:
            pass
    self._lock.release()
    return results

  def get_event_q(self, event_name):
    """Obtain the queue storing events of the specified name.

    If no event of this name has been polled, wait for one to.

    Returns: A queue storing all the events of the specified name.
    """
    self._lock.acquire()
    if (event_name not in self._event_dict
        or self._event_dict[event_name] is None):
      self._event_dict[event_name] = queue.Queue()
    self._lock.release()

    event_queue = self._event_dict[event_name]
    return event_queue

  def handle_subscribed_event(self, event_obj, event_name):
    """Execute the registered handler of an event.

    Retrieve the handler and its arguments, and execute the handler in a
        new thread.

    Args:
        event_obj: Json object of the event.
        event_name: Name of the event to call handler for.
    """
    handler, args = self._handlers[event_name]
    self._executor.submit(handler, event_obj, *args)

  def _handle(self, event_handler, event_name, user_args, event_timeout,
              cond, cond_timeout):
    """Pop an event of specified type and calls its handler on it. If
    condition is not None, block until condition is met or timeout.
    """
    if cond:
      cond.wait(cond_timeout)
    event = self.pop_event(event_name, event_timeout)
    return event_handler(event, *user_args)

  def handle_event(self,
                   event_handler,
                   event_name,
                   user_args,
                   event_timeout=None,
                   cond=None,
                   cond_timeout=None):
    """Handle events that don't have registered handlers

    In a new thread, poll one event of specified type from its queue and
    execute its handler. If no such event exists, the thread waits until
    one appears.

    Args:
        event_handler: Handler for the event, which should take at least
            one argument - the event json object.
        event_name: Name of the event to be handled.
        user_args: User arguments for the handler; to be passed in after
            the event json.
        event_timeout: Number of seconds to wait for the event to come.
        cond: A condition to wait on before executing the handler. Should
            be a threading.Event object.
        cond_timeout: Number of seconds to wait before the condition times
            out. Never times out if None.

    Returns:
        worker: A concurrent.Future object associated with the handler.
            If blocking call worker.result() is triggered, the handler
            needs to return something to unblock.
    """
    worker = self._executor.submit(self._handle, event_handler, event_name,
                                   user_args, event_timeout, cond,
                                   cond_timeout)
    return worker

  def pop_all(self, event_name):
    """Return and remove all stored events of a specified name.

    Pops all events from their queue. May miss the latest ones.
    If no event is available, return immediately.

    Args:
        event_name: Name of the events to be popped.

    Returns:
       results: List of the desired events.

    Raises:
        IllegalStateError: Raised if pop is called before the dispatcher
            starts polling.
    """
    if not self._started:
      raise IllegalStateError(("Dispatcher needs to be started before "
                               "popping."))
    results = []
    try:
      self._lock.acquire()
      while True:
        e = self._event_dict[event_name].get(block=False)
        results.append(e)
    except (queue.Empty, KeyError):
      return results
    finally:
      self._lock.release()

  def clear_events(self, event_name):
    """Clear all events of a particular name.

    Args:
        event_name: Name of the events to be popped.
    """
    self._lock.acquire()
    try:
      q = self.get_event_q(event_name)
      q.queue.clear()
    except queue.Empty:
      return
    finally:
      self._lock.release()

  def clear_all_events(self):
    """Clear all event queues and their cached events."""
    self._lock.acquire()
    self._event_dict.clear()
    self._lock.release()

  def is_event_match(self, event, field, value):
    return self.is_event_match_for_list(event, field, [value])

  def is_event_match_for_list(self, event, field, value_list):
    try:
      value_in_event = event['data'][field]
    except KeyError:
      return False
    for value in value_list:
      if value_in_event == value:
        return True
    return False
