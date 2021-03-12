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
import unittest

from mobly.controllers.android_device_lib.services import snippet_management_service

MOCK_PACKAGE = 'com.mock.package'
SNIPPET_CLIENT_CLASS_PATH = 'mobly.controllers.android_device_lib.snippet_client.SnippetClient'


class SnippetManagementServiceTest(unittest.TestCase):
  """Tests for the snippet management service."""

  def test_empty_manager_start_stop(self):
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager.start()
    # When no client is registered, manager is never alive.
    self.assertFalse(manager.is_alive)
    manager.stop()
    self.assertFalse(manager.is_alive)

  @mock.patch(SNIPPET_CLIENT_CLASS_PATH)
  def test_get_snippet_client(self, mock_class):
    mock_client = mock_class.return_value
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager.add_snippet_client('foo', MOCK_PACKAGE)
    self.assertEqual(manager.get_snippet_client('foo'), mock_client)

  @mock.patch(SNIPPET_CLIENT_CLASS_PATH)
  def test_get_snippet_client_fail(self, _):
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    self.assertIsNone(manager.get_snippet_client('foo'))

  @mock.patch(SNIPPET_CLIENT_CLASS_PATH)
  def test_stop_with_live_client(self, mock_class):
    mock_client = mock_class.return_value
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager.add_snippet_client('foo', MOCK_PACKAGE)
    mock_client.start_app_and_connect.assert_called_once_with()
    manager.stop()
    mock_client.stop_app.assert_called_once_with()
    mock_client.stop_app.reset_mock()
    mock_client.is_alive = False
    self.assertFalse(manager.is_alive)
    manager.stop()
    mock_client.stop_app.assert_not_called()

  @mock.patch(SNIPPET_CLIENT_CLASS_PATH)
  def test_add_snippet_client_dup_name(self, _):
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager.add_snippet_client('foo', MOCK_PACKAGE)
    msg = ('.* Name "foo" is already registered with package ".*", it '
           'cannot be used again.')
    with self.assertRaisesRegex(snippet_management_service.Error, msg):
      manager.add_snippet_client('foo', MOCK_PACKAGE + 'ha')

  @mock.patch(SNIPPET_CLIENT_CLASS_PATH)
  def test_add_snippet_client_dup_package(self, mock_class):
    mock_client = mock_class.return_value
    mock_client.package = MOCK_PACKAGE
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager.add_snippet_client('foo', MOCK_PACKAGE)
    msg = ('Snippet package "com.mock.package" has already been loaded '
           'under name "foo".')
    with self.assertRaisesRegex(snippet_management_service.Error, msg):
      manager.add_snippet_client('bar', MOCK_PACKAGE)

  @mock.patch(SNIPPET_CLIENT_CLASS_PATH)
  def test_remove_snippet_client(self, mock_class):
    mock_client = mock.MagicMock()
    mock_class.return_value = mock_client
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager.add_snippet_client('foo', MOCK_PACKAGE)
    manager.remove_snippet_client('foo')
    msg = 'No snippet client is registered with name "foo".'
    with self.assertRaisesRegex(snippet_management_service.Error, msg):
      manager.foo.do_something()

  @mock.patch(SNIPPET_CLIENT_CLASS_PATH)
  def test_remove_snippet_client(self, mock_class):
    mock_client = mock.MagicMock()
    mock_class.return_value = mock_client
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    with self.assertRaisesRegex(
        snippet_management_service.Error,
        'No snippet client is registered with name "foo".'):
      manager.remove_snippet_client('foo')

  @mock.patch(SNIPPET_CLIENT_CLASS_PATH)
  def test_start_with_live_service(self, mock_class):
    mock_client = mock_class.return_value
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager.add_snippet_client('foo', MOCK_PACKAGE)
    mock_client.start_app_and_connect.reset_mock()
    mock_client.is_alive = True
    manager.start()
    mock_client.start_app_and_connect.assert_not_called()
    self.assertTrue(manager.is_alive)
    mock_client.is_alive = False
    manager.start()
    mock_client.start_app_and_connect.assert_called_once_with()

  @mock.patch(SNIPPET_CLIENT_CLASS_PATH)
  def test_pause(self, mock_class):
    mock_client = mock_class.return_value
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager.add_snippet_client('foo', MOCK_PACKAGE)
    manager.pause()
    mock_client.disconnect.assert_called_once_with()

  @mock.patch(SNIPPET_CLIENT_CLASS_PATH)
  def test_resume_positive_case(self, mock_class):
    mock_client = mock_class.return_value
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager.add_snippet_client('foo', MOCK_PACKAGE)
    mock_client.is_alive = False
    manager.resume()
    mock_client.restore_app_connection.assert_called_once_with()

  @mock.patch(SNIPPET_CLIENT_CLASS_PATH)
  def test_resume_negative_case(self, mock_class):
    mock_client = mock_class.return_value
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager.add_snippet_client('foo', MOCK_PACKAGE)
    mock_client.is_alive = True
    manager.resume()
    mock_client.restore_app_connection.assert_not_called()

  @mock.patch(SNIPPET_CLIENT_CLASS_PATH)
  def test_attribute_access(self, mock_class):
    mock_client = mock.MagicMock()
    mock_class.return_value = mock_client
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager.add_snippet_client('foo', MOCK_PACKAGE)
    manager.foo.ha('param')
    mock_client.ha.assert_called_once_with('param')


if __name__ == '__main__':
  unittest.main()
