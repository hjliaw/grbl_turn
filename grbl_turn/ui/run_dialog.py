"""Preview + run dialog: shows the generated program and its travel extents,
requires an explicit confirmation, then streams with progress and a console."""

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel,
                               QPlainTextEdit, QProgressBar, QPushButton,
                               QVBoxLayout)

from grbl_turn.gcode import extents
from grbl_turn.ops.base import Operation


class RunDialog(QDialog):
    def __init__(self, op: Operation, lines: list[str], controller,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{op.title} — preview & run")
        self.resize(700, 640)
        self.controller = controller
        self.lines = lines

        preview = QPlainTextEdit("\n".join(lines))
        preview.setReadOnly(True)
        preview.setFont(QFont("Courier New", 12))

        ext = extents(lines)
        parts = []
        if "X" in ext:
            parts.append(f"X {ext['X'][0]:g} … {ext['X'][1]:g}")
        if "Z" in ext:
            parts.append(f"Z {ext['Z'][0]:g} … {ext['Z'][1]:g}")
        extent_label = QLabel("Travel extents:   " + "      ".join(parts))
        extent_label.setObjectName("dro")

        layout = QVBoxLayout(self)
        layout.addWidget(preview, 2)
        layout.addWidget(extent_label)

        if op.is_threading:
            warn = QLabel(
                "⚠ THREADING: feed hold is DEFERRED during spindle-synced "
                "passes —\nthe pass finishes before motion stops. Use the "
                "machine E-stop for emergencies.")
            warn.setObjectName("warning")
            layout.addWidget(warn)

        self.confirm = QCheckBox(
            "I checked tool clearance, spindle direction, and the travel "
            "extents above")
        layout.addWidget(self.confirm)

        self.run_btn = QPushButton("Run")
        self.run_btn.setObjectName("run")
        self.run_btn.setEnabled(False)
        self.hold_btn = QPushButton("Hold")
        self.resume_btn = QPushButton("Resume")
        self.stop_btn = QPushButton("STOP (soft reset — not an E-stop)")
        self.stop_btn.setObjectName("stop")
        save_btn = QPushButton("Save .nc…")
        for b in (self.hold_btn, self.resume_btn, self.stop_btn):
            b.setEnabled(False)

        buttons = QHBoxLayout()
        buttons.addWidget(self.run_btn)
        buttons.addWidget(self.hold_btn)
        buttons.addWidget(self.resume_btn)
        buttons.addWidget(self.stop_btn)
        buttons.addStretch(1)
        buttons.addWidget(save_btn)
        layout.addLayout(buttons)

        self.progress = QProgressBar()
        self.progress.setRange(0, len(lines))
        layout.addWidget(self.progress)

        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Courier New", 11))
        self.console.setMaximumHeight(140)
        layout.addWidget(self.console, 1)

        self.status_label = QLabel(
            "" if controller.is_connected
            else "Not connected — connect in the main window to run")
        layout.addWidget(self.status_label)

        self.confirm.toggled.connect(self._update_buttons)
        self.run_btn.clicked.connect(self.on_run)
        self.hold_btn.clicked.connect(controller.feed_hold)
        self.resume_btn.clicked.connect(controller.resume)
        self.stop_btn.clicked.connect(controller.soft_reset)
        save_btn.clicked.connect(self.on_save)

        w = controller.signals
        w.progress.connect(self.on_progress)
        w.stream_finished.connect(self.on_finished)
        w.comm_log.connect(self.on_log)

        self._update_buttons()

    def _update_buttons(self) -> None:
        ready = (self.controller.is_connected and self.confirm.isChecked()
                 and not self.controller.is_streaming)
        self.run_btn.setEnabled(ready)

    def on_run(self) -> None:
        self.run_btn.setEnabled(False)
        for b in (self.hold_btn, self.resume_btn, self.stop_btn):
            b.setEnabled(True)
        self.status_label.setText("running…")
        self.controller.stream(self.lines)
        self.progress.setRange(0, max(1, len([l for l in self.lines
                                              if l.strip()])))
        self.progress.setValue(0)

    def on_progress(self, done: int, total: int) -> None:
        self.progress.setRange(0, total)
        self.progress.setValue(done)

    def on_finished(self, ok: bool, msg: str) -> None:
        self.status_label.setText(msg)
        for b in (self.hold_btn, self.resume_btn, self.stop_btn):
            b.setEnabled(False)
        self._update_buttons()

    def on_log(self, direction: str, text: str) -> None:
        self.console.appendPlainText(f"{direction} {text}")

    def on_save(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Save G-code", f"{self.windowTitle().split(' —')[0]}.nc",
            "G-code (*.nc *.gcode);;All files (*)")
        if path:
            with open(path, "w") as f:
                f.write("\n".join(self.lines) + "\n")
            self.status_label.setText(f"saved to {path}")
