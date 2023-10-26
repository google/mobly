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

import logging
import random
import string
import unittest
from unittest import mock

from mobly.snippet import client_base
from mobly.snippet import errors


def _generate_fix_length_rpc_response(
    response_length,
    template='{"id": 0, "result": "%s", "error": null, "callback": null}',
):
  """Generates an RPC response string with specified length.

  This function generates a random string and formats the template with the
  generated random string to get the response string. This function formats
  the template with printf style string formatting.

  Args:
    response_length: int, the length of the response string to generate.
    template: str, the template used for generating the response string.

  Returns:
    The generated response string.

  Raises:
    ValueError: if the specified length is too small to generate a response.
  """
  # We need to -2 here because the string formatting will delete the substring
  # '%s' in the template, of which the length is 2.
  result_length = response_length - (len(template) - 2)
  if result_length < 0:
    raise ValueError(
        'The response_length should be no smaller than '
        'template_length + 2. Got response_length '
        f'{response_length}, template_length {len(template)}.'
    )
  chars = string.ascii_letters + string.digits
  return template % ''.join(random.choice(chars) for _ in range(result_length))


class FakeClient(client_base.ClientBase):
  """Fake client class for unit tests."""

  def __init__(self):
    """Initializes the instance by mocking a device controller."""
    mock_device = mock.Mock()
    mock_device.log = logging
    super().__init__(package='FakeClient', device=mock_device)

  # Override abstract methods to enable initialization
  def before_starting_server(self):
    pass

  def start_server(self):
    pass

  def make_connection(self):
    pass

  def restore_server_connection(self, port=None):
    pass

  def check_server_proc_running(self):
    pass

  def send_rpc_request(self, request):
    pass

  def handle_callback(self, callback_id, ret_value, rpc_func_name):
    pass

  def stop(self):
    pass

  def close_connection(self):
    pass


class ClientBaseTest(unittest.TestCase):
  """Unit tests for mobly.snippet.client_base.ClientBase."""

  def setUp(self):
    super().setUp()
    self.client = FakeClient()
    self.client.host_port = 12345

  @mock.patch.object(FakeClient, 'before_starting_server')
  @mock.patch.object(FakeClient, 'start_server')
  @mock.patch.object(FakeClient, '_make_connection')
  def test_init_server_stage_order(
      self, mock_make_conn_func, mock_start_func, mock_before_func
  ):
    """Test that initialization runs its stages in expected order."""
    order_manager = mock.Mock()
    order_manager.attach_mock(mock_before_func, 'mock_before_func')
    order_manager.attach_mock(mock_start_func, 'mock_start_func')
    order_manager.attach_mock(mock_make_conn_func, 'mock_make_conn_func')

    self.client.initialize()

    expected_call_order = [
        mock.call.mock_before_func(),
        mock.call.mock_start_func(),
        mock.call.mock_make_conn_func(),
    ]
    self.assertListEqual(order_manager.mock_calls, expected_call_order)

  @mock.patch.object(FakeClient, 'stop')
  @mock.patch.object(FakeClient, 'before_starting_server')
  def test_init_server_before_starting_server_fail(
      self, mock_before_func, mock_stop_func
  ):
    """Test before_starting_server stage of initialization fails."""
    mock_before_func.side_effect = Exception('ha')

    with self.assertRaisesRegex(Exception, 'ha'):
      self.client.initialize()
    mock_stop_func.assert_not_called()

  @mock.patch.object(FakeClient, 'stop')
  @mock.patch.object(FakeClient, 'start_server')
  def test_init_server_start_server_fail(self, mock_start_func, mock_stop_func):
    """Test start_server stage of initialization fails."""
    mock_start_func.side_effect = Exception('ha')

    with self.assertRaisesRegex(Exception, 'ha'):
      self.client.initialize()
    mock_stop_func.assert_called()

  @mock.patch.object(FakeClient, 'stop')
  @mock.patch.object(FakeClient, '_make_connection')
  def test_init_server_make_connection_fail(
      self, mock_make_conn_func, mock_stop_func
  ):
    """Test _make_connection stage of initialization fails."""
    mock_make_conn_func.side_effect = Exception('ha')

    with self.assertRaisesRegex(Exception, 'ha'):
      self.client.initialize()
    mock_stop_func.assert_called()

  @mock.patch.object(FakeClient, 'check_server_proc_running')
  @mock.patch.object(FakeClient, '_gen_rpc_request')
  @mock.patch.object(FakeClient, 'send_rpc_request')
  @mock.patch.object(FakeClient, '_decode_response_string_and_validate_format')
  @mock.patch.object(FakeClient, '_handle_rpc_response')
  def test_rpc_stage_dependencies(
      self,
      mock_handle_resp,
      mock_decode_resp_str,
      mock_send_request,
      mock_gen_request,
      mock_precheck,
  ):
    """Test the internal dependencies when sending an RPC.

    When sending an RPC, it calls multiple functions in specific order, and
    each function uses the output of the previously called function. This test
    case checks above dependencies.

    Args:
      mock_handle_resp: the mock function of FakeClient._handle_rpc_response.
      mock_decode_resp_str: the mock function of
        FakeClient._decode_response_string_and_validate_format.
      mock_send_request: the mock function of FakeClient.send_rpc_request.
      mock_gen_request: the mock function of FakeClient._gen_rpc_request.
      mock_precheck: the mock function of FakeClient.check_server_proc_running.
    """
    self.client.initialize()

    expected_response_str = (
        '{"id": 0, "result": 123, "error": null, "callback": null}'
    )
    expected_response_dict = {
        'id': 0,
        'result': 123,
        'error': None,
        'callback': None,
    }
    expected_request = (
        '{"id": 10, "method": "some_rpc", "params": [1, 2],'
        '"kwargs": {"test_key": 3}'
    )
    expected_result = 123

    mock_gen_request.return_value = expected_request
    mock_send_request.return_value = expected_response_str
    mock_decode_resp_str.return_value = expected_response_dict
    mock_handle_resp.return_value = expected_result
    rpc_result = self.client.some_rpc(1, 2, test_key=3)

    mock_precheck.assert_called()
    mock_gen_request.assert_called_with(0, 'some_rpc', 1, 2, test_key=3)
    mock_send_request.assert_called_with(expected_request)
    mock_decode_resp_str.assert_called_with(0, expected_response_str)
    mock_handle_resp.assert_called_with('some_rpc', expected_response_dict)
    self.assertEqual(rpc_result, expected_result)

  @mock.patch.object(FakeClient, 'check_server_proc_running')
  @mock.patch.object(FakeClient, '_gen_rpc_request')
  @mock.patch.object(FakeClient, 'send_rpc_request')
  @mock.patch.object(FakeClient, '_decode_response_string_and_validate_format')
  @mock.patch.object(FakeClient, '_handle_rpc_response')
  def test_rpc_precheck_fail(
      self,
      mock_handle_resp,
      mock_decode_resp_str,
      mock_send_request,
      mock_gen_request,
      mock_precheck,
  ):
    """Test when RPC precheck fails it will skip sending the RPC."""
    self.client.initialize()
    mock_precheck.side_effect = Exception('server_died')

    with self.assertRaisesRegex(Exception, 'server_died'):
      self.client.some_rpc(1, 2)

    mock_gen_request.assert_not_called()
    mock_send_request.assert_not_called()
    mock_handle_resp.assert_not_called()
    mock_decode_resp_str.assert_not_called()

  def test_gen_request(self):
    """Test generating an RPC request.

    Test that _gen_rpc_request returns a string represents a JSON dict
    with all required fields.
    """
    request = self.client._gen_rpc_request(0, 'test_rpc', 1, 2, test_key=3)
    expected_result = (
        '{"id": 0, "kwargs": {"test_key": 3}, '
        '"method": "test_rpc", "params": [1, 2]}'
    )
    self.assertEqual(request, expected_result)

  def test_gen_request_without_kwargs(self):
    """Test no keyword arguments.

    Test that _gen_rpc_request ignores the kwargs field when no
    keyword arguments.
    """
    request = self.client._gen_rpc_request(0, 'test_rpc', 1, 2)
    expected_result = '{"id": 0, "method": "test_rpc", "params": [1, 2]}'
    self.assertEqual(request, expected_result)

  def test_rpc_no_response(self):
    """Test parsing an empty RPC response."""
    with self.assertRaisesRegex(
        errors.ProtocolError, errors.ProtocolError.NO_RESPONSE_FROM_SERVER
    ):
      self.client._decode_response_string_and_validate_format(0, '')

    with self.assertRaisesRegex(
        errors.ProtocolError, errors.ProtocolError.NO_RESPONSE_FROM_SERVER
    ):
      self.client._decode_response_string_and_validate_format(0, None)

  def test_rpc_response_missing_fields(self):
    """Test parsing an RPC response that misses some required fields."""
    mock_resp_without_id = '{"result": 123, "error": null, "callback": null}'
    with self.assertRaisesRegex(
        errors.ProtocolError, errors.ProtocolError.RESPONSE_MISSING_FIELD % 'id'
    ):
      self.client._decode_response_string_and_validate_format(
          10, mock_resp_without_id
      )

    mock_resp_without_result = '{"id": 10, "error": null, "callback": null}'
    with self.assertRaisesRegex(
        errors.ProtocolError,
        errors.ProtocolError.RESPONSE_MISSING_FIELD % 'result',
    ):
      self.client._decode_response_string_and_validate_format(
          10, mock_resp_without_result
      )

    mock_resp_without_error = '{"id": 10, "result": 123, "callback": null}'
    with self.assertRaisesRegex(
        errors.ProtocolError,
        errors.ProtocolError.RESPONSE_MISSING_FIELD % 'error',
    ):
      self.client._decode_response_string_and_validate_format(
          10, mock_resp_without_error
      )

    mock_resp_without_callback = '{"id": 10, "result": 123, "error": null}'
    with self.assertRaisesRegex(
        errors.ProtocolError,
        errors.ProtocolError.RESPONSE_MISSING_FIELD % 'callback',
    ):
      self.client._decode_response_string_and_validate_format(
          10, mock_resp_without_callback
      )

  def test_rpc_response_error(self):
    """Test parsing an RPC response with a non-empty error field."""
    mock_resp_with_error = {
        'id': 10,
        'result': 123,
        'error': 'some_error',
        'callback': None,
    }
    with self.assertRaisesRegex(errors.ApiError, 'some_error'):
      self.client._handle_rpc_response('some_rpc', mock_resp_with_error)

  def test_rpc_response_callback(self):
    """Test parsing response function handles the callback field well."""
    # Call handle_callback function if the "callback" field is not None
    mock_resp_with_callback = {
        'id': 10,
        'result': 123,
        'error': None,
        'callback': '1-0',
    }
    with mock.patch.object(
        self.client, 'handle_callback'
    ) as mock_handle_callback:
      expected_callback = mock.Mock()
      mock_handle_callback.return_value = expected_callback

      rpc_result = self.client._handle_rpc_response(
          'some_rpc', mock_resp_with_callback
      )
      mock_handle_callback.assert_called_with('1-0', 123, 'some_rpc')
      # Ensure the RPC function returns what handle_callback returned
      self.assertIs(expected_callback, rpc_result)

    # Do not call handle_callback function if the "callback" field is None
    mock_resp_without_callback = {
        'id': 10,
        'result': 123,
        'error': None,
        'callback': None,
    }
    with mock.patch.object(
        self.client, 'handle_callback'
    ) as mock_handle_callback:
      self.client._handle_rpc_response('some_rpc', mock_resp_without_callback)
      mock_handle_callback.assert_not_called()

  def test_rpc_response_id_mismatch(self):
    """Test parsing an RPC response with a wrong id."""
    right_id = 5
    wrong_id = 20
    resp = f'{{"id": {right_id}, "result": 1, "error": null, "callback": null}}'

    with self.assertRaisesRegex(
        errors.ProtocolError, errors.ProtocolError.MISMATCHED_API_ID
    ):
      self.client._decode_response_string_and_validate_format(wrong_id, resp)

  @mock.patch.object(FakeClient, 'send_rpc_request')
  def test_rpc_verbose_logging_with_long_string(self, mock_send_request):
    """Test RPC response isn't truncated when verbose logging is on."""
    mock_log = mock.Mock()
    self.client.log = mock_log
    self.client.set_snippet_client_verbose_logging(True)
    self.client.initialize()

    resp = _generate_fix_length_rpc_response(
        client_base._MAX_RPC_RESP_LOGGING_LENGTH * 2
    )
    mock_send_request.return_value = resp
    self.client.some_rpc(1, 2)
    mock_log.debug.assert_called_with('Snippet received: %s', resp)

  @mock.patch.object(FakeClient, 'send_rpc_request')
  def test_rpc_truncated_logging_short_response(self, mock_send_request):
    """Test RPC response isn't truncated with small length."""
    mock_log = mock.Mock()
    self.client.log = mock_log
    self.client.set_snippet_client_verbose_logging(False)
    self.client.initialize()

    resp = _generate_fix_length_rpc_response(
        int(client_base._MAX_RPC_RESP_LOGGING_LENGTH // 2)
    )
    mock_send_request.return_value = resp
    self.client.some_rpc(1, 2)
    mock_log.debug.assert_called_with('Snippet received: %s', resp)

  @mock.patch.object(FakeClient, 'send_rpc_request')
  def test_rpc_truncated_logging_fit_size_response(self, mock_send_request):
    """Test RPC response isn't truncated with length equal to the threshold."""
    mock_log = mock.Mock()
    self.client.log = mock_log
    self.client.set_snippet_client_verbose_logging(False)
    self.client.initialize()

    resp = _generate_fix_length_rpc_response(
        client_base._MAX_RPC_RESP_LOGGING_LENGTH
    )
    mock_send_request.return_value = resp
    self.client.some_rpc(1, 2)
    mock_log.debug.assert_called_with('Snippet received: %s', resp)

  @mock.patch.object(FakeClient, 'send_rpc_request')
  def test_rpc_truncated_logging_long_response(self, mock_send_request):
    """Test RPC response is truncated with length larger than the threshold."""
    mock_log = mock.Mock()
    self.client.log = mock_log
    self.client.set_snippet_client_verbose_logging(False)
    self.client.initialize()

    max_len = client_base._MAX_RPC_RESP_LOGGING_LENGTH
    resp = _generate_fix_length_rpc_response(max_len * 40)
    mock_send_request.return_value = resp
    self.client.some_rpc(1, 2)
    mock_log.debug.assert_called_with(
        'Snippet received: %s... %d chars are truncated',
        resp[: client_base._MAX_RPC_RESP_LOGGING_LENGTH],
        len(resp) - max_len,
    )

  @mock.patch.object(FakeClient, 'send_rpc_request')
  def test_rpc_call_increment_counter(self, mock_send_request):
    """Test that with each RPC call the counter is incremented by 1."""
    self.client.initialize()
    resp = '{"id": %d, "result": 123, "error": null, "callback": null}'
    mock_send_request.side_effect = (resp % (i,) for i in range(10))

    for _ in range(0, 10):
      self.client.some_rpc()

    self.assertEqual(next(self.client._counter), 10)

  @mock.patch.object(FakeClient, 'send_rpc_request')
  def test_init_connection_reset_counter(self, mock_send_request):
    """Test that _make_connection resets the counter to zero."""
    self.client.initialize()
    resp = '{"id": %d, "result": 123, "error": null, "callback": null}'
    mock_send_request.side_effect = (resp % (i,) for i in range(10))

    for _ in range(0, 10):
      self.client.some_rpc()

    self.assertEqual(next(self.client._counter), 10)
    self.client._make_connection()
    self.assertEqual(next(self.client._counter), 0)


if __name__ == '__main__':
  unittest.main()
