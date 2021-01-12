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

from mobly import test_runner

from tests.lib import integration_test


class Integration2Test(integration_test.IntegrationTest):
  """Same as the IntegrationTest class, created this so we have two
  'different' test classes to use in unit tests.
  """


if __name__ == "__main__":
  test_runner.main()
