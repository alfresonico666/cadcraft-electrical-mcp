"""Back-plate layout planner (pure geometry, no DXF).

Plate coordinates: origin at the lower-left corner of the mounting plate, mm.
Arrangement from top to bottom::

    margin | duct | clearance | rail row 1 | clearance | duct | clearance | rail row 2 | ... | duct | margin

with optional vertical ducts at the left and right edges. DIN-rail devices are placed left to right
(centred on the rail) in the given order; a new row starts when the row is full. Devices with a
manual placement keep it. The result also reports fill ratio and spare length per rail.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.model import CabinetSpec

DIN_RAIL_HEIGHT = 35.0


@dataclass(frozen=True)
class DeviceBox:
    tag: str
    width: float
    height: float
    model_dxf: str | None = None
    label: str = ""


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.h

    def overlaps(self, other: Rect, tol: float = 0.01) -> bool:
        return not (
            self.x2 <= other.x + tol
            or other.x2 <= self.x + tol
            or self.y2 <= other.y + tol
            or other.y2 <= self.y + tol
        )

    def inside(self, other: Rect, tol: float = 0.01) -> bool:
        return (
            self.x >= other.x - tol
            and self.y >= other.y - tol
            and self.x2 <= other.x2 + tol
            and self.y2 <= other.y2 + tol
        )


@dataclass
class PlacedDevice:
    box: DeviceBox
    rect: Rect
    rail: int | None


@dataclass
class RailRow:
    index: int
    y_center: float
    x_start: float
    length: float
    used: float = 0.0

    @property
    def spare_ratio(self) -> float:
        return 1.0 - self.used / self.length if self.length else 0.0


@dataclass
class CabinetPlan:
    plate: Rect
    usable: Rect
    ducts: list[Rect] = field(default_factory=list)
    rails: list[RailRow] = field(default_factory=list)
    devices: list[PlacedDevice] = field(default_factory=list)
    unplaced: list[DeviceBox] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def fill_ratio(self) -> float:
        total = sum(r.length for r in self.rails)
        return sum(r.used for r in self.rails) / total if total else 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "plate_mm": [self.plate.w, self.plate.h],
            "rails": [
                {
                    "index": r.index + 1,
                    "y_center": round(r.y_center, 1),
                    "length": round(r.length, 1),
                    "used": round(r.used, 1),
                    "spare_pct": round(100 * r.spare_ratio, 1),
                }
                for r in self.rails
            ],
            "devices": [
                {
                    "tag": d.box.tag,
                    "x": round(d.rect.x, 1),
                    "y": round(d.rect.y, 1),
                    "w": d.rect.w,
                    "h": d.rect.h,
                    "rail": None if d.rail is None else d.rail + 1,
                }
                for d in self.devices
            ],
            "unplaced": [b.tag for b in self.unplaced],
            "fill_pct": round(100 * self.fill_ratio, 1),
            "warnings": self.warnings,
        }


def plan_backplate(
    spec: CabinetSpec,
    boxes: list[DeviceBox],
    rails: list[list[str]] | None = None,
) -> CabinetPlan:
    """Place ``boxes`` on the plate. ``rails`` optionally fixes which tags go on which rail."""
    plate = Rect(0, 0, spec.plate_width, spec.plate_height)
    m, dw, c = spec.plate_margin, spec.duct_width, spec.duct_clearance
    x_left = m + (dw + c if spec.vertical_ducts else 0)
    x_right = spec.plate_width - m - (dw + c if spec.vertical_ducts else 0)
    usable = Rect(x_left, m, x_right - x_left, spec.plate_height - 2 * m)
    plan = CabinetPlan(plate=plate, usable=usable)
    if x_right <= x_left:
        plan.warnings.append("Plate too narrow for the vertical wire ducts.")
        plan.unplaced = list(boxes)
        return plan

    manual = {tag for tag in spec.placements}
    by_tag = {b.tag: b for b in boxes}
    flow = [b for b in boxes if b.tag not in manual]

    # rows: explicit rail assignment or greedy fill
    rows: list[list[DeviceBox]] = []
    if rails:
        assigned: set[str] = set()
        for rail_tags in rails:
            rows.append([by_tag[t] for t in rail_tags if t in by_tag and t not in manual])
            assigned.update(rail_tags)
        leftovers = [b for b in flow if b.tag not in assigned]
        if leftovers:
            plan.warnings.append(
                "Devices not assigned to a rail were appended automatically: "
                + ", ".join(b.tag for b in leftovers)
            )
            rows.extend(_greedy_rows(leftovers, usable.w, spec.device_gap))
    else:
        rows = _greedy_rows(flow, usable.w, spec.device_gap)

    # vertical stacking from the top
    y_top = spec.plate_height - m
    plan.ducts.append(Rect(m, y_top - dw, spec.plate_width - 2 * m, dw))
    cursor = y_top - dw
    for index, row in enumerate(rows):
        row_h = max([b.height for b in row] + [DIN_RAIL_HEIGHT])
        needed = c + row_h + c + dw
        if cursor - needed < m - 0.01:
            for remaining in rows[index:]:
                plan.unplaced.extend(remaining)
            plan.warnings.append(
                f"{len(rows) - index} rail row(s) do not fit on the plate; use a bigger plate, fewer "
                "devices or a second plate."
            )
            break
        y_center = cursor - c - row_h / 2
        rail = RailRow(index, y_center, usable.x, usable.w)
        x = usable.x
        for box in row:
            if x + box.width > usable.x2 + 0.01:
                plan.unplaced.append(box)
                plan.warnings.append(f"{box.tag} does not fit on rail {index + 1}.")
                continue
            plan.devices.append(
                PlacedDevice(box, Rect(x, y_center - box.height / 2, box.width, box.height), index)
            )
            x += box.width + spec.device_gap
            rail.used += box.width + spec.device_gap
        rail.used = min(rail.used, rail.length)
        plan.rails.append(rail)
        cursor -= c + row_h + c
        plan.ducts.append(Rect(m, cursor - dw, spec.plate_width - 2 * m, dw))
        cursor -= dw

    if spec.vertical_ducts and plan.ducts:
        bottom = plan.ducts[-1].y
        top = plan.ducts[0].y2
        plan.ducts.append(Rect(m, bottom, dw, top - bottom))
        plan.ducts.append(Rect(spec.plate_width - m - dw, bottom, dw, top - bottom))

    for tag, placement in spec.placements.items():
        manual_box = by_tag.get(tag)
        if manual_box is None:
            plan.warnings.append(f"Manual placement for unknown/non-cabinet device {tag}.")
            continue
        rect = Rect(placement.x, placement.y, manual_box.width, manual_box.height)
        plan.devices.append(PlacedDevice(manual_box, rect, None))

    for rail in plan.rails:
        if rail.spare_ratio < spec.spare_ratio:
            plan.warnings.append(
                f"Rail {rail.index + 1}: only {100 * rail.spare_ratio:.0f}% spare "
                f"(target {100 * spec.spare_ratio:.0f}%)."
            )
    return plan


def _greedy_rows(boxes: list[DeviceBox], width: float, gap: float) -> list[list[DeviceBox]]:
    rows: list[list[DeviceBox]] = [[]]
    used = 0.0
    for box in boxes:
        if rows[-1] and used + box.width > width + 0.01:
            rows.append([])
            used = 0.0
        rows[-1].append(box)
        used += box.width + gap
    return [row for row in rows if row]
