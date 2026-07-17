"""Preview + run page: one big view area toggled between the toolpath plot,
the G-code text, and the comm console (simplest layout for a touch-only
800x480 screen). Back is locked while streaming; the red tool dot on the
plot is the run feedback."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (QButtonGroup, QHBoxLayout, QLabel,
                               QPlainTextEdit, QPushButton, QScroller,
                               QStackedWidget, QVBoxLayout, QWidget)

from grbl_turn import resource
from grbl_turn.ops.base import Operation
from grbl_turn.ui.path_view import PathView
from grbl_turn.units import Units

PLOT, GCODE, CONSOLE = range(3)


class RunPage(QWidget):
    back_requested = Signal()

    def __init__(self, op: Operation, lines: list[str], controller,
                 units: Units, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.lines = lines
        self.op_title = op.title

        self.back_btn = QPushButton(QIcon(resource("arrow-left.svg")), "")
        self.back_btn.setObjectName("back")
        self.back_btn.setIconSize(QSize(28, 28))
        self.back_btn.setToolTip("Back")
        self.back_btn.clicked.connect(self.back_requested)

        # view toggle: plot / g-code text / console share one big area
        self.views = QStackedWidget()
        self.path_view = PathView(lines, silhouette=op.silhouette)
        self.views.addWidget(self.path_view)

        preview = QPlainTextEdit("\n".join(lines))
        preview.setReadOnly(True)
        preview.setFont(QFont("Courier New", 13))
        QScroller.grabGesture(preview.viewport(),
                              QScroller.ScrollerGestureType.LeftMouseButtonGesture)
        self.views.addWidget(preview)

        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Courier New", 12))
        QScroller.grabGesture(self.console.viewport(),
                              QScroller.ScrollerGestureType.LeftMouseButtonGesture)
        self.views.addWidget(self.console)

        def icon_btn(icon: str, tip: str) -> QPushButton:
            b = QPushButton(QIcon(resource(icon)), "")
            b.setIconSize(QSize(28, 28))
            b.setToolTip(tip)
            return b

        self.view_group = QButtonGroup(self)
        self.view_group.setExclusive(True)
        top = QHBoxLayout()
        top.addWidget(self.back_btn)
        top.addSpacing(8)
        top.addWidget(QLabel(f"<b>{op.title}</b>"))
        top.addStretch(1)
        self.sim_btn = icon_btn(
            "play.svg", "Simulate: animate the tool tip along the toolpath")
        self.sim_btn.clicked.connect(self.on_simulate)
        top.addWidget(self.sim_btn)
        # shown in place of the view toggle while a simulation runs
        self.sim_pause_btn = icon_btn("pause.svg", "Pause simulation")
        self.sim_pause_btn.clicked.connect(self.on_sim_pause)
        self.sim_quit_btn = icon_btn("x.svg", "End simulation")
        self.sim_quit_btn.clicked.connect(
            lambda: self.path_view.stop_simulation())
        top.addWidget(self.sim_pause_btn)
        top.addWidget(self.sim_quit_btn)
        top.addSpacing(8)
        seg = QHBoxLayout()      # joined segmented control, not loose buttons
        seg.setSpacing(0)
        for (idx, name, icon), pos in zip(((PLOT, "Plot", "plot.svg"),
                                           (GCODE, "G-code", "list.svg"),
                                           (CONSOLE, "Console", "terminal.svg")),
                                          ("first", "mid", "last")):
            b = icon_btn(icon, name)
            b.setCheckable(True)
            b.setProperty("seg", pos)
            self.view_group.addButton(b, idx)
            seg.addWidget(b)
        top.addLayout(seg)
        self.save_btn = icon_btn("save.svg", "Save .nc…")
        self.save_btn.clicked.connect(self.on_save)
        top.addSpacing(8)
        top.addWidget(self.save_btn)
        self._set_sim_ui(False)
        self.path_view.sim_stopped.connect(lambda: self._set_sim_ui(False))
        self.view_group.idClicked.connect(self.views.setCurrentIndex)
        self.view_group.button(PLOT).setChecked(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)
        layout.addLayout(top)
        layout.addWidget(self.views, 1)

        if op.is_threading:
            warn = QLabel(
                "⚠ THREADING: feed hold is DEFERRED during spindle-synced "
                "passes — use the machine E-stop for emergencies.")
            warn.setObjectName("warning")
            warn.setWordWrap(True)      # keep the page inside 800px
            layout.addWidget(warn)

        self.run_btn = icon_btn("play.svg", "Run")
        self.run_btn.setObjectName("run")
        self.run_btn.setEnabled(False)
        self.hold_btn = icon_btn("pause.svg", "Hold")
        self.hold_btn.setObjectName("hold")
        self.resume_btn = icon_btn("refresh.svg", "Resume")
        self.resume_btn.setObjectName("resume")
        self.stop_btn = icon_btn("stop.svg", "STOP (soft reset)")
        self.stop_btn.setObjectName("stop")
        for b in (self.hold_btn, self.resume_btn, self.stop_btn):
            b.setEnabled(False)

        buttons = QHBoxLayout()
        buttons.addWidget(self.run_btn, 1)
        buttons.addWidget(self.hold_btn, 1)
        buttons.addWidget(self.resume_btn, 1)
        buttons.addWidget(self.stop_btn, 1)
        layout.addLayout(buttons)

        self.run_btn.clicked.connect(self.on_run)
        self.hold_btn.clicked.connect(controller.feed_hold)
        self.resume_btn.clicked.connect(controller.resume)
        self.stop_btn.clicked.connect(controller.soft_reset)

        w = controller.signals
        w.stream_finished.connect(self.on_finished)
        w.comm_log.connect(self.on_log)
        # bound-method slots so the worker-thread signals queue to the GUI
        # thread; a bare lambda would run on the worker thread
        w.connected.connect(self.on_connected)
        w.disconnected.connect(self.on_disconnected)

        self._update_buttons()

    def _update_buttons(self) -> None:
        ready = (self.controller.is_connected
                 and not self.controller.is_streaming)
        self.run_btn.setEnabled(ready)

    def show_view(self, idx: int) -> None:
        self.view_group.button(idx).setChecked(True)
        self.views.setCurrentIndex(idx)

    def on_simulate(self) -> None:
        self.show_view(PLOT)
        self.path_view.start_simulation()
        if self.path_view.sim_point is not None:   # empty programs: no sim
            self._set_sim_ui(True)

    def on_sim_pause(self) -> None:
        pv = self.path_view
        if pv.sim_paused:
            pv.resume_simulation()
        else:
            pv.pause_simulation()
        self.sim_pause_btn.setIcon(QIcon(resource(
            "play.svg" if pv.sim_paused else "pause.svg")))
        self.sim_pause_btn.setToolTip(
            "Resume simulation" if pv.sim_paused else "Pause simulation")

    def _set_sim_ui(self, active: bool) -> None:
        self.sim_btn.setVisible(not active)
        self.save_btn.setVisible(not active)
        for idx in (PLOT, GCODE, CONSOLE):
            self.view_group.button(idx).setVisible(not active)
        self.sim_pause_btn.setVisible(active)
        self.sim_quit_btn.setVisible(active)
        if active:   # fresh sim always starts running
            self.sim_pause_btn.setIcon(QIcon(resource("pause.svg")))
            self.sim_pause_btn.setToolTip("Pause simulation")

    def on_run(self) -> None:
        self.run_btn.setEnabled(False)
        self.back_btn.setEnabled(False)     # stop or finish before leaving
        for b in (self.hold_btn, self.resume_btn, self.stop_btn):
            b.setEnabled(True)
        self.controller.stream(self.lines)

    def on_connected(self, _desc: str) -> None:
        self._update_buttons()

    def on_disconnected(self, _reason: str) -> None:
        self._update_buttons()

    def on_finished(self, ok: bool, msg: str) -> None:
        self.back_btn.setEnabled(True)
        for b in (self.hold_btn, self.resume_btn, self.stop_btn):
            b.setEnabled(False)
        if not ok:
            self.show_view(CONSOLE)     # surface what went wrong
        self._update_buttons()

    def on_log(self, direction: str, text: str) -> None:
        self.console.appendPlainText(f"{direction} {text}")

    def on_save(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Save G-code", f"{self.op_title}.nc",
            "G-code (*.nc *.gcode);;All files (*)")
        if path:
            with open(path, "w") as f:
                f.write("\n".join(self.lines) + "\n")
