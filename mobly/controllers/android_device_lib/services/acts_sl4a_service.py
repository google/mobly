# Copyright 2021 Google Inc.
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

"""Module for the ActsSl4aService."""

from mobly.controllers.android_device_lib.acts_sl4a_lib import sl4a_manager
from mobly.controllers.android_device_lib.services import base_service


class ActsSl4aService(base_service.BaseService):
  """Service that wraps the ACTS sl4a manager.

  Direct calls on the service object will forwarded to the main sl4a client
  object as syntactic sugar. So `ActsSl4aService.doFoo()` is equivalent to
  `RpcClient.doFoo()`.
  """

  def __init__(self, device, *_):
    self._ad = device
    self._sl4a_manager = sl4a_manager.create_sl4a_manager(self._ad.adb)

  @property
  def sl4a_manager(self):
    """Returns the SL4A manager instance."""
    return self._sl4a_manager

  @property
  def sl4a_session(self):
    """Returns the primary (first created) session of the SL4A manager, or
    None if no session exists.
    """
    if not self._sl4a_manager.sessions:
      return None
    session_id = sorted(self._sl4a_manager.sessions.keys())[0]
    return self._sl4a_manager.sessions[session_id]

  @property
  def ed(self):
    """Returns the event dispatcher of the primary SL4A session."""
    if not self.sl4a_session:
      return None
    return self.sl4a_session.get_event_dispatcher()

  @property
  def is_alive(self):
    """True is there is at least one alive session."""
    return any(session.is_alive for session in
               self._sl4a_manager.sessions.values())

  def start(self):
    session = self._sl4a_manager.create_session()
    session.get_event_dispatcher().start()

  def stop(self):
    self._sl4a_manager.terminate_all_sessions()
    self._sl4a_manager.stop_service()

  def __getattr__(self, name):
    """Forwards the getattr calls to the client itself."""
    if self.sl4a_session:
      return getattr(self.sl4a_session.rpc_client, name)
    return self.__getattribute__(name)
