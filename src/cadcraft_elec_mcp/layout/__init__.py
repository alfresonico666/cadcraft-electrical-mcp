"""Physical layout planning (back plate, door) – pure geometry."""

from .cabinet_planner import CabinetPlan, DeviceBox, PlacedDevice, RailRow, Rect, plan_backplate

__all__ = ["CabinetPlan", "DeviceBox", "PlacedDevice", "RailRow", "Rect", "plan_backplate"]
