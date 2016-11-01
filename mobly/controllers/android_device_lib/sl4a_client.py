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

"""
JSON RPC interface to android scripting engine.
"""

from builtins import str

import json
import logging
import os
import socket
import sys
import threading
import time

from mobly.controllers.android_device_lib import adb

HOST = os.environ.get('SL4A_HOST_ADDRESS', None)
PORT = os.environ.get('SL4A_HOST_PORT', 9999)
DEFAULT_DEVICE_SIDE_PORT = 8080

UNKNOWN_UID = -1

MAX_SL4A_WAIT_TIME = 10
_SL4A_LAUNCH_CMD = (
    "am start -a com.googlecode.android_scripting.action.LAUNCH_SERVER "
    "--ei com.googlecode.android_scripting.extra.USE_SERVICE_PORT {} "
    "com.googlecode.android_scripting/.activity.ScriptingLayerServiceLauncher")


class Sl4aException(Exception):
    pass


class Sl4aStartError(Sl4aException):
    """Raised when sl4a is not able to be started."""


class Sl4aApiError(Sl4aException):
    """Raised when remote API reports an error."""


class Sl4aProtocolError(Sl4aException):
    """Raised when there is some error in exchanging data with server on device."""
    NO_RESPONSE_FROM_HANDSHAKE = "No response from handshake."
    NO_RESPONSE_FROM_SERVER = "No response from server."
    MISMATCHED_API_ID = "Mismatched API id."


def start_sl4a(adb_proxy,
               device_side_port=DEFAULT_DEVICE_SIDE_PORT,
               wait_time=MAX_SL4A_WAIT_TIME):
    """Starts sl4a server on the android device.

    Args:
        adb_proxy: adb.AdbProxy, The adb proxy to use to start sl4a
        device_side_port: int, The port number to open on the device side.
        wait_time: float, The time to wait for sl4a to come up before raising
                   an error.

    Raises:
        Sl4aException: Raised when SL4A was not able to be started.
    """
    if not is_sl4a_installed(adb_proxy):
        raise Sl4aStartError("SL4A is not installed on %s" % adb_proxy.serial)
    MAX_SL4A_WAIT_TIME = 10
    adb_proxy.shell(_SL4A_LAUNCH_CMD.format(device_side_port))
    for _ in range(wait_time):
        time.sleep(1)
        if is_sl4a_running(adb_proxy):
            return
    raise Sl4aStartError("SL4A failed to start on %s." % adb_proxy.serial)


def stop_sl4a(adb_proxy):
    """Kills any running instance of sl4a.

    Kills any running instance of sl4a. If no instance is running then nothing
    is done.

    Args:
        adb_proxy: adb.AdbProxy, The adb proxy to use for checking.
    """
    if is_sl4a_running(adb_proxy):
        adb_proxy.shell('am force-stop com.googlecode.android_scripting')


def is_sl4a_installed(adb_proxy):
    """Checks if sl4a is installed by querying the package path of sl4a.

    Args:
        adb: adb.AdbProxy, The adb proxy to use for checking install.

    Returns:
        True if sl4a is installed, False otherwise.
    """
    try:
        adb_proxy.shell("pm path com.googlecode.android_scripting")
        return True
    except adb.AdbError as e:
        if not e.stderr:
            return False
        raise


def is_sl4a_running(adb_proxy):
    """Checks if the sl4a app is running on an android device.

    Args:
        adb_proxy: adb.AdbProxy, The adb proxy to use for checking.

    Returns:
        True if the sl4a app is running, False otherwise.
    """
    # Grep for process with a preceding S which means it is truly started.
    out = adb_proxy.shell('ps | grep "S com.googlecode.android_scripting"')
    if len(out) == 0:
        return False
    return True


class Sl4aCommand(object):
    """Commands that can be invoked on the sl4a client.

    INIT: Initializes a new sessions in sl4a.
    CONTINUE: Creates a connection.
    """
    INIT = 'initiate'
    CONTINUE = 'continue'


class Sl4aClient(object):
    """A sl4a client that is connected to remotely.

    Connects to a remove device running sl4a. Before opening a connection
    a port forward must be setup to go over usb. This be done using
    adb.tcp_forward(). This is calling the shell command
    adb forward <local> remote>. Once the port has been forwarded it can be
    used in this object as the port of communication.

    Attributes:
        port: int, The host port to communicate through.
        addr: str, The host address who is communicating to the device (usually
                   localhost).
        client: file, The socket file used to communicate.
        uid: int, The sl4a uid of this session.
        conn: socket.Socket, The socket connection to the remote client.
    """

    _SOCKET_TIMEOUT = 60

    def __init__(self, port=PORT, addr=HOST, uid=UNKNOWN_UID):
        """
        Args:
            port: int, The port this client should connect to.
            addr: str, The address this client should connect to.
            uid: int, The uid of the session to join, or UNKNOWN_UID to start a
                 new session.
        """
        self.port = port
        self.addr = addr
        self._lock = threading.Lock()
        self.client = None  # prevent close errors on connect failure
        self.uid = uid
        self.conn = None

    def __del__(self):
        self.close()

    def _id_counter(self):
        i = 0
        while True:
            yield i
            i += 1

    def open(self, connection_timeout=None, cmd=Sl4aCommand.INIT):
        """Opens a connection to the remote client.

        Opens a connection to a remote client with sl4a. The connection will
        error out if it takes longer than the connection_timeout time. Once
        connected if the socket takes longer than _SOCKET_TIMEOUT to respond
        the connection will be closed.

        Args:
            connection_timeout: int, The time to wait for the connection to come
                                up.
            cmd: Sl4aCommand, The command to use for creating the connection.

        Raises:
            IOError: Raised when the socket times out from io error
            socket.timeout: Raised when the socket waits to long for connection.
            Sl4aProtocolError: Raised when there is an error in the protocol.
        """
        if connection_timeout:
            timeout_time = time.time() + connection_timeout
        else:
            timeout_time = sys.maxsize
        self._counter = self._id_counter()
        while True:
            try:
                self.conn = socket.create_connection(
                    (self.addr, self.port), max(1, timeout_time - time.time()))
                self.conn.settimeout(self._SOCKET_TIMEOUT)
                break
            except (socket.timeout):
                logging.exception("Failed to create socket connection!")
                raise
            except (socket.error, IOError):
                # TODO: optimize to only forgive some errors here
                # error values are OS-specific so this will require
                # additional tuning to fail faster
                if time.time() + 1 >= timeout_time:
                    logging.exception("Failed to create socket connection!")
                    raise
                time.sleep(1)

        self.client = self.conn.makefile(mode="brw")

        resp = self._cmd(cmd, self.uid)
        if not resp:
            raise Sl4aProtocolError(
                Sl4aProtocolError.NO_RESPONSE_FROM_HANDSHAKE)
        result = json.loads(str(resp, encoding="utf8"))
        if result['status']:
            self.uid = result['uid']
        else:
            self.uid = UNKNOWN_UID

    def close(self):
        """Close the connection to the remote client."""
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def _cmd(self, command, uid=None):
        """Send a command to sl4a.

        Given a command name, this will package the command and send it to
        sl4a.

        Args:
            command: str, The name of the command to execute.
            uid: int, the uid of the session to send the command to.

        Returns:
            The line that was written back.
        """
        if not uid:
            uid = self.uid
        self.client.write(json.dumps({'cmd': command,
                                      'uid': uid}).encode("utf8") + b'\n')
        self.client.flush()
        return self.client.readline()

    def _rpc(self, method, *args):
        """Sends an rpc to sl4a.

        Sends an rpc call to sl4a using this clients connection.

        Args:
            method: str, The name of the method to execute.
            args: any, The args to send to sl4a.

        Returns:
            The result of the rpc.

        Raises:
            Sl4aProtocolError: Something went wrong with the sl4a protocol.
            Sl4aApiError: The rpc went through, however executed with errors.
        """
        with self._lock:
            apiid = next(self._counter)
        data = {'id': apiid, 'method': method, 'params': args}
        request = json.dumps(data)
        self.client.write(request.encode("utf8") + b'\n')
        self.client.flush()
        response = self.client.readline()
        if not response:
            raise Sl4aProtocolError(Sl4aProtocolError.NO_RESPONSE_FROM_SERVER)
        result = json.loads(str(response, encoding="utf8"))
        if result['error']:
            raise Sl4aApiError(result['error'])
        if result['id'] != apiid:
            raise Sl4aProtocolError(Sl4aProtocolError.MISMATCHED_API_ID)
        return result['result']

    def __getattr__(self, name):
        """Wrapper for python magic to turn method calls into RPC calls."""

        def rpc_call(*args):
            return self._rpc(name, *args)

        return rpc_call
