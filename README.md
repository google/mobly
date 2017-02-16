[![Build Status](https://travis-ci.org/google/mobly.svg?branch=master)](https://travis-ci.org/google/mobly)

# Welcome to Mobly

**Mobly** is a Python-based test framework that specializes in supporting test
cases that require multiple devices, complex environments, or custom hardware
setups. Examples:

*   P2P data transfer between two devices
*   Conference calls across three phones
*   Wearable device interacting with a phone
*   Internet-Of-Things devices interacting with each other
*   Testing RF characteristics of devices with special equipment

Mobly can support many different types of devices and equipment, and it's easy
to plug your own device or custom equipment/service into Mobly.

Mobly comes with a set of libs to control common devices like Android devices.

While developed by Googlers, Mobly is not an official Google product.

## System dependencies
  - adb (1.0.36+ recommended)
  - python2.7 or python3.4+
  - python-setuptools

**If you use Python3, use `pip3` and `python3` (or python3.x) accordingly.**

## Installation

Mobly is compatible with both python 3.4+ and python 2.7.

You can install the released package from pip

```
$ pip install mobly
```

or download the source then run `setup.py` to use the bleeding edge:

```
<<<<<<< HEAD

**sample_test.py**

```python
from mobly import asserts
from mobly import base_test
from mobly import test_runner
from mobly.controllers import android_device

class HelloWorldTest(base_test.BaseTestClass):

  def setup_class(self):
    # Registering android_device controller module, and declaring that the test
    # requires at least two Android devices.
    self.ads = self.register_controller(android_device, min_number=2)
    self.dut = android_device.get_device(self.ads, label="dut")
    self.dut.load_sl4a()
    self.discoverer = android_device.get_device(self.ads, label="discoverer")
    self.discoverer.load_sl4a()
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
=======
$ git clone git@github.com:google/mobly.git
$ cd mobly
$ python setup.py install
>>>>>>> Update docs.
```

You may need `sudo` for the above commands if your system has certain permission
restrictions.

## Tutorials
To get started with some simple tests, see the [Mobly tutorial](https://github.com/google/mobly/wiki/Getting-Started-with-Mobly).

## Mobly Snippet
The Mobly Snippet projects let users better control Android devices.

* [Mobly Snippet Lib](https://github.com/google/mobly-snippet-lib): used for
triggering custom device-side code from host-side Mobly tests. You could use existing
Android libraries like UI Automator and Espresso.
* [Mobly Bundled Snippets](https://github.com/google/mobly-bundled-snippets): a set
of Snippets to allow Mobly tests to control Android devices by exposing a simplified
verison of the public Android API suitable for testing.
