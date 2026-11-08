"""Title block (ISO 7200 fields) as a block with attributes, one INSERT per sheet.

Two sources:
* built-in parametric block (default);
* a company template DXF (``title_block_template`` setting): its model space is scaled into the
  title-block area and every TEXT/MTEXT containing ``{field}`` becomes an attribute, e.g.
  ``{project_title}``, ``{sheet_title}``, ``{sheet}``/``{sheets}``, ``{author}``, ``{date}`` ...
"""

from __future__ import annotations

import re
from pathlib import Path

import ezdxf
from ezdxf import bbox
from ezdxf.addons.importer import Importer
from ezdxf.document import Drawing
from ezdxf.enums import TextEntityAlignment
from ezdxf.layouts import BaseLayout, BlockLayout
from ezdxf.math import Matrix44

from ..errors import GenerationError
from ..logging_setup import get_logger
from ..standards import StandardProfile
from .document import TEXT_STYLE
from .sheet_frame import SheetGeometry

log = get_logger("drawing.title_block")

FIELDS = (
    "company", "client", "plant", "project_title", "project_code", "machine", "sheet_title", "file",
    "standard", "author", "reviewer", "date", "revision", "sheet", "sheets", "description",
)
_PLACEHOLDER = re.compile(r"\{(\w+)\}")

# (label, field, x0, y0, x1, y1, value height key) in fractions of the title-block size
_CELLS: list[tuple[str, str, float, float, float, float, str]] = [
    ("", "company", 0.00, 0.50, 0.18, 1.00, "heading"),
    ("Cliente / Client", "client", 0.00, 0.00, 0.18, 0.50, "general"),
    ("Proyecto / Project", "project_title", 0.18, 0.50, 0.52, 1.00, "heading"),
    ("No. proyecto / Job", "project_code", 0.18, 0.00, 0.30, 0.50, "designation"),
    ("Máquina / Machine", "machine", 0.30, 0.00, 0.52, 0.50, "general"),
    ("Hoja / Sheet title", "sheet_title", 0.52, 0.50, 0.78, 1.00, "heading"),
    ("Norma / Standard", "standard", 0.52, 0.00, 0.78, 0.50, "general"),
    ("Dibujó / Drawn", "author", 0.78, 0.6667, 0.90, 1.00, "general"),
    ("Revisó / Checked", "reviewer", 0.78, 0.3333, 0.90, 0.6667, "general"),
    ("Fecha / Date", "date", 0.78, 0.00, 0.90, 0.3333, "general"),
    ("Rev.", "revision", 0.90, 0.50, 1.00, 1.00, "designation"),
    ("Hoja / Sheet", "sheet", 0.90, 0.00, 1.00, 0.50, "designation"),
]


class TitleBlockBuilder:
    def __init__(self, doc: Drawing, profile: StandardProfile, template: Path | None = None) -> None:
        self.doc = doc
        self.profile = profile
        self.template = template
        self._name: str | None = None

    def ensure(self, width: float, height: float) -> str:
        if self._name:
            return self._name
        name = "TITLE_BLOCK"
        block = self.doc.blocks.new(name)
        if self.template is not None:
            self._from_template(block, width, height)
        else:
            self._parametric(block, width, height)
        self._name = name
        return name

    # -- built-in ----------------------------------------------------------------------------------
    def _parametric(self, block: BlockLayout, width: float, height: float) -> None:
        text = self.profile.text
        label_h = text.minimum
        block.add_lwpolyline([(0, 0), (width, 0), (width, height), (0, height)], close=True,
                             dxfattribs={"layer": "E-FRAME"})
        for label, field, fx0, fy0, fx1, fy1, size in _CELLS:
            x0, y0, x1, y1 = fx0 * width, fy0 * height, fx1 * width, fy1 * height
            block.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                                 dxfattribs={"layer": "E-TITLE"})
            if label:
                lbl = block.add_text(label, height=label_h * 0.8,
                                     dxfattribs={"layer": "E-TITLE", "style": TEXT_STYLE})
                lbl.set_placement((x0 + 1.0, y1 - 0.8), align=TextEntityAlignment.TOP_LEFT)
            value_h = min(getattr(text, size), (y1 - y0) * 0.45)
            attdef = block.add_attdef(field.upper(), insert=(x0 + 1.5, y0 + 1.5), height=value_h,
                                      dxfattribs={"layer": "E-TITLE", "style": TEXT_STYLE})
            attdef.set_placement((x0 + 1.5, y0 + 1.5), align=TextEntityAlignment.BOTTOM_LEFT)

    # -- company template --------------------------------------------------------------------------
    def _from_template(self, block: BlockLayout, width: float, height: float) -> None:
        assert self.template is not None
        try:
            source = ezdxf.readfile(self.template)
        except (OSError, ezdxf.DXFStructureError) as exc:
            raise GenerationError(f"Cannot read title block template {self.template}: {exc}") from exc
        importer = Importer(source, self.doc)
        importer.import_entities(source.modelspace(), target_layout=block)
        importer.finalize()
        extents = bbox.extents(block, fast=True)
        if not extents.has_data:
            raise GenerationError(f"Title block template {self.template} is empty.")
        scale = min(width / extents.size.x, height / extents.size.y)
        matrix = Matrix44.translate(-extents.extmin.x, -extents.extmin.y, 0) @ Matrix44.scale(scale)
        for entity in list(block):
            try:
                entity.transform(matrix)
            except (NotImplementedError, AttributeError):
                log.debug("Cannot transform %s in template", entity.dxftype())
        self._placeholders_to_attdefs(block)

    @staticmethod
    def _placeholders_to_attdefs(block: BlockLayout) -> None:
        for entity in list(block):
            if entity.dxftype() == "TEXT":
                raw = entity.dxf.text
                insert = entity.dxf.insert
                height = entity.dxf.height
            elif entity.dxftype() == "MTEXT":
                raw = entity.plain_text()
                insert = entity.dxf.insert
                height = entity.dxf.char_height
            else:
                continue
            match = _PLACEHOLDER.search(raw)
            if not match or match.group(1) not in FIELDS:
                continue
            block.add_attdef(match.group(1).upper(), insert=(insert.x, insert.y), height=height,
                             dxfattribs={"layer": entity.dxf.layer, "style": TEXT_STYLE})
            block.delete_entity(entity)

    # -- insertion -------------------------------------------------------------------------------
    def insert(self, layout: BaseLayout, geo: SheetGeometry, values: dict[str, str]) -> None:
        x0, y0, x1, y1 = geo.title_block
        name = self.ensure(x1 - x0, y1 - y0)
        ref = layout.add_blockref(name, (x0, y0), dxfattribs={"layer": "E-TITLE"})
        ref.add_auto_attribs({k.upper(): v for k, v in values.items() if k in FIELDS})
