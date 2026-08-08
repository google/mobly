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

import io
import logging
import re
import selectors
import subprocess
import threading
import time
from typing import Generator, List, Optional, Union

from mobly import utils

# Command to use for running ADB commands.
ADB = 'adb'

# adb gets confused if we try to manage bound ports in parallel, so anything to
# do with port forwarding must happen under this lock.
ADB_PORT_LOCK = threading.Lock()

# Number of attempts to execute "adb root", and seconds for interval time and
# the timeout of this command.
ADB_ROOT_RETRY_ATTEMPTS = 3
ADB_ROOT_RETRY_ATTEMPT_INTERVAL_SEC = 10
ADB_ROOT_ATTEMPT_TIMEOUT_SEC = 5

# Qualified class name of the default instrumentation test runner.
DEFAULT_INSTRUMENTATION_RUNNER = (
    'com.android.common.support.test.runner.AndroidJUnitRunner'
)

# `adb shell getprop` can take surprisingly long, when the device is a
# networked virtual device.
DEFAULT_GETPROP_TIMEOUT_SEC = 10
DEFAULT_GETPROPS_ATTEMPTS = 3
DEFAULT_GETPROPS_RETRY_SLEEP_SEC = 1

# The regex pattern indicating the `adb connect` command did not fail.
PATTERN_ADB_CONNECT_SUCCESS = re.compile(
    r'^connected to .*|^already connected to .*'
)


class Error(Exception):
  """Base error type for adb proxy module."""


class AdbError(Error):
  """Raised when an adb command encounters an error.

  Attributes:
    cmd: list of strings, the adb command executed.
    stdout: byte string, the raw stdout of the command.
    stderr: byte string, the raw stderr of the command.
    ret_code: int, the return code of the command.
    serial: string, the serial of the device the command is executed on.
      This is an empty string if the adb command is not specific to a
      device.
  """

  def __init__(self, cmd, stdout, stderr, ret_code, serial=''):
    super().__init__()
    self.cmd = cmd
    self.stdout = stdout
    self.stderr = stderr
    self.ret_code = ret_code
    self.serial = serial

  def __str__(self):
    return 'Error executing adb cmd "%s". ret: %d, stdout: %s, stderr: %s' % (
        utils.cli_cmd_to_string(self.cmd),
        self.ret_code,
        self.stdout,
        self.stderr,
    )


class AdbTimeoutError(Error):
  """Raised when an command did not complete within expected time.

  Attributes:
    cmd: list of strings, the adb command that timed out
    timeout: float, the number of seconds passed before timing out.
    serial: string, the serial of the device the command is executed on.
      This is an empty string if the adb command is not specific to a
      device.
  """

  def __init__(self, cmd, timeout, serial=''):
    super().__init__()
    self.cmd = cmd
    self.timeout = timeout
    self.serial = serial

  def __str__(self):
    return 'Timed out executing command "%s" after %ss.' % (
        utils.cli_cmd_to_string(self.cmd),
        self.timeout,
    )


class AdbProcess:
  """A wrapper for an asynchronous ADB subprocess.

  Attributes:
    pid: int, the process ID.
    cmd: string or list of strings, the command executed.
    serial: string, the device serial number.
    returncode: int or None, the exit code of the process.
    is_alive: bool, True if the process is currently running.
    stdout: stream or None, stdout of the process.
    stderr: stream or None, stderr of the process.
  """

  def __init__(
      self,
      proc: subprocess.Popen,
      cmd: Union[str, List[str]],
      serial: str = '',
  ):
    self._proc = proc
    self._cmd = cmd
    self._serial = serial

  @property
  def pid(self) -> int:
    """The process ID."""
    return self._proc.pid

  @property
  def cmd(self) -> Union[str, List[str]]:
    """The command executed."""
    return self._cmd

  @property
  def serial(self) -> str:
    """The serial of the device the command is executed on."""
    return self._serial

  @property
  def returncode(self) -> Optional[int]:
    """The return code of the process if terminated, None otherwise."""
    return self._proc.returncode

  @property
  def is_alive(self) -> bool:
    """Whether the process is currently running."""
    return self.poll() is None

  @property
  def stdout(self):
    """The stdout stream of the process."""
    return self._proc.stdout

  @property
  def stderr(self):
    """The stderr stream of the process."""
    return self._proc.stderr

  def poll(self) -> Optional[int]:
    """Polls the process to check if it has terminated.

    Returns:
      The returncode if terminated, None otherwise.
    """
    return self._proc.poll()

  def wait(self, timeout: Optional[float] = None) -> int:
    """Waits for the process to complete and returns its return code.

    Args:
      timeout: float, the number of seconds to wait before timing out.

    Returns:
      int, the return code of the process.

    Raises:
      ValueError: If timeout is not a positive value.
      AdbTimeoutError: If the process timed out.
    """
    if timeout is not None and timeout <= 0:
      raise ValueError('Timeout is not a positive value: %s' % timeout)
    try:
      return self._proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
      raise AdbTimeoutError(
          cmd=self._cmd, timeout=timeout, serial=self._serial
      )

  def stop(self) -> int:
    """Cleanly stops the process and returns the exit code.

    Returns:
      int, the return code of the process.
    """
    if self.poll() is None:
      try:
        utils.stop_standing_subprocess(self._proc)
      except utils.Error:
        if self.poll() is None:
          raise
    elif self._proc.returncode is None:
      self._proc.wait()
    return self._proc.returncode if self._proc.returncode is not None else 0

  def iter_lines(
      self,
      timeout: Optional[float] = None,
      decode_errors: str = 'replace',
  ) -> Generator[str, None, None]:
    """Yields lines of stdout as strings.

    Args:
      timeout: float, maximum time in seconds to wait before timing out.
      decode_errors: str, error handling scheme for decoding bytes.

    Yields:
      Decoded stdout lines as strings.

    Raises:
      ValueError: If stdout is not available or timeout is not positive.
      AdbTimeoutError: If waiting for output times out.
    """
    if self._proc.stdout is None:
      raise ValueError('Process stdout is not a readable pipe.')

    if timeout is not None:
      if timeout <= 0:
        raise ValueError('Timeout is not a positive value: %s' % timeout)
      deadline = time.time() + timeout
    else:
      deadline = None

    while True:
      if deadline is not None:
        remaining = deadline - time.time()
        if remaining <= 0:
          raise AdbTimeoutError(
              cmd=self._cmd, timeout=timeout, serial=self._serial
          )
        if hasattr(self._proc.stdout, 'fileno'):
          try:
            sel = selectors.DefaultSelector()
            sel.register(self._proc.stdout, selectors.EVENT_READ)
            try:
              events = sel.select(timeout=max(0.0, remaining))
              if not events:
                raise AdbTimeoutError(
                    cmd=self._cmd, timeout=timeout, serial=self._serial
                )
            finally:
              sel.close()
          except (io.UnsupportedOperation, AttributeError, ValueError, OSError):
            pass

      line = self._proc.stdout.readline()
      if not line:
        break

      if deadline is not None and time.time() > deadline:
        raise AdbTimeoutError(
            cmd=self._cmd, timeout=timeout, serial=self._serial
        )

      if isinstance(line, bytes):
        yield line.decode('utf-8', errors=decode_errors)
      else:
        yield line

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    self.stop()


def is_adb_available():
  """Checks if adb is available as a command line tool.

  Returns:
    True if adb binary is available in console, False otherwise.
  """
  ret, out, err = utils.run_command('which adb', shell=True)
  clean_out = out.decode('utf-8').strip()
  if clean_out:
    return True
  return False


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


class AdbProxy:
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

  def _exec_cmd(self, args, shell, timeout, stderr) -> bytes:
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
    if timeout and timeout <= 0:
      raise ValueError('Timeout is not a positive value: %s' % timeout)
    try:
      (ret, out, err) = utils.run_command(args, shell=shell, timeout=timeout)
    except subprocess.TimeoutExpired:
      raise AdbTimeoutError(cmd=args, timeout=timeout, serial=self.serial)

    if stderr:
      stderr.write(err)
    if ret == 0:
      return out
    else:
      raise AdbError(
          cmd=args, stdout=out, stderr=err, ret_code=ret, serial=self.serial
      )

  def _execute_and_process_stdout(self, args, shell, handler) -> bytes:
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
        bufsize=1,
    )
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
    logging.debug(
        'cmd: %s, stdout: %s, stderr: %s, ret: %s',
        utils.cli_cmd_to_string(args),
        out,
        err,
        ret,
    )
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
      args = utils.cli_cmd_to_string(args)
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
        if isinstance(args, str):
          adb_cmd.append(args)
        else:
          adb_cmd.extend(args)
    return adb_cmd

  def _exec_adb_cmd(self, name, args, shell, timeout, stderr) -> bytes:
    adb_cmd = self._construct_adb_cmd(name, args, shell=shell)
    out = self._exec_cmd(adb_cmd, shell=shell, timeout=timeout, stderr=stderr)
    return out

  def _spawn_cmd(
      self,
      name: str,
      args=None,
      shell: bool = False,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      env=None,
  ) -> AdbProcess:
    """Spawns an adb command asynchronously.

    Args:
      name: string, the adb command name.
      args: string or list of strings, arguments to the adb command.
      shell: bool, True to run this command through the system shell,
        False to invoke it directly.
      stdout: file handle or subprocess pipe for stdout.
      stderr: file handle or subprocess pipe for stderr.
      env: dict, custom environment variables.

    Returns:
      An AdbProcess instance wrapping the spawned subprocess.
    """
    adb_cmd = self._construct_adb_cmd(name, args, shell=shell)
    proc = utils.start_standing_subprocess(
        adb_cmd,
        shell=shell,
        env=env,
        stdout=stdout,
        stderr=stderr,
    )
    return AdbProcess(proc, cmd=adb_cmd, serial=self.serial)

  def _execute_adb_and_process_stdout(
      self, name, args, shell, handler
  ) -> bytes:
    adb_cmd = self._construct_adb_cmd(name, args, shell=shell)
    err = self._execute_and_process_stdout(
        adb_cmd, shell=shell, handler=handler
    )
    return err

  def _parse_getprop_output(self, output):
    """Parses the raw output of `adb shell getprop` into a dictionary.

    Args:
      output: byte str, the raw output of the `adb shell getprop` call.

    Returns:
      dict, name-value pairs of the properties.
    """
    output = output.decode('utf-8', errors='ignore').replace('\r\n', '\n')
    results = {}
    for line in output.split(']\n'):
      if not line:
        continue
      try:
        name, value = line.split(': ', 1)
      except ValueError:
        logging.debug('Failed to parse adb getprop line %s', line)
        continue
      name = name.strip()[1:-1]
      # Remove any square bracket from either end of the value string.
      value = value.removeprefix('[')
      results[name] = value
    return results

  @property
  def current_user_id(self) -> int:
    """The integer ID of the current Android user.

    Some adb commands require specifying a user ID to work properly. Use
    this to get the current user ID.

    Note a "user" is not the same as an "account" in Android. See AOSP's
    documentation for details.
    https://source.android.com/devices/tech/admin/multi-user
    """
    sdk_int = int(self.getprop('ro.build.version.sdk'))
    if sdk_int >= 24:
      return int(self.shell(['am', 'get-current-user']))
    if sdk_int >= 21:
      user_info_str = self.shell(['dumpsys', 'user']).decode('utf-8')
      return int(re.findall(r'\{(\d+):', user_info_str)[0])
    # Multi-user is not supported in SDK < 21, only user 0 exists.
    return 0

  def connect(self, address) -> bytes:
    """Executes the `adb connect` command with proper status checking.

    Args:
      address: string, the address of the Android instance to connect to.

    Returns:
      The stdout content.

    Raises:
      AdbError: if the connection failed.
    """
    stdout = self._exec_adb_cmd(
        'connect', address, shell=False, timeout=None, stderr=None
    )
    if PATTERN_ADB_CONNECT_SUCCESS.match(stdout.decode('utf-8')) is None:
      raise AdbError(
          cmd=f'connect {address}', stdout=stdout, stderr='', ret_code=0
      )
    return stdout

  def getprop(self, prop_name, timeout=DEFAULT_GETPROP_TIMEOUT_SEC):
    """Get a property of the device.

    This is a convenience wrapper for `adb shell getprop xxx`.

    Args:
      prop_name: A string that is the name of the property to get.
      timeout: float, the number of seconds to wait before timing out.
          If not specified, the DEFAULT_GETPROP_TIMEOUT_SEC is used.

    Returns:
      A string that is the value of the property, or None if the property
      doesn't exist.
    """
    return (
        self.shell(['getprop', prop_name], timeout=timeout)
        .decode('utf-8')
        .strip()
    )

  def getprops(self, prop_names):
    """Get multiple properties of the device.

    This is a convenience wrapper for `adb shell getprop`. Use this to
    reduce the number of adb calls when getting multiple properties.

    Args:
      prop_names: list of strings, the names of the properties to get.

    Returns:
      A dict containing name-value pairs of the properties requested, if
      they exist.
    """
    attempts = DEFAULT_GETPROPS_ATTEMPTS
    results = {}
    for attempt in range(attempts):
      # The ADB getprop command can randomly return empty string, so try
      # multiple times. This value should always be non-empty if the device
      # in a working state.
      raw_output = self.shell(['getprop'], timeout=DEFAULT_GETPROP_TIMEOUT_SEC)
      properties = self._parse_getprop_output(raw_output)
      if properties:
        for name in prop_names:
          if name in properties:
            results[name] = properties[name]
        break
      # Don't call sleep on the last attempt.
      if attempt < attempts - 1:
        time.sleep(DEFAULT_GETPROPS_RETRY_SLEEP_SEC)
    return results

  def has_shell_command(self, command) -> bool:
    """Checks to see if a given check command exists on the device.

    Args:
      command: A string that is the name of the command to check.

    Returns:
      A boolean that is True if the command exists and False otherwise.
    """
    try:
      output = self.shell(['command', '-v', command]).decode('utf-8').strip()
      return command in output
    except AdbError:
      # If the command doesn't exist, then 'command -v' can return
      # an exit code > 1.
      return False

  def forward(self, args=None, shell=False) -> bytes:
    with ADB_PORT_LOCK:
      return self._exec_adb_cmd(
          'forward', args, shell, timeout=None, stderr=None
      )

  def reverse(self, args=None, shell=False) -> bytes:
    with ADB_PORT_LOCK:
      return self._exec_adb_cmd(
          'reverse', args, shell, timeout=None, stderr=None
      )

  def instrument(
      self, package, options=None, runner=None, handler=None
  ) -> bytes:
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
        options_string,
        package,
        runner,
    )
    logging.info(
        'AndroidDevice|%s: Executing adb shell %s',
        self.serial,
        instrumentation_command,
    )
    if handler is None:
      return self._exec_adb_cmd(
          'shell',
          instrumentation_command,
          shell=False,
          timeout=None,
          stderr=None,
      )
    else:
      return self._execute_adb_and_process_stdout(
          'shell', instrumentation_command, shell=False, handler=handler
      )

  def root(self) -> bytes:
    """Enables ADB root mode on the device.

    This method will retry to execute the command `adb root` when an
    AdbError occurs, since sometimes the error `adb: unable to connect
    for root: closed` is raised when executing `adb root` immediately after
    the device is booted to OS.

    Returns:
      A string that is the stdout of root command.

    Raises:
      AdbError: If the command exit code is not 0.
      AdbTimeoutError: If the command timed out.
    """
    retry_interval = ADB_ROOT_RETRY_ATTEMPT_INTERVAL_SEC
    for attempt in range(ADB_ROOT_RETRY_ATTEMPTS):
      try:
        return self._exec_adb_cmd(
            'root',
            args=None,
            shell=False,
            timeout=ADB_ROOT_ATTEMPT_TIMEOUT_SEC,
            stderr=None,
        )
      except (AdbError, AdbTimeoutError) as e:
        if attempt + 1 < ADB_ROOT_RETRY_ATTEMPTS:
          retry_reason = (
              f'Error "{e.stderr.decode("utf-8").strip()}" occurred'
              if isinstance(e, AdbError)
              else f'it timed out after {e.timeout} seconds'
          )
          logging.debug(
              'Retry the command "%s" since %s.',
              utils.cli_cmd_to_string(e.cmd),
              retry_reason,
          )

          # Buffer between "adb root" commands.
          time.sleep(retry_interval)
          retry_interval *= 2
        else:
          raise e

  def __getattr__(self, name):
    def adb_call(
        args=None,
        shell=False,
        timeout=None,
        stderr=None,
        spawn=False,
        stream=False,
        stdout=subprocess.PIPE,
        env=None,
    ):
      """Wrapper for an ADB command.

      Args:
        args: string or list of strings, arguments to the adb command.
          See subprocess.Popen() documentation.
        shell: bool, True to run this command through the system shell,
          False to invoke it directly. See subprocess.Popen() docs.
        timeout: float, the number of seconds to wait before timing out.
          If not specified, no timeout takes effect.
        stderr: a Byte stream, like io.BytesIO, or subprocess pipe.
        spawn: bool, True to spawn the process asynchronously and return
          an AdbProcess object.
        stream: bool, True to spawn the process and return a line generator.
        stdout: subprocess pipe or file handle for stdout when spawn=True
          or stream=True.
        env: dict, optional environment variables.

      Returns:
        bytes if spawn=False and stream=False.
        AdbProcess if spawn=True.
        Generator[str, None, None] if stream=True.

      Raises:
        ValueError: If timeout is specified when spawn=True, or if both
          spawn=True and stream=True are specified.
        AdbError: The adb command exit code is not 0 (sync mode).
        AdbTimeoutError: The adb command timed out.
      """
      if spawn and stream:
        raise ValueError('Cannot specify both spawn=True and stream=True.')

      if spawn:
        if timeout is not None:
          raise ValueError(
              'Timeout cannot be specified when spawn=True. '
              'Use AdbProcess.wait(timeout=...) instead.'
          )
        return self._spawn_cmd(
            name,
            args=args,
            shell=shell,
            stdout=stdout,
            stderr=stderr if stderr is not None else subprocess.PIPE,
            env=env,
        )

      if stream:
        proc = self._spawn_cmd(
            name,
            args=args,
            shell=shell,
            stdout=stdout,
            stderr=stderr if stderr is not None else subprocess.PIPE,
            env=env,
        )
        return proc.iter_lines(timeout=timeout)

      return self._exec_adb_cmd(
          name, args, shell=shell, timeout=timeout, stderr=stderr
      )

    return adb_call
