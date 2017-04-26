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
                 associated with a particular CallbackHandler object.>
"""

from builtins import str

import json
import logging
import re
import socket
import threading
import time

from mobly.controllers.android_device_lib import adb
from mobly.controllers.android_device_lib import callback_handler

# Maximum time to wait for the app to start on the device (10 minutes).
# TODO: This timeout is set high in order to allow for retries in start_app.
# Decrease it when the call to connect() has the option for a quicker timeout
# than the default _cmd() timeout.
APP_START_WAIT_TIME = 10 * 60

# UID of the 'unknown' jsonrpc session. Will cause creation of a new session.
UNKNOWN_UID = -1

# Maximum time to wait for the socket to open on the device.
_SOCKET_CONNECTION_TIMEOUT = 60

# Maximum time to wait for a response message on the socket.
_SOCKET_READ_TIMEOUT = callback_handler.MAX_TIMEOUT


class Error(Exception):
    pass


class AppStartError(Error):
    """Raised when the app is not able to be started."""


class ApiError(Error):
    """Raised when remote API reports an error."""


class ProtocolError(Error):
    """Raised when there is some error in exchanging data with server."""
    NO_RESPONSE_FROM_HANDSHAKE = 'No response from handshake.'
    NO_RESPONSE_FROM_SERVER = 'No response from server.'
    MISMATCHED_API_ID = 'Mismatched API id.'


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
    adb.forward([local, remote]). Once the port has been forwarded it can be
    used in this object as the port of communication.

    Attributes:
        host_port: (int) The host port of this RPC client.
        device_port: (int) The device port of this RPC client.
        app_name: (str) The user-visible name of the app being communicated
                  with.
        uid: (int) The uid of this session.
    """

    def __init__(self,
                 host_port,
                 device_port,
                 app_name,
                 adb_proxy,
                 log=logging.getLogger()):
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
        self._event_client = None
        self._log = log

    def __del__(self):
        self.close()

    # Methods to be implemented by subclasses.

    def _do_start_app(self):
        """Starts the server app on the android device.

        Must be implemented by subclasses.
        """
        raise NotImplementedError()

    def _start_event_client(self):
        """Starts a separate JsonRpc client to the same session for propagating
        events.

        This is an optional function that should only implement if the client
        utilizes the snippet event mechanism.

        Returns:
            A JsonRpc Client object that connects to the same session as the
            one on which this function is called.
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
            wait_time: int, The minimum number of seconds to wait for the app
                to come up before raising an error. Note that _is_app_running()
                may take longer than wait_time.

        Raises:
            AppStartError: When the app was not able to be started.
        """
        self.check_app_installed()
        self._do_start_app()
        start_time = time.time()
        expiration_time = start_time + wait_time
        while time.time() < expiration_time:
            self._log.debug('Attempting to start %s.', self.app_name)
            if self._is_app_running():
                self._log.debug('Successfully started %s after %.1f seconds.',
                                self.app_name, time.time() - start_time)
                return
            time.sleep(1)
        raise AppStartError('%s failed to start on %s.' % (self.app_name,
                                                           self._adb.serial))

    def connect(self, uid=UNKNOWN_UID, cmd=JsonRpcCommand.INIT):
        """Opens a connection to a JSON RPC server.

        Opens a connection to a remote client. The connection attempt will time
        out if it takes longer than _SOCKET_CONNECTION_TIMEOUT seconds. Each
        subsequent operation over this socket will time out after
        _SOCKET_READ_TIMEOUT seconds as well.

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
                                              _SOCKET_CONNECTION_TIMEOUT)
        self._conn.settimeout(_SOCKET_READ_TIMEOUT)
        self._client = self._conn.makefile(mode='brw')

        resp = self._cmd(cmd, uid)
        if not resp:
            raise ProtocolError(ProtocolError.NO_RESPONSE_FROM_HANDSHAKE)
        result = json.loads(str(resp, encoding='utf8'))
        if result['status']:
            self.uid = result['uid']
        else:
            self.uid = UNKNOWN_UID

    def close(self):
        """Close the connection to the remote client."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def _grep(self, regex, output):
        """Similar to linux's `grep`, this returns the line in an output stream
        that matches a given regex pattern.

        This function is specifically used to grep strings from AdbProxy's
        output. We have to do this in Python instead of using cli tools because
        we need to support windows which does not have `grep` in all vesions.

        Args:
            regex: string, a regex that matches the expected pattern.
            output: byte string, the raw output of the adb cmd.

        Returns:
            A list of strings, all of which are output lines that matches the
            regex pattern.
        """
        lines = output.decode('utf-8').strip().splitlines()
        results = []
        for line in lines:
            if re.search(regex, line):
                results.append(line.strip())
        return results

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
        if result.get('callback') is not None:
            if self._event_client is None:
                self._event_client = self._start_event_client()
            return callback_handler.CallbackHandler(
                callback_id=result['callback'],
                event_client=self._event_client,
                ret_value=result['result'],
                method_name=method)
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
