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

import unittest
from unittest import mock

from mobly.controllers.android_device_lib.services import snippet_management_service

MOCK_PACKAGE = 'com.mock.package'
SNIPPET_CLIENT_V2_CLASS_PATH = 'mobly.controllers.android_device_lib.snippet_client_v2.SnippetClientV2'


class SnippetManagementServiceTest(unittest.TestCase):
  """Tests for the snippet management service."""

  def test_empty_manager_start_stop(self):
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager._use_client_v2_switch = True
    manager.start()
    # When no client is registered, manager is never alive.
    self.assertFalse(manager.is_alive)
    manager.stop()
    self.assertFalse(manager.is_alive)

  @mock.patch(SNIPPET_CLIENT_V2_CLASS_PATH)
  def test_get_snippet_client(self, mock_class):
    mock_client = mock_class.return_value
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager._use_client_v2_switch = True
    manager.add_snippet_client('foo', MOCK_PACKAGE)
    self.assertEqual(manager.get_snippet_client('foo'), mock_client)

  @mock.patch(SNIPPET_CLIENT_V2_CLASS_PATH)
  def test_get_snippet_client_fail(self, _):
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager._use_client_v2_switch = True
    self.assertIsNone(manager.get_snippet_client('foo'))

  @mock.patch(SNIPPET_CLIENT_V2_CLASS_PATH)
  def test_stop_with_live_client(self, mock_class):
    mock_client = mock_class.return_value
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager._use_client_v2_switch = True
    manager.add_snippet_client('foo', MOCK_PACKAGE)
    mock_client.initialize.assert_called_once_with()
    manager.stop()
    mock_client.stop.assert_called_once_with()
    mock_client.stop.reset_mock()
    mock_client.is_alive = False
    self.assertFalse(manager.is_alive)
    manager.stop()
    mock_client.stop.assert_not_called()

  @mock.patch(SNIPPET_CLIENT_V2_CLASS_PATH)
  def test_add_snippet_client_dup_name(self, _):
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager._use_client_v2_switch = True
    manager.add_snippet_client('foo', MOCK_PACKAGE)
    msg = ('.* Name "foo" is already registered with package ".*", it '
           'cannot be used again.')
    with self.assertRaisesRegex(snippet_management_service.Error, msg):
      manager.add_snippet_client('foo', MOCK_PACKAGE + 'ha')

  @mock.patch(SNIPPET_CLIENT_V2_CLASS_PATH)
  def test_add_snippet_client_dup_package(self, mock_class):
    mock_client = mock_class.return_value
    mock_client.package = MOCK_PACKAGE
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager._use_client_v2_switch = True
    manager.add_snippet_client('foo', MOCK_PACKAGE)
    msg = ('Snippet package "com.mock.package" has already been loaded '
           'under name "foo".')
    with self.assertRaisesRegex(snippet_management_service.Error, msg):
      manager.add_snippet_client('bar', MOCK_PACKAGE)

  @mock.patch(SNIPPET_CLIENT_V2_CLASS_PATH)
  def test_remove_snippet_client(self, mock_class):
    mock_client = mock.MagicMock()
    mock_class.return_value = mock_client
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager._use_client_v2_switch = True
    manager.add_snippet_client('foo', MOCK_PACKAGE)
    manager.remove_snippet_client('foo')
    msg = 'No snippet client is registered with name "foo".'
    with self.assertRaisesRegex(snippet_management_service.Error, msg):
      manager.foo.do_something()

  @mock.patch(SNIPPET_CLIENT_V2_CLASS_PATH)
  def test_remove_snippet_client(self, mock_class):
    mock_client = mock.MagicMock()
    mock_class.return_value = mock_client
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager._use_client_v2_switch = True
    with self.assertRaisesRegex(
        snippet_management_service.Error,
        'No snippet client is registered with name "foo".'):
      manager.remove_snippet_client('foo')

  @mock.patch(SNIPPET_CLIENT_V2_CLASS_PATH)
  def test_start_with_live_service(self, mock_class):
    mock_client = mock_class.return_value
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager._use_client_v2_switch = True
    manager.add_snippet_client('foo', MOCK_PACKAGE)
    mock_client.initialize.reset_mock()
    mock_client.is_alive = True
    manager.start()
    mock_client.initialize.assert_not_called()
    self.assertTrue(manager.is_alive)
    mock_client.is_alive = False
    manager.start()
    mock_client.initialize.assert_called_once_with()

  @mock.patch(SNIPPET_CLIENT_V2_CLASS_PATH)
  def test_pause(self, mock_class):
    mock_client = mock_class.return_value
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager._use_client_v2_switch = True
    manager.add_snippet_client('foo', MOCK_PACKAGE)
    manager.pause()
    mock_client.close_connection.assert_called_once_with()

  @mock.patch(SNIPPET_CLIENT_V2_CLASS_PATH)
  def test_resume_positive_case(self, mock_class):
    mock_client = mock_class.return_value
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager._use_client_v2_switch = True
    manager.add_snippet_client('foo', MOCK_PACKAGE)
    mock_client.is_alive = False
    manager.resume()
    mock_client.restore_server_connection.assert_called_once_with()

  @mock.patch(SNIPPET_CLIENT_V2_CLASS_PATH)
  def test_resume_negative_case(self, mock_class):
    mock_client = mock_class.return_value
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager._use_client_v2_switch = True
    manager.add_snippet_client('foo', MOCK_PACKAGE)
    mock_client.is_alive = True
    manager.resume()
    mock_client.restore_server_connection.assert_not_called()

  @mock.patch(SNIPPET_CLIENT_V2_CLASS_PATH)
  def test_attribute_access(self, mock_class):
    mock_client = mock.MagicMock()
    mock_class.return_value = mock_client
    manager = snippet_management_service.SnippetManagementService(
        mock.MagicMock())
    manager._use_client_v2_switch = True
    manager.add_snippet_client('foo', MOCK_PACKAGE)
    manager.foo.ha('param')
    mock_client.ha.assert_called_once_with('param')

  # TODO(mhaoli): The client v2 switch is transient, we will remove related
  # tests after we complete the migration from v1 to v2.
  def test_client_v2_switch_default_value(self):
    self._set_device_attribute_and_check_client_v2_switch(
        expect_switch_value=True)

  def test_client_v2_switch_when_set_device_dimension_to_false(self):
    self._set_device_attribute_and_check_client_v2_switch(
        expect_switch_value=False,
        dimensions={'use_mobly_snippet_client_v2': 'false'})

  def test_client_v2_switch_when_set_device_dimension_to_true(self):
    self._set_device_attribute_and_check_client_v2_switch(
        expect_switch_value=True,
        dimensions={'use_mobly_snippet_client_v2': 'true'})

  def test_client_v2_switch_when_set_device_attribute_to_false(self):
    self._set_device_attribute_and_check_client_v2_switch(
        expect_switch_value=False, use_mobly_snippet_client_v2='false')

  def test_client_v2_switch_when_set_device_attribute_to_true(self):
    self._set_device_attribute_and_check_client_v2_switch(
        expect_switch_value=True, use_mobly_snippet_client_v2='true')

  def test_client_v2_switch_when_both_attribute_and_dimension_are_false(self):
    self._set_device_attribute_and_check_client_v2_switch(
        expect_switch_value=False,
        use_mobly_snippet_client_v2='false',
        dimensions={'use_mobly_snippet_client_v2': 'false'})

  def test_client_v2_switch_when_both_attribute_and_dimension_are_true(self):
    self._set_device_attribute_and_check_client_v2_switch(
        expect_switch_value=True,
        use_mobly_snippet_client_v2='true',
        dimensions={'use_mobly_snippet_client_v2': 'true'})

  def _set_device_attribute_and_check_client_v2_switch(self,
                                                       expect_switch_value,
                                                       **device_attributes):
    mock_device = mock.MagicMock(**device_attributes, spec=['log'])
    manager = snippet_management_service.SnippetManagementService(mock_device)
    self.assertEqual(expect_switch_value, manager._is_using_client_v2())


if __name__ == '__main__':
  unittest.main()
