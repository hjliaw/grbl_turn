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

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
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


def segment_extents(segments: list[Segment]) -> dict[str, tuple[float, float]]:
    """Min/max positions the tool actually reaches. Unlike scanning X/Z
    words, this includes G76 passes (depth hides in I/J/K words)."""
    if not segments:
        return {}
    zs = [v for s in segments for v in (s.z0, s.z1)]
    xs = [v for s in segments for v in (s.x0, s.x1)]
    return {"X": (min(xs), max(xs)), "Z": (min(zs), max(zs))}


RAPID_PEN = (QColor(110, 150, 255), 1, Qt.PenStyle.DashLine)
FEED_PEN = (QColor(120, 220, 120), 2, Qt.PenStyle.SolidLine)
TOOL_COLOR = QColor(255, 70, 70)
SIM_COLOR = QColor(255, 200, 60)
SIM_DURATION_MS = 10000       # short programs: whole run in this time
SIM_FEED_SEG_MS = 1000        # many-pass programs: per cut segment
SIM_TICK_MS = 30
SIM_RAPID_FACTOR = 4.0        # rapids animate this much faster


class PathView(QWidget):
    sim_moved = Signal(float, float)    # z, x in program coordinates
    sim_stopped = Signal()

    def __init__(self, lines: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setMinimumSize(260, 120)
        self.segments: list[Segment] = []
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
        zmin, zmax = min(zs), max(zs)
        xmin, xmax = min(xs), max(xs)
        z_span = max(zmax - zmin, 1e-9)
        x_span = max(xmax - xmin, 1e-9)

        margin = 26
        avail_w = max(rect.width() - 2 * margin, 1)
        avail_h = max(rect.height() - 2 * margin, 1)
        # true aspect when it stays readable, otherwise stretch to fit
        s_uni = min(avail_w / z_span, avail_h / x_span)
        if s_uni * z_span >= 0.25 * avail_w and s_uni * x_span >= 0.25 * avail_h:
            sz = sx = s_uni
        else:
            sz, sx = avail_w / z_span, avail_h / x_span
        off_z = margin + (avail_w - sz * z_span) / 2.0
        off_x = margin + (avail_h - sx * x_span) / 2.0

        def px(z: float) -> float:
            return off_z + (z - zmin) * sz

        def py(x: float) -> float:
            return off_x + (x - xmin) * sx     # +X points down (tool in front)

        # spindle centerline (X0)
        if xmin <= 0.0 <= xmax:
            p.setPen(QPen(QColor(120, 120, 120), 1,
                          Qt.PenStyle.DashDotLine))
            p.drawLine(int(margin / 2), int(py(0.0)),
                       int(rect.width() - margin / 2), int(py(0.0)))

        # part face (Z0)
        if zmin <= 0.0 <= zmax:
            p.setPen(QPen(QColor(90, 90, 90), 1, Qt.PenStyle.DashLine))
            p.drawLine(int(px(0.0)), int(margin / 2),
                       int(px(0.0)), int(rect.height() - margin / 2))

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

        # axis hints, tucked under the centerline where no cutting happens
        hint_y = int(py(0.0) if xmin <= 0.0 <= xmax else margin) + 16
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QColor(140, 140, 140))
        p.drawText(rect.width() - 60, hint_y, "+Z →")
        p.drawText(10, hint_y, "X↓ (radius)")
