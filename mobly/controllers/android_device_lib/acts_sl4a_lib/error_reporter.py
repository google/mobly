#!/usr/bin/env python3
#
#   Copyright 2018 - Google, Inc.
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

import logging
import re
import threading
import time

from mobly.controllers.android_device_lib.acts_sl4a_lib import utils


class ErrorLogger(logging.LoggerAdapter):
  """A logger for a given error report."""

  def __init__(self, label):
    self.label = label
    super(ErrorLogger, self).__init__(logging.getLogger(), {})

  def process(self, msg, kwargs):
    """Transforms a log message to be in a given format."""
    return '[Error Report|%s] %s' % (self.label, msg), kwargs


class ErrorReporter(object):
  """A class that reports errors and diagnoses possible points of failure.

  Attributes:
      max_reports: The maximum number of reports that should be reported.
          Defaulted to 1 to prevent multiple reports from reporting at the
          same time over one another.
      name: The name of the report to be used in the error logs.
  """

  def __init__(self, name, max_reports=1):
    """Creates an error report.

    Args:
        name: The name of the error report.
        max_reports: Sets the maximum number of reports to this value.
    """
    self.name = name
    self.max_reports = max_reports
    self._ticket_number = 0
    self._ticket_lock = threading.Lock()
    self._current_request_count = 0
    self._accept_requests = True

  def create_error_report(self, sl4a_manager, sl4a_session, rpc_connection):
    """Creates an error report, if possible.

    Returns:
        False iff a report cannot be created.
    """
    if not self._accept_requests:
      return False

    self._current_request_count += 1

    try:
      ticket = self._get_report_ticket()
      if not ticket:
        return False

      report = ErrorLogger('%s|%s' % (self.name, ticket))

      (self.report_on_adb(sl4a_manager.adb, report)
       and self.report_device_processes(sl4a_manager.adb, report) and
       self.report_sl4a_state(rpc_connection, sl4a_manager.adb, report)
       and self.report_sl4a_session(sl4a_manager, sl4a_session, report))

      return True
    finally:
      self._current_request_count -= 1

  def report_on_adb(self, adb, report):
    """Creates an error report for ADB. Returns false if ADB has failed."""
    adb_uptime = utils.get_command_uptime('"adb .* server"')
    if adb_uptime:
      report.info('The adb daemon has an uptime of %s '
                  '([[dd-]hh:]mm:ss).' % adb_uptime)
    else:
      report.warning('The adb daemon (on the host machine) is not '
                     'running. All forwarded ports have been removed.')
      return False

    devices_output = adb.devices()
    if adb.serial not in devices_output:
      report.warning(
        'This device cannot be found by ADB. The device may have shut '
        'down or disconnected.')
      return False
    elif re.findall(r'%s\s+offline' % adb.serial, devices_output):
      report.warning(
        'The device is marked as offline in ADB. We are no longer able '
        'to access the device.')
      return False
    else:
      report.info(
        'The device is online and accessible through ADB calls.')
    return True

  def report_device_processes(self, adb, report):
    """Creates an error report for the device's required processes.

    Returns:
        False iff user-apks cannot be communicated with over tcp.
    """
    zygote_uptime = utils.get_device_process_uptime(adb, 'zygote')
    if zygote_uptime:
      report.info(
        'Zygote has been running for %s ([[dd-]hh:]mm:ss). If this '
        'value is low, the phone may have recently crashed.' %
        zygote_uptime)
    else:
      report.warning(
        'Zygote has been killed. It is likely the Android Runtime has '
        'crashed. Check the bugreport/logcat for more information.')
      return False

    netd_uptime = utils.get_device_process_uptime(adb, 'netd')
    if netd_uptime:
      report.info(
        'Netd has been running for %s ([[dd-]hh:]mm:ss). If this '
        'value is low, the phone may have recently crashed.' %
        zygote_uptime)
    else:
      report.warning(
        'Netd has been killed. The Android Runtime may have crashed. '
        'Check the bugreport/logcat for more information.')
      return False

    adbd_uptime = utils.get_device_process_uptime(adb, 'adbd')
    if netd_uptime:
      report.info(
        'Adbd has been running for %s ([[dd-]hh:]mm:ss). If this '
        'value is low, the phone may have recently crashed.' %
        adbd_uptime)
    else:
      report.warning('Adbd is not running.')
      return False
    return True

  def report_sl4a_state(self, rpc_connection, adb, report):
    """Creates an error report for the state of SL4A."""
    report.info(
      'Diagnosing Failure over connection %s.' % rpc_connection.ports)

    ports = rpc_connection.ports
    forwarded_ports_output = adb.forward('--list')

    expected_output = '%s tcp:%s tcp:%s' % (
      adb.serial, ports.forwarded_port, ports.server_port)
    if expected_output not in forwarded_ports_output:
      formatted_output = re.sub(
        '^', '    ', forwarded_ports_output, flags=re.MULTILINE)
      report.warning(
        'The forwarded port for the failed RpcConnection is missing.\n'
        'Expected:\n    %s\nBut found:\n%s' % (expected_output,
                                               formatted_output))
      return False
    else:
      report.info('The connection port has been properly forwarded to '
                  'the device.')

    sl4a_uptime = utils.get_device_process_uptime(
      adb, 'com.googlecode.android_scripting')
    if sl4a_uptime:
      report.info(
        'SL4A has been running for %s ([[dd-]hh:]mm:ss). If this '
        'value is lower than the test case, it must have been '
        'restarted during the test.' % sl4a_uptime)
    else:
      report.warning(
        'The SL4A scripting service is not running. SL4A may have '
        'crashed, or have been terminated by the Android Runtime.')
      return False
    return True

  def report_sl4a_session(self, sl4a_manager, session, report):
    """Reports the state of an SL4A session."""
    if session.server_port not in sl4a_manager.sl4a_ports_in_use:
      report.warning('SL4A server port %s not found in set of open '
                     'ports %s' % (session.server_port,
                                   sl4a_manager.sl4a_ports_in_use))
      return False

    if session not in sl4a_manager.sessions.values():
      report.warning('SL4A session %s over port %s is not managed by '
                     'the SL4A Manager. This session is already dead.' %
                     (session.uid, session.server_port))
      return False
    return True

  def finalize_reports(self):
    self._accept_requests = False
    while self._current_request_count > 0:
      # Wait for other threads to finish.
      time.sleep(.1)

  def _get_report_ticket(self):
    """Returns the next ticket, or none if all tickets have been used."""
    with self._ticket_lock:
      self._ticket_number += 1
      ticket_number = self._ticket_number

    if ticket_number <= self.max_reports:
      return ticket_number
    else:
      return None
