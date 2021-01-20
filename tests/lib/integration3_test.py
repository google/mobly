# Copyright 2018 Google Inc.
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


class Integration3Test(base_test.BaseTestClass):
  """This test class is used to cause a failure in integration tests."""

  def setup_class(self):
    asserts.fail('Setup failure.')

  def on_fail(self, record):
    asserts.abort_all('Skip tests.')

  def test_empty(self):
    pass


if __name__ == '__main__':
  test_runner.main()
