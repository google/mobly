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
"""Unit tests for mobly.snippet.callback_event.CallbackEvent."""

import unittest

from mobly.snippet import callback_event

MOCK_CALLBACK_ID = 'myCallbackId'
MOCK_EVENT_NAME = 'onXyzEvent'
MOCK_CREATION_TIME = '12345678'
MOCK_DATA = {'foo': 'bar'}


class CallbackEventTest(unittest.TestCase):
  """Unit tests for mobly.snippet.callback_event.CallbackEvent."""

  def test_basic(self):
    """Verifies that an event object can be created and logged properly."""
    event = callback_event.CallbackEvent(
        MOCK_CALLBACK_ID, MOCK_EVENT_NAME, MOCK_CREATION_TIME, MOCK_DATA
    )
    self.assertEqual(
        repr(event),
        'CallbackEvent(callback_id: myCallbackId, name: onXyzEvent, '
        "creation_time: 12345678, data: {'foo': 'bar'})",
    )


if __name__ == '__main__':
  unittest.main()
