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
    # Reserved keywords for the config.
    key_mobly_params = "MoblyParams"
    key_mobly_params_log_path = "LogPath"
    # Top-level keywordss used in a test bed config.
    key_testbed = "TestBeds"
    key_testbed_name = "Name"
    key_testbed_controllers = "Controllers"
    key_testbed_test_params = "TestParams"
    # Internal keys, used internally to detach the internal var names from
    # keywords that define the config format.
    ikey_user_param = "user_params"
    ikey_testbed_name = "testbed_name"
    ikey_testbed_controllers = "controller_configs"
    ikey_logger = "log"
    ikey_logpath = "log_path"
    ikey_cli_args = "cli_args"


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
