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

import re
import time

from mobly import utils
from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import errors
from mobly.controllers.android_device_lib import jsonrpc_client_base

_INSTRUMENTATION_RUNNER_PACKAGE = (
    'com.google.android.mobly.snippet.SnippetRunner')

# Major version of the launch and communication protocol being used by this
# client.
# Incrementing this means that compatibility with clients using the older
# version is broken. Avoid breaking compatibility unless there is no other
# choice.
_PROTOCOL_MAJOR_VERSION = 1

# Minor version of the launch and communication protocol.
# Increment this when new features are added to the launch and communication
# protocol that are backwards compatible with the old protocol and don't break
# existing clients.
_PROTOCOL_MINOR_VERSION = 0

_LAUNCH_CMD = ('%s am instrument -w -e action start %s/' +
               _INSTRUMENTATION_RUNNER_PACKAGE)

_STOP_CMD = (
    'am instrument -w -e action stop %s/' + _INSTRUMENTATION_RUNNER_PACKAGE)

# Test that uses UiAutomation requires the shell session to be maintained while
# test is in progress. However, this requirement does not hold for the test that
# deals with device USB disconnection (Once device disconnects, the shell
# session that started the instrument ends, and UiAutomation fails with error:
# "UiAutomation not connected"). To keep the shell session and redirect
# stdin/stdout/stderr, use "setsid" or "nohup" while launching the
# instrumentation test. Because these commands may not be available in every
# android system, try to use them only if exists.
_SETSID_COMMAND = 'setsid'

_NOHUP_COMMAND = 'nohup'


class AppStartPreCheckError(jsonrpc_client_base.Error):
    """Raised when pre checks for the snippet failed."""


class ProtocolVersionError(jsonrpc_client_base.AppStartError):
    """Raised when the protocol reported by the snippet is unknown."""


class SnippetClient(jsonrpc_client_base.JsonRpcClientBase):
    """A client for interacting with snippet APKs using Mobly Snippet Lib.

    See superclass documentation for a list of public attributes.

    For a description of the launch protocols, see the documentation in
    mobly-snippet-lib, SnippetRunner.java.
    """

    def __init__(self, package, ad):
        """Initializes a SnippetClient.

        Args:
            package: (str) The package name of the apk where the snippets are
                defined.
            ad: (AndroidDevice) the device object associated with this client.
        """
        super(SnippetClient, self).__init__(app_name=package, ad=ad)
        self.package = package
        self._ad = ad
        self._adb = ad.adb
        self._proc = None

    def start_app_and_connect(self):
        """Overrides superclass. Launches a snippet app and connects to it."""
        self._check_app_installed()
        self.disable_hidden_api_blacklist()

        persists_shell_cmd = self._get_persist_command()
        # Use info here so people can follow along with the snippet startup
        # process. Starting snippets can be slow, especially if there are
        # multiple, and this avoids the perception that the framework is hanging
        # for a long time doing nothing.
        self.log.info('Launching snippet apk %s with protocol %d.%d',
                      self.package, _PROTOCOL_MAJOR_VERSION,
                      _PROTOCOL_MINOR_VERSION)
        cmd = _LAUNCH_CMD % (persists_shell_cmd, self.package)
        start_time = time.time()
        self._proc = self._do_start_app(cmd)

        # Check protocol version and get the device port
        line = self._read_protocol_line()
        match = re.match('^SNIPPET START, PROTOCOL ([0-9]+) ([0-9]+)$', line)
        if not match or match.group(1) != '1':
            raise ProtocolVersionError(self._ad, line)

        line = self._read_protocol_line()
        match = re.match('^SNIPPET SERVING, PORT ([0-9]+)$', line)
        if not match:
            raise ProtocolVersionError(self._ad, line)
        self.device_port = int(match.group(1))

        # Forward the device port to a new host port, and connect to that port
        self.host_port = utils.get_available_host_port()
        self._adb.forward(
            ['tcp:%d' % self.host_port,
             'tcp:%d' % self.device_port])
        self.connect()

        # Yaaay! We're done!
        self.log.debug('Snippet %s started after %.1fs on host port %s',
                       self.package,
                       time.time() - start_time, self.host_port)

    def restore_app_connection(self, port=None):
        """Restores the app after device got reconnected.

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
        self._adb.forward(
            ['tcp:%d' % self.host_port,
             'tcp:%d' % self.device_port])
        try:
            self.connect()
        except:
            # Failed to connect to app, something went wrong.
            raise jsonrpc_client_base.AppRestoreConnectionError(
                self._ad(
                    'Failed to restore app connection for %s at host port %s, '
                    'device port %s'), self.package, self.host_port,
                self.device_port)

        # Because the previous connection was lost, update self._proc
        self._proc = None
        self._restore_event_client()

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
                raise errors.DeviceError(
                    self._ad,
                    'Failed to stop existing apk. Unexpected output: %s' % out)
        finally:
            # Always clean up the adb port
            if self.host_port:
                self._adb.forward(['--remove', 'tcp:%d' % self.host_port])

    def _start_event_client(self):
        """Overrides superclass."""
        event_client = SnippetClient(package=self.package, ad=self._ad)
        event_client.host_port = self.host_port
        event_client.device_port = self.device_port
        event_client.connect(self.uid,
                             jsonrpc_client_base.JsonRpcCommand.CONTINUE)
        return event_client

    def _restore_event_client(self):
        """Restores previously created event client."""
        if not self._event_client:
            self._event_client = self._start_event_client()
            return
        self._event_client.host_port = self.host_port
        self._event_client.device_port = self.device_port
        self._event_client.connect()

    def _check_app_installed(self):
        # Check that the Mobly Snippet app is installed.
        out = self._adb.shell('pm list package')
        if not utils.grep('^package:%s$' % self.package, out):
            raise AppStartPreCheckError(self._ad,
                                        '%s is not installed.' % self.package)
        # Check that the app is instrumented.
        out = self._adb.shell('pm list instrumentation')
        matched_out = utils.grep('^instrumentation:%s/%s' %
                                 (self.package,
                                  _INSTRUMENTATION_RUNNER_PACKAGE), out)
        if not matched_out:
            raise AppStartPreCheckError(
                self._ad,
                '%s is installed, but it is not instrumented.' % self.package)
        match = re.search('^instrumentation:(.*)\/(.*) \(target=(.*)\)$',
                          matched_out[0])
        target_name = match.group(3)
        # Check that the instrumentation target is installed if it's not the
        # same as the snippet package.
        if target_name != self.package:
            out = self._adb.shell('pm list package')
            if not utils.grep('^package:%s$' % target_name, out):
                raise AppStartPreCheckError(
                    self._ad, 'Instrumentation target %s is not installed.' %
                    target_name)

    def _do_start_app(self, launch_cmd):
        adb_cmd = [adb.ADB]
        if self._adb.serial:
            adb_cmd += ['-s', self._adb.serial]
        adb_cmd += ['shell', launch_cmd]
        return utils.start_standing_subprocess(adb_cmd, shell=False)

    def _read_protocol_line(self):
        """Reads the next line of instrumentation output relevant to snippets.

        This method will skip over lines that don't start with 'SNIPPET' or
        'INSTRUMENTATION_RESULT'.

        Returns:
            (str) Next line of snippet-related instrumentation output, stripped.

        Raises:
            jsonrpc_client_base.AppStartError: If EOF is reached without any
                protocol lines being read.
        """
        while True:
            line = self._proc.stdout.readline().decode('utf-8')
            if not line:
                raise jsonrpc_client_base.AppStartError(
                    self._ad, 'Unexpected EOF waiting for app to start')
            # readline() uses an empty string to mark EOF, and a single newline
            # to mark regular empty lines in the output. Don't move the strip()
            # call above the truthiness check, or this method will start
            # considering any blank output line to be EOF.
            line = line.strip()
            if (line.startswith('INSTRUMENTATION_RESULT:')
                    or line.startswith('SNIPPET ')):
                self.log.debug(
                    'Accepted line from instrumentation output: "%s"', line)
                return line
            self.log.debug('Discarded line from instrumentation output: "%s"',
                           line)

    def _get_persist_command(self):
        """Check availability and return path of command if available."""
        for command in [_SETSID_COMMAND, _NOHUP_COMMAND]:
            try:
                if command in self._adb.shell(['which',
                                               command]).decode('utf-8'):
                    return command
            except adb.AdbError:
                continue
        self.log.warning(
            'No %s and %s commands available to launch instrument '
            'persistently, tests that depend on UiAutomator and '
            'at the same time performs USB disconnection may fail',
            _SETSID_COMMAND, _NOHUP_COMMAND)
        return ''
