[![Build Status](https://travis-ci.org/google/mobly.svg?branch=master)](https://travis-ci.org/google/mobly)

# Welcome to Mobly

**Mobly** is a Python-based test framework that specializes in supporting test
cases that require multiple devices, complex environments, or custom hardware
setups.

Here are some example use cases:
*   P2P data transfer between two devices
*   Conference calls across three phones
*   Wearable device interacting with a phone
*   Internet-Of-Things devices interacting with each other
*   Testing RF characteristics of devices with special equipment
*   Testing LTE network by controlling phones, base stations, and eNBs

Mobly can support many different types of devices and equipment, and it's easy
to plug your own device or custom equipment/service into Mobly.

Mobly comes with a set of libs to control common devices like Android devices.

While developed by Googlers, Mobly is not an official Google product.

## Compatibility

Mobly is compatible with both *python 3.4+* and *python 2.7*.

Mobly tests could run on the following platforms:
  - Ubuntu 14.04+
  - MacOS 10.6+
  - Windows 7+

## System dependencies
  - adb (1.0.36+ recommended)
  - python2.7 or python3.4+
  - python-setuptools

*If you use Python3, use `pip3` and `python3` (or python3.x) accordingly.*

## Installation
You can install the released package from pip

```
$ pip install mobly
```

or download the source then run `setup.py` to use the bleeding edge:

```
$ git clone https://github.com/google/mobly.git
$ cd mobly
$ python setup.py install
```

You may need `sudo` for the above commands if your system has certain permission
restrictions.

## Tutorials
To get started with some simple tests, see the [Mobly tutorial](docs/tutorial.md).

## Mobly Snippet
The Mobly Snippet projects let users better control Android devices.

* [Mobly Snippet Lib](https://github.com/google/mobly-snippet-lib): used for
triggering custom device-side code from host-side Mobly tests. You could use existing
Android libraries like UI Automator and Espresso.
* [Mobly Bundled Snippets](https://github.com/google/mobly-bundled-snippets): a set
of Snippets to allow Mobly tests to control Android devices by exposing a simplified
version of the public Android API suitable for testing.
