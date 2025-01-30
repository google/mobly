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

import logging
from subprocess import PIPE

from mobly import utils


class FastbootProxy:
  """Proxy class for fastboot.

  For syntactic reasons, the '-' in fastboot commands need to be replaced
  with '_'. Can directly execute fastboot commands on an object:
  >> fb = FastbootProxy(<serial>)
  >> fb.devices() # will return the console output of "fastboot devices".
  """

  def __init__(self, serial='', timeout=1200):
    self.serial = serial
    self._timeout = timeout

  def fastboot_str(self):
    if self.serial:
      return 'fastboot -s {}'.format(self.serial)
    return 'fastboot'

  def _exec_cmd_timeout(self, *cmds):
    """Executes commands in a new shell. Directing stderr to PIPE, with timeout.

    This is fastboot's own exec_cmd function because of its peculiar way of
    writing non-error info to stderr.

    Args:
      *cmds: The commands to execute.

    Returns:
      The output of the command run, in bytes.
    """
    cmd = ' '.join(cmds)
    (ret, out, err) = utils.run_command(
        cmd=cmd,
        stdout=PIPE,
        stderr=PIPE,
        shell=True,
        timeout=self._timeout,
    )
    logging.debug(
        'cmd: %s, stdout: %s, stderr: %s, ret: %s',
        utils.cli_cmd_to_string(cmds),
        out,
        err,
        ret,
    )
    if not err:
      return out
    return err

  def _exec_fastboot_cmd(self, name, arg_str):
    return self._exec_cmd_timeout(
        ' '.join((self.fastboot_str(), name, arg_str))
    )

  def args(self, *args):
    return self._exec_cmd_timeout(' '.join((self.fastboot_str(),) + args))

  def __getattr__(self, name):
    def fastboot_call(*args):
      clean_name = name.replace('_', '-')
      arg_str = ' '.join(str(elem) for elem in args)
      return self._exec_fastboot_cmd(clean_name, arg_str)

    return fastboot_call
