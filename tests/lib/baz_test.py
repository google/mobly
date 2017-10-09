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

from mobly import asserts
from mobly import base_test
from mobly import test_runner


class BazTest(base_test.BaseTestClass):
    """Adding some additional test methods for test selection tests. """
    
    def test_baz_a(self):
        asserts.explicit_pass("baz")

    def test_baz_b(self):
        asserts.explicit_pass("baz")

if __name__ == "__main__":
    test_runner.main()
