---
layout: page
title: Getting Started with Mobly
permalink: /tutorials/index.html
site_nav_category: tutorials
is_site_nav_category2: true
site_nav_category_order: 10
---
{::options toc_levels="2"/}

* TOC
{:toc}

## Overview
__What is Mobly?__

Mobly is a Python-based test framework that specializes in
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

__What will I learn here?__

Writing and executing simple test cases that use Android devices. We are
focusing on Android devices here since they are the most accessible devices.
Mobly supports various devices and you can also use your own custom
hardware/equipment.

## Requirements

### Tutorial requirements
*   A computer with 2 USB ports (or a USB hub).
*   One or two Android devices with the app SL4A installed.\*
*   Mobly package and its system dependencies installed on the computer.
*   A working adb setup. To check, connect one Android device to the computer
    and make sure it has "USB debugging" enabled. Make sure the device shows up
    in the list printed by `adb devices`.

 \* You can get SL4A from the
[Android repo](https://source.android.com/source/downloading.html), under
project `<aosp>/external/sl4a`

It can be built like a regular system app with `mm` commands. It needs to be
signed with the build you use on your Android devices.

### Mobly Installation
___Mobly system requirements___

*   adb (1.0.36+ recommended)
*   python2.7 or python3.4+
*   python-setuptools or python3.4-setuptools or later

__Python compatibility__

Mobly is compatible with both python 3.4+ and python 2.7.\*

For Python3

```
sudo python3 setup.py install
```

For Python2

```
sudo python setup.py install
```

\*Use the Python version you installed Mobly with to run the tests. So if you
installed with 'python3', execute tests with 'python3'.

