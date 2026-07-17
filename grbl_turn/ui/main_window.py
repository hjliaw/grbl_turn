"""Main window: DRO/status strip and a page stack — the 2x4 operation
grid, the device (connection + machine control) page, parameter pages,
and the run page all redraw in the same window (no popups; sized to
work on a 7" screen)."""

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QMainWindow, QMessageBox, QPushButton,
                               QSizePolicy, QStackedWidget, QToolButton,
                               QVBoxLayout, QWidget)

from grbl_turn import resource
from grbl_turn.comms.grbl import GrblController
from grbl_turn.config import convert_saved_params, settings
from grbl_turn.machine import MachineProfile
from grbl_turn.ops import REGISTRY
from grbl_turn.ui.connect_widgets import ConnectBar
from grbl_turn.ui.widgets import TouchCombo
from grbl_turn.ui.op_page import OpPage
from grbl_turn.ui.run_page import RunPage
from grbl_turn.units import Units, convert

GRID_COLS = 4

STATE_COLORS = {"Idle": "rgb(120, 220, 120)", "Run": "rgb(120, 200, 255)",
                "Jog": "rgb(120, 200, 255)", "Home": "rgb(120, 200, 255)",
                "Hold": "rgb(255, 200, 60)", "Door": "rgb(255, 200, 60)",
                "Alarm": "rgb(255, 90, 90)"}
NEUTRAL = "rgb(200, 200, 200)"


class OpButton(QToolButton):
    """The op SVGs carry their own whitespace, so the icon fills the button."""

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.setIconSize(event.size())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("grbl_turn")
        self.controller = GrblController(self)
        self.machine = MachineProfile()
        self.units = Units(str(settings().value("units", Units.INCH.value)))
        self.report_units = Units.MM   # GRBL $13 default; queried on connect
        self._sim_active = False       # toolpath sim owns the X/Z readouts

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        self.status_strip = self._build_status_strip()
        layout.addWidget(self.status_strip)

        home = QWidget()
        grid = QGridLayout(home)
        grid.setSpacing(6)
        for i, op in enumerate(REGISTRY):
            btn = OpButton()
            btn.setIcon(QIcon(resource(op.icon)))
            btn.setToolTip(op.title)
            btn.setMinimumSize(150, 150)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding,
                              QSizePolicy.Policy.Expanding)
            btn.clicked.connect(lambda checked=False, o=op: self.open_op(o))
            grid.addWidget(btn, i // GRID_COLS, i % GRID_COLS)

        self.stack = QStackedWidget()
        self.stack.addWidget(home)
        self.connect_page = self._build_connect_page()
        self.stack.addWidget(self.connect_page)
        self._nav = [home]
        layout.addWidget(self.stack, 1)

        self.setCentralWidget(central)

        w = self.controller.signals
        w.connected.connect(self.on_connected)
        w.disconnected.connect(self.on_disconnected)
        w.status.connect(self.on_status)
        w.setting.connect(self.on_setting)
        w.alarm.connect(self.on_alarm)

    def _build_status_strip(self) -> QWidget:
        host = QWidget()
        strip = QHBoxLayout(host)
        # pages add their own 6px margins inside the central layout's 6px;
        # match that so the strip lines up with page content
        strip.setContentsMargins(6, 0, 6, 0)
        self.state_label = QLabel("disconnected")
        self.state_label.setObjectName("state")
        self.x_label = QLabel("X ?")
        self.x_label.setObjectName("dro")
        self.z_label = QLabel("Z ?")
        self.z_label.setObjectName("dro")
        self.rpm_label = QLabel("S ?")
        self.rpm_label.setObjectName("dro")

        self.units_combo = TouchCombo()
        self.units_combo.addItems([u.value for u in Units])
        self.units_combo.setCurrentText(self.units.value)
        self.units_combo.setToolTip(
            "Saved parameters are converted when switching units "
            "(thread pitch excepted: TPI/in per rev vs mm per rev)")
        self.units_combo.currentTextChanged.connect(self.on_units_changed)

        self.device_btn = QPushButton(QIcon(resource("cable.svg")), "")
        self.device_btn.setObjectName("device")
        self.device_btn.setIconSize(QSize(28, 28))
        self.device_btn.setToolTip("Connection and machine controls")
        self.device_btn.clicked.connect(
            lambda: self._push(self.connect_page))

        # anchor the DRO labels: minimum widths sized for the longest
        # readouts so changing digits/state never shifts them
        for label, width in ((self.x_label, 145), (self.z_label, 140),
                             (self.rpm_label, 120)):
            label.setMinimumWidth(width)

        dro_panel = QFrame()
        dro_panel.setObjectName("dropanel")
        dro_row = QHBoxLayout(dro_panel)
        dro_row.setContentsMargins(12, 3, 12, 3)
        dro_row.setSpacing(16)
        dro_row.addWidget(self.x_label)
        dro_row.addWidget(self.z_label)
        dro_row.addWidget(self.rpm_label)

        strip.addWidget(dro_panel)
        strip.addStretch(1)   # state grows leftward into the stretch
        strip.addWidget(self.state_label)
        strip.addSpacing(12)
        strip.addWidget(self.units_combo)
        strip.addSpacing(8)
        strip.addWidget(self.device_btn)
        return host

    def _build_connect_page(self) -> QWidget:
        page = QWidget()

        back = QPushButton(QIcon(resource("arrow-left.svg")), "")
        back.setObjectName("back")
        back.setIconSize(QSize(28, 28))
        back.setToolTip("Back")
        back.clicked.connect(lambda: self._pop(self.connect_page))
        title = QLabel("<b>Device</b>")
        top = QHBoxLayout()
        top.addWidget(back)
        top.addSpacing(12)
        top.addWidget(title)
        top.addStretch(1)

        self.connect_bar = ConnectBar()
        self.connect_bar.connect_btn.clicked.connect(self.on_connect)

        self.hold_btn = QPushButton("Hold")
        self.resume_btn = QPushButton("Resume")
        self.reset_btn = QPushButton("Reset")
        self.unlock_btn = QPushButton("Unlock")
        self.unlock_btn.setToolTip("$X — clear an alarm lock")
        self.hold_btn.clicked.connect(self.controller.feed_hold)
        self.resume_btn.clicked.connect(self.controller.resume)
        self.reset_btn.clicked.connect(self.controller.soft_reset)
        self.unlock_btn.clicked.connect(self.controller.unlock)
        self._set_conn_ui(False)

        controls = QHBoxLayout()
        for b in (self.hold_btn, self.resume_btn, self.reset_btn,
                  self.unlock_btn):
            controls.addWidget(b)
        controls.addStretch(1)

        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)
        layout.addLayout(top)
        layout.addSpacing(20)
        layout.addWidget(self.connect_bar)
        layout.addSpacing(20)
        layout.addLayout(controls)
        layout.addStretch(1)
        return page

    def _set_conn_ui(self, connected: bool) -> None:
        for b in (self.hold_btn, self.resume_btn, self.reset_btn,
                  self.unlock_btn):
            b.setEnabled(connected)

    # -- slots -----------------------------------------------------------------
    def on_units_changed(self, text: str) -> None:
        new = Units(text)
        if new is self.units:
            return
        convert_saved_params(self.units, new)
        self.units = new
        settings().setValue("units", new.value)

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

    def _set_state(self, text: str, color: str = NEUTRAL) -> None:
        self.state_label.setText(text)
        self.state_label.setStyleSheet(f"color: {color};")

    def on_connected(self, desc: str) -> None:
        self.report_units = Units.MM   # until this device's $13 arrives
        self._set_state("connected")
        self.connect_bar.connect_btn.setText("Disconnect")
        self._set_conn_ui(True)

    def on_disconnected(self, reason: str) -> None:
        self._set_state("disconnected" + (f" — {reason}" if reason else ""))
        self.connect_bar.connect_btn.setText("Connect")
        self._set_conn_ui(False)
        for label in (self.x_label, self.z_label, self.rpm_label):
            label.setText(label.text().split()[0] + " ?")

    def on_setting(self, number: int, value: str) -> None:
        if number == 13:   # $13: report positions in inches (1) or mm (0)
            self.report_units = Units.INCH if value.startswith("1") \
                else Units.MM

    def on_status(self, st: dict) -> None:
        state = st.get("state", "?")
        self._set_state(state, STATE_COLORS.get(state.split(":")[0], NEUTRAL))
        pos = st.get("WPos") or st.get("MPos")
        if pos and len(pos) >= 3:
            if not self._sim_active:   # sim owns the readouts while running
                x_dia = pos[0] if self.machine.x_words_are_diameter \
                    else pos[0] * 2
                self._show_xz(convert(x_dia, self.report_units, self.units),
                              convert(pos[2], self.report_units, self.units))
            page = self.stack.currentWidget()
            if isinstance(page, RunPage):
                # plot coordinates use the program's units and X-word
                # convention (pos[0] already matches the X words)
                page.path_view.set_tool(
                    convert(pos[2], self.report_units, self.units),
                    convert(pos[0], self.report_units, self.units))
        if "rpm" in st:
            self.rpm_label.setText(f"S {st['rpm']:.0f} rpm")

    def _show_xz(self, x_dia: float, z: float) -> None:
        dec = self.units.display_decimals
        unit = "in" if self.units is Units.INCH else "mm"
        self.x_label.setText(f"X⌀ {x_dia:.{dec}f} {unit}")
        self.z_label.setText(f"Z {z:.{dec}f} {unit}")

    def on_sim_moved(self, z: float, x: float) -> None:
        self._sim_active = True
        for label in (self.x_label, self.z_label):
            label.setStyleSheet("color: rgb(255, 200, 60);")   # sim yellow
        self._show_xz(x if self.machine.x_words_are_diameter else x * 2, z)

    def on_sim_stopped(self) -> None:
        self._sim_active = False
        for label in (self.x_label, self.z_label):
            label.setStyleSheet("")
            label.setText(label.text().split()[0] + " ?")   # next poll refills

    def on_alarm(self, line: str) -> None:
        self._set_state(line, STATE_COLORS["Alarm"])
        QMessageBox.critical(
            self, "ALARM",
            f"{line}\n\nMotion is locked. Clear the cause, then press "
            "Unlock ($X) or Reset.")

    # -- page-stack navigation --------------------------------------------------
    def _push(self, page: QWidget) -> None:
        if page in self._nav:   # Device… tapped while its page is open
            return
        if self.stack.indexOf(page) == -1:
            self.stack.addWidget(page)
        self._nav.append(page)
        self.stack.setCurrentWidget(page)
        # unit switching would silently invalidate values on open pages;
        # the DRO shows the unit, so hide the dead selector entirely
        self.units_combo.setVisible(False)
        # parameter pages want the full screen, no live-status distraction
        self.status_strip.setVisible(not isinstance(page, OpPage))

    def _pop(self, page: QWidget) -> None:
        if isinstance(page, RunPage):   # leaving mid-sim: release the DRO
            page.path_view.stop_simulation()
        self._nav.remove(page)
        self.stack.setCurrentWidget(self._nav[-1])
        if page is not self.connect_page:   # the device page is permanent
            self.stack.removeWidget(page)
            page.deleteLater()
        self.units_combo.setVisible(len(self._nav) == 1)
        self.status_strip.setVisible(
            not isinstance(self.stack.currentWidget(), OpPage))

    def open_op(self, op) -> None:
        page = OpPage(op, self.machine, self.units)
        page.back_requested.connect(lambda: self._pop(page))
        page.run_requested.connect(
            lambda lines, o=op: self.open_run(o, lines))
        self._push(page)

    def open_run(self, op, lines: list[str]) -> None:
        page = RunPage(op, lines, self.controller, self.units)
        page.back_requested.connect(lambda: self._pop(page))
        page.path_view.sim_moved.connect(self.on_sim_moved)
        page.path_view.sim_stopped.connect(self.on_sim_stopped)
        self._push(page)

    def closeEvent(self, event) -> None:
        self.controller.shutdown()
        event.accept()
