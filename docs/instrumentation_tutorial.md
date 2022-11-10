# Running Android instrumentation tests with Mobly

This tutorial shows how to write and execute Mobly tests for running Android
instrumentation tests. For more details about instrumentation tests, please refer to
https://developer.android.com/studio/test/index.html.

## Setup Requirements

*   A computer with at least 1 USB ports.
*   Mobly package and its system dependencies installed on the computer.
*   One Android device that is compatible with your instrumentatation and
    application apks.
*   Your instrumentation and applications apks for installing.
*   A working adb setup. To check, connect one Android device to the computer
    and make sure it has "USB debugging" enabled. Make sure the device shows up
    in the list printed by `adb devices`.

## Example Name Substitutions

Here are the names that we use in this tutorial, substitute these names with
your actual apk package and file names when using your real files:

*   The application apk : `application.apk`
*   The instrumentation apk : `instrumentation_test.apk`
*   The instrumentation test package : `com.example.package.test`

## Example 1: Running Instrumentation Tests

Assuming your apks are already installed on devices. You can just subclass the
instrumentation test class and run against your package.

You will need a configuration file for Mobly to find your devices.

***sample_config.yml***

```yaml
TestBeds:
  - Name: BasicTestBed
    Controllers:
        AndroidDevice: '*'
```

***instrumentation_test.py***

```python
from mobly import base_instrumentation_test
from mobly import test_runner
from mobly.controllers import android_device

class InstrumentationTest(base_instrumentation_test.BaseInstrumentationTestClass):
    def setup_class(self):
        self.dut = self.register_controller(android_device)[0]

    def test_instrumentation(self):
        self.run_instrumentation_test(self.dut, 'com.example.package.test')


if __name__ == '__main__':
  test_runner.main()
```

*To execute:*

```
$ python instrumentation_test.py -c sample_config.yml
```

*Expect*:

The output from normally running your instrumentation tests along with a summary
of the test results.

## Example 2: Specifying Instrumentation Options

If your instrumentation tests use instrumentation options for controlling
behaviour, then you can put these options into your configuration file and then
fetch them when you run your instrumentatation tests.

***sample_config.yml***

```yaml
TestBeds:
  - Name: BasicTestBed
    Controllers:
        AndroidDevice: '*'
    TestParams:
        instrumentation_option_annotation: android.support.test.filters.LargeTest
        instrumentation_option_nonAnnotation: android.support.test.filters.SmallTest
```

***instrumentation_test.py***

```python
from mobly import base_instrumentation_test
from mobly import test_runner
from mobly.controllers import android_device

class InstrumentationTest(base_instrumentation_test.BaseInstrumentationTestClass):
    def setup_class(self):
        self.dut = self.register_controller(android_device)[0]
        self.options = self.parse_instrumentation_options(self.user_params)

    def test_instrumentation(self):
        self.run_instrumentation_test(self.dut, 'com.example.package.test',
            options=self.options)


if __name__ == '__main__':
  test_runner.main()
```

*To execute:*

```
$ python instrumentation_test.py -c sample_config.yml
```

*Expect*:

The output of your *LargeTest* instrumentation tests with no *SmallTest*
instrumentation test being run.

## Example 3 Using a Custom Runner

If you have a custom runner that you use for instrumentation tests, then you can
specify it in the *run_instrumentation_test* method call. Replace
`com.example.package.test.CustomRunner` with the fully qualified package name of
your real instrumentation runner.

```python
def test_instrumentation(self):
  self.run_instrumentation_test(self.dut, 'com.example.package.test',
      runner='com.example.package.test.CustomRunner')
```

## Example 4: Multiple Instrumentation Runs

If you have multiple devices that you want to run instrumentation tests
against, then you can simply call the *run_instrumentation_test* method
multiple times. If you need to distinguish between runs, then you can specify
a prefix.

***sample_config.yml***

```yaml
TestBeds:
  - Name: TwoDeviceTestBed
    Controllers:
        AndroidDevice:
          - serial: xyz
            label: dut
          - serial: abc
            label: dut
```

***instrumentation_test.py***

```python
from mobly import base_instrumentation_test
from mobly import test_runner
from mobly.controllers import android_device

class InstrumentationTest(base_instrumentation_test.BaseInstrumentationTestClass):
    def setup_class(self):
        self.ads = self.register_controller(android_device)
        # Get all of the dut devices to run instrumentation tests against.
        self.duts = android_device.get_devices(self.ads, label='dut')

    def test_instrumentation(self):
        # Iterate over the dut devices with a corresponding index.
        for index, dut in enumerate(self.duts):
            # Specify a prefix to help disambiguate the runs.
            self.run_instrumentation_test(dut, 'com.example.package.tests',
                prefix='test_run_%s' % index)


if __name__ == '__main__':
  test_runner.main()
```

*To execute:*

```
$ python instrumentation_test.py -c sample_config.yml
```

*Expect*:

The output from both instrumentation runs along with an aggregated summary of
the results from both runs.
