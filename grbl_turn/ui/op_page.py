"""Operation parameter page: SVG diagram on the left, grouped form on the
right. Shown inside the main-window stack (single-window UI, sized for
small screens) instead of a popup dialog."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QScrollArea, QScroller, QSpinBox, QVBoxLayout,
                               QWidget)

from grbl_turn import resource
from grbl_turn.config import load_op_params, save_op_params
from grbl_turn.machine import MachineProfile
from grbl_turn.ops.base import DIMENSIONAL_KINDS, Field, Operation
from grbl_turn.ui.numpad import TouchNumberEdit
from grbl_turn.units import MM_PER_INCH, Units


class OpPage(QWidget):
    back_requested = Signal()
    run_requested = Signal(list)     # generated G-code lines

    def __init__(self, op: Operation, machine: MachineProfile, units: Units,
                 parent=None):
        super().__init__(parent)
        self.op = op
        self.machine = machine
        self.units = units
        self.widgets: dict[str, object] = {}

        back = QPushButton("◀ Back")
        back.clicked.connect(self.back_requested)
        title = QLabel(f"<b>{op.title}</b>")
        top = QHBoxLayout()
        top.addWidget(back)
        top.addSpacing(12)
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(QLabel(f"Units: {units.value}    "
                             "X0 = centerline   Z0 = face   Z− into work"))

        diagram = QSvgWidget(resource(op.diagram))
        diagram.renderer().setAspectRatioMode(Qt.KeepAspectRatio)
        diagram.setMinimumSize(240, 240)

        # build grouped form
        groups: dict[str, QFormLayout] = {}
        form_host = QWidget()
        form_col = QVBoxLayout(form_host)
        saved = load_op_params(op.key)
        for f in op.fields:
            if f.group not in groups:
                box = QGroupBox(f.group or "Parameters")
                groups[f.group] = QFormLayout(box)
                form_col.addWidget(box)
            widget = self._make_widget(f, saved.get(f.name))
            self.widgets[f.name] = widget
            groups[f.group].addRow(self._label(f), widget)

        form_col.addStretch(1)

        # scroll the form so tall operations still fit a 7" screen;
        # finger-drag scrolling for the touch screen
        scroll = QScrollArea()
        scroll.setWidget(form_host)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        QScroller.grabGesture(scroll.viewport(),
                              QScroller.ScrollerGestureType.LeftMouseButtonGesture)

        body = QHBoxLayout()
        body.addWidget(diagram, 2)
        body.addWidget(scroll, 3)   # the form needs the width on 800px

        # Generate lives outside the scroll area: always visible
        generate = QPushButton("Generate G-code…")
        generate.setObjectName("run")
        generate.clicked.connect(self.on_generate)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)
        layout.addLayout(top)
        layout.addLayout(body, 1)
        layout.addWidget(generate)

    def _label(self, f: Field) -> str:
        unit = "in" if self.units is Units.INCH else "mm"
        if f.kind in ("dia", "len", "zpos"):
            return f"{f.label} [{unit}]"
        if f.kind == "feed":
            return f"{f.label} [{unit}/min]"
        if f.kind == "pitch" and self.units is Units.MM:
            return f"{f.label} [mm/rev]"
        return f.label

    def _float_default(self, f: Field) -> float:
        """Field defaults are written in inches; adapt them to mm mode."""
        if self.units is Units.MM:
            if f.kind == "pitch":
                return f.default_mm if f.default_mm is not None else f.default
            if f.kind in DIMENSIONAL_KINDS:
                return round(f.default * MM_PER_INCH, 6)
        return f.default

    def _make_widget(self, f: Field, saved):
        if f.kind == "bool":
            w = QCheckBox()
            w.setChecked(saved in ("true", "True", True)
                         if saved is not None else bool(f.default))
        elif f.kind == "pitch_mode":
            w = QComboBox()
            if self.units is Units.INCH:
                w.addItems(f.choices)
                if saved is not None:
                    w.setCurrentText(str(saved))   # no-op if saved was mm/rev
            else:
                w.addItem("mm/rev")
                w.setEnabled(False)
        elif f.kind == "choice":
            w = QComboBox()
            w.addItems(f.choices)
            w.setCurrentText(str(saved) if saved is not None else str(f.default))
        elif f.kind in ("int", "rpm"):
            w = QSpinBox()
            w.setRange(int(f.minimum), int(f.maximum))
            w.setValue(int(saved) if saved is not None else int(f.default))
        else:  # dia, len, zpos, feed, angle, pitch -> numpad-backed edit
            w = TouchNumberEdit(self._label(f))
            validator = QDoubleValidator(f.minimum, f.maximum, 4, w)
            validator.setNotation(QDoubleValidator.StandardNotation)
            w.setValidator(validator)
            w.setAlignment(Qt.AlignRight)
            w.setText(str(saved) if saved is not None
                      else str(self._float_default(f)))
        if f.tooltip:
            w.setToolTip(f.tooltip)
        return w

    def collect_params(self) -> dict:
        params = {}
        for f in self.op.fields:
            w = self.widgets[f.name]
            if f.kind == "bool":
                params[f.name] = w.isChecked()
            elif f.kind in ("choice", "pitch_mode"):
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
        try:
            params = self.collect_params()
            lines = self.op.generate(params, self.machine, self.units)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid parameters", str(exc))
            return
        to_save = dict(params)
        if self.units is Units.MM:
            # keep the inch-mode pitch type (TPI/custom); mm mode shows a
            # fixed "mm/rev" placeholder that must not overwrite it
            for f in self.op.fields:
                if f.kind == "pitch_mode":
                    to_save.pop(f.name, None)
        save_op_params(self.op.key, to_save)
        self.run_requested.emit(lines)
