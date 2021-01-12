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
"""Module for the Sl4aService."""

from mobly.controllers.android_device_lib import sl4a_client
from mobly.controllers.android_device_lib.services import base_service


class Sl4aService(base_service.BaseService):
  """Service for managing sl4a's client.

  Direct calls on the service object will forwarded to the client object as
  syntactic sugar. So `Sl4aService.doFoo()` is equivalent to
  `Sl4aClient.doFoo()`.
  """

  def __init__(self, device, configs=None):
    del configs  # Never used.
    self._ad = device
    self._sl4a_client = None

  @property
  def is_alive(self):
    return self._sl4a_client is not None

  def start(self):
    self._sl4a_client = sl4a_client.Sl4aClient(ad=self._ad)
    self._sl4a_client.start_app_and_connect()

  def stop(self):
    if self.is_alive:
      self._sl4a_client.stop_app()
      self._sl4a_client = None

  def pause(self):
    # Need to stop dispatcher because it continuously polls the device.
    # It's not necessary to stop the sl4a client.
    self._sl4a_client.stop_event_dispatcher()
    self._sl4a_client.clear_host_port()

  def resume(self):
    # Restore sl4a if needed.
    self._sl4a_client.restore_app_connection()

  def __getattr__(self, name):
    """Forwards the getattr calls to the client itself."""
    if self._sl4a_client:
      return getattr(self._sl4a_client, name)
    return self.__getattribute__(name)
