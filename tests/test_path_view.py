"""Toolpath-preview parsing (pure part of grbl_turn.ui.path_view)."""

import pytest

from grbl_turn.machine import MachineProfile
from grbl_turn.ops import BY_KEY
from grbl_turn.ui.path_view import parse_segments

MACHINE = MachineProfile()


def defaults(op) -> dict:
    return {f.name: f.default for f in op.fields}


def test_segments_are_continuous():
    from grbl_turn.units import Units
    op = BY_KEY["ext_turning"]
    segs = parse_segments(op.generate(defaults(op), MACHINE, Units.INCH))
    assert segs
    for a, b in zip(segs, segs[1:]):
        assert (a.z1, a.x1) == (b.z0, b.x0)


def test_turning_feeds_match_passes():
    from grbl_turn.units import Units
    op = BY_KEY["ext_turning"]
    lines = op.generate(defaults(op), MACHINE, Units.INCH)
    feeds = [s for s in parse_segments(lines) if not s.rapid]
    # default 0.25 -> 0.2 radius, doc 0.02, finish 0.005 -> 4 passes
    assert len(feeds) == 4
    assert all(s.z1 == pytest.approx(-0.75) for s in feeds)
    assert feeds[-1].x1 == pytest.approx(0.2)


def test_g76_expands_to_thread_passes():
    from grbl_turn.units import Units
    op = BY_KEY["ext_thread"]
    lines = op.generate(defaults(op), MACHINE, Units.INCH)
    assert any(l.startswith("G76") for l in lines)
    feeds = [s for s in parse_segments(lines) if not s.rapid]
    assert len(feeds) >= 5                    # multiple passes drawn
    # every pass runs the full thread length at increasing depth
    assert all(s.z1 == pytest.approx(-0.5) for s in feeds)
    depths = [s.x1 for s in feeds]
    assert all(b <= a for a, b in zip(depths, depths[1:]))
    # final passes at full depth: major radius - 0.6134 * pitch
    assert depths[-1] == pytest.approx(0.25 - 0.6134 * 0.05, abs=1e-4)


def test_g33_fallback_draws_same_shape():
    from grbl_turn.units import Units
    op = BY_KEY["ext_thread"]
    machine = MachineProfile(has_g76=False)
    lines = op.generate(defaults(op), machine, Units.INCH)
    feeds = [s for s in parse_segments(lines) if not s.rapid]
    assert len(feeds) >= 5
    assert feeds[-1].x1 == pytest.approx(0.25 - 0.6134 * 0.05, abs=1e-4)


def test_comments_and_blank_lines_ignored():
    segs = parse_segments(["(comment with X9 Z9)", "", "G20 G18 G90 G94",
                           "G0 X0.5 Z0.1", "G1 Z-1.0 F3"])
    assert len(segs) == 1
    assert not segs[0].rapid
    assert (segs[0].z0, segs[0].x0) == (0.1, 0.5)
    assert (segs[0].z1, segs[0].x1) == (-1.0, 0.5)
