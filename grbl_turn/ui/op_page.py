"""Operation parameter page: SVG diagram on the left, grouped form on the
right. Shown inside the main-window stack (single-window UI, sized for
small screens) instead of a popup dialog."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QDoubleValidator, QIcon, QIntValidator
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox,
                               QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QScrollArea,
                               QScroller, QSizePolicy, QVBoxLayout, QWidget)

from grbl_turn import resource
from grbl_turn.config import load_op_params, save_op_params
from grbl_turn.machine import MachineProfile
from grbl_turn.ops.base import DIMENSIONAL_KINDS, Field, Operation
from grbl_turn.ui.numpad import TouchNumberEdit
from grbl_turn.units import MM_PER_INCH, Units

LABEL_COL_W = 240   # uniform columns across the parameter groups
UNIT_COL_W = 56
AUTO_BTN_W = 36


class SegmentedChoice(QWidget):
    """A choice as a row of exclusive checkable buttons — bigger touch
    targets than a combo box. Mirrors the QComboBox API the form code
    uses (currentText/setCurrentText/currentTextChanged)."""
    currentTextChanged = Signal(str)

    def __init__(self, choices: list[str], parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for text in choices:
            btn = QPushButton(text)
            btn.setCheckable(True)
            self._group.addButton(btn)
            row.addWidget(btn, 1)
        self._group.buttonToggled.connect(
            lambda btn, checked:
            checked and self.currentTextChanged.emit(btn.text()))

    def currentText(self) -> str:
        btn = self._group.checkedButton()
        return btn.text() if btn else ""

    def setCurrentText(self, text: str) -> None:
        for btn in self._group.buttons():
            if btn.text() == text:
                btn.setChecked(True)


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
        self._rows: dict[str, list[QWidget]] = {}   # form-row widgets per field
        self._auto_prev: dict[str, str] = {}   # values before "auto" clicks

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
            if f.placement == "left":   # mode selector above the diagram
                widget = self._make_widget(f, saved.get(f.name))
                self.widgets[f.name] = widget
                left.insertWidget(left.count() - 1, widget)
                continue
            if f.group not in groups:
                box = QGroupBox(f.group or "Parameters")
                form = QFormLayout(box)
                form.setFieldGrowthPolicy(
                    QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
                groups[f.group] = form
                form_col.addWidget(box)
            widget = self._make_widget(f, saved.get(f.name))
            self.widgets[f.name] = widget
            label = self._row_label(f.label)
            box = self._with_unit(f, widget)
            groups[f.group].addRow(label, box)
            self._rows[f.name] = [label, box]

        for f in op.fields:   # gray out fields governed by a checked bool
            if f.kind == "bool" and f.disables:
                checkbox = self.widgets[f.name]

                def apply(checked, names=tuple(f.disables)):
                    for name in names:
                        self.widgets[name].setEnabled(not checked)

                checkbox.toggled.connect(apply)
                apply(checkbox.isChecked())

        for f in op.fields:   # rows shown only in one mode of a choice
            if f.visible_when:
                ctrl_name, value = f.visible_when
                ctrl = self.widgets[ctrl_name]

                def apply(current, name=f.name, value=value):
                    for w in self._rows[name]:
                        w.setVisible(current == value)

                ctrl.currentTextChanged.connect(apply)
                apply(ctrl.currentText())

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

        # Generate lives outside the scroll area: always visible,
        # at the bottom of the diagram column so the form gets full height
        generate = QPushButton("G-code")
        generate.setObjectName("run")
        generate.clicked.connect(self.on_generate)
        left.addWidget(generate)

        right = QVBoxLayout()
        right.addWidget(scroll, 1)

        body = QHBoxLayout()
        body.addLayout(left, 1)
        body.addLayout(right, 2)   # the form needs the width on 800px

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)
        layout.addLayout(body, 1)

    def _row_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setMinimumWidth(LABEL_COL_W)
        label.setAlignment(Qt.AlignmentFlag.AlignRight
                           | Qt.AlignmentFlag.AlignVCenter)
        return label

    def _preset_combo(self, f: Field, widget) -> QComboBox:
        """Dropdown beside the input that fills in a named preset value;
        picking a name writes its exact value into the input, and editing
        the input to anything else flips the dropdown to 'Custom'."""
        combo = QComboBox()
        combo.addItems(f.presets.keys())
        combo.addItem("Custom")
        # the style sizes the box to its widest item, arrow included —
        # hand-computed widths clip on the macOS combo bezel
        combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)

        def apply(name: str) -> None:
            if name in f.presets:
                widget.setText(self._fmt_value(f.presets[name]))

        def follow(text: str) -> None:
            name = combo.currentText()
            if name in f.presets and text != self._fmt_value(f.presets[name]):
                combo.setCurrentText("Custom")

        combo.currentTextChanged.connect(apply)
        widget.textChanged.connect(follow)
        combo.setCurrentText("Custom")
        for name, value in f.presets.items():   # recognize a saved preset
            if widget.text() == self._fmt_value(value):
                combo.setCurrentText(name)
                break
        return combo

    def _unit_suffix(self, f: Field) -> str:
        if f.unit:
            return f.unit
        unit = "in" if self.units is Units.INCH else "mm"
        if f.kind in ("dia", "len", "zpos"):
            return unit
        if f.kind == "feed":
            return f"{unit}/min"
        if f.kind == "pitch":
            return "TPI" if self.units is Units.INCH else "mm"
        if f.kind == "angle":
            return "deg"
        return ""

    def _with_unit(self, f: Field, widget) -> QWidget:
        """The input widget flanked by a preset dropdown / auto button
        (or placeholder) on the left and its unit text (or placeholder)
        on the right, so every input spans the same column."""
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)   # macOS varies spacing by widget type otherwise
        if f.presets:
            row.addWidget(self._preset_combo(f, widget))
        elif f.auto is not None:
            btn = QPushButton("A")
            btn.setFixedWidth(AUTO_BTN_W)
            btn.setToolTip("Calculate from the other parameters")
            btn.clicked.connect(
                lambda checked=False, f=f, w=widget, b=btn:
                self.on_auto(f, w, b))
            row.addWidget(btn)
        else:
            pad = QWidget()   # placeholder: keeps the input column aligned
            pad.setFixedWidth(AUTO_BTN_W)
            row.addWidget(pad)
        row.addWidget(widget, 1)
        unit = QLabel(self._unit_suffix(f))
        unit.setMinimumWidth(UNIT_COL_W)
        row.addWidget(unit)
        return box

    def on_auto(self, f: Field, widget, btn: QPushButton) -> None:
        if btn.text() == "A":
            try:
                value = f.auto(self.collect_params(), self.units)
            except ValueError as exc:
                QMessageBox.warning(self, "Auto value", str(exc))
                return
            self._auto_prev[f.name] = widget.text()
            widget.setText(self._fmt_value(value))
            btn.setText("R")
            btn.setToolTip("Restore the previous value")
        else:
            widget.setText(self._auto_prev.get(f.name, "0.0"))
            btn.setText("A")
            btn.setToolTip("Calculate from the other parameters")

    def _fmt_value(self, value: float) -> str:
        """Short numbers stay as-is; long tails are rounded to the G-code
        precision (3 decimals in mm mode, 4 in inch mode)."""
        return f"{round(value, self.units.decimals):g}"

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
            if f.placement == "left":
                w = SegmentedChoice(f.choices)
            else:
                w = QComboBox()
                w.addItems(f.choices)
                w.setSizePolicy(QSizePolicy.Policy.Expanding,
                                QSizePolicy.Policy.Fixed)
            if saved is not None and str(saved) in f.choices:
                w.setCurrentText(str(saved))
            else:
                w.setCurrentText(str(f.default))
        elif f.kind in ("int", "rpm"):
            w = TouchNumberEdit(f.label, integer=True)
            w.setValidator(QIntValidator(int(f.minimum), int(f.maximum), w))
            w.setAlignment(Qt.AlignRight)
            w.setText(str(int(saved) if saved is not None
                          else int(f.default)))
        else:  # dia, len, zpos, feed, angle, pitch -> numpad-backed edit
            w = TouchNumberEdit(f.label)
            validator = QDoubleValidator(f.minimum, f.maximum, 4, w)
            validator.setNotation(QDoubleValidator.StandardNotation)
            w.setValidator(validator)
            w.setAlignment(Qt.AlignRight)
            try:
                value = float(saved) if saved is not None \
                    else self._float_default(f)
                w.setText(self._fmt_value(value))
            except (TypeError, ValueError):
                w.setText(str(saved))
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
                try:
                    params[f.name] = int(w.text().strip())
                except ValueError:
                    raise ValueError(f"'{f.label}' must be a whole number")
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
        warns = [l.strip("()") for l in lines if l.startswith("(WARNING")]
        if warns:
            QMessageBox.warning(self, "Check parameters", "\n\n".join(warns))
        save_op_params(self.op.key, params)
        self.run_requested.emit(lines)
