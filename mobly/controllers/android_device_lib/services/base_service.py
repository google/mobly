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
"""Module for the BaseService."""


class BaseService(object):
    """Base class of a Mobly AndroidDevice service.

    This class defines the interface for Mobly's AndroidDevice service.
    """

    def __init__(self, device, configs=None):
        """Constructor of the class.

        Args:
          device: the device object this service is associated with.
          config: optional configuration defined by the author of the service
              class.
        """
        self._device = device
        self._configs = configs

    @property
    def is_alive(self):
        """True if the service is active; False otherwise."""
        raise NotImplementedError('"is_alive" is a required service property.')

    def start(self, configs=None):
        """Starts the service.

        Args:
            configs: optional configs to be passed for startup.
        """
        raise NotImplementedError('"start" is a required service method.')

    def stop(self):
        """Stops the service and cleans up all resources.

        This method should handle any error and not throw.
        """
        raise NotImplementedError('"stop" is a required service method.')

    def pause(self):
        """Pauses a service temporarily.

        For when the Python service object needs to temporarily lose connection
        to the device without shutting down the service running on the actual
        device.

        This is relevant when a service needs to maintain a constant connection
        to the device and the connection is lost if USB connection to the
        device is disrupted.

        E.g. a services that utilizes a socket connection over adb port
        forwarding would need to implement this for the situation where the USB
        connection to the device will be temporarily cut, but the device is not
        rebooted.

        For more context, see:
        `mobly.controllers.android_device.AndroidDevice.handle_usb_disconnect`

        If not implemented, we assume the service is not sensitive to device
        disconnect, and `stop` will be called by default.
        """
        self.stop()

    def resume(self, config=None):
        """Resumes a paused service.

        Same context as the `pause` method. This should resume the service
        after the connection to the device has been re-established.

        If not implemented, we assume the service is not sensitive to device
        disconnect, and `start` will be called by default.
        """
        self.start(config)
