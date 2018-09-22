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
"""Module for the manager of services."""
# TODO(xpconanfan: move the device errors to a more generic location so
# other device controllers like iOS can share it.
from mobly import expects
from mobly.controllers.android_device_lib import errors


class Error(errors.DeviceError):
    """Root error type for this module."""


class ServiceManager(object):
    """Manager for services of AndroidDevice.

    A service is a long running process that involves an Android device, like
    adb logcat or Snippet.
    """

    def __init__(self, parent):
        self._service_objects = {}
        self._parent = parent

    @property
    def is_anything_alive(self):
        """True if any service is alive; False otherwise."""
        for service in self._service_objects.values():
            if service.is_alive:
                return True
        return False

    def register(self, alias, service_class, configs=None):
        """Registers a service.

        This will create a service instance, starts the service, and adds the
        instance to the mananger.

        Args:
            alias: string, the alias for this instance.
            service_class: class, the service class to instantiate.
            configs: (optional) config object to pass to the service class's
                constructor.
        """
        if alias in self._service_objects:
            raise Error(
                'A service is already registered with alias "%s"' % alias)
        service_obj = None
        if configs is None:
            service_obj = service_class(self._parent)
        else:
            service_obj = service_class(self._parent, configs)
        service_obj.start()
        self._service_objects[alias] = service_obj

    def unregister(self, alias):
        """Unregisters a service instance.

        Stops a service and removes it from the manager.

        Args:
            alias: string, the alias of the service instance to unregister.
        """
        if alias not in self._service_objects:
            raise Error('No service is registered with alias "%s"' % alias)
        service_obj = self._service_objects.pop(alias)
        if service_obj.is_alive:
            service_obj.stop()

    def unregister_all_safe(self):
        """Safely unregisters all active instances.

        Errors occurred here will be recorded but not raised.
        """
        aliases = list(self._service_objects.keys())
        for alias in aliases:
            with expects.expect_no_raises(
                    'Failed to unregister service %s' % alias):
                self.unregister(alias)

    def __getattr__(self, name):
        return self._service_objects[name]
