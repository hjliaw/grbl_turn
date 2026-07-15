"""Dark theme carried over from the eznc.ui prototype, sized for a
touch-only 800x480 screen: ~44px touch targets, wide scrollbars,
big spinbox arrows and checkbox indicators."""

STYLESHEET = """
QWidget {
    background-color: rgb(30, 30, 30);
    color: rgb(255, 255, 255);
    font-size: 16px;
}
QToolButton, QPushButton {
    background-color: rgb(45, 45, 45);
    border: 1px solid rgb(70, 70, 70);
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 28px;
}
QToolButton:hover, QPushButton:hover {
    background-color: rgb(60, 60, 60);
}
QPushButton:pressed {
    background-color: rgb(80, 80, 80);
}
QPushButton:checked {
    background-color: rgb(55, 90, 55);
    border-color: rgb(120, 220, 120);
}
QPushButton:disabled {
    color: rgb(110, 110, 110);
}
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {
    background-color: rgb(45, 45, 45);
    border: 1px solid rgb(70, 70, 70);
    border-radius: 4px;
    padding: 6px;
}
QLineEdit, QComboBox, QSpinBox {
    min-height: 28px;
}
QComboBox {
    padding-right: 24px;
}
QComboBox::drop-down {
    width: 18px;
}
QComboBox QAbstractItemView::item {
    min-height: 40px;
}
QSpinBox::up-button, QSpinBox::down-button {
    width: 40px;
}
QScrollBar:vertical {
    width: 18px;
    background: rgb(38, 38, 38);
}
QScrollBar:horizontal {
    height: 18px;
    background: rgb(38, 38, 38);
}
QScrollBar::handle {
    background: rgb(90, 90, 90);
    border-radius: 6px;
    min-height: 40px;
}
QCheckBox::indicator {
    width: 22px;
    height: 22px;
    border: 1px solid rgb(160, 160, 160);
    border-radius: 4px;
    background-color: rgb(45, 45, 45);
}
QCheckBox::indicator:hover {
    border-color: rgb(220, 220, 220);
}
QCheckBox::indicator:checked {
    background-color: rgb(80, 180, 80);
    border-color: rgb(120, 220, 120);
}
QCheckBox::indicator:disabled {
    border-color: rgb(90, 90, 90);
}
QGroupBox {
    border: 1px solid rgb(70, 70, 70);
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 8px;
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
    font-size: 18px;
    font-weight: bold;
}
QLabel#warning {
    color: rgb(255, 170, 60);
    font-weight: bold;
}
QPushButton#stop {
    background-color: rgb(140, 30, 30);
    font-weight: bold;
    min-height: 36px;
}
QPushButton#run {
    background-color: rgb(30, 100, 30);
    font-weight: bold;
    min-height: 36px;
}
QPushButton#back {
    background-color: rgb(30, 100, 30);
}
QPushButton#numpad, QPushButton#numpadok {
    font-size: 22px;
    min-height: 40px;
    min-width: 60px;
}
QPushButton#numpadok {
    background-color: rgb(30, 100, 30);
    font-weight: bold;
}
"""
