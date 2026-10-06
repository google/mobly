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
"""
Helper module for common telnet capability to communicate with
AttenuatorDevice(s).

User code shouldn't need to directly access this class.
"""

import re
import select
import socket
import time

from mobly.controllers import attenuator

# Telnet protocol bytes (RFC 854). Only what is needed to strip option
# negotiation from the stream; SCPI instruments speak plain text otherwise.
_IAC = 255
_DONT = 254
_DO = 253
_WONT = 252
_WILL = 251
_SB = 250
_SE = 240


class _Telnet:
  """Minimal replacement for the `telnetlib.Telnet` subset used here.

  `telnetlib` was removed from the standard library in Python 3.13 (PEP 594).
  This implements `open`, `read_until`, `expect`, `write` and `close` with the
  same semantics as the stdlib class, including stripping of IAC command
  sequences from the inbound stream.
  """

  def __init__(self):
    self._sock = None
    self._buf = b''  # Decoded (IAC-stripped) bytes not yet consumed.
    self._raw = b''  # Raw bytes that may end mid IAC sequence.

  def open(self, host, port, timeout):
    self._sock = socket.create_connection((host, port), timeout)

  def close(self):
    if self._sock:
      self._sock.close()
      self._sock = None

  def write(self, data):
    self._sock.sendall(data.replace(bytes([_IAC]), bytes([_IAC, _IAC])))

  def _fill(self, timeout):
    """Reads whatever is available within `timeout` into the buffer.

    Returns:
      False if the connection was closed by the peer, True otherwise.
    """
    ready, _, _ = select.select([self._sock], [], [], timeout)
    if not ready:
      return True
    data = self._sock.recv(4096)
    if not data:
      return False
    self._raw += data
    self._buf += self._strip_iac()
    return True

  def _strip_iac(self):
    """Removes complete IAC sequences from `_raw`, returning clean bytes."""
    out = bytearray()
    raw = self._raw
    i = 0
    while i < len(raw):
      b = raw[i]
      if b != _IAC:
        out.append(b)
        i += 1
        continue
      if i + 1 >= len(raw):
        break  # Incomplete sequence, wait for more data.
      cmd = raw[i + 1]
      if cmd == _IAC:
        out.append(_IAC)
        i += 2
      elif cmd in (_DO, _DONT, _WILL, _WONT):
        if i + 2 >= len(raw):
          break
        i += 3
      elif cmd == _SB:
        end = raw.find(bytes([_IAC, _SE]), i + 2)
        if end == -1:
          break
        i = end + 2
      else:
        i += 2
    self._raw = raw[i:]
    return bytes(out)

  def read_until(self, expected, timeout):
    """Reads until `expected` is seen or `timeout` seconds pass.

    Returns everything read so far in either case, like `telnetlib`.
    """
    return self.expect([re.escape(expected)], timeout)[2]

  def expect(self, patterns, timeout):
    """Reads until one of the regex `patterns` (bytes) matches.

    Returns:
      (index, match, text): like `telnetlib.Telnet.expect`. On timeout or
      EOF `index` is -1, `match` is None and `text` is whatever was read.
    """
    compiled = [re.compile(p) for p in patterns]
    deadline = None if timeout is None else time.monotonic() + timeout
    while True:
      for idx, pattern in enumerate(compiled):
        m = pattern.search(self._buf)
        if m:
          text, self._buf = self._buf[: m.end()], self._buf[m.end() :]
          return idx, m, text
      remaining = None if deadline is None else deadline - time.monotonic()
      if remaining is not None and remaining <= 0:
        break
      if not self._fill(remaining):
        break
    text, self._buf = self._buf, b''
    return -1, None, text


class TelnetScpiClient:
  """This is an internal helper class for Telnet+SCPI command-based
  instruments. It should only be used by those implemention control libraries
  and not by any user code directly.
  """

  def __init__(self, tx_cmd_separator='\n', rx_cmd_separator='\n', prompt=''):
    self._tn = None
    self.tx_cmd_separator = tx_cmd_separator
    self.rx_cmd_separator = rx_cmd_separator
    self.prompt = prompt
    self.host = None
    self.port = None

  def open(self, host, port=23):
    if self._tn:
      self._tn.close()
    self.host = host
    self.port = port
    self._tn = _Telnet()
    self._tn.open(host, port, 10)

  @property
  def is_open(self):
    return bool(self._tn)

  def close(self):
    if self._tn:
      self._tn.close()
      self._tn = None

  def cmd(self, cmd_str, wait_ret=True):
    if not isinstance(cmd_str, str):
      raise TypeError('Invalid command string', cmd_str)
    if not self.is_open:
      raise attenuator.Error('Telnet connection not open for commands')

    self._tn.read_until(self.prompt.encode('ascii'), 2)
    self._tn.write((cmd_str + self.tx_cmd_separator).encode('ascii'))
    if wait_ret is False:
      return None

    match_idx, _, ret_text = self._tn.expect(
        [(r'\S+' + self.rx_cmd_separator).encode('ascii')], 1
    )

    if match_idx == -1:
      raise attenuator.Error('Telnet command failed to return valid data')

    return ret_text.decode().strip(
        self.tx_cmd_separator + self.rx_cmd_separator + self.prompt
    )
