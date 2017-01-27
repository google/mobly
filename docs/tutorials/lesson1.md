---
layout: page
title: "Lesson 1: Hello World"
permalink: /tutorials/lesson1.html
site_nav_category: tutorials
site_nav_category_order: 101
---

Let's start with the simple example of posting "Hello World" on the Android
device's screen. Create the following files:

**sample_config.json**

```python
{
    "testbed":
    [
        {
            "_description": "A testbed where adb will find Android devices.",
            "name": "SampleTestBed",
            "AndroidDevice": "*"
        }
    ],
    "logpath": "/tmp/logs"
}
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
    self.dut.load_sl4a()

  def test_hello(self):
    self.dut.sl4a.makeToast('Hello World!')

if __name__ == "__main__":
  test_runner.main()
```

*To execute:*

    $ python hello_world_test.py -c sample_config.json

*Expect:* A "Hello World!" toast notification appears on your device's screen.

Within SampleTestBed, we used `"AndroidDevice" : "*"` to tell the test runner to
automatically find all connected Android devices. You can also specify
particular devices by serial number and attach extra attributes to the object:

```python
"AndroidDevice": [
  {"serial": "xyz", "phone_number": "123456"},
  {"serial": "abc", "label": "golden_device"},
]
```

