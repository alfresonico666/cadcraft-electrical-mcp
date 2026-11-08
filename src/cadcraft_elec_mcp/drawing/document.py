"""DXF document factory and tiny drawing helpers shared by every generator."""

from __future__ import annotations

from typing import Any

import ezdxf
from ezdxf import units
from ezdxf.document import Drawing
from ezdxf.enums import TextEntityAlignment
from ezdxf.layouts import BaseLayout

from ..standards import StandardProfile

TEXT_STYLE = "ELEC"
DXF_VERSION = "R2018"


def new_document(profile: StandardProfile, font: str = "arial.ttf") -> Drawing:
    doc = ezdxf.new(DXF_VERSION, setup=["linetypes", "styles", "dimstyles"])
    doc.units = units.MM
    doc.header["$INSUNITS"] = units.MM
    doc.header["$MEASUREMENT"] = 1
    doc.header["$LUNITS"] = 2
    doc.header["$LWDISPLAY"] = 1
    doc.header["$LTSCALE"] = 1.0
    if TEXT_STYLE not in doc.styles:
        doc.styles.add(TEXT_STYLE, font=font)
    for layer in profile.all_layers():
        if layer.name in doc.layers:
            continue
        linetype = layer.linetype if layer.linetype in doc.linetypes else "Continuous"
        doc.layers.add(
            layer.name,
            color=layer.color,
            linetype=linetype,
            lineweight=round(layer.lineweight * 100),
        )
    return doc


def add_text(
    layout: BaseLayout,
    value: str,
    at: tuple[float, float],
    *,
    height: float,
    layer: str = "E-TEXT",
    align: str = "BOTTOM_LEFT",
    rotation: float = 0.0,
    **extra: Any,
) -> None:
    if not value:
        return
    attribs: dict[str, Any] = {"layer": layer, "style": TEXT_STYLE, "rotation": rotation, **extra}
    text = layout.add_text(value, height=height, dxfattribs=attribs)
    text.set_placement(at, align=TextEntityAlignment[align])


def add_rect(
    layout: BaseLayout, x0: float, y0: float, x1: float, y1: float, *, layer: str, **extra: Any
) -> None:
    layout.add_lwpolyline(
        [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True, dxfattribs={"layer": layer, **extra}
    )


def add_line(
    layout: BaseLayout, p1: tuple[float, float], p2: tuple[float, float], *, layer: str, **extra: Any
) -> None:
    layout.add_line(p1, p2, dxfattribs={"layer": layer, **extra})


def add_dot(layout: BaseLayout, at: tuple[float, float], *, layer: str, radius: float = 0.6) -> None:
    """Filled junction dot (connection point on a rail, IEC 60617 S00016)."""
    hatch = layout.add_hatch(dxfattribs={"layer": layer})
    hatch.paths.add_edge_path().add_arc(at, radius, 0, 360)
    layout.add_circle(at, radius, dxfattribs={"layer": layer})
