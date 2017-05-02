Getting started with Mobly
======

This tutorial shows how to write and execute simple Mobly test cases. We are
using Android devices here since they are pretty accessible. Mobly supports
various devices and you can also use your own custom hardware/equipment.

# Setup Requirements

*   A computer with at least 2 USB ports.
*   Mobly package and its system dependencies installed on the computer.
*   One or two Android devices with the [Mobly Bundled Snippets]
    (https://github.com/google/mobly-bundled-snippets) (MBS) installed. We will
    use MBS to trigger actions on the Android devices.
*   A working adb setup. To check, connect one Android device to the computer
    and make sure it has "USB debugging" enabled. Make sure the device shows up
    in the list printed by `adb devices`.

# Example 1: Hello World!
 
Let's start with the simple example of posting "Hello World" on the Android
device's screen. Create the following files:
 
**sample_config.yml**
 
```yaml
TestBeds:
  # A test bed where adb will find Android devices.
  - Name: SampleTestBed
    Controllers:
        AndroidDevice: '*'
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
    # Start Mobly Bundled Snippets (MBS).
    self.dut.load_snippet('mbs', 'com.google.android.mobly.snippet.bundled')
 
  def test_hello(self):
    self.dut.mbs.makeToast('Hello World!')
 
if __name__ == '__main__':
  test_runner.main()
```
 
*To execute:*
 
    $ python hello_world_test.py -c sample_config.yml
 
*Expect*
 
A "Hello World!" toast notification appears on your device's screen.
 
Within SampleTestBed's `Controllers` section, we used `AndroidDevice: '*'` to tell
the test runner to automatically find all connected Android devices. You can also
specify particular devices by serial number and attach extra attributes to the object:
 
```yaml
AndroidDevice:
  - serial: xyz,
    phone_number: 123456,
  - serial: abc,
    label: golden_device
```
 
# Example 2: Invoking specific test case
 
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
    self.dut.load_snippet('mbs', 'com.google.android.mobly.snippet.bundled')
 
  def test_hello(self):
    self.dut.mbs.makeToast('Hello World!')
 
  def test_bye(self):
    self.dut.mbs.makeToast('Goodbye!')
 
if __name__ == '__main__':
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
 
# Example 3: User parameters
 
You could specify user parameters to be passed into your test class in the
config file.
 
In the following config, we added a parameter `favorite_food` to be used in the test case.
 
**sample_config.yml**
 
```yaml
TestBeds:
  - Name: SampleTestBed,
    Controllers:
        AndroidDevice: '*'
    TestParams:
        favorite_food: Green eggs and ham.
```
 
In the test script, you could access the user parameter:
 
```python
  def test_favorite_food(self):
    food = self.user_params.get('favorite_food')
    if food:
      self.dut.mbs.makeToast("I'd like to eat %s." % food)
    else:
      self.dut.mbs.makeToast("I'm not hungry.")
```
 
# Example 4: Multiple Test Beds and Default Test Parameters
 
Multiple test beds can be configured in one configuration file.
 
**sample_config.yaml**
 
```yaml
# DefaultParams is optional here. It uses yaml's anchor feature to easily share
# a set of parameters between multiple test bed configs
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
 
 
# Example 5: Test with Multiple Android devices
 
In this example, we use one Android device to discover another Android device
via bluetooth. This test demonstrates several essential elements in test
writing, like asserts, device debug tag, and general logging vs logging with device tag.
 
**sample_config.yml**
 
```yaml
TestBeds:
  - Name: TwoDeviceTestBed,
    Controllers:
        AndroidDevice:
          - serial: xyz,
            label: target
          - serial: abc,
            label: discoverer
    TestParams:
        bluetooth_name: MagicBluetooth,
        bluetooth_timeout: 5

```
 
**sample_test.py**
 
 
```python
import logging
import pprint

from mobly import asserts
from mobly import base_test
from mobly import test_runner
from mobly.controllers import android_device

# Number of seconds for the target to stay discoverable on Bluetooth.
DISCOVERABLE_TIME = 60


class HelloWorldTest(base_test.BaseTestClass):
    def setup_class(self):
        # Registering android_device controller module, and declaring that the test
        # requires at least two Android devices.
        self.ads = self.register_controller(android_device, min_number=2)
        # The device used to discover Bluetooth devices.
        self.discoverer = android_device.get_device(
            self.ads, label='discoverer')
        # Sets the tag that represents this device in logs.
        self.discoverer.debug_tag = 'discoverer'
        # The device that is expected to be discovered
        self.target = android_device.get_device(self.ads, label='target')
        self.target.debug_tag = 'target'
        self.target.load_snippet('mbs',
                                 'com.google.android.mobly.snippet.bundled')
        self.discoverer.load_snippet(
            'mbs', 'com.google.android.mobly.snippet.bundled')

    def setup_test(self):
        # Make sure bluetooth is on.
        self.target.mbs.btEnable()
        self.discoverer.mbs.btEnable()
        # Set Bluetooth name on target device.
        self.target.mbs.btSetName('LookForMe!')

    def test_bluetooth_discovery(self):
        target_name = self.target.mbs.btGetName()
        self.target.log.info('Become discoverable with name "%s" for %ds.',
                             target_name, DISCOVERABLE_TIME)
        self.target.mbs.btBecomeDiscoverable(DISCOVERABLE_TIME)
        self.discoverer.log.info('Looking for Bluetooth devices.')
        discovered_devices = self.discoverer.mbs.btDiscoverAndGetResults()
        self.discoverer.log.debug('Found Bluetooth devices: %s',
                                  pprint.pformat(discovered_devices, indent=2))
        discovered_names = [device['Name'] for device in discovered_devices]
        logging.info('Verifying the target is discovered by the discoverer.')
        asserts.assert_true(
            target_name in discovered_names,
            'Failed to discover the target device %s over Bluetooth.' %
            target_name)

    def teardown_test(self):
        # Turn Bluetooth off on both devices after test finishes.
        self.target.mbs.btDisable()
        self.discoverer.mbs.btDisable()


if __name__ == '__main__':
    test_runner.main()

```

There's potentially a lot more we could do in this test, e.g. check
the hardware address, see whether we can pair devices, transfer files, etc.

To learn more about the features included in MBS, go to [MBS repo]
(https://github.com/google/mobly-bundled-snippets) to see how to check its help
menu.

To learn more about Mobly Snippet Lib, including features like Espresso support
and asynchronous calls, see the [snippet lib examples]
(https://github.com/google/mobly-snippet-lib/tree/master/examples).
