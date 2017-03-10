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
import re

from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import jsonrpc_client_base

_INSTRUMENTATION_RUNNER_PACKAGE = 'com.google.android.mobly.snippet.SnippetRunner'

_LAUNCH_CMD = 'am instrument -e action start -e port %s %s/' + _INSTRUMENTATION_RUNNER_PACKAGE

_STOP_CMD = 'am instrument -w -e action stop %s/' + _INSTRUMENTATION_RUNNER_PACKAGE


class Error(Exception):
    pass


class SnippetClient(jsonrpc_client_base.JsonRpcClientBase):
    """A client for interacting with snippet APKs using Mobly Snippet Lib.

    See superclass documentation for a list of public attributes.
    """

    def __init__(self, package, host_port, adb_proxy, log=logging.getLogger()):
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
            host_port=host_port,
            device_port=host_port,
            app_name=package,
            adb_proxy=adb_proxy)
        self.package = package
        self.log = log
        self._serial = self._adb.serial

    def _do_start_app(self):
        """Overrides superclass."""
        cmd = _LAUNCH_CMD % (self.device_port, self.package)
        # Use info here so people know exactly what's happening here, which is
        # helpful since they need to create their own instrumentations and
        # manifest.
        self.log.info('Launching snippet apk %s', self.package)
        self._adb.shell(cmd)

    def stop_app(self):
        """Overrides superclass."""
        cmd = _STOP_CMD % self.package
        self.log.debug('Stopping snippet apk %s', self.package)
        out = self._adb.shell(_STOP_CMD % self.package).decode('utf-8')
        if 'OK (0 tests)' not in out:
            raise Error('Failed to stop existing apk. Unexpected output: %s' %
                        out)

    def check_app_installed(self):
        """Overrides superclass."""
        # Check that the Mobly Snippet app is installed.
        if not self._adb_grep_wrapper(
                r'pm list package | tr -d "\r" | grep "^package:%s$"' %
                self.package):
            raise jsonrpc_client_base.AppStartError(
                '%s is not installed on %s' % (self.package, self._serial))
        # Check that the app is instrumented.
        out = self._adb_grep_wrapper(
            r'pm list instrumentation | tr -d "\r" | grep ^instrumentation:%s/%s'
            % (self.package, _INSTRUMENTATION_RUNNER_PACKAGE))
        if not out:
            raise jsonrpc_client_base.AppStartError(
                '%s is installed on %s, but it is not instrumented.' %
                (self.package, self._serial))
        match = re.search(r'^instrumentation:(.*)\/(.*) \(target=(.*)\)$', out)
        target_name = match.group(3)
        # Check that the instrumentation target is installed if it's not the
        # same as the snippet package.
        if target_name != self.package:
            out = self._adb_grep_wrapper(
                r'pm list package | tr -d "\r" | grep ^package:%s$' %
                target_name)
            if not out:
                raise jsonrpc_client_base.AppStartError(
                    'Instrumentation target %s is not installed on %s' %
                    (target_name, self._serial))

    def _start_event_client(self):
        event_client = SnippetClient(
            package=self.package,
            host_port=self.host_port,
            adb_proxy=self._adb,
            log=self.log)
        event_client.connect(self.uid,
                             jsonrpc_client_base.JsonRpcCommand.CONTINUE)
        return event_client
