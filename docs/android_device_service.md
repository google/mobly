# Mobly Android Device Service

This tutorial shows how to use the service mechanism in Mobly's `AndroidDevice`
controller.

## Purpose
Mobly's `AndroidDevice` controller is a Python module that lets users interact
with Android devices with Python code.

Often times, we need long-running services associated with `AndroidDevice`
objects that persist during a test, e.g. adb logcat collection, screen
recording. Meanwhile, we may want to alter the device's state during the
test, e.g. reboot.

`AndroidDevice` services makes it easier to implement long-running services.

## Usage

Implement your service per the
[`BaseService` interface](https://github.com/google/mobly/blob/master/mobly/controllers/android_device_lib/services/base_service.py).

Here is a dummy service example:

**my_service.py**

```python
class Configs(object):
  def __init__(self, secret=None):
    self.secret = secret


class MyService(base_service.BaseService):
  """Dummy service demonstrating the service interface."""
  def __init__(self, device, configs=None):
    self._device = device
    self._configs = configs
    self._is_alive = False

  def get_my_secret(self):
    return self._configs.secret

  @property
  def is_alive(self):
    """Override base class."""
    return self._is_alive

  def start(self):
    """Override base class."""
    self._is_alive = True

  def stop(self):
    """Override base class."""
    self._is_alive = False
```

Once you have your service class, you can register your service with the
`ServiceManager`. Let's say we already have an `AndroidDevice` instance `ad`:

```python
ad.services.register('secret_service',
                     my_service.MyService,
                     my_service.Configs(secret=42))
```

After registration, you can interact with the service instance:

```python
ad.services.secret_service.is_alive # True
ad.services.secret_service.get_my_secret() # 42
```

When the `ad` reboots or gets destroyed, the service manager will handle the
lifecycle changes of each service instance. So users don't have to explicitly
write code to handle device state changes for each service, which makes the
test verbose.

The service interface also has optional methods `pause` and `resume` for
services that are sensitive to device disconnect without reboot. For more
details, see the docstrings of the
[`BaseService` interface](https://github.com/google/mobly/blob/master/mobly/controllers/android_device_lib/services/base_service.py).
