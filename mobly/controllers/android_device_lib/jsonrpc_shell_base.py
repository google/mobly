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

"""Shared library for frontends to jsonrpc servers."""
from __future__ import print_function

import code
import pprint
import sys

from mobly.controllers import android_device


class Error(Exception):
  pass


class JsonRpcShellBase(object):
    def _start_services(self, console_env):
        """Starts the services needed by this client and adds them to console_env.
  
        Must be implemented by subclasses.
        """
        raise NotImplemented()

    def _get_banner(self, serial):
        """Returns the user-friendly banner message to print before the console.
  
        Must be implemented by subclasses.
        """
        raise NotImplemented()

    def load_device(self, serial=None):
        """Creates an AndroidDevice for the given serial number.

        If no serial is given, it will be read from 'adb devices' if there is
        only one.
        """
        serials = android_device.list_adb_devices()
        if (not serial) and len(serials) != 1:
            raise Error('Expected 1 phone, but %d found. Use the -s flag.' %
                        len(serials))
        serial = serials[0]
        if serial not in serials:
            raise Error("Device '%s' is not found by adb." % serial)
        ads = android_device.get_instances([serial])
        assert len(ads) == 1
        self._ad = ads[0]

    def start_console(self):
        # Set up initial console environment
        console_env = {
            'ad': self._ad,
            'pprint': pprint.pprint,
        }

        # Start the services
        self._start_services(console_env)

        # Start the console
        console_banner = self._get_banner(self._ad.serial)
        code.interact(banner=console_banner, local=console_env)

        # Tear everything down
        self._ad.stop_services()

    def main(self, serial=None):
        try:
            self.load_device(serial)
        except Error as e:
            print('ERROR: %s' % e, file=sys.stderr)
            sys.exit(1)
        self.start_console()
