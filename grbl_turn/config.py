"""Persistent settings (last connection, last-used parameters per op)."""

from PySide6.QtCore import QSettings

from grbl_turn.units import MM_PER_INCH, Units


def settings() -> QSettings:
    return QSettings("grbl_turn", "grbl_turn")


def save_op_params(op_key: str, values: dict) -> None:
    s = settings()
    s.beginGroup(f"ops/{op_key}")
    for name, value in values.items():
        s.setValue(name, value)
    s.endGroup()


def load_op_params(op_key: str) -> dict:
    s = settings()
    s.beginGroup(f"ops/{op_key}")
    values = {name: s.value(name) for name in s.childKeys()}
    s.endGroup()
    return values


def convert_saved_params(old: Units, new: Units) -> None:
    """Convert every op's saved length-type parameters between unit systems.
    Thread pitch (kind "pitch") is deliberately left alone — it is re-entered
    as TPI/in per rev in inch mode or mm per rev in mm mode."""
    if old is new:
        return
    from grbl_turn.ops import REGISTRY
    from grbl_turn.ops.base import DIMENSIONAL_KINDS
    factor = MM_PER_INCH if new is Units.MM else 1.0 / MM_PER_INCH
    for op in REGISTRY:
        saved = load_op_params(op.key)
        converted = {}
        for f in op.fields:
            if f.kind in DIMENSIONAL_KINDS and f.name in saved:
                try:
                    value = float(saved[f.name])
                except (TypeError, ValueError):
                    continue
                converted[f.name] = round(value * factor, 6)
        if converted:
            save_op_params(op.key, converted)
