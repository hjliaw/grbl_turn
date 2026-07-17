"""Toolpath preview: parses the generated program and draws the X/Z motion.

Coordinates are drawn as emitted (X = radius for stock GRBL), Z increasing
to the right — the part face sits at the right edge and cuts run leftward.
+X points down, matching a hobby lathe with the tool in front of the
centerline: the tool sits below the work in the view, as the operator sees it.
G76 canned cycles are expanded into their individual passes with the same
degressive-infeed math the G33 fallback uses, so the thread passes are
visible even when the firmware does the looping.
"""

import math
import re
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from grbl_turn.ops.passes import thread_infeeds

WORD_RE = re.compile(r"([A-Z])(-?\d*\.?\d+)")


@dataclass
class Segment:
    z0: float
    x0: float
    z1: float
    x1: float
    rapid: bool


def _words(line: str) -> dict[str, list[float]]:
    line = re.sub(r"\(.*?\)", "", line).upper()
    found: dict[str, list[float]] = {}
    for letter, value in WORD_RE.findall(line):
        found.setdefault(letter, []).append(float(value))
    return found


def _expand_g76(w: dict, z: float, x: float) -> list[Segment]:
    """Approximate the passes G76 will run, from its words and the current
    (drive-line) position. Flank offset is ignored — invisibly small here."""
    try:
        z_end = w["Z"][0]
        i_word = w["I"][0]
        first = w["J"][0]
        total = w["K"][0]
        spring = int(w.get("H", [1])[0])
        degression = w.get("R", [2.0])[0]
        peak_x = x + i_word
        sign = 1.0 if i_word > 0 else -1.0     # cut direction off the peak
        depths = thread_infeeds(total, min(first, total), degression, spring)
    except (KeyError, IndexError, ValueError):
        return []
    if len(depths) > 80:   # viz-only: thin absurdly dense schedules
        step = math.ceil(len(depths) / 80)
        depths = depths[::step] + depths[-1:]
    segs = []
    for d in depths:
        cut_x = peak_x + sign * d
        segs.append(Segment(z, x, z, cut_x, rapid=True))
        segs.append(Segment(z, cut_x, z_end, cut_x, rapid=False))
        segs.append(Segment(z_end, cut_x, z_end, x, rapid=True))
        segs.append(Segment(z_end, x, z, x, rapid=True))
    return segs


def parse_segments(lines: list[str]) -> list[Segment]:
    segments: list[Segment] = []
    modal = 0                     # current motion mode: 0, 1, or 33
    pos: tuple[float, float] | None = None    # (z, x)
    for line in lines:
        w = _words(line)
        if not w:
            continue
        gs = w.get("G", [])
        if 76 in gs:
            if pos is not None:
                segments += _expand_g76(w, pos[0], pos[1])
            continue
        for g in gs:
            if g in (0, 1, 33):
                modal = int(g)
        if "X" not in w and "Z" not in w:
            continue
        z = w["Z"][0] if "Z" in w else (pos[0] if pos else 0.0)
        x = w["X"][0] if "X" in w else (pos[1] if pos else 0.0)
        if pos is not None and (z, x) != pos:
            segments.append(Segment(pos[0], pos[1], z, x, rapid=modal == 0))
        pos = (z, x)
    return segments


# nominal rates for duration estimates; the spindle is manual (no S words)
# so threading assumes an RPM. Absolute accuracy doesn't matter — progress
# only needs the relative weight between lines.
EST_THREAD_RPM = 300.0
EST_RAPID_MM = 1500.0        # units/min
EST_RAPID_INCH = 60.0


def line_durations(lines: list[str]) -> list[float]:
    """Estimated seconds per non-blank line, parallel to the list the
    streamer acks (it drops blank lines the same way)."""
    out: list[float] = []
    modal = 0
    pos: tuple[float, float] | None = None
    feed = 60.0                  # units/min; placeholder until an F arrives
    rapid = EST_RAPID_MM
    pitch = 1.0                  # units/rev; placeholder until a G33 K
    for line in (l.strip() for l in lines if l.strip()):
        w = _words(line)
        gs = w.get("G", [])
        if 20 in gs:
            rapid = EST_RAPID_INCH
        if 21 in gs:
            rapid = EST_RAPID_MM
        if "F" in w:
            feed = w["F"][0]
        seconds = 0.0
        if 76 in gs:             # whole canned cycle on one line
            thread_feed = w.get("P", [pitch])[0] * EST_THREAD_RPM
            if pos is not None:
                for s in _expand_g76(w, pos[0], pos[1]):
                    d = math.hypot(s.z1 - s.z0, s.x1 - s.x0)
                    seconds += 60.0 * d / (rapid if s.rapid
                                           else max(thread_feed, 1e-9))
            out.append(seconds)
            continue
        for g in gs:
            if g in (0, 1, 33):
                modal = int(g)
        if ("X" in w or "Z" in w) and pos is not None:
            z = w["Z"][0] if "Z" in w else pos[0]
            x = w["X"][0] if "X" in w else pos[1]
            if modal == 33:
                if "K" in w:
                    pitch = w["K"][0]
                rate = max(pitch * EST_THREAD_RPM, 1e-9)
            else:
                rate = rapid if modal == 0 else max(feed, 1e-9)
            seconds = 60.0 * math.hypot(z - pos[0], x - pos[1]) / rate
            pos = (z, x)
        elif "X" in w or "Z" in w:
            pos = (w.get("Z", [0.0])[0], w.get("X", [0.0])[0])
        out.append(seconds)
    return out


def segment_extents(segments: list[Segment]) -> dict[str, tuple[float, float]]:
    """Min/max positions the tool actually reaches. Unlike scanning X/Z
    words, this includes G76 passes (depth hides in I/J/K words)."""
    if not segments:
        return {}
    zs = [v for s in segments for v in (s.z0, s.z1)]
    xs = [v for s in segments for v in (s.x0, s.x1)]
    return {"X": (min(xs), max(xs)), "Z": (min(zs), max(zs))}


@dataclass
class Profile:
    """Part silhouette sampled on a uniform Z grid."""
    mode: str
    zs: list[float]
    env: list[float]
    stock: float           # radius of the untouched surface

PROFILE_COLS = 400


def feed_profile(segments: list[Segment], mode: str) -> Profile | None:
    """Derive the finished-part surface from the cutting moves alone: each
    feed move redefines the surface at the radius it passed. Columns no cut
    touched keep the stock radius; "face" cuts also clear everything to
    their +Z side; "bore" cuts raise the bore wall instead."""
    feeds = [s for s in segments if not s.rapid]
    if not feeds:
        return None
    zl = min(min(s.z0, s.z1) for s in feeds)
    zr = max(max(s.z0, s.z1) for s in feeds)
    # stock runs from the face (Z0 by app convention) into the chuck: clamp
    # away cut overshoot into air on the right, overhang a little on the
    # left so the bar reads as continuing stock
    zr = 0.0
    if zr - zl <= 1e-9:
        return None
    zl -= 0.06 * (zr - zl)
    n = PROFILE_COLS
    dz = (zr - zl) / (n - 1)
    pick = max if mode == "bore" else min
    cols: list[float | None] = [None] * n
    for s in feeds:
        a, b = sorted((s.z0, s.z1))
        i0 = max(0, math.ceil((a - zl) / dz - 1e-9))
        i1 = min(n - 1, math.floor((b - zl) / dz + 1e-9))
        if i1 < i0:        # narrower than one column: snap to the nearest
            i0 = i1 = min(n - 1, max(0, round((0.5 * (a + b) - zl) / dz)))
        for i in range(i0, i1 + 1):
            if abs(s.z1 - s.z0) < 1e-12:
                x = pick(s.x0, s.x1)
            else:
                f = (zl + i * dz - s.z0) / (s.z1 - s.z0)
                x = s.x0 + min(max(f, 0.0), 1.0) * (s.x1 - s.x0)
            cols[i] = x if cols[i] is None else pick(cols[i], x)
    xs = [v for s in feeds for v in (s.x0, s.x1)]
    stock = min(xs) if mode == "bore" else max(xs)
    if mode == "face":     # material right of a facing cut is gone too;
        env, cur = [], stock       # the drop lands after the cut column so
        for c in cols:             # the finished face reads as a wall
            env.append(cur)
            if c is not None:
                cur = min(cur, c)
    else:      # turn: untouched columns keep stock; bore: the pilot wall
        env = [stock if c is None else c for c in cols]
    return Profile(mode, [zl + i * dz for i in range(n)], env, stock)


def _nice_step(span: float, target: int) -> float:
    """Tick spacing: a 1/2/5 x 10^k value giving about `target` ticks."""
    raw = span / max(target, 1)
    mag = 10.0 ** math.floor(math.log10(raw))
    for m in (1.0, 2.0, 5.0):
        if m * mag >= raw - 1e-12:
            return m * mag
    return 10.0 * mag


RAPID_PEN = (QColor(110, 150, 255), 1, Qt.PenStyle.DashLine)
FEED_PEN = (QColor(120, 220, 120), 2, Qt.PenStyle.SolidLine)
TOOL_COLOR = QColor(255, 70, 70)
SIM_COLOR = QColor(255, 200, 60)
PART_FILL = QColor(84, 90, 86)       # finished part body
STOCK_FILL = QColor(60, 64, 61)      # material the cuts remove
PROFILE_COLOR = QColor(168, 178, 170)
GRID_COLOR = QColor(58, 58, 58)
FRAME_COLOR = QColor(72, 72, 72)
TICK_COLOR = QColor(150, 150, 150)
SIM_DURATION_MS = 10000       # short programs: whole run in this time
SIM_FEED_SEG_MS = 1000        # many-pass programs: per cut segment
SIM_TICK_MS = 30
SIM_RAPID_FACTOR = 4.0        # rapids animate this much faster


class PathView(QWidget):
    sim_moved = Signal(float, float)    # z, x in program coordinates
    sim_stopped = Signal()

    def __init__(self, lines: list[str] | None = None,
                 silhouette: str = "turn", parent=None):
        super().__init__(parent)
        self.setMinimumSize(260, 120)
        self.silhouette = silhouette
        self.segments: list[Segment] = []
        self.profile: Profile | None = None
        self.tool: tuple[float, float] | None = None    # (z, x) from status
        self.sim_point: tuple[float, float] | None = None
        self.sim_paused = False
        self._sim_t = 0.0
        self._sim_timer = QTimer(self)
        self._sim_timer.setInterval(SIM_TICK_MS)
        self._sim_timer.timeout.connect(self._sim_step)
        if lines:
            self.set_lines(lines)

    def set_lines(self, lines: list[str]) -> None:
        self.segments = parse_segments(lines)
        self.profile = feed_profile(self.segments, self.silhouette)
        self.stop_simulation()
        self.update()

    def set_tool(self, z: float, x: float) -> None:
        """Current machine position, in the program's units and X-word
        convention (radius, or diameter on diameter-mode machines)."""
        if self.tool != (z, x):
            self.tool = (z, x)
            self.update()

    # -- tool-tip simulation ---------------------------------------------------
    def _sim_durations(self) -> list[float]:
        """Per-segment animation 'durations' (path length, rapids scaled)."""
        return [math.hypot(s.z1 - s.z0, s.x1 - s.x0)
                / (SIM_RAPID_FACTOR if s.rapid else 1.0)
                for s in self.segments]

    def start_simulation(self) -> None:
        if not self.segments:
            return
        # give every cut pass enough screen time (threading has dozens)
        feeds = sum(1 for s in self.segments if not s.rapid)
        self._sim_duration_ms = max(SIM_DURATION_MS, SIM_FEED_SEG_MS * feeds)
        self._sim_t = 0.0
        self.sim_paused = False
        first = self.segments[0]
        self.sim_point = (first.z0, first.x0)
        self._sim_timer.start()
        self.update()

    def pause_simulation(self) -> None:
        if self.sim_point is not None:
            self._sim_timer.stop()
            self.sim_paused = True

    def resume_simulation(self) -> None:
        if self.sim_point is not None:
            self.sim_paused = False
            self._sim_timer.start()

    def stop_simulation(self) -> None:
        was_running = self._sim_timer.isActive() or self.sim_point is not None
        self._sim_timer.stop()
        self.sim_point = None
        self.sim_paused = False
        if was_running:
            self.sim_stopped.emit()
        self.update()

    def _sim_step(self) -> None:
        durations = self._sim_durations()
        total = sum(durations)
        if total <= 0.0:
            self.stop_simulation()
            return
        self._sim_t += total * SIM_TICK_MS / self._sim_duration_ms
        t = self._sim_t
        for seg, dur in zip(self.segments, durations):
            if t <= dur and dur > 0.0:
                f = t / dur
                self.sim_point = (seg.z0 + f * (seg.z1 - seg.z0),
                                  seg.x0 + f * (seg.x1 - seg.x0))
                self.sim_moved.emit(*self.sim_point)
                self.update()
                return
            t -= dur
        self.stop_simulation()     # ran off the end: done

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        p.fillRect(rect, QColor(42, 42, 42))
        p.setPen(QColor(92, 92, 92))
        p.drawRect(rect.adjusted(0, 0, -1, -1))
        if not self.segments:
            p.setPen(QColor(140, 140, 140))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "no motion")
            return

        zs = [v for s in self.segments for v in (s.z0, s.z1)]
        xs = [v for s in self.segments for v in (s.x0, s.x1)]
        xs.append(0.0)                       # always show the centerline
        if self.profile:                     # silhouette overhangs the cuts
            zs += (self.profile.zs[0], self.profile.zs[-1])
        zmin, zmax = min(zs), max(zs)
        xmin, xmax = min(xs), max(xs)
        z_span = max(zmax - zmin, 1e-9)
        x_span = max(xmax - xmin, 1e-9)

        ml, mr, mt, mb = 48, 14, 16, 30      # left/bottom hold tick labels
        avail_w = max(rect.width() - ml - mr, 1)
        avail_h = max(rect.height() - mt - mb, 1)
        # true aspect when it stays readable, otherwise stretch to fit
        s_uni = min(avail_w / z_span, avail_h / x_span)
        if s_uni * z_span >= 0.25 * avail_w and s_uni * x_span >= 0.25 * avail_h:
            sz = sx = s_uni
        else:
            sz, sx = avail_w / z_span, avail_h / x_span
        off_z = ml + (avail_w - sz * z_span) / 2.0
        off_x = mt + (avail_h - sx * x_span) / 2.0

        def px(z: float) -> float:
            return off_z + (z - zmin) * sz

        def py(x: float) -> float:
            return off_x + (x - xmin) * sx     # +X points down (tool in front)

        left, right = ml, rect.width() - mr
        top, bottom = mt, rect.height() - mb

        # grid + tick labels over the whole plot area, not just the data span
        tick_font = p.font()
        tick_font.setPixelSize(11)
        p.setFont(tick_font)
        align = Qt.AlignmentFlag
        z_lo, z_hi = zmin - (off_z - left) / sz, zmin + (right - off_z) / sz
        step = _nice_step(z_hi - z_lo, 6)
        v = math.ceil(z_lo / step - 1e-9) * step
        while v <= z_hi + 1e-9:
            gx = px(v)
            p.setPen(QPen(GRID_COLOR, 1))
            p.drawLine(int(gx), top, int(gx), bottom)
            p.setPen(TICK_COLOR)
            p.drawText(QRectF(gx - 40, bottom + 3, 80, mb - 4),
                       align.AlignHCenter | align.AlignTop,
                       f"{round(v, 9) or 0.0:g}")     # or: no "-0" labels
            v += step
        x_lo, x_hi = xmin - (off_x - top) / sx, xmin + (bottom - off_x) / sx
        step = _nice_step(x_hi - x_lo, 4)
        v = math.ceil(x_lo / step - 1e-9) * step
        while v <= x_hi + 1e-9:
            gy = py(v)
            p.setPen(QPen(GRID_COLOR, 1))
            p.drawLine(left, int(gy), right, int(gy))
            p.setPen(TICK_COLOR)
            p.drawText(QRectF(0, gy - 8, ml - 6, 16),
                       align.AlignRight | align.AlignVCenter,
                       f"{round(v, 9) or 0.0:g}")
            v += step

        p.setClipRect(left, top, right - left, bottom - top)
        self._draw_silhouette(p, px, py, bottom)
        p.setClipping(False)

        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(FRAME_COLOR, 1))
        p.drawRect(QRectF(left, top, right - left, bottom - top))

        # spindle centerline (X0)
        if xmin <= 0.0 <= xmax:
            p.setPen(QPen(QColor(120, 120, 120), 1,
                          Qt.PenStyle.DashDotLine))
            p.drawLine(left, int(py(0.0)), right, int(py(0.0)))

        # part face (Z0)
        if zmin <= 0.0 <= zmax:
            p.setPen(QPen(QColor(90, 90, 90), 1, Qt.PenStyle.DashLine))
            p.drawLine(int(px(0.0)), top, int(px(0.0)), bottom)

        for seg in self.segments:
            color, width, style = RAPID_PEN if seg.rapid else FEED_PEN
            p.setPen(QPen(color, width, style))
            p.drawLine(int(px(seg.z0)), int(py(seg.x0)),
                       int(px(seg.z1)), int(py(seg.x1)))

        # start point marker
        first = self.segments[0]
        p.setPen(QPen(QColor(255, 255, 255), 1))
        p.setBrush(QColor(255, 255, 255))
        p.drawEllipse(int(px(first.z0)) - 3, int(py(first.x0)) - 3, 6, 6)

        # live tool position from the controller
        if self.tool is not None:
            p.setPen(QPen(TOOL_COLOR, 1))
            p.setBrush(TOOL_COLOR)
            p.drawEllipse(int(px(self.tool[0])) - 4,
                          int(py(self.tool[1])) - 4, 8, 8)

        # simulated tool tip
        if self.sim_point is not None:
            p.setPen(QPen(SIM_COLOR, 1))
            p.setBrush(SIM_COLOR)
            p.drawEllipse(int(px(self.sim_point[0])) - 4,
                          int(py(self.sim_point[1])) - 4, 8, 8)

        # axis hints in the top corners, clear of the toolpath and markers
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QColor(140, 140, 140))
        p.drawText(left + 6, top + 16, "X↓ (radius)")
        p.drawText(right - 46, top + 16, "+Z →")

    def _draw_silhouette(self, p: QPainter, px, py, bottom: int) -> None:
        prof = self.profile
        if prof is None:
            return
        p.setPen(Qt.PenStyle.NoPen)
        if prof.mode == "bore":
            # bore wall: material from the cut surface down to the plot edge
            pts = [QPointF(px(z), py(r)) for z, r in zip(prof.zs, prof.env)]
            poly = QPolygonF(pts)
            poly.append(QPointF(pts[-1].x(), bottom))
            poly.append(QPointF(pts[0].x(), bottom))
            p.setBrush(PART_FILL)
            p.drawPolygon(poly)
            p.setPen(QPen(PROFILE_COLOR, 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPolyline(QPolygonF(pts))
            return
        # stock first; the removed skin stays visible above the part body
        z0, z1 = prof.zs[0], prof.zs[-1]
        p.setBrush(STOCK_FILL)
        p.drawRect(QRectF(QPointF(px(z0), py(0.0)),
                          QPointF(px(z1), py(prof.stock))))
        pts = [QPointF(px(z), py(r)) for z, r in zip(prof.zs, prof.env)]
        p.setBrush(PART_FILL)
        p.drawPolygon(QPolygonF([QPointF(px(z0), py(0.0))] + pts
                                + [QPointF(px(z1), py(0.0))]))
        p.setPen(QPen(PROFILE_COLOR, 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPolyline(QPolygonF(pts))
