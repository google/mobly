# Copyright 2022 Google Inc.
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
"""Module for errors thrown from snippet client objects."""
# TODO(mhaoli): Package `mobly.snippet` should not import errors from
# android_device_lib. However android_device_lib.DeviceError is the base error
# for the errors thrown from Android snippet clients and device controllers.
# We should resolve this legacy problem.
from mobly.controllers.android_device_lib import errors


class ServerDiedError(errors.DeviceError):
  """Raised if snippet server died before all tests finish."""
