"""Wire numbering strategies.

* ``potential``      – rail-connected conductors carry the potential name (24V, 0V, L1 ...);
                        every other conductor gets ``<sheet><column>-<index>`` (e.g. 304-1).
* ``sheet_column``   – every conductor is ``<sheet>.<column>.<index>`` (EPLAN-like, IEC 61082).
* ``line_reference`` – NFPA 79 style: the wire number is the ladder line number plus a suffix.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class NumberingStrategy(StrEnum):
    POTENTIAL = "potential"
    SHEET_COLUMN = "sheet_column"
    LINE_REFERENCE = "line_reference"


@dataclass
class WireNumberer:
    strategy: NumberingStrategy
    _counters: dict[tuple[int, int], int] = field(default_factory=dict)

    def number(self, *, sheet: int, column: int, potential: str | None = None) -> str:
        """Next number for a conductor drawn on ``sheet``/``column`` (1-based)."""
        if potential and self.strategy is NumberingStrategy.POTENTIAL:
            return potential
        key = (sheet, column)
        index = self._counters.get(key, 0) + 1
        self._counters[key] = index
        if self.strategy is NumberingStrategy.SHEET_COLUMN:
            return f"{sheet}.{column}.{index}"
        if self.strategy is NumberingStrategy.LINE_REFERENCE:
            line = sheet * 100 + column
            return f"{line}" if index == 1 else f"{line}{chr(ord('A') + index - 2)}"
        return f"{sheet}{column:02d}-{index}"
