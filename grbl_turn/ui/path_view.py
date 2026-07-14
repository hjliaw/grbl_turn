"""Toolpath preview: parses the generated program and draws the X/Z motion.

Coordinates are drawn as emitted (X = radius for stock GRBL), Z increasing
to the right — the part face sits at the right edge and cuts run leftward.
G76 canned cycles are expanded into their individual passes with the same
degressive-infeed math the G33 fallback uses, so the thread passes are
visible even when the firmware does the looping.
"""

import re
from dataclasses import dataclass

from PySide6.QtCore import Qt
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
        peak_x = x + i_word
        sign = 1.0 if i_word > 0 else -1.0     # cut direction off the peak
        min_depth = max(total / 50.0, 1e-6)    # viz-only clamp on pass count
        depths = thread_infeeds(total, min(first, total), min_depth, spring)
    except (KeyError, IndexError, ValueError):
        return []
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


RAPID_PEN = (QColor(110, 150, 255), 1, Qt.PenStyle.DashLine)
FEED_PEN = (QColor(120, 220, 120), 2, Qt.PenStyle.SolidLine)


class PathView(QWidget):
    def __init__(self, lines: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 240)
        self.segments: list[Segment] = []
        if lines:
            self.set_lines(lines)

    def set_lines(self, lines: list[str]) -> None:
        self.segments = parse_segments(lines)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        p.fillRect(rect, QColor(20, 20, 20))
        p.setPen(QColor(70, 70, 70))
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
            return off_x + (xmax - x) * sx

        # spindle centerline (X0)
        if xmin <= 0.0 <= xmax:
            p.setPen(QPen(QColor(120, 120, 120), 1,
                          Qt.PenStyle.DashDotLine))
            p.drawLine(int(margin / 2), int(py(0.0)),
                       int(rect.width() - margin / 2), int(py(0.0)))

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

        # legend + axis hint
        p.setBrush(Qt.BrushStyle.NoBrush)
        y = 16
        for label, (color, width, style) in (("feed", FEED_PEN),
                                             ("rapid", RAPID_PEN)):
            p.setPen(QPen(color, width, style))
            p.drawLine(10, y - 4, 40, y - 4)
            p.setPen(QColor(200, 200, 200))
            p.drawText(46, y, label)
            y += 16
        p.setPen(QColor(140, 140, 140))
        p.drawText(rect.width() - 60, rect.height() - 8, "+Z →")
        p.drawText(10, rect.height() - 8, "X↑ (radius)")
