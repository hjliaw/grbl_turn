"""Pass calculations shared by the operations. Pure functions, unit-agnostic:
they work in whatever units the caller is using. All radial values are radii."""

import math


def turning_passes(start_r: float, end_r: float, doc: float,
                   finish_allow: float = 0.0) -> list[float]:
    """Radii to cut, stepping from start_r toward end_r by doc (radial depth
    per pass). Works in both directions: shrinking (OD turning) and growing
    (boring). A finish_allow leaves that much for a final pass at end_r.
    The returned list always ends exactly at end_r."""
    if doc <= 0:
        raise ValueError("depth per pass must be positive")
    direction = 1.0 if end_r > start_r else -1.0
    rough_target = end_r - direction * finish_allow
    passes = []
    r = start_r
    # guard: if allowance overshoots the start there is only the finish pass
    if (rough_target - start_r) * direction > 1e-9:
        while True:
            r += direction * doc
            if (r - rough_target) * direction >= -1e-9:
                passes.append(rough_target)
                break
            passes.append(r)
    if not passes or abs(passes[-1] - end_r) > 1e-9:
        passes.append(end_r)
    return passes


def thread_infeeds(total_depth: float, first_depth: float,
                   degression: float = 2.0, spring: int = 1) -> list[float]:
    """Cumulative infeed depths for threading passes with LinuxCNC G76 "R"
    depth degression: depth_n = first_depth * n**(1/degression). R1.0 cuts
    the same depth every pass, R2.0 keeps the chip area constant. Depths
    are capped at total_depth, plus `spring` repeat passes at full depth."""
    if not (0 < first_depth <= total_depth):
        raise ValueError("first pass depth must be >0 and <= total depth")
    if degression < 1.0:
        raise ValueError("degression must be >= 1.0")
    depths = []
    prev = 0.0
    n = 1
    while prev < total_depth - 1e-9:
        d = min(first_depth * n ** (1.0 / degression), total_depth)
        depths.append(d)
        prev = d
        n += 1
    depths.extend([total_depth] * spring)
    return depths


def flank_offset(depth: float, compound_deg: float) -> float:
    """Z shift toward the tailstock for a given infeed depth when feeding
    along the thread flank (compound angle, typically 29.5 deg)."""
    return depth * math.tan(math.radians(compound_deg))
