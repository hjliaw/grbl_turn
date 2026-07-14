"""Dark theme carried over from the eznc.ui prototype."""

STYLESHEET = """
QWidget {
    background-color: rgb(30, 30, 30);
    color: rgb(255, 255, 255);
    font-size: 14px;
}
QToolButton, QPushButton {
    background-color: rgb(45, 45, 45);
    border: 1px solid rgb(70, 70, 70);
    border-radius: 4px;
    padding: 6px;
}
QToolButton:hover, QPushButton:hover {
    background-color: rgb(60, 60, 60);
}
QPushButton:disabled {
    color: rgb(110, 110, 110);
}
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {
    background-color: rgb(45, 45, 45);
    border: 1px solid rgb(70, 70, 70);
    border-radius: 3px;
    padding: 3px;
}
QGroupBox {
    border: 1px solid rgb(70, 70, 70);
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 6px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    color: rgb(180, 200, 180);
}
QLabel#dro {
    font-family: monospace;
    font-size: 20px;
    color: rgb(120, 220, 120);
}
QLabel#state {
    font-size: 16px;
    font-weight: bold;
}
QLabel#warning {
    color: rgb(255, 170, 60);
    font-weight: bold;
}
QPushButton#stop {
    background-color: rgb(140, 30, 30);
    font-weight: bold;
}
QPushButton#run {
    background-color: rgb(30, 100, 30);
    font-weight: bold;
}
"""
