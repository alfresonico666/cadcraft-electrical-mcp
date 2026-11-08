"""Reference designations (IEC 81346-1) and tag allocation.

A full designation is ``=FUNCTION +LOCATION -PRODUCT :TERMINAL`` (e.g. ``=A1+CAB1-QA2:13``). In the
project, devices are keyed by their *tag* (the product aspect as shown on drawings, e.g. ``-KF1`` in
IEC profiles or ``CR1`` in NFPA profiles). The function/location aspects are stored separately on
the device so drawings can show either the short tag or the full designation.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from ..errors import DesignationError

# '=' '+' ':' aspects stop at any sign; the product aspect may contain '-' (nested products: -A1-KF2).
_ASPECT_RE = re.compile(r"([=+:])([^=+:\-]+)|(-)([^=+:]+)")


@dataclass(frozen=True)
class Designation:
    product: str
    function: str | None = None
    location: str | None = None
    terminal: str | None = None

    @classmethod
    def parse(cls, text: str) -> Designation:
        """Parse ``=A1+CAB1-KF1:13`` (any subset, product aspect required)."""
        raw = text.strip().replace(" ", "")
        if not raw:
            raise DesignationError("Empty designation.")
        if raw[0] not in "=+-:":
            raw = "-" + raw
        parts: dict[str, str] = {}
        position = 0
        for match in _ASPECT_RE.finditer(raw):
            if match.start() != position:
                raise DesignationError(f"Invalid designation syntax: {text!r}")
            sign = match.group(1) or match.group(3)
            value = match.group(2) or match.group(4)
            if sign in parts:
                raise DesignationError(f"Aspect {sign!r} repeated in {text!r}")
            parts[sign] = value
            position = match.end()
        if position != len(raw) or "-" not in parts:
            raise DesignationError(
                f"Invalid designation {text!r}: a product aspect ('-XX1') is required."
            )
        return cls(
            product=parts["-"],
            function=parts.get("="),
            location=parts.get("+"),
            terminal=parts.get(":"),
        )

    def format(self, *, with_function: bool = True, with_location: bool = True) -> str:
        out = ""
        if with_function and self.function:
            out += f"={self.function}"
        if with_location and self.location:
            out += f"+{self.location}"
        out += f"-{self.product}"
        if self.terminal:
            out += f":{self.terminal}"
        return out


def split_terminal_ref(ref: str) -> tuple[str, str | None]:
    """``'-KF1:A1'`` -> ``('-KF1', 'A1')``; ``'-KF1'`` -> ``('-KF1', None)``."""
    if ":" in ref:
        tag, terminal = ref.rsplit(":", 1)
        return tag, terminal or None
    return ref, None


def tag_number(tag: str, prefix: str) -> int | None:
    """Number part of ``tag`` when it is ``prefix`` + digits, else ``None``."""
    if not tag.startswith(prefix):
        return None
    rest = tag[len(prefix):]
    return int(rest) if rest.isdigit() else None


def next_tag(prefix: str, existing: Iterable[str], start: int = 1) -> str:
    """Smallest free ``prefix<n>`` (n >= start) not present in ``existing``."""
    used = {n for tag in existing if (n := tag_number(tag, prefix)) is not None}
    number = start
    while number in used:
        number += 1
    return f"{prefix}{number}"


def natural_key(text: str) -> tuple[object, ...]:
    """Sort key so that -KF2 < -KF10 and I0.2 < I0.10."""
    return tuple(int(tok) if tok.isdigit() else tok for tok in re.split(r"(\d+)", text))


__all__ = ["Designation", "natural_key", "next_tag", "split_terminal_ref", "tag_number"]
