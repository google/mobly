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

from builtins import str

import os
import sys

from mobly import keys
from mobly import utils

# An environment variable defining the base location for Mobly logs.
_ENV_MOBLY_LOGPATH = 'MOBLY_LOGPATH'


class MoblyConfigError(Exception):
    """Raised when there is a problem in test configuration file."""


def _validate_test_config(test_config):
    """Validates the raw configuration loaded from the config file.

    Making sure all the required fields exist.
    """
    for k in keys.Config.reserved_keys.value:
        if k not in test_config:
            raise MoblyConfigError("Required key %s missing in test config." % k)


def _validate_testbed_name(name):
    """Validates the name of a test bed.

    Since test bed names are used as part of the test run id, it needs to meet
    certain requirements.

    Args:
        name: The test bed's name specified in config file.

    Raises:
        If the name does not meet any criteria, MoblyConfigError is raised.
    """
    if not name:
        raise MoblyConfigError("Test bed names can't be empty.")
    if not isinstance(name, str):
        raise MoblyConfigError("Test bed names have to be string.")
    for l in name:
        if l not in utils.valid_filename_chars:
            raise MoblyConfigError(
                "Char '%s' is not allowed in test bed names." % l)


def _validate_testbed_configs(testbed_configs):
    """Validates the testbed configurations.

    Args:
        testbed_configs: A list of testbed configuration json objects.

    Raises:
        If any part of the configuration is invalid, MoblyConfigError is raised.
    """
    seen_names = set()
    # Cross checks testbed configs for resource conflicts.
    for config in testbed_configs:
        # Check for conflicts between multiple concurrent testbed configs.
        # No need to call it if there's only one testbed config.
        name = config[keys.Config.key_testbed_name.value]
        _validate_testbed_name(name)
        # Test bed names should be unique.
        if name in seen_names:
            raise MoblyConfigError("Duplicate testbed name %s found." % name)
        seen_names.add(name)


def _verify_test_class_name(test_cls_name):
    if not test_cls_name.endswith("Test"):
        raise MoblyConfigError(
            ("Requested test class '%s' does not follow the test class naming "
             "convention *Test.") % test_cls_name)


def gen_term_signal_handler(test_runners):
    def termination_sig_handler(signal_num, frame):
        for t in test_runners:
            t.stop()
        sys.exit(1)
    return termination_sig_handler


def _parse_one_test_specifier(item):
    """Parse one test specifier from command line input.

    This also verifies that the test class name and test case names follow
    Mobly's naming conventions. A test class name has to end with "Test"; a test
    case name has to start with "test".

    Args:
        item: A string that specifies a test class or test cases in one test
            class to run.

    Returns:
        A tuple of a string and a list of strings. The string is the test class
        name, the list of strings is a list of test case names. The list can be
        None.
    """
    tokens = item.split(':')
    if len(tokens) > 2:
        raise MoblyConfigError("Syntax error in test specifier %s" % item)
    if len(tokens) == 1:
        # This should be considered a test class name
        test_cls_name = tokens[0]
        _verify_test_class_name(test_cls_name)
        return (test_cls_name, None)
    elif len(tokens) == 2:
        # This should be considered a test class name followed by
        # a list of test case names.
        test_cls_name, test_case_names = tokens
        clean_names = []
        _verify_test_class_name(test_cls_name)
        for elem in test_case_names.split(','):
            test_case_name = elem.strip()
            if not test_case_name.startswith("test_"):
                raise MoblyConfigError(("Requested test case '%s' in test class "
                                 "'%s' does not follow the test case "
                                 "naming convention test_*.") %
                                (test_case_name, test_cls_name))
            clean_names.append(test_case_name)
        return (test_cls_name, clean_names)


def parse_test_list(test_list):
    """Parse user provided test list into internal format for test_runner.

    Args:
        test_list: A list of test classes/cases.
    """
    result = []
    for elem in test_list:
        result.append(_parse_one_test_specifier(elem))
    return result


def load_test_config_file(test_config_path, tb_filters=None):
    """Processes the test configuration file provied by user.

    Loads the configuration file into a json object, unpacks each testbed
    config into its own json object, and validate the configuration in the
    process.

    Args:
        test_config_path: Path to the test configuration file.
        tb_filters: A subset of test bed names to be pulled from the config
                    file. If None, then all test beds will be selected.

    Returns:
        A list of test configuration json objects to be passed to
        test_runner.TestRunner.
    """
    configs = utils.load_config(test_config_path)
    if tb_filters:
        tbs = []
        for tb in configs[keys.Config.key_testbed.value]:
            if tb[keys.Config.key_testbed_name.value] in tb_filters:
                tbs.append(tb)
        if len(tbs) != len(tb_filters):
            raise MoblyConfigError(
                ("Expect to find %d test bed configs, found %d. Check if"
                 " you have the correct test bed names.") %
                (len(tb_filters), len(tbs)))
        configs[keys.Config.key_testbed.value] = tbs

    if (not keys.Config.key_log_path.value in configs and
            _ENV_MOBLY_LOGPATH in os.environ):
        print('Using environment log path: %s' %
              (os.environ[_ENV_MOBLY_LOGPATH]))
        configs[keys.Config.key_log_path.value] = os.environ[_ENV_MOBLY_LOGPATH]

    _validate_test_config(configs)
    _validate_testbed_configs(configs[keys.Config.key_testbed.value])
    k_log_path = keys.Config.key_log_path.value
    configs[k_log_path] = utils.abs_path(configs[k_log_path])
    config_path, _ = os.path.split(utils.abs_path(test_config_path))
    configs[keys.Config.key_config_path] = config_path
    # Unpack testbeds into separate json objects.
    beds = configs.pop(keys.Config.key_testbed.value)
    config_jsons = []
    # TODO: See if there is a better way to do this: b/29836695
    config_path, _ = os.path.split(utils.abs_path(test_config_path))
    configs[keys.Config.key_config_path] = config_path
    for original_bed_config in beds:
        new_test_config = dict(configs)
        new_test_config[keys.Config.key_testbed.value] = original_bed_config
        # Keys in each test bed config will be copied to a level up to be
        # picked up for user_params. If the key already exists in the upper
        # level, the local one defined in test bed config overwrites the
        # general one.
        new_test_config.update(original_bed_config)
        config_jsons.append(new_test_config)
    return config_jsons


def parse_test_file(fpath):
    """Parses a test file that contains test specifiers.

    Args:
        fpath: A string that is the path to the test file to parse.

    Returns:
        A list of strings, each is a test specifier.
    """
    with open(fpath, 'r') as f:
        tf = []
        for line in f:
            line = line.strip()
            if not line:
                continue
            if len(tf) and (tf[-1].endswith(':') or tf[-1].endswith(',')):
                tf[-1] += line
            else:
                tf.append(line)
        return tf
