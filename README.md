[![Build Status](https://travis-ci.org/google/mobly.svg?branch=master)](https://travis-ci.org/google/mobly)

# Getting Started with Mobly

**Mobly** is a Python-based test framework that specializes in
supporting test cases that require multiple devices, complex environments, or
custom hardware setups. Examples:

*   P2P data transfer between two devices
*   Conference calls across three phones
*   Wearable device interacting with a phone
*   Internet-Of-Things devices interacting with each other
*   Testing RF characteristics of devices with special equipment

Mobly can support many different types of devices and equipment, and it's easy
to plug your own device or custom equipment/service into Mobly.

Mobly comes with a set of libs to control common devices like Android devices.

While developed by Googlers, Mobly is not an official Google product.

### What will I learn here?

Writing and executing simple test cases that use Android devices. We are
focusing on Android devices here since they are the most accessible devices.
Mobly supports various devices and you can also use your own custom
hardware/equipment.

### Setup Requirements

*   A computer with 2 USB ports (or a USB hub).
*   Mobly package and its system dependencies installed on the computer.
*   One or two Android devices with the app SL4A* installed.
*   A working adb setup. To check, connect one Android device to the computer
    and make sure it has "USB debugging" enabled. Make sure the device shows up
    in the list printed by `adb devices`.

\* You can get SL4A from the
[Android repo](https://source.android.com/source/downloading.html), under
project `<aosp>/external/sl4a`

It can be built like a regular system app with `mm` commands. It needs to be
signed with the build you use on your Android devices.


### __System dependencies__
  - adb (1.0.36+ recommended)
  - python2.7 or python3.4+
  - python-setuptools

**If you use Python3, use `pip3` and `python3` (or python3.x) accordingly
throughout this tutorial.**

### Installation

Mobly is compatible with both python 3.4+ and python 2.7.

You can install the released package from pip
```
$ pip install mobly
```
or download the source to use the bleeding edge:
```
$ python setup.py install
```
You may need `sudo` for the above commands if your system has certain permission
restrictions.


## Example 1: Hello World!

Let's start with the simple example of posting "Hello World" on the Android
device's screen. Create the following files:

**sample_config.yml**

```yaml
TestBeds:
  # A testbed where adb will find Android devices.
  - Name: SampleTestBed,
    Controllers:
        "AndroidDevice": "*"
```

**hello_world_test.py**

```python
from mobly import base_test
from mobly import test_runner
from mobly.controllers import android_device

class HelloWorldTest(base_test.BaseTestClass):

  def setup_class(self):
    # Registering android_device controller module declares the test's
    # dependency on Android device hardware. By default, we expect at least one
    # object is created from this.
    self.ads = self.register_controller(android_device)
    self.dut = self.ads[0]

  def test_hello(self):
    self.dut.sl4a.makeToast('Hello World!')

if __name__ == "__main__":
  test_runner.main()
```

*To execute:*

    $ python hello_world_test.py -c sample_config.yml

*Expect*

A "Hello World!" toast notification appears on your device's screen.

Within SampleTestBed's `Controllers` section, we used `"AndroidDevice" : "*"` to tell
the test runner to automatically find all connected Android devices. You can also
specify particular devices by serial number and attach extra attributes to the object:

```yaml
AndroidDevice:
  - serial: xyz,
    phone_number: 123456,
  - serial: abc,
    label: golden_device
```

## Example 2: Invoking specific test case

We have multiple tests written in a test script, and we only want to execute
a subset of them.

**hello_world_test.py**

```python
from mobly import base_test
from mobly import test_runner
from mobly.controllers import android_device

class HelloWorldTest(base_test.BaseTestClass):

  def setup_class(self):
    self.ads = self.register_controller(android_device)
    self.dut = self.ads[0]

  def test_hello(self):
    self.dut.sl4a.makeToast('Hello World!')

  def test_bye(self):
    self.dut.sl4a.makeToast('Goodbye!')

if __name__ == "__main__":
  test_runner.main()
```

*To execute:*

    $ python hello_world_test.py -c sample_config.yml --test_case test_bye


*Expect*

A "Goodbye!" toast notification appears on your device's screen.

You can dictate what test cases to execute within a test script and their
execution order, shown below:

    $ python hello_world_test.py -c sample_config.yml --test_case test_bye test_hello test_bye

*Expect*

Toast notifications appear on your device's screen in the following order:
"Goodbye!", "Hello World!", "Goodbye!".

## Example 3: User parameters

You could specify user parameters to be passed into your test class in the
config file.

In the following config, we added a parameter `favorite_food` to be used in the test case.

**sample_config.yml**

```yaml
TestBeds:
  - Name: SampleTestBed,
    Controllers:
        AndroidDevice" : "*"
    TestParams:
        favorite_food: Green eggs and ham.
```

In the test script, you could access the user parameter:

```python
  def test_favorite_food(self):
    food = self.user_params.get('favorite_food')
    if food:
      self.dut.sl4a.makeToast("I'd like to eat %s." % food)
    else:
      self.dut.sl4a.makeToast("I'm not hungry.")
```

## Example 4: Multiple Test Beds and Default Test Parameters

Multiple test beds can be configured in one configuration file.

**sample_config.yaml**

```yaml
DefaultParams: &DefaultParams
    favorite_food: green eggs and ham.

TestBeds:
  - Name: XyzTestBed,
    Controllers:
        AndroidDevice:
          - serial: xyz,
            phone_number: 123456
    TestParams:
        <<: *DefaultParams
  - Name: AbcTestBed,
    Controllers:
        AndroidDevice:
          - serial: abc,
            label: golden_device
    TestParams:
        <<: *DefaultParams
```

You can choose which one to execute on with the command line argument
`--test_bed`:

    $ python hello_world_test.py -c sample_config.yml --test_bed AbcTestBed

*Expect*

A "Hello World!" and a "Goodbye!" toast notification appear on your device's
screen.


## Example 5: Test with Multiple Android devices

In this example, we use one Android device to discover another Android device
via bluetooth. This test demonstrates several essential elements in test
writing, like logging and asserts.

**sample_config.yml**

```yaml
TestBeds:
  - Name: TwoDeviceTestBed,
    Controllers:
        AndroidDevice:
          - serial: xyz,
            label: dut
          - serial: abc,
            label: discoverer
    TestParams:
        bluetooth_name: MagicBluetooth,
        bluetooth_timeout: 5
```

**sample_test.py**

```python
from mobly import base_test
from mobly import test_runner
from mobly.controllerse import android_device

class HelloWorldTest(base_test.BaseTestClass):

  def setup_class(self):
    # Registering android_device controller module, and declaring that the test
    # requires at least two Android devices.
    self.ads = self.register_controller(android_device, min_number=2)
    self.dut = android_device.get_device(self.ads, label="dut")
    self.discoverer = android_device.get_device(self.ads, label="discoverer")
    self.dut.ed.clear_all_events()
    self.discoverer.ed.clear_all_events()

  def setup_test(self):
    # Make sure bluetooth is on
    self.dut.sl4a.bluetoothToggleState(True)
    self.discoverer.sl4a.bluetoothToggleState(True)
    self.dut.ed.pop_event(event_name='BluetoothStateChangedOn',
                          timeout=10)
    self.discoverer.ed.pop_event(event_name='BluetoothStateChangedOn',
                                 timeout=10)
    if (not self.dut.sl4a.bluetoothCheckState() or
           not self.discoverer.sl4a.bluetoothCheckState()):
      asserts.abort_class('Could not turn on Bluetooth on both devices.')

    # Set the name of device #1 and verify the name properly registered.
    self.dut.sl4a.bluetoothSetLocalName(self.bluetooth_name)
    asserts.assert_equal(self.dut.sl4a.bluetoothGetLocalName(),
                         self.bluetooth_name,
                         'Failed to set bluetooth name to %s on %s' %
                         (self.bluetooth_name, self.dut.serial))

  def test_bluetooth_discovery(self):
    # Make dut discoverable.
    self.dut.sl4a.bluetoothMakeDiscoverable()
    scan_mode = self.dut.sl4a.bluetoothGetScanMode()
    asserts.assert_equal(
        scan_mode, 3,  # 3 signifies CONNECTABLE and DISCOVERABLE
        'Android device %s failed to make blueooth discoverable.' %
            self.dut.serial)

    # Start the discovery process on #discoverer.
    self.discoverer.ed.clear_all_events()
    self.discoverer.sl4a.bluetoothStartDiscovery()
    self.discoverer.ed.pop_event(
        event_name='BluetoothDiscoveryFinished',
        timeout=self.bluetooth_timeout)

    # The following log entry demonstrates AndroidDevice log object, which
    # prefixes log entries with "[AndroidDevice|<serial>] "
    self.discoverer.log.info('Discovering other bluetooth devices.')

    # Get a list of discovered devices
    discovered_devices = self.discoverer.sl4a.bluetoothGetDiscoveredDevices()
    self.discoverer.log.info('Found devices: %s', discovered_devices)
    matching_devices = [d for d in discovered_devices
                        if d.get('name') == self.bluetooth_name]
    if not matching_devices:
      asserts.fail('Android device %s did not discover %s.' %
                   (self.discoverer.serial, self.dut.serial))
    self.discoverer.log.info('Discovered at least 1 device named '
                             '%s: %s', self.bluetooth_name, matching_devices)

if __name__ == "__main__":
  test_runner.main()
```

One will notice that this is not the most robust test (another nearby device
could be using the same name), but in the interest of simplicity, we've limited
the number of RPCs sent to each Android device to just two:

*   For `self.dut`, we asked it to make itself discoverable and checked that it
    did it.
*   For `self.discoverer`, we asked it to start scanning for nearby bluetooth
    devices, and then we pulled the list of devices seen.

There's potentially a lot more we could do to write a thorough test (e.g., check
the hardware address, see whether we can pair devices, transfer files, etc.).

### Event Dispatcher

You'll notice above that we've used `self.{device_alias}.ed.pop_event()`. The
`ed` attribute of an Android device object is an EventDispatcher, which provides
APIs to interact with async events.

For example, `pop_event` is a function which will block until either a
specified event is seen or the call times out, and by using it we avoid the use
of busy loops that constantly check the device state. For more, see the APIs in
`mobly.controllers.android_device_lib.event_dispatcher`.
