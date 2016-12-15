---
layout: page
title: "Lesson 4: Multiple test beds"
permalink: /tutorials/lesson4.html
site_nav_category: tutorials
site_nav_category_order: 104
---

Multiple test beds can be configured in one configuration file.

**sample_config.json**

```python
{
    "testbed":[
        {
            "name" : "XyzTestBed",
            "AndroidDevice" : [{"serial": "xyz", "phone_number": "123456"}]
        },
        {
            "name" : "AbcTestBed",
            "AndroidDevice" : [{"serial": "abc", "label": "golden_device"}]
        }
    ],
    "logpath" : "/tmp/logs",
    "favorite_food": "green eggs and ham"
}
```

You can choose which one to execute on with the command line argument
`--test_bed`:

    $ python hello_world_test.py -c sample_config.json --test_bed AbcTestBed

*Expect:* A "Hello World!" and a "Goodbye!" toast notification appear on your device's
screen.



