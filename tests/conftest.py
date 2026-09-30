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
"""Pytest guards that keep Mobly's unit tests hermetic.

Unit tests must never talk to real devices or leave processes behind. Both
have caused order-dependent CI hangs in the past: a leaked object's `__del__`
ran a real `adb` command long after the test's mocks were gone, and a test
left a real `adb logcat` process running after pytest exited.

This plugin:
  * blocks spawning real `adb`/`fastboot` processes, and
  * kills and reports subprocesses that are still running when the session
    ends.
Either one fails the test session.
"""

import os
import subprocess

import pytest

_DEVICE_TOOLS = frozenset(['adb', 'fastboot'])

_original_popen_init = subprocess.Popen.__init__
_current_test = ['<outside of a test>']
_blocked_calls = []
_spawned_processes = []
_leftover_processes = []


def _executable_name(args):
  """Returns the lowercase base name of the program `args` would execute."""
  if isinstance(args, (str, bytes, os.PathLike)):
    tokens = os.fsdecode(args).split()
  else:
    tokens = [os.fsdecode(arg) for arg in args]
  if not tokens:
    return ''
  name = os.path.basename(tokens[0].strip('"\'')).lower()
  if name.endswith('.exe'):
    name = name[: -len('.exe')]
  return name


def _guarded_popen_init(self, args, *pargs, **kwargs):
  if _executable_name(args) in _DEVICE_TOOLS:
    _blocked_calls.append((_current_test[0], repr(args)))
    raise RuntimeError(
        f'Unit tests must not run real device tools, got: {args!r}. Mock the'
        ' adb/fastboot layer, and make sure no object created by the test'
        ' runs adb commands when it is garbage collected.'
    )
  _original_popen_init(self, args, *pargs, **kwargs)
  _spawned_processes.append((_current_test[0], self))


def pytest_configure(config):
  # Intentionally never restored: finalizers of leaked objects can still run
  # after the session ends, e.g. at interpreter shutdown.
  subprocess.Popen.__init__ = _guarded_popen_init


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
  _current_test[0] = item.nodeid
  try:
    yield
  finally:
    _current_test[0] = '<outside of a test>'


@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
  for test, proc in _spawned_processes:
    if proc.poll() is None:
      _leftover_processes.append((test, repr(proc.args)))
      proc.kill()
      proc.wait()
  _spawned_processes.clear()
  if _blocked_calls or _leftover_processes:
    session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter):
  if not (_blocked_calls or _leftover_processes):
    return
  terminalreporter.section('hermeticity violations', red=True, bold=True)
  for test, args in _blocked_calls:
    terminalreporter.write_line(
        f'Blocked real device tool call in {test}: {args}'
    )
  for test, args in _leftover_processes:
    terminalreporter.write_line(
        f'Subprocess started in {test} was still running at the end: {args}'
    )
