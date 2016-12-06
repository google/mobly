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
$ sl4a_client
>>> s.getBuildID()
u'N2F52'
"""
from __future__ import print_function

import argparse
import code
import pprint
import sys

from mobly.controllers import android_device

# Dictionary of variables available by default to the console shell.
gConsoleEnv = {}


def _start_console(banner=None):
    code.interact(banner=banner, local=gConsoleEnv)


def _connect():
    ad = gConsoleEnv['ad']
    (droid, ed) = ad.get_droid()
    gConsoleEnv['s'] = droid
    gConsoleEnv['sl4a'] = droid
    gConsoleEnv['ed'] = ed
    gConsoleEnv['ed'].start()
    print('Connection succeeded')


def main(serial):
    if not serial:
        serials = android_device.list_adb_devices()
        if len(serials) != 1:
            print('ERROR: Expected 1 phone, but %d found. Use the -s flag.' %
                      len(serials),
                  file=sys.stderr)
            sys.exit(1)
        serial = serials[0]
    ads = android_device.get_instances([serial])
    assert len(ads) == 1

    # Set up initial console environment
    gConsoleEnv.update({
        'ad': ads[0],
        'pprint': pprint.pprint,
    })
    _connect()
    _start_console("""
Connected to {}. Call methods against:
    ad (android_device.AndroidDevice)
    sl4a or s (SL4A)
    ed (EventDispatcher)
""".format(serial))
    gConsoleEnv['ad'].terminate_all_sessions()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Interactive client for sl4a.')
    parser.add_argument(
        '-s', '--serial',
        help=
        'Device serial to connect to (if more than one device is connected)')
    args = parser.parse_args()
    main(args.serial)
