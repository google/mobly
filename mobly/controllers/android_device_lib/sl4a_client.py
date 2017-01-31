#/usr/bin/env python3.4
#
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

from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import jsonrpc_client_base

DEVICE_SIDE_PORT = 8080

_LAUNCH_CMD = (
    "am start -a com.googlecode.android_scripting.action.LAUNCH_SERVER "
    "--ei com.googlecode.android_scripting.extra.USE_SERVICE_PORT {} "
    "com.googlecode.android_scripting/.activity.ScriptingLayerServiceLauncher")


class Sl4aClient(jsonrpc_client_base.JsonRpcClientBase):
    """A client for interacting with SL4A using Mobly Snippet Lib.

    See superclass documentation for a list of public attributes.
    """

    def __init__(self, host_port, adb_proxy):
        """Initializes an Sl4aClient.

        Args:
            host_port: (int) The host port of this RPC client.
            adb_proxy: (adb.AdbProxy) The adb proxy to use to start the app.
        """
        super(Sl4aClient, self).__init__(
            host_port=host_port, device_port=DEVICE_SIDE_PORT, app_name='SL4A',
            adb_proxy=adb_proxy)

    def _do_start_app(self):
        """Overrides superclass."""
        self._adb.shell(_LAUNCH_CMD.format(self.device_port))

    def stop_app(self):
        """Overrides superclass."""
        self._adb.shell('am force-stop com.googlecode.android_scripting')

    def check_app_installed(self):
        """Overrides superclass."""
        if not self._adb_grep_wrapper(
            "pm list package | grep com.googlecode.android_scripting"):
            raise jsonrpc_client_base.AppStartError(
                '%s is not installed on %s' % (
                self.app_name, self._adb.getprop('ro.boot.serialno')))
