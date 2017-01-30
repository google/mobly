---
layout: page
title: "Lesson 3: User parameters"
permalink: /tutorials/lesson3.html
site_nav_category: tutorials
site_nav_category_order: 103
---

You could specify user parameters to be passed into your test class in the
config file.

In the following config, we added a user parameter `favorite_food`.

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

