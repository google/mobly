# Copyright 2016 Google Inc.
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
"""JSON RPC interface to android scripting engine."""

import time

from mobly import utils
from mobly.controllers.android_device_lib import event_dispatcher
from mobly.controllers.android_device_lib import jsonrpc_client_base

_APP_NAME = 'SL4A'
_DEVICE_SIDE_PORT = 8080
_LAUNCH_CMD = (
    'am start -a com.googlecode.android_scripting.action.LAUNCH_SERVER '
    '--ei com.googlecode.android_scripting.extra.USE_SERVICE_PORT %s '
    'com.googlecode.android_scripting/.activity.ScriptingLayerServiceLauncher')
# Maximum time to wait for the app to start on the device (10 minutes).
# TODO: This timeout is set high in order to allow for retries in
# start_app_and_connect. Decrease it when the call to connect() has the option
# for a quicker timeout than the default _cmd() timeout.
# TODO: Evaluate whether the high timeout still makes sense for sl4a. It was
# designed for user snippets which could be very slow to start depending on the
# size of the snippet and main apps. sl4a can probably use a much smaller value.
_APP_START_WAIT_TIME = 2 * 60


class Sl4aClient(jsonrpc_client_base.JsonRpcClientBase):
  """A client for interacting with SL4A using Mobly Snippet Lib.

  Extra public attributes:
  ed: Event dispatcher instance for this sl4a client.
  """

  def __init__(self, ad):
    """Initializes an Sl4aClient.

    Args:
      ad: AndroidDevice object.
    """
    super().__init__(app_name=_APP_NAME, ad=ad)
    self._ad = ad
    self.ed = None
    self._adb = ad.adb

  def start_app_and_connect(self):
    """Overrides superclass."""
    # Check that sl4a is installed
    out = self._adb.shell('pm list package')
    if not utils.grep('com.googlecode.android_scripting', out):
      raise jsonrpc_client_base.AppStartError(
          self._ad, '%s is not installed on %s' % (_APP_NAME, self._adb.serial))
    self.disable_hidden_api_blacklist()

    # sl4a has problems connecting after disconnection, so kill the apk and
    # try connecting again.
    try:
      self.stop_app()
    except Exception as e:
      self.log.warning(e)

    # Launch the app
    self.device_port = _DEVICE_SIDE_PORT
    self._adb.shell(_LAUNCH_CMD % self.device_port)

    # Try to start the connection (not restore the connectivity).
    # The function name restore_app_connection is used here is for the
    # purpose of reusing the same code as it does when restoring the
    # connection. And we do not want to come up with another function
    # name to complicate the API. Change the name if necessary.
    self.restore_app_connection()

  def restore_app_connection(self, port=None):
    """Restores the sl4a after device got disconnected.

    Instead of creating new instance of the client:
      - Uses the given port (or find a new available host_port if none is
      given).
      - Tries to connect to remote server with selected port.

    Args:
      port: If given, this is the host port from which to connect to remote
        device port. If not provided, find a new available port as host
        port.

    Raises:
      AppRestoreConnectionError: When the app was not able to be started.
    """
    self.host_port = port or utils.get_available_host_port()
    self._retry_connect()
    self.ed = self._start_event_client()

  def stop_app(self):
    """Overrides superclass."""
    try:
      if self._conn:
        # Be polite; let the dest know we're shutting down.
        try:
          self.closeSl4aSession()
        except Exception:
          self.log.exception('Failed to gracefully shut down %s.',
                             self.app_name)

        # Close the socket connection.
        self.disconnect()
        self.stop_event_dispatcher()

      # Terminate the app
      self._adb.shell('am force-stop com.googlecode.android_scripting')
    finally:
      # Always clean up the adb port
      self.clear_host_port()

  def stop_event_dispatcher(self):
    # Close Event Dispatcher
    if self.ed:
      try:
        self.ed.clean_up()
      except Exception:
        self.log.exception('Failed to shutdown sl4a event dispatcher.')
      self.ed = None

  def _retry_connect(self):
    self._adb.forward(['tcp:%d' % self.host_port, 'tcp:%d' % self.device_port])
    expiration_time = time.perf_counter() + _APP_START_WAIT_TIME
    started = False
    while time.perf_counter() < expiration_time:
      self.log.debug('Attempting to start %s.', self.app_name)
      try:
        self.connect()
        started = True
        break
      except Exception:
        self.log.debug('%s is not yet running, retrying',
                       self.app_name,
                       exc_info=True)
      time.sleep(1)
    if not started:
      raise jsonrpc_client_base.AppRestoreConnectionError(
          self._ad, '%s failed to connect for %s at host port %s, '
          'device port %s' %
          (self.app_name, self._adb.serial, self.host_port, self.device_port))

  def _start_event_client(self):
    # Start an EventDispatcher for the current sl4a session
    event_client = Sl4aClient(self._ad)
    event_client.host_port = self.host_port
    event_client.device_port = self.device_port
    event_client.connect(uid=self.uid,
                         cmd=jsonrpc_client_base.JsonRpcCommand.CONTINUE)
    ed = event_dispatcher.EventDispatcher(event_client)
    ed.start()
    return ed
