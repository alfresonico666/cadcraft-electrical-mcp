"""Sheet frame (ISO 5457): trimmed-paper outline, border, zone grid, path columns.

All sheets of a project live side by side in model space (one row). The outer closed polyline is
exactly the paper size, which is what CADCraft ``pdfbook`` uses to split pages.
"""

from __future__ import annotations

import string
from dataclasses import dataclass

from ezdxf.layouts import BaseLayout

from ..standards import StandardProfile
from .document import add_line, add_rect, add_text

SHEET_GAP = 40.0
ROW_LETTERS = [c for c in string.ascii_uppercase if c not in "IO"]


@dataclass(frozen=True)
class SheetGeometry:
    index: int                  # 0-based position in the drawing
    number: int                 # printed sheet number (1-based)
    x: float                    # lower-left corner of the paper
    y: float
    width: float
    height: float
    inner: tuple[float, float, float, float]      # border rectangle
    area: tuple[float, float, float, float]       # drawable area (inside zones, above title block)
    title_block: tuple[float, float, float, float]
    columns: int
    rows: int

    @property
    def window(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    @property
    def column_width(self) -> float:
        x0, _, x1, _ = self.area
        return (x1 - x0) / self.columns

    def column_center(self, column: int) -> float:
        """Center x of path column ``column`` (1-based)."""
        return self.area[0] + (column - 0.5) * self.column_width

    def column_at(self, x: float) -> int:
        col = int((x - self.area[0]) // self.column_width) + 1
        return min(max(col, 1), self.columns)

    def row_at(self, y: float) -> str:
        _, y0, _, y1 = self.inner
        height = (y1 - y0) / self.rows
        row = int((y1 - y) // height)
        return ROW_LETTERS[min(max(row, 0), self.rows - 1)]

    def ref(self, x: float, y: float) -> str:
        """Cross reference ``/sheet.column`` (IEC 61082-1 path referencing)."""
        return f"/{self.number}.{self.column_at(x)}"


def sheet_geometry(profile: StandardProfile, index: int, number: int) -> SheetGeometry:
    fmt = profile.sheet
    x = index * (fmt.width + SHEET_GAP)
    y = 0.0
    inner = (x + fmt.margin_left, y + fmt.margin_bottom, x + fmt.width - fmt.margin_right,
             y + fmt.height - fmt.margin_top)
    band = fmt.zone_band
    tb = (inner[0] + band, inner[1] + band, inner[2] - band, inner[1] + band + fmt.title_block_height)
    area = (inner[0] + band, tb[3], inner[2] - band, inner[3] - band)
    return SheetGeometry(index, number, x, y, fmt.width, fmt.height, inner, area, tb, fmt.columns, fmt.rows)


def draw_frame(layout: BaseLayout, geo: SheetGeometry, profile: StandardProfile) -> None:
    text_h = profile.text.general
    band = profile.sheet.zone_band
    # trimmed paper outline (pdfbook page frame) + border
    add_rect(layout, geo.x, geo.y, geo.x + geo.width, geo.y + geo.height, layer="E-GRID")
    x0, y0, x1, y1 = geo.inner
    add_rect(layout, x0, y0, x1, y1, layer="E-FRAME")
    add_rect(layout, x0 + band, y0 + band, x1 - band, y1 - band, layer="E-GRID")

    # path columns (numbers in the top and bottom bands)
    ax0, _, ax1, _ = geo.area
    col_w = (ax1 - ax0) / geo.columns
    for c in range(geo.columns + 1):
        x = ax0 + c * col_w
        add_line(layout, (x, y1 - band), (x, y1), layer="E-GRID")
        add_line(layout, (x, y0), (x, y0 + band), layer="E-GRID")
    for c in range(geo.columns):
        cx = ax0 + (c + 0.5) * col_w
        add_text(layout, str(c + 1), (cx, y1 - band / 2), height=text_h, layer="E-GRID", align="MIDDLE_CENTER")
        add_text(layout, str(c + 1), (cx, y0 + band / 2), height=text_h, layer="E-GRID", align="MIDDLE_CENTER")

    # zone rows (letters in the left and right bands)
    row_h = (y1 - y0) / geo.rows
    for r in range(geo.rows + 1):
        y = y1 - r * row_h
        add_line(layout, (x0, y), (x0 + band, y), layer="E-GRID")
        add_line(layout, (x1 - band, y), (x1, y), layer="E-GRID")
    for r in range(geo.rows):
        cy = y1 - (r + 0.5) * row_h
        letter = ROW_LETTERS[r % len(ROW_LETTERS)]
        add_text(layout, letter, (x0 + band / 2, cy), height=text_h, layer="E-GRID", align="MIDDLE_CENTER")
        add_text(layout, letter, (x1 - band / 2, cy), height=text_h, layer="E-GRID", align="MIDDLE_CENTER")
