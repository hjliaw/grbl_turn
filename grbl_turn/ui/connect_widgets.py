"""Connection bar: transport picker (Serial / WiFi / Simulator) and the
matching parameter widgets."""

from pathlib import Path

from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLineEdit, QPushButton,
                               QSpinBox, QStackedWidget, QWidget)
from serial.tools import list_ports

from grbl_turn.comms.simulator import SimTransport
from grbl_turn.comms.transport import SerialTransport, TelnetTransport, Transport
from grbl_turn.config import settings

BAUD_RATES = ["115200", "230400", "57600", "9600"]


class ConnectBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        s = settings()

        self.kind = QComboBox()
        self.kind.addItems(["Serial", "WiFi", "Simulator"])

        # serial page
        serial_page = QWidget()
        row = QHBoxLayout(serial_page)
        row.setContentsMargins(0, 0, 0, 0)
        self.port = QComboBox()
        self.refresh_ports()
        refresh = QPushButton("↻")
        refresh.setFixedWidth(32)
        refresh.setToolTip("Rescan serial ports")
        refresh.clicked.connect(self.refresh_ports)
        self.baud = QComboBox()
        self.baud.addItems(BAUD_RATES)
        row.addWidget(self.port, 1)
        row.addWidget(refresh)
        row.addWidget(self.baud)

        # wifi page
        wifi_page = QWidget()
        row = QHBoxLayout(wifi_page)
        row.setContentsMargins(0, 0, 0, 0)
        self.host = QLineEdit(str(s.value("conn/host", "grblesp32.local")))
        self.host.setPlaceholderText("controller IP or hostname")
        self.tcp_port = QSpinBox()
        self.tcp_port.setRange(1, 65535)
        self.tcp_port.setValue(int(s.value("conn/tcp_port", 23)))
        row.addWidget(self.host, 1)
        row.addWidget(self.tcp_port)

        self.pages = QStackedWidget()
        self.pages.addWidget(serial_page)
        self.pages.addWidget(wifi_page)
        self.pages.addWidget(QWidget())   # simulator needs no parameters
        self.kind.currentIndexChanged.connect(self.pages.setCurrentIndex)

        self.connect_btn = QPushButton("Connect")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.kind)
        layout.addWidget(self.pages, 1)
        layout.addWidget(self.connect_btn)

        self.kind.setCurrentIndex(int(s.value("conn/kind", 0)))
        last_port = str(s.value("conn/port", ""))
        if last_port:
            i = self.port.findText(last_port)
            if i >= 0:
                self.port.setCurrentIndex(i)

    def refresh_ports(self) -> None:
        self.port.clear()
        ports = [p.device for p in list_ports.comports()]
        # serial proxies (ptys/symlinks) that list_ports won't find in /dev
        proxy = Path("/tmp/ttyproxy")
        if proxy.is_dir():
            ports += sorted(str(p) for p in proxy.iterdir())
        elif proxy.exists():
            ports.append(str(proxy))
        self.port.addItems(ports)

    def make_transport(self) -> Transport:
        kind = self.kind.currentIndex()
        s = settings()
        s.setValue("conn/kind", kind)
        if kind == 0:
            if not self.port.currentText():
                raise ValueError("no serial port selected")
            s.setValue("conn/port", self.port.currentText())
            return SerialTransport(self.port.currentText(),
                                   int(self.baud.currentText()))
        if kind == 1:
            if not self.host.text().strip():
                raise ValueError("no host entered")
            s.setValue("conn/host", self.host.text().strip())
            s.setValue("conn/tcp_port", self.tcp_port.value())
            return TelnetTransport(self.host.text().strip(),
                                   self.tcp_port.value())
        return SimTransport(ack_delay=0.05)
