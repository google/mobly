# Copyright 2022 Google Inc.
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

"""Unit tests for mobly.snippet.client_base."""

import json
import logging
import unittest
from unittest import mock

from mobly.controllers.android_device_lib import jsonrpc_client_base
from mobly.snippet import client_base
from tests.lib.snippet import utils as snippet_utils

MOCK_RESP = ('{"id": 10, "result": 123, "error": null, "status": 1,'
             '"callback": null}')
MOCK_RESP_TEMPLATE = (
    '{"id": %d, "result": %d, "error": null, "status": 1, "uid": 1,'
    '"callback": null}')
MOCK_RESP_WITHOUT_ID = '{"result": 123, "error": null, "callback": null}'
MOCK_RESP_WITHOUT_RESULT = '{"id": 10, "error": null, "callback": null}'
MOCK_RESP_WITHOUT_ERROR = '{"id": 10, "result": 123, "callback": null}'
MOCK_RESP_WITHOUT_CALLBACK = '{"id": 10, "result": 123, "error": null}'
MOCK_RESP_WITH_ERROR = ('{"id": 10, "result": 123, "error": "some_error",'
                        '"status": 1, "uid": 1, "callback": null}')
MOCK_RESP_WITH_CALLBACK = ('{"id": 10, "result": 123, "error": null,'
                           '"status": 1, "callback": "1-0"}')


class FakeClient(client_base.ClientBase):

  def __init__(self):
    mock_device = mock.Mock()
    mock_device.log = logging
    super().__init__(package='FakeClient', device=mock_device)

  # Override abstract methods to enable initialization
  def before_starting_server(self):
    pass

  def do_start_server(self):
    pass

  def build_connection(self):
    pass

  def after_starting_server(self):
    pass

  def restore_server_connection(self, port=None):
    pass

  def check_server_proc_running(self):
    pass

  def send_rpc_request(self, request):
    pass

  def handle_callback(self, callback_id, ret_value, rpc_func_name):
    pass

  def do_stop_server(self):
    pass

  def close_connection(self):
    pass


class ClientBaseTest(unittest.TestCase):
  """Unit tests for mobly.snippet.client_base.ClientBase."""

  @mock.patch.object(FakeClient, 'before_starting_server')
  @mock.patch.object(FakeClient, 'do_start_server')
  @mock.patch.object(FakeClient, '_build_connection')
  @mock.patch.object(FakeClient, 'after_starting_server')
  def test_start_server_stage_order(self, mock_after_func, mock_build_conn_func,
                                    mock_do_start_func, mock_before_func):
    """Test that starting server runs its stages in expected order."""
    order_manager = mock.Mock()
    order_manager.attach_mock(mock_before_func, 'mock_before_func')
    order_manager.attach_mock(mock_do_start_func, 'mock_do_start_func')
    order_manager.attach_mock(mock_build_conn_func, 'mock_build_conn_func')
    order_manager.attach_mock(mock_after_func, 'mock_after_func')

    client = FakeClient()
    client.host_port = 12345
    client.start_server()

    expected_call_order = [
        mock.call.mock_before_func(),
        mock.call.mock_do_start_func(),
        mock.call.mock_build_conn_func(),
        mock.call.mock_after_func(),
    ]
    self.assertListEqual(order_manager.mock_calls, expected_call_order)

  @mock.patch.object(FakeClient, 'stop_server')
  @mock.patch.object(FakeClient, 'before_starting_server')
  def test_start_server_before_starting_server_fail(self, mock_before_func,
                                                    mock_stop_server):
    """Test starting server's stage before_starting_server fails.

    Test that when the before_starting_server stage fails with exception, it
    should not stop server before exiting.
    """
    client = FakeClient()
    mock_before_func.side_effect = Exception('ha')

    with self.assertRaisesRegex(Exception, 'ha'):
      client.start_server()
    mock_stop_server.assert_not_called()

  @mock.patch.object(FakeClient, 'stop_server')
  @mock.patch.object(FakeClient, 'do_start_server')
  def test_start_server_do_start_server_fail(self, mock_do_start_func,
                                             mock_stop_server):
    """Test starting server's stage do_start_server fails.

    Test that when the do_start_server stage fails with exception, it should
    stop server before exiting.
    """
    client = FakeClient()
    mock_do_start_func.side_effect = Exception('ha')

    with self.assertRaisesRegex(Exception, 'ha'):
      client.start_server()
    mock_stop_server.assert_called()

  @mock.patch.object(FakeClient, 'stop_server')
  @mock.patch.object(FakeClient, '_build_connection')
  def test_start_server_build_connection_fail(self, mock_build_conn_func,
                                              mock_stop_server):
    """Test starting server's stage _build_connection fails.

    Test that when the building connection fails with exception, it should
    stop server before exiting.
    """
    client = FakeClient()
    mock_build_conn_func.side_effect = Exception('ha')

    with self.assertRaisesRegex(Exception, 'ha'):
      client.start_server()
    mock_stop_server.assert_called()

  @mock.patch.object(FakeClient, 'stop_server')
  @mock.patch.object(FakeClient, 'after_starting_server')
  def test_start_server_after_starting_server_fail(self, mock_after_func,
                                                   mock_stop_server):
    """Test starting server's stage after_starting_server fails.

    Test that when the stage after building connection fails with exception,
    it should stop server before exiting.
    """
    client = FakeClient()
    mock_after_func.side_effect = Exception('ha')

    with self.assertRaisesRegex(Exception, 'ha'):
      client.start_server()
    mock_stop_server.assert_called()

  @mock.patch.object(FakeClient, 'check_server_proc_running')
  @mock.patch.object(FakeClient, '_gen_rpc_request')
  @mock.patch.object(FakeClient, 'send_rpc_request')
  @mock.patch.object(FakeClient, '_parse_rpc_response')
  def test_rpc_stage_dependencies(self, mock_parse_response, mock_send_request,
                                  mock_gen_request, mock_precheck):
    """Test rpc stage dependencies.

    In the rpc stage, the sending rpc function utils the output of generating
    rpc request, and the output of the sending function if used by the parse
    rpc response function. This test case checks above dependencies.
    """
    client = FakeClient()
    client.host_port = 12345
    client.start_server()

    expected_response = MOCK_RESP_TEMPLATE % (0, 123)
    expected_request = ("{'id': 10, 'method': 'some_rpc', 'params': [1, 2],"
                        "'kwargs': {'test_key': 3}")
    expected_result = 123

    mock_gen_request.return_value = expected_request
    mock_send_request.return_value = expected_response
    mock_parse_response.return_value = expected_result
    rpc_result = client.some_rpc(1, 2, test_key=3)

    mock_precheck.assert_called()
    mock_gen_request.assert_called_with(0, 'some_rpc', 1, 2, test_key=3)
    mock_send_request.assert_called_with(expected_request)
    mock_parse_response.assert_called_with(0, 'some_rpc', expected_response)
    self.assertEqual(rpc_result, expected_result)

  @mock.patch.object(FakeClient, 'check_server_proc_running')
  @mock.patch.object(FakeClient, '_gen_rpc_request')
  @mock.patch.object(FakeClient, 'send_rpc_request')
  @mock.patch.object(FakeClient, '_parse_rpc_response')
  def test_rpc_precheck_fail(self, mock_parse_response, mock_send_request,
                             mock_gen_request, mock_precheck):
    """Test rpc precheck fails.

    Test that when an rpc precheck fails with exception, the rpc function
    should throws that error and skip sending rpc.
    """
    client = FakeClient()
    client.host_port = 12345
    client.start_server()
    mock_precheck.side_effect = Exception('server_died')

    with self.assertRaises(Exception):
      client.some_rpc(1, 2)

    mock_gen_request.assert_not_called()
    mock_send_request.assert_not_called()
    mock_parse_response.assert_not_called()

  def test_gen_request(self):
    """Test generate rcp request

    Test that _gen_rpc_request returns a string represents a JSON dict
    with all request fields.
    """
    client = FakeClient()
    request_str = client._gen_rpc_request(0, 'test_rpc', 1, 2, test_key=3)
    self.assertIs(type(request_str), str)
    request = json.loads(request_str)
    expected_result = {
        'id': 0,
        'method': 'test_rpc',
        'params': [1, 2],
        'kwargs': {
            'test_key': 3,
        },
    }
    self.assertDictEqual(request, expected_result)

  def test_gen_request_without_kwargs(self):
    """Test no keyword arguments.

    Test that _gen_rpc_request ignores the kwargs field when no
    keyword arguments.
    """
    client = FakeClient()
    request_str = client._gen_rpc_request(0, 'test_rpc', 1, 2)
    self.assertIs(type(request_str), str)
    request = json.loads(request_str)
    expected_result = {'id': 0, 'method': 'test_rpc', 'params': [1, 2]}
    self.assertDictEqual(request, expected_result)

  def test_parse_rpc_no_response(self):
    """Test rpc that does not get a response.

    Test that when an rpc does not get a response it throws a protocol
    error.
    """
    client = FakeClient()

    with self.assertRaisesRegex(
        jsonrpc_client_base.ProtocolError,
        jsonrpc_client_base.ProtocolError.NO_RESPONSE_FROM_SERVER):
      client._parse_rpc_response(0, 'some_rpc', '')

    with self.assertRaisesRegex(
        jsonrpc_client_base.ProtocolError,
        jsonrpc_client_base.ProtocolError.NO_RESPONSE_FROM_SERVER):
      client._parse_rpc_response(0, 'some_rpc', None)

  def test_parse_response_miss_fields(self):
    """Test rpc response that miss some required fields.

    Test that when an rpc miss some required fields it throws a protocol
    error.
    """
    client = FakeClient()

    with self.assertRaisesRegex(
        jsonrpc_client_base.ProtocolError,
        jsonrpc_client_base.ProtocolError.RESPONSE_MISS_FIELD % 'id'):
      client._parse_rpc_response(10, 'some_rpc', MOCK_RESP_WITHOUT_ID)

    with self.assertRaisesRegex(
        jsonrpc_client_base.ProtocolError,
        jsonrpc_client_base.ProtocolError.RESPONSE_MISS_FIELD % 'result'):
      client._parse_rpc_response(10, 'some_rpc', MOCK_RESP_WITHOUT_RESULT)

    with self.assertRaisesRegex(
        jsonrpc_client_base.ProtocolError,
        jsonrpc_client_base.ProtocolError.RESPONSE_MISS_FIELD % 'error'):
      client._parse_rpc_response(10, 'some_rpc', MOCK_RESP_WITHOUT_ERROR)

    with self.assertRaisesRegex(
        jsonrpc_client_base.ProtocolError,
        jsonrpc_client_base.ProtocolError.RESPONSE_MISS_FIELD % 'callback'):
      client._parse_rpc_response(10, 'some_rpc', MOCK_RESP_WITHOUT_CALLBACK)

  def test_parse_response_error(self):
    """Test rpc that is given an error response.

    Test that when an rpc receives a response with an error will raised
    an api error.
    """
    client = FakeClient()

    with self.assertRaisesRegex(jsonrpc_client_base.ApiError, 'some_error'):
      client._parse_rpc_response(10, 'some_rpc', MOCK_RESP_WITH_ERROR)

  def test_parse_response_callback(self):
    """Test rpc that is given a callback response.

    Test that when an rpc receives a callback response, the function to
    handle callback will be called.
    """
    client = FakeClient()

    # call handle_callback function if "callback" field exists
    with mock.patch.object(client, 'handle_callback') as mock_handle_callback:
      expected_callback = mock.Mock()
      mock_handle_callback.return_value = expected_callback

      rpc_result = client._parse_rpc_response(10, 'some_rpc',
                                              MOCK_RESP_WITH_CALLBACK)
      mock_handle_callback.assert_called_with('1-0', 123, 'some_rpc')
      # ensure the rpc function return what handle_callback returns
      self.assertIs(expected_callback, rpc_result)

    # Do not call handle_callback function if no "callback" field
    with mock.patch.object(client, 'handle_callback') as mock_handle_callback:
      client._parse_rpc_response(10, 'some_rpc', MOCK_RESP)

      mock_handle_callback.assert_not_called()

  def test_parse_response_id_mismatch(self):
    """Test rpc that returns a different id than expected.

    Test that if an rpc returns with an id that is different than what
    is expected will give a protocl error.
    """
    client = FakeClient()

    right_id = 5
    wrong_id = 20
    resp = MOCK_RESP_TEMPLATE % (right_id, 123)

    with self.assertRaisesRegex(
        jsonrpc_client_base.ProtocolError,
        jsonrpc_client_base.ProtocolError.MISMATCHED_API_ID):
      client._parse_rpc_response(wrong_id, 'some_rpc', resp)

  @mock.patch.object(FakeClient, 'send_rpc_request')
  def test_rpc_verbose_logging_with_long_string(self, mock_send_request):
    """Test rpc response isn't truncated when verbose logging is on."""
    client = FakeClient()
    mock_log = mock.Mock()
    client.log = mock_log
    client.set_snippet_client_verbose_logging(True)
    client.start_server()

    resp = snippet_utils.generate_fix_length_rpc_response(
        client_base._MAX_RPC_RESP_LOGGING_LENGTH * 2)
    mock_send_request.return_value = resp
    client.some_rpc(1, 2)
    mock_log.debug.assert_called_with('Snippet received: %s', resp)

  @mock.patch.object(FakeClient, 'send_rpc_request')
  def test_rpc_truncated_logging_short_response(self, mock_send_request):
    """Test rpc response isn't truncated with small length."""
    client = FakeClient()
    mock_log = mock.Mock()
    client.log = mock_log
    client.set_snippet_client_verbose_logging(False)
    client.start_server()

    resp = snippet_utils.generate_fix_length_rpc_response(
        int(client_base._MAX_RPC_RESP_LOGGING_LENGTH // 2))
    mock_send_request.return_value = resp
    client.some_rpc(1, 2)
    mock_log.debug.assert_called_with('Snippet received: %s', resp)

  @mock.patch.object(FakeClient, 'send_rpc_request')
  def test_rpc_truncated_logging_fit_size_response(self, mock_send_request):
    """Test rpc response isn't truncated with length equal to the threshold."""
    client = FakeClient()
    mock_log = mock.Mock()
    client.log = mock_log
    client.set_snippet_client_verbose_logging(False)
    client.start_server()

    resp = snippet_utils.generate_fix_length_rpc_response(
        client_base._MAX_RPC_RESP_LOGGING_LENGTH)
    mock_send_request.return_value = resp
    client.some_rpc(1, 2)
    mock_log.debug.assert_called_with('Snippet received: %s', resp)

  @mock.patch.object(FakeClient, 'send_rpc_request')
  def test_rpc_truncated_logging_long_response(self, mock_send_request):
    """Test rpc response is truncated with length larger than the threshold."""
    client = FakeClient()
    mock_log = mock.Mock()
    client.log = mock_log
    client.set_snippet_client_verbose_logging(False)
    client.start_server()

    max_len = client_base._MAX_RPC_RESP_LOGGING_LENGTH
    resp = snippet_utils.generate_fix_length_rpc_response(max_len * 40)
    mock_send_request.return_value = resp
    client.some_rpc(1, 2)
    mock_log.debug.assert_called_with(
        'Snippet received: %s... %d chars are truncated',
        resp[:client_base._MAX_RPC_RESP_LOGGING_LENGTH],
        len(resp) - max_len)

  @mock.patch.object(FakeClient, 'send_rpc_request')
  def test_rpc_call_increment_counter(self, mock_send_request):
    """Test rpc counter.

    Test that with each rpc call the counter is incremented by 1.
    """
    client = FakeClient()
    client.host_port = 12345
    client.start_server()
    mock_send_request.side_effect = (
        MOCK_RESP_TEMPLATE % (i, 123) for i in range(10))

    for _ in range(0, 10):
      client.some_rpc()

    self.assertEqual(next(client._counter), 10)

  @mock.patch.object(FakeClient, 'send_rpc_request')
  def test_build_connection_reset_counter(self, mock_send_request):
    """Test rpc counter.

    Test that _build_connection reset the the counter to zero.
    """
    client = FakeClient()
    client.host_port = 12345
    client.start_server()
    mock_send_request.side_effect = (
        MOCK_RESP_TEMPLATE % (i, 123) for i in range(10))

    for _ in range(0, 10):
      client.some_rpc()

    self.assertEqual(next(client._counter), 10)
    client._build_connection()
    self.assertEqual(next(client._counter), 0)


if __name__ == '__main__':
  unittest.main()
