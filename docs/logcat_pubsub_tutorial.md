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
that was tracking the battery voltage of a BLE speaker with a sampling rate of
once every 20 seconds.

```
01-02 03:45:02.300  2000  2001 I SpeakerBattery: voltage=4.7859
01-02 03:45:22.350  2000  2001 I SpeakerBattery: voltage=4.7832
01-02 03:45:42.290  2000  2001 I SpeakerBattery: voltage=4.7810
01-02 03:46:02.310  2000  2001 I SpeakerBattery: voltage=4.7798
```

You can define a subclass `SpeakerBatterySubscriber` as such:

```python
import threading
from mobly.controllers import android_device
from mobly.controllers.android_device_lib.services import logcat

class SpeakerBatterySubscriber(logcat.LogcatSubscriber):

    LOW_VOLTAGE = 4.78

    def __init__(self):
        self.low_voltage_event = threading.Event()

    def handle(self, data):
        if data.tag == 'SpeakerBattery':
            match = re.match('voltage=([\d\.]+)', data.message)
            if match and float(match.group(1)) < self.LOW_VOLTAGE:
                self.low_voltage_event.set()
```

Before the subscriber can subscribe to a logcat stream, the logcat service
must first be initialized.

```
ad = android_device.AndroidDevice('0123456789')
ad.start_services()
```

From here, we can create a new instance of `SpeakerBatterySubscriber` and
have it subscribe to the logcat service.

```
speaker_battery_subscriber = SpeakerBatterySubscriber()
speaker_battery_subscriber.subscribe(ad.services.logcat)
```

When each logcat line appears, the battery voltage will be compared against
the low battery voltage and the `low_voltage_event` will be set if the
reported voltage drops below 4.78 volts.

```
# Wait 10 minutes for battery to dip below the low voltage threshold
if speaker_battery_subscriber.low_voltage_event.wait(10 * 60):
    logging.info('Battery dropped below 4.78V in less than 10 minutes.')
```

# Example 2: Logcat Event Context Manager

Mobly includes a built-in implementation of `LogcatSubscriber` called
`LogcatEventSubscriber` and is created ephemerally when the user calls the
`event` context manager. For example, a Mobly test can wait for the following
log line:

```
10-02 16:19:00.408  1463  1463 D BluetoothManagerService: Airplane Mode change - current state:  ON
```

The following code will spawn a context manager to trigger on the regular
expression `Airplane Mode change - current state:  (?P<state>[A-Z]*)` and the
call to `event.wait()` will block until that logcat line appears.

```python
from mobly.controllers import android_device

ad = android_device.AndroidDevice('0123456789')
tag = 'BluetoothManagerService'
pattern = r'Airplane Mode change - current state:  (?P<state>[A-Z]*)'

with ad.services.publisher.event(pattern=pattern, tag=tag) as event:
    ad.adb.shell(['settings', 'put', 'global', 'airplane_mode_on', '1'])
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
tag: BluetoothManagerService
message: Airplane Mode change - current state:  ON
regex match groups: ('ON',)
```

Notice that the potential for a race condition between placing the device
into airplane mode to detecting the resulting logcat line has been
eliminated because the tracking of the logcat event happens before the
enabling of airplane mode. Upon exiting the context manager, the event
subscriber is automatically unsubscribed.
