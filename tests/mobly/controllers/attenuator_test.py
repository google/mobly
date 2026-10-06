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
"""Tests for the attenuator controller against a fake Mini-Circuits server."""

import socket
import socketserver
import threading
import unittest

from mobly.controllers import attenuator
from mobly.controllers.attenuator_lib import telnet_scpi_client

_IAC, _DO, _WILL, _SB, _SE = 255, 253, 251, 250, 240


class _FakeMiniCircuitsHandler(socketserver.BaseRequestHandler):
  """Speaks just enough of the RCDAT telnet/SCPI protocol."""

  def handle(self):
    # Telnet option negotiation that a real device may emit; the client must
    # strip it from the text stream.
    self.request.sendall(
        bytes([_IAC, _WILL, 1, _IAC, _DO, 3, _IAC, _SB, 24, _IAC, _SE])
    )
    buf = b''
    while True:
      data = self.request.recv(1024)
      if not data:
        return
      buf += data
      while b'\n' in buf:
        line, buf = buf.split(b'\n', 1)
        cmd = line.decode().strip('\r')
        self.server.commands.append(cmd)
        if cmd == 'MN?':
          resp = 'MN=RCDAT-6000-90'
        elif cmd.startswith('CHAN:') and ':SETATT:' in cmd:
          _, chan, _, value = cmd.split(':')
          self.server.attens[int(chan)] = float(value)
          resp = '1'
        elif cmd.startswith('CHAN:') and cmd.endswith(':ATT?'):
          chan = int(cmd.split(':')[1])
          resp = '%.2f' % self.server.attens.get(chan, 0.0)
        else:
          resp = '0'
        self.request.sendall((resp + '\r\n').encode())


class _FakeServer(socketserver.ThreadingTCPServer):
  allow_reuse_address = True
  daemon_threads = True

  def __init__(self):
    super().__init__(('127.0.0.1', 0), _FakeMiniCircuitsHandler)
    self.commands = []
    self.attens = {}


class AttenuatorTest(unittest.TestCase):

  def setUp(self):
    self.server = _FakeServer()
    self.thread = threading.Thread(target=self.server.serve_forever)
    self.thread.daemon = True
    self.thread.start()
    self.addCleanup(self.server.server_close)
    self.addCleanup(self.server.shutdown)
    self.port = self.server.server_address[1]

  def _create(self):
    return attenuator.create(
        [
            {
                'address': '127.0.0.1',
                'port': self.port,
                'model': 'minicircuits',
                'paths': ['AP1-2G', 'AP1-5G'],
            }
        ]
    )

  def test_create_set_get_destroy(self):
    paths = self._create()
    self.assertEqual([p.name for p in paths], ['AP1-2G', 'AP1-5G'])
    self.assertEqual(paths[0].attenuation_device.max_atten, 90.0)
    self.assertEqual(paths[0].get_atten(), 0.0)

    paths[1].set_atten(42.5)
    self.assertEqual(paths[1].get_atten(), 42.5)
    self.assertEqual(paths[0].get_atten(), 0.0)
    self.assertEqual(
        self.server.commands[:3],
        ['MN?', 'CHAN:1:ATT?', 'CHAN:2:SETATT:42.5'],
    )

    attenuator.destroy(paths)
    self.assertFalse(paths[0].attenuation_device.is_open)
    with self.assertRaisesRegex(attenuator.Error, 'is not open'):
      paths[0].get_atten()

  def test_set_atten_out_of_range(self):
    paths = self._create()
    self.addCleanup(attenuator.destroy, paths)
    with self.assertRaises(ValueError):
      paths[0].set_atten(100)
    with self.assertRaises(IndexError):
      paths[0].attenuation_device.set_atten(2, 1)

  def test_missing_config_key(self):
    with self.assertRaisesRegex(
        attenuator.Error, "Required key 'paths' missing from config"
    ):
      attenuator.create([{'address': 'x', 'port': 23, 'model': 'minicircuits'}])

  def test_cmd_times_out_without_response(self):
    # A server that accepts but never answers.
    silent = socket.socket()
    silent.bind(('127.0.0.1', 0))
    silent.listen(1)
    self.addCleanup(silent.close)
    client = telnet_scpi_client.TelnetScpiClient()
    client.open('127.0.0.1', silent.getsockname()[1])
    self.addCleanup(client.close)
    with self.assertRaisesRegex(
        attenuator.Error, 'failed to return valid data'
    ):
      client.cmd('MN?')

  def test_cmd_requires_open_connection(self):
    client = telnet_scpi_client.TelnetScpiClient()
    with self.assertRaisesRegex(attenuator.Error, 'not open'):
      client.cmd('MN?')
    with self.assertRaises(TypeError):
      client.cmd(b'MN?')


if __name__ == '__main__':
  unittest.main()
