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

from builtins import bytes

import logging
import mock
import os

DEFAULT_MOCK_PROPERTIES = {
    'ro.build.id': 'AB42',
    'ro.build.type': 'userdebug',
    'ro.build.product': 'FakeModel',
    'ro.build.version.codename': 'Z',
    'ro.build.version.sdk': '28',
    'ro.product.name': 'FakeModel',
    'ro.debuggable': '1',
    'sys.boot_completed': "1",
    'ro.build.characteristics': 'emulator,phone',
    'ro.hardware': 'marlin',
}


class Error(Exception):
  pass


def get_mock_ads(num):
  """Generates a list of mock AndroidDevice objects.

  The serial number of each device will be integer 0 through num - 1.

  Args:
    num: An integer that is the number of mock AndroidDevice objects to
      create.
  """
  ads = []
  for i in range(num):
    ad = mock.MagicMock(name="AndroidDevice", serial=str(i), h_port=None)
    ad.skip_logcat = False
    ads.append(ad)
  return ads


def get_all_instances():
  return get_mock_ads(5)


def get_instances(serials):
  ads = []
  for serial in serials:
    ad = mock.MagicMock(name="AndroidDevice", serial=serial, h_port=None)
    ads.append(ad)
  return ads


def get_instances_with_configs(dicts):
  return get_instances([d['serial'] for d in dicts])


def list_adb_devices():
  return [ad.serial for ad in get_mock_ads(5)]


class MockAdbProxy:
  """Mock class that swaps out calls to adb with mock calls."""

  def __init__(self,
               serial='',
               fail_br=False,
               fail_br_before_N=False,
               mock_properties=None,
               installed_packages=None,
               instrumented_packages=None):
    self.serial = serial
    self.fail_br = fail_br
    self.fail_br_before_N = fail_br_before_N
    self.getprops_call_count = 0
    if mock_properties is None:
      self.mock_properties = DEFAULT_MOCK_PROPERTIES.copy()
    else:
      self.mock_properties = mock_properties
    if installed_packages is None:
      installed_packages = []
    self.installed_packages = installed_packages
    if instrumented_packages is None:
      instrumented_packages = []
    self.installed_packages = installed_packages
    self.instrumented_packages = instrumented_packages

  def shell(self, params, timeout=None):
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
    elif 'pm list package' in params:
      packages = self.installed_packages + [
          package for package, _, _ in self.instrumented_packages
      ]
      return bytes('\n'.join(['package:%s' % package for package in packages]),
                   'utf-8')
    elif 'pm list instrumentation' in params:
      return bytes(
          '\n'.join([
              'instrumentation:%s/%s (target=%s)' % (package, runner, target)
              for package, runner, target in self.instrumented_packages
          ]), 'utf-8')
    elif 'which' in params:
      return b''

  def getprop(self, params):
    if params in self.mock_properties:
      return self.mock_properties[params]

  def getprops(self, params):
    self.getprops_call_count = self.getprops_call_count + 1
    return self.mock_properties

  def bugreport(self, args, shell=False, timeout=None):
    expected = os.path.join(
        logging.log_path, 'AndroidDevice%s' % self.serial, 'BugReports',
        'bugreport,test_something,%s,fakemodel,sometime' % self.serial)
    if expected not in args:
      raise Error('"Expected "%s", got "%s"' % (expected, args))

  def __getattr__(self, name):
    """All calls to the none-existent functions in adb proxy would
    simply return the adb command string.
    """

    def adb_call(*args, **kwargs):
      arg_str = ' '.join(str(elem) for elem in args)
      return arg_str

    return adb_call


class MockFastbootProxy:
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
