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
import copy
import datetime
import fnmatch
import io
import logging
import os
import re
import threading

from dateutil.parser import parse as parse_date
from mobly import logger as mobly_logger
from mobly import utils
from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import errors
from mobly.controllers.android_device_lib.services import base_service


LogcatData = collections.namedtuple(
    'LogcatData', ['time', 'pid', 'tid', 'level', 'tag', 'message',
                   'host_time', 'line'])


class Error(errors.ServiceError):
    """Root error type for logcat service."""
    SERVICE_TYPE = 'Logcat'


class Config(object):
    """Config object for logcat service.

    Attributes:
        clear_log: bool, clears the logcat before collection if True.
        logcat_params: string, extra params to be added to logcat command.
    """

    def __init__(self, params=None, clear_log=True):
        self.clear_log = clear_log
        self.logcat_params = params if params else ''


class Logcat(base_service.BaseService):
    """Android logcat service for Mobly's AndroidDevice controller."""
    line_regex = re.compile(
        r'(?P<time>\d\d-\d\d \d\d:\d\d:\d\d.\d\d\d)\s+'
        r'(?P<pid>\d+)\s+(?P<tid>\d+)\s+(?P<level>[VDIWEFS])\s+'
        r'(?P<tag>.+?)\s*:\s+(?P<message>.*)')

    def __init__(self, android_device, configs=None):
        super(Logcat, self).__init__(android_device, configs)
        self._ad = android_device
        self._adb_logcat_process = None
        self.adb_logcat_file_path = None
        self._configs = configs if configs else Config()
        self._publisher_thread = None
        self._publisher_process = None
        self._subscribers = []

    def _enable_logpersist(self):
        """Attempts to enable logpersist daemon to persist logs."""
        # Logpersist is only allowed on rootable devices because of excessive
        # reads/writes for persisting logs.
        if not self._ad.is_rootable:
            return

        logpersist_warning = ('%s encountered an error enabling persistent'
                              ' logs, logs may not get saved.')
        # Android L and older versions do not have logpersist installed,
        # so check that the logpersist scripts exists before trying to use
        # them.
        if not self._ad.adb.has_shell_command('logpersist.start'):
            logging.warning(logpersist_warning, self)
            return

        try:
            # Disable adb log spam filter for rootable devices. Have to stop
            # and clear settings first because 'start' doesn't support --clear
            # option before Android N.
            self._ad.adb.shell('logpersist.stop --clear')
            self._ad.adb.shell('logpersist.start')
        except adb.AdbError:
            logging.warning(logpersist_warning, self)

    def _is_timestamp_in_range(self, target, begin_time, end_time):
        low = mobly_logger.logline_timestamp_comparator(begin_time,
                                                        target) <= 0
        high = mobly_logger.logline_timestamp_comparator(end_time, target) >= 0
        return low and high

    @property
    def is_alive(self):
        return True if self._adb_logcat_process else False

    def clear_adb_log(self):
        # Clears cached adb content.
        try:
            self._ad.adb.logcat('-c')
        except adb.AdbError as e:
            # On Android O, the clear command fails due to a known bug.
            # Catching this so we don't crash from this Android issue.
            if "failed to clear" in e.stderr:
                self._ad.log.warning(
                    'Encountered known Android error to clear logcat.')
            else:
                raise

    def cat_adb_log(self, tag, begin_time):
        """Takes an excerpt of the adb logcat log from a certain time point to
        current time.

        Args:
            tag: An identifier of the time period, usualy the name of a test.
            begin_time: Logline format timestamp of the beginning of the time
                period.
        """
        if not self.adb_logcat_file_path:
            raise Error(
                self._ad,
                'Attempting to cat adb log when none has been collected.')
        end_time = mobly_logger.get_log_line_timestamp()
        self._ad.log.debug('Extracting adb log from logcat.')
        adb_excerpt_path = os.path.join(self._ad.log_path, 'AdbLogExcerpts')
        utils.create_dir(adb_excerpt_path)
        f_name = os.path.basename(self.adb_logcat_file_path)
        out_name = f_name.replace('adblog,', '').replace('.txt', '')
        out_name = ',%s,%s.txt' % (begin_time, out_name)
        out_name = out_name.replace(':', '-')
        tag_len = utils.MAX_FILENAME_LEN - len(out_name)
        tag = tag[:tag_len]
        out_name = tag + out_name
        full_adblog_path = os.path.join(adb_excerpt_path, out_name)
        with io.open(full_adblog_path, 'w', encoding='utf-8') as out:
            in_file = self.adb_logcat_file_path
            with io.open(
                    in_file, 'r', encoding='utf-8', errors='replace') as f:
                in_range = False
                while True:
                    line = None
                    try:
                        line = f.readline()
                        if not line:
                            break
                    except:
                        continue
                    line_time = line[:mobly_logger.log_line_timestamp_len]
                    if not mobly_logger.is_valid_logline_timestamp(line_time):
                        continue
                    if self._is_timestamp_in_range(line_time, begin_time,
                                                   end_time):
                        in_range = True
                        if not line.endswith('\n'):
                            line += '\n'
                        out.write(line)
                    else:
                        if in_range:
                            break

    def start(self, configs=None):
        """Starts a standing adb logcat collection.

        The collection runs in a separate subprocess and saves logs in a file.

        Args:
            configs: Conifg object.
        """
        if self._adb_logcat_process:
            raise Error(
                self._ad,
                'Logcat thread is already running, cannot start another one.')
        configs = configs if configs else self._configs
        if configs.clear_log:
            self.clear_adb_log()

        self._enable_logpersist()

        f_name = 'adblog,%s,%s.txt' % (self._ad.model,
                                       self._ad._normalized_serial)
        utils.create_dir(self._ad.log_path)
        logcat_file_path = os.path.join(self._ad.log_path, f_name)
        cmd = '"%s" -s %s logcat -v threadtime %s >> "%s"' % (
            adb.ADB, self._ad.serial, configs.logcat_params, logcat_file_path)
        process = utils.start_standing_subprocess(cmd, shell=True)
        self._adb_logcat_process = process
        self.adb_logcat_file_path = logcat_file_path
        if self._subscribers:
            self._start_publisher()

    def stop(self):
        """Stops the adb logcat service."""
        if not self._adb_logcat_process:
            return
        try:
            utils.stop_standing_subprocess(self._adb_logcat_process)
        except:
            self._ad.log.exception('Failed to stop adb logcat.')
        self._adb_logcat_process = None
        self._stop_publisher()

    def pause(self):
        """Pauses logcat for usb disconnect."""
        self.stop()
        # Clears cached adb content, so that the next time start_adb_logcat()
        # won't produce duplicated logs to log file.
        # This helps disconnection that caused by, e.g., USB off; at the
        # cost of losing logs at disconnection caused by reboot.
        self.clear_adb_log()

    def resume(self):
        """Resumes a paused logcat service.

        Args:
            configs: Not used.
        """
        # Do not clear device log at this time. Otherwise the log during USB
        # disconnection will be lost.
        resume_configs = copy.copy(self._configs)
        resume_configs.clear_log = False
        self.start(resume_configs)

    def subscribe(self, subscriber):
        """Subscribe a subscriber to this publisher.

        Args:
            subscriber: LogcatSubscriber, a logcat subscriber to subscribe.

        Raises:
            Error: When subscriber is not a LogcatSubscriber.
        """
        if not self._publisher_is_active:
            self._start_publisher()

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

    def event(self, pattern='.*', tag='*', level='V'):
        """Context manager object for a logcat event.

        Args:
            pattern: str, Regular expression pattern to trigger on.
            tag: str, Tag portion of filterspec string.
            level: str, Level portion of filterspec string.

        Returns:
            A context manager describing the event.
        """
        subscriber = LogcatEventSubscriber(
            pattern=pattern, tag=tag, level=level)
        subscriber.subscribe(self)
        return subscriber

    @property
    def _publisher_is_active(self):
        """Returns a boolean value indicating if publisher is running."""
        return (self._publisher_process
                and self._publisher_process.returncode is None
                and self._publisher_thread
                and self._publisher_thread.is_alive())

    def _start_publisher(self):
        """Start the publisher process and task."""
        if self.adb_logcat_file_path is None:
            raise Error('ADB logcat file path is not defined.')
        if self._publisher_is_active:
            raise Error('Publisher process is already running.')

        cmd = ['tail', '-F', self.adb_logcat_file_path]
        self._publisher_process = utils.start_standing_subprocess(cmd)
        self._publisher_thread = threading.Thread(
            target=self._publisher_task)
        self._publisher_thread.daemon = True
        self._publisher_thread.start()

    def _stop_publisher(self):
        """Stop the publisher process and task."""
        if self._publisher_is_active:
            self._publisher_process.terminate()
            self._publisher_process.wait()
            self._publisher_thread.join()

    def _publisher_task(self):
        """Main publisher thread task."""
        for line in iter(self._publisher_process.stdout.readline, ''):
            match = self.line_regex.match(line)
            if match is None:
                continue
            time = match and parse_date(match.group('time'))
            pid = match and int(match.group('pid'))
            tid = match and int(match.group('tid'))
            level = match and match.group('level')
            tag = match and match.group('tag')
            message = match and match.group('message').strip()

            pub_data = LogcatData(
                time=time, pid=pid, tid=tid, level=level, tag=tag,
                message=message, host_time=datetime.datetime.now(), line=line)

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
        if not isinstance(publisher, Logcat):
            raise Error('Only Logcat instance can be subscribed to.')
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
        if self.trigger:
            return
        if data.tag is None or not fnmatch.fnmatchcase(data.tag, self._tag):
            return
        if data.level is None or data.level not in self._levels:
            return
        self.match = self._pattern.match(data.message)
        if self.match:
            self.trigger = data
            self._event.set()
