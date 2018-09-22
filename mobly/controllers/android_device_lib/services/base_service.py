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

    All AndroidDevice services should inherit from this class.
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
        """
        """
        self.stop()

    def resume(self, config=None):
        """
        """
        self.start(config)
