"""Byte transports to the controller. The GrblController owns exactly one
transport and does all reads/writes from its worker thread."""

import socket
from abc import ABC, abstractmethod

import serial

try:
    import termios
except ImportError:  # Windows: no termios, and no HUPCL to clear
    termios = None


class Transport(ABC):
    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def write(self, data: bytes) -> None: ...

    @abstractmethod
    def read_available(self) -> bytes:
        """Return whatever bytes have arrived (possibly b''), without
        blocking longer than ~50 ms."""

    @abstractmethod
    def describe(self) -> str: ...


class _HandsOffSerial(serial.Serial):
    """pyserial sets DTR and RTS with one ioctl each on open; the ESP32
    auto-program circuit fires on the asymmetric intermediate state (one
    line asserted, the other not) and resets the chip. Skip the per-line
    pokes; SerialTransport.open() sets both lines in a single ioctl."""

    def _update_dtr_state(self) -> None:
        pass

    def _update_rts_state(self) -> None:
        pass


class SerialTransport(Transport):
    def __init__(self, port: str, baud: int = 115200):
        self.port = port
        self.baud = baud
        self.ser: serial.Serial | None = None

    def open(self) -> None:
        ser = _HandsOffSerial(self.port, self.baud, timeout=0.05)
        # DTR/RTS edges reach EN/GPIO0 through the ESP32 auto-program
        # circuit. The driver raises both lines during open() — nothing
        # userspace can prevent — so instead keep them raised forever:
        # with HUPCL cleared, close() no longer drops them, and every
        # open after the first is edge-free (no reset). Windows has no
        # HUPCL, so there the controller may reset once per connect.
        if termios is not None:
            attrs = termios.tcgetattr(ser.fd)
            attrs[2] &= ~termios.HUPCL
            termios.tcsetattr(ser.fd, termios.TCSANOW, attrs)
        self.ser = ser

    def close(self) -> None:
        if self.ser:
            self.ser.close()
            self.ser = None

    def write(self, data: bytes) -> None:
        self.ser.write(data)

    def read_available(self) -> bytes:
        waiting = self.ser.in_waiting
        return self.ser.read(waiting) if waiting else self.ser.read(1)

    def describe(self) -> str:
        return f"serial {self.port} @ {self.baud}"


class TelnetTransport(Transport):
    """Raw TCP socket. ESP32 GRBL 'telnet' is a plain byte stream on port 23,
    no telnet option negotiation."""

    def __init__(self, host: str, port: int = 23):
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None

    def open(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=5)
        self.sock.settimeout(0.05)

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def write(self, data: bytes) -> None:
        self.sock.sendall(data)

    def read_available(self) -> bytes:
        try:
            data = self.sock.recv(4096)
            if data == b"":
                raise ConnectionError("connection closed by controller")
            return data
        except (socket.timeout, BlockingIOError):
            return b""

    def describe(self) -> str:
        return f"tcp {self.host}:{self.port}"
