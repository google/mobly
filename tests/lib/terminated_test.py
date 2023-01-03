# Copyright 2022 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os
import platform
import signal

from mobly import base_test
from mobly import signals
from mobly import test_runner


class TerminatedTest(base_test.BaseTestClass):

  def test_terminated(self):
    # SIGTERM handler does not work on Windows. So just simulate the behaviour
    # for the purpose of this test.
    if platform.system() == 'Windows':
      logging.warning('Test received a SIGTERM. Aborting all tests.')
      raise signals.TestAbortAll('Test received a SIGTERM.')
    else:
      os.kill(os.getpid(), signal.SIGTERM)


if __name__ == '__main__':
  test_runner.main()
