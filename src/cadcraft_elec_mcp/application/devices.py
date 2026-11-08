"""Device use cases (add from catalog or manually, update, remove, list)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..domain.designation import natural_key
from ..domain.model import Device, DeviceKind, Mount
from ..errors import ProjectError
from .session import Session


class DeviceInput(BaseModel):
    """What a caller may give to create a device. Everything except kind/catalog is optional."""

    model_config = ConfigDict(extra="forbid")

    catalog_id: str | None = Field(default=None, description="Fill data from the catalog (library_search)")
    kind: DeviceKind | None = Field(default=None, description="Required when no catalog_id")
    tag: str | None = Field(default=None, description="Auto-assigned from the profile letter code if empty")
    description: str | None = None
    manufacturer: str | None = None
    part_number: str | None = None
    function: str | None = None
    location: str | None = None
    mount: Mount | None = None
    terminals: list[str] | None = None
    ports: list[str] | None = None
    width_mm: float | None = None
    height_mm: float | None = None
    model_dxf: str | None = None
    data: dict[str, str] | None = None


def add_devices(session: Session, items: list[DeviceInput]) -> list[dict[str, Any]]:
    project = session.project
    profile = session.profile
    created: list[Device] = []
    for item in items:
        values: dict[str, Any] = {}
        if item.catalog_id:
            entry = session.catalog.get(item.catalog_id)
            values.update(
                kind=entry.kind,
                manufacturer=entry.manufacturer,
                part_number=entry.part_number,
                description=entry.description,
                mount=entry.mount,
                terminals=list(entry.terminals),
                ports=list(entry.ports),
                width_mm=entry.width_mm,
                height_mm=entry.height_mm,
                depth_mm=entry.depth_mm,
                model_dxf=entry.model_dxf,
                catalog_id=entry.id,
            )
        values.update({k: v for k, v in item.model_dump(exclude={"catalog_id"}).items() if v is not None})
        if "kind" not in values:
            raise ProjectError("Each device needs 'kind' or 'catalog_id'.")
        kind = DeviceKind(values["kind"])
        if not values.get("tag"):
            values["tag"] = profile.allocate_tag(kind, [d.tag for d in project.devices])
        device = project.add_device(Device.model_validate(values))
        if kind is DeviceKind.TERMINAL_STRIP:
            project.get_or_create_strip(device.tag, device.description)
        created.append(device)
    session.commit()
    return [d.model_dump(mode="json", exclude_defaults=True) for d in created]


def update_device(session: Session, tag: str, changes: dict[str, Any]) -> dict[str, Any]:
    project = session.project
    device = project.device(tag)
    new_tag = changes.get("tag")
    data = device.model_dump()
    data.update({k: v for k, v in changes.items() if v is not None})
    updated = Device.model_validate(data)
    if new_tag and new_tag != tag:
        if project.has_device(new_tag):
            raise ProjectError(f"{new_tag} already exists.")
        _rename_references(session, tag, new_tag)
    project.devices[project.devices.index(device)] = updated
    project.devices.sort(key=lambda d: natural_key(d.tag))
    session.commit()
    return updated.model_dump(mode="json", exclude_defaults=True)


def _rename_references(session: Session, old: str, new: str) -> None:
    project = session.project
    for sheet in project.sheets:
        if sheet.plc == old:
            sheet.plc = new
        for path in sheet.paths:
            for element in path.elements:
                if element.device == old:
                    element.device = new
    for channel in project.plc_io:
        if channel.plc == old:
            channel.plc = new
        if channel.device == old:
            channel.device = new
        if channel.strip_terminal and channel.strip_terminal.startswith(f"{old}:"):
            channel.strip_terminal = new + channel.strip_terminal[len(old) :]
    for link in project.network:
        if link.a_device == old:
            link.a_device = new
        if link.b_device == old:
            link.b_device = new
    for strip in project.terminal_strips:
        if strip.tag == old:
            strip.tag = new
    if project.cabinet:
        for rail in project.cabinet.rails:
            rail.devices = [new if t == old else t for t in rail.devices]
        if old in project.cabinet.placements:
            project.cabinet.placements[new] = project.cabinet.placements.pop(old)
        project.cabinet.door_devices = [new if t == old else t for t in project.cabinet.door_devices]


def remove_device(session: Session, tag: str, force: bool = False) -> dict[str, Any]:
    project = session.project
    project.device(tag)
    refs = [s.id for s in project.sheets if any(e.device == tag for p in s.paths for e in p.elements)]
    refs += [c.address for c in project.plc_io if tag in (c.plc, c.device)]
    refs += [f"{n.a_device}-{n.b_device}" for n in project.network if tag in (n.a_device, n.b_device)]
    if refs and not force:
        raise ProjectError(
            f"{tag} is still referenced by: {', '.join(refs)}",
            hint="Remove those references first or call again with force=true.",
        )
    if force:
        for sheet in project.sheets:
            for path in sheet.paths:
                path.elements = [e for e in path.elements if e.device != tag]
        project.plc_io = [c for c in project.plc_io if c.plc != tag]
        for channel in project.plc_io:
            if channel.device == tag:
                channel.device = None
        project.network = [n for n in project.network if tag not in (n.a_device, n.b_device)]
        project.terminal_strips = [s for s in project.terminal_strips if s.tag != tag]
    project.remove_device(tag)
    session.commit()
    return {"removed": tag, "references_cleared": refs if force else []}


def list_devices(session: Session, kind: DeviceKind | None = None) -> list[dict[str, Any]]:
    return [
        {
            "tag": d.tag,
            "kind": d.kind.value,
            "description": d.description,
            "part_number": d.part_number,
            "manufacturer": d.manufacturer,
            "mount": d.mount.value,
            "ports": d.ports,
        }
        for d in session.project.devices
        if kind is None or d.kind is kind
    ]
