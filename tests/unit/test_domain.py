import pytest

from cadcraft_elec_mcp.domain.designation import Designation, natural_key, next_tag, split_terminal_ref
from cadcraft_elec_mcp.domain.model import PotentialKind
from cadcraft_elec_mcp.domain.numbering import NumberingStrategy, WireNumberer
from cadcraft_elec_mcp.domain.potentials import infer_potential_kind
from cadcraft_elec_mcp.errors import DesignationError


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("=A1+CAB1-KF1:13", Designation("KF1", "A1", "CAB1", "13")),
        ("-QA2", Designation("QA2")),
        ("KF3", Designation("KF3")),
        ("+CAB1-A1-KF2", Designation("A1-KF2", None, "CAB1")),
    ],
)
def test_parse_designation(text: str, expected: Designation) -> None:
    assert Designation.parse(text) == expected


def test_format_roundtrip() -> None:
    text = "=A1+CAB1-KF1:13"
    assert Designation.parse(text).format() == text
    assert Designation.parse(text).format(with_function=False, with_location=False) == "-KF1:13"


@pytest.mark.parametrize("bad", ["", "=A1", "=A1=B2-K1"])
def test_invalid_designations(bad: str) -> None:
    with pytest.raises(DesignationError):
        Designation.parse(bad)


def test_next_tag_fills_gaps() -> None:
    assert next_tag("-KF", ["-KF1", "-KF2", "-KF4", "-QA1"]) == "-KF3"
    assert next_tag("CR", []) == "CR1"


def test_split_and_sort() -> None:
    assert split_terminal_ref("-XD1:5") == ("-XD1", "5")
    assert split_terminal_ref("-XD1") == ("-XD1", None)
    assert sorted(["-KF10", "-KF2", "-KF1"], key=natural_key) == ["-KF1", "-KF2", "-KF10"]


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("L1", PotentialKind.AC_PHASE),
        ("L1_PLC", PotentialKind.AC_PHASE),
        ("N", PotentialKind.AC_NEUTRAL),
        ("PE", PotentialKind.PE),
        ("24V", PotentialKind.DC_PLUS),
        ("24V_HMI", PotentialKind.DC_PLUS),
        ("0V", PotentialKind.DC_MINUS),
        ("M", PotentialKind.DC_MINUS),
        ("L+", PotentialKind.DC_PLUS),
    ],
)
def test_infer_potential(name: str, kind: PotentialKind) -> None:
    assert infer_potential_kind(name) is kind


def test_wire_numbering_strategies() -> None:
    pot = WireNumberer(NumberingStrategy.POTENTIAL)
    assert pot.number(sheet=3, column=4, potential="24V") == "24V"
    assert pot.number(sheet=3, column=4) == "304-1"
    assert pot.number(sheet=3, column=4) == "304-2"
    sc = WireNumberer(NumberingStrategy.SHEET_COLUMN)
    assert sc.number(sheet=2, column=1, potential="24V") == "2.1.1"
    line = WireNumberer(NumberingStrategy.LINE_REFERENCE)
    assert [line.number(sheet=1, column=5) for _ in range(3)] == ["105", "105A", "105B"]
