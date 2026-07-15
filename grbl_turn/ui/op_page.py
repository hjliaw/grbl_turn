"""Operation parameter page: SVG diagram on the left, grouped form on the
right. Shown inside the main-window stack (single-window UI, sized for
small screens) instead of a popup dialog."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QDoubleValidator, QIcon
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QScrollArea, QScroller, QSizePolicy, QSpinBox,
                               QVBoxLayout, QWidget)

from grbl_turn import resource
from grbl_turn.config import load_op_params, save_op_params
from grbl_turn.machine import MachineProfile
from grbl_turn.ops.base import DIMENSIONAL_KINDS, Field, Operation
from grbl_turn.ui.numpad import TouchNumberEdit
from grbl_turn.units import MM_PER_INCH, Units

LABEL_COL_W = 240   # uniform columns across the parameter groups
UNIT_COL_W = 56


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

        back = QPushButton(QIcon(resource("arrow-left.svg")), "")
        back.setObjectName("back")
        back.setIconSize(QSize(28, 28))
        back.setToolTip("Back")
        back.clicked.connect(self.back_requested)

        title = QLabel(f"<b>{op.title}</b>")

        diagram = QSvgWidget(resource(op.diagram))
        diagram.renderer().setAspectRatioMode(Qt.KeepAspectRatio)
        diagram.setMinimumSize(240, 240)

        head = QHBoxLayout()
        head.addWidget(back)
        head.addSpacing(12)
        head.addWidget(title)
        head.addStretch(1)

        left = QVBoxLayout()
        left.addLayout(head)
        left.addWidget(diagram, 1)

        # build grouped form; fixed label/unit columns keep every group's
        # input widgets aligned in one column
        groups: dict[str, QFormLayout] = {}
        form_host = QWidget()
        form_col = QVBoxLayout(form_host)
        saved = load_op_params(op.key)
        for f in op.fields:
            if f.group not in groups:
                box = QGroupBox(f.group or "Parameters")
                form = QFormLayout(box)
                form.setFieldGrowthPolicy(
                    QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
                groups[f.group] = form
                form_col.addWidget(box)
            widget = self._make_widget(f, saved.get(f.name))
            self.widgets[f.name] = widget
            label = QLabel(f.label)
            label.setMinimumWidth(LABEL_COL_W)
            label.setAlignment(Qt.AlignmentFlag.AlignRight
                               | Qt.AlignmentFlag.AlignVCenter)
            groups[f.group].addRow(label, self._with_unit(f, widget))

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

        # Generate lives outside the scroll area: always visible
        generate = QPushButton("G-code")
        generate.setObjectName("run")
        generate.clicked.connect(self.on_generate)

        right = QVBoxLayout()
        right.addWidget(scroll, 1)
        right.addWidget(generate)

        body = QHBoxLayout()
        body.addLayout(left, 2)
        body.addLayout(right, 3)   # the form needs the width on 800px

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)
        layout.addLayout(body, 1)

        # units badge floating in the top-right corner (takes no form height)
        self.unit_label = QLabel(units.value, self)
        self.unit_label.setStyleSheet(
            "color: rgb(180, 200, 180); background: transparent;")
        self.unit_label.adjustSize()
        self.unit_label.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # clear the form's right margin and scrollbar
        self.unit_label.move(self.width() - self.unit_label.width() - 34, 6)

    def _unit_suffix(self, f: Field) -> str:
        if f.unit:
            return f.unit
        unit = "in" if self.units is Units.INCH else "mm"
        if f.kind in ("dia", "len", "zpos"):
            return unit
        if f.kind == "feed":
            return f"{unit}/min"
        if f.kind == "pitch":
            return "TPI" if self.units is Units.INCH else "mm/rev"
        if f.kind == "angle":
            return "deg"
        return ""

    def _with_unit(self, f: Field, widget) -> QWidget:
        """The input widget with its unit text to the right. Unit-less rows
        get an empty placeholder so every input spans the same column."""
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(widget, 1)
        unit = QLabel(self._unit_suffix(f))
        unit.setMinimumWidth(UNIT_COL_W)
        row.addWidget(unit)
        return box

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
        elif f.kind == "choice":
            w = QComboBox()
            w.addItems(f.choices)
            w.setCurrentText(str(saved) if saved is not None else str(f.default))
            w.setSizePolicy(QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Fixed)
        elif f.kind in ("int", "rpm"):
            w = QSpinBox()
            w.setRange(int(f.minimum), int(f.maximum))
            w.setValue(int(saved) if saved is not None else int(f.default))
            w.setSizePolicy(QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Fixed)
        else:  # dia, len, zpos, feed, angle, pitch -> numpad-backed edit
            w = TouchNumberEdit(f.label)
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
        try:
            params = self.collect_params()
            lines = self.op.generate(params, self.machine, self.units)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid parameters", str(exc))
            return
        save_op_params(self.op.key, params)
        self.run_requested.emit(lines)
