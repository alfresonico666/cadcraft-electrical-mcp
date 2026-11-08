"""Shared state of one build: document, profile, page allocation, netlist and cross references."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from ezdxf.document import Drawing
from ezdxf.layouts import Modelspace

from ..domain.model import Device, PotentialKind, Project
from ..domain.numbering import WireNumberer
from ..drawing import SheetGeometry, TitleBlockBuilder, draw_frame, sheet_geometry
from ..errors import GenerationError
from ..standards import StandardProfile
from ..symbols import SymbolLibrary, TerminalAllocator
from .crossref import CrossRefRegistry


@dataclass
class Wire:
    number: str
    from_ref: str
    to_ref: str
    potential_kind: PotentialKind
    color_code: str
    cross_section_mm2: float
    sheet: int
    ref: str
    potential: str | None = None


@dataclass
class Page:
    geometry: SheetGeometry
    title: str
    kind: str


@dataclass
class BuildContext:
    project: Project
    profile: StandardProfile
    doc: Drawing
    title_block: TitleBlockBuilder
    symbols: SymbolLibrary
    terminals: TerminalAllocator = field(default_factory=TerminalAllocator)
    xrefs: CrossRefRegistry = field(default_factory=CrossRefRegistry)
    wires: list[Wire] = field(default_factory=list)
    pages: list[Page] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    numberer: WireNumberer = field(init=False)
    finalizers: list[Callable[[], None]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.numberer = WireNumberer(self.profile.numbering)

    @property
    def msp(self) -> Modelspace:
        return self.doc.modelspace()

    @property
    def vertical(self) -> bool:
        return self.profile.orientation == "vertical"

    def device(self, tag: str) -> Device:
        if not self.project.has_device(tag):
            raise GenerationError(
                f"Device {tag!r} is used on a sheet but does not exist.",
                hint="Add it with device_add or fix the sheet definition.",
            )
        return self.project.device(tag)

    def designation(self, device: Device) -> str:
        if not self.profile.show_full_designation:
            return device.tag
        prefix = ""
        if device.function:
            prefix += f"={device.function}"
        if device.location:
            prefix += f"+{device.location}"
        return prefix + device.tag

    def new_page(self, title: str, kind: str) -> SheetGeometry:
        index = len(self.pages)
        geo = sheet_geometry(self.profile, index, index + 1)
        draw_frame(self.msp, geo, self.profile)
        self.pages.append(Page(geo, title, kind))
        return geo

    def add_wire(self, wire: Wire) -> None:
        self.wires.append(wire)

    def finish_title_blocks(self, file_name: str) -> None:
        """Title blocks need the total page count, so they are inserted at the end."""
        info = self.project.info
        total = str(len(self.pages))
        for page in self.pages:
            values = {
                "company": info.company,
                "client": info.client,
                "plant": info.plant,
                "project_title": info.project_title,
                "project_code": info.project_code,
                "machine": info.machine,
                "sheet_title": page.title,
                "file": file_name,
                "standard": self.profile.title,
                "author": info.author,
                "reviewer": info.reviewer,
                "date": info.date,
                "revision": info.revision,
                "sheet": f"{page.geometry.number} / {total}",
                "sheets": total,
                "description": info.description,
            }
            self.title_block.insert(self.msp, page.geometry, values)
