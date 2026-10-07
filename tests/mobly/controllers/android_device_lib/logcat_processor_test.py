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
"""Unit tests for mobly.controllers.android_device_lib.logcat_processor."""

import os
import re
import shutil
import tempfile
import threading
import time
import unittest

from mobly.controllers.android_device_lib import logcat_processor

LogLine = logcat_processor.LogLine
LogcatPosition = logcat_processor.LogcatPosition
LogcatProcessor = logcat_processor.LogcatProcessor

SAMPLE_LINES = [
    '--------- beginning of system',
    '08-09 22:00:00.100  1000  1010 I SystemServer: Entered main',
    '2026-08-09 22:00:01.200  1000  1020 D WifiService: Enabling wlan0',
    '08-09 22:00:02.300  2050  2050 I ExampleApp: Initialised \u2713 \u00e9t\u00e9',
    '08-09 22:00:03.400  1000  1040 W BtGatt: Retry 1 for AA:BB',
    '\tat com.example.app.NetworkClient.connect(NetworkClient.java:42)',
    '08-09 22:00:05.150  2050  2060 E ExampleApp: Failed to connect',
    '08-09 22:00:05.800  1000  1040 F BtGatt: Fatal controller error',
]


def _make_line(timestamp='08-09 22:00:00.000', level='I', tag='T', msg='m'):
  return LogLine.from_string(f'{timestamp}  1000  1010 {level} {tag}: {msg}')


class LogLineTest(unittest.TestCase):

  def test_from_string_parses_fields(self):
    line = LogLine.from_string(
        '2026-08-09 22:00:01.200  1000  1020 D WifiService: Enabling wlan0\r\n',
        byte_offset=42,
    )
    self.assertEqual(line.timestamp, '2026-08-09 22:00:01.200')
    self.assertEqual(line.pid, 1000)
    self.assertEqual(line.tid, 1020)
    self.assertEqual(line.level, 'D')
    self.assertEqual(line.tag, 'WifiService')
    self.assertEqual(line.message, 'Enabling wlan0')
    self.assertEqual(line.raw.endswith('wlan0'), True)
    self.assertEqual(line.position._byte_offset, 42)

  def test_from_string_rejects_non_logcat_lines(self):
    self.assertIsNone(LogLine.from_string(''))
    self.assertIsNone(LogLine.from_string('--------- beginning of main'))
    self.assertIsNone(LogLine.from_string(None))

  def test_matches_pattern_str_and_compiled(self):
    line = _make_line(msg='DHCP OFFER received from 192.168.1.1')
    self.assertTrue(line.matches(pattern=r'OFFER.*192\.168'))
    self.assertTrue(line.matches(pattern=re.compile(r'^DHCP')))
    self.assertFalse(line.matches(pattern='DISCOVER'))
    # The pattern is also searched against the full raw line.
    self.assertTrue(line.matches(pattern=r'1000\s+1010'))

  def test_matches_tag_variants(self):
    line = _make_line(tag='WifiService')
    self.assertTrue(line.matches(tag='WifiService'))
    self.assertFalse(line.matches(tag='Wifi'))
    self.assertTrue(line.matches(tag=re.compile('^Wifi')))
    self.assertTrue(line.matches(tag=['BtGatt', 'WifiService']))
    self.assertTrue(line.matches(tag={'WifiService'}))
    self.assertFalse(line.matches(tag=('BtGatt',)))
    # A tag object that is neither str, regex nor iterable never filters.
    self.assertTrue(line.matches(tag=object()))

  def test_matches_level_normalisation(self):
    line = _make_line(level='E')
    self.assertTrue(line.matches(level='E'))
    self.assertTrue(line.matches(level='error'))
    self.assertTrue(line.matches(level=['W', 'ERROR']))
    self.assertTrue(line.matches(level={'e'}))
    self.assertFalse(line.matches(level='W'))
    self.assertFalse(line.matches(level=['V', 'D', 'I']))
    fatal = _make_line(level='F')
    self.assertTrue(fatal.matches(level='A'))
    self.assertTrue(fatal.matches(level='ASSERT'))

  def test_matches_combined_criteria(self):
    line = _make_line(level='E', tag='ExampleApp', msg='Failed to connect')
    self.assertTrue(line.matches(pattern='Failed', tag='ExampleApp', level='E'))
    self.assertFalse(
        line.matches(pattern='Failed', tag='ExampleApp', level='I')
    )
    self.assertFalse(line.matches(pattern='Failed', tag='Other', level='E'))
    self.assertFalse(line.matches(pattern='Nope', tag='ExampleApp', level='E'))

  def test_line_filter_is_equivalent_to_matches(self):
    lines = [
        _make_line(level=lvl, tag=tag, msg=msg)
        for lvl in 'VDIWEF'
        for tag in ('WifiService', 'BtGatt', 'ExampleApp')
        for msg in ('DHCP OFFER', 'Failed to connect', 'hello')
    ]
    criteria = [
        dict(),
        dict(pattern='DHCP'),
        dict(pattern=re.compile('connect$')),
        dict(tag='BtGatt'),
        dict(tag=re.compile('Service')),
        dict(tag=['WifiService', 'ExampleApp']),
        dict(level='error'),
        dict(level=['W', 'e', 'FATAL']),
        dict(pattern='hello', tag={'BtGatt'}, level=('I', 'D')),
    ]
    for kwargs in criteria:
      filt = logcat_processor._LineFilter(**kwargs)
      for line in lines:
        self.assertEqual(
            filt.matches(line), line.matches(**kwargs), (kwargs, line.raw)
        )

  def test_line_filter_compiles_pattern_once(self):
    filt = logcat_processor._LineFilter(pattern='abc')
    self.assertIsInstance(filt._regex, re.Pattern)
    compiled = re.compile('xyz')
    self.assertIs(
        logcat_processor._LineFilter(pattern=compiled)._regex, compiled
    )


class TimestampCutoffTest(unittest.TestCase):

  TIMESTAMPS = [
      None,
      '',
      '08-09 22:00:00.000',
      '08-09 22:00:00.001',
      '08-09 21:59:59.999',
      '2026-08-09 22:00:00.000',
      '2025-08-09 22:00:00.000',
      '2027-01-01 00:00:00.000',
      '2026-08-09T22:00:00.5',
      '08-09 22:00',
      'garbage',
      '08/09 22:00:00',
  ]

  def test_is_before_matches_compare_timestamps(self):
    for begin in self.TIMESTAMPS:
      for ts in self.TIMESTAMPS:
        expected = bool(begin) and (
            LogcatPosition._compare_timestamps(ts, begin) < 0
        )
        self.assertEqual(
            logcat_processor._is_before(ts, begin or None),
            expected,
            (ts, begin),
        )


class _FileTestBase(unittest.TestCase):

  def setUp(self):
    self.tmp_dir = tempfile.mkdtemp()
    self.log_file = os.path.join(self.tmp_dir, 'logcat.txt')
    self.processor = LogcatProcessor(self.log_file)

  def tearDown(self):
    shutil.rmtree(self.tmp_dir)

  def _write(self, text, mode='w'):
    with open(self.log_file, mode, encoding='utf-8', newline='') as f:
      f.write(text)

  def _write_bytes(self, data, mode='wb'):
    with open(self.log_file, mode) as f:
      f.write(data)

  def _write_sample(self, newline='\n'):
    self._write(newline.join(SAMPLE_LINES) + newline)


class IterLinesTest(_FileTestBase):

  def test_missing_file_yields_nothing(self):
    self.assertEqual(list(self.processor._iter_lines()), [])
    self.assertEqual(list(self.processor._iter_lines(offset=10)), [])

  def test_offsets_are_byte_offsets_with_multibyte_chars(self):
    self._write_sample()
    data = open(self.log_file, 'rb').read()
    results = list(self.processor._iter_lines())
    # Only parseable lines are yielded.
    self.assertEqual(len(results), 6)
    for next_offset, line in results:
      start = line.position._byte_offset
      raw_bytes = data[start:next_offset]
      self.assertEqual(raw_bytes.decode('utf-8'), line.raw + '\n')
    # Yielded next_offset of a line equals the file position after it, so
    # resuming from there continues with the following line.
    first_next, _ = results[0]
    resumed = list(self.processor._iter_lines(offset=first_next))
    self.assertEqual(
        [l.raw for _, l in resumed], [l.raw for _, l in results[1:]]
    )

  def test_offsets_consistent_with_tail(self):
    self._write_sample()
    forward = {l.raw: l for _, l in self.processor._iter_lines()}
    backward = self.processor.tail(num_lines=100)
    self.assertEqual(len(backward), len(forward))
    for line in backward:
      self.assertEqual(
          line.position._byte_offset,
          forward[line.raw].position._byte_offset,
      )
      self.assertEqual(line.raw, forward[line.raw].raw)

  def test_crlf_line_endings(self):
    self._write_sample(newline='\r\n')
    data = open(self.log_file, 'rb').read()
    results = list(self.processor._iter_lines())
    self.assertEqual(len(results), 6)
    for next_offset, line in results:
      self.assertFalse(line.raw.endswith('\r'))
      start = line.position._byte_offset
      self.assertEqual(data[start:next_offset], (line.raw + '\r\n').encode())
    self.assertEqual(results[-1][0], os.path.getsize(self.log_file))

  def test_invalid_utf8_is_replaced(self):
    self._write_bytes(
        b'08-09 22:00:00.100  1000  1010 I Tag: bad \xff\xfe byte\n'
        b'08-09 22:00:00.200  1000  1010 I Tag: ok\n'
    )
    results = list(self.processor._iter_lines())
    self.assertEqual(len(results), 2)
    self.assertEqual(results[0][1].message, 'bad \ufffd\ufffd byte')
    # The replaced bytes still count as 1 byte each in offsets.
    self.assertEqual(
        results[1][1].position._byte_offset,
        len(b'08-09 22:00:00.100  1000  1010 I Tag: bad \xff\xfe byte\n'),
    )

  def test_last_line_without_newline_is_yielded(self):
    self._write('08-09 22:00:00.100  1000  1010 I Tag: partial')
    results = list(self.processor._iter_lines())
    self.assertEqual(len(results), 1)
    self.assertEqual(results[0][1].message, 'partial')
    self.assertEqual(results[0][0], os.path.getsize(self.log_file))

  def test_offset_beyond_eof_yields_nothing(self):
    self._write_sample()
    size = os.path.getsize(self.log_file)
    self.assertEqual(list(self.processor._iter_lines(offset=size)), [])
    self.assertEqual(list(self.processor._iter_lines(offset=size + 100)), [])

  def test_generator_closes_file_when_abandoned(self):
    self._write_sample()
    reader = logcat_processor._LineReader(self.log_file)
    with reader:
      gen = reader.read_lines()
      next(gen)
      self.assertIsNotNone(reader._file)
    self.assertIsNone(reader._file)


class LineReaderTest(_FileTestBase):

  def test_reader_picks_up_appended_data_without_reopening(self):
    self._write(SAMPLE_LINES[1] + '\n')
    with logcat_processor._LineReader(self.log_file) as reader:
      first = list(reader.read_lines())
      self.assertEqual(len(first), 1)
      handle = reader._file
      self.assertEqual(list(reader.read_lines()), [])
      self._write(SAMPLE_LINES[2] + '\n', mode='a')
      second = list(reader.read_lines())
      self.assertEqual(len(second), 1)
      self.assertEqual(second[0][1].tag, 'WifiService')
      self.assertIs(reader._file, handle)
      self.assertEqual(reader.offset, os.path.getsize(self.log_file))

  def test_reader_opens_lazily_when_file_appears(self):
    with logcat_processor._LineReader(self.log_file) as reader:
      self.assertEqual(list(reader.read_lines()), [])
      self.assertIsNone(reader._file)
      self._write(SAMPLE_LINES[1] + '\n')
      self.assertEqual(len(list(reader.read_lines())), 1)
      self.assertIsNotNone(reader._file)

  def test_reader_starts_from_offset(self):
    self._write_sample()
    all_lines = list(self.processor._iter_lines())
    offset = all_lines[2][0]
    with logcat_processor._LineReader(self.log_file, offset) as reader:
      self.assertEqual(
          [l.raw for _, l in reader.read_lines()],
          [l.raw for _, l in all_lines[3:]],
      )

  def test_reader_close_is_idempotent(self):
    self._write_sample()
    reader = logcat_processor._LineReader(self.log_file)
    list(reader.read_lines())
    reader.close()
    reader.close()
    self.assertIsNone(reader._file)

  def test_reader_consumes_partial_last_line_by_default(self):
    line = SAMPLE_LINES[1]
    split = line.index('main')
    self._write(line[:split])
    with logcat_processor._LineReader(self.log_file) as reader:
      got = list(reader.read_lines())
      self.assertEqual(len(got), 1)
      self.assertEqual(got[0][1].raw, line[:split])
      self.assertEqual(reader.offset, split)

  def test_reader_waits_for_newline_on_partial_last_line(self):
    line = SAMPLE_LINES[1]
    split = line.index('main')
    self._write(line[:split])
    with logcat_processor._LineReader(
        self.log_file, wait_for_newline=True
    ) as reader:
      self.assertEqual(list(reader.read_lines()), [])
      self.assertEqual(reader.offset, 0)
      self._write(line[split:] + '\n', mode='a')
      got = list(reader.read_lines())
      self.assertEqual(len(got), 1)
      self.assertEqual(got[0][1].raw, line)
      self.assertEqual(got[0][0], len(line) + 1)


class PartialLineWaitForTest(_FileTestBase):

  def test_wait_for_matches_line_split_across_writes(self):
    line = SAMPLE_LINES[1]
    split = line.index('Entered')
    self._write(line[:split])

    def append_rest():
      time.sleep(0.2)
      self._write(line[split:] + '\n', mode='a')

    t = threading.Thread(target=append_rest)
    t.start()
    try:
      matched = self.processor.wait_for(['Entered main'], timeout_sec=2)
    finally:
      t.join()
    self.assertEqual(matched[0].raw, line)


class GetLinesTest(_FileTestBase):

  def test_requires_a_filter(self):
    self._write_sample()
    with self.assertRaises(ValueError):
      self.processor.get_lines()

  def test_filters(self):
    self._write_sample()
    errors = self.processor.get_lines(level=['E', 'F'])
    self.assertEqual([l.tag for l in errors], ['ExampleApp', 'BtGatt'])
    self.assertEqual(
        [l.message for l in self.processor.get_lines(tag='BtGatt')],
        ['Retry 1 for AA:BB', 'Fatal controller error'],
    )
    self.assertEqual(len(self.processor.get_lines(pattern=r'\u2713')), 1)
    self.assertEqual(len(self.processor.get_lines(max_lines=2)), 2)

  def test_since_position_offset(self):
    self._write_sample()
    start = LogcatPosition.from_file(self.log_file)
    self._write('08-09 22:00:06.000  1000  1030 I WifiService: New\n', mode='a')
    lines = self.processor.get_lines(tag='WifiService', since=start)
    self.assertEqual([l.message for l in lines], ['New'])
    self.assertTrue(lines[0].position > start)

  def test_since_logline(self):
    self._write_sample()
    warn = self.processor.get_lines(level='W')[0]
    after = self.processor.get_lines(max_lines=10, since=warn)
    # A LogLine position points at the start of that line, so it is inclusive.
    self.assertEqual([l.level for l in after], ['W', 'E', 'F'])

  def test_since_timestamp_only_cutoff(self):
    self._write_sample()
    since = LogcatPosition(timestamp='08-09 22:00:03.400', _byte_offset=0)
    lines = self.processor.get_lines(max_lines=100, since=since)
    self.assertEqual([l.level for l in lines], ['W', 'E', 'F'])
    # Year-less and full-date timestamps compare on month/day/time.
    since = LogcatPosition(timestamp='2026-08-09 22:00:01.200', _byte_offset=0)
    lines = self.processor.get_lines(max_lines=100, since=since)
    self.assertEqual(lines[0].tag, 'WifiService')
    self.assertEqual(len(lines), 5)

  def test_since_unparseable_timestamp_falls_back_to_string_compare(self):
    self._write_sample()
    since = LogcatPosition(timestamp='09', _byte_offset=0)
    lines = self.processor.get_lines(max_lines=100, since=since)
    # '08-09 ...' < '09' lexicographically, but '2026-...' > '09'.
    self.assertEqual([l.tag for l in lines], ['WifiService'])
    since = LogcatPosition(timestamp='00', _byte_offset=0)
    self.assertEqual(
        len(self.processor.get_lines(max_lines=100, since=since)), 6
    )


class TailTest(_FileTestBase):

  def test_tail_basic(self):
    self._write_sample()
    last = self.processor.tail(num_lines=2)
    self.assertEqual([l.level for l in last], ['E', 'F'])
    self.assertEqual(self.processor.tail(num_lines=0), [])
    self.assertEqual(self.processor.tail(num_lines=1, tag='Nope'), [])

  def test_tail_missing_or_empty_file(self):
    self.assertEqual(self.processor.tail(), [])
    self._write('')
    self.assertEqual(self.processor.tail(), [])

  def test_tail_across_block_boundary_matches_forward_scan(self):
    filler = '08-09 22:00:05.000  1000  1030 I Filler: padding \u00e9\n'
    self._write(filler * 3000)
    self._write('08-09 22:00:06.000  1000  1030 I WifiService: Last\n', 'a')
    forward = [l for _, l in self.processor._iter_lines()]
    backward = self.processor.tail(num_lines=2500)
    self.assertEqual(
        [l.raw for l in backward], [l.raw for l in forward[-2500:]]
    )
    self.assertEqual(backward[-1].message, 'Last')
    self.assertEqual(
        [l.position._byte_offset for l in backward],
        [l.position._byte_offset for l in forward[-2500:]],
    )


class WaitForTest(_FileTestBase):

  def test_wait_for_in_order(self):
    self._write_sample()
    lines = self.processor.wait_for(
        ['Entered', 'Retry', 'Fatal'], timeout_sec=2.0
    )
    self.assertEqual(
        [l.tag for l in lines], ['SystemServer', 'BtGatt', 'BtGatt']
    )
    self.assertTrue(lines[0] < lines[1] < lines[2])

  def test_wait_for_in_order_respects_order(self):
    self._write_sample()
    with self.assertRaises(TimeoutError) as cm:
      self.processor.wait_for(['Fatal', 'Entered'], timeout_sec=0.3)
    self.assertIn("'Entered'", str(cm.exception))

  def test_wait_for_unordered(self):
    self._write_sample()
    lines = self.processor.wait_for(
        ['Fatal', 'Entered'], in_order=False, timeout_sec=2.0
    )
    self.assertEqual([l.tag for l in lines], ['BtGatt', 'SystemServer'])

  def test_wait_for_unordered_timeout_lists_remaining(self):
    self._write_sample()
    with self.assertRaises(TimeoutError) as cm:
      self.processor.wait_for(
          ['Entered', 'Never'], in_order=False, timeout_sec=0.3
      )
    self.assertIn("['Never']", str(cm.exception))

  def test_wait_for_since_and_appended_data(self):
    self._write_sample()
    start = LogcatPosition.from_file(self.log_file)
    results = []

    def _wait():
      results.extend(
          self.processor.wait_for(
              ['Entered', 'Later'], since=start, timeout_sec=5.0
          )
      )

    import threading  # pylint: disable=g-import-not-at-top

    t = threading.Thread(target=_wait)
    t.start()
    time.sleep(0.3)
    self._write('08-09 22:00:07.000  1000  1030 I Tag: Entered again\n', 'a')
    self._write('08-09 22:00:08.000  1000  1030 I Tag: Later\n', 'a')
    t.join(timeout=5.0)
    self.assertFalse(t.is_alive())
    self.assertEqual([l.message for l in results], ['Entered again', 'Later'])

  def test_wait_for_file_created_after_start(self):
    with self.assertRaises(TimeoutError):
      self.processor.wait_for(['x'], timeout_sec=0.2)
    import threading  # pylint: disable=g-import-not-at-top

    results = []
    t = threading.Thread(
        target=lambda: results.extend(
            self.processor.wait_for(['hello'], timeout_sec=5.0)
        )
    )
    t.start()
    time.sleep(0.3)
    self._write('08-09 22:00:08.000  1000  1030 I Tag: hello\n')
    t.join(timeout=5.0)
    self.assertFalse(t.is_alive())
    self.assertEqual(results[0].message, 'hello')

  def test_wait_for_single_returns_offset_after_line(self):
    self._write_sample()
    line, offset = self.processor._wait_for_single('Retry', timeout_sec=1.0)
    self.assertEqual(line.tag, 'BtGatt')
    following = list(self.processor._iter_lines(offset=offset))
    self.assertEqual([l.level for _, l in following], ['E', 'F'])

  def test_wait_for_empty_patterns(self):
    self.assertEqual(self.processor.wait_for([], timeout_sec=1.0), [])


class ListenTest(_FileTestBase):

  def test_listen_receives_appended_lines(self):
    self._write_sample()
    with self.processor.listen(tag='WifiService') as listener:
      self.assertFalse(listener.has_events())
      self._write('08-09 22:00:07.000  1000  1030 I WifiService: One\n', 'a')
      self.assertEqual(listener.get_next_event(timeout=2.0).message, 'One')
      self._write('08-09 22:00:07.100  1000  1030 I Other: skip\n', 'a')
      self._write('08-09 22:00:07.200  1000  1030 I WifiService: Two\n', 'a')
      self.assertEqual(listener.get_next_event(timeout=2.0).message, 'Two')
      self.assertEqual([e.message for e in listener.events], ['One', 'Two'])
    self.assertIsNone(listener._thread)

  def test_listen_from_position(self):
    self._write_sample()
    pos = LogcatPosition(_byte_offset=0)
    with self.processor.listen(level='F', position=pos) as listener:
      event = listener.get_next_event(timeout=2.0)
    self.assertEqual(event.message, 'Fatal controller error')

  def test_listen_file_created_after_start(self):
    with self.processor.listen(pattern='hello') as listener:
      time.sleep(0.2)
      self._write('08-09 22:00:08.000  1000  1030 I Tag: hello\n')
      self.assertEqual(listener.get_next_event(timeout=2.0).message, 'hello')

  def test_listen_timeout_message(self):
    self._write_sample()
    with self.processor.listen(pattern='nothing', tag='X') as listener:
      with self.assertRaises(TimeoutError) as cm:
        listener.get_next_event(timeout=0.1)
    self.assertIn("pattern='nothing'", str(cm.exception))


if __name__ == '__main__':
  unittest.main()
