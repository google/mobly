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

import shutil
from mobly.controllers import sniffer
from mobly.controllers.sniffer_lib.local import local_base


class Sniffer(local_base.SnifferLocalBase):
  """This class defines a sniffer which uses tshark as its back-end"""

  def __init__(self, config_path, logger, base_configs=None):
    """See base class documentation"""
    self._executable_path = None

    super().__init__(config_path, logger, base_configs=base_configs)

    self._executable_path = shutil.which('tshark') or shutil.which(
        '/usr/local/bin/tshark'
    )
    if self._executable_path is None:
      raise sniffer.SnifferError(
          "Cannot find a path to the 'tshark' "
          "executable (or to '/usr/local/bin/tshark')"
      )

  def get_descriptor(self):
    """See base class documentation"""
    return f'local-tshark-{self._interface}'

  def get_subtype(self):
    """See base class documentation"""
    return 'tshark'

  def _get_command_line(
      self, additional_args=None, duration=None, packet_count=None
  ):
    cmd = f'{self._executable_path} -i {self._interface} -w {self._temp_capture_file_path}'
    if duration is not None:
      cmd = f'{cmd} -a duration:{duration}'
    if packet_count is not None:
      cmd = f'{cmd} -c {packet_count}'
    if additional_args is not None:
      cmd = f'{cmd} {additional_args}'
    return cmd
