"""Single-point threading, external and internal.

Requires spindle-synchronized motion in the firmware (spindle encoder).
Two emitters, selected by the machine profile:
  - G76 canned cycle (grblHAL / LinuxCNC-style words)
  - explicit G33 passes computed by the app (fallback; also useful to read
    to see exactly what G76 will do)

Both use the same degressive infeed math from passes.thread_infeeds().
"""

from grbl_turn.gcode import Program
from grbl_turn.machine import MachineProfile
from grbl_turn.ops.base import Field, Operation
from grbl_turn.ops.passes import flank_offset, thread_infeeds
from grbl_turn.units import Units, fmt

# thread depth as a fraction of pitch for 60 deg threads (UN/ISO shop values)
EXT_DEPTH_FACTOR = 0.6134
INT_DEPTH_FACTOR = 0.5413


def _fields(internal: bool) -> list[Field]:
    return [
        Field("pitch_val", "Pitch (P)", "pitch", 20.0, group="Z (bed/leadscrew)",
              default_mm=1.5,
              tooltip="Inch mode: TPI; mm mode: mm/rev"),
        Field("length", "Thread length (Z)", "len", 0.500,
              group="Z (bed/leadscrew)"),
        Field("lead_in", "Lead-in", "len", 0.0,
              group="Z (bed/leadscrew)", minimum=0.0,
              tooltip="Sync-up distance in front of the face; auto = 2x pitch",
              auto=lambda p, u: 2.0 * _pitch(p, u)),
        Field("total_depth", "Total depth (K)", "len", 0.0,
              group="X (cross-slide)", minimum=0.0,
              tooltip="Radial thread depth; auto = 0.6134x pitch (ext) or "
                      "0.5413x pitch (int) for 60 deg threads",
              auto=lambda p, u: _pitch(p, u) * (INT_DEPTH_FACTOR if internal
                                                else EXT_DEPTH_FACTOR)),
        Field("first_depth", "First pass depth (J)", "len", 0.003,
              group="X (cross-slide)"),
        Field("degression", "Depth degression (R)", "ratio", 1.5,
              group="X (cross-slide)", minimum=1.0, maximum=2.0,
              tooltip="G76 R word: 1.0 = same depth every pass, "
                      "2.0 = constant chip area (passes taper off)"),
        Field("clearance", "Clearance (I)", "len", 0.020,
              group="X (cross-slide)",
              tooltip="Radial gap between the tool and the crest at the "
                      "start of the program"),
        Field("spring", "Spring passes (H)", "int", 1, group="Cutting",
              minimum=0, maximum=9),
        Field("compound", "Compound angle (Q)", "choice", "29.5", group="Cutting",
              choices=["0", "29.5", "30"], unit="deg"),
    ]


def _pitch(p: dict, units: Units) -> float:
    if p["pitch_val"] <= 0:
        raise ValueError("pitch must be positive")
    if units is Units.MM:
        return p["pitch_val"]           # mm/rev
    return 1.0 / p["pitch_val"]         # inch mode: TPI


def _generate(p: dict, machine: MachineProfile, units: Units,
              internal: bool) -> list[str]:
    pitch = _pitch(p, units)
    depth = p["total_depth"]
    if depth <= 0:
        raise ValueError("total depth must be > 0 — tap its A button "
                         "to auto-calculate from the pitch")
    lead_in = p["lead_in"]   # 0 is honored: sync-up starts at the face
    clear = p["clearance"]
    angle = float(p["compound"])
    inward = -1.0 if internal else 1.0       # retract direction off the thread
    z_end = -p["length"]

    # No absolute X exists here: the thread's diameter is never asked for, so
    # X is measured from wherever the operator parks the tool. External starts
    # on the crest and backs out to the drive line; internal starts on the
    # drive line already, a clearance inside the crest.
    x_drive = 0.0 if internal else clear
    x_peak = clear if internal else 0.0

    title = "Internal threading" if internal else "External threading"
    kind = "mm/rev" if units is Units.MM else "TPI"
    note = (f"with the tool {p['clearance']} clear of the crest at the face"
            if internal else "with the tool touching the crest at the face")
    prog = Program(machine, units, origin_r=None, start_note=note)
    prog.header(
        title,
        [f"pitch {p['pitch_val']:g} {kind}, length {p['length']}",
         f"depth {depth:.4f} radial, first {p['first_depth']}, "
         f"compound {angle:g} deg",
         "REQUIRES spindle sync (encoder); feed hold is DEFERRED during passes"])
    prog.rapid(x=x_drive)        # crest -> drive line (external only)
    prog.rapid(z=lead_in)

    if machine.has_g76:
        # I: thread peak offset from the drive line (negative = external).
        # The Z word is a distance here like every other axis word; I/J/K are
        # magnitudes either way. Where the cycle leaves Z afterwards differs
        # between firmwares, so the program ends on the cycle.
        i_word = -inward * clear
        prog.raw(
            f"G76 P{fmt(pitch, units)} Z{prog.z_delta(z_end, advance=False)} "
            f"I{fmt(i_word, units)} J{fmt(p['first_depth'], units)} "
            f"R{p['degression']:g} K{fmt(depth, units)} "
            f"Q{angle:g} H{int(p['spring'])}")
        return prog.stop("G76 ends on the drive line in X; Z is left wherever "
                         "the firmware puts it - re-touch before re-running")

    for d in thread_infeeds(depth, p["first_depth"], p["degression"],
                            int(p["spring"])):
        prog.rapid(z=lead_in - flank_offset(d, angle))
        prog.rapid(x=x_peak - inward * d)
        prog.raw(f"G33 Z{prog.z_delta(z_end)} K{fmt(pitch, units)}")
        prog.rapid(x=x_drive)
    return prog.end()


def generate_ext(p, machine, units):
    return _generate(p, machine, units, internal=False)


def generate_int(p, machine, units):
    return _generate(p, machine, units, internal=True)


OP_EXT = Operation("ext_thread", "External thread", "ext_thread2.svg",
                   "ext_thread2_dim.svg", _fields(False), generate_ext,
                   is_threading=True)
OP_INT = Operation("int_thread", "Internal thread", "int_thread2.svg",
                   "int_thread2_dim.svg", _fields(True), generate_int,
                   is_threading=True, silhouette="bore")
