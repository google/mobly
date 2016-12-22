#!/usr/bin/env python3.4
#
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

MOCK_RESP = b'{"id": 0, "result": 123, "error": null, "status": 1, "uid": 1}'
MOCK_RESP_TEMPLATE = '{"id": %d, "result": 123, "error": null, "status": 1, "uid": 1}'
MOCK_RESP_UNKWN_STATUS = b'{"id": 0, "result": 123, "error": null, "status": 0}'
MOCK_RESP_WITH_ERROR = b'{"id": 0, "error": 1, "status": 1, "uid": 1}'


class MockSocketFile(object):
    def __init__(self, resp):
        self.resp = resp
        self.last_write = None

    def write(self, msg):
        self.last_write = msg

    def readline(self):
        return self.resp

    def flush(self):
        pass


class FakeRpcClient(jsonrpc_client_base.JsonRpcClientBase):
    def __init__(self):
      super(FakeRpcClient, self).__init__(adb_proxy=None)


class JsonRpcClientBaseTest(unittest.TestCase):
    """Unit tests for mobly.controllers.android_device_lib.jsonrpc_client_base.
    """

    def setup_mock_socket_file(self, mock_create_connection):
        """Sets up a fake socket file from the mock connection.

        Args:
            mock_create_connection: The mock method for creating a method.

        Returns:
            The mock file that will be injected into the code.
        """
        fake_file = MockSocketFile(MOCK_RESP)
        fake_conn = mock.MagicMock()
        fake_conn.makefile.return_value = fake_file
        mock_create_connection.return_value = fake_conn
        return fake_file

    @mock.patch('socket.create_connection')
    def test_open_timeout_io_error(self, mock_create_connection):
        """Test socket timeout with io error

        Test that if the net socket gives an io error, then the client
        will eventually exit with an IOError.
        """
        mock_create_connection.side_effect = IOError()
        with self.assertRaises(IOError):
            client = FakeRpcClient()
            client.connect(port=80)

    @mock.patch('socket.create_connection')
    def test_connect_timeout(self, mock_create_connection):
        """Test socket timeout

        Test that a timeout exception will be raised if the socket gives a
        timeout.
        """
        mock_create_connection.side_effect = socket.timeout
        with self.assertRaises(socket.timeout):
            client = FakeRpcClient()
            client.connect(port=80)

    @mock.patch('socket.create_connection')
    def test_handshake_error(self, mock_create_connection):
        """Test error in jsonrpc handshake

        Test that if there is an error in the jsonrpc handshake then a protocol
        error will be raised.
        """
        fake_conn = mock.MagicMock()
        fake_conn.makefile.return_value = MockSocketFile(None)
        mock_create_connection.return_value = fake_conn
        with self.assertRaises(jsonrpc_client_base.ProtocolError):
            client = FakeRpcClient()
            client.connect(port=80)

    @mock.patch('socket.create_connection')
    def test_connect_handshake(self, mock_create_connection):
        """Test client handshake

        Test that at the end of a handshake with no errors the client object
        has the correct parameters.
        """
        fake_conn = mock.MagicMock()
        fake_conn.makefile.return_value = MockSocketFile(MOCK_RESP)
        mock_create_connection.return_value = fake_conn

        client = FakeRpcClient()
        client.connect(port=80)

        self.assertEqual(client.uid, 1)

    @mock.patch('socket.create_connection')
    def test_connect_handshake_unknown_status(self, mock_create_connection):
        """Test handshake with unknown status response

        Test that when the handshake is given an unknown status then the client
        will not be given a uid.
        """
        fake_conn = mock.MagicMock()
        fake_conn.makefile.return_value = MockSocketFile(
            MOCK_RESP_UNKWN_STATUS)
        mock_create_connection.return_value = fake_conn

        client = FakeRpcClient()
        client.connect(port=80)

        self.assertEqual(client.uid, jsonrpc_client_base.UNKNOWN_UID)

    @mock.patch('socket.create_connection')
    def test_connect_no_response(self, mock_create_connection):
        """Test handshake no response

        Test that if a handshake recieves no response then it will give a
        protocol error.
        """
        fake_file = self.setup_mock_socket_file(mock_create_connection)

        client = FakeRpcClient()
        client.connect(port=80)

        fake_file.resp = None

        with self.assertRaises(
                jsonrpc_client_base.ProtocolError,
                msg=
                jsonrpc_client_base.ProtocolError.NO_RESPONSE_FROM_HANDSHAKE):
            client.some_rpc(1, 2, 3)

    @mock.patch('socket.create_connection')
    def test_rpc_error_response(self, mock_create_connection):
        """Test rpc that is given an error response

        Test that when an rpc recieves a reponse with an error will raised
        an api error.
        """
        fake_file = self.setup_mock_socket_file(mock_create_connection)

        client = FakeRpcClient()
        client.connect(port=80)

        fake_file.resp = MOCK_RESP_WITH_ERROR

        with self.assertRaises(jsonrpc_client_base.ApiError, msg=1):
            client.some_rpc(1, 2, 3)

    @mock.patch('socket.create_connection')
    def test_rpc_id_mismatch(self, mock_create_connection):
        """Test rpc that returns a different id than expected

        Test that if an rpc returns with an id that is different than what
        is expected will give a protocl error.
        """
        fake_file = self.setup_mock_socket_file(mock_create_connection)

        client = FakeRpcClient()
        client.connect(port=80)

        fake_file.resp = (MOCK_RESP_TEMPLATE % 52).encode('utf8')

        with self.assertRaises(
                jsonrpc_client_base.ProtocolError,
                msg=jsonrpc_client_base.ProtocolError.MISMATCHED_API_ID):
            client.some_rpc(1, 2, 3)

    @mock.patch('socket.create_connection')
    def test_rpc_no_response(self, mock_create_connection):
        """Test rpc that does not get a reponse

        Test that when an rpc does not get a response it throws a protocol
        error.
        """
        fake_file = self.setup_mock_socket_file(mock_create_connection)

        client = FakeRpcClient()
        client.connect(port=80)

        fake_file.resp = None

        with self.assertRaises(
                jsonrpc_client_base.ProtocolError,
                msg=jsonrpc_client_base.ProtocolError.NO_RESPONSE_FROM_SERVER):
            client.some_rpc(1, 2, 3)

    @mock.patch('socket.create_connection')
    def test_rpc_send_to_socket(self, mock_create_connection):
        """Test rpc sending and recieving

        Tests that when an rpc is sent and received the corrent data
        is used.
        """
        fake_file = self.setup_mock_socket_file(mock_create_connection)

        client = FakeRpcClient()
        client.connect(port=80)

        result = client.some_rpc(1, 2, 3)
        self.assertEquals(result, 123)

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
        client.connect(port=80)

        for i in range(0, 10):
            fake_file.resp = (MOCK_RESP_TEMPLATE % i).encode('utf-8')
            client.some_rpc()

        self.assertEquals(next(client._counter), 10)


if __name__ == "__main__":
    unittest.main()
