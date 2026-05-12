"""Compatibility shim for older sensor imports."""

from .power_device_sensor import EnergyDeviceSensor, IndividualLoadEnergySensor

__all__ = ["EnergyDeviceSensor", "IndividualLoadEnergySensor"]
