"""Cabinet use cases: configure enclosure/plate, resolve device sizes, plan the back plate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import ezdxf
from ezdxf import bbox

from ..domain.designation import natural_key
from ..domain.model import CabinetSpec, Device, DeviceKind, Mount, Placement, RailSpec
from ..errors import NotFoundError
from ..layout import CabinetPlan, DeviceBox, plan_backplate
from ..logging_setup import get_logger
from .session import Session

log = get_logger("application.cabinet")

DEFAULT_SIZE = (20.0, 80.0)
TERMINAL_PITCH = 5.2
TERMINAL_END = 9.0
TERMINAL_HEIGHT = 50.0
_NOT_IN_CABINET = {DeviceKind.CABLE, DeviceKind.MOTOR}
_ORDER = [
    DeviceKind.MAIN_SWITCH,
    DeviceKind.SURGE_PROTECTOR,
    DeviceKind.RCD,
    DeviceKind.MCB,
    DeviceKind.MPCB,
    DeviceKind.FUSE,
    DeviceKind.CONTACTOR,
    DeviceKind.OVERLOAD,
    DeviceKind.PSU,
    DeviceKind.TRANSFORMER,
    DeviceKind.PLC_CPU,
    DeviceKind.PLC_MODULE,
    DeviceKind.FIELDBUS_COUPLER,
    DeviceKind.NETWORK_SWITCH,
    DeviceKind.IOLINK_MASTER,
    DeviceKind.SAFETY_RELAY,
    DeviceKind.RELAY,
    DeviceKind.TIMER_RELAY,
    DeviceKind.MEASURING_SENSOR,
    DeviceKind.VFD,
    DeviceKind.GENERIC,
    DeviceKind.TERMINAL_STRIP,
]


@dataclass
class ResolvedBoxes:
    plate: list[DeviceBox]
    door: list[DeviceBox]
    sized_from_default: list[str]


def configure(session: Session, changes: dict[str, Any]) -> dict[str, Any]:
    project = session.project
    data = project.cabinet.model_dump() if project.cabinet else {}
    catalog_id = changes.get("enclosure_catalog_id")
    if catalog_id:
        entry = session.catalog.get(catalog_id)
        if entry.width_mm:
            data["enclosure_width"] = entry.width_mm
        if entry.height_mm:
            data["enclosure_height"] = entry.height_mm
        if entry.depth_mm:
            data["enclosure_depth"] = entry.depth_mm
    data.update({k: v for k, v in changes.items() if v is not None})
    project.cabinet = CabinetSpec.model_validate(data)
    session.commit()
    return project.cabinet.model_dump(mode="json")


def set_rails(session: Session, rails: list[list[str]]) -> dict[str, Any]:
    spec = _spec(session)
    for rail in rails:
        for tag in rail:
            session.project.device(tag)
    spec.rails = [RailSpec(devices=list(r)) for r in rails]
    session.commit()
    return spec.model_dump(mode="json")


def place(session: Session, tag: str, x: float | None, y: float | None) -> dict[str, Any]:
    spec = _spec(session)
    session.project.device(tag)
    if x is None or y is None:
        spec.placements.pop(tag, None)
    else:
        spec.placements[tag] = Placement(x=x, y=y)
    session.commit()
    return {"placements": {k: v.model_dump() for k, v in spec.placements.items()}}


def _spec(session: Session) -> CabinetSpec:
    if session.project.cabinet is None:
        session.project.cabinet = CabinetSpec()
    return session.project.cabinet


def _model_size(path: str) -> tuple[float, float] | None:
    try:
        extents = bbox.extents(ezdxf.readfile(path).modelspace(), fast=True)
    except (OSError, ezdxf.DXFError):
        return None
    return (extents.size.x, extents.size.y) if extents.has_data else None


def _box(session: Session, device: Device, sized_default: list[str]) -> DeviceBox:
    width, height = device.width_mm, device.height_mm
    model = device.model_dxf
    if device.catalog_id:
        try:
            entry = session.catalog.get(device.catalog_id)
            width, height = width or entry.width_mm, height or entry.height_mm
            model = model or entry.model_dxf
        except NotFoundError:
            pass
    if model and not Path(model).is_file():
        log.warning("Model %s for %s not found", model, device.tag)
        model = None
    if device.kind is DeviceKind.TERMINAL_STRIP:
        count = 0
        for strip in session.project.terminal_strips:
            if strip.tag == device.tag:
                count = len(strip.terminals)
        width = width or (max(count, 1) * TERMINAL_PITCH + 2 * TERMINAL_END)
        height = height or TERMINAL_HEIGHT
    if (not width or not height) and model:
        size = _model_size(model)
        if size:
            width, height = width or size[0], height or size[1]
    if not width or not height:
        sized_default.append(device.tag)
        width, height = width or DEFAULT_SIZE[0], height or DEFAULT_SIZE[1]
    label = device.part_number or device.description
    return DeviceBox(device.tag, float(width), float(height), model, label)


def resolve_boxes(session: Session) -> ResolvedBoxes:
    project = session.project
    spec = _spec(session)
    sized: list[str] = []
    door_tags = set(spec.door_devices)
    plate: list[Device] = []
    door: list[Device] = []
    for device in project.devices:
        if device.kind in _NOT_IN_CABINET:
            continue
        if device.mount is Mount.DOOR or device.tag in door_tags:
            door.append(device)
        elif device.mount in (Mount.DIN_RAIL, Mount.BACKPLATE):
            plate.append(device)
    order = {kind: i for i, kind in enumerate(_ORDER)}
    plate.sort(key=lambda d: (order.get(d.kind, len(_ORDER) - 1), natural_key(d.tag)))
    return ResolvedBoxes(
        [_box(session, d, sized) for d in plate], [_box(session, d, sized) for d in door], sized
    )


def plan(session: Session) -> tuple[CabinetPlan, ResolvedBoxes]:
    spec = _spec(session)
    boxes = resolve_boxes(session)
    rails = [r.devices for r in spec.rails] or None
    return plan_backplate(spec, boxes.plate, rails), boxes
