"""G-code program assembly and analysis.

Programs are relative (G91): every move is emitted as a delta from the one
before it, so nothing depends on the machine's work offsets. The operator
parks the tool on the reference surface at the face -- the ORIGIN comment
in the header names it -- and runs. Programs return to that start position
when they end, so one can be run again without re-touching.

The operations still do their own math in absolute coordinates:
  X0 = spindle centerline, Z0 = part face, Z negative into the work.
Program turns those targets into deltas on the way out, tracking the
position it has actually commanded (each delta as rounded for output) so
rounding cannot accumulate across a long list of passes.

G18 (XZ plane), G91 (incremental), G94 (units/min feed).
"""

import re
from datetime import date

from grbl_turn.machine import MachineProfile
from grbl_turn.units import Units, fmt


def _comment(text: str) -> str:
    """GRBL rejects nested parentheses inside a comment."""
    return "(" + text.replace("(", "[").replace(")", "]") + ")"


class Program:
    """Assembles a relative-mode program from absolute coordinates."""

    def __init__(self, machine: MachineProfile, units: Units,
                 origin_r: float | None = None, origin_z: float = 0.0,
                 start_note: str = "touch off here, then run"):
        """origin_r is the radius of the surface the operator touches off
        on. None means the program has no absolute X reference at all --
        threading works off the thread crest, whose diameter it is never
        told -- and the op's own X targets are then radial distances from
        wherever the tool starts."""
        self.machine = machine
        self.units = units
        self.origin_r = 0.0 if origin_r is None else origin_r
        self.origin_z = origin_z
        self.absolute_x = origin_r is not None
        self.start_note = start_note
        self._x = machine.x_word(self.origin_r)   # commanded X, word space
        self._z = origin_z
        self.lines: list[str] = []

    # -- assembly --------------------------------------------------------
    def header(self, title: str, param_desc: list[str]) -> "Program":
        self.lines.append(
            _comment(f"{title} - grbl_turn {date.today().isoformat()}"))
        self.lines += [_comment(d) for d in param_desc]
        if self.absolute_x:
            # machine-readable: the preview reads it back to redraw the
            # program in absolute coordinates
            where = (f"ORIGIN X{fmt(self._x, self.units)} "
                     f"Z{fmt(self._z, self.units)} - {self.start_note}")
        else:
            where = f"START {self.start_note}"
        self.lines.append(_comment(f"{where}; every move is relative"))
        self.lines.append(f"{self.units.gcode} G18 G91 G94")
        return self

    def rapid(self, x: float | None = None, z: float | None = None):
        return self._move("G0", x, z)

    def feed(self, x: float | None = None, z: float | None = None,
             f: float = 0.0):
        return self._move("G1", x, z, f)

    def raw(self, line: str) -> "Program":
        """A line the emitter cannot model, e.g. a G76 canned cycle."""
        self.lines.append(line)
        return self

    def comment(self, text: str) -> "Program":
        self.lines.append(_comment(text))
        return self

    def z_delta(self, z: float, advance: bool = True) -> str:
        """The Z word that reaches absolute `z` from here, for a line this
        class does not build itself. advance=False when the move's end
        position is not knowable, after which nothing more may be emitted."""
        word = fmt(z - self._z, self.units)
        if advance:
            self._z += float(word)
        return word

    def end(self) -> list[str]:
        """Return to the start position and stop. Z comes back first, while
        X is still clear of the work, then X comes in to the origin surface.
        Leaves the tool where it began, so the program can be run again."""
        self.rapid(z=self.origin_z)
        self.rapid(x=self.origin_r)
        self.lines.append("M2")
        return self.lines

    def stop(self, note: str = "") -> list[str]:
        """Stop where we are, for programs that cannot know their end
        position (a G76 cycle leaves Z wherever the firmware chooses)."""
        if note:
            self.comment(note)
        self.lines.append("M2")
        return self.lines

    # -- emission --------------------------------------------------------
    def _move(self, code: str, x: float | None, z: float | None,
              feed: float | None = None) -> "Program":
        words = []
        if x is not None:
            # format first, then track what was formatted: the commanded
            # position stays exactly what the machine will have executed
            word = fmt(self.machine.x_word(x) - self._x, self.units)
            if float(word):
                words.append(f"X{word}")
                self._x += float(word)
        if z is not None:
            word = fmt(z - self._z, self.units)
            if float(word):
                words.append(f"Z{word}")
                self._z += float(word)
        if not words:            # already there: nothing to command
            return self
        if feed is not None:
            words.append(f"F{feed:g}")
        self.lines.append(" ".join([code] + words))
        return self


_WORD = re.compile(r"([XZ])(-?\d+\.?\d*)")
ORIGIN_RE = re.compile(r"\(ORIGIN X(-?[\d.]+) Z(-?[\d.]+)")


def origin(lines: list[str]) -> tuple[float, float] | None:
    """The (x, z) the program's ORIGIN comment names, or None when it has
    no absolute reference."""
    for line in lines:
        m = ORIGIN_RE.search(line)
        if m:
            return float(m.group(1)), float(m.group(2))
    return None


def positions(lines: list[str]) -> list[tuple[str, float, float]]:
    """Walk the program, resolving G90/G91 from the ORIGIN comment: one
    (line, x, z) per line carrying an axis word, holding the absolute
    position it leaves the tool at. Motion inside a G76 cycle is invisible
    here -- its depth lives in I/J/K words, not axis words."""
    start = origin(lines)
    pos = {"X": start[0], "Z": start[1]} if start else {"X": 0.0, "Z": 0.0}
    out: list[tuple[str, float, float]] = []
    incremental = False
    for line in lines:
        text = re.sub(r"\(.*?\)", "", line)
        if "G90" in text:
            incremental = False
        if "G91" in text:
            incremental = True
        words = _WORD.findall(text)
        if not words:
            continue
        for axis, num in words:
            value = float(num)
            pos[axis] = pos[axis] + value if incremental else value
        out.append((line, pos["X"], pos["Z"]))
    return out


def extents(lines: list[str]) -> dict[str, tuple[float, float]]:
    """Min/max of the positions the program's axis words reach."""
    start = origin(lines)
    seed = (start[0], start[1]) if start else (0.0, 0.0)
    xs = [seed[0]] + [x for _, x, _ in positions(lines)]
    zs = [seed[1]] + [z for _, _, z in positions(lines)]
    return {"X": (min(xs), max(xs)), "Z": (min(zs), max(zs))}
