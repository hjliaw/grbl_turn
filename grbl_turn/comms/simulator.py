"""In-process fake GRBL controller, used by the tests and `grbl-turn --sim`.

Responds like a friendly GRBL 1.1: banner on open/reset, 'ok' per line,
status reports on '?', naive X/Z position tracking from G0/G1/G33 words,
Hold/Run states for '!' and '~'. Optionally answers error:N on lines
matching an injected predicate (for tests)."""

import re
import time
from typing import Callable

from grbl_turn.comms.transport import Transport

BANNER = b"\r\nGrbl 1.1h ['$' for help]\r\n"
_WORD = re.compile(rb"([XZ])(-?\d+\.?\d*)")


class SimTransport(Transport):
    def __init__(self, ack_delay: float = 0.0,
                 error_on: Callable[[bytes], int | None] | None = None,
                 report_inches: bool = False):
        self.ack_delay = ack_delay
        self.error_on = error_on
        self.report_inches = report_inches
        self.out = bytearray()
        self.pos = {"X": 0.0, "Z": 0.0}
        self.state = "Idle"
        self._inbuf = b""
        self._open = False

    # -- Transport interface -------------------------------------------------
    def open(self) -> None:
        self._open = True
        self.out += BANNER

    def close(self) -> None:
        self._open = False

    def write(self, data: bytes) -> None:
        for byte in data:
            b = bytes([byte])
            if b == b"?":
                self._status_report()
            elif b == b"!":
                self.state = "Hold:0"
            elif b == b"~":
                self.state = "Idle"
            elif b == b"\x18":
                self._inbuf = b""
                self.state = "Idle"
                self.out += BANNER
            else:
                self._inbuf += b
                if b == b"\n":
                    self._handle_line(self._inbuf.strip())
                    self._inbuf = b""

    def read_available(self) -> bytes:
        if self.ack_delay:
            time.sleep(0.01)
        data = bytes(self.out)
        self.out.clear()
        return data

    def describe(self) -> str:
        return "simulator"

    # -- fake GRBL behaviour -------------------------------------------------
    def _handle_line(self, line: bytes) -> None:
        if not line:
            return
        if self.ack_delay:
            time.sleep(self.ack_delay)
        if self.error_on:
            code = self.error_on(line)
            if code:
                self.out += f"error:{code}\r\n".encode()
                return
        if line.startswith(b"$"):
            if line == b"$$":
                self.out += f"$13={int(self.report_inches)}\r\n".encode()
            self.out += b"ok\r\n"
            return
        for axis, num in _WORD.findall(line):
            self.pos[axis.decode()] = float(num)
        self.out += b"ok\r\n"

    def _status_report(self) -> None:
        report = (f"<{self.state}|MPos:{self.pos['X']:.3f},0.000,"
                  f"{self.pos['Z']:.3f}|FS:0,0>\r\n")
        self.out += report.encode()
