# Custom Controller Tutorial

Mobly enables users to control custom hardware devices (e.g., smart lights, switches) by creating custom controller modules. This tutorial explains how to implement a production-ready custom controller.

## Controller Module Interface

A Mobly controller module must implement the following top-level functions:

* **`create(configs)`**: Instantiates controller objects from the configuration.
* **`destroy(objects)`**: Cleans up resources when the test ends.
* **`get_info(objects)`**: Returns device information for the test report.

## Implementation Example

The following example demonstrates a custom controller for a **Smart Light**, featuring type hinting, input validation, and fault-tolerant cleanup.

### 1. Controller Module (`smart_light.py`)

Save this code as `smart_light.py`.

```python
"""Mobly controller module for a Smart Light."""

import logging
from typing import Any, Dict, List

# The key used in the config file to identify this controller.
MOBLY_CONTROLLER_CONFIG_NAME = "SmartLight"

class SmartLight:
    """A class representing a smart light device.
    
    Attributes:
        name: String, the name of the device.
        ip: String, the IP address of the device.
    """

    def __init__(self, name: str, ip: str):
        self.name = name
        self.ip = ip
        self.is_on = False
        logging.info("Initialized SmartLight [%s] at %s", self.name, self.ip)

    def power_on(self):
        """Turns the light on."""
        self.is_on = True
        logging.info("SmartLight [%s] turned ON", self.name)

    def power_off(self):
        """Turns the light off."""
        self.is_on = False
        logging.info("SmartLight [%s] turned OFF", self.name)

    def close(self):
        """Simulates closing the connection."""
        logging.info("SmartLight [%s] connection closed", self.name)


def create(configs: List[Dict[str, Any]]) -> List[SmartLight]:
    """Creates SmartLight instances from a list of configurations.

    Args:
        configs: A list of dicts, where each dict represents a configuration
            for a SmartLight device.

    Returns:
        A list of SmartLight objects.

    Raises:
        ValueError: If a required configuration parameter is missing.
    """
    devices = []
    for config in configs:
        if "name" not in config or "ip" not in config:
            raise ValueError(
                f"Invalid config: {config}. 'name' and 'ip' are required."
            )
        
        devices.append(SmartLight(
            name=config["name"],
            ip=config["ip"]
        ))
    return devices


def destroy(objects: List[SmartLight]) -> None:
    """Cleans up SmartLight instances.
    
    Args:
        objects: A list of SmartLight objects to be destroyed.
    """
    for light in objects:
        try:
            if light.is_on:
                light.power_off()
            light.close()
        except Exception:
            # Catching broad exceptions ensures that a failure in one device
            # does not prevent others from being cleaned up.
            logging.exception("Failed to clean up SmartLight [%s]", light.name)


def get_info(objects: List[SmartLight]) -> List[Dict[str, Any]]:
    """Returns information for the test result.

    Args:
        objects: A list of SmartLight objects.

    Returns:
        A list of dicts containing device information.
    """
    return [{"name": light.name, "ip": light.ip} for light in objects]

```

### 2. Controller Module (`smart_light.py`)

To use the custom controller, register it in your test script.

```python
from mobly import base_test
from mobly import test_runner
import smart_light

class LightTest(base_test.BaseTestClass):
    def setup_class(self):
        # Register the custom controller
        self.lights = self.register_controller(smart_light)

    def test_turn_on(self):
        light = self.lights[0]
        light.power_on()
        
        # Verify the light is on
        if not light.is_on:
            raise signals.TestFailure(f"Light {light.name} should be on!")

if __name__ == "__main__":
    test_runner.main()
```

### 3. Configuration File (config.yaml)
Define the device in your configuration file using the SmartLight key.
```yaml
TestBeds:
  - Name: BedroomTestBed
    Controllers:
      SmartLight:
        - name: "BedLight"
          ip: "192.168.1.50"
```
