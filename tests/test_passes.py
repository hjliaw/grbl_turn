import math

import pytest

from grbl_turn.ops.passes import flank_offset, thread_infeeds, turning_passes


def test_turning_passes_shrinking():
    passes = turning_passes(0.25, 0.20, doc=0.02, finish_allow=0.005)
    assert passes == pytest.approx([0.23, 0.21, 0.205, 0.20])
    assert passes[-1] == 0.20


def test_turning_passes_growing_boring():
    passes = turning_passes(0.125, 0.1875, doc=0.01, finish_allow=0.0)
    assert passes[0] == pytest.approx(0.135)
    assert passes[-1] == pytest.approx(0.1875)
    assert all(b > a for a, b in zip(passes, passes[1:]))


def test_turning_passes_exact_multiple():
    passes = turning_passes(0.25, 0.21, doc=0.02)
    assert passes == pytest.approx([0.23, 0.21])


def test_turning_passes_only_finish():
    # allowance covers the whole cut -> single pass at final size
    passes = turning_passes(0.25, 0.245, doc=0.02, finish_allow=0.01)
    assert passes == pytest.approx([0.245])


def test_turning_passes_bad_doc():
    with pytest.raises(ValueError):
        turning_passes(0.25, 0.2, doc=0.0)


def test_thread_infeeds_degressive():
    depths = thread_infeeds(0.035, first_depth=0.005, min_depth=0.001,
                            spring=1)
    assert depths[0] == pytest.approx(0.005)
    assert depths[1] == pytest.approx(0.005 * math.sqrt(2))
    # monotonic, capped at total, spring pass duplicated at the end
    assert all(b >= a for a, b in zip(depths, depths[1:]))
    assert depths[-1] == depths[-2] == pytest.approx(0.035)
    # increments never smaller than min_depth, except the last one which is
    # capped at total depth
    increments = [b - a for a, b in zip(depths, depths[1:-1])]
    assert all(inc >= 0.001 - 1e-9 for inc in increments[:-1])


def test_thread_infeeds_bad_first():
    with pytest.raises(ValueError):
        thread_infeeds(0.02, first_depth=0.05, min_depth=0.001)


def test_flank_offset():
    assert flank_offset(0.010, 0) == 0
    assert flank_offset(0.010, 29.5) == pytest.approx(
        0.010 * math.tan(math.radians(29.5)))
