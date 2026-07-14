"""On-screen numeric keypad for a touch-only screen (no OS keyboard).

TouchNumberEdit is a QLineEdit that opens the keypad when tapped; a real
keyboard still works if one is attached."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QGridLayout, QLabel, QLineEdit,
                               QPushButton, QVBoxLayout)


class NumPad(QDialog):
    def __init__(self, label: str, initial: str, parent=None):
        super().__init__(parent, Qt.WindowType.Dialog
                         | Qt.WindowType.FramelessWindowHint)
        self.setModal(True)

        title = QLabel(label)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.display = QLabel(initial)
        self.display.setObjectName("dro")
        self.display.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.display.setMinimumWidth(260)

        grid = QGridLayout()
        grid.setSpacing(6)
        keys = [("7", "8", "9", "⌫"),
                ("4", "5", "6", "C"),
                ("1", "2", "3", "±"),
                ("0", ".", "✕", "OK")]
        self.ok_btn = None
        for r, row in enumerate(keys):
            for c, key in enumerate(row):
                b = QPushButton(key)
                b.setObjectName("numpad")
                b.clicked.connect(lambda checked=False, k=key: self.on_key(k))
                grid.addWidget(b, r, c)
                if key == "OK":
                    b.setObjectName("numpadok")
                    self.ok_btn = b

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.display)
        layout.addLayout(grid)
        self._validate()

    def on_key(self, key: str) -> None:
        text = self.display.text()
        if key == "⌫":
            text = text[:-1]
        elif key == "C":
            text = ""
        elif key == "±":
            text = text[1:] if text.startswith("-") else "-" + text
        elif key == "✕":
            self.reject()
            return
        elif key == "OK":
            self.accept()
            return
        else:
            if key == "." and "." in text:
                return
            text += key
        self.display.setText(text)
        self._validate()

    def _validate(self) -> None:
        try:
            float(self.display.text())
            self.ok_btn.setEnabled(True)
        except ValueError:
            self.ok_btn.setEnabled(False)

    @staticmethod
    def get_value(label: str, initial: str, parent=None) -> tuple[str, bool]:
        pad = NumPad(label, initial, parent)
        if parent is not None:
            pad.adjustSize()
            center = parent.window().geometry().center()
            pad.move(center.x() - pad.width() // 2,
                     center.y() - pad.height() // 2)
        ok = pad.exec() == QDialog.DialogCode.Accepted
        return pad.display.text(), ok


class TouchNumberEdit(QLineEdit):
    """Line edit that opens the numeric keypad when tapped."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.pad_label = label
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        text, ok = NumPad.get_value(self.pad_label, self.text(), self)
        if ok:
            self.setText(text)
