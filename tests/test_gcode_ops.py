"""Generator checks per operation, inch and mm."""

import pytest

from grbl_turn.gcode import extents, origin, positions
from grbl_turn.machine import MachineProfile
from grbl_turn.ops import BY_KEY, REGISTRY
from grbl_turn.ops.taper import MODE_TRIM
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


def ends_at(lines, prefix):
    """Absolute (x, z) each line starting with `prefix` leaves the tool at."""
    return [(x, z) for l, x, z in positions(lines) if l.startswith(prefix)]


@pytest.mark.parametrize("units", [Units.INCH, Units.MM])
@pytest.mark.parametrize("op", REGISTRY, ids=lambda op: op.key)
def test_all_ops_generate_with_defaults(op, units):
    lines = op.generate(defaults(op), MACHINE, units)
    b = body(lines)
    assert b[0] == f"{units.gcode} G18 G91 G94"
    assert b[-1] == "M2"
    # every move is relative: nothing may switch back to absolute, and the
    # header must tell the operator where to start
    assert not any("G90" in l for l in b)
    assert any(l.startswith("(ORIGIN ") or l.startswith("(START ")
               for l in lines)
    # no motion before the units/plane line, spindle never started by default
    assert not any(l.startswith("M3") for l in b)
    # GRBL rejects nested parentheses inside comments
    for l in lines:
        if l.startswith("("):
            assert "(" not in l[1:-1] and ")" not in l[1:-1], l


def test_turning_passes_and_extents():
    op = BY_KEY["ext_turning"]
    p = defaults(op) | {"start_dia": 0.5, "end_dia": 0.4, "doc": 0.02,
                        "finish_allow": 0.005, "length": 0.75}
    lines = op.generate(p, MACHINE, Units.INCH)
    ext = extents(lines)
    # radius mode: deepest X word is the final radius
    assert ext["X"][0] == pytest.approx(0.2)
    assert ext["Z"][0] == pytest.approx(-0.75)
    # each cut is one relative move: clearance in front of the face, then
    # the full length
    assert "G1 Z-0.7900 F3" in "\n".join(lines)
    assert all(z == pytest.approx(-0.75) for _, z in ends_at(lines, "G1 Z"))


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
    plunges = ends_at(lines, "G1 X")
    assert len(plunges) == 8            # 0.375 radius / 0.05 peck
    assert plunges[-1][0] == pytest.approx(0.0)      # parts off at center


def test_taper_finish_pass_moves_both_axes():
    op = BY_KEY["ext_taper"]
    lines = op.generate(defaults(op), MACHINE, Units.INCH)
    finish = [l for l in lines if "X" in l and "Z-" in l and l.startswith("G1")]
    assert finish, "expected a simultaneous X/Z taper move"
    assert not any(l.startswith("(WARNING") for l in lines)


def test_taper_trim_progressive_passes():
    import math
    op = BY_KEY["ext_taper"]
    p = defaults(op) | {"mode": MODE_TRIM}
    # defaults: existing 0.500 -> target 0.480 at face, 0.010 radial skin;
    # doc 0.020 covers it in a single full-length pass
    lines = op.generate(p, MACHINE, Units.INCH)

    def taper_ends(lines):
        return [(x, z) for l, x, z in positions(lines)
                if l.startswith("G1") and "X" in l and "Z" in l]

    def roughing_cuts(lines):
        # straight roughing feeds into the work; the taper passes' Z-only
        # feed only closes the clearance gap back to the face
        return [(x, z) for l, x, z in positions(lines)
                if l.startswith("G1 Z") and "X" not in l and z < -1e-9]

    assert len(taper_ends(lines)) == 1
    assert not roughing_cuts(lines)
    end_r = p["target_dia"] / 2 + p["length"] * math.tan(
        math.radians(p["angle"]))
    assert taper_ends(lines)[0][0] == pytest.approx(end_r, abs=1e-4)
    # stock diameter is irrelevant in trim mode
    assert op.generate(p | {"start_dia": 9.9}, MACHINE, Units.INCH) == lines

    # a smaller doc steps down in parallel passes, ending on the target
    lines = op.generate(p | {"doc": 0.004}, MACHINE, Units.INCH)
    ends = taper_ends(lines)
    assert len(ends) == 3          # 0.010 skin / 0.004 doc
    assert ends[-1][0] == pytest.approx(end_r, abs=1e-4)
    assert ends[0][0] == pytest.approx(end_r + 0.006, abs=1e-4)

    # a target that leaves the existing surface uncut is an error
    with pytest.raises(ValueError):
        op.generate(p | {"target_dia": 0.6}, MACHINE, Units.INCH)


def test_taper_overrun_warns_but_generates():
    # exceeding the stock / undercutting the bore is allowed with a warning
    op = BY_KEY["ext_taper"]
    lines = op.generate(defaults(op) | {"angle": 20.0}, MACHINE, Units.INCH)
    assert any("WARNING" in l and "exceeds the stock" in l for l in lines)
    assert any(l.startswith("G1") for l in lines)

    op = BY_KEY["int_taper"]
    lines = op.generate(defaults(op) | {"angle": 12.0}, MACHINE, Units.INCH)
    assert any("WARNING" in l and "undercuts the existing bore" in l
               for l in lines)


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
    # Z is a distance like any other axis word under G91: the default
    # lead-in of 2x pitch is already travelled, so the cycle's Z spans the
    # lead-in plus the thread
    assert "G0 Z0.1000" in lines
    assert "Z-0.6000" in g76[0]
    # external starts on the crest: one hop out to the drive line by abs(I)
    # before the cycle, and one hop back after it — no other X motion, so
    # the cycle itself infeeds from there
    assert [l for l in body(lines) if "X" in l] == ["G0 X0.0200", "G0 X-0.0200"]
    assert body(lines).index("G0 X0.0200") < body(lines).index(g76[0])


def test_thread_g76_z_word_follows_the_lead_in():
    # the Z word is relative, so it tracks where the lead-in rapid left the
    # tool rather than repeating the thread length blindly
    op = BY_KEY["ext_thread"]
    lines = op.generate(defaults(op) | {"lead_in": 0.0}, MACHINE, Units.INCH)
    g76 = [l for l in lines if l.startswith("G76")][0]
    before = lines[:lines.index(g76)]
    assert not any(l.startswith("G0 Z") for l in before)  # already at the face
    assert "Z-0.5000" in g76        # no lead-in: just the thread


def test_thread_internal_g76_has_no_x_move():
    # internal is parked clear of the crest already: nothing to back out of
    op = BY_KEY["int_thread"]
    lines = op.generate(defaults(op) | {"total_depth": 0.027}, MACHINE,
                        Units.INCH)
    assert not any("X" in l for l in body(lines))


def test_thread_g33_fallback():
    op = BY_KEY["ext_thread"]
    machine = MachineProfile(has_g76=False)
    lines = op.generate(defaults(op), machine, Units.INCH)
    g33 = [l for l in lines if l.startswith("G33")]
    assert len(g33) > 3
    assert all("K0.0500" in l for l in g33)
    assert not any(l.startswith("G76") for l in lines)
    # every synced pass runs to the same absolute Z
    assert all(z == pytest.approx(-0.5) for _, z in ends_at(lines, "G33"))


def test_thread_internal_direction():
    op = BY_KEY["int_thread"]
    machine = MachineProfile(has_g76=False)
    lines = op.generate(defaults(op), machine, Units.INCH)
    # X is measured from the start position; internal cuts outward into the
    # bore wall, past the crest a clearance away
    assert extents(lines)["X"][1] > 0.02


def test_thread_external_direction():
    op = BY_KEY["ext_thread"]
    machine = MachineProfile(has_g76=False)
    lines = op.generate(defaults(op), machine, Units.INCH)
    # X is measured from the crest: infeeds go negative, and nothing reaches
    # further out than the drive line
    ext = extents(lines)
    assert ext["X"][0] == pytest.approx(-0.6134 * 0.05, abs=1e-4)
    assert ext["X"][1] == pytest.approx(0.02)


def test_thread_g33_returns_to_the_start():
    # the fallback knows where it ends, so the program is re-runnable
    op = BY_KEY["ext_thread"]
    lines = op.generate(defaults(op), MachineProfile(has_g76=False),
                        Units.INCH)
    end = positions(lines)[-1]
    assert end[1] == pytest.approx(0.0) and end[2] == pytest.approx(0.0)


def test_thread_g76_returns_to_the_start():
    # eznc now ends the cycle at the Z word (thread end) like grblHAL and
    # LinuxCNC, so the program knows exactly where it is and can close out
    # with an ordinary return to the origin, same as the G33 fallback
    op = BY_KEY["ext_thread"]
    lines = op.generate(defaults(op), MACHINE, Units.INCH)
    b = body(lines)
    i = next(k for k, l in enumerate(b) if l.startswith("G76"))
    assert b[i + 1] == "G0 Z0.5000"    # back from the thread end to the face
    assert b[i + 2] == "G0 X-0.0200"  # back from the drive line to the crest
    assert b[i + 3] == "M2"
    assert len(b) == i + 4
    end = positions(lines)[-1]
    assert end[1] == pytest.approx(0.0) and end[2] == pytest.approx(0.0)


def test_thread_metric_pitch():
    # mm mode: pitch_val is mm/rev, used verbatim
    op = BY_KEY["ext_thread"]
    p = defaults(op) | {"pitch_val": 1.5, "first_depth": 0.1,
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
