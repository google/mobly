# Copyright 2018 Google Inc.
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
import collections
import datetime
import fnmatch
import re
import threading

from dateutil.parser import parse as parse_date
from mobly import utils
from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import errors
from mobly.controllers.android_device_lib.services import base_service


LogcatData = collections.namedtuple(
    'LogcatData', ['time', 'pid', 'tid', 'level', 'tag', 'message',
                   'host_time', 'raw'])

class Error(errors.ServiceError):
  """Root error type for logcat publisher service."""
  SERVICE_TYPE = 'LogcatPublisher'


class LogcatPublisher(base_service.BaseService):
    """Android logcat publisher service."""
    raw_regex = re.compile(
        r'(?P<time>\d\d-\d\d \d\d:\d\d:\d\d.\d\d\d)\s+'
        r'(?P<pid>\d+)\s+(?P<tid>\d+)\s+(?P<level>[VDIWEFS])\s+'
        r'(?P<tag>.+?)\s*:\s+(?P<message>.*)')

    def __init__(self, android_device, configs=None):
        super(LogcatPublisher, self).__init__(android_device, configs)
        self._ad = android_device
        self._configs = configs
        self._subscribers = []
        self._proc = None
        self._running = threading.Event()
        self._stopped = False
        self._thread = threading.Thread(target=self._run)
        self._thread.daemon = True
        self._thread.start()

    @property
    def is_alive(self):
        return self._proc and self._proc.poll() is None

    def start(self):
      """Start logcat monitoring.

      Raises:
          Error: When existing publisher is active.
      """
      if self.is_alive:
          raise Error(self._ad, 'Existing publisher process is active.')
      cmd = [adb.ADB, '-s', self._ad.serial, 'logcat', '-T', '0']
      self._proc = utils.start_standing_subprocess(cmd)
      self._running.set()

    def stop(self):
      """Stop logcat monitoring."""
      self._stopped = True
      self.pause()

    def pause(self):
      """Pause logcat monitoring.

      Raises:
          Error: When no existing publisher is active.
      """
      if not self.is_alive:
          raise Error(self._ad, 'No existing publisher process is active.')
      self._running.clear()
      utils.stop_standing_subprocess(self._proc)

    def subscribe(self, subscriber):
        """Subscribe a subscriber to this publisher.

        Args:
            subscriber: LogcatSubscriber, a logcat subscriber to subscribe.
        Raises:
            Error: When subscriber is not a LogcatSubscriber.
        """
        if not isinstance(subscriber, LogcatSubscriber):
            raise Error(self._ad, 'Attempt to subscribe a non-subscriber.')
        self._subscribers.append(subscriber)

    def unsubscribe(self, subscriber):
        """Unsubscribe a subscriber to this publisher.

        Args:
            subscriber: LogcatSubscriber, a logcat subscriber to unsubscribe.
        Raises:
            Error: When the argument is not previously registered subscriber.
        """
        if subscriber not in self._subscribers:
            raise Error(self._ad, 'Attempt to unsubscribe a non-subscriber.')
        self._subscribers.remove(subscriber)

    def _run(self):
        """Main publisher thread task."""
        while not self._stopped:
            if not self._running.is_set():
                self._running.wait()

            raw = self._proc.stdout.readline()
            if raw:
              match = self.raw_regex.match(raw)
              time = match and parse_date(match.group('time'))
              pid = match and int(match.group('pid'))
              tid = match and int(match.group('tid'))
              level = match and match.group('level')
              tag = match and match.group('tag')
              message = match and match.group('message').strip()

              pub_data = LogcatData(
                  time=time, pid=pid, tid=tid, level=level, tag=tag,
                  message=message, host_time=datetime.datetime.now(), raw=raw)

              for subscriber in self._subscribers:
                subscriber.handle(pub_data)


class LogcatSubscriber(object):
    """Base class for logcat subscriber."""

    def __init__(self):
        super(LogcatSubscriber, self).__init__()
        self._publisher = None

    def subscribe(self, publisher):
        """Subscribe this object to a publisher.

        Args:
            publisher: LogcatPublisher, a logcat publisher to subscribe to.
        Raises:
            Error: If publisher is not a LogcatPublisher.
        """
        if not isinstance(publisher, LogcatPublisher):
            raise Error(
                'LogcatSubscriber can only subscribe a LogcatPublisher.')
        publisher.subscribe(self)
        self._publisher = publisher

    def unsubscribe(self):
        """Unsubscribe this object to its publisher."""
        self._publisher.unsubscribe(self)
        self._publisher = None

    def handle(self, data):
        """Abstract subscribe handler method.

        This abstract method defines the subscribe handler and must be
        overridden by derived class.

        Args:
            data: LogcatData, Data to handle.
        """
        raise NotImplementedError('"handle" is a required subscriber method.')


class LogcatEventSubscriber(LogcatSubscriber):
    """Logcat event subscriber class.

    This class waits for a particular logcat event to occur.

    Args:
        pattern: str, Regular expression pattern to trigger on.
        tag: str, Tag portion of filterspec string.
        level: str, Level portion of filterspec string.
    """
    _LOG_LEVELS = 'VDIWEF'

    def __init__(self, pattern='.*', tag='*', level='V'):
        super(LogcatEventSubscriber, self).__init__()
        self._event = threading.Event()
        self._pattern = (re.compile(pattern) if isinstance(pattern, str)
                         else pattern)
        self._tag = tag
        self._levels = (self._LOG_LEVELS if level == '*'
                        else self._LOG_LEVELS[self._LOG_LEVELS.find(level):])
        self.trigger = None
        self.match = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.unsubscribe()

    def clear(self):
        """Clears any set event."""
        self.trigger = None
        self.match = None
        self._event.clear()

    def wait(self, timeout=None):
        """Wait until the trigger expression is seen.

        Args:
            timeout: float, Timeout in seconds.
        Returns:
            True except if a timeout is given and the operation times out.
        """
        return self._event.wait(timeout)

    def handle(self, data):
        """Handle a logcat subscription message.

        Args:
            data: LogcatData, Data to handle.
        """
        if data.tag is None or not fnmatch.fnmatchcase(data.tag, self._tag):
            return
        if data.level is None or data.level not in self._levels:
            return
        self.match = self._pattern.match(data.message)
        if self.match:
            self.trigger = data
            self._event.set()
