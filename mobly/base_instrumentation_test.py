# Copyright 2017 Google Inc.
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

import logging
import mobly.controllers.android_device

from collections import defaultdict
from enum import Enum
from mobly import records
from mobly import signals
from mobly.base_test import BaseTestClass


class _InstrumentationStructurePrefixes(object):
    STATUS = 'INSTRUMENTATION_STATUS:'
    STATUS_CODE = 'INSTRUMENTATION_STATUS_CODE:'
    RESULT = 'INSTRUMENTATION_RESULT:'
    CODE = 'INSTRUMENTATION_CODE:'
    FAILED = 'INSTRUMENTATION_FAILED:'


class _InstrumentationKnownStatusKeys(object):
    CLASS = 'class'
    ERROR = 'Error'
    STACK = 'stack'
    TEST = 'test'
    STREAM = 'stream'


class _InstrumentationStatusCodes(object):
    UNKNOWN = None
    OK = '0'
    START = '1'
    IN_PROGRESS = '2'
    ERROR = '-1'
    FAILURE = '-2'
    IGNORED = '-3'
    ASSUMPTION_FAILURE = '-4'


class _InstrumentationStatusCodeCategories(object):
    TIMING = [
        _InstrumentationStatusCodes.START,
        _InstrumentationStatusCodes.IN_PROGRESS,
    ]
    PASS = [
        _InstrumentationStatusCodes.OK,
    ]
    FAIL = [
        _InstrumentationStatusCodes.ERROR,
        _InstrumentationStatusCodes.FAILURE,
    ]
    SKIPPED = [
        _InstrumentationStatusCodes.IGNORED,
        _InstrumentationStatusCodes.ASSUMPTION_FAILURE,
    ]


class _InstrumentationKnownResultKeys(object):
    LONGMSG = 'longMsg'
    SHORTMSG = 'shortMsg'


class _InstrumentationResultSignals(object):
    FAIL = 'FAILURES!!!'
    PASS = 'OK ('


class _InstrumentationBlockStates(Enum):
    UNKNOWN = 0
    METHOD = 1
    RESULT = 2


class _InstrumentationBlock(object):
    def __init__(self,
                 state=_InstrumentationBlockStates.UNKNOWN,
                 prefix=None,
                 previous_instrumentation_block=None):
        self.state = state
        self.prefix = prefix
        self.previous_instrumentation_block = previous_instrumentation_block

        self.empty = True
        self.error_message = ''
        self.status_code = _InstrumentationStatusCodes.UNKNOWN

        self.current_key = _InstrumentationKnownStatusKeys.STREAM
        self.known_keys = {
            _InstrumentationKnownStatusKeys.STREAM: [],
            _InstrumentationKnownStatusKeys.CLASS: [],
            _InstrumentationKnownStatusKeys.ERROR: [],
            _InstrumentationKnownStatusKeys.STACK: [],
            _InstrumentationKnownStatusKeys.TEST: [],
            _InstrumentationKnownResultKeys.LONGMSG: [],
            _InstrumentationKnownResultKeys.SHORTMSG: [],
        }
        self.unknown_keys = defaultdict(list)

    def is_empty(self):
        return self.empty

    def set_error_message(self, error_message):
        self.empty = False
        self.error_message = error_message

    def _remove_structure_prefix(self, prefix, line):
        return line[len(prefix):].strip()

    def set_status_code(self, status_code_line):
        self.empty = False
        self.status_code = self._remove_structure_prefix(
            _InstrumentationStructurePrefixes.STATUS_CODE,
            status_code_line,
        )

    def set_key(self, structure_prefix, key_line):
        self.empty = False
        key_value = self._remove_structure_prefix(
            structure_prefix,
            key_line,
        )
        if '=' in key_value:
            (key, value) = key_value.split('=')
            self.current_key = key
            if key in self.known_keys:
                self.known_keys[key].append(value)
            else:
                self.unknown_keys[key].append(key_value)

    def add_value(self, line):
        self.empty = False
        if self.current_key in self.known_keys:
            self.known_keys[self.current_key].append(line)
        else:
            self.unknown_keys[self.current_key].append(line)

    def transition_state(self, new_state):
        if self.state == _InstrumentationBlockStates.UNKNOWN:
            self.state = new_state
            return self
        else:
            return _InstrumentationBlock(
                state=new_state,
                prefix=self.prefix,
                previous_instrumentation_block=self,
            )


class _InstrumentationBlockFormatter(object):
    DEFAULT_INSTRUMENTATION_METHOD_NAME = 'instrumentation_method'

    def __init__(self, instrumentation_block):
        self.prefix = instrumentation_block.prefix
        self.status_code = instrumentation_block.status_code
        self.error_message = instrumentation_block.error_message
        self.known_keys = {}
        self.unknown_keys = {}
        for key, value in instrumentation_block.known_keys.items():
            self.known_keys[key] = '\n'.join(
                instrumentation_block.known_keys[key])
        for key, value in instrumentation_block.unknown_keys.items():
            self.unknown_keys[key] = '\n'.join(
                instrumentation_block.unknown_keys[key])

    def _add_part(self, parts, part):
        if part:
            parts.append(part)

    def _get_name(self):
        if self.known_keys[_InstrumentationKnownStatusKeys.TEST]:
            return self.known_keys[_InstrumentationKnownStatusKeys.TEST]
        else:
            return self.DEFAULT_INSTRUMENTATION_METHOD_NAME

    def _get_class(self):
        class_parts = []
        self._add_part(class_parts, self.prefix)
        self._add_part(class_parts,
                       self.known_keys[_InstrumentationKnownStatusKeys.CLASS])
        return '.'.join(class_parts)

    def _get_full_name(self, ):
        full_name_parts = []
        self._add_part(full_name_parts, self._get_class())
        self._add_part(full_name_parts, self._get_name())
        return '.'.join(full_name_parts)

    def _get_details(self):
        detail_parts = []
        self._add_part(detail_parts, self._get_full_name())
        self._add_part(detail_parts, self.error_message)
        return '\n'.join(detail_parts)

    def _get_extras(self):
        # Add empty line to start key-value pairs on new line.
        extra_parts = ['']

        for value in self.unknown_keys.values():
            self._add_part(extra_parts, value)

        self._add_part(extra_parts,
                       self.known_keys[_InstrumentationKnownStatusKeys.STREAM])
        self._add_part(
            extra_parts,
            self.known_keys[_InstrumentationKnownResultKeys.SHORTMSG])
        self._add_part(
            extra_parts,
            self.known_keys[_InstrumentationKnownResultKeys.LONGMSG])
        self._add_part(extra_parts,
                       self.known_keys[_InstrumentationKnownStatusKeys.ERROR])

        if self.known_keys[
                _InstrumentationKnownStatusKeys.STACK] not in self.known_keys[
                    _InstrumentationKnownStatusKeys.STREAM]:
            self._add_part(
                extra_parts,
                self.known_keys[_InstrumentationKnownStatusKeys.STACK])

        return '\n'.join(extra_parts)

    def _is_failed(self):
        if self.status_code in _InstrumentationStatusCodeCategories.FAIL:
            return True
        elif self.known_keys[_InstrumentationKnownStatusKeys.
                             STACK] and self.status_code != _InstrumentationStatusCodes.ASSUMPTION_FAILURE:
            return True
        elif self.known_keys[_InstrumentationKnownStatusKeys.ERROR]:
            return True
        elif self.known_keys[_InstrumentationKnownResultKeys.SHORTMSG]:
            return True
        elif self.known_keys[_InstrumentationKnownResultKeys.LONGMSG]:
            return True
        else:
            return False

    def create_test_record(self):
        details = self._get_details()
        extras = self._get_extras()

        tr_record = records.TestResultRecord(
            t_name=self._get_name(),
            t_class=self._get_class(),
        )
        if self._is_failed():
            tr_record.test_fail(
                e=signals.TestFailure(details=details, extras=extras))
        elif self.status_code in _InstrumentationStatusCodeCategories.SKIPPED:
            tr_record.test_skip(
                e=signals.TestSkip(details=details, extras=extras))
        elif self.status_code in _InstrumentationStatusCodeCategories.PASS:
            tr_record.test_pass(
                e=signals.TestPass(details=details, extras=extras))
        elif self.status_code in _InstrumentationStatusCodeCategories.TIMING:
            if self.error_message:
                tr_record.test_error(
                    e=signals.TestError(details=details, extras=extras))
            else:
                tr_record = None
        else:
            tr_record.test_error(
                e=signals.TestError(details=details, extras=extras))
        return tr_record

    def has_completed_result_block_format(self, error_message):
        extras = self._get_extras()
        if _InstrumentationResultSignals.PASS in extras:
            return True
        elif _InstrumentationResultSignals.FAIL in extras:
            return False
        else:
            raise signals.TestError(details=error_message, extras=extras)


class BaseInstrumentationTestClass(BaseTestClass):
    """Base class for all instrumentation test claseses to inherit from.

    This class extends the BaseTestClass to add functionality to run and parse
    the output of instrumentation runs.
    """

    DEFAULT_INSTRUMENTATION_OPTION_PREFIX = 'instrumentation_option_'
    DEFAULT_INSTRUMENTATION_ERROR_MESSAGE = ('instrumentation run exited '
                                             'unexpectedly')

    def _create_formatters(self, instrumentation_block, new_state):
        formatters = []
        # If starting a new block and yet the previous block never completed, error the last block.
        if instrumentation_block.previous_instrumentation_block:
            if instrumentation_block.previous_instrumentation_block.status_code in _InstrumentationStatusCodeCategories.TIMING:
                if instrumentation_block.status_code == _InstrumentationStatusCodes.START:
                    instrumentation_block.previous_instrumentation_block.set_error_message(
                        self.DEFAULT_INSTRUMENTATION_ERROR_MESSAGE)
                    formatters.append(
                        _InstrumentationBlockFormatter(
                            instrumentation_block.
                            previous_instrumentation_block))
            if new_state == _InstrumentationBlockStates.RESULT:
                if instrumentation_block.previous_instrumentation_block.status_code in _InstrumentationStatusCodeCategories.TIMING:
                    instrumentation_block.previous_instrumentation_block.set_error_message(
                        self.DEFAULT_INSTRUMENTATION_ERROR_MESSAGE)
                    formatters.append(
                        _InstrumentationBlockFormatter(
                            instrumentation_block.
                            previous_instrumentation_block))
        if not instrumentation_block.is_empty():
            formatters.append(
                _InstrumentationBlockFormatter(instrumentation_block))
        return formatters

    def _transition_instrumentation_block(
            self,
            instrumentation_block,
            new_state=_InstrumentationBlockStates.UNKNOWN):
        formatters = self._create_formatters(instrumentation_block, new_state)
        for formatter in formatters:
            test_record = formatter.create_test_record()
            if test_record:
                self.results.add_record(test_record)
                self.summary_writer.dump(test_record.to_dict(),
                                         records.TestSummaryEntryType.RECORD)
        return instrumentation_block.transition_state(new_state=new_state)

    def _parse_method_block_line(self, instrumentation_block, line):
        if line.startswith(_InstrumentationStructurePrefixes.STATUS):
            instrumentation_block.set_key(
                _InstrumentationStructurePrefixes.STATUS, line)
            return instrumentation_block
        elif line.startswith(_InstrumentationStructurePrefixes.STATUS_CODE):
            instrumentation_block.set_status_code(line)
            return self._transition_instrumentation_block(
                instrumentation_block)
        elif line.startswith(_InstrumentationStructurePrefixes.RESULT):
            # Unexpected transition from method block -> result block
            instrumentation_block.set_key(
                _InstrumentationStructurePrefixes.RESULT, line)
            return self._parse_result_line(
                self._transition_instrumentation_block(
                    instrumentation_block,
                    new_state=_InstrumentationBlockStates.RESULT,
                ),
                line,
            )
        else:
            instrumentation_block.add_value(line)
            return instrumentation_block

    def _parse_result_block_line(self, instrumentation_block, line):
        instrumentation_block.add_value(line)
        return instrumentation_block

    def _parse_unknown_block_line(self, instrumentation_block, line):
        if line.startswith(_InstrumentationStructurePrefixes.STATUS):
            return self._parse_method_block_line(
                self._transition_instrumentation_block(
                    instrumentation_block,
                    new_state=_InstrumentationBlockStates.METHOD,
                ),
                line,
            )
        elif (line.startswith(_InstrumentationStructurePrefixes.RESULT)
              or _InstrumentationStructurePrefixes.FAILED in line):
            return self._parse_result_block_line(
                self._transition_instrumentation_block(
                    instrumentation_block,
                    new_state=_InstrumentationBlockStates.RESULT,
                ),
                line,
            )
        else:
            # This would only really execute if instrumentation failed to start.
            instrumentation_block.add_value(line)
            return instrumentation_block

    def _parse_line(self, instrumentation_block, line):
        if instrumentation_block.state == _InstrumentationBlockStates.METHOD:
            return self._parse_method_block_line(instrumentation_block, line)
        elif instrumentation_block.state == _InstrumentationBlockStates.RESULT:
            return self._parse_result_block_line(instrumentation_block, line)
        else:
            return self._parse_unknown_block_line(instrumentation_block, line)

    def _finish_parsing(self, instrumentation_block):
        formatter = _InstrumentationBlockFormatter(instrumentation_block)
        return formatter.has_completed_result_block_format(
            self.DEFAULT_INSTRUMENTATION_ERROR_MESSAGE, )

    def parse_instrumentation_options(self, parameters=None):
        """Returns the options for the instrumentation test from user_params.

        By default, this method assume that the correct instrumentation options
        all start with DEFAULT_INSTRUMENTATION_OPTION_PREFIX.

        Args:
            parameters: A dictionary of key value pairs representing an
                assortment of parameters including instrumentation options.
                Usually, this argument will be from self.user_params.

        Returns:
            A dictionary of options/parameters for the instrumentation tst.
        """
        if parameters is None:
            return {}

        filtered_parameters = {}
        for parameter_key, parameter_value in parameters.items():
            if parameter_key.startswith(
                    self.DEFAULT_INSTRUMENTATION_OPTION_PREFIX):
                option_key = parameter_key[len(
                    self.DEFAULT_INSTRUMENTATION_OPTION_PREFIX):]
                filtered_parameters[option_key] = parameter_value
        return filtered_parameters

    def run_instrumentation_test(self,
                                 device,
                                 package,
                                 options=None,
                                 prefix=None,
                                 runner=None):
        """Runs instrumentation tests on a device and creates test records.

        Args:
            device: The device to run instrumentation tests on.
            package: The package name of the instrumentation tests.
            options: Instrumentation options for the instrumentation tests.
            prefix: An optional prefix for parser output for distinguishing
                between instrumentation test runs.
            runner: The runner to use for the instrumentation package,
                default to DEFAULT_INSTRUMENTATION_RUNNER.

        Returns:
            A boolean indicating whether or not all the instrumentation test
                methods passed.

        Raises:
            TestError if the instrumentation run crashed or if parsing the
                output failed.
        """
        instrumentation_output = device.instrument(
            package=package,
            options=options,
            runner=runner,
        )
        logging.info('Outputting instrumentation test log...')
        logging.info(instrumentation_output)

        instrumentation_block = _InstrumentationBlock(prefix=prefix)
        for line in instrumentation_output.splitlines():
            instrumentation_block = self._parse_line(instrumentation_block,
                                                     line)
        return self._finish_parsing(instrumentation_block)
