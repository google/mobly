---
layout: page
title: "Lesson 2: Invoking a specific test case"
permalink: /tutorials/lesson2.html
site_nav_category: tutorials
site_nav_category_order: 102
---

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

    $ python hello_world_test.py -c sample_config.json --test_case test_bye


*Expect:* A "Goodbye!" toast notification appears on your device's screen.

You can dictate what test cases to execute within a test script and their
execution order, shown below:

    $ python hello_world_test.py -c sample_config.json --test_case test_bye test_hello test_bye

*Expect:* Toast notifications appear on your device's screen in the following order:
"Goodbye!", "Hello World!", "Goodbye!".


