# Copyright 2026 Google Inc.
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
"""Logcat line parsing, timestamp comparison, and file reader utilities."""

import collections
from collections.abc import Iterable
import dataclasses
import os
import queue
import re
import threading
import time
from typing import Any, ClassVar, Iterator, Optional, Pattern, Sequence, Set, Union


_LEVEL_NORM_MAP = {
    'V': 'V',
    'VERBOSE': 'V',
    'D': 'D',
    'DEBUG': 'D',
    'I': 'I',
    'INFO': 'I',
    'W': 'W',
    'WARN': 'W',
    'WARNING': 'W',
    'E': 'E',
    'ERROR': 'E',
    'F': 'F',
    'FATAL': 'F',
    'A': 'F',
    'ASSERT': 'F',
    'S': 'S',
    'SILENT': 'S',
}


@dataclasses.dataclass(frozen=True)
class LogcatPosition:
  """A position marker representing a specific point in the logcat stream.

  Attributes:
    timestamp: Optional string timestamp corresponding to this position.
    creation_time: Host epoch time when this position was marked.
  """

  timestamp: Optional[str] = None
  creation_time: float = dataclasses.field(default_factory=time.time)
  _byte_offset: int = 0

  @classmethod
  def from_file(
      cls, file_path: str, timestamp: Optional[str] = None
  ) -> 'LogcatPosition':
    """Captures a LogcatPosition snapshot of a logcat file at the current moment."""
    try:
      file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
    except OSError:
      file_size = 0
    return cls(
        timestamp=timestamp,
        creation_time=time.time(),
        _byte_offset=file_size,
    )

  @staticmethod
  def _parse_timestamp(t: str) -> tuple[int, int, int, int, int, int, int]:
    """Parses a logline timestamp into (year, month, day, hour, minute, second, microsecond)."""
    if not t:
      raise ValueError('Empty timestamp string')

    date_part, time_part = re.split(r'[\sT]+', t.strip(), maxsplit=1)
    date_elements = [int(x) for x in re.split(r'[-/]', date_part)]
    if len(date_elements) == 3:
      year, month, day = date_elements
    elif len(date_elements) == 2:
      year = 0
      month, day = date_elements
    else:
      raise ValueError(f'Invalid date elements in timestamp: {t}')

    time_parts = time_part.split(':')
    hour = int(time_parts[0])
    minute = int(time_parts[1]) if len(time_parts) > 1 else 0
    second, microsecond = 0, 0
    if len(time_parts) > 2:
      s_ms = time_parts[2].split('.', 1)
      second = int(s_ms[0])
      if len(s_ms) > 1:
        microsecond = int(s_ms[1].ljust(6, '0')[:6])

    return (year, month, day, hour, minute, second, microsecond)

  @classmethod
  def _compare_timestamps(cls, t1: Optional[str], t2: Optional[str]) -> int:
    """Compares two logline timestamps chronologically."""
    if not t1 and not t2:
      return 0
    if not t1:
      return -1
    if not t2:
      return 1
    try:
      p1 = cls._parse_timestamp(t1)
      p2 = cls._parse_timestamp(t2)
      if p1[0] == 0 or p2[0] == 0:
        p1 = (0,) + p1[1:]
        p2 = (0,) + p2[1:]
      return (p1 > p2) - (p1 < p2)
    except (ValueError, IndexError):
      str_t1, str_t2 = str(t1 or ''), str(t2 or '')
      return (str_t1 > str_t2) - (str_t1 < str_t2)

  def __lt__(self, other: Any) -> bool:
    if not isinstance(other, LogcatPosition):
      return NotImplemented
    if self._byte_offset != other._byte_offset:
      return self._byte_offset < other._byte_offset
    return self._compare_timestamps(self.timestamp, other.timestamp) < 0

  def __le__(self, other: Any) -> bool:
    if not isinstance(other, LogcatPosition):
      return NotImplemented
    if self._byte_offset != other._byte_offset:
      return self._byte_offset <= other._byte_offset
    return self._compare_timestamps(self.timestamp, other.timestamp) <= 0

  def __gt__(self, other: Any) -> bool:
    if not isinstance(other, LogcatPosition):
      return NotImplemented
    if self._byte_offset != other._byte_offset:
      return self._byte_offset > other._byte_offset
    return self._compare_timestamps(self.timestamp, other.timestamp) > 0

  def __ge__(self, other: Any) -> bool:
    if not isinstance(other, LogcatPosition):
      return NotImplemented
    if self._byte_offset != other._byte_offset:
      return self._byte_offset >= other._byte_offset
    return self._compare_timestamps(self.timestamp, other.timestamp) >= 0


@dataclasses.dataclass(frozen=True)
class LogLine:
  """Represents a single parsed Android logcat line in threadtime format.

  Attributes:
    position: LogcatPosition, position marker and timestamp of this log line.
    pid: int, process ID.
    tid: int, thread ID.
    level: str, single-letter severity level ('V', 'D', 'I', 'W', 'E', 'F', 'S').
    tag: str, log tag.
    message: str, log message payload.
    raw: str, original raw log line string without line endings.
  """

  position: LogcatPosition
  pid: int
  tid: int
  level: str
  tag: str
  message: str
  raw: str

  _PATTERN: ClassVar[Pattern[str]] = re.compile(
      r'^(?P<timestamp>(?:\d{4}[-/])?\d{2}[-/]\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)'
      r'\s+(?P<pid>\d+)'
      r'\s+(?P<tid>\d+)'
      r'\s+(?P<level>[VDIWEFSA])'
      r'\s+(?P<tag>.*?)'
      r'\s*:\s?'
      r'(?P<message>.*)$'
  )

  @property
  def timestamp(self) -> str:
    """Returns the string timestamp of this log line."""
    return self.position.timestamp or ''

  @classmethod
  def from_string(cls, line: str, byte_offset: int = 0) -> Optional['LogLine']:
    """Parses a raw logcat line in threadtime format into a LogLine object."""
    if not line or not isinstance(line, str):
      return None

    clean_line = line.rstrip('\r\n')
    match = cls._PATTERN.match(clean_line)
    if not match:
      return None

    try:
      pos = LogcatPosition(
          timestamp=match.group('timestamp'),
          _byte_offset=byte_offset,
      )
      return cls(
          position=pos,
          pid=int(match.group('pid')),
          tid=int(match.group('tid')),
          level=match.group('level'),
          tag=match.group('tag'),
          message=match.group('message'),
          raw=clean_line,
      )
    except (ValueError, TypeError, IndexError):
      return None

  def matches(
      self,
      pattern: Optional[Union[str, Pattern[str]]] = None,
      tag: Optional[Union[str, Pattern[str], Sequence[str], Set[str]]] = None,
      level: Optional[Union[str, Sequence[str], Set[str]]] = None,
  ) -> bool:
    """Checks if this log line matches the given pattern, tag, and/or level."""
    if pattern is not None:
      regex = re.compile(pattern) if isinstance(pattern, str) else pattern
      if not (regex.search(self.message) or regex.search(self.raw)):
        return False

    if tag is not None:
      if isinstance(tag, str):
        if self.tag != tag:
          return False
      elif hasattr(tag, 'search'):
        if not tag.search(self.tag):
          return False
      elif isinstance(tag, Iterable) and self.tag not in tag:
        return False

    if level is not None:
      levels = {level} if isinstance(level, str) else set(level)
      norm_levels = {
          _LEVEL_NORM_MAP.get(str(l).upper(), str(l).upper()) for l in levels
      }
      self_norm = _LEVEL_NORM_MAP.get(self.level.upper(), self.level.upper())
      if self.level not in levels and self_norm not in norm_levels:
        return False

    return True

  @property
  def is_error(self) -> bool:
    """Returns True if this line represents an error or fatal severity."""
    return self.level.upper() in ('E', 'F', 'A')

  def __lt__(self, other: Any) -> bool:
    if not isinstance(other, LogLine):
      return NotImplemented
    return self.position < other.position

  def __le__(self, other: Any) -> bool:
    if not isinstance(other, LogLine):
      return NotImplemented
    return self.position <= other.position

  def __gt__(self, other: Any) -> bool:
    if not isinstance(other, LogLine):
      return NotImplemented
    return self.position > other.position

  def __ge__(self, other: Any) -> bool:
    if not isinstance(other, LogLine):
      return NotImplemented
    return self.position >= other.position


class LogcatListenerContext:
  """Context manager for listening to real-time logcat events."""

  def __init__(
      self,
      processor: 'LogcatProcessor',
      pattern: Optional[Union[str, Pattern[str]]] = None,
      tag: Optional[Union[str, Pattern[str], Sequence[str], Set[str]]] = None,
      level: Optional[Union[str, Sequence[str], Set[str]]] = None,
      position: Optional[Union[LogcatPosition, LogLine]] = None,
      max_events: int = 1000,
      timeout_error_cls: type[Exception] = TimeoutError,
  ):
    self._processor = processor
    self._pattern = pattern
    self._tag = tag
    self._level = level
    self._position = (
        position.position if isinstance(position, LogLine) else position
    )
    self._max_events = max_events
    self._timeout_error_cls = timeout_error_cls
    self._events: collections.deque[LogLine] = collections.deque(
        maxlen=max_events
    )
    self._queue: queue.Queue[LogLine] = queue.Queue(maxsize=max_events)
    self._lock = threading.Lock()
    self._stop_event = threading.Event()
    self._thread: Optional[threading.Thread] = None

  @property
  def events(self) -> list[LogLine]:
    """Returns a snapshot list of captured events."""
    with self._lock:
      return list(self._events)

  def has_events(self) -> bool:
    """Returns True if any events have been captured."""
    with self._lock:
      return bool(self._events)

  def get_next_event(self, timeout: Optional[float] = None) -> LogLine:
    """Gets the next event from the queue, blocking up to timeout seconds."""
    try:
      return self._queue.get(block=True, timeout=timeout)
    except queue.Empty:
      raise self._timeout_error_cls(
          f'Timed out after {timeout}s waiting for next logcat event '
          f'(pattern={self._pattern!r}, tag={self._tag!r},'
          f' level={self._level!r})'
      )

  def _dispatch(self, line: LogLine) -> None:
    if line.matches(pattern=self._pattern, tag=self._tag, level=self._level):
      with self._lock:
        self._events.append(line)
      try:
        self._queue.put_nowait(line)
      except queue.Full:
        pass

  def _listen_loop(self) -> None:
    current_offset = (
        self._position._byte_offset
        if self._position
        else LogcatPosition.from_file(self._processor.file_path)._byte_offset
    )
    while not self._stop_event.is_set():
      for offset, line in self._processor._iter_lines(offset=current_offset):
        current_offset = offset
        self._dispatch(line)
        if self._stop_event.is_set():
          break
      time.sleep(0.05)

  def __enter__(self) -> 'LogcatListenerContext':
    self._stop_event.clear()
    self._thread = threading.Thread(target=self._listen_loop, daemon=True)
    self._thread.start()
    return self

  def __exit__(self, exc_type, exc_val, exc_tb) -> None:
    self._stop_event.set()
    if self._thread and self._thread.is_alive():
      self._thread.join(timeout=2.0)
    self._thread = None


class LogcatProcessor:
  """Thread-safe processor for querying and streaming logcat files on the host."""

  def __init__(
      self,
      file_path: str,
      timeout_error_cls: type[Exception] = TimeoutError,
  ):
    self._file_path = file_path
    self._timeout_error_cls = timeout_error_cls

  @property
  def file_path(self) -> str:
    return self._file_path

  def _iter_lines(self, offset: int = 0) -> Iterator[tuple[int, LogLine]]:
    """Yields (line_offset, LogLine) pairs from the file from the given offset."""
    if not os.path.exists(self._file_path):
      return
    try:
      with open(
          self._file_path, 'r', encoding='utf-8', errors='replace', newline=''
      ) as f:
        if offset > 0:
          f.seek(offset)
        while True:
          line_offset = f.tell()
          line = f.readline()
          if not line:
            break
          current_offset = f.tell()
          parsed = LogLine.from_string(line, byte_offset=line_offset)
          if parsed is not None:
            yield current_offset, parsed
    except OSError:
      return

  def get_lines(
      self,
      pattern: Optional[Union[str, Pattern[str]]] = None,
      *,
      tag: Optional[Union[str, Pattern[str], Sequence[str], Set[str]]] = None,
      level: Optional[Union[str, Sequence[str], Set[str]]] = None,
      since: Optional[Union[LogcatPosition, LogLine]] = None,
      max_lines: Optional[int] = None,
  ) -> list[LogLine]:
    """Gets log lines from the file satisfying filter criteria."""
    if (
        pattern is None
        and tag is None
        and level is None
        and since is None
        and max_lines is None
    ):
      raise ValueError(
          'At least one filter criteria (pattern, tag, level, since, or'
          ' max_lines) must be specified. To inspect the latest logs, use'
          ' tail() instead.'
      )

    pos = since.position if isinstance(since, LogLine) else since
    offset = pos._byte_offset if pos else 0
    begin_time = pos.timestamp if pos and offset == 0 else None

    results: list[LogLine] = []
    for _, parsed in self._iter_lines(offset=offset):
      if (
          begin_time
          and LogcatPosition._compare_timestamps(parsed.timestamp, begin_time)
          < 0
      ):
        continue
      if parsed.matches(pattern=pattern, tag=tag, level=level):
        results.append(parsed)
        if max_lines is not None and len(results) >= max_lines:
          break
    return results

  def tail(
      self,
      num_lines: int = 100,
      pattern: Optional[Union[str, Pattern[str]]] = None,
      tag: Optional[Union[str, Pattern[str], Sequence[str], Set[str]]] = None,
      level: Optional[Union[str, Sequence[str], Set[str]]] = None,
  ) -> list[LogLine]:
    """Tails the last num_lines matching log lines by reading backwards from EOF."""
    if num_lines <= 0 or not os.path.exists(self._file_path):
      return []

    buf: collections.deque[LogLine] = collections.deque()
    block_size = 64 * 1024  # 64KB chunks

    try:
      with open(self._file_path, 'rb') as f:
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
        if file_size == 0:
          return []

        remaining = file_size
        remainder = b''
        lines_to_process: list[tuple[int, bytes]] = []

        while remaining > 0 and len(buf) < num_lines:
          read_size = min(block_size, remaining)
          remaining -= read_size
          f.seek(remaining)
          chunk = f.read(read_size)
          data = chunk + remainder

          # Split lines from chunk
          split = data.split(b'\n')
          if remaining > 0:
            remainder = split[0]
            lines_chunk = split[1:]
          else:
            remainder = b''
            lines_chunk = split

          # Calculate offsets and parse lines in reverse order within this block
          current_offset = remaining + len(remainder)
          block_lines: list[tuple[int, LogLine]] = []
          for line_bytes in lines_chunk:
            line_offset = current_offset
            current_offset += len(line_bytes) + 1  # count \n byte
            line_str = line_bytes.decode('utf-8', errors='replace')
            parsed = LogLine.from_string(line_str, byte_offset=line_offset)
            if parsed is not None:
              block_lines.append((line_offset, parsed))

          for _, parsed in reversed(block_lines):
            if parsed.matches(pattern=pattern, tag=tag, level=level):
              buf.appendleft(parsed)
              if len(buf) >= num_lines:
                break
    except OSError:
      return []

    return list(buf)

  def listen(
      self,
      pattern: Optional[Union[str, Pattern[str]]] = None,
      tag: Optional[Union[str, Pattern[str], Sequence[str], Set[str]]] = None,
      level: Optional[Union[str, Sequence[str], Set[str]]] = None,
      position: Optional[Union[LogcatPosition, LogLine]] = None,
  ) -> LogcatListenerContext:
    """Listens for real-time logcat events in a context manager."""
    return LogcatListenerContext(
        processor=self,
        pattern=pattern,
        tag=tag,
        level=level,
        position=position,
        timeout_error_cls=self._timeout_error_cls,
    )

  def wait_for(
      self,
      patterns: Sequence[Union[str, Pattern[str]]],
      timeout_sec: float = 60.0,
      in_order: bool = True,
      since: Optional[Union[LogcatPosition, LogLine]] = None,
  ) -> list[LogLine]:
    """Waits until a sequence of patterns appears in logcat."""
    if not patterns:
      return []

    deadline = time.perf_counter() + timeout_sec

    if in_order:
      matched_lines: list[LogLine] = []
      current_since = since
      for pat in patterns:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
          raise self._timeout_error_cls(
              f'Timed out after {timeout_sec}s waiting for in-order pattern:'
              f' {pat!r}'
          )
        matched, next_offset = self._wait_for_single(
            pattern=pat,
            timeout_sec=remaining,
            since=current_since,
        )
        matched_lines.append(matched)
        current_since = LogcatPosition(_byte_offset=next_offset)
      return matched_lines

    unmatched = list(enumerate(patterns))
    matched_dict: dict[int, LogLine] = {}
    pos = since.position if isinstance(since, LogLine) else since
    offset = pos._byte_offset if pos else 0
    begin_time = pos.timestamp if pos and offset == 0 else None
    scan_offset = offset

    while time.perf_counter() < deadline:
      for current_offset, parsed in self._iter_lines(offset=scan_offset):
        scan_offset = current_offset
        if (
            begin_time
            and LogcatPosition._compare_timestamps(parsed.timestamp, begin_time)
            < 0
        ):
          continue
        for idx, pat in list(unmatched):
          if parsed.matches(pattern=pat):
            matched_dict[idx] = parsed
            unmatched.remove((idx, pat))
        if not unmatched:
          return [matched_dict[i] for i in range(len(patterns))]
      time.sleep(0.1)

    remaining_patterns = [pat for _, pat in unmatched]
    raise self._timeout_error_cls(
        f'Timed out after {timeout_sec}s waiting for patterns:'
        f' {remaining_patterns!r}'
    )

  def _wait_for_single(
      self,
      pattern: Union[str, Pattern[str]],
      timeout_sec: float = 60.0,
      since: Optional[Union[LogcatPosition, LogLine]] = None,
  ) -> tuple[LogLine, int]:
    deadline = time.perf_counter() + timeout_sec
    pos = since.position if isinstance(since, LogLine) else since
    offset = pos._byte_offset if pos else 0
    begin_time = pos.timestamp if pos and offset == 0 else None
    scan_offset = offset

    while time.perf_counter() < deadline:
      for current_offset, parsed in self._iter_lines(offset=scan_offset):
        scan_offset = current_offset
        if (
            begin_time
            and LogcatPosition._compare_timestamps(parsed.timestamp, begin_time)
            < 0
        ):
          continue
        if parsed.matches(pattern=pattern):
          return parsed, current_offset
      time.sleep(0.1)

    raise self._timeout_error_cls(
        f'Timed out after {timeout_sec}s waiting for logcat pattern:'
        f' {pattern!r}'
    )
