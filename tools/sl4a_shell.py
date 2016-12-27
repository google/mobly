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

"""Tool to interactively call sl4a methods.

SL4A (Scripting Layer for Android) is an RPC service exposing API calls on
Android.

Original version: https://github.com/damonkohler/sl4a

Fork in AOSP (can make direct system privileged calls):
https://android.googlesource.com/platform/external/sl4a/

Also allows access to Event Dispatcher, which allows waiting for asynchronous
actions. For more information see the Mobly codelab:
https://github.com/google/mobly#event-dispatcher

Usage:
$ sl4a_shell
>>> s.getBuildID()
u'N2F52'
"""

import argparse

from mobly.controllers.android_device_lib import jsonrpc_shell_base


class Sl4aShell(jsonrpc_shell_base.JsonRpcShellBase):
    def _start_services(self, console_env):
        """Overrides superclass."""
        self._ad.start_services()
        console_env['s'] = self._ad.sl4a
        console_env['sl4a'] = self._ad.sl4a
        console_env['ed'] = self._ad.ed

    def _get_banner(self, serial):
        lines = ['Connected to %s.' % serial,
                 'Call methods against:',
                 '    ad (android_device.AndroidDevice)',
                 '    sl4a or s (SL4A)',
                 '    ed (EventDispatcher)']
        return '\n'.join(lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Interactive client for sl4a.')
    parser.add_argument(
        '-s', '--serial',
        help=
        'Device serial to connect to (if more than one device is connected)')
    args = parser.parse_args()
    Sl4aShell().main(args.serial)
