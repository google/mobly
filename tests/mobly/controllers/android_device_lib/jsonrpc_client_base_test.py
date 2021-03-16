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

from builtins import str

import json
import mock
import socket
import unittest

from mobly.controllers.android_device_lib import jsonrpc_client_base
from tests.lib import jsonrpc_client_test_base


class FakeRpcClient(jsonrpc_client_base.JsonRpcClientBase):

  def __init__(self):
    super().__init__(app_name='FakeRpcClient', ad=mock.Mock())


class JsonRpcClientBaseTest(jsonrpc_client_test_base.JsonRpcClientTestBase):
  """Unit tests for mobly.controllers.android_device_lib.jsonrpc_client_base.
  """

  @mock.patch('socket.create_connection')
  def test_open_timeout_io_error(self, mock_create_connection):
    """Test socket timeout with io error

    Test that if the net socket gives an io error, then the client
    will eventually exit with an IOError.
    """
    mock_create_connection.side_effect = IOError()
    with self.assertRaises(IOError):
      client = FakeRpcClient()
      client.connect()

  @mock.patch('socket.create_connection')
  def test_connect_timeout(self, mock_create_connection):
    """Test socket timeout

    Test that a timeout exception will be raised if the socket gives a
    timeout.
    """
    mock_create_connection.side_effect = socket.timeout
    with self.assertRaises(socket.timeout):
      client = FakeRpcClient()
      client.connect()

  @mock.patch('socket.create_connection')
  def test_handshake_error(self, mock_create_connection):
    """Test error in jsonrpc handshake

    Test that if there is an error in the jsonrpc handshake then a protocol
    error will be raised.
    """
    self.setup_mock_socket_file(mock_create_connection, resp=None)
    client = FakeRpcClient()
    with self.assertRaisesRegex(
        jsonrpc_client_base.ProtocolError,
        jsonrpc_client_base.ProtocolError.NO_RESPONSE_FROM_HANDSHAKE):
      client.connect()

  def test_disconnect(self):
    client = FakeRpcClient()
    mock_conn = mock.MagicMock()
    client.clear_host_port = mock.MagicMock()
    client._conn = mock_conn
    client.disconnect()
    self.assertIsNone(client._conn)
    mock_conn.close.assert_called_once_with()
    client.clear_host_port.assert_called_once_with()

  def test_disconnect_raises(self):
    client = FakeRpcClient()
    mock_conn = mock.MagicMock()
    client.clear_host_port = mock.MagicMock()
    client._conn = mock_conn
    # Explicitly making the second side_effect noop to avoid uncaught exception
    # when `__del__` is called after the test is done, which triggers
    # `disconnect`.
    mock_conn.close.side_effect = [Exception('ha'), None]
    with self.assertRaisesRegex(Exception, 'ha'):
      client.disconnect()
    client.clear_host_port.assert_called_once_with()

  def test_clear_host_port_positive(self):
    client = FakeRpcClient()
    client.host_port = 1
    client.clear_host_port()
    client._ad.adb.forward.assert_called_once_with(['--remove', 'tcp:1'])
    self.assertIsNone(client.host_port)

  def test_clear_host_port_negative(self):
    client = FakeRpcClient()
    client.host_port = None
    client.clear_host_port()
    client._ad.adb.forward.assert_not_called()

  @mock.patch('socket.create_connection')
  def test_connect_handshake(self, mock_create_connection):
    """Test client handshake

    Test that at the end of a handshake with no errors the client object
    has the correct parameters.
    """
    self.setup_mock_socket_file(mock_create_connection)
    client = FakeRpcClient()
    client.connect()
    self.assertEqual(client.uid, 1)

  @mock.patch('socket.create_connection')
  def test_connect_handshake_unknown_status(self, mock_create_connection):
    """Test handshake with unknown status response

    Test that when the handshake is given an unknown status then the client
    will not be given a uid.
    """
    self.setup_mock_socket_file(mock_create_connection,
                                resp=self.MOCK_RESP_UNKNOWN_STATUS)
    client = FakeRpcClient()
    client.connect()
    self.assertEqual(client.uid, jsonrpc_client_base.UNKNOWN_UID)

  @mock.patch('socket.create_connection')
  def test_rpc_error_response(self, mock_create_connection):
    """Test rpc that is given an error response

    Test that when an rpc receives a response with an error will raised
    an api error.
    """
    fake_file = self.setup_mock_socket_file(mock_create_connection)

    client = FakeRpcClient()
    client.connect()

    fake_file.resp = self.MOCK_RESP_WITH_ERROR

    with self.assertRaisesRegex(jsonrpc_client_base.ApiError, '1'):
      client.some_rpc(1, 2, 3)

  @mock.patch('socket.create_connection')
  def test_rpc_callback_response(self, mock_create_connection):
    """Test rpc that is given a callback response.

    Test that when an rpc receives a callback response, a callback object is
    created correctly.
    """
    fake_file = self.setup_mock_socket_file(mock_create_connection)

    client = FakeRpcClient()
    client.connect()

    fake_file.resp = self.MOCK_RESP_WITH_CALLBACK
    client._event_client = mock.Mock()

    callback = client.some_rpc(1, 2, 3)
    self.assertEqual(callback.ret_value, 123)
    self.assertEqual(callback._id, '1-0')

  @mock.patch('socket.create_connection')
  def test_rpc_id_mismatch(self, mock_create_connection):
    """Test rpc that returns a different id than expected

    Test that if an rpc returns with an id that is different than what
    is expected will give a protocl error.
    """
    fake_file = self.setup_mock_socket_file(mock_create_connection)

    client = FakeRpcClient()
    client.connect()

    fake_file.resp = (self.MOCK_RESP_TEMPLATE % 52).encode('utf8')

    with self.assertRaisesRegex(
        jsonrpc_client_base.ProtocolError,
        jsonrpc_client_base.ProtocolError.MISMATCHED_API_ID):
      client.some_rpc(1, 2, 3)

  @mock.patch('socket.create_connection')
  def test_rpc_no_response(self, mock_create_connection):
    """Test rpc that does not get a response

    Test that when an rpc does not get a response it throws a protocol
    error.
    """
    fake_file = self.setup_mock_socket_file(mock_create_connection)

    client = FakeRpcClient()
    client.connect()

    fake_file.resp = None

    with self.assertRaisesRegex(
        jsonrpc_client_base.ProtocolError,
        jsonrpc_client_base.ProtocolError.NO_RESPONSE_FROM_SERVER):
      client.some_rpc(1, 2, 3)

  @mock.patch('socket.create_connection')
  def test_rpc_send_to_socket(self, mock_create_connection):
    """Test rpc sending and recieving

    Tests that when an rpc is sent and received the corrent data
    is used.
    """
    fake_file = self.setup_mock_socket_file(mock_create_connection)

    client = FakeRpcClient()
    client.connect()

    result = client.some_rpc(1, 2, 3)
    self.assertEqual(result, 123)

    expected = {'id': 0, 'method': 'some_rpc', 'params': [1, 2, 3]}
    actual = json.loads(fake_file.last_write.decode('utf-8'))

    self.assertEqual(expected, actual)

  @mock.patch('socket.create_connection')
  def test_rpc_send_to_socket_without_callback(self, mock_create_connection):
    """Test rpc sending and recieving with Rpc protocol before callback was
    added to the resp message.

    Logic is the same as test_rpc_send_to_socket.
    """
    fake_file = self.setup_mock_socket_file(
        mock_create_connection, resp=self.MOCK_RESP_WITHOUT_CALLBACK)

    client = FakeRpcClient()
    client.connect()

    result = client.some_rpc(1, 2, 3)
    self.assertEqual(result, 123)

    expected = {'id': 0, 'method': 'some_rpc', 'params': [1, 2, 3]}
    actual = json.loads(fake_file.last_write.decode('utf-8'))

    self.assertEqual(expected, actual)

  @mock.patch('socket.create_connection')
  def test_rpc_call_increment_counter(self, mock_create_connection):
    """Test rpc counter

    Test that with each rpc call the counter is incremented by 1.
    """
    fake_file = self.setup_mock_socket_file(mock_create_connection)

    client = FakeRpcClient()
    client.connect()

    for i in range(0, 10):
      fake_file.resp = (self.MOCK_RESP_TEMPLATE % i).encode('utf-8')
      client.some_rpc()

    self.assertEqual(next(client._counter), 10)

  @mock.patch('socket.create_connection')
  def test_rpc_verbose_logging_with_long_string(self, mock_create_connection):
    """Test rpc response fully write into DEBUG level log."""
    fake_file = self.setup_mock_socket_file(mock_create_connection)
    testing_rpc_response = self.generate_rpc_response(4000)
    fake_file.resp = testing_rpc_response

    client = FakeRpcClient()
    client.connect()

    response = client._client_receive()
    self.assertEqual(response, testing_rpc_response)

    client.log.debug.assert_called_with('Snippet received: %s',
                                        testing_rpc_response)

  @mock.patch('socket.create_connection')
  def test_rpc_truncated_logging_short_response(self, mock_create_connection):
    """Test rpc response will full logged when length is short."""
    fake_file = self.setup_mock_socket_file(mock_create_connection)
    testing_rpc_response = self.generate_rpc_response(
        int(jsonrpc_client_base._MAX_RPC_RESP_LOGGING_LENGTH / 2))
    fake_file.resp = testing_rpc_response

    client = FakeRpcClient()
    client.connect()

    client.set_snippet_client_verbose_logging(False)
    response = client._client_receive()

    self.assertEqual(response, testing_rpc_response)
    client.log.debug.assert_called_with('Snippet received: %s',
                                        testing_rpc_response)

  @mock.patch('socket.create_connection')
  def test_rpc_truncated_logging_fit_size_response(self,
                                                   mock_create_connection):
    """Test rpc response will full logged when length is equal to threshold.
    """
    fake_file = self.setup_mock_socket_file(mock_create_connection)
    testing_rpc_response = self.generate_rpc_response(
        jsonrpc_client_base._MAX_RPC_RESP_LOGGING_LENGTH)
    fake_file.resp = testing_rpc_response

    client = FakeRpcClient()
    client.connect()

    client.set_snippet_client_verbose_logging(False)
    response = client._client_receive()

    self.assertEqual(response, testing_rpc_response)
    client.log.debug.assert_called_with('Snippet received: %s',
                                        testing_rpc_response)

  @mock.patch('socket.create_connection')
  def test_rpc_truncated_logging_long_response(self, mock_create_connection):
    """Test rpc response truncated with given length in DEBUG level log."""
    fake_file = self.setup_mock_socket_file(mock_create_connection)
    resp_len = jsonrpc_client_base._MAX_RPC_RESP_LOGGING_LENGTH * 40
    testing_rpc_response = self.generate_rpc_response(resp_len)
    fake_file.resp = testing_rpc_response

    client = FakeRpcClient()
    client.connect()

    client.set_snippet_client_verbose_logging(False)
    response = client._client_receive()

    self.assertEqual(response, testing_rpc_response)
    # DEBUG level log should truncated by given length.
    client.log.debug.assert_called_with(
        'Snippet received: %s... %d chars are truncated',
        testing_rpc_response[:jsonrpc_client_base._MAX_RPC_RESP_LOGGING_LENGTH],
        resp_len - jsonrpc_client_base._MAX_RPC_RESP_LOGGING_LENGTH)


if __name__ == '__main__':
  unittest.main()
