#!/usr/bin/env python3.4
#
# Copyright 2016 Google Inc.
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# This is a mock third-party controller module used for unit testing Mobly.

import logging

MOBLY_CONTROLLER_CONFIG_NAME = "MagicDevice"


def create(configs):
    objs = []
    for c in configs:
        if isinstance(c, dict):
            c.pop("serial")
        objs.append(MagicDevice(c))
    return objs


def destroy(objs):
    print("Destroying magic")


def get_info(objs):
    infos = []
    for obj in objs:
        infos.append(obj.who_am_i())
    return infos


class MagicDevice(object):
    def __init__(self, config):
        self.magic = config

    def get_magic(self):
        logging.info("My magic is %s.", self.magic)
        return self.magic

    def who_am_i(self):
        return {"MyMagic": self.magic}
