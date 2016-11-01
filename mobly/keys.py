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

import enum
"""This module has the global key values that are used across framework
modules.
"""


class Config(enum.Enum):
    """Enum values for test config related lookups.
    """
    # Keys used to look up values from test config files.
    # These keys define the wording of test configs and their internal
    # references.
    key_log_path = "logpath"
    key_testbed = "testbed"
    key_testbed_name = "name"
    key_config_path = "configpath"
    key_test_paths = "testpaths"
    key_port = "Port"
    key_address = "Address"
    # Config names for controllers packaged in Mobly.
    key_android_device = "AndroidDevice"
    key_iperf_server = "IPerfServer"
    key_monsoon = "Monsoon"
    key_sniffer = "Sniffer"
    # Internal keys, used internally, not exposed to user's config files.
    ikey_user_param = "user_params"
    ikey_testbed_name = "testbed_name"
    ikey_logger = "log"
    ikey_logpath = "log_path"
    ikey_cli_args = "cli_args"
    # module name of controllers packaged in Mobly.
    m_key_monsoon = "monsoon"
    m_key_android_device = "android_device"
    m_key_iperf_server = "iperf_server"
    m_key_sniffer = "sniffer"

    # A list of keys whose values in configs should not be passed to test
    # classes without unpacking first.
    reserved_keys = (key_testbed, key_log_path, key_test_paths)

    # Controller names packaged with Mobly.
    builtin_controller_names = [
        key_android_device, key_iperf_server, key_monsoon,
        key_sniffer
    ]


def get_name_by_value(value):
    for name, member in Config.__members__.items():
        if member.value == value:
            return name
    return None


def get_internal_value(external_value):
    """Translates the value of an external key to the value of its
    corresponding internal key.
    """
    return value_to_value(external_value, "i%s")


def get_module_name(name_in_config):
    """Translates the name of a controller in config file to its module name.
    """
    return value_to_value(name_in_config, "m_%s")


def value_to_value(ref_value, pattern):
    """Translates the value of a key to the value of its corresponding key. The
    corresponding key is chosen based on the variable name pattern.
    """
    ref_key_name = get_name_by_value(ref_value)
    if not ref_key_name:
        return None
    target_key_name = pattern % ref_key_name
    try:
        return getattr(Config, target_key_name).value
    except AttributeError:
        return None
