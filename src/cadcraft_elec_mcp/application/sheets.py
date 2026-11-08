"""Sheet use cases: define power/control/PLC-I/O/network/... sheets and their current paths."""

from __future__ import annotations

import re
from typing import Any

from ..domain.model import CircuitPath, IoKind, SheetKind, SheetSpec
from ..errors import DuplicateError, ProjectError
from .session import Session


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "sheet"


def add_sheet(
    session: Session,
    kind: SheetKind,
    title: str,
    *,
    sheet_id: str | None = None,
    paths: list[CircuitPath] | None = None,
    plc: str | None = None,
    io_kinds: list[IoKind] | None = None,
    note: str = "",
    position: int | None = None,
) -> dict[str, Any]:
    project = session.project
    new_id = sheet_id or _slug(title)
    if any(s.id == new_id for s in project.sheets):
        raise DuplicateError(f"Sheet id {new_id!r} already exists.", hint="Use sheet_update or another id.")
    if kind is SheetKind.PLC_IO and not plc:
        raise ProjectError("plc_io sheets need 'plc' (the CPU or module tag).")
    for path in paths or []:
        for element in path.elements:
            project.device(element.device)  # fail early on unknown tags
    sheet = SheetSpec(
        id=new_id,
        kind=kind,
        title=title,
        paths=list(paths or []),
        plc=plc,
        io_kinds=list(io_kinds or []),
        note=note,
    )
    if position is None:
        project.sheets.append(sheet)
    else:
        project.sheets.insert(max(position - 1, 0), sheet)
    session.commit()
    return sheet.model_dump(mode="json", exclude_defaults=True)


def add_paths(session: Session, sheet_id: str, paths: list[CircuitPath]) -> dict[str, Any]:
    sheet = session.project.sheet(sheet_id)
    if sheet.kind not in (SheetKind.POWER, SheetKind.CONTROL):
        raise ProjectError(
            f"Sheet {sheet_id} is {sheet.kind.value}; paths only apply to power/control sheets."
        )
    for path in paths:
        for element in path.elements:
            session.project.device(element.device)
    sheet.paths.extend(paths)
    session.commit()
    return {"sheet": sheet_id, "paths": len(sheet.paths)}


def update_sheet(session: Session, sheet_id: str, changes: dict[str, Any]) -> dict[str, Any]:
    project = session.project
    sheet = project.sheet(sheet_id)
    data = sheet.model_dump()
    data.update({k: v for k, v in changes.items() if v is not None})
    updated = SheetSpec.model_validate(data)
    project.sheets[project.sheets.index(sheet)] = updated
    session.commit()
    return updated.model_dump(mode="json", exclude_defaults=True)


def remove_sheet(session: Session, sheet_id: str) -> dict[str, str]:
    project = session.project
    project.sheets.remove(project.sheet(sheet_id))
    session.commit()
    return {"removed": sheet_id}


def move_sheet(session: Session, sheet_id: str, position: int) -> list[str]:
    project = session.project
    sheet = project.sheet(sheet_id)
    project.sheets.remove(sheet)
    project.sheets.insert(max(position - 1, 0), sheet)
    session.commit()
    return [s.id for s in project.sheets]


def get_sheet(session: Session, sheet_id: str) -> dict[str, Any]:
    return session.project.sheet(sheet_id).model_dump(mode="json", exclude_defaults=True)
