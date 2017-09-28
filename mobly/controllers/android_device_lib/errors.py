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

# Module for errors thrown from AndroidDevice object.

from mobly import signals


class Error(signals.ControllerError):
    pass


class DeviceError(Error):
    """Raised for errors specific to an AndroidDevice object."""
    def __init__(self, ad, msg):
        new_msg = '%s %s' % (repr(ad), msg)
        super(DeviceError, self).__init__(new_msg)
