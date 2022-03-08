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

    Test that when the _build_connection fails with exception, it should
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

    Test that when the stage after_starting_server fails with exception,
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
    """Test the internal dependencies when sending a RPC.

    When sending a RPC, the function send_rpc_request uses the output of
    the function _gen_rpc_request, and the function _parse_rpc_response uses the
    output of send_rpc_request. This test case checks above dependencies.
    """
    client = FakeClient()
    client.host_port = 12345
    client.start_server()

    expected_response = ('{"id": 0, "result": 123, "error": null, '
                         '"callback": null}')
    expected_request = ('{"id": 10, "method": "some_rpc", "params": [1, 2],'
                        '"kwargs": {"test_key": 3}')
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
    """Test RPC precheck fails.

    Test that when an RPC precheck fails with exception, the RPC function
    should throw that exception and skip sending RPC.
    """
    client = FakeClient()
    client.host_port = 12345
    client.start_server()
    mock_precheck.side_effect = Exception('server_died')

    with self.assertRaisesRegex(Exception, 'server_died'):
      client.some_rpc(1, 2)

    mock_gen_request.assert_not_called()
    mock_send_request.assert_not_called()
    mock_parse_response.assert_not_called()

  def test_gen_request(self):
    """Test generating a RPC request

    Test that _gen_rpc_request returns a string represents a JSON dict
    with all required fields.
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
    """Test parsing an empty RPC response."""
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
    """Test parsing a RPC response that misses some required fields."""
    client = FakeClient()

    mock_resp_without_id = '{"result": 123, "error": null, "callback": null}'
    with self.assertRaisesRegex(
        jsonrpc_client_base.ProtocolError,
        jsonrpc_client_base.ProtocolError.RESPONSE_MISS_FIELD % 'id'):
      client._parse_rpc_response(10, 'some_rpc', mock_resp_without_id)

    mock_resp_without_result = '{"id": 10, "error": null, "callback": null}'
    with self.assertRaisesRegex(
        jsonrpc_client_base.ProtocolError,
        jsonrpc_client_base.ProtocolError.RESPONSE_MISS_FIELD % 'result'):
      client._parse_rpc_response(10, 'some_rpc', mock_resp_without_result)

    mock_resp_without_error = '{"id": 10, "result": 123, "callback": null}'
    with self.assertRaisesRegex(
        jsonrpc_client_base.ProtocolError,
        jsonrpc_client_base.ProtocolError.RESPONSE_MISS_FIELD % 'error'):
      client._parse_rpc_response(10, 'some_rpc', mock_resp_without_error)

    mock_resp_without_callback = '{"id": 10, "result": 123, "error": null}'
    with self.assertRaisesRegex(
        jsonrpc_client_base.ProtocolError,
        jsonrpc_client_base.ProtocolError.RESPONSE_MISS_FIELD % 'callback'):
      client._parse_rpc_response(10, 'some_rpc', mock_resp_without_callback)

  def test_parse_response_error(self):
    """Test parsing a RPC response with a non-empty error field."""
    client = FakeClient()

    mock_resp_with_error = ('{"id": 10, "result": 123, "error": "some_error", '
                            '"callback": null}')
    with self.assertRaisesRegex(jsonrpc_client_base.ApiError, 'some_error'):
      client._parse_rpc_response(10, 'some_rpc', mock_resp_with_error)

  def test_parse_response_callback(self):
    """Test parsing response function handles the callback field well."""
    client = FakeClient()

    # Call handle_callback function if the "callback" field is not null
    mock_resp_with_callback = ('{"id": 10, "result": 123, "error": null, '
                               '"callback": "1-0"}')
    with mock.patch.object(client, 'handle_callback') as mock_handle_callback:
      expected_callback = mock.Mock()
      mock_handle_callback.return_value = expected_callback

      rpc_result = client._parse_rpc_response(10, 'some_rpc',
                                              mock_resp_with_callback)
      mock_handle_callback.assert_called_with('1-0', 123, 'some_rpc')
      # Ensure the RPC function returns what handle_callback returned
      self.assertIs(expected_callback, rpc_result)

    # Do not call handle_callback function if the "callback" field is null
    mock_resp = '{"id": 10, "result": 123, "error": null, "callback": null}'
    with mock.patch.object(client, 'handle_callback') as mock_handle_callback:
      client._parse_rpc_response(10, 'some_rpc', mock_resp)
      mock_handle_callback.assert_not_called()

  def test_parse_response_id_mismatch(self):
    """Test parsing a RPC response with wrong id."""
    client = FakeClient()

    right_id = 5
    wrong_id = 20
    resp = f'{{"id": {right_id}, "result": 1, "error": null, "callback": null}}'

    with self.assertRaisesRegex(
        jsonrpc_client_base.ProtocolError,
        jsonrpc_client_base.ProtocolError.MISMATCHED_API_ID):
      client._parse_rpc_response(wrong_id, 'some_rpc', resp)

  @mock.patch.object(FakeClient, 'send_rpc_request')
  def test_rpc_verbose_logging_with_long_string(self, mock_send_request):
    """Test RPC response isn't truncated when verbose logging is on."""
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
    """Test RPC response isn't truncated with small length."""
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
    """Test RPC response isn't truncated with length equal to the threshold."""
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
    """Test RPC response is truncated with length larger than the threshold."""
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
    """Test that with each RPC call the counter is incremented by 1."""
    client = FakeClient()
    client.host_port = 12345
    client.start_server()
    resp = '{"id": %d, "result": 123, "error": null, "callback": null}'
    mock_send_request.side_effect = (resp % (i,) for i in range(10))

    for _ in range(0, 10):
      client.some_rpc()

    self.assertEqual(next(client._counter), 10)

  @mock.patch.object(FakeClient, 'send_rpc_request')
  def test_build_connection_reset_counter(self, mock_send_request):
    """Test that _build_connection resets the the counter to zero."""
    client = FakeClient()
    client.host_port = 12345
    client.start_server()
    resp = '{"id": %d, "result": 123, "error": null, "callback": null}'
    mock_send_request.side_effect = (resp % (i,) for i in range(10))

    for _ in range(0, 10):
      client.some_rpc()

    self.assertEqual(next(client._counter), 10)
    client._build_connection()
    self.assertEqual(next(client._counter), 0)


if __name__ == '__main__':
  unittest.main()
