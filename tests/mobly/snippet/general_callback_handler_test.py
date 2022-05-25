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
from mobly.snippet import general_callback_handler
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


class CallbackHandlerTest(unittest.TestCase):
  """Unit tests for mobly.snippet.callback_handler_base.CallbackHandlerBase."""

  def _make_callback_handler(self,
                             callback_id=None,
                             event_client=None,
                             ret_value=None,
                             method_name=None,
                             device=None,
                             rpc_max_timeout_sec=600,
                             default_timeout_sec=120,
                             timeout_msg_pattern=None):
    return general_callback_handler.GeneralCallbackHandler(
        callback_id=callback_id,
        event_client=event_client,
        ret_value=ret_value,
        method_name=method_name,
        device=device,
        rpc_max_timeout_sec=rpc_max_timeout_sec,
        default_timeout_sec=default_timeout_sec,
        timeout_msg_pattern=timeout_msg_pattern)

  def assert_event_correct(self, actual_event, expected_raw_event_dict):
    expected_event = snippet_event.from_dict(expected_raw_event_dict)
    self.assertEqual(str(actual_event), str(expected_event))

  def test_wait_and_get(self):
    mock_event_client = mock.Mock()
    mock_event_client.eventWaitAndGet = mock.Mock(return_value=MOCK_RAW_EVENT)
    handler = self._make_callback_handler(callback_id=MOCK_CALLBACK_ID,
                                          event_client=mock_event_client)
    event = handler.waitAndGet('ha')
    self.assert_event_correct(event, MOCK_RAW_EVENT)
    mock_event_client.eventWaitAndGet.assert_called_once_with(
        MOCK_CALLBACK_ID, 'ha', mock.ANY)

  def test_wait_and_get_timeout_arg_transform(self):
    mock_event_client = mock.Mock()
    mock_event_client.eventWaitAndGet = mock.Mock(return_value=MOCK_RAW_EVENT)
    handler = self._make_callback_handler(event_client=mock_event_client)

    wait_and_get_timeout_sec = 10
    expected_rpc_timeout_ms = 10000
    event = handler.waitAndGet('ha', timeout=wait_and_get_timeout_sec)
    mock_event_client.eventWaitAndGet.assert_called_once_with(
        mock.ANY, mock.ANY, expected_rpc_timeout_ms)

  def test_wait_for_event(self):
    mock_event_client = mock.Mock()
    handler = self._make_callback_handler(callback_id=MOCK_CALLBACK_ID,
                                          event_client=mock_event_client)

    event_should_ignore = {
        'callbackId': '2-1',
        'name': 'AsyncTaskResult',
        'time': 20460228696,
        'data': {
            'successful': False,
        }
    }
    mock_event_client.eventWaitAndGet.side_effect = [
        event_should_ignore, MOCK_RAW_EVENT]

    def some_condition(event):
      return event.data['successful']

    event = handler.waitForEvent('AsyncTaskResult', some_condition, 0.01)
    self.assert_event_correct(event, MOCK_RAW_EVENT)
    mock_event_client.eventWaitAndGet.assert_has_calls(
        [
          mock.call(MOCK_CALLBACK_ID, 'AsyncTaskResult', mock.ANY),
          mock.call(MOCK_CALLBACK_ID, 'AsyncTaskResult', mock.ANY),
        ]
    )

  def test_get_all(self):
    mock_event_client = mock.Mock()
    handler = self._make_callback_handler(
        callback_id=MOCK_CALLBACK_ID,
        event_client=mock_event_client)

    mock_event_client.eventGetAll = mock.Mock(
        return_value=[MOCK_RAW_EVENT, MOCK_RAW_EVENT])

    all_events = handler.getAll('ha')
    self.assertEqual(len(all_events), 2)
    for event in all_events:
      self.assert_event_correct(event, MOCK_RAW_EVENT)

    mock_event_client.eventGetAll.assert_called_once_with(
        MOCK_CALLBACK_ID, 'ha'
    )

  def test_wait_and_get_reraise_if_no_timeout_pattern(self):
    mock_event_client = mock.Mock()
    snippet_timeout_msg = 'EventSnippetException: timeout.'
    mock_event_client.eventWaitAndGet = mock.Mock(
        side_effect=errors.ApiError(mock.Mock(), snippet_timeout_msg))
    handler = self._make_callback_handler(
        event_client=mock_event_client,
        timeout_msg_pattern=None)

    with self.assertRaisesRegex(errors.ApiError, snippet_timeout_msg):
      handler.waitAndGet('ha')

  def test_wait_and_get_android_timeout_message_pattern(self):
    mock_event_client = mock.Mock()
    android_snippet_timeout_msg = (
        'com.google.android.mobly.snippet.event.EventSnippet$'
        'EventSnippetException: timeout.')
    mock_event_client.eventWaitAndGet = mock.Mock(
        side_effect=errors.ApiError(mock.Mock(), android_snippet_timeout_msg))
    handler = self._make_callback_handler(
        event_client=mock_event_client,
        timeout_msg_pattern=(
            general_callback_handler.ANDROID_SNIPPET_TIMEOUT_MESSAGE_PATTERN),
    )

    expected_msg = 'Timed out after waiting .*s for event "ha" .*'
    with self.assertRaisesRegex(errors.CallbackHandlerTimeoutError, expected_msg):
      handler.waitAndGet('ha')

  def test_wait_and_get_reraise_if_pattern_not_match(self):
    mock_event_client = mock.Mock()
    snippet_timeout_msg = 'Snippet executed with error.'
    mock_event_client.eventWaitAndGet = mock.Mock(
        side_effect=errors.ApiError(mock.Mock(), snippet_timeout_msg))
    handler = self._make_callback_handler(
        event_client=mock_event_client,
        timeout_msg_pattern='EventSnippetException: timeout.')

    with self.assertRaisesRegex(errors.ApiError, snippet_timeout_msg):
      handler.waitAndGet('ha')

if __name__ == "__main__":
  unittest.main()
