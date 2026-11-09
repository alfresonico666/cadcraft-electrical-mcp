from cadcraft_elec_mcp.domain.model import CabinetSpec, Placement
from cadcraft_elec_mcp.layout import DeviceBox, plan_backplate


def boxes(n: int, width: float = 45, height: float = 85) -> list[DeviceBox]:
    return [DeviceBox(f"-QA{i + 1}", width, height) for i in range(n)]


def test_devices_fill_rows_without_overlaps() -> None:
    spec = CabinetSpec(plate_width=400, plate_height=600)
    plan = plan_backplate(spec, boxes(12))
    assert not plan.unplaced
    rects = [d.rect for d in plan.devices]
    for i, a in enumerate(rects):
        assert a.inside(plan.plate)
        for b in rects[i + 1 :]:
            assert not a.overlaps(b)
        for duct in plan.ducts:
            assert not a.overlaps(duct)
    # 270 mm rails (400 - 2x15 margin - 2x(40+10) ducts); 20 % spare -> 216 mm -> 4 devices per rail
    assert len(plan.rails) == 3


def test_overflow_is_reported() -> None:
    spec = CabinetSpec(plate_width=300, plate_height=250)
    plan = plan_backplate(spec, boxes(20))
    assert plan.unplaced
    assert any("do not fit" in w for w in plan.warnings)


def test_spare_warning_and_explicit_rails() -> None:
    spec = CabinetSpec(plate_width=400, plate_height=400, spare_ratio=0.5)
    plan = plan_backplate(spec, boxes(5), rails=[["-QA1", "-QA2", "-QA3", "-QA4"], ["-QA5"]])
    assert [len([d for d in plan.devices if d.rail == i]) for i in range(2)] == [4, 1]
    # rail 1: 4 x 45 = 180 of 270 mm -> 33 % spare < 50 % target; rail 2 has 83 % spare
    assert [w for w in plan.warnings if "spare" in w] == ["Rail 1: only 33% spare (target 50%)."]


def test_manual_placement() -> None:
    spec = CabinetSpec(plate_width=400, plate_height=400, placements={"-QA1": Placement(x=10, y=10)})
    plan = plan_backplate(spec, boxes(2))
    manual = next(d for d in plan.devices if d.box.tag == "-QA1")
    assert (manual.rect.x, manual.rect.y, manual.rail) == (10, 10, None)


def test_auto_fill_keeps_spare_when_possible() -> None:
    spec = CabinetSpec(plate_width=400, plate_height=700, spare_ratio=0.2)
    plan = plan_backplate(spec, boxes(10))
    assert not plan.unplaced
    assert all(rail.spare_ratio >= 0.2 - 1e-6 for rail in plan.rails)
    assert not [w for w in plan.warnings if "spare" in w]
