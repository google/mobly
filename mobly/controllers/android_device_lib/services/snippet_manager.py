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
"""Module for the snippet service."""
from mobly.controllers.android_device_lib import errors
from mobly.controllers.android_device_lib import snippet_client
from mobly.controllers.android_device_lib.services import base_service
from mobly.controllers.android_device_lib.services import snippet_service


class Error(errors.ServiceError):
    """Root error type for logcat service."""
    SERVICE_TYPE = 'SnippetClientServiceManager'


class SnippetManager(base_service.BaseService):
    """Manager of snippet clients.

    The manager itself is a service so `AndroidDevice` can interact with it as
    a regular service. Underneath, this class manages individual snippet client
    which are also services.
    """

    def __init__(self, device, configs=None):
        """Constructor of the class.

        Args:
          device: the device object this service is associated with.
          config: optional configuration defined by the author of the service
              class.
        """
        del configs  # Unused param.
        self._device = device
        self._is_alive = False
        self._snippet_services = {}

    @property
    def is_alive(self):
        """True if any service is alive, False otherwise."""
        return any(
            [client.is_alive for client in self._snippet_services.values()])

    def get_snippet_client(self, name):
        if name in self._snippet_services:
            return self._snippet_services[name]

    def add_snippet_client(self, name, package):
        # Should not load snippet with the same name more than once.
        if name in self._snippet_services:
            raise Error(
                self,
                'Attribute "%s" is already registered with package "%s", it '
                'cannot be used again.' %
                (name, self._snippet_services[name].client.package))
        # Should not load the same snippet package more than once.
        for name, service in self._snippet_services.items():
            if package == service.client.package:
                raise Error(
                    self,
                    'Snippet package "%s" has already been loaded under name'
                    ' "%s".' % (package, name))
        config = snippet_service.Config(package=package)
        service = snippet_service.SnippetService(self._device, config)
        service.start()
        self._snippet_services[name] = service

    def remove_snippet_client(self, name):
        if name not in self._snippet_services:
            raise Error(self._device,
                        'No snippet registered with name "%s"' % name)
        service = self._snippet_services.pop(name)
        service.stop()

    def start(self, configs=None):
        """Starts all the snippet services under management."""
        del configs  # Not used.
        for service in self._snippet_services.values():
            if not service.is_alive:
                service.start()

    def stop(self):
        """Stops all the snippet services under management."""
        names = list(self._snippet_services.keys())
        for name in names:
            service = self._snippet_services.pop(name)
            if service.is_alive:
                service.stop()

    def pause(self):
        """Intentionally no-op."""

    def resume(self):
        for service in self._snippet_services.values():
            service.resume()

    def __getattr__(self, name):
        client = self.get_snippet_client(name)
        if client:
            return client
        raise Error(self._device,
                    'No snippet client is registered with name "%s".' % name)
