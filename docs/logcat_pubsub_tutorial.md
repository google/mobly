Logcat Publisher and Subscriber Tutorial
======

The Android logcat publisher and subscriber module allows a Mobly test to
keep track of arbitrary states observed from the output of an Android
device's logcat stream. This tutorial guides you through writing your own
logcat subscriber and using the logcat event context manager.

# Setup Requirements

*   A computer with at least 1 USB port.
*   Mobly package and its system dependencies installed on the computer.
*   Example logcat lines that you would like to monitor.

# Example 1: User defined Logcat Subscriber

You can create your own subclass of LogcatSubscriber and register that
subscriber with the publisher service. For example, suppose you had a service
that was dumping out logcat lines such as:

```
01-02 03:45:02.300  2000  2001 I MyService: metric_a=20 metric_b=80
```

You can define a subclass `MyLogcatSubscriber` as such:

```python
from mobly.controllers import android_device
from mobly.controllers.android_device_lib.services import logcat_pubsub

class MyLogcatSubscriber(logcat_pubsub.LogcatSubscriber):
    def __init__(self):
        self.metric_a = None
        self.metric_b = None

    def handle(self, data):
        match = re.match('metric_a=(\d+) metric_b=(\d+)', data.message)
        if match:
            self.metric_a = int(match.group(1))
            self.metric_b = int(match.group(2))
```

Before the subscriber can subscribe to a logcat stream, the publisher first
needs to be registered with the `AndroidDevice` object:

```
ad = android_device.AndroidDevice('0123456789')
ad.services.register('publisher', logcat_pubsub.LogcatPublisher)
```

From here, we can create a new instance of `MyLogcatSubscriber` and have it
subscribe to the publisher service.

```
my_logcat_subscriber = MyLogcatSubscriber()
my_logcat_subscriber.subscribe(ad.services.publisher)
```

When the logcat line appears, the subscriber's internal state will get updated:

```
>>> print(my_logcat_subscriber.metric_a)
20
>>> print(my_logcat_subscriber.metric_b)
80
```

# Example 2: Logcat Event Context Manager

Mobly includes a built-in implementation of `LogcatSubscriber` called
`LogcatEventSubscriber` and is created ephemerally when the user calls the
`logcat_event` context manager. For example, a Mobly test can wait for the
following log line:

```
10-02 16:19:00.408  1463  1463 I vol.Events: writeEvent dismiss_dialog volume_controller
```

The following code will spawn an context manager to trigger on the regular
expression `writeEvent (.*) (.*)` and the call to `event.wait()` will block
until that logcat line appears.

```python
from mobly.controllers import android_device

ad = android_device.AndroidDevice('0123456789')
with ad.services.publisher.event(pattern='writeEvent (.*) (.*)') as event:
   event.wait()
   print('time: %s' % event.trigger.time)
   print('pid: %d' % event.trigger.pid)
   print('tid: %d' % event.trigger.tid)
   print('tag: %s' % event.trigger.tag)
   print('message: %s' % event.trigger.message)
   print('regex match groups: %s' % str(event.match.groups()))
```

This will result in the output:

```
time: 2018-10-02 16:19:00.408000
pid: 1463
tid: 1463
tag: vol.Events
message: writeEvent dismiss_dialog volume_controller
regex match groups: ('dismiss_dialog', 'volume_controller')
```

This saves you from having to backtrack through the existing logcat file
to search for the given event. In cases where the logcat line is caused by
another test input, the context manager helps prevent race conditions since
the test input can be scheduled after the creation of the context manager
but before the call to the event's `wait()` method.
