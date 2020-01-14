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

NOTE: As part of the bigger [communitiy initiative](https://python3statement.org/),
we are planning to drop Python 2.7 support in 2020. Mobly 1.10 is likely the last
major release to support Python 2.7.

Mobly tests could run on the following platforms:
  - Ubuntu 14.04+
  - MacOS 10.6+
  - Windows 7+

| Platform | Build Status |
|----------|--------------|
| Linux    | [![Linux Build Status](https://travis-ci.org/google/mobly.svg?branch=master)](https://travis-ci.org/google/mobly) |
| Windows  | [![Windows Build Status](https://storage.googleapis.com/mobly-kokoro-build-badges/mobly-windows.svg)](https://fusion.corp.google.com/projectanalysis/current/KOKORO/prod%3Amobly%2Fgcp_windows%2Fcontinuous) |

## System dependencies
  - adb (1.0.36+ recommended)
  - python2.7 or python3.4+
  - python-setuptools

*If you use Python3, use `pip3` and `python3` (or python3.x) accordingly.*

## Installation
You can install the released package from pip

```sh
pip install mobly
```

or download the source then run `setup.py` to use the bleeding edge:

```sh
git clone https://github.com/google/mobly.git
cd mobly
python setup.py install
```

You may need `sudo` for the above commands if your system has certain permission
restrictions.

## Tutorials

* [Mobly 101](docs/tutorial.md) -
Simple test examples to get you started with Mobly.

* [Mobly Instrumentation Runner Tutorial](docs/instrumentation_tutorial.md) -
How to use Mobly's Android instrumentation test runner to run Android instrumentation tests.

* [Mobly AndroidDevice Service](docs/android_device_service.md) -
Create custom service to attach to Mobly's `AndroidDevice` controller.

## Mobly Snippet
The Mobly Snippet projects let users better control Android devices.

* [Mobly Snippet Lib](https://github.com/google/mobly-snippet-lib): used for
triggering custom device-side code from host-side Mobly tests. You could use existing
Android libraries like UI Automator and Espresso.
* [Mobly Bundled Snippets](https://github.com/google/mobly-bundled-snippets): a set
of Snippets to allow Mobly tests to control Android devices by exposing a simplified
version of the public Android API suitable for testing.
