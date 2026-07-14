"""Generic operation parameter dialog: SVG diagram on the left, grouped
form on the right — the layout of the original ext_thread prototype."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QSpinBox, QVBoxLayout)

from grbl_turn import resource
from grbl_turn.config import load_op_params, save_op_params, settings
from grbl_turn.machine import MachineProfile
from grbl_turn.ops.base import Field, Operation
from grbl_turn.ui.run_dialog import RunDialog
from grbl_turn.units import Units


class OpDialog(QDialog):
    def __init__(self, op: Operation, controller, machine: MachineProfile,
                 parent=None):
        super().__init__(parent)
        self.op = op
        self.controller = controller
        self.machine = machine
        self.setWindowTitle(op.title)
        self.widgets: dict[str, object] = {}

        diagram = QSvgWidget(resource(op.diagram))
        diagram.renderer().setAspectRatioMode(Qt.KeepAspectRatio)
        diagram.setMinimumSize(320, 320)

        # unit selector
        self.units_combo = QComboBox()
        self.units_combo.addItems([u.value for u in Units])
        last_units = str(settings().value("units", Units.INCH.value))
        self.units_combo.setCurrentText(last_units)

        top = QHBoxLayout()
        top.addWidget(QLabel("Units:"))
        top.addWidget(self.units_combo)
        top.addStretch(1)
        convention = QLabel("X0 = centerline   Z0 = face   Z− into work")
        top.addWidget(convention)

        # build grouped form
        groups: dict[str, QFormLayout] = {}
        form_col = QVBoxLayout()
        saved = load_op_params(op.key)
        for f in op.fields:
            if f.group not in groups:
                box = QGroupBox(f.group or "Parameters")
                groups[f.group] = QFormLayout(box)
                form_col.addWidget(box)
            widget = self._make_widget(f, saved.get(f.name))
            self.widgets[f.name] = widget
            groups[f.group].addRow(f.label, widget)

        generate = QPushButton("Generate G-code…")
        generate.setObjectName("run")
        generate.clicked.connect(self.on_generate)
        form_col.addStretch(1)
        form_col.addWidget(generate)

        body = QHBoxLayout()
        body.addWidget(diagram, 1)
        body.addLayout(form_col, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addLayout(body)

    def _make_widget(self, f: Field, saved):
        if f.kind == "bool":
            w = QCheckBox()
            w.setChecked(saved in ("true", "True", True)
                         if saved is not None else bool(f.default))
        elif f.kind == "choice":
            w = QComboBox()
            w.addItems(f.choices)
            w.setCurrentText(str(saved) if saved is not None else str(f.default))
        elif f.kind in ("int", "rpm"):
            w = QSpinBox()
            w.setRange(int(f.minimum), int(f.maximum))
            w.setValue(int(saved) if saved is not None else int(f.default))
        else:  # dia, len, zpos, feed, angle -> float line edit
            w = QLineEdit()
            validator = QDoubleValidator(f.minimum, f.maximum, 4, w)
            validator.setNotation(QDoubleValidator.StandardNotation)
            w.setValidator(validator)
            w.setAlignment(Qt.AlignRight)
            w.setText(str(saved) if saved is not None else str(f.default))
        if f.tooltip:
            w.setToolTip(f.tooltip)
        return w

    def collect_params(self) -> dict:
        params = {}
        for f in self.op.fields:
            w = self.widgets[f.name]
            if f.kind == "bool":
                params[f.name] = w.isChecked()
            elif f.kind == "choice":
                params[f.name] = w.currentText()
            elif f.kind in ("int", "rpm"):
                params[f.name] = w.value()
            else:
                text = w.text().strip()
                if not text:
                    raise ValueError(f"'{f.label}' is empty")
                params[f.name] = float(text)
        return params

    def on_generate(self) -> None:
        units = Units(self.units_combo.currentText())
        try:
            params = self.collect_params()
            lines = self.op.generate(params, self.machine, units)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid parameters", str(exc))
            return
        save_op_params(self.op.key, params)
        settings().setValue("units", units.value)
        RunDialog(self.op, lines, self.controller, self).exec()
