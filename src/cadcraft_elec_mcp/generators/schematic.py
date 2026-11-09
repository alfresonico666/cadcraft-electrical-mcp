"""Power and control schematic sheets (IEC 61082-1 current paths / NFPA 79 ladder)."""

from __future__ import annotations

from ..domain.model import CircuitPath, SheetKind, SheetSpec
from .context import BuildContext
from .ladder import LadderPath, LadderSheet, paginate, slots_needed


def to_ladder(path: CircuitPath) -> LadderPath:
    return LadderPath(
        label=path.label,
        supply=list(path.supply),
        elements=list(path.elements),
        return_rail=path.return_rail,
        pe=path.pe,
        slot=(path.column - 1) if path.column else None,
        feeds=list(path.feeds) if path.feeds else None,
    )


def generate_schematic(ctx: BuildContext, spec: SheetSpec) -> list[int]:
    """Draw a power/control sheet (auto-paginated). Returns the page numbers created."""
    paths = [to_ladder(p) for p in spec.paths]
    capacity, pitch = _capacity(ctx)
    created: list[int] = []
    pages = paginate(paths, capacity, lambda p: slots_needed(p, ctx.vertical, pitch)) or [[]]
    for i, page in enumerate(pages, start=1):
        title = spec.title if len(pages) == 1 else f"{spec.title} ({i}/{len(pages)})"
        geo = ctx.new_page(title, spec.kind.value)
        supply = [rail for _, p in page for rail in p.supply]
        returns = [p.return_rail for _, p in page if p.return_rail]
        sheet = LadderSheet(ctx, geo, spec.kind, supply, returns)
        sheet.draw_rails()
        for slot, path in page:
            sheet.draw_path(slot, path)
        if spec.note:
            _note(ctx, geo, spec.note)
        created.append(geo.number)
    return created


def _capacity(ctx: BuildContext) -> tuple[int, float]:
    """(slots per page, slot pitch) – same numbers LadderSheet computes from the sheet geometry."""
    fmt = ctx.profile.sheet
    if ctx.vertical:
        return fmt.columns, 0.0
    area_h = fmt.height - fmt.margin_top - fmt.margin_bottom - 2 * fmt.zone_band - fmt.title_block_height
    return fmt.columns * fmt.rungs, area_h / fmt.rungs


def _note(ctx: BuildContext, geo, note: str) -> None:  # type: ignore[no-untyped-def]
    from ..drawing import add_text

    x0, _, _, _ = geo.area
    _, _, _, ty1 = geo.title_block
    add_text(ctx.msp, note, (x0 + 1.0, ty1 + 1.5), height=ctx.profile.text.general, layer="E-TEXT")


SCHEMATIC_KINDS = {SheetKind.POWER, SheetKind.CONTROL}
