---
layout: page
title: "Lesson 5: Test with multiple Android devices"
permalink: /tutorials/lesson5.html
site_nav_category: tutorials
site_nav_category_order: 105
---

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

