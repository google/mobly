# Copyright 2018 Google Inc.
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
import mock
from future.tests.base import unittest

from mobly.controllers.android_device_lib.services import snippet_manager


class SnippetManagerTest(unittest.TestCase):
    """Tests for the service manager of snippet."""

    def test_empty_manager_start_stop(self):
        mock_service = mock.MagicMock()
        mock_device = mock.MagicMock()
        manager = snippet_manager.SnippetManager(mock_device)
        manager.start()
        # When no service is registered, manager is never alive.
        self.assertFalse(manager.is_alive)
        manager.stop()
        self.assertFalse(manager.is_alive)
        


if __name__ == '__main__':
    unittest.main()
