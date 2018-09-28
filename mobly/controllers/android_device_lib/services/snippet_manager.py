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


class Error(errors.ServiceError):
    """Root error type for snippet service."""
    SERVICE_TYPE = 'SnippetService'


class SnippetManager(base_service.BaseService):
    """Manager of snippet clients."""

    def __init__(self, device, configs=None):
        del configs  # Unused param.
        self._device = device
        self._is_alive = False
        self._snippet_clients = {}

    @property
    def is_alive(self):
        """True if any client is running, False otherwise."""
        return any(
            [client.is_alive for client in self._snippet_clients.values()])

    def get_snippet_client(self, name):
        if name in self._snippet_clients:
            return self._snippet_clients[name]

    def add_snippet_client(self, name, package):
        # Should not load snippet with the same name more than once.
        if name in self._snippet_clients:
            raise Error(
                self,
                'Attribute "%s" is already registered with package "%s", it '
                'cannot be used again.' %
                (name, self._snippet_clients[name].client.package))
        # Should not load the same snippet package more than once.
        for name, client in self._snippet_clients.items():
            if package == client.package:
                raise Error(
                    self,
                    'Snippet package "%s" has already been loaded under name'
                    ' "%s".' % (package, name))
        client = snippet_client.SnippetClient(package=package, ad=self._device)
        client.start_app_and_connect()
        self._snippet_clients[name] = client

    def remove_snippet_client(self, name):
        if name not in self._snippet_clients:
            raise Error(self._device,
                        'No snippet registered with name "%s"' % name)
        client = self._snippet_clients.pop(name)
        client.stop_app()

    def start(self, configs=None):
        """Starts all the snippet services under management."""
        del configs  # Not used.
        for client in self._snippet_clients.values():
            if not client.is_running:
                client.start_app_and_connect()

    def stop(self):
        """Stops all the snippet services under management."""
        for client in self._snippet_clients.values():
            if not client.is_running:
                client.stop_app()

    def pause(self):
        """Intentionally no-op."""

    def resume(self):
        for client in self._snippet_clients.values():
            client.restore_app_connection()

    def __getattr__(self, name):
        client = self.get_snippet_client(name)
        if client:
            return client
        raise Error(self._device,
                    'No snippet client is registered with name "%s".' % name)
