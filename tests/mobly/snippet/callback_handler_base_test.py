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

import unittest
from unittest import mock

from mobly.snippet import callback_handler_base
from mobly.snippet import errors
from mobly.snippet import snippet_event
from mobly.controllers.android_device_lib import jsonrpc_client_base

MOCK_CALLBACK_ID = "2-1"
MOCK_RAW_EVENT = {
    'callbackId': '2-1',
    'name': 'AsyncTaskResult',
    'time': 20460228696,
    'data': {
        'exampleData': "Here's a simple event.",
        'successful': True,
        'secretNumber': 12
    }
}

class FakeCallbackHandler(callback_handler_base.CallbackHandlerBase):

  def __init__(self,
      callback_id=None, event_client=None, ret_value=None, method_name=None,
      device=None, rpc_max_timeout_sec=120, default_timeout_sec=120):
    super().__init__(callback_id, event_client, ret_value, method_name, device,
                     rpc_max_timeout_sec, default_timeout_sec)
    self.mock_rpc_func = mock.Mock()

  def callEventWaitAndGetRpc(self, *args, **kwargs):
    return self.mock_rpc_func.callEventWaitAndGetRpc(*args, **kwargs)

  def callEventGetAllRpc(self, *args, **kwargs):
    return self.mock_rpc_func.callEventGetAllRpc(*args, **kwargs)


class CallbackHandlerTest(unittest.TestCase):
  """Unit tests for mobly.snippet.callback_handler_base.CallbackHandlerBase."""

  def assert_event_correct(self, actual_event, expected_raw_event_dict):
    expected_event = snippet_event.from_dict(expected_raw_event_dict)
    self.assertEqual(str(actual_event), str(expected_event))

  # TODO: we should modify this test...
  def _test_timeout_value(self):
    self.assertGreaterEqual(jsonrpc_client_base._SOCKET_READ_TIMEOUT,
                            callback_handler.MAX_TIMEOUT)

  def test_default_timeout_too_large(self):
    err_msg = ('The max timeout of single RPC must be no smaller than '
               'the default timeout of the callback handler. '
               f'Got rpc_max_timeout_sec=10, '
               f'default_timeout_sec=20.')
    with self.assertRaisesRegex(ValueError, err_msg):
      handler = FakeCallbackHandler(rpc_max_timeout_sec=10, default_timeout_sec=20)

  def test_timeout_property(self):
    handler = FakeCallbackHandler(rpc_max_timeout_sec=20, default_timeout_sec=10)
    self.assertEqual(handler.rpc_max_timeout_sec, 20)
    self.assertEqual(handler.default_timeout_sec, 10)
    with self.assertRaisesRegex(AttributeError, "can't set attribute"):
      handler.rpc_max_timeout_sec = 5

    with self.assertRaisesRegex(AttributeError, "can't set attribute"):
      handler.default_timeout_sec = 5

  def test_callback_id_property(self):
    handler = FakeCallbackHandler(callback_id=MOCK_CALLBACK_ID)
    self.assertEqual(handler.callback_id, MOCK_CALLBACK_ID)
    with self.assertRaisesRegex(AttributeError, "can't set attribute"):
      handler.callback_id = 'ha'

  def test_event_dict_to_snippet_event(self):
    handler = FakeCallbackHandler(callback_id=MOCK_CALLBACK_ID)
    handler.mock_rpc_func.callEventWaitAndGetRpc = mock.Mock(return_value=MOCK_RAW_EVENT)

    event = handler.waitAndGet('ha', timeout=10)
    self.assert_event_correct(event, MOCK_RAW_EVENT)
    handler.mock_rpc_func.callEventWaitAndGetRpc.assert_called_once_with(
        MOCK_CALLBACK_ID, 'ha', 10)

  def test_wait_and_get_timeout_default(self):
    handler = FakeCallbackHandler(rpc_max_timeout_sec=20, default_timeout_sec=5)
    handler.mock_rpc_func.callEventWaitAndGetRpc = mock.Mock(return_value=MOCK_RAW_EVENT)
    _ = handler.waitAndGet('ha')
    handler.mock_rpc_func.callEventWaitAndGetRpc.assert_called_once_with(
        mock.ANY, mock.ANY, 5)

  def test_wait_and_get_timeout_ecxeed_threshold(self):
    rpc_max_timeout_sec = 5
    big_timeout_sec = 10
    handler = FakeCallbackHandler(rpc_max_timeout_sec=rpc_max_timeout_sec,
                                  default_timeout_sec=rpc_max_timeout_sec)
    handler.mock_rpc_func.callEventWaitAndGetRpc = mock.Mock(return_value=MOCK_RAW_EVENT)

    expected_msg = (f'Specified timeout {big_timeout_sec} is longer than max timeout '
                    f'{rpc_max_timeout_sec}.')
    with self.assertRaisesRegex(errors.CallbackHandlerBaseError, expected_msg):
      handler.waitAndGet('ha', big_timeout_sec)

  def test_wait_for_event(self):
    handler = FakeCallbackHandler()
    handler.mock_rpc_func.callEventWaitAndGetRpc = mock.Mock(return_value=MOCK_RAW_EVENT)

    def some_condition(event):
      return event.data['successful']

    event = handler.waitForEvent('AsyncTaskResult', some_condition, 0.01)
    self.assert_event_correct(event, MOCK_RAW_EVENT)

  def test_wait_for_event_negative(self):
    handler = FakeCallbackHandler()
    handler.mock_rpc_func.callEventWaitAndGetRpc = mock.Mock(return_value=MOCK_RAW_EVENT)

    expected_msg = (
        'Timed out after 0.01s waiting for an "AsyncTaskResult" event that'
        ' satisfies the predicate "some_condition".')

    def some_condition(event):
      return False

    with self.assertRaisesRegex(errors.CallbackHandlerTimeoutError, expected_msg):
      handler.waitForEvent('AsyncTaskResult', some_condition, 0.01)

  def test_wait_for_event_max_timeout(self):
    """waitForEvent should not raise the timeout exceed threshold error."""
    rpc_max_timeout_sec = 5
    big_timeout_sec = 10
    handler = FakeCallbackHandler(rpc_max_timeout_sec=rpc_max_timeout_sec,
                                  default_timeout_sec=rpc_max_timeout_sec)
    handler.mock_rpc_func.callEventWaitAndGetRpc = mock.Mock(return_value=MOCK_RAW_EVENT)

    def some_condition(event):
      return event.data['successful']

    # This line should not raise.
    event = handler.waitForEvent('AsyncTaskResult',
                                 some_condition,
                                 timeout=big_timeout_sec)
    self.assert_event_correct(event, MOCK_RAW_EVENT)

  def test_get_all(self):
    handler = FakeCallbackHandler(callback_id=MOCK_CALLBACK_ID)
    handler.mock_rpc_func.callEventGetAllRpc = mock.Mock(
        return_value=[MOCK_RAW_EVENT, MOCK_RAW_EVENT])

    all_events = handler.getAll('ha')
    for event in all_events:
      self.assert_event_correct(event, MOCK_RAW_EVENT)

    handler.mock_rpc_func.callEventGetAllRpc.assert_called_once_with(
        MOCK_CALLBACK_ID, 'ha'
    )

if __name__ == "__main__":
  unittest.main()
