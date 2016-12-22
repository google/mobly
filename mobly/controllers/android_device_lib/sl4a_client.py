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
    def __init__(self, adb_proxy):
        super(Sl4aClient, self).__init__(adb_proxy)
        self.app_name = 'SL4A'

    def _do_start_app(self):
        """Overrides superclass."""
        self._adb.shell(_LAUNCH_CMD.format(DEVICE_SIDE_PORT))

    def stop_app(self):
        """Overrides superclass."""
        self._adb.shell('am force-stop com.googlecode.android_scripting')

    def _is_app_installed(self):
        """Overrides superclass."""
        try:
            out = self._adb.shell("pm path com.googlecode.android_scripting"
                                  ).decode('utf-8').strip()
            return bool(out)
        except adb.AdbError as e:
            if (e.ret_code == 1) and (not e.stdout) and (not e.stderr):
                return False
            raise

    def _is_app_running(self):
        """Overrides superclass."""
        # Grep for process with a preceding S which means it is truly started.
        try:
            out = self._adb.shell(
                'ps | grep "S com.googlecode.android_scripting"').decode(
                    'utf-8').strip()
            return bool(out)
        except adb.AdbError as e:
            if (e.ret_code == 1) and (not e.stdout) and (not e.stderr):
                return False
            raise
