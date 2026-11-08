"""Cabinet drawings from a :class:`CabinetPlan`.

``build_cabinet_block`` draws (geometry at 1:1, mm) the back plate – wire ducts, DIN rails, fixing
holes, devices (real vendor model when available, otherwise a labelled rectangle), dimensions – and
the door view with its devices, into one block. ``text_scale`` multiplies every text/dimension
height, so a block inserted at 1:n with ``text_scale=n`` still prints texts at their nominal size.

* fabrication DXF: block inserted 1:1, ``text_scale=1``;
* drawing set: block inserted at the largest standard reduction that fits the sheet.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import ezdxf
from ezdxf import bbox
from ezdxf.addons.importer import Importer
from ezdxf.document import Drawing
from ezdxf.enums import TextEntityAlignment
from ezdxf.layouts import BlockLayout

from ..domain.model import CabinetSpec, SheetSpec
from ..drawing import add_text
from ..drawing.document import TEXT_STYLE
from ..layout import CabinetPlan, DeviceBox, Rect
from ..logging_setup import get_logger
from ..standards import StandardProfile
from .context import BuildContext

log = get_logger("generators.cabinet")

STANDARD_SCALES = [1, 2, 2.5, 4, 5, 10, 20]
DOOR_GAP = 80.0
DOOR_MARGIN = 30.0
DOOR_SPACING = 25.0
HOLE_D = 5.5
HOLE_PITCH = 150.0
Align = TextEntityAlignment


@dataclass
class CabinetDrawing:
    block: str
    width: float
    height: float


class ModelBlocks:
    """Imports vendor model DXFs as blocks (once per file and document)."""

    def __init__(self, doc: Drawing) -> None:
        self.doc = doc
        self._cache: dict[str, str | None] = {}

    def get(self, path: str | None) -> str | None:
        if not path:
            return None
        if path in self._cache:
            return self._cache[path]
        stem = "".join(ch if ch.isalnum() else "_" for ch in Path(path).stem).upper()[:60]
        block_name = f"MODEL_{stem}"
        name: str | None = block_name
        try:
            if block_name not in self.doc.blocks:
                source = ezdxf.readfile(path)
                block = self.doc.blocks.new(block_name)
                importer = Importer(source, self.doc)
                importer.import_entities(source.modelspace(), block)
                importer.finalize()
        except (OSError, ezdxf.DXFError) as exc:
            log.warning("Model %s not usable (%s); drawing a rectangle instead.", path, exc)
            name = None
        self._cache[path] = name
        return name


class _Painter:
    """Block drawing helper with a text scale factor."""

    def __init__(self, block: BlockLayout, text_scale: float) -> None:
        self.block = block
        self.k = text_scale

    def rect(self, r: Rect, layer: str) -> None:
        self.block.add_lwpolyline(
            [(r.x, r.y), (r.x2, r.y), (r.x2, r.y2), (r.x, r.y2)], close=True, dxfattribs={"layer": layer}
        )

    def line(self, p1: tuple[float, float], p2: tuple[float, float], layer: str) -> None:
        self.block.add_line(p1, p2, dxfattribs={"layer": layer})

    def text(
        self,
        value: str,
        at: tuple[float, float],
        height: float,
        *,
        layer: str = "L-TEXT",
        align: TextEntityAlignment = Align.MIDDLE_CENTER,
        rotation: float = 0.0,
    ) -> None:
        if not value:
            return
        text = self.block.add_text(
            value,
            height=height * self.k,
            dxfattribs={"layer": layer, "style": TEXT_STYLE, "rotation": rotation},
        )
        text.set_placement(at, align=align)

    def holes_along(self, x0: float, x1: float, y: float, inset: float = 20.0) -> None:
        length = x1 - x0
        if length <= 2 * inset:
            xs = [(x0 + x1) / 2]
        else:
            count = max(int((length - 2 * inset) // HOLE_PITCH) + 1, 2)
            step = (length - 2 * inset) / (count - 1)
            xs = [x0 + inset + i * step for i in range(count)]
        for x in xs:
            self.block.add_circle((x, y), HOLE_D / 2, dxfattribs={"layer": "L-HOLES"})


def build_cabinet_block(
    doc: Drawing,
    spec: CabinetSpec,
    plan: CabinetPlan,
    door_boxes: list[DeviceBox],
    labels: dict[str, str],
    *,
    name: str = "CABINET_LAYOUT",
    text_scale: float = 1.0,
) -> CabinetDrawing:
    block = doc.blocks.get(name) if name in doc.blocks else doc.blocks.new(name)
    pen = _Painter(block, text_scale)
    models = ModelBlocks(doc)
    plate = plan.plate

    # enclosure outline (front, door removed) centred around the plate
    enclosure = Rect(
        (plate.w - spec.enclosure_width) / 2,
        (plate.h - spec.enclosure_height) / 2,
        spec.enclosure_width,
        spec.enclosure_height,
    )
    pen.rect(enclosure, "L-ENCLOSURE")
    pen.rect(plate, "L-PLATE")
    pen.text(
        f"Placa de montaje / Mounting plate {plate.w:g} x {plate.h:g}",
        (plate.w / 2, enclosure.y - 8 * text_scale),
        3.5,
    )
    _ducts(pen, spec, plan)
    _rails(pen, plan)
    for placed in plan.devices:
        _device(pen, models, placed.box, placed.rect, labels.get(placed.box.tag, placed.box.tag))
    _plate_dimensions(block, plan, text_scale)

    door = Rect(enclosure.x2 + DOOR_GAP, enclosure.y, enclosure.w, enclosure.h)
    pen.rect(door, "L-ENCLOSURE")
    pen.text(
        "Puerta (vista exterior) / Door (outside view)", (door.x + door.w / 2, door.y - 8 * text_scale), 3.5
    )
    _door_devices(pen, models, door, door_boxes, labels)
    return CabinetDrawing(name, door.x2 - enclosure.x, enclosure.h)


def _ducts(pen: _Painter, spec: CabinetSpec, plan: CabinetPlan) -> None:
    inner = 4.0
    for duct in plan.ducts:
        pen.rect(duct, "L-DUCT")
        if duct.w >= duct.h:
            pen.line((duct.x, duct.y + inner), (duct.x2, duct.y + inner), "L-DUCT")
            pen.line((duct.x, duct.y2 - inner), (duct.x2, duct.y2 - inner), "L-DUCT")
            pen.text(
                f"Canaleta {spec.duct_width:g}x{spec.duct_depth:g}",
                (duct.x2 - 6.0, duct.y + duct.h / 2),
                2.0,
                layer="L-DUCT",
                align=Align.MIDDLE_RIGHT,
            )
            pen.holes_along(duct.x, duct.x2, duct.y + duct.h / 2)
        else:
            pen.line((duct.x + inner, duct.y), (duct.x + inner, duct.y2), "L-DUCT")
            pen.line((duct.x2 - inner, duct.y), (duct.x2 - inner, duct.y2), "L-DUCT")


def _rails(pen: _Painter, plan: CabinetPlan) -> None:
    horizontal_ducts = [d for d in plan.ducts if d.w >= d.h]
    for rail in plan.rails:
        x1 = rail.x_start + rail.length
        pen.rect(Rect(rail.x_start, rail.y_center - 17.5, rail.length, 35.0), "L-RAIL")
        pen.line((rail.x_start, rail.y_center - 12.5), (x1, rail.y_center - 12.5), "L-RAIL")
        pen.line((rail.x_start, rail.y_center + 12.5), (x1, rail.y_center + 12.5), "L-RAIL")
        pen.holes_along(rail.x_start, x1, rail.y_center, inset=15.0)
        # label inside the wire duct below the rail row, so it never hides a device
        below = horizontal_ducts[rail.index + 1] if rail.index + 1 < len(horizontal_ducts) else None
        at = (below.x + 6.0, below.y + below.h / 2) if below else (rail.x_start, rail.y_center - 19.0)
        pen.text(
            f"Riel TS35-{rail.index + 1}  L={rail.length:.0f}  ({100 * rail.spare_ratio:.0f}% libre)",
            at,
            2.0,
            align=Align.MIDDLE_LEFT if below else Align.TOP_LEFT,
        )


def _device(pen: _Painter, models: ModelBlocks, box: DeviceBox, rect: Rect, label: str) -> None:
    model = models.get(box.model_dxf)
    if model:
        pen.block.add_blockref(model, (rect.x, rect.y), dxfattribs={"layer": "L-DEVICE"})
    else:
        pen.rect(rect, "L-DEVICE")
        vertical = rect.w < rect.h * 0.6
        span = rect.h if vertical else rect.w
        height = min(2.0, span / max(len(box.label), 1) * 1.4 / pen.k)
        pen.text(
            box.label, (rect.x + rect.w / 2, rect.y + rect.h / 2), height, rotation=90 if vertical else 0
        )
    # designation above the device; rotated when the device is narrower than the text
    narrow = rect.w < 3.0 * pen.k * len(label) * 0.6
    pen.text(
        label,
        (rect.x + rect.w / 2, rect.y2 + 1.0 * pen.k),
        3.0,
        layer="E-DESIG",
        align=Align.MIDDLE_LEFT if narrow else Align.BOTTOM_CENTER,
        rotation=90 if narrow else 0,
    )


def _door_devices(
    pen: _Painter, models: ModelBlocks, door: Rect, boxes: list[DeviceBox], labels: dict[str, str]
) -> None:
    """Shelf packing from the top-left of the door: biggest devices first, rows side by side."""
    x_min, x_max = door.x + DOOR_MARGIN, door.x2 - DOOR_MARGIN
    x, y_top, row_h = x_min, door.y2 - DOOR_MARGIN - 8.0 * pen.k, 0.0
    for box in sorted(boxes, key=lambda b: -b.width * b.height):
        if x + box.width > x_max and x > x_min:
            x, y_top, row_h = x_min, y_top - row_h - DOOR_SPACING - 6.0 * pen.k, 0.0
        rect = Rect(x, y_top - box.height, box.width, box.height)
        if rect.y < door.y + DOOR_MARGIN:
            log.warning("Door is full; %s overflows the door view.", box.tag)
        _device(pen, models, box, rect, labels.get(box.tag, box.tag))
        x += box.width + DOOR_SPACING
        row_h = max(row_h, box.height)


def _plate_dimensions(block: BlockLayout, plan: CabinetPlan, text_scale: float) -> None:
    plate = plan.plate
    override = {
        "dimtxt": 2.5 * text_scale,
        "dimasz": 2.0 * text_scale,
        "dimexo": 1.0,
        "dimexe": 1.5 * text_scale,
        "dimgap": 0.8 * text_scale,
        "dimdec": 0,
        "dimtad": 1,
        "dimlfac": 1.0,
        "dimscale": 1.0,
        "dimtxsty": TEXT_STYLE,
    }
    gap = 12.0 * text_scale
    attribs = {"layer": "L-DIM"}
    try:
        block.add_linear_dim(
            base=(0, plate.y - gap),
            p1=(plate.x, plate.y),
            p2=(plate.x2, plate.y),
            dimstyle="EZDXF",
            override=override,
            dxfattribs=attribs,
        ).render()
        block.add_linear_dim(
            base=(plate.x - gap, 0),
            p1=(plate.x, plate.y),
            p2=(plate.x, plate.y2),
            angle=90,
            dimstyle="EZDXF",
            override=override,
            dxfattribs=attribs,
        ).render()
        for rail in plan.rails:  # rail axes measured from the plate bottom (drilling)
            block.add_linear_dim(
                base=(plate.x2 + gap * (1 + 0.6 * rail.index), 0),
                p1=(plate.x2, plate.y),
                p2=(plate.x2, rail.y_center),
                angle=90,
                dimstyle="EZDXF",
                override=override,
                dxfattribs=attribs,
            ).render()
    except ezdxf.DXFError as exc:  # pragma: no cover - dimstyle missing
        log.warning("Dimensions skipped: %s", exc)


def fit_scale(content_w: float, content_h: float, area_w: float, area_h: float) -> float:
    """Smallest standard reduction (1:n) that fits the area."""
    for n in STANDARD_SCALES:
        if content_w / n <= area_w and content_h / n <= area_h:
            return float(n)
    return float(STANDARD_SCALES[-1])


def sheet_scale(profile: StandardProfile, spec: CabinetSpec) -> float:
    """Reduction for the drawing-set sheet, estimated from the enclosure size (before drawing)."""
    fmt = profile.sheet
    area_w = fmt.width - fmt.margin_left - fmt.margin_right - 2 * fmt.zone_band - 16.0
    area_h = (
        fmt.height - fmt.margin_top - fmt.margin_bottom - 2 * fmt.zone_band - fmt.title_block_height - 16.0
    )
    width = 2 * spec.enclosure_width + DOOR_GAP + 60.0
    height = spec.enclosure_height + 40.0
    return fit_scale(width, height, area_w, area_h)


def generate_cabinet_sheet(
    ctx: BuildContext, spec: SheetSpec, drawing: CabinetDrawing, n: float
) -> list[int]:
    """Insert the cabinet block at 1:n, centred in a sheet of the set."""
    geo = ctx.new_page(spec.title, spec.kind.value)
    x0, y0, x1, y1 = geo.area
    extents = bbox.extents(ctx.doc.blocks.get(drawing.block), fast=True)
    scale = 1.0 / n
    insert_x = (x0 + x1) / 2 - (extents.extmin.x + extents.size.x / 2) * scale
    insert_y = (y0 + y1) / 2 - (extents.extmin.y + extents.size.y / 2) * scale
    ctx.msp.add_blockref(
        drawing.block,
        (insert_x, insert_y),
        dxfattribs={"xscale": scale, "yscale": scale, "layer": "L-DEVICE"},
    )
    add_text(
        ctx.msp,
        f"Escala / Scale 1:{n:g}",
        (x1 - 2.0, y0 + 2.0),
        height=ctx.profile.text.designation,
        layer="E-TEXT",
        align="BOTTOM_RIGHT",
    )
    return [geo.number]
