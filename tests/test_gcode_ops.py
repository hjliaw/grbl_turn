"""Generator checks per operation, inch and mm."""

import pytest

from grbl_turn.gcode import extents
from grbl_turn.machine import MachineProfile
from grbl_turn.ops import BY_KEY, REGISTRY
from grbl_turn.units import Units

MACHINE = MachineProfile()


def defaults(op) -> dict:
    p = {f.name: f.default for f in op.fields}
    for f in op.fields:   # zero defaults are literal now: "tap A" like a user
        if f.auto is not None and not p[f.name]:
            p[f.name] = f.auto(p, Units.INCH)
    return p


def body(lines):
    return [l for l in lines if not l.startswith("(")]


@pytest.mark.parametrize("units", [Units.INCH, Units.MM])
@pytest.mark.parametrize("op", REGISTRY, ids=lambda op: op.key)
def test_all_ops_generate_with_defaults(op, units):
    lines = op.generate(defaults(op), MACHINE, units)
    b = body(lines)
    assert b[0] == f"{units.gcode} G18 G90 G94"
    assert b[-1] == "M2"
    # no motion before the units/plane line, spindle never started by default
    assert not any(l.startswith("M3") for l in b)


def test_turning_passes_and_extents():
    op = BY_KEY["ext_turning"]
    p = defaults(op) | {"start_dia": 0.5, "end_dia": 0.4, "doc": 0.02,
                        "finish_allow": 0.005, "length": 0.75}
    lines = op.generate(p, MACHINE, Units.INCH)
    ext = extents(lines)
    # radius mode: deepest X word is the final radius
    assert ext["X"][0] == pytest.approx(0.2)
    assert ext["Z"][0] == pytest.approx(-0.75)
    assert "G1 Z-0.7500 F3" in "\n".join(lines)


def test_turning_diameter_mode():
    op = BY_KEY["ext_turning"]
    machine = MachineProfile(x_words_are_diameter=True)
    lines = op.generate(defaults(op), machine, Units.INCH)
    ext = extents(lines)
    assert ext["X"][0] == pytest.approx(0.4)   # X words are diameters


def test_turning_rejects_growing_cut():
    op = BY_KEY["ext_turning"]
    with pytest.raises(ValueError):
        op.generate(defaults(op) | {"end_dia": 0.6}, MACHINE, Units.INCH)


def test_boring_retracts_inward():
    op = BY_KEY["int_boring"]
    p = defaults(op) | {"start_dia": 0.25, "end_dia": 0.375,
                        "clearance": 0.02}
    lines = op.generate(p, MACHINE, Units.INCH)
    ext = extents(lines)
    assert ext["X"][0] == pytest.approx(0.125 - 0.02)  # never past start bore
    assert ext["X"][1] == pytest.approx(0.375 / 2)


def test_facing_reaches_center():
    op = BY_KEY["ext_facing"]
    lines = op.generate(defaults(op), MACHINE, Units.INCH)
    ext = extents(lines)
    assert ext["X"][0] == pytest.approx(0.0)
    assert ext["Z"][0] == pytest.approx(-0.020)


def test_parting_pecks():
    op = BY_KEY["int_parting"]
    p = defaults(op) | {"peck": 0.05, "work_dia": 0.75, "end_dia": 0.0}
    lines = op.generate(p, MACHINE, Units.INCH)
    plunges = [l for l in lines if l.startswith("G1 X")]
    assert len(plunges) == 8            # 0.375 radius / 0.05 peck
    assert plunges[-1].startswith("G1 X0.0000")


def test_taper_finish_pass_moves_both_axes():
    op = BY_KEY["ext_taper"]
    lines = op.generate(defaults(op), MACHINE, Units.INCH)
    finish = [l for l in lines if "X" in l and "Z-" in l and l.startswith("G1")]
    assert finish, "expected a simultaneous X/Z taper move"


def test_thread_g76_words():
    op = BY_KEY["ext_thread"]
    lines = op.generate(defaults(op), MACHINE, Units.INCH)
    g76 = [l for l in lines if l.startswith("G76")]
    assert len(g76) == 1
    # 20 TPI -> pitch 0.05, auto depth 0.6134 * 0.05
    assert "P0.0500" in g76[0]
    assert "K0.0307" in g76[0]
    assert "I-0.0200" in g76[0]     # external: peak below drive line
    assert "R1.5" in g76[0]         # default depth degression
    assert "Q29.5" in g76[0]


def test_thread_g33_fallback():
    op = BY_KEY["ext_thread"]
    machine = MachineProfile(has_g76=False)
    lines = op.generate(defaults(op), machine, Units.INCH)
    g33 = [l for l in lines if l.startswith("G33")]
    assert len(g33) > 3
    assert all("K0.0500" in l for l in g33)
    assert not any(l.startswith("G76") for l in lines)


def test_thread_internal_direction():
    op = BY_KEY["int_thread"]
    machine = MachineProfile(has_g76=False)
    p = defaults(op) | {"dia": 0.4056}
    lines = op.generate(p, machine, Units.INCH)
    ext = extents(lines)
    # internal threading cuts outward from the bore
    assert ext["X"][1] > 0.4056 / 2


def test_thread_metric_pitch():
    # mm mode: pitch_val is mm/rev, used verbatim
    op = BY_KEY["ext_thread"]
    p = defaults(op) | {"pitch_val": 1.5,
                        "dia": 10.0, "first_depth": 0.1,
                        "clearance": 0.5, "length": 12.0}
    lines = op.generate(p, MACHINE, Units.MM)
    g76 = [l for l in lines if l.startswith("G76")][0]
    assert "P1.500" in g76


def test_thread_inch_pitch_is_tpi():
    # inch mode: pitch_val is TPI, arbitrary values allowed
    op = BY_KEY["ext_thread"]
    p = defaults(op) | {"pitch_val": 13.5}
    lines = op.generate(p, MACHINE, Units.INCH)
    g76 = [l for l in lines if l.startswith("G76")][0]
    assert f"P{1 / 13.5:.4f}" in g76


def test_thread_zero_depth_rejected():
    # 0 is no longer "auto": the user must tap A to fill the depth
    op = BY_KEY["ext_thread"]
    p = defaults(op) | {"total_depth": 0.0}
    with pytest.raises(ValueError):
        op.generate(p, MACHINE, Units.INCH)


def test_thread_zero_pitch_rejected():
    op = BY_KEY["ext_thread"]
    p = defaults(op) | {"pitch_val": 0.0}
    with pytest.raises(ValueError):
        op.generate(p, MACHINE, Units.INCH)
