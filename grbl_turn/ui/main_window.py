"""Main window: connection bar, DRO/status strip, and the 2x4 operation grid
from the original eznc.ui launcher."""

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QMainWindow,
                               QMessageBox, QPushButton, QToolButton,
                               QVBoxLayout, QWidget)

from grbl_turn import resource
from grbl_turn.comms.grbl import GrblController
from grbl_turn.machine import MachineProfile
from grbl_turn.ops import REGISTRY
from grbl_turn.ui.connect_widgets import ConnectBar
from grbl_turn.ui.op_dialog import OpDialog

GRID_COLS = 4


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("grbl_turn")
        self.controller = GrblController(self)
        self.machine = MachineProfile()

        central = QWidget()
        layout = QVBoxLayout(central)

        self.connect_bar = ConnectBar()
        self.connect_bar.connect_btn.clicked.connect(self.on_connect)
        layout.addWidget(self.connect_bar)

        layout.addLayout(self._build_status_strip())

        grid = QGridLayout()
        grid.setSpacing(4)
        for i, op in enumerate(REGISTRY):
            btn = QToolButton()
            btn.setIcon(QIcon(resource(op.icon)))
            btn.setIconSize(QSize(180, 180))
            btn.setToolTip(op.title)
            btn.setMinimumSize(200, 200)
            btn.clicked.connect(lambda checked=False, o=op: self.open_op(o))
            grid.addWidget(btn, i // GRID_COLS, i % GRID_COLS)
        layout.addLayout(grid, 1)

        self.setCentralWidget(central)

        w = self.controller.signals
        w.connected.connect(self.on_connected)
        w.disconnected.connect(self.on_disconnected)
        w.status.connect(self.on_status)
        w.alarm.connect(self.on_alarm)

    def _build_status_strip(self) -> QHBoxLayout:
        strip = QHBoxLayout()
        self.state_label = QLabel("disconnected")
        self.state_label.setObjectName("state")
        self.x_label = QLabel("X —")
        self.x_label.setObjectName("dro")
        self.z_label = QLabel("Z —")
        self.z_label.setObjectName("dro")
        self.rpm_label = QLabel("S —")
        self.rpm_label.setObjectName("dro")

        self.hold_btn = QPushButton("Hold")
        self.resume_btn = QPushButton("Resume")
        self.reset_btn = QPushButton("Reset")
        self.unlock_btn = QPushButton("Unlock ($X)")
        self.hold_btn.clicked.connect(self.controller.feed_hold)
        self.resume_btn.clicked.connect(self.controller.resume)
        self.reset_btn.clicked.connect(self.controller.soft_reset)
        self.unlock_btn.clicked.connect(self.controller.unlock)
        self._set_conn_ui(False)

        strip.addWidget(self.state_label)
        strip.addSpacing(20)
        strip.addWidget(self.x_label)
        strip.addWidget(self.z_label)
        strip.addWidget(self.rpm_label)
        strip.addStretch(1)
        for b in (self.hold_btn, self.resume_btn, self.reset_btn,
                  self.unlock_btn):
            strip.addWidget(b)
        return strip

    def _set_conn_ui(self, connected: bool) -> None:
        for b in (self.hold_btn, self.resume_btn, self.reset_btn,
                  self.unlock_btn):
            b.setEnabled(connected)

    # -- slots -----------------------------------------------------------------
    def on_connect(self) -> None:
        if self.controller.is_connected:
            self.controller.disconnect_transport()
            return
        try:
            transport = self.connect_bar.make_transport()
        except ValueError as exc:
            QMessageBox.warning(self, "Connection", str(exc))
            return
        self.state_label.setText("connecting…")
        self.controller.connect_transport(transport)

    def on_connected(self, desc: str) -> None:
        self.state_label.setText(f"connected ({desc})")
        self.connect_bar.connect_btn.setText("Disconnect")
        self._set_conn_ui(True)

    def on_disconnected(self, reason: str) -> None:
        self.state_label.setText("disconnected"
                                 + (f" — {reason}" if reason else ""))
        self.connect_bar.connect_btn.setText("Connect")
        self._set_conn_ui(False)
        for label in (self.x_label, self.z_label, self.rpm_label):
            label.setText(label.text().split()[0] + " —")

    def on_status(self, st: dict) -> None:
        self.state_label.setText(st.get("state", "?"))
        pos = st.get("WPos") or st.get("MPos")
        if pos and len(pos) >= 3:
            x_radius = pos[0] / 2.0 if self.machine.x_words_are_diameter \
                else pos[0]
            self.x_label.setText(f"X⌀ {x_radius * 2:.4f}")
            self.z_label.setText(f"Z {pos[2]:.4f}")
        if "rpm" in st:
            self.rpm_label.setText(f"S {st['rpm']:.0f}")

    def on_alarm(self, line: str) -> None:
        self.state_label.setText(line)
        QMessageBox.critical(
            self, "ALARM",
            f"{line}\n\nMotion is locked. Clear the cause, then press "
            "Unlock ($X) or Reset.")

    def open_op(self, op) -> None:
        OpDialog(op, self.controller, self.machine, self).exec()

    def closeEvent(self, event) -> None:
        self.controller.shutdown()
        event.accept()
