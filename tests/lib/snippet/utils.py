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

"""Util functions for snippet client test modules."""

import string
import random


def generate_fix_length_rpc_response(
    response_length,
    template='{"id": 0, "result": "%s", "error": null, "callback": null}'):
  """Generates a RPC response string with specified length.

  This function generates a random string and formats the template with the
  generated random string to get the response string. This function uses
  printf style string formatting, i.e. the template can be

  ```
  '{"id": 0, "result": "%s", "error": null, "callback": null}'
  ```

  Args:
    response_length: int, the length of the response string to generate.
    template: str, the template used for generating the response string.

  Returns:
    The generated response string.


  Raises:
    ValueError: if the specified length is too small to generate a response.
  """
  length = response_length - len(template) + 2
  if length < 0:
    raise ValueError(
        'The response_length should be no smaller than '
        'template_length + 2. Got response_length %d, '
        'template_length %d.', response_length, len(template))
  chars = string.ascii_letters + string.digits
  random_msg = ''.join(random.choice(chars) for _ in range(length))
  return template % random_msg
