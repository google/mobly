# Copyright 2026 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from mobly import asserts
from mobly import base_test
from mobly import test_runner
from tests.lib import mock_controller


class DynamicTest(base_test.BaseTestClass):
  """Test class using @repeat and @retry with dynamic user_params keys."""

  repeat_counter = 0
  retry_counter = 0

  def setup_class(self):
    self.register_controller(mock_controller)
    type(self).repeat_counter = 0
    type(self).retry_counter = 0

  @base_test.repeat(count=2, count_key='repeat_key')
  def test_repeat(self):
    type(self).repeat_counter += 1
    asserts.assert_true(True, 'Repeat iteration succeeded')

  @base_test.retry(max_count=2, max_count_key='retry_key')
  def test_retry(self):
    type(self).retry_counter += 1
    # Succeeds on 3rd attempt if retry limit is >= 3.
    if type(self).retry_counter < 3:
      asserts.fail(f'Retry attempt {type(self).retry_counter} failed')
    asserts.assert_true(True, 'Retry attempt succeeded')


if __name__ == '__main__':
  test_runner.main()
