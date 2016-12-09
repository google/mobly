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

# This module has common mock objects and functions used in unit tests for
# mobly.controllers.android_device module.

import logging
import mock
import os


def get_mock_ads(num):
    """Generates a list of mock AndroidDevice objects.

    The serial number of each device will be integer 0 through num - 1.

    Args:
        num: An integer that is the number of mock AndroidDevice objects to
            create.
    """
    ads = []
    for i in range(num):
        ad = mock.MagicMock(name="AndroidDevice", serial=i, h_port=None)
        ads.append(ad)
    return ads


def get_all_instances():
    return get_mock_ads(5)


def list_adb_devices():
    return [ad.serial for ad in get_mock_ads(5)]


class MockAdbProxy(object):
    """Mock class that swaps out calls to adb with mock calls."""

    def __init__(self, serial, fail_br=False, fail_br_before_N=False):
        self.serial = serial
        self.fail_br = fail_br
        self.fail_br_before_N = fail_br_before_N

    def shell(self, params):
        if params == "id -u":
            return b"root"
        elif params == "bugreportz":
            if self.fail_br:
                return b"OMG I died!\n"
            return b'OK:/path/bugreport.zip\n'
        elif params == "bugreportz -v":
            if self.fail_br_before_N:
                return b"/system/bin/sh: bugreportz: not found"
            return b'1.1'

    def getprop(self, params):
        if params == "ro.build.id":
            return "AB42"
        elif params == "ro.build.type":
            return "userdebug"
        elif params == "ro.build.product" or params == "ro.product.name":
            return "FakeModel"
        elif params == "sys.boot_completed":
            return "1"
        elif params == "ro.build.type":
            return "userdebug"

    def bugreport(self, params):
        expected = os.path.join(logging.log_path,
                                "AndroidDevice%s" % self.serial, "BugReports",
                                "test_something,sometime,%s" % (self.serial))
        assert expected in params, "Expected '%s', got '%s'." % (expected,
                                                                 params)

    def __getattr__(self, name):
        """All calls to the none-existent functions in adb proxy would
        simply return the adb command string.
        """
        def adb_call(*args):
            arg_str = ' '.join(str(elem) for elem in args)
            return arg_str

        return adb_call


class MockFastbootProxy(object):
    """Mock class that swaps out calls to adb with mock calls."""

    def __init__(self, serial):
        self.serial = serial

    def devices(self):
        return b"xxxx device\nyyyy device"

    def __getattr__(self, name):
        def fastboot_call(*args):
            arg_str = ' '.join(str(elem) for elem in args)
            return arg_str
        return fastboot_call
