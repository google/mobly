---
layout: page
title: "Lesson 4: Multiple test beds"
permalink: /tutorials/lesson4.html
site_nav_category: tutorials
site_nav_category_order: 104
---

Multiple test beds can be configured in one configuration file.

**sample_config.yml**

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

    $ python hello_world_test.py -c sample_config.json --test_bed AbcTestBed

*Expect:* A "Hello World!" and a "Goodbye!" toast notification appear on your device's
screen.



