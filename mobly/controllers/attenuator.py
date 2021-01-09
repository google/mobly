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
"""Controller module for attenuators.

Sample Config:

.. code-block:: python

  "Attenuator": [
    {
      "address": "192.168.1.12",
      "port": 23,
      "model": "minicircuits",
      "paths": ["AP1-2G", "AP1-5G", "AP2-2G", "AP2-5G"]
    },
    {
      "address": "192.168.1.14",
      "port": 23,
      "model": "minicircuits",
      "paths": ["AP-DUT"]
    }
  ]
"""
import importlib
import logging

MOBLY_CONTROLLER_CONFIG_NAME = "Attenuator"
# Keys used inside a config dict for attenuator.
# Keys for making the connection to the attenuator device. Right now we only
# use telnet lib. This can be refactored when the need for a different
# communication protocol arises.
KEY_ADDRESS = "address"
KEY_PORT = "port"
# A string that is the model of the attenuator used. This is essentially the
# module name for the underlying driver for the attenuator hardware.
KEY_MODEL = "model"
# A list of strings, each describing what's the connected to this attenuation
# path
KEY_PATHS = "paths"

PACKAGE_PATH_TEMPLATE = "mobly.controllers.attenuator_lib.%s"


def create(configs):
  objs = []
  for config in configs:
    _validate_config(config)
    attenuator_model = config[KEY_MODEL]
    # Import the correct driver module for the attenuator device
    module_name = PACKAGE_PATH_TEMPLATE % attenuator_model
    module = importlib.import_module(module_name)
    # Create each
    attenuation_device = module.AttenuatorDevice(
        path_count=len(config[KEY_PATHS]))
    attenuation_device.model = attenuator_model
    attenuation_device.open(config[KEY_ADDRESS], config[KEY_PORT])
    for idx, path_name in enumerate(config[KEY_PATHS]):
      path = AttenuatorPath(attenuation_device, idx=idx, name=path_name)
      objs.append(path)
  return objs


def destroy(objs):
  for attenuation_path in objs:
    attenuation_path.attenuation_device.close()


class Error(Exception):
  """This is the Exception class defined for all errors generated by Attenuator-related modules."""


def _validate_config(config):
  """Verifies that a config dict for an attenuator device is valid.

  Args:
    config: A dict that is the configuration for an attenuator device.

  Raises:
    attenuator.Error: A config is not valid.
  """
  required_keys = [KEY_ADDRESS, KEY_MODEL, KEY_PORT, KEY_PATHS]
  for key in required_keys:
    if key not in config:
      raise Error("Required key %s missing from config %s" % (key, config))


class AttenuatorPath(object):
  """A convenience class that allows users to control attenuator device object.

  A convenience class that allows users to control each attenuator path
  separately as different objects, as opposed to passing in an index number
  to the functions of an attenuator device object.

  This decouples the test code from the actual attenuator device used in the
  physical test bed.

  For example, if a test needs to attenuate four signal paths, this allows the
  test to do:

  .. code-block:: python

    self.attenuation_paths[0].set_atten(50)
    self.attenuation_paths[1].set_atten(40)

  instead of:

  .. code-block:: python

    self.attenuators[0].set_atten(0, 50)
    self.attenuators[0].set_atten(1, 40)

  The benefit the former is that the physical test bed can use either four
  single-channel attenuators, or one four-channel attenuators. Whereas the
  latter forces the test bed to use a four-channel attenuator.
  """

  def __init__(self, attenuation_device, idx=0, name=None):
    self.model = attenuation_device.model
    self.attenuation_device = attenuation_device
    self.idx = idx
    if self.idx >= attenuation_device.path_count:
      raise IndexError("Attenuator index out of range!")

  def set_atten(self, value):
    """This function sets the attenuation of Attenuator.

    Args:
      value: This is a floating point value for nominal attenuation to be set.
        Unit is db.
    """
    self.attenuation_device.set_atten(self.idx, value)

  def get_atten(self):
    """Gets the current attenuation setting of Attenuator.

    Returns:
      A float that is the current attenuation value. Unit is db.
    """
    return self.attenuation_device.get_atten(self.idx)

  def get_max_atten(self):
    """Gets the max attenuation supported by the Attenuator.

    Returns:
      A float that is the max attenuation value.
    """
    return self.attenuation_device.max_atten
