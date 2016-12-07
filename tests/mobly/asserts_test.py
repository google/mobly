#!/usr/bin/env python3.4
#
# Copyright 2016 Google Inc.
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

from mobly import asserts
from mobly import signals

MSG_EXPECTED_EXCEPTION = "This is an expected exception."


class AssertsTest(unittest.TestCase):
    """Verifies that asserts.xxx functions raise the correct test signals.
    """

    def test_assert_false(self):
        asserts.assert_false(False, MSG_EXPECTED_EXCEPTION)
        with self.assertRaisesRegexp(signals.TestFailure,
                                     MSG_EXPECTED_EXCEPTION):
            asserts.assert_false(True, MSG_EXPECTED_EXCEPTION)


if __name__ == "__main__":
    unittest.main()
