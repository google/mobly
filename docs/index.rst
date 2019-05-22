.. Mobly documentation master file, created by
   sphinx-quickstart on Wed Feb 22 11:40:14 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Mobly's documentation!
=================================

**Mobly** is a Python-based test framework that specializes in supporting
test cases that require multiple devices, complex environments, or custom
hardware setups.

Here are some example use cases:

* P2P data transfer between two devices
* Conference calls across three phones
* Wearable device interacting with a phone
* Internet-of-Things devices interacting with each other
* Testing RF characteristics of devices with special equipment
* Testing LTE network by controlling phones, base stations, and eNBs

Mobly can support many different types of devices and equipment, and it's
easy to plug your own device or custom equipment/service into Mobly.

Mobly comes with a set of libraries to control common devices like Android
devices.

While developed by Googlers, Mobly is not an official Google product.

.. toctree::
   :maxdepth: 2

   tutorial
   android_device_service
   instrumentation_tutorial

License
-------

Copyright 2019 Google Inc. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
