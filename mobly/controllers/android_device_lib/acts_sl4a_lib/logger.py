#!/usr/bin/env python3
#
#   Copyright 2021 - Google, Inc.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""Modified functions from ACTS logging library."""

import logging


class LoggerAdapter(logging.LoggerAdapter):
  """A LoggerAdapter class that takes in a lambda for transforming logs."""

  def __init__(self, logging_lambda):
    self.logging_lambda = logging_lambda
    super(LoggerAdapter, self).__init__(logging.getLogger(), {})

  def process(self, msg, kwargs):
    return self.logging_lambda(msg), kwargs


def create_tagged_logger(tag=''):
  """Returns a logger that logs each line with the given prefix.

  Args:
      tag: The tag of the log line, E.g. if tag == tag123, the output
          line would be:

          <TESTBED> <TIME> <LOG_LEVEL> [tag123] logged message
  """

  def logging_lambda(msg):
    return '[%s] %s' % (tag, msg)

  return LoggerAdapter(logging_lambda)
