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
"""Base class for clients that communicate with apps over a JSON RPC interface.

The JSON protocol expected by this module is:

Request:
{
    "id": <monotonically increasing integer containing the ID of this request>
    "method": <string containing the name of the method to execute>
    "params": <JSON array containing the arguments to the method>
}

Response:
{
    "id": <int id of request that this response maps to>,
    "result": <Arbitrary JSON object containing the result of executing the
               method. If the method could not be executed or returned void,
               contains 'null'.>,
    "error": <String containing the error thrown by executing the method.
              If no error occurred, contains 'null'.>
    "callback": <String that represents a callback ID used to identify events
                 associated with a particular CallbackFuture object.>
"""

from builtins import str

import json
import socket
import threading
import time

from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import callback_future

# Maximum time to wait for the app to start on the device.
APP_START_WAIT_TIME = 15

# UID of the 'unknown' jsonrpc session. Will cause creation of a new session.
UNKNOWN_UID = -1

# Maximum time to wait for the socket to open on the device.
_SOCKET_TIMEOUT = 60


class Error(Exception):
    pass


class AppStartError(Error):
    """Raised when the app is not able to be started."""


class ApiError(Error):
    """Raised when remote API reports an error."""


class ProtocolError(Error):
    """Raised when there is some error in exchanging data with server."""
    NO_RESPONSE_FROM_HANDSHAKE = "No response from handshake."
    NO_RESPONSE_FROM_SERVER = "No response from server."
    MISMATCHED_API_ID = "Mismatched API id."


class JsonRpcCommand(object):
    """Commands that can be invoked on all jsonrpc clients.

    INIT: Initializes a new session.
    CONTINUE: Creates a connection.
    """
    INIT = 'initiate'
    CONTINUE = 'continue'


class JsonRpcClientBase(object):
    """Base class for jsonrpc clients that connect to remote servers.

    Connects to a remote device running a jsonrpc-compatible app. Before opening
    a connection a port forward must be setup to go over usb. This be done using
    adb.tcp_forward(). This calls the shell command adb forward <local> remote>.
    Once the port has been forwarded it can be used in this object as the port
    of communication.

    Attributes:
        host_port: (int) The host port of this RPC client.
        device_port: (int) The device port of this RPC client.
        app_name: (str) The user-visible name of the app being communicated
                  with.
        uid: (int) The uid of this session.
    """

    def __init__(self, host_port, device_port, app_name, adb_proxy):
        """
        Args:
            host_port: (int) The host port of this RPC client.
            device_port: (int) The device port of this RPC client.
            app_name: (str) The user-visible name of the app being communicated
                      with.
            adb_proxy: (adb.AdbProxy) The adb proxy to use to start the app.
        """
        self.host_port = host_port
        self.device_port = device_port
        self.app_name = app_name
        self.uid = None
        self._adb = adb_proxy
        self._client = None  # prevent close errors on connect failure
        self._conn = None
        self._counter = None
        self._lock = threading.Lock()
        self._event_poller = None

    def __del__(self):
        self.close()

    # Methods to be implemented by subclasses.

    def _do_start_app(self):
        """Starts the server app on the android device.

        Must be implemented by subclasses.
        """
        raise NotImplementedError()

    def stop_app(self):
        """Kills any running instance of the app.

        Must be implemented by subclasses.
        """
        raise NotImplementedError()

    def check_app_installed(self):
        """Checks if app is installed.

        Must be implemented by subclasses.
        """
        raise NotImplementedError()

    # Rest of the client methods.

    def start_app(self, wait_time=APP_START_WAIT_TIME):
        """Starts the server app on the android device.

        Args:
            wait_time: float, The time to wait for the app to come up before
                       raising an error.

        Raises:
            AppStartError: When the app was not able to be started.
        """
        self.check_app_installed()
        self._do_start_app()
        for _ in range(wait_time):
            time.sleep(1)
            if self._is_app_running():
                return
        raise AppStartError('%s failed to start on %s.' %
                            (self.app_name, self._adb.serial))

    def connect(self, uid=UNKNOWN_UID, cmd=JsonRpcCommand.INIT):
        """Opens a connection to a JSON RPC server.

        Opens a connection to a remote client. The connection attempt will time
        out if it takes longer than _SOCKET_TIMEOUT seconds. Each subsequent
        operation over this socket will time out after _SOCKET_TIMEOUT seconds
        as well.

        Args:
            uid: int, The uid of the session to join, or UNKNOWN_UID to start a
                 new session.
            cmd: JsonRpcCommand, The command to use for creating the connection.

        Raises:
            IOError: Raised when the socket times out from io error
            socket.timeout: Raised when the socket waits to long for connection.
            ProtocolError: Raised when there is an error in the protocol.
        """
        self._counter = self._id_counter()
        self._conn = socket.create_connection(('127.0.0.1', self.host_port),
                                              _SOCKET_TIMEOUT)
        self._conn.settimeout(_SOCKET_TIMEOUT)
        self._client = self._conn.makefile(mode="brw")

        resp = self._cmd(cmd, uid)
        if not resp:
            raise ProtocolError(ProtocolError.NO_RESPONSE_FROM_HANDSHAKE)
        result = json.loads(str(resp, encoding="utf8"))
        if result['status']:
            self.uid = result['uid']
        else:
            self.uid = UNKNOWN_UID

    def close(self):
        """Close the connection to the remote client."""
        if self._conn:
            self._conn.close()
            self._conn = None
        if self._event_poller:
            self._event_poller.stop()

    def _adb_grep_wrapper(self, adb_shell_cmd):
        """A wrapper for the specific usage of adb shell grep in this class.

        This surpresses AdbError if the grep fails to find anything.

        Args:
            adb_shell_cmd: A string that is an adb shell cmd with grep.

        Returns:
            The stdout of the grep result if the grep found something, False
            otherwise.
        """
        try:
            return self._adb.shell(adb_shell_cmd).decode('utf-8')
        except adb.AdbError as e:
            if (e.ret_code == 1) and (not e.stdout) and (not e.stderr):
                return False
            raise

    def _cmd(self, command, uid=None):
        """Send a command to the server.

        Args:
            command: str, The name of the command to execute.
            uid: int, the uid of the session to send the command to.

        Returns:
            The line that was written back.
        """
        if not uid:
            uid = self.uid
        self._client.write(
            json.dumps({
                'cmd': command,
                'uid': uid
            }).encode("utf8") + b'\n')
        self._client.flush()
        return self._client.readline()

    def _rpc(self, method, *args):
        """Sends an rpc to the app.

        Args:
            method: str, The name of the method to execute.
            args: any, The args of the method.

        Returns:
            The result of the rpc.

        Raises:
            ProtocolError: Something went wrong with the protocol.
            ApiError: The rpc went through, however executed with errors.
        """
        with self._lock:
            apiid = next(self._counter)
        data = {'id': apiid, 'method': method, 'params': args}
        request = json.dumps(data)
        self._client.write(request.encode("utf8") + b'\n')
        self._client.flush()
        response = self._client.readline()
        if not response:
            raise ProtocolError(ProtocolError.NO_RESPONSE_FROM_SERVER)
        result = json.loads(str(response, encoding="utf8"))
        if result['error']:
            raise ApiError(result['error'])
        if result['id'] != apiid:
            raise ProtocolError(ProtocolError.MISMATCHED_API_ID)
        if result['callback'] is not None:
            if self._event_poller is None:
                self.start_event_polling()
            return callback_future.CallbackFuture(result['callback'],
                                                  self._event_poller)
        return result['result']

    def _is_app_running(self):
        """Checks if the app is currently running on an android device.

        May be overridden by subclasses with custom sanity checks.
        """
        running = False
        try:
            self.connect()
            running = True
        finally:
            self.close()
            # This 'return' squashes exceptions from connect()
            return running

    def __getattr__(self, name):
        """Wrapper for python magic to turn method calls into RPC calls."""

        def rpc_call(*args):
            return self._rpc(name, *args)

        return rpc_call

    def _id_counter(self):
        i = 0
        while True:
            yield i
            i += 1
