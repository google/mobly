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

import string
import random
from unittest import mock
from tests.lib import mock_android_device

MOCK_RESP_FLEXIABLE_RESULT_LENGTH = (
    '{"id": 0, "result": "%s", "error": null, "status": 0, "callback": null}')

MOCK_USER_ID = 0


def generate_fix_length_rpc_response(response_length):
  length = response_length - len(MOCK_RESP_FLEXIABLE_RESULT_LENGTH) + 2
  chars = string.ascii_letters + string.digits
  random_msg = ''.join(random.choice(chars) for i in range(length))
  mock_response = MOCK_RESP_FLEXIABLE_RESULT_LENGTH % random_msg
  return mock_response
