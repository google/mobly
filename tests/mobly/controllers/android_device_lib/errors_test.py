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
"""Unit tests for Mobly android_device_lib.errors."""

import mock
import unittest

from mobly.controllers.android_device_lib import errors


class ErrorsTest(unittest.TestCase):

  def test_device_error(self):
    device = mock.MagicMock()
    device.__repr__ = lambda _: '[MockDevice]'
    exception = errors.DeviceError(device, 'Some error message.')
    self.assertEqual(str(exception), '[MockDevice] Some error message.')

  def test_service_error(self):
    device = mock.MagicMock()
    device.__repr__ = lambda _: '[MockDevice]'
    exception = errors.ServiceError(device, 'Some error message.')
    self.assertEqual(str(exception),
                     '[MockDevice]::Service<None> Some error message.')

  def test_subclass_service_error(self):

    class Error(errors.ServiceError):
      SERVICE_TYPE = 'SomeType'

    device = mock.MagicMock()
    device.__repr__ = lambda _: '[MockDevice]'
    exception = Error(device, 'Some error message.')
    self.assertEqual(str(exception),
                     '[MockDevice]::Service<SomeType> Some error message.')


if __name__ == '__main__':
  unittest.main()
