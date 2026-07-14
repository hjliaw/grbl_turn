"""Persistent settings (last connection, last-used parameters per op)."""

from PySide6.QtCore import QSettings


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
