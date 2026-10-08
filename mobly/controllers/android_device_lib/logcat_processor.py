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
from typing import (
    Any,
    ClassVar,
    Iterator,
    Optional,
    Pattern,
    Sequence,
    Set,
    Union,
)

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

# Splits a timestamp into its date and time halves ("MM-DD HH:MM:SS.mmm").
_TIMESTAMP_SPLIT_RE = re.compile(r'[\sT]+')
# Splits the date half into its numeric elements ("2026-08-09" or "08/09").
_DATE_SPLIT_RE = re.compile(r'[-/]')

# Encoding used for all logcat file reads. Mirrors the text-mode arguments the
# logcat service uses when it opens the same file.
_ENCODING = 'utf-8'
_ENCODING_ERRORS = 'replace'


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
    """Captures a snapshot of a logcat file at the current moment."""
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
    """Parses a timestamp into (year, month, day, hr, min, sec, microsec)."""
    if not t:
      raise ValueError('Empty timestamp string')

    date_part, time_part = _TIMESTAMP_SPLIT_RE.split(t.strip(), maxsplit=1)
    date_elements = [int(x) for x in _DATE_SPLIT_RE.split(date_part)]
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
    level: str, single-letter severity level ('V', 'D', 'I', 'W', 'E', 'F',
      'S').
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
      r'^(?P<timestamp>(?:\d{4}[-/])?\d{2}[-/]\d{2}\s+'
      r'\d{2}:\d{2}:\d{2}(?:\.\d+)?)'
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
    return _LineFilter(pattern=pattern, tag=tag, level=level).matches(self)

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


class _LineFilter:
  """Pre-normalised (pattern, tag, level) filter applied to many LogLines.

  Normalising the criteria once (compiling the regex, building the level sets)
  and reusing the result is much cheaper than doing it per line, which matters
  when scanning large logcat files. The matching semantics are identical to
  :meth:`LogLine.matches`.
  """

  def __init__(
      self,
      pattern: Optional[Union[str, Pattern[str]]] = None,
      tag: Optional[Union[str, Pattern[str], Sequence[str], Set[str]]] = None,
      level: Optional[Union[str, Sequence[str], Set[str]]] = None,
  ):
    self._regex: Optional[Pattern[str]] = None
    if pattern is not None:
      self._regex = re.compile(pattern) if isinstance(pattern, str) else pattern

    # _tag_mode: None (no filter), 'eq', 'search', 'in' or 'noop' (an object
    # that is neither a str, a regex nor an Iterable never filters anything).
    self._tag_mode: Optional[str] = None
    self._tag: Any = tag
    if tag is not None:
      if isinstance(tag, str):
        self._tag_mode = 'eq'
      elif hasattr(tag, 'search'):
        self._tag_mode = 'search'
      elif isinstance(tag, Iterable):
        self._tag_mode = 'in'
        try:
          self._tag = frozenset(tag)
        except TypeError:
          self._tag = tuple(tag)
      else:
        self._tag_mode = 'noop'

    self._levels: Optional[frozenset[Any]] = None
    self._norm_levels: Optional[frozenset[str]] = None
    if level is not None:
      levels = {level} if isinstance(level, str) else set(level)
      self._levels = frozenset(levels)
      self._norm_levels = frozenset(
          _LEVEL_NORM_MAP.get(str(l).upper(), str(l).upper()) for l in levels
      )

  def matches(self, line: LogLine) -> bool:
    """Returns True if the line satisfies every configured criterion."""
    regex = self._regex
    if regex is not None and not (
        regex.search(line.message) or regex.search(line.raw)
    ):
      return False

    tag_mode = self._tag_mode
    if tag_mode == 'eq':
      if line.tag != self._tag:
        return False
    elif tag_mode == 'search':
      if not self._tag.search(line.tag):
        return False
    elif tag_mode == 'in':
      if line.tag not in self._tag:
        return False

    if self._levels is not None:
      self_norm = _LEVEL_NORM_MAP.get(line.level.upper(), line.level.upper())
      if line.level not in self._levels and self_norm not in self._norm_levels:
        return False

    return True


class _TimeBound:
  """A lower timestamp bound whose own timestamp is parsed exactly once.

  ``since=`` filtering compares every scanned line against the same bound, so
  parsing the bound up front avoids re-parsing it per line. The comparison
  semantics are identical to :meth:`LogcatPosition._compare_timestamps`.
  """

  def __init__(self, begin_time: str):
    self._begin_time = begin_time
    self._parsed: Optional[tuple[int, ...]] = None
    try:
      self._parsed = LogcatPosition._parse_timestamp(begin_time)
    except (ValueError, IndexError):
      pass

  def is_before(self, timestamp: Optional[str]) -> bool:
    """True if `timestamp` is chronologically before this bound."""
    if not timestamp:
      return True
    p2 = self._parsed
    if p2 is not None:
      try:
        p1 = LogcatPosition._parse_timestamp(timestamp)
      except (ValueError, IndexError):
        p1 = None
      if p1 is not None:
        if p1[0] == 0 or p2[0] == 0:
          p1 = (0,) + p1[1:]
          p2 = (0,) + p2[1:]
        return p1 < p2
    return str(timestamp) < str(self._begin_time)


def _is_before(timestamp: Optional[str], bound: Optional[_TimeBound]) -> bool:
  """True if `timestamp` is chronologically before `bound` (if set)."""
  return bound is not None and bound.is_before(timestamp)


class _LineReader:
  """Incrementally reads parsed LogLines from a (possibly growing) file.

  The file is opened lazily in binary mode and the handle is kept open across
  successive :meth:`read_lines` calls, so that polling loops do not pay for an
  ``open()`` on every iteration. Byte offsets are tracked by summing the length
  of each raw line, which is both exact and far cheaper than text-mode
  ``tell()``; the offsets are therefore directly comparable with the ones
  computed by :meth:`LogcatProcessor.tail`.

  Always use as a context manager (or call :meth:`close`) so the handle is not
  held longer than necessary.
  """

  def __init__(
      self, file_path: str, offset: int = 0, wait_for_newline: bool = False
  ):
    self._file_path = file_path
    self.offset = offset
    self._wait_for_newline = wait_for_newline
    self._file: Optional[Any] = None

  def __enter__(self) -> '_LineReader':
    return self

  def __exit__(self, exc_type, exc_val, exc_tb) -> None:
    self.close()

  def close(self) -> None:
    """Closes the underlying file handle, if any."""
    f, self._file = self._file, None
    if f is not None:
      try:
        f.close()
      except OSError:
        pass

  def _ensure_open(self) -> bool:
    if self._file is not None:
      return True
    if not os.path.exists(self._file_path):
      return False
    try:
      f = open(self._file_path, 'rb')
    except OSError:
      return False
    try:
      if self.offset > 0:
        f.seek(self.offset)
    except OSError:
      f.close()
      return False
    self._file = f
    return True

  def read_lines(self) -> Iterator[tuple[int, LogLine]]:
    """Yields (offset_after_line, LogLine) for every new parseable line.

    Reading stops at the current end of file; calling this again later picks up
    data appended in the meantime. On an I/O error the handle is closed and the
    iteration ends; the next call will try to re-open the file.

    With ``wait_for_newline`` the reader does not consume a trailing line that
    has no newline yet: logcat output is block-buffered, so a poll can observe
    a half-written line, and consuming it would split one log line into two
    fragments that neither match a pattern. The partial line is re-read in
    full on a later call once the rest has been flushed. Consequently, if the
    writer dies without terminating its last line, that line is never yielded
    by a ``wait_for_newline`` reader (one-shot :meth:`LogcatProcessor.get_lines`
    and :meth:`LogcatProcessor.tail` still return it).
    """
    if not self._ensure_open():
      return
    f = self._file
    offset = self.offset
    try:
      while True:
        raw = f.readline()
        if not raw:
          break
        if self._wait_for_newline and not raw.endswith(b'\n'):
          f.seek(offset)
          break
        line_offset = offset
        offset += len(raw)
        self.offset = offset
        parsed = LogLine.from_string(
            raw.decode(_ENCODING, _ENCODING_ERRORS), byte_offset=line_offset
        )
        if parsed is not None:
          yield offset, parsed
    except OSError:
      self.close()
      return


def _resolve_since(
    since: Optional[Union[LogcatPosition, LogLine]],
) -> tuple[int, Optional[_TimeBound]]:
  """Converts a `since` argument into (byte_offset, lower time bound).

  The time bound is only used when the position carries no byte offset; a
  position with an offset is already exact.
  """
  pos = since.position if isinstance(since, LogLine) else since
  offset = pos._byte_offset if pos else 0
  begin_time = pos.timestamp if pos and offset == 0 else None
  return offset, _TimeBound(begin_time) if begin_time else None


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
    self._filter = _LineFilter(pattern=pattern, tag=tag, level=level)
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
    if self._filter.matches(line):
      with self._lock:
        self._events.append(line)
      try:
        self._queue.put_nowait(line)
      except queue.Full:
        pass

  def _listen_loop(self, start_offset: int) -> None:
    stop_event = self._stop_event
    # A single reader (and file handle) is reused for the whole listen session
    # instead of re-opening the file on every poll.
    with _LineReader(
        self._processor.file_path, start_offset, wait_for_newline=True
    ) as reader:
      while not stop_event.is_set():
        for _, line in reader.read_lines():
          self._dispatch(line)
          if stop_event.is_set():
            break
        stop_event.wait(0.05)

  def __enter__(self) -> 'LogcatListenerContext':
    self._stop_event.clear()
    # Snapshot the start offset before the thread starts so that lines
    # appended right after `listen()` returns are not missed.
    start_offset = (
        self._position._byte_offset
        if self._position
        else LogcatPosition.from_file(self._processor.file_path)._byte_offset
    )
    self._thread = threading.Thread(
        target=self._listen_loop, args=(start_offset,), daemon=True
    )
    self._thread.start()
    return self

  def __exit__(self, exc_type, exc_val, exc_tb) -> None:
    self._stop_event.set()
    if self._thread and self._thread.is_alive():
      self._thread.join(timeout=2.0)
    self._thread = None


class LogcatProcessor:
  """Thread-safe processor for querying and streaming logcat files."""

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
    """Yields (offset_after_line, LogLine) pairs from file from given offset.

    The file is read in binary mode and byte offsets are derived from the raw
    line lengths, so they match the offsets produced by :meth:`tail`. Lines are
    decoded as UTF-8 with replacement of undecodable bytes.
    """
    with _LineReader(self._file_path, offset) as reader:
      yield from reader.read_lines()

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

    offset, begin_time = _resolve_since(since)
    line_filter = _LineFilter(pattern=pattern, tag=tag, level=level)

    results: list[LogLine] = []
    for _, parsed in self._iter_lines(offset=offset):
      if _is_before(parsed.timestamp, begin_time):
        continue
      if line_filter.matches(parsed):
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
    """Tails last num_lines matching log lines reading backwards from EOF."""
    if num_lines <= 0 or not os.path.exists(self._file_path):
      return []

    buf: collections.deque[LogLine] = collections.deque()
    block_size = 64 * 1024  # 64KB chunks
    line_filter = _LineFilter(pattern=pattern, tag=tag, level=level)

    try:
      with open(self._file_path, 'rb') as f:
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
        if file_size == 0:
          return []

        remaining = file_size
        remainder = b''

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
            current_offset = remaining + len(remainder) + 1
          else:
            remainder = b''
            lines_chunk = split
            current_offset = 0

          # Calculate offsets and parse lines in reverse order within this block
          block_lines: list[LogLine] = []
          for line_bytes in lines_chunk:
            line_offset = current_offset
            current_offset += len(line_bytes) + 1  # count \n byte
            line_str = line_bytes.decode(_ENCODING, _ENCODING_ERRORS)
            parsed = LogLine.from_string(line_str, byte_offset=line_offset)
            if parsed is not None:
              block_lines.append(parsed)

          for parsed in reversed(block_lines):
            if line_filter.matches(parsed):
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
    offset, begin_time = _resolve_since(since)

    if in_order:
      matched_lines: list[LogLine] = []
      with _LineReader(
          self._file_path, offset, wait_for_newline=True
      ) as reader:
        for pat in patterns:
          remaining = deadline - time.perf_counter()
          if remaining <= 0:
            raise self._timeout_error_cls(
                f'Timed out after {timeout_sec}s waiting for in-order pattern:'
                f' {pat!r}'
            )
          matched_lines.append(
              self._wait_on_reader(
                  reader,
                  _LineFilter(pattern=pat),
                  begin_time,
                  deadline,
                  remaining,
                  pat,
              )
          )
          # Subsequent patterns continue right after the matched line; the
          # timestamp bound only applies to the initial scan.
          begin_time = None
      return matched_lines

    unmatched: list[tuple[int, Union[str, Pattern[str]], _LineFilter]] = [
        (idx, pat, _LineFilter(pattern=pat)) for idx, pat in enumerate(patterns)
    ]
    matched_dict: dict[int, LogLine] = {}

    with _LineReader(self._file_path, offset, wait_for_newline=True) as reader:
      while time.perf_counter() < deadline:
        for _, parsed in reader.read_lines():
          if _is_before(parsed.timestamp, begin_time):
            continue
          for entry in list(unmatched):
            if entry[2].matches(parsed):
              matched_dict[entry[0]] = parsed
              unmatched.remove(entry)
          if not unmatched:
            return [matched_dict[i] for i in range(len(patterns))]
        time.sleep(0.1)

    remaining_patterns = [pat for _, pat, _ in unmatched]
    raise self._timeout_error_cls(
        f'Timed out after {timeout_sec}s waiting for patterns:'
        f' {remaining_patterns!r}'
    )

  def _wait_on_reader(
      self,
      reader: _LineReader,
      line_filter: _LineFilter,
      begin_time: Optional[_TimeBound],
      deadline: float,
      timeout_sec: float,
      pattern: Union[str, Pattern[str]],
  ) -> LogLine:
    """Polls `reader` until a line matches `line_filter` or `deadline` passes."""
    while time.perf_counter() < deadline:
      for _, parsed in reader.read_lines():
        if _is_before(parsed.timestamp, begin_time):
          continue
        if line_filter.matches(parsed):
          return parsed
      time.sleep(0.1)

    raise self._timeout_error_cls(
        f'Timed out after {timeout_sec}s waiting for logcat pattern:'
        f' {pattern!r}'
    )

  def _wait_for_single(
      self,
      pattern: Union[str, Pattern[str]],
      timeout_sec: float = 60.0,
      since: Optional[Union[LogcatPosition, LogLine]] = None,
  ) -> tuple[LogLine, int]:
    """Waits for a single pattern; returns (line, offset after that line)."""
    deadline = time.perf_counter() + timeout_sec
    offset, begin_time = _resolve_since(since)
    with _LineReader(self._file_path, offset, wait_for_newline=True) as reader:
      matched = self._wait_on_reader(
          reader,
          _LineFilter(pattern=pattern),
          begin_time,
          deadline,
          timeout_sec,
          pattern,
      )
      return matched, reader.offset
