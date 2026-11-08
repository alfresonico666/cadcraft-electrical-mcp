"""Project use cases: create, open, describe, update title-block data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..domain.model import Potential, PotentialKind, Project, TitleBlockInfo
from ..errors import DuplicateError
from ..standards import available_profiles, load_profile
from .session import Session

DEFAULT_POTENTIALS = {
    "iec": [
        ("L1", PotentialKind.AC_PHASE, "400/230 VAC"),
        ("L2", PotentialKind.AC_PHASE, ""),
        ("L3", PotentialKind.AC_PHASE, ""),
        ("N", PotentialKind.AC_NEUTRAL, ""),
        ("PE", PotentialKind.PE, ""),
        ("24V", PotentialKind.DC_PLUS, "24 VDC"),
        ("0V", PotentialKind.DC_MINUS, "0 VDC"),
    ],
    "nfpa": [
        ("L1", PotentialKind.AC_PHASE, "480 VAC"),
        ("L2", PotentialKind.AC_PHASE, ""),
        ("L3", PotentialKind.AC_PHASE, ""),
        ("N", PotentialKind.AC_NEUTRAL, ""),
        ("PE", PotentialKind.PE, ""),
        ("24V", PotentialKind.DC_PLUS, "24 VDC"),
        ("0V", PotentialKind.DC_MINUS, "0 VDC"),
    ],
}


def create_project(
    session: Session, info: TitleBlockInfo, profile: str, directory: str | None, overwrite: bool = False
) -> dict[str, Any]:
    load_profile(profile)  # validates the name
    path = (
        (Path(directory) / f"{info.project_code}.elec.yaml")
        if directory
        else session.store.project_file(info.project_code)
    )
    if path.exists() and not overwrite:
        raise DuplicateError(
            f"Project file already exists: {path}", hint="Use project_open or overwrite=true."
        )
    family = "nfpa" if profile.startswith("nfpa") else "iec"
    project = Project(
        info=info,
        profile=profile,
        potentials=[Potential(name=n, kind=k, voltage=v) for n, k, v in DEFAULT_POTENTIALS[family]],
    )
    session.activate(project, path)
    session.commit()
    return describe(session)


def open_project(session: Session, code_or_path: str) -> dict[str, Any]:
    path = session.store.resolve(code_or_path)
    session.activate(session.store.load(path), path)
    return describe(session)


def describe(session: Session) -> dict[str, Any]:
    project = session.project
    return {
        "path": str(session.path),
        "profile": project.profile,
        "profile_title": session.profile.title,
        "info": project.info.model_dump(),
        "counts": {
            "devices": len(project.devices),
            "sheets": len(project.sheets),
            "plc_io": len(project.plc_io),
            "network_links": len(project.network),
            "terminal_strips": len(project.terminal_strips),
        },
        "potentials": [p.model_dump(mode="json") for p in project.potentials],
        "sheets": [
            {"id": s.id, "kind": s.kind.value, "title": s.title, "paths": len(s.paths)}
            for s in project.sheets
        ],
        "cabinet": project.cabinet.model_dump(mode="json") if project.cabinet else None,
        "output_dir": str(session.path.parent / "output"),
    }


def update_info(session: Session, changes: dict[str, Any]) -> dict[str, Any]:
    info = session.project.info.model_copy(update={k: v for k, v in changes.items() if v is not None})
    session.project.info = TitleBlockInfo.model_validate(info.model_dump())
    session.commit()
    return session.project.info.model_dump()


def set_profile(session: Session, profile: str) -> dict[str, Any]:
    load_profile(profile)
    session.project.profile = profile
    session.commit()
    return {"profile": profile, "available": available_profiles()}


def set_potential(session: Session, potential: Potential) -> list[dict[str, Any]]:
    session.project.upsert_potential(potential)
    session.commit()
    return [p.model_dump(mode="json") for p in session.project.potentials]
