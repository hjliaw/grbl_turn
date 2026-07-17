"""Toolpath-preview parsing (pure part of grbl_turn.ui.path_view)."""

import pytest

from grbl_turn.machine import MachineProfile
from grbl_turn.ops import BY_KEY
from grbl_turn.ui.path_view import (Segment, feed_profile, line_durations,
                                    parse_segments, segment_extents)
from grbl_turn.units import Units

MACHINE = MachineProfile()


def defaults(op) -> dict:
    p = {f.name: f.default for f in op.fields}
    for f in op.fields:   # zero defaults are literal now: "tap A" like a user
        if f.auto is not None and not p[f.name]:
            p[f.name] = f.auto(p, Units.INCH)
    return p


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


def test_g76_extents_include_thread_depth():
    from grbl_turn.units import Units
    from grbl_turn.gcode import extents
    op = BY_KEY["ext_thread"]
    lines = op.generate(defaults(op), MACHINE, Units.INCH)
    ext = segment_extents(parse_segments(lines))
    # tool must reach the minor radius: major 0.25 - 0.6134 * pitch 0.05
    assert ext["X"][0] == pytest.approx(0.25 - 0.6134 * 0.05, abs=1e-4)
    # word-scanning only sees the drive line — the very bug this guards
    assert extents(lines)["X"][0] > ext["X"][0]


def test_feed_profile_turning_envelope():
    segs = [Segment(0.1, 0.4, -1.0, 0.4, rapid=False),
            Segment(0.1, 0.3, -1.0, 0.3, rapid=False)]
    prof = feed_profile(segs, "turn")
    assert prof.stock == pytest.approx(0.4)
    # bar runs from a little beyond the cuts (stock) to the face (Z0)
    assert prof.zs[0] < -1.0 and prof.zs[-1] == pytest.approx(0.0)
    assert prof.env[0] == pytest.approx(0.4)    # chuck-side overhang
    assert prof.env[-1] == pytest.approx(0.3)   # cut down at the face
    assert min(prof.env) == pytest.approx(0.3)


def test_feed_profile_facing_clears_right_of_cut():
    segs = [Segment(-0.02, 0.4, -0.02, 0.0, rapid=False),
            Segment(-0.01, 0.4, -0.01, 0.0, rapid=False)]
    prof = feed_profile(segs, "face")
    assert prof.env[0] == pytest.approx(0.4)    # the finished face wall
    assert prof.env[-1] == pytest.approx(0.0)   # everything right: removed


def test_feed_profile_bore_envelope():
    segs = [Segment(0.1, 0.2, -0.5, 0.2, rapid=False),
            Segment(0.1, 0.25, -0.5, 0.25, rapid=False)]
    prof = feed_profile(segs, "bore")
    assert prof.stock == pytest.approx(0.2)     # the pilot bore surface
    assert prof.env[0] == pytest.approx(0.2)    # overhang: pilot wall
    assert prof.env[-1] == pytest.approx(0.25)
    assert max(prof.env) == pytest.approx(0.25)


def test_feed_profile_parting_notch():
    # plunge-only cut: the bar spans groove-overhang to face, notched
    segs = [Segment(0.1, 0.55, -0.5, 0.55, rapid=True),
            Segment(-0.5, 0.55, -0.5, 0.02, rapid=False),
            Segment(-0.5, 0.02, -0.5, 0.55, rapid=True)]
    prof = feed_profile(segs, "turn")
    assert prof.zs[0] < -0.5 and prof.zs[-1] == pytest.approx(0.0)
    assert min(prof.env) == pytest.approx(0.02)   # the groove
    assert prof.env[-1] == pytest.approx(0.55)    # bar kept beside it


def test_feed_profile_needs_feeds():
    assert feed_profile([Segment(0.1, 0.5, -1.0, 0.5, rapid=True)],
                        "turn") is None


def test_line_durations_weight_cuts_over_rapids():
    lines = ["(header)", "G20 G18 G90 G94",
             "G0 X0.5 Z0.1", "G1 Z-1.0 F2", "G0 X0.6", "", "G0 Z0.1"]
    dur = line_durations(lines)
    assert len(dur) == 6              # blank dropped, like the streamer
    assert dur[0] == 0.0 and dur[1] == 0.0
    # the 1.1"-long cut at F2 dwarfs the rapids around it
    assert dur[3] == pytest.approx(33.0)
    assert dur[3] > 10 * max(dur[2], dur[4], dur[5])


def test_line_durations_g76_weighs_the_whole_cycle():
    op = BY_KEY["ext_thread"]
    lines = op.generate(defaults(op), MACHINE, Units.INCH)
    stripped = [l for l in lines if l.strip()]
    dur = line_durations(lines)
    assert len(dur) == len(stripped)
    g76_time = sum(d for l, d in zip(stripped, dur) if l.startswith("G76"))
    assert g76_time > 0.5 * sum(dur)   # the cycle dominates the program


def test_comments_and_blank_lines_ignored():
    segs = parse_segments(["(comment with X9 Z9)", "", "G20 G18 G90 G94",
                           "G0 X0.5 Z0.1", "G1 Z-1.0 F3"])
    assert len(segs) == 1
    assert not segs[0].rapid
    assert (segs[0].z0, segs[0].x0) == (0.1, 0.5)
    assert (segs[0].z1, segs[0].x1) == (-1.0, 0.5)
