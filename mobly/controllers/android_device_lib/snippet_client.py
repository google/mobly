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
import socket

from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import jsonrpc_client_base

_LAUNCH_CMD = ('am instrument -e action start -e port {} '
               '{}/com.google.android.mobly.snippet.SnippetRunner')

_STOP_CMD = ('am instrument -w -e action stop '
             '{}/com.google.android.mobly.snippet.SnippetRunner')


class Error(Exception):
    pass


class SnippetClient(jsonrpc_client_base.JsonRpcClientBase):
    def __init__(self, package, port, adb_proxy):
        """Initialzies a SnippetClient.
  
        Args:
          package: (str) The package name of the apk where the snippets are
            defined.
          port: (int) The port at which to start the snippet client. Note that
            the same port will currently be used for both the device and host
            side of the connection.
            TODO(adorokhine): allocate a distinct free port for both sides of
            the connection; it is not safe in general to reuse the same one.
          adb_proxy: (adb.AdbProxy) The adb proxy to use to start the app.
        """
        super(SnippetClient, self).__init__(adb_proxy)
        self.app_name = package
        self._package = package
        self._port = port

    @property
    def package(self):
        return self._package

    def _do_start_app(self):
        """Overrides superclass."""
        cmd = _LAUNCH_CMD.format(self._port, self._package)
        # Use info here so people know exactly what's happening here, which is
        # helpful since they need to create their own instrumentations and
        # manifest.
        logging.info('Launching snippet apk with: %s', cmd)
        self._adb.shell(_LAUNCH_CMD.format(self._port, self._package))

    def stop_app(self):
        """Overrides superclass."""
        cmd = _STOP_CMD.format(self._package)
        logging.info('Stopping snippet apk with: %s', cmd)
        out = self._adb.shell(_STOP_CMD.format(self._package)).decode('utf-8')
        if 'OK (0 tests)' not in out:
            raise Error('Failed to stop existing apk. Unexpected output: %s' %
                        out)

    def _is_app_installed(self):
        """Overrides superclass."""
        try:
            out = self._adb.shell(
                'pm list instrumentation | grep ^instrumentation:%s/' %
                self._package).decode('utf-8')
            return bool(out)
        except adb.AdbError as e:
            if (e.ret_code == 1) and (not e.stdout) and (not e.stderr):
                return False
            raise

    def _is_app_running(self):
        """Overrides superclass."""
        # While instrumentation is running, 'ps' only shows the package of the
        # main apk. However, the main apk might be running for other reasons.
        # Instead of grepping the process tree, this is implemented by seeing if
        # our destination port is alive.
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            result = sock.connect_ex(('127.0.0.1', self._port))
            return result == 0
        finally:
            sock.close()
