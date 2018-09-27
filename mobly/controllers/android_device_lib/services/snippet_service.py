# Copyright 2018 Google Inc.
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
"""Module for the snippet service."""
from mobly.controllers.android_device_lib import errors
from mobly.controllers.android_device_lib import snippet_client
from mobly.controllers.android_device_lib.services import base_service


class Error(errors.ServiceError):
    SERVICE_TYPE = 'Snippet:%s'

    def __init__(self, snippet_package, device, msg):
        self.SERVICE_TYPE = self.SERVICE_TYPE % snippet_package
        super(Error, self).__init__(device, msg)


class Config(object):
    def __init__(self, package):
        self.package = package


class SnippetService(base_service.BaseService):
    """Service for a single Snippet client."""

    def __init__(self, device, configs=None):
        self._device = device
        self._configs = configs
        self._is_alive = False
        self.client = None

    @property
    def is_alive(self):
        return self.client is not None

    def start(self, configs=None):
        if configs:
            raise Error(
                self._configs.package, self._device,
                'Overriding config in `start` is allowed for SnippetService.')
        client = snippet_client.SnippetClient(
            package=self._configs.package, ad=self._device)
        try:
            client.start_app_and_connect()
        except snippet_client.AppStartPreCheckError:
            # Precheck errors don't need cleanup, directly raise.
            raise
        except Exception as e:
            # Log the stacktrace of `e` as re-raising doesn't preserve trace.
            self._device.log.exception('Failed to start app and connect.')
            # If errors happen, make sure we clean up before raising.
            try:
                client.stop_app()
            except:
                self._device.log.exception(
                    'Failed to stop app after failure to start and connect.'
                )
            # Explicitly raise the error from start app failure.
            raise e
        self.client = client

    def stop(self):
        if self.client:
            self.client.stop_app()
            self.client = None

    def pause(self):
        """No op."""
        return

    def resume(self):
        if self.client:
            self.client.restore_app_connection()

    def __getattr__(self, name):
        if self.client:
            return getattr(self.client, name)
