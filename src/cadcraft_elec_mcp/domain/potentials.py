"""Potential helpers (pure)."""

from __future__ import annotations

import re

from .model import PotentialKind, Project

_ORDER = ["L", "L1", "L2", "L3", "N", "N1", "PE"]


def infer_potential_kind(name: str) -> PotentialKind:
    """Best guess when a rail name is not declared in the project."""
    upper = name.upper().replace(" ", "")
    if upper == "L" or re.match(r"L[123](?![+\-\d])", upper):
        return PotentialKind.AC_PHASE
    if upper.startswith("PE") or upper in {"GND_PE", "GNYE"}:
        return PotentialKind.PE
    if re.fullmatch(r"N\d*(_\w+)?", upper):
        return PotentialKind.AC_NEUTRAL
    if upper in {"L-", "-24V", "GND"} or upper.startswith("0V") or re.fullmatch(r"M\d*", upper):
        return PotentialKind.DC_MINUS
    if ("V" in upper and any(ch.isdigit() for ch in upper)) or upper in {"L+", "+24V"}:
        return PotentialKind.DC_PLUS
    return PotentialKind.AC_CONTROL


def potential_kind(project: Project, name: str) -> PotentialKind:
    declared = project.potential(name)
    return declared.kind if declared else infer_potential_kind(name)


def rail_sort_key(name: str) -> tuple[int, str]:
    return (_ORDER.index(name) if name in _ORDER else len(_ORDER), name)
