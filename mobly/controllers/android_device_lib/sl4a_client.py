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
import logging
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
# TODO: This timeout is set high in order to allow for retries in start_app.
# Decrease it when the call to connect() has the option for a quicker timeout
# than the default _cmd() timeout.
_APP_START_WAIT_TIME = 10 * 60


class Error(Exception):
    pass


class AppStartError(Error):
    """Raised when sl4a is not able to be started."""


class Sl4aClient(jsonrpc_client_base.JsonRpcClientBase):
    """A client for interacting with SL4A using Mobly Snippet Lib.

    Extra public attributes:
    ed: Event dispatcher instance for this sl4a client.
    """

    def __init__(self, adb_proxy, log=logging.getLogger()):
        """Initializes an Sl4aClient.

        Args:
            self._adb: (adb.AdbProxy) The adb proxy to use to start the app.
            log: (logging.Logger) logger to which to send log messages.
        """
        super(Sl4aClient, self).__init__(app_name=_APP_NAME, log=log)
        self.ed = None
        self._adb = adb_proxy

    def start_app(self):
        """Overrides superclass."""
        # Check that sl4a is installed
        out = self._adb.shell('pm list package')
        if not utils.grep('com.googlecode.android_scripting', out):
            raise AppStartError('%s is not installed on %s' %
                                (_APP_NAME, self._adb.serial))

        # sl4a has problems connecting after disconnection, so kill the apk and
        # try connecting again.
        try:
            self.stop_app()
        except Exception as e:
            self.log.warning(e)

        # Launch the app
        self.host_port = utils.get_available_host_port()
        self.device_port = _DEVICE_SIDE_PORT
        self._adb.forward(
            ['tcp:%d' % self.host_port, 'tcp:%d' % self.device_port])
        self._adb.shell(_LAUNCH_CMD % self.device_port)

        # Connect with retry
        start_time = time.time()
        expiration_time = start_time + _APP_START_WAIT_TIME
        started = False
        while time.time() < expiration_time:
            self.log.debug('Attempting to start %s.', self.app_name)
            try:
                self.connect()
                started = True
                break
            except:
                self.log.debug(
                    '%s is not yet running, retrying',
                    self.app_name,
                    exc_info=True)
            time.sleep(1)
        if not started:
            raise jsonrpc_client_base.AppStartError(
                '%s failed to start on %s.' % (self.app_name, self._adb.serial))

        # Start an EventDispatcher for the current sl4a session
        event_client = Sl4aClient(self._adb, self.log)
        event_client.host_port = self.host_port
        event_client.connect(
            uid=self.uid, cmd=jsonrpc_client_base.JsonRpcCommand.CONTINUE)
        self.ed = event_dispatcher.EventDispatcher(event_client)
        self.ed.start()

    def stop_app(self):
        """Overrides superclass."""
        try:
            if self._conn:
                # Be polite; let the dest know we're shutting down.
                try:
                    self.closeSl4aSession()
                except:
                    self.log.exception('Failed to gracefully shut down %s.',
                                       self.app_name)

                # Close the socket connection.
                self.disconnect()

                # Close Event Dispatcher
                if self.ed:
                    try:
                        self.ed.clean_up()
                    except:
                        self.log.exception(
                            'Failed to shutdown sl4a event dispatcher.')
                    self.ed = None

            # Terminate the app
            self._adb.shell('am force-stop com.googlecode.android_scripting')
        finally:
            # Always clean up the adb port
            if self.host_port:
                self._adb.forward(['--remove', 'tcp:%d' % self.host_port])
