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
import time

from mobly import utils
from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import jsonrpc_client_base

_INSTRUMENTATION_RUNNER_PACKAGE = (
    'com.google.android.mobly.snippet.SnippetRunner')

_LAUNCH_CMD_V0 = ('am instrument -w -e action start -e port %s %s/' +
                  _INSTRUMENTATION_RUNNER_PACKAGE)

_LAUNCH_CMD_V1 = (
    'am instrument -w -e action start %s/' + _INSTRUMENTATION_RUNNER_PACKAGE)

_STOP_CMD = (
    'am instrument -w -e action stop %s/' + _INSTRUMENTATION_RUNNER_PACKAGE)

# Maximum time to wait for the app to start on the device (10 minutes).
# TODO: This timeout is set high in order to allow for retries in start_app.
# Decrease it when the call to connect() has the option for a quicker timeout
# than the default _cmd() timeout.
_APP_START_WAIT_TIME_V0 = 10 * 60


class Error(Exception):
    pass


class ProtocolVersionError(Error):
    """Raised when the protocol reported by the snippet is unknown."""


class SnippetClient(jsonrpc_client_base.JsonRpcClientBase):
    """A client for interacting with snippet APKs using Mobly Snippet Lib.

    See superclass documentation for a list of public attributes.
    """

    def __init__(self, package, adb_proxy, log=logging.getLogger()):
        """Initializes a SnippetClient.
  
        Args:
            package: (str) The package name of the apk where the snippets are
                     defined.
            adb_proxy: (adb.AdbProxy) Adb proxy for running adb commands.
            log: (logging.Logger) logger to which to send log messages.
        """
        super(SnippetClient, self).__init__(app_name=package, log=log)
        self.package = package
        self._adb = adb_proxy
        self._proc = None

    def start_app(self):
        """Overrides superclass. Launches a snippet app and connects to it."""
        self._check_app_installed()

        # Try launching the app with the v1 protocol. If that fails, fall back
        # to v0 for compatibility. Use info here so people know exactly what's
        # happening here, which is helpful since they need to create their own
        # instrumentations and manifest.
        self.log.info('Launching snippet apk %s with protocol v1',
                      self.package)
        cmd = _LAUNCH_CMD_V1 % self.package
        start_time = time.time()
        self._proc = self._do_start_app(cmd)

        # "Instrumentation crashed" could be due to several reasons, eg
        # exception thrown during startup or just a launch protocol 0 snippet
        # dying because it needs the port flag. Sadly we have no way to tell so
        # just warn and retry as v0. TODO(adorokhine): remove v0 compatibility
        # path in next release.
        line = self._proc.stdout.readline().rstrip()
        if line == 'INSTRUMENTATION_RESULT: shortMsg=Process crashed.':
            self.log.warning('Snippet %s crashed on startup. This might be an '
                             'actual error or a snippet using deprecated v0 '
                             'start protocol. Retrying as a v0 snippet.',
                             self.package)
            self.host_port = utils.get_available_host_port()
            # Reuse the host port as the device port in v0 snippet. This isn't
            # safe in general, but the protocol is deprecated.
            cmd = _LAUNCH_CMD_V0 % (self.host_port, self.package)
            self._proc = self._do_start_app(cmd)
            self._connect_to_v0()
        else:
            # Check protocol version and get the device port
            match = re.match('^SNIPPET START, PROTOCOL ([0-9]+)$', line)
            if not match or match.group(1) != '1':
                raise ProtocolVersionError(line)
            self._connect_to_v1()
        self.log.debug('Snippet %s started after %.1fs on host port %s',
                       self.package, time.time() - start_time, self.host_port)

    def stop_app(self):
        # Kill the pending 'adb shell am instrument -w' process if there is one.
        # Although killing the snippet apk would abort this process anyway, we
        # want to call stop_standing_subprocess() to perform a health check,
        # print the failure stack trace if there was any, and reap it from the
        # process table.
        self.log.debug('Stopping snippet apk %s', self.package)
        try:
            # Close the socket connection.
            self.disconnect()
            if self._proc:
                utils.stop_standing_subprocess(self._proc)
            out = self._adb.shell(_STOP_CMD % self.package).decode('utf-8')
            if 'OK (0 tests)' not in out:
                raise Error('Failed to stop existing apk. Unexpected '
                            'output: %s' % out)
        finally:
            # Always clean up the adb port
            if self.host_port:
                self._adb.forward(['--remove', 'tcp:%d' % self.host_port])

    def _start_event_client(self):
        """Overrides superclass."""
        event_client = SnippetClient(
            package=self.package,
            host_port=self.host_port,
            adb_proxy=self._adb,
            log=self.log)
        event_client.connect(self.uid,
                             jsonrpc_client_base.JsonRpcCommand.CONTINUE)
        return event_client

    def _check_app_installed(self):
        # Check that the Mobly Snippet app is installed.
        out = self._adb.shell('pm list package')
        if not utils.grep('^package:%s$' % self.package, out):
            raise jsonrpc_client_base.AppStartError(
                '%s is not installed on %s' % (self.package, self._adb.serial))
        # Check that the app is instrumented.
        out = self._adb.shell('pm list instrumentation')
        matched_out = utils.grep('^instrumentation:%s/%s' %
                                 (self.package,
                                  _INSTRUMENTATION_RUNNER_PACKAGE), out)
        if not matched_out:
            raise jsonrpc_client_base.AppStartError(
                '%s is installed on %s, but it is not instrumented.' %
                (self.package, self._adb.serial))
        match = re.search('^instrumentation:(.*)\/(.*) \(target=(.*)\)$',
                          matched_out[0])
        target_name = match.group(3)
        # Check that the instrumentation target is installed if it's not the
        # same as the snippet package.
        if target_name != self.package:
            out = self._adb.shell('pm list package')
            if not utils.grep('^package:%s$' % target_name, out):
                raise jsonrpc_client_base.AppStartError(
                    'Instrumentation target %s is not installed on %s' %
                    (target_name, self._adb.serial))

    def _do_start_app(self, launch_cmd):
        adb_cmd = [adb.ADB]
        if self._adb.serial:
            adb_cmd += ['-s', self._adb.serial]
        adb_cmd += ['shell', launch_cmd]
        return utils.start_standing_subprocess(adb_cmd, shell=False)

    def _connect_to_v0(self):
        """TODO: Remove this after v0 snippet support is dropped."""
        self.device_port = self.host_port
        self._adb.forward(
            ['tcp:%d' % self.host_port, 'tcp:%d' % self.device_port])
        start_time = time.time()
        expiration_time = start_time + _APP_START_WAIT_TIME_V0
        while time.time() < expiration_time:
            self.log.debug('Attempting to start %s.', self.package)
            try:
                self.connect()
                return
            except:
                self.log.debug(
                    'v0 snippet %s is not yet running, retrying',
                    self.package,
                    exc_info=True)
            time.sleep(1)
        raise jsonrpc_client_base.AppStartError(
            '%s failed to start on %s.' % (self.package, self._adb.serial))

    def _connect_to_v1(self):
        line = self._proc.stdout.readline().rstrip()
        match = re.match('^SNIPPET SERVING, PORT ([0-9]+)$', line)
        if not match:
            raise ProtocolVersionError(line)
        self.device_port = int(match.group(1))

        # Forward the device port to a new host port, and connect to that port
        self.host_port = utils.get_available_host_port()
        self._adb.forward(
            ['tcp:%d' % self.host_port, 'tcp:%d' % self.device_port])
        self.connect()
