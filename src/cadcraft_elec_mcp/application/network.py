"""Network use cases (PROFINET / Ethernet / IO-Link links between device ports)."""

from __future__ import annotations

from typing import Any

from ..domain.model import NetworkLink
from ..errors import NotFoundError
from .session import Session


def add_links(session: Session, links: list[NetworkLink]) -> list[dict[str, Any]]:
    project = session.project
    for link in links:
        project.device(link.a_device)
        project.device(link.b_device)
        project.network.append(link)
    session.commit()
    return [link.model_dump(mode="json", exclude_defaults=True) for link in links]


def remove_link(session: Session, a_device: str, b_device: str) -> dict[str, str]:
    project = session.project
    before = len(project.network)
    project.network = [n for n in project.network if {n.a_device, n.b_device} != {a_device, b_device}]
    if len(project.network) == before:
        raise NotFoundError(f"No link between {a_device} and {b_device}.")
    session.commit()
    return {"removed": f"{a_device} <-> {b_device}"}


def list_links(session: Session) -> list[dict[str, Any]]:
    return [n.model_dump(mode="json", exclude_defaults=True) for n in session.project.network]
