"""GrblController: owns the transport on a worker thread and talks GRBL.

Streaming uses simple send-response (one line out, wait for ok/error) —
predictable behaviour matters more than throughput on a lathe. Realtime
bytes (?, !, ~, 0x18) are written between lines without waiting.

All public methods are safe to call from the GUI thread; results come back
as Qt signals."""

import queue
import re
import time

from PySide6.QtCore import QObject, QThread, Signal

from grbl_turn.comms.transport import Transport

POLL_INTERVAL = 0.2
_STATUS = re.compile(r"<([^|>]+)(.*)>")
_SETTING = re.compile(r"\$(\d+)=(.*)")


def debug(direction: str, text: str) -> None:
    """Print every byte exchanged with the controller to the terminal."""
    print(f"[{time.strftime('%H:%M:%S')}] {direction} {text}", flush=True)


def parse_status(line: str) -> dict:
    m = _STATUS.match(line)
    if not m:
        return {}
    status = {"state": m.group(1)}
    for part in m.group(2).split("|"):
        if ":" not in part:
            continue
        key, val = part.split(":", 1)
        if key in ("MPos", "WPos", "WCO"):
            status[key] = [float(v) for v in val.split(",")]
        elif key == "FS":
            feed, rpm = val.split(",")[:2]
            status["feed"] = float(feed)
            status["rpm"] = float(rpm)
    return status


class GrblWorker(QObject):
    connected = Signal(str)          # transport description
    disconnected = Signal(str)       # reason ('' for user request)
    status = Signal(dict)
    setting = Signal(int, str)       # $ setting number, value
    comm_log = Signal(str, str)      # direction ('>' sent, '<' received), text
    progress = Signal(int, int)      # lines acked, total
    stream_finished = Signal(bool, str)   # ok, message
    alarm = Signal(str)

    def __init__(self):
        super().__init__()
        self.transport: Transport | None = None
        self.commands: queue.Queue = queue.Queue()
        self.running = True
        self._rx = b""
        self._last_poll = 0.0
        # streaming state
        self._lines: list[str] | None = None
        self._next = 0
        self._acked = 0

    # -- worker loop ----------------------------------------------------------
    def loop(self) -> None:
        while self.running:
            self.step()
            time.sleep(0.005)

    def step(self) -> None:
        self._process_commands()
        if self.transport:
            try:
                self._read_incoming()
                self._poll()
            except Exception as exc:  # transport died (cable/wifi drop)
                self._drop_transport(str(exc))

    def _process_commands(self) -> None:
        while True:
            try:
                cmd, arg = self.commands.get_nowait()
            except queue.Empty:
                return
            try:
                getattr(self, "_cmd_" + cmd)(arg)
            except Exception as exc:
                if cmd == "connect":
                    self.disconnected.emit(f"connect failed: {exc}")
                else:
                    self._drop_transport(str(exc))

    def _cmd_connect(self, transport: Transport) -> None:
        transport.open()
        self.transport = transport
        debug("--", f"connected: {transport.describe()}")
        self.transport.write(b"\r\n\r\n")   # wake GRBL
        debug(">", r"\r\n\r\n (wake)")
        self.connected.emit(transport.describe())
        self._write_line("$$")   # learn the settings, notably $13

    def _cmd_disconnect(self, _) -> None:
        self._abort_stream()
        if self.transport:
            self.transport.close()
            self.transport = None
        debug("--", "disconnected (user request)")
        self.disconnected.emit("")

    def _cmd_stream(self, lines: list[str]) -> None:
        if not self.transport or self._lines is not None:
            return
        self._lines = [l.strip() for l in lines if l.strip()]
        self._next = 0
        self._acked = 0
        if self._lines:
            self._send_next()
        else:
            self._lines = None
            self.stream_finished.emit(True, "empty program")

    def _cmd_line(self, line: str) -> None:
        if self.transport and self._lines is None:
            self._write_line(line)

    def _cmd_realtime(self, data: bytes) -> None:
        if not self.transport:
            return
        self.transport.write(data)
        debug(">", f"{data!r} (realtime)")
        if data == b"\x18":   # soft reset kills any stream
            if self._lines is not None:
                self._lines = None
                self.stream_finished.emit(False, "stopped by soft reset")
            self.comm_log.emit(">", "[soft reset]")

    def _cmd_stop(self, _) -> None:
        self.running = False
        if self.transport:
            self.transport.close()
            self.transport = None

    # -- reading --------------------------------------------------------------
    def _read_incoming(self) -> None:
        data = self.transport.read_available()
        if not data:
            return
        self._rx += data
        while b"\n" in self._rx:
            raw, self._rx = self._rx.split(b"\n", 1)
            line = raw.strip().decode(errors="replace")
            if line:
                self._handle_line(line)

    def _handle_line(self, line: str) -> None:
        debug("<", line)
        if line.startswith("<"):
            st = parse_status(line)
            if st:
                self.status.emit(st)
            return
        self.comm_log.emit("<", line)
        m = _SETTING.match(line)
        if m:
            self.setting.emit(int(m.group(1)), m.group(2).strip())
            return
        if line == "ok":
            self._on_ack()
        elif line.startswith("error:"):
            self._on_error(line)
        elif line.startswith("ALARM"):
            self.alarm.emit(line)
            if self._lines is not None:
                self._lines = None
                self.stream_finished.emit(False, line)

    # -- streaming ------------------------------------------------------------
    def _send_next(self) -> None:
        assert self._lines is not None and self._next < len(self._lines)
        line = self._lines[self._next]
        self._next += 1
        self._write_line(line)

    def _on_ack(self) -> None:
        if self._lines is None:
            return
        self._acked += 1
        self.progress.emit(self._acked, len(self._lines))
        if self._acked >= len(self._lines):
            self._lines = None
            self.stream_finished.emit(True, "program complete")
        else:
            self._send_next()

    def _on_error(self, line: str) -> None:
        if self._lines is not None:
            failed = self._lines[self._next - 1] if self._next else "?"
            self._lines = None
            self.stream_finished.emit(False, f"{line} on line: {failed}")

    def _abort_stream(self) -> None:
        if self._lines is not None:
            self._lines = None
            self.stream_finished.emit(False, "disconnected")

    # -- helpers --------------------------------------------------------------
    def _write_line(self, line: str) -> None:
        self.transport.write(line.encode() + b"\n")
        debug(">", line)
        self.comm_log.emit(">", line)

    def _poll(self) -> None:
        now = time.monotonic()
        if now - self._last_poll >= POLL_INTERVAL:
            self._last_poll = now
            self.transport.write(b"?")
            debug(">", "? (status poll)")

    def _drop_transport(self, reason: str) -> None:
        debug("--", f"transport dropped: {reason}")
        self._abort_stream()
        if self.transport:
            try:
                self.transport.close()
            except Exception:
                pass
            self.transport = None
        self.disconnected.emit(reason)


class GrblController(QObject):
    """GUI-thread facade: starts the worker thread, re-exposes its signals."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = GrblWorker()
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.loop)
        self.thread.start()
        self.is_connected = False
        self.is_streaming = False
        self.worker.connected.connect(self._on_connected)
        self.worker.disconnected.connect(self._on_disconnected)
        self.worker.stream_finished.connect(self._on_stream_finished)

    # signal passthroughs for convenience
    @property
    def signals(self) -> GrblWorker:
        return self.worker

    def _on_connected(self, _desc: str) -> None:
        self.is_connected = True

    def _on_disconnected(self, _reason: str) -> None:
        self.is_connected = False
        self.is_streaming = False

    def _on_stream_finished(self, _ok: bool, _msg: str) -> None:
        self.is_streaming = False

    # -- commands (callable from GUI thread) ----------------------------------
    def connect_transport(self, transport: Transport) -> None:
        self.worker.commands.put(("connect", transport))

    def disconnect_transport(self) -> None:
        self.worker.commands.put(("disconnect", None))

    def stream(self, lines: list[str]) -> None:
        self.is_streaming = True
        self.worker.commands.put(("stream", lines))

    def send_line(self, line: str) -> None:
        self.worker.commands.put(("line", line))

    def feed_hold(self) -> None:
        self.worker.commands.put(("realtime", b"!"))

    def resume(self) -> None:
        self.worker.commands.put(("realtime", b"~"))

    def soft_reset(self) -> None:
        self.worker.commands.put(("realtime", b"\x18"))

    def unlock(self) -> None:
        self.worker.commands.put(("line", "$X"))

    def shutdown(self) -> None:
        self.worker.commands.put(("stop", None))
        self.thread.quit()
        self.thread.wait(2000)
