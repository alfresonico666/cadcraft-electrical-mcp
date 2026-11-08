import ezdxf
import pytest

from cadcraft_elec_mcp.domain.model import DeviceKind, PotentialKind, SheetKind
from cadcraft_elec_mcp.errors import StandardsError, SymbolError
from cadcraft_elec_mcp.standards import available_profiles, load_profile
from cadcraft_elec_mcp.symbols import (
    SymbolLibrary,
    TerminalAllocator,
    default_symbol,
    get_symbol,
    symbols_for_style,
)


def test_profiles_load_and_cover_every_kind() -> None:
    assert {"iec", "iec_legacy", "nfpa"} <= set(available_profiles())
    for name in available_profiles():
        profile = load_profile(name)
        for kind in DeviceKind:
            assert profile.code_for(kind)
        for kind in PotentialKind:
            assert profile.wire_color(kind).aci > 0
        assert profile.text.general >= profile.text.minimum


def test_profile_specifics() -> None:
    assert load_profile("iec").tag_prefix(DeviceKind.CONTACTOR) == "-QA"
    assert load_profile("iec_legacy").tag_prefix(DeviceKind.CONTACTOR) == "-K"
    nfpa = load_profile("nfpa")
    assert nfpa.tag_prefix(DeviceKind.RELAY) == "CR"
    assert nfpa.orientation == "horizontal"
    assert nfpa.wire_color(PotentialKind.PE).code == "GRN"


def test_unknown_profile() -> None:
    with pytest.raises(StandardsError):
        load_profile("does-not-exist")


@pytest.mark.parametrize("style", ["iec", "nfpa"])
def test_every_symbol_builds_a_block(style: str) -> None:
    doc = ezdxf.new("R2018")
    doc.styles.add("ELEC", font="arial.ttf")
    library = SymbolLibrary(doc, load_profile("nfpa" if style == "nfpa" else "iec"))
    for symbol_id, symbol in symbols_for_style(style).items():
        ref = library.ensure(symbol_id, 3 if symbol.spans_poles else 1)
        block = doc.blocks.get(ref.name)
        assert len(block) > 0
        assert any(e.dxftype() == "ATTDEF" and e.dxf.tag == "TAG" for e in block)
    assert library.ensure("contact_no", secondary=True).name.endswith("_S")


def test_symbol_defaults_and_errors() -> None:
    assert default_symbol(DeviceKind.CONTACTOR, SheetKind.POWER) == "power_contact"
    assert default_symbol(DeviceKind.CONTACTOR, SheetKind.CONTROL) == "coil"
    with pytest.raises(SymbolError):
        get_symbol("iec", "nope")


def test_terminal_allocation_iec60947() -> None:
    alloc = TerminalAllocator()
    assert alloc.allocate("-QA1", DeviceKind.CONTACTOR, "coil", 1) == [["A1", "A2"]]
    assert alloc.allocate("-QA1", DeviceKind.CONTACTOR, "power_contact", 3) == [
        ["1", "2"],
        ["3", "4"],
        ["5", "6"],
    ]
    assert alloc.allocate("-KF1", DeviceKind.RELAY, "contact_no", 1) == [["13", "14"]]
    assert alloc.allocate("-KF1", DeviceKind.RELAY, "contact_nc", 1) == [["21", "22"]]
    assert alloc.allocate("-FC2", DeviceKind.OVERLOAD, "contact_nc", 1) == [["95", "96"]]
    alloc.reserve("-KF2", [["33", "34"]])
    assert alloc.allocate("-KF2", DeviceKind.RELAY, "contact_no", 1) == [["43", "44"]]
