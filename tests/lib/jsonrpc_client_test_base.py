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
import random
import string
from builtins import str

import mock
import unittest


class JsonRpcClientTestBase(unittest.TestCase):
  """Base class for tests of JSONRPC clients.

  Contains infrastructure for mocking responses.
  """

  MOCK_RESP = (
      b'{"id": 0, "result": 123, "error": null, "status": 1, "uid": 1, '
      b'"callback": null}')
  MOCK_RESP_WITHOUT_CALLBACK = (
      b'{"id": 0, "result": 123, "error": null, "status": 1, "uid": 1}')
  MOCK_RESP_TEMPLATE = (
      '{"id": %d, "result": 123, "error": null, "status": 1, "uid": 1, '
      '"callback": null}')
  MOCK_RESP_UNKNOWN_STATUS = (
      b'{"id": 0, "result": 123, "error": null, "status": 0, '
      b'"callback": null}')
  MOCK_RESP_WITH_CALLBACK = (
      b'{"id": 0, "result": 123, "error": null, "status": 1, "uid": 1, '
      b'"callback": "1-0"}')
  MOCK_RESP_WITH_ERROR = b'{"id": 0, "error": 1, "status": 1, "uid": 1}'
  MOCK_RESP_FLEXIABLE_RESULT_LENGTH = (
      '{"id": 0, "result": "%s", "error": null, "status": 0, "callback": null}')

  class MockSocketFile:

    def __init__(self, resp):
      self.resp = resp
      self.last_write = None

    def write(self, msg):
      self.last_write = msg

    def readline(self):
      return self.resp

    def flush(self):
      pass

  def setup_mock_socket_file(self, mock_create_connection, resp=MOCK_RESP):
    """Sets up a fake socket file from the mock connection.

    Args:
      mock_create_connection: The mock method for creating a method.
      resp: (str) response to give. MOCK_RESP by default.

    Returns:
      The mock file that will be injected into the code.
    """
    fake_file = self.MockSocketFile(resp)
    fake_conn = mock.MagicMock()
    fake_conn.makefile.return_value = fake_file
    mock_create_connection.return_value = fake_conn
    return fake_file

  def generate_rpc_response(self, response_length=1024):
    length = response_length - len(self.MOCK_RESP_FLEXIABLE_RESULT_LENGTH) + 2
    chars = string.ascii_letters + string.digits
    random_msg = ''.join(random.choice(chars) for i in range(length))
    mock_response = self.MOCK_RESP_FLEXIABLE_RESULT_LENGTH % random_msg
    return bytes(mock_response, 'utf-8')
