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


class Sl4aPorts(object):
  """A container for the three ports needed for an SL4A connection.

  Attributes:
      client_port: The port on the host associated with the SL4A client
      forwarded_port: The port forwarded to the Android device.
      server_port: The port on the device associated with the SL4A server.
  """

  def __init__(self, client_port=0, forwarded_port=0, server_port=0):
    self.client_port = client_port
    self.forwarded_port = forwarded_port
    self.server_port = server_port

  def __str__(self):
    return '(%s, %s, %s)' % (self.client_port, self.forwarded_port,
                             self.server_port)
