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

from mobly.controllers.android_device_lib import snippet_client
from mobly.controllers.android_device_lib.services import snippet_service

MOCK_SNIPPET_PACKAGE = 'com.some.snippet'
MOCK_CONFIG = snippet_service.Config(package=MOCK_SNIPPET_PACKAGE)


class SnippetServiceTest(unittest.TestCase):
    """Tests for Snippet service."""

    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient')
    @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy')
    def test_snippet_service_start_stop(self, mock_adb, mock_snippet_client):
        mock_device = mock.MagicMock()
        service = snippet_service.SnippetService(mock_device, MOCK_CONFIG)
        service.start()
        self.assertTrue(service.is_alive)
        self.assertIsNotNone(service.client)
        service.stop()
        self.assertFalse(service.is_alive)
        self.assertIsNone(service.client)

    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient')
    @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy')
    def test_direct_attribute_access(self, mock_adb, mock_snippet_client):
        mock_device = mock.MagicMock()
        service = snippet_service.SnippetService(mock_device, MOCK_CONFIG)
        service.start()
        service.client.do_something = mock.MagicMock()
        service.do_something('crazy')
        service.client.do_something.assert_called_once_with('crazy')

    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient')
    @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy')
    def test_override_start_config(self, mock_adb, mock_snippet_client):
        mock_device = mock.MagicMock()
        service = snippet_service.SnippetService(mock_device, MOCK_CONFIG)
        msg = 'Overriding config in `start` is allowed for SnippetService.'
        with self.assertRaisesRegex(snippet_service.Error, msg):
            service.start('something')
        self.assertFalse(service.is_alive)

    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient.start_app_and_connect'
    )
    @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy')
    def test_start_precheck_fail(self, mock_adb, mock_start_func):
        mock_device = mock.MagicMock()
        mock_start_func.side_effect = snippet_client.AppStartPreCheckError(
            mock_device, 'ha')
        service = snippet_service.SnippetService(mock_device, MOCK_CONFIG)
        with self.assertRaisesRegex(snippet_client.AppStartPreCheckError,
                                    'ha'):
            service.start()
        self.assertFalse(service.is_alive)
        self.assertIsNone(service.client)

    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient.start_app_and_connect'
    )
    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient.stop_app'
    )
    @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy')
    def test_start_generic_error(self, mock_adb, mock_stop_func,
                                 mock_start_func):
        mock_device = mock.MagicMock()
        mock_start_func.side_effect = Exception('Something failed!')
        service = snippet_service.SnippetService(mock_device, MOCK_CONFIG)
        with self.assertRaisesRegex(Exception, 'Something failed!'):
            service.start()
        mock_stop_func.assert_called_once_with()
        self.assertFalse(service.is_alive)
        self.assertIsNone(service.client)

    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient.start_app_and_connect'
    )
    @mock.patch(
        'mobly.controllers.android_device_lib.snippet_client.SnippetClient.stop_app'
    )
    @mock.patch('mobly.controllers.android_device_lib.adb.AdbProxy')
    def test_start_generic_error_stop_also_fail(self, mock_adb, mock_stop_func,
                                                mock_start_func):
        mock_device = mock.MagicMock()
        mock_start_func.side_effect = Exception('Something failed!')
        mock_stop_func.side_effect = Exception('Something else also failed!')
        service = snippet_service.SnippetService(mock_device, MOCK_CONFIG)
        with self.assertRaisesRegex(Exception, 'Something failed!'):
            service.start()
        mock_stop_func.assert_called_once_with()
        self.assertFalse(service.is_alive)
        self.assertIsNone(service.client)


if __name__ == '__main__':
    unittest.main()
