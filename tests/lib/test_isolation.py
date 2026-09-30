# Copyright 2026 Google Inc.
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
"""Helpers to keep process-global state from leaking between unit tests."""

import logging
import signal

# Attributes that Mobly sets directly on the `logging` module during a test run.
_LOGGING_MODULE_ATTRS = ('log_path', 'root_output_path')

_MISSING = object()


def preserve_global_state(test_case):
  """Restores process-global state touched by Mobly when a test finishes.

  Running Mobly's test runner, base test, or logger setup inside a unit test
  mutates state that outlives the test:

  * the root logger's handlers, level and propagation;
  * the `log_path` and `root_output_path` attributes on the `logging` module;
  * the SIGTERM handler.

  Without restoring these, later tests silently depend on which tests ran
  before them. Call this from `setUp` of tests that exercise such code paths.

  Args:
    test_case: unittest.TestCase, the test to register the cleanup on.
  """
  root = logging.getLogger()
  saved_handlers = list(root.handlers)
  saved_level = root.level
  saved_propagate = root.propagate
  saved_attrs = {
      name: getattr(logging, name, _MISSING) for name in _LOGGING_MODULE_ATTRS
  }
  saved_sigterm = signal.getsignal(signal.SIGTERM)

  def _restore():
    for handler in list(root.handlers):
      if handler not in saved_handlers:
        root.removeHandler(handler)
        handler.close()
    for handler in saved_handlers:
      if handler not in root.handlers:
        root.addHandler(handler)
    root.setLevel(saved_level)
    root.propagate = saved_propagate
    for name, value in saved_attrs.items():
      if value is _MISSING:
        if hasattr(logging, name):
          delattr(logging, name)
      else:
        setattr(logging, name, value)
    if saved_sigterm is not None:
      signal.signal(signal.SIGTERM, saved_sigterm)

  test_case.addCleanup(_restore)
