"""Standards profile model + loader.

Profiles are *data* (YAML under ``standards/profiles``). Nothing in generators hard-codes a colour,
a letter code or a sheet size: they all ask the active :class:`StandardProfile`. A profile may
``extends:`` another one; mappings are deep-merged.
"""

from __future__ import annotations

from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from ..domain.designation import next_tag
from ..domain.model import DeviceKind, PotentialKind
from ..domain.numbering import NumberingStrategy
from ..errors import StandardsError


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TagRules(_Strict):
    prefix: str = "-"
    scheme: str = ""
    codes: dict[DeviceKind, str]


class SheetFormat(_Strict):
    paper: str
    width: float
    height: float
    margin_left: float
    margin_right: float
    margin_top: float
    margin_bottom: float
    zone_band: float
    columns: int = Field(ge=1)
    rows: int = Field(ge=1, description="ISO 5457 zone rows (letters)")
    rungs: int = Field(default=20, ge=1, description="Ladder rungs per band (horizontal profiles)")
    title_block_height: float


class TextHeights(_Strict):
    general: float
    terminal: float
    wire_number: float
    designation: float
    heading: float
    title: float
    minimum: float


class LineWeights(_Strict):
    thin: float
    symbol: float
    wire: float
    frame: float


class WireColor(_Strict):
    code: str
    name: str
    aci: int


class LayerDef(_Strict):
    name: str
    color: int
    linetype: str = "Continuous"
    lineweight: float = 0.25


class StandardProfile(_Strict):
    name: str
    title: str
    symbol_style: Literal["iec", "nfpa"]
    orientation: Literal["vertical", "horizontal"]
    numbering: NumberingStrategy
    show_full_designation: bool = False
    tag: TagRules
    sheet: SheetFormat
    text: TextHeights
    lineweights: LineWeights
    wire_colors: dict[PotentialKind, WireColor]
    cross_sections_mm2: dict[PotentialKind, float]
    layers: list[LayerDef]
    terminal_marking: dict[str, Any] = Field(default_factory=dict)

    # -- designations ---------------------------------------------------------------------------
    def code_for(self, kind: DeviceKind) -> str:
        return self.tag.codes.get(kind, self.tag.codes.get(DeviceKind.GENERIC, "A"))

    def tag_prefix(self, kind: DeviceKind) -> str:
        return f"{self.tag.prefix}{self.code_for(kind)}"

    def allocate_tag(self, kind: DeviceKind, existing: list[str]) -> str:
        return next_tag(self.tag_prefix(kind), existing)

    # -- wires ----------------------------------------------------------------------------------
    def wire_color(self, kind: PotentialKind) -> WireColor:
        return self.wire_colors[kind]

    def wire_layer(self, kind: PotentialKind) -> str:
        return f"E-WIRE-{kind.value.upper()}"

    def all_layers(self) -> list[LayerDef]:
        wires = [
            LayerDef(
                name=self.wire_layer(kind), color=color.aci, linetype="Continuous",
                lineweight=self.lineweights.wire,
            )
            for kind, color in self.wire_colors.items()
        ]
        return [*self.layers, *wires]


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict) and key != "codes":
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _profile_dir() -> Path:
    return Path(str(resources.files("cadcraft_elec_mcp.standards") / "profiles"))


def available_profiles() -> list[str]:
    return sorted(p.stem for p in _profile_dir().glob("*.yaml"))


def _raw(name: str, seen: tuple[str, ...] = ()) -> dict[str, Any]:
    if name in seen:
        raise StandardsError(f"Circular 'extends' in profiles: {' -> '.join((*seen, name))}")
    path = _profile_dir() / f"{name}.yaml"
    if not path.is_file():
        raise StandardsError(
            f"Unknown standards profile {name!r}.", hint=f"Available: {', '.join(available_profiles())}"
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    parent = data.pop("extends", None)
    if parent:
        return _deep_merge(_raw(parent, (*seen, name)), data)
    return dict(data)


@cache
def load_profile(name: str) -> StandardProfile:
    try:
        return StandardProfile.model_validate(_raw(name))
    except StandardsError:
        raise
    except Exception as exc:
        raise StandardsError(f"Invalid profile {name!r}: {exc}") from exc
