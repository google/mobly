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

from builtins import str
from past.builtins import basestring

import logging
import pipes
import psutil
import subprocess
import threading

# Command to use for running ADB commands.
ADB = 'adb'

# adb gets confused if we try to manage bound ports in parallel, so anything to
# do with port forwarding must happen under this lock.
ADB_PORT_LOCK = threading.Lock()

# Qualified class name of the default instrumentation test runner.
DEFAULT_INSTRUMENTATION_RUNNER = 'com.android.common.support.test.runner.AndroidJUnitRunner'


class Error(Exception):
    """Base error type for adb proxy module."""


class AdbError(Error):
    """Raised when an adb command encounters an error.

    Args:
        cmd: list of strings, the adb command executed.
        stdout: byte string, the raw stdout of the command.
        stderr: byte string, the raw stderr of the command.
        ret_code: int, the return code of the command.
        serial: string, the serial of the device the command is executed on.
            This is an empty string if the adb command is not specific to a
            device.
    """

    def __init__(self, cmd, stdout, stderr, ret_code, serial=''):
        self.cmd = cmd
        self.stdout = stdout
        self.stderr = stderr
        self.ret_code = ret_code
        self.serial = serial

    def __str__(self):
        return ('Error executing adb cmd "%s". ret: %d, stdout: %s, stderr: %s'
                ) % (cli_cmd_to_string(self.cmd), self.ret_code, self.stdout,
                     self.stderr)


class AdbTimeoutError(Error):
    """Raised when an command did not complete within expected time.

    Args:
        cmd: list of strings, the adb command that timed out
        timeout: float, the number of seconds passed before timing out.
        serial: string, the serial of the device the command is executed on.
            This is an empty string if the adb command is not specific to a
            device.
    """

    def __init__(self, cmd, timeout, serial=''):
        self.cmd = cmd
        self.timeout = timeout
        self.serial = serial

    def __str__(self):
        return 'Timed out executing command "%s" after %ss.' % (
            cli_cmd_to_string(self.cmd), self.timeout)


def list_occupied_adb_ports():
    """Lists all the host ports occupied by adb forward.

    This is useful because adb will silently override the binding if an attempt
    to bind to a port already used by adb was made, instead of throwing binding
    error. So one should always check what ports adb is using before trying to
    bind to a port with adb.

    Returns:
        A list of integers representing occupied host ports.
    """
    out = AdbProxy().forward('--list')
    clean_lines = str(out, 'utf-8').strip().split('\n')
    used_ports = []
    for line in clean_lines:
        tokens = line.split(' tcp:')
        if len(tokens) != 3:
            continue
        used_ports.append(int(tokens[1]))
    return used_ports


def cli_cmd_to_string(args):
    """Converts a cmd arg list to string.

    Args:
        args: list of strings, the arguments of a command.

    Returns:
        String representation of the command.
    """
    if isinstance(args, basestring):
        # Return directly if it's already a string.
        return args
    return ' '.join([pipes.quote(arg) for arg in args])


class AdbProxy(object):
    """Proxy class for ADB.

    For syntactic reasons, the '-' in adb commands need to be replaced with
    '_'. Can directly execute adb commands on an object:
    >> adb = AdbProxy(<serial>)
    >> adb.start_server()
    >> adb.devices() # will return the console output of "adb devices".

    By default, command args are expected to be an iterable which is passed
    directly to subprocess.Popen():
    >> adb.shell(['echo', 'a', 'b'])

    This way of launching commands is recommended by the subprocess
    documentation to avoid shell injection vulnerabilities and avoid having to
    deal with multiple layers of shell quoting and different shell environments
    between different OSes.

    If you really want to run the command through the system shell, this is
    possible by supplying shell=True, but try to avoid this if possible:
    >> adb.shell('cat /foo > /tmp/file', shell=True)
    """

    def __init__(self, serial=''):
        self.serial = serial

    def _exec_cmd(self, args, shell, timeout, stderr):
        """Executes adb commands.

        Args:
            args: string or list of strings, program arguments.
                See subprocess.Popen() documentation.
            shell: bool, True to run this command through the system shell,
                False to invoke it directly. See subprocess.Popen() docs.
            timeout: float, the number of seconds to wait before timing out.
                If not specified, no timeout takes effect.
            stderr: a Byte stream, like io.BytesIO, stderr of the command will
                be written to this object if provided.

        Returns:
            The output of the adb command run if exit code is 0.

        Raises:
            ValueError: timeout value is invalid.
            AdbError: The adb command exit code is not 0.
            AdbTimeoutError: The adb command timed out.
        """
        proc = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=shell)
        process = psutil.Process(proc.pid)
        if timeout and timeout <= 0:
            raise ValueError('Timeout is not a positive value: %s' % timeout)
        if timeout and timeout > 0:
            try:
                process.wait(timeout=timeout)
            except psutil.TimeoutExpired:
                process.terminate()
                raise AdbTimeoutError(
                    cmd=args, timeout=timeout, serial=self.serial)

        (out, err) = proc.communicate()
        if stderr:
            stderr.write(err)
        ret = proc.returncode
        logging.debug('cmd: %s, stdout: %s, stderr: %s, ret: %s',
                      cli_cmd_to_string(args), out, err, ret)
        if ret == 0:
            return out
        else:
            raise AdbError(
                cmd=args,
                stdout=out,
                stderr=err,
                ret_code=ret,
                serial=self.serial)

    def _execute_and_process_stdout(self, args, shell, handler):
        """Executes adb commands and processes the stdout with a handler.

        Args:
            args: string or list of strings, program arguments.
                See subprocess.Popen() documentation.
            shell: bool, True to run this command through the system shell,
                False to invoke it directly. See subprocess.Popen() docs.
            handler: func, a function to handle adb stdout line by line.

        Returns:
            The stderr of the adb command run if exit code is 0.

        Raises:
            AdbError: The adb command exit code is not 0.
        """
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=shell,
            bufsize=1)
        out = '[elided, processed via handler]'
        try:
            # Even if the process dies, stdout.readline still works
            # and will continue until it runs out of stdout to process.
            while True:
                line = proc.stdout.readline()
                if line:
                    handler(line)
                else:
                    break
        finally:
            # Note, communicate will not contain any buffered output.
            (unexpected_out, err) = proc.communicate()
            if unexpected_out:
                out = '[unexpected stdout] %s' % unexpected_out
                for line in unexpected_out.splitlines():
                    handler(line)

        ret = proc.returncode
        logging.debug('cmd: %s, stdout: %s, stderr: %s, ret: %s',
                      cli_cmd_to_string(args), out, err, ret)
        if ret == 0:
            return err
        else:
            raise AdbError(cmd=args, stdout=out, stderr=err, ret_code=ret)

    def _construct_adb_cmd(self, raw_name, args, shell):
        """Constructs an adb command with arguments for a subprocess call.

        Args:
            raw_name: string, the raw unsanitized name of the adb command to
                format.
            args: string or list of strings, arguments to the adb command.
                See subprocess.Proc() documentation.
            shell: bool, True to run this command through the system shell,
                False to invoke it directly. See subprocess.Proc() docs.

        Returns:
            The adb command in a format appropriate for subprocess. If shell is
                True, then this is a string; otherwise, this is a list of
                strings.
        """
        args = args or ''
        name = raw_name.replace('_', '-')
        if shell:
            args = cli_cmd_to_string(args)
            # Add quotes around "adb" in case the ADB path contains spaces. This
            # is pretty common on Windows (e.g. Program Files).
            if self.serial:
                adb_cmd = '"%s" -s "%s" %s %s' % (ADB, self.serial, name, args)
            else:
                adb_cmd = '"%s" %s %s' % (ADB, name, args)
        else:
            adb_cmd = [ADB]
            if self.serial:
                adb_cmd.extend(['-s', self.serial])
            adb_cmd.append(name)
            if args:
                if isinstance(args, basestring):
                    adb_cmd.append(args)
                else:
                    adb_cmd.extend(args)
        return adb_cmd

    def _exec_adb_cmd(self, name, args, shell, timeout, stderr):
        adb_cmd = self._construct_adb_cmd(name, args, shell=shell)
        out = self._exec_cmd(
            adb_cmd, shell=shell, timeout=timeout, stderr=stderr)
        return out

    def _execute_adb_and_process_stdout(self, name, args, shell, handler):
        adb_cmd = self._construct_adb_cmd(name, args, shell=shell)
        out = self._execute_and_process_stdout(
            adb_cmd, shell=shell, handler=handler)
        return out

    def getprop(self, prop_name):
        """Get a property of the device.

        This is a convenience wrapper for "adb shell getprop xxx".

        Args:
            prop_name: A string that is the name of the property to get.

        Returns:
            A string that is the value of the property, or None if the property
            doesn't exist.
        """
        return self.shell('getprop %s' % prop_name).decode('utf-8').strip()

    def has_shell_command(self, command):
        """Checks to see if a given check command exists on the device.

        Args:
            command: A string that is the name of the command to check.

        Returns:
            A boolean that is True if the command exists and False otherwise.
        """
        try:
            output = self.shell(['command', '-v',
                                 command]).decode('utf-8').strip()
            return command in output
        except AdbError:
            # If the command doesn't exist, then 'command -v' can return
            # an exit code > 1.
            return False

    def forward(self, args=None, shell=False):
        with ADB_PORT_LOCK:
            return self._exec_adb_cmd(
                'forward', args, shell, timeout=None, stderr=None)

    def instrument(self, package, options=None, runner=None, handler=None):
        """Runs an instrumentation command on the device.

        This is a convenience wrapper to avoid parameter formatting.

        Example:

        .. code-block:: python

            device.instrument(
                'com.my.package.test',
                options = {
                    'class': 'com.my.package.test.TestSuite',
                },
            )

        Args:
            package: string, the package of the instrumentation tests.
            options: dict, the instrumentation options including the test
                class.
            runner: string, the test runner name, which defaults to
                DEFAULT_INSTRUMENTATION_RUNNER.
            handler: optional func, when specified the function is used to parse
                the instrumentation stdout line by line as the output is
                generated; otherwise, the stdout is simply returned once the
                instrumentation is finished.

        Returns:
            The stdout of instrumentation command or the stderr if the handler
                is set.
        """
        if runner is None:
            runner = DEFAULT_INSTRUMENTATION_RUNNER
        if options is None:
            options = {}

        options_list = []
        for option_key, option_value in options.items():
            options_list.append('-e %s %s' % (option_key, option_value))
        options_string = ' '.join(options_list)

        instrumentation_command = 'am instrument -r -w %s %s/%s' % (
            options_string, package, runner)
        logging.info('AndroidDevice|%s: Executing adb shell %s', self.serial,
                     instrumentation_command)
        if handler is None:
            # Flow kept for backwards-compatibility reasons
            self._exec_adb_cmd(
                'shell',
                instrumentation_command,
                shell=False,
                timeout=None,
                stderr=None)
        else:
            return self._execute_adb_and_process_stdout(
                'shell', instrumentation_command, shell=False, handler=handler)

    def __getattr__(self, name):
        def adb_call(args=None, shell=False, timeout=None, stderr=None):
            """Wrapper for an ADB command.

            Args:
                args: string or list of strings, arguments to the adb command.
                    See subprocess.Proc() documentation.
                shell: bool, True to run this command through the system shell,
                    False to invoke it directly. See subprocess.Proc() docs.
                timeout: float, the number of seconds to wait before timing out.
                    If not specified, no timeout takes effect.
                stderr: a Byte stream, like io.BytesIO, stderr of the command
                    will be written to this object if provided.

            Returns:
                The output of the adb command run if exit code is 0.
            """
            return self._exec_adb_cmd(
                name, args, shell=shell, timeout=timeout, stderr=stderr)

        return adb_call
