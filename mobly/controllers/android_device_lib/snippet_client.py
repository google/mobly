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
"""JSON RPC interface to Mobly Snippet Lib."""
import logging

from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import jsonrpc_client_base

_LAUNCH_CMD = ('am instrument -e action start -e port {} '
               '{}/com.google.android.mobly.snippet.SnippetRunner')

_STOP_CMD = ('am instrument -w -e action stop '
             '{}/com.google.android.mobly.snippet.SnippetRunner')


class Error(Exception):
    pass


class SnippetClient(jsonrpc_client_base.JsonRpcClientBase):
    """A client for interacting with snippet APKs using Mobly Snippet Lib.

    See superclass documentation for a list of public attributes.
    """

    def __init__(self, package, host_port, adb_proxy):
        """Initializes a SnippetClient.
  
        Args:
            package: (str) The package name of the apk where the snippets are
                     defined.
            host_port: (int) The port at which to start the snippet client. Note
                       that the same port will currently be used for both the
                      device and host side of the connection.
            adb_proxy: (adb.AdbProxy) The adb proxy to use to start the app.
        """
        # TODO(adorokhine): Don't assume that a free host-side port is free on
        # the device as well. Both sides should allocate a unique port.
        super(SnippetClient, self).__init__(
            host_port=host_port, device_port=host_port, app_name=package,
            adb_proxy=adb_proxy)
        self.package = package

    def _do_start_app(self):
        """Overrides superclass."""
        cmd = _LAUNCH_CMD.format(self.device_port, self.package)
        # Use info here so people know exactly what's happening here, which is
        # helpful since they need to create their own instrumentations and
        # manifest.
        logging.info('Launching snippet apk with: %s', cmd)
        self._adb.shell(cmd)

    def stop_app(self):
        """Overrides superclass."""
        cmd = _STOP_CMD.format(self.package)
        logging.info('Stopping snippet apk with: %s', cmd)
        out = self._adb.shell(_STOP_CMD.format(self.package)).decode('utf-8')
        if 'OK (0 tests)' not in out:
            raise Error('Failed to stop existing apk. Unexpected output: %s' %
                        out)

    def _is_app_installed(self):
        """Overrides superclass."""
        try:
            out = self._adb.shell(
                'pm list instrumentation | grep ^instrumentation:%s/' %
                self.package).decode('utf-8')
            return bool(out)
        except adb.AdbError as e:
            if (e.ret_code == 1) and (not e.stdout) and (not e.stderr):
                return False
            raise
