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
"""Module for the snippet management service."""
from mobly.controllers.android_device_lib import errors
from mobly.controllers.android_device_lib import snippet_client
from mobly.controllers.android_device_lib import snippet_client_v2
from mobly.controllers.android_device_lib.services import base_service

MISSING_SNIPPET_CLIENT_MSG = 'No snippet client is registered with name "%s".'

# This config is transient and we will remove it after completing the migration
# from v1 to v2.
_CLIENT_V2_CONFIG_KEY = 'use_mobly_snippet_client_v2'


class Error(errors.ServiceError):
  """Root error type for snippet management service."""
  SERVICE_TYPE = 'SnippetManagementService'


class SnippetManagementService(base_service.BaseService):
  """Management service of snippet clients.

  This service manages all the snippet clients associated with an Android
  device.
  """

  def __init__(self, device, configs=None):
    del configs  # Unused param.
    self._device = device
    self._is_alive = False
    self._snippet_clients = {}
    super().__init__(device)
    self._use_client_v2_switch = None

  # TODO(mhaoli): The client v2 switch is transient, we will remove it after we
  # complete the migration from v1 to v2.
  def _is_using_client_v2(self):
    """Is this service using snippet client V2.

    Do not call this function in the constructor, as this function depends on
    the device configuration and the device object will load its configuration
    right after constructing the services.

    NOTE: This is a transient function when we are migrating the snippet client
    from v1 to v2. It will be removed after the migration is completed.

    Returns:
      A bool for whether this service is using snippet client V2.
    """
    if self._use_client_v2_switch is None:
      device_dimensions = getattr(self._device, 'dimensions', {})
      switch_from_dimension = (device_dimensions.get(_CLIENT_V2_CONFIG_KEY,
                                                     'true').lower() == 'true')

      switch_from_attribute = (getattr(self._device, _CLIENT_V2_CONFIG_KEY,
                                       'true').lower() == 'true')

      self._use_client_v2_switch = (switch_from_dimension and
                                    switch_from_attribute)
    return self._use_client_v2_switch

  @property
  def is_alive(self):
    """True if any client is running, False otherwise."""
    return any([client.is_alive for client in self._snippet_clients.values()])

  def get_snippet_client(self, name):
    """Gets the snippet client managed under a given name.

    Args:
      name: string, the name of the snippet client under management.

    Returns:
      SnippetClient.
    """
    if name in self._snippet_clients:
      return self._snippet_clients[name]

  def add_snippet_client(self, name, package):
    """Adds a snippet client to the management.

    Args:
      name: string, the attribute name to which to attach the snippet
        client. E.g. `name='maps'` attaches the snippet client to
        `ad.maps`.
      package: string, the package name of the snippet apk to connect to.

    Raises:
      Error, if a duplicated name or package is passed in.
    """
    # Should not load snippet with the same name more than once.
    if name in self._snippet_clients:
      raise Error(
          self, 'Name "%s" is already registered with package "%s", it cannot '
          'be used again.' % (name, self._snippet_clients[name].client.package))
    # Should not load the same snippet package more than once.
    for snippet_name, client in self._snippet_clients.items():
      if package == client.package:
        raise Error(
            self, 'Snippet package "%s" has already been loaded under name'
            ' "%s".' % (package, snippet_name))

    if self._is_using_client_v2():
      client = snippet_client_v2.SnippetClientV2(package=package,
                                                 ad=self._device)
      client.initialize()
    else:
      client = snippet_client.SnippetClient(package=package, ad=self._device)
      client.start_app_and_connect()
    self._snippet_clients[name] = client

  def remove_snippet_client(self, name):
    """Removes a snippet client from management.

    Args:
      name: string, the name of the snippet client to remove.

    Raises:
      Error: if no snippet client is managed under the specified name.
    """
    if name not in self._snippet_clients:
      raise Error(self._device, MISSING_SNIPPET_CLIENT_MSG % name)
    client = self._snippet_clients.pop(name)
    if self._is_using_client_v2():
      client.stop()
    else:
      client.stop_app()

  def start(self):
    """Starts all the snippet clients under management."""
    for client in self._snippet_clients.values():
      if not client.is_alive:
        self._device.log.debug('Starting SnippetClient<%s>.', client.package)
        if self._is_using_client_v2():
          client.initialize()
        else:
          client.start_app_and_connect()
      else:
        self._device.log.debug(
            'Not startng SnippetClient<%s> because it is already alive.',
            client.package)

  def stop(self):
    """Stops all the snippet clients under management."""
    for client in self._snippet_clients.values():
      if client.is_alive:
        self._device.log.debug('Stopping SnippetClient<%s>.', client.package)
        if self._is_using_client_v2():
          client.stop()
        else:
          client.stop_app()
      else:
        self._device.log.debug(
            'Not stopping SnippetClient<%s> because it is not alive.',
            client.package)

  def pause(self):
    """Pauses all the snippet clients under management.

    This clears the host port of a client because a new port will be
    allocated in `resume`.
    """
    for client in self._snippet_clients.values():
      self._device.log.debug('Pausing SnippetClient<%s>.', client.package)
      if self._is_using_client_v2():
        client.close_connection()
      else:
        client.disconnect()

  def resume(self):
    """Resumes all paused snippet clients."""
    for client in self._snippet_clients.values():
      if not client.is_alive:
        self._device.log.debug('Resuming SnippetClient<%s>.', client.package)
        if self._is_using_client_v2():
          client.restore_server_connection()
        else:
          client.restore_app_connection()
      else:
        self._device.log.debug('Not resuming SnippetClient<%s>.',
                               client.package)

  def __getattr__(self, name):
    client = self.get_snippet_client(name)
    if client:
      return client
    return self.__getattribute__(name)
