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

import base64
import concurrent.futures
import datetime
import logging
import os
import platform
import portpicker
import psutil
import random
import re
import signal
import string
import subprocess
import time
import traceback

from mobly.controllers.android_device_lib import adb
# File name length is limited to 255 chars on some OS, so we need to make sure
# the file names we output fits within the limit.
MAX_FILENAME_LEN = 255
# Number of times to retry to get available port
MAX_PORT_ALLOCATION_RETRY = 50

ascii_letters_and_digits = string.ascii_letters + string.digits
valid_filename_chars = "-_." + ascii_letters_and_digits

GMT_to_olson = {
    "GMT-9": "America/Anchorage",
    "GMT-8": "US/Pacific",
    "GMT-7": "US/Mountain",
    "GMT-6": "US/Central",
    "GMT-5": "US/Eastern",
    "GMT-4": "America/Barbados",
    "GMT-3": "America/Buenos_Aires",
    "GMT-2": "Atlantic/South_Georgia",
    "GMT-1": "Atlantic/Azores",
    "GMT+0": "Africa/Casablanca",
    "GMT+1": "Europe/Amsterdam",
    "GMT+2": "Europe/Athens",
    "GMT+3": "Europe/Moscow",
    "GMT+4": "Asia/Baku",
    "GMT+5": "Asia/Oral",
    "GMT+6": "Asia/Almaty",
    "GMT+7": "Asia/Bangkok",
    "GMT+8": "Asia/Hong_Kong",
    "GMT+9": "Asia/Tokyo",
    "GMT+10": "Pacific/Guam",
    "GMT+11": "Pacific/Noumea",
    "GMT+12": "Pacific/Fiji",
    "GMT+13": "Pacific/Tongatapu",
    "GMT-11": "Pacific/Midway",
    "GMT-10": "Pacific/Honolulu"
}


class Error(Exception):
    """Raised when an error occurs in a util"""


def abs_path(path):
    """Resolve the '.' and '~' in a path to get the absolute path.

    Args:
        path: The path to expand.

    Returns:
        The absolute path of the input path.
    """
    return os.path.abspath(os.path.expanduser(path))


def create_dir(path):
    """Creates a directory if it does not exist already.

    Args:
        path: The path of the directory to create.
    """
    full_path = abs_path(path)
    if not os.path.exists(full_path):
        os.makedirs(full_path)


def create_alias(target_path, alias_path):
    """Creates an alias at 'alias_path' pointing to the file 'target_path'.

    On Unix, this is implemented via symlink. On Windows, this is done by
    creating a Windows shortcut file.

    Args:
        target_path: Destination path that the alias should point to.
        alias_path: Path at which to create the new alias.
    """
    if platform.system() == 'Windows' and not alias_path.endswith('.lnk'):
        alias_path += '.lnk'
    if os.path.lexists(alias_path):
        os.remove(alias_path)
    if platform.system() == 'Windows':
        from win32com import client
        shell = client.Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(alias_path)
        shortcut.Targetpath = target_path
        shortcut.save()
    else:
        os.symlink(target_path, alias_path)


def get_current_epoch_time():
    """Current epoch time in milliseconds.

    Returns:
        An integer representing the current epoch time in milliseconds.
    """
    return int(round(time.time() * 1000))


def get_current_human_time():
    """Returns the current time in human readable format.

    Returns:
        The current time stamp in Month-Day-Year Hour:Min:Sec format.
    """
    return time.strftime("%m-%d-%Y %H:%M:%S ")


def epoch_to_human_time(epoch_time):
    """Converts an epoch timestamp to human readable time.

    This essentially converts an output of get_current_epoch_time to an output
    of get_current_human_time

    Args:
        epoch_time: An integer representing an epoch timestamp in milliseconds.

    Returns:
        A time string representing the input time.
        None if input param is invalid.
    """
    if isinstance(epoch_time, int):
        try:
            d = datetime.datetime.fromtimestamp(epoch_time / 1000)
            return d.strftime("%m-%d-%Y %H:%M:%S ")
        except ValueError:
            return None


def get_timezone_olson_id():
    """Return the Olson ID of the local (non-DST) timezone.

    Returns:
        A string representing one of the Olson IDs of the local (non-DST)
        timezone.
    """
    tzoffset = int(time.timezone / 3600)
    gmt = None
    if tzoffset <= 0:
        gmt = "GMT+{}".format(-tzoffset)
    else:
        gmt = "GMT-{}".format(tzoffset)
    return GMT_to_olson[gmt]


def find_files(paths, file_predicate):
    """Locate files whose names and extensions match the given predicate in
    the specified directories.

    Args:
        paths: A list of directory paths where to find the files.
        file_predicate: A function that returns True if the file name and
          extension are desired.

    Returns:
        A list of files that match the predicate.
    """
    file_list = []
    for path in paths:
        p = abs_path(path)
        for dirPath, _, fileList in os.walk(p):
            for fname in fileList:
                name, ext = os.path.splitext(fname)
                if file_predicate(name, ext):
                    file_list.append((dirPath, name, ext))
    return file_list


def load_file_to_base64_str(f_path):
    """Loads the content of a file into a base64 string.

    Args:
        f_path: full path to the file including the file name.

    Returns:
        A base64 string representing the content of the file in utf-8 encoding.
    """
    path = abs_path(f_path)
    with open(path, 'rb') as f:
        f_bytes = f.read()
        base64_str = base64.b64encode(f_bytes).decode("utf-8")
        return base64_str


def find_field(item_list, cond, comparator, target_field):
    """Finds the value of a field in a dict object that satisfies certain
    conditions.

    Args:
        item_list: A list of dict objects.
        cond: A param that defines the condition.
        comparator: A function that checks if an dict satisfies the condition.
        target_field: Name of the field whose value to be returned if an item
            satisfies the condition.

    Returns:
        Target value or None if no item satisfies the condition.
    """
    for item in item_list:
        if comparator(item, cond) and target_field in item:
            return item[target_field]
    return None


def rand_ascii_str(length):
    """Generates a random string of specified length, composed of ascii letters
    and digits.

    Args:
        length: The number of characters in the string.

    Returns:
        The random string generated.
    """
    letters = [random.choice(ascii_letters_and_digits) for _ in range(length)]
    return ''.join(letters)


# Thead/Process related functions.
def concurrent_exec(func, param_list):
    """Executes a function with different parameters pseudo-concurrently.

    This is basically a map function. Each element (should be an iterable) in
    the param_list is unpacked and passed into the function. Due to Python's
    GIL, there's no true concurrency. This is suited for IO-bound tasks.

    Args:
        func: The function that parforms a task.
        param_list: A list of iterables, each being a set of params to be
            passed into the function.

    Returns:
        A list of return values from each function execution. If an execution
        caused an exception, the exception object will be the corresponding
        result.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        # Start the load operations and mark each future with its params
        future_to_params = {executor.submit(func, *p): p for p in param_list}
        return_vals = []
        for future in concurrent.futures.as_completed(future_to_params):
            params = future_to_params[future]
            try:
                return_vals.append(future.result())
            except Exception as exc:
                print("{} generated an exception: {}".format(
                    params, traceback.format_exc()))
                return_vals.append(exc)
        return return_vals


def _assert_subprocess_running(proc):
    """Checks if a subprocess has terminated on its own.

    Args:
        proc: A subprocess returned by subprocess.Popen.

    Raises:
        Error is raised if the subprocess has stopped.
    """
    ret = proc.poll()
    if ret is not None:
        out, err = proc.communicate()
        raise Error("Process %d has terminated. ret: %d, stderr: %s,"
                    " stdout: %s" % (proc.pid, ret, err, out))


def start_standing_subprocess(cmd, check_health_delay=0, shell=False):
    """Starts a long-running subprocess.

    This is not a blocking call and the subprocess started by it should be
    explicitly terminated with stop_standing_subprocess.

    For short-running commands, you should use subprocess.check_call, which
    blocks.

    You can specify a health check after the subprocess is started to make sure
    it did not stop prematurely.

    Args:
        cmd: string, the command to start the subprocess with.
        check_health_delay: float, the number of seconds to wait after the
                            subprocess starts to check its health. Default is 0,
                            which means no check.
        shell: bool, True to run this command through the system shell,
            False to invoke it directly. See subprocess.Proc() docs.

    Returns:
        The subprocess that was started.
    """
    logging.debug('Start standing subprocess with cmd: %s', cmd)
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=shell)
    logging.debug('Start standing subprocess with cmd: %s', cmd)
    # Leaving stdin open causes problems for input, e.g. breaking the
    # code.inspect() shell (http://stackoverflow.com/a/25512460/1612937), so
    # explicitly close it assuming it is not needed for standing subprocesses.
    proc.stdin.close()
    proc.stdin = None
    if check_health_delay > 0:
        time.sleep(check_health_delay)
        _assert_subprocess_running(proc)
    return proc


def stop_standing_subprocess(proc, kill_signal=signal.SIGTERM):
    """Stops a subprocess started by start_standing_subprocess.

    Before killing the process, we check if the process is running, if it has
    terminated, Error is raised.

    Catches and ignores the PermissionError which only happens on Macs.

    Args:
        proc: Subprocess to terminate.

    Raises:
        Error: if the subprocess could not be stopped.
    """
    pid = proc.pid
    logging.debug('Stop standing subprocess %d', pid)
    _assert_subprocess_running(proc)
    process = psutil.Process(pid)
    success = True
    try:
        children = process.children(recursive=True)
    except AttributeError:
        # Handle versions <3.0.0 of psutil.
        children = process.get_children(recursive=True)
    for child in children:
        try:
            child.kill()
            child.wait(timeout=10)
        except:
            success = False
            logging.exception('Failed to kill standing subprocess %d',
                              child.pid)
    try:
        process.kill()
        process.wait(timeout=10)
    except:
        success = False
        logging.exception('Failed to kill standing subprocess %d', pid)
    if not success:
        raise Error('Some standing subprocess failed to die')


def wait_for_standing_subprocess(proc, timeout=None):
    """Waits for a subprocess started by start_standing_subprocess to finish
    or times out.

    Propagates the exception raised by the subprocess.wait(.) function.
    The subprocess.TimeoutExpired exception is raised if the process timed-out
    rather then terminating.

    If no exception is raised: the subprocess terminated on its own. No need
    to call stop_standing_subprocess() to kill it.

    If an exception is raised: the subprocess is still alive - it did not
    terminate. Either call stop_standing_subprocess() to kill it, or call
    wait_for_standing_subprocess() to keep waiting for it to terminate on its
    own.

    Args:
        p: Subprocess to wait for.
        timeout: An integer number of seconds to wait before timing out.
    """
    proc.wait(timeout)


def get_available_host_port():
    """Gets a host port number available for adb forward.

    Returns:
        An integer representing a port number on the host available for adb
        forward.

    Raises:
      Error: when no port is found after MAX_PORT_ALLOCATION_RETRY times.
    """
    for _ in range(MAX_PORT_ALLOCATION_RETRY):
        port = portpicker.PickUnusedPort()
        # Make sure adb is not using this port so we don't accidentally
        # interrupt ongoing runs by trying to bind to the port.
        if port not in adb.list_occupied_adb_ports():
            return port
    raise Error('Failed to find available port after {} retries'.format(
        MAX_PORT_ALLOCATION_RETRY))


def grep(regex, output):
    """Similar to linux's `grep`, this returns the line in an output stream
    that matches a given regex pattern.

    It does not rely on the `grep` binary and is not sensitive to line endings,
    so it can be used cross-platform.

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
