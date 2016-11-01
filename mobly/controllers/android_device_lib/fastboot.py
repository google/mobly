#!/usr/bin/env python3.4
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

from subprocess import Popen, PIPE


def exe_cmd(*cmds):
    """Executes commands in a new shell. Directing stderr to PIPE.

    This is fastboot's own exe_cmd because of its peculiar way of writing
    non-error info to stderr.

    Args:
        cmds: A sequence of commands and arguments.

    Returns:
        The output of the command run.

    Raises:
        Exception is raised if an error occurred during the command execution.
    """
    cmd = ' '.join(cmds)
    proc = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
    (out, err) = proc.communicate()
    if not err:
        return out
    return err


class FastbootProxy():
    """Proxy class for fastboot.

    For syntactic reasons, the '-' in fastboot commands need to be replaced
    with '_'. Can directly execute fastboot commands on an object:
    >> fb = FastbootProxy(<serial>)
    >> fb.devices() # will return the console output of "fastboot devices".
    """

    def __init__(self, serial=""):
        self.serial = serial
        if serial:
            self.fastboot_str = "fastboot -s {}".format(serial)
        else:
            self.fastboot_str = "fastboot"

    def _exec_fastboot_cmd(self, name, arg_str):
        return exe_cmd(' '.join((self.fastboot_str, name, arg_str)))

    def args(self, *args):
        return exe_cmd(' '.join((self.fastboot_str, ) + args))

    def __getattr__(self, name):
        def fastboot_call(*args):
            clean_name = name.replace('_', '-')
            arg_str = ' '.join(str(elem) for elem in args)
            return self._exec_fastboot_cmd(clean_name, arg_str)

        return fastboot_call
