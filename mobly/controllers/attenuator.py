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

import importlib
import logging

MOBLY_CONTROLLER_CONFIG_NAME = "Attenuator"
KEY_ADDRESS = "Address"
KEY_PORT = "Port"


def create(configs):
    objs = []
    for c in configs:
        attn_model = c["Model"]
        # Default to telnet.
        protocol = c.get("Protocol", "telnet")
        # Import the correct driver module for the attenuator device
        module_name = "mobly.controllers.attenuator_lib.%s" % attn_model
        module = importlib.import_module(module_name)
        # Create each
        path_cnt = c["PathCount"]
        attn_device = module.AttenuatorDevice(path_cnt)
        attn_device.model = attn_model
        insts = attn_device.open(c[KEY_ADDRESS], c[KEY_PORT])
        for i in range(path_cnt):
            path_name = None
            if "Paths" in c:
                try:
                    path_name = c["Paths"][i]
                except IndexError:
                    logging.error(
                        "No path specified for attenuation path %d.", i)
                    raise
            attn = AttenuatorPath(attn_device, idx=i, name=path_name)
            objs.append(attn)
    return objs


def destroy(objs):
    for attn_path in objs:
        attn_path.attn_device.close()


class Error(Exception):
    """This is the Exception class defined for all errors generated by
    Attenuator-related modules.
    """


class AttenuatorPath(object):
    """A convenience class that allows users to control each attenuator path
    separately as different objects, as opposed to passing in an index number
    to the functions of an attenuator device object.

    This decouples the test code from the actual attenuator device used in the
    physical test bed.

    For example, if a test needs to attenuate four signal paths, this allows the
    test to do:
        self.attenuation_paths[0].set_attn(50)
        self.attenuation_paths[1].set_attn(40)
    instead of:
        self.attenuators[0].set_attn(0, 50)
        self.attenuators[0].set_attn(1, 40)

    The benefit the former is that the physical test bed can use either four
    single-channel attenuators, or one four-channel attenuators. Whereas the
    latter forces the test bed to use a four-channel attenuator.
    """
    def __init__(self, attn_device, idx=0, name=None):
        self.model = attn_device.model
        self.attn_device = attn_device
        self.idx = idx
        if (self.idx >= attn_device.path_count):
            raise IndexError(
                "Attenuator index out of range for attenuator attn_device")

    def set_attn(self, value):
        """This function sets the attenuation of Attenuator.

        Args:
            value: This is a floating point value for nominal attenuation to be
                   set.
        """
        self.attn_device.set_attn(self.idx, value)

    def get_attn(self):
        """Gets the current attenuation setting of Attenuator.

        Returns:
            A float that is the current attenuation value.
        """

        return self.attn_device.get_attn(self.idx)

    def get_max_attn(self):
        """Gets the max attenuation supported by the Attenuator.

        Returns:
            A float that is the max attenuation value.
        """
        return self.attn_device.max_attn
