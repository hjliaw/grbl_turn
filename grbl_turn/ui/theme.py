"""Dark theme carried over from the eznc.ui prototype, sized for a
touch-only 800x480 screen: ~44px touch targets, wide scrollbars,
big spinbox arrows and checkbox indicators."""

STYLESHEET = """
QWidget {
    background-color: rgb(50, 50, 50);
    color: rgb(255, 255, 255);
    font-size: 16px;
}
QToolButton, QPushButton {
    background-color: rgb(66, 66, 66);
    border: 1px solid rgb(92, 92, 92);
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 28px;
}
QToolButton:hover, QPushButton:hover {
    background-color: rgb(82, 82, 82);
}
QPushButton:pressed {
    background-color: rgb(96, 96, 96);
}
QPushButton:checked {
    background-color: rgb(55, 90, 55);
    border-color: rgb(120, 220, 120);
}
QPushButton:disabled {
    color: rgb(110, 110, 110);
}
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {
    background-color: rgb(66, 66, 66);
    border: 1px solid rgb(92, 92, 92);
    border-radius: 4px;
    padding: 6px;
}
QLineEdit, QComboBox, QSpinBox {
    min-height: 28px;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
    color: rgb(120, 120, 120);
    background-color: rgb(56, 56, 56);
    border-color: rgb(76, 76, 76);
}
QComboBox {
    padding-right: 24px;
    combobox-popup: 0;   /* styled list popup, not the native macOS menu */
}
QComboBox::drop-down {
    width: 18px;
}
QComboBox QAbstractItemView {
    background-color: rgb(66, 66, 66);
    border: 1px solid rgb(92, 92, 92);
    font-size: 18px;
}
QComboBox QAbstractItemView::item {
    min-height: 48px;
    padding: 0 10px;
}
QComboBox QAbstractItemView::item:selected {
    background-color: rgb(55, 90, 55);
}
QToolTip {
    background-color: rgb(66, 66, 66);
    color: rgb(255, 255, 255);
    border: 1px solid rgb(112, 112, 112);
}
QSpinBox::up-button, QSpinBox::down-button {
    width: 40px;
}
QScrollBar:vertical {
    width: 18px;
    background: rgb(58, 58, 58);
}
QScrollBar:horizontal {
    height: 18px;
    background: rgb(58, 58, 58);
}
QScrollBar::handle {
    background: rgb(112, 112, 112);
    border-radius: 6px;
    min-height: 40px;
}
QCheckBox::indicator {
    width: 22px;
    height: 22px;
    border: 1px solid rgb(160, 160, 160);
    border-radius: 4px;
    background-color: rgb(66, 66, 66);
}
QCheckBox::indicator:hover {
    border-color: rgb(220, 220, 220);
}
QCheckBox::indicator:checked {
    background-color: rgb(80, 180, 80);
    border-color: rgb(120, 220, 120);
}
QCheckBox::indicator:disabled {
    border-color: rgb(112, 112, 112);
}
QGroupBox {
    border: 1px solid rgb(92, 92, 92);
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
    font-size: 22px;
    color: rgb(120, 220, 120);
}
QFrame#dropanel {
    border: 1px solid rgb(86, 86, 86);
    border-radius: 6px;
}
QLabel#state {
    font-size: 18px;
    font-weight: bold;
}
QLabel#warning {
    color: rgb(255, 170, 60);
    font-weight: bold;
}
QLabel#caption {
    font-family: monospace;
    font-size: 14px;
    color: rgb(168, 180, 168);
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
QPushButton#hold, QPushButton#resume {
    min-height: 36px;
}
QPushButton#stop:disabled {
    background-color: rgb(72, 46, 46);
}
QPushButton#run:disabled {
    background-color: rgb(44, 62, 44);
}
QPushButton[seg="first"] {
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
}
QPushButton[seg="mid"] {
    border-radius: 0;
    border-left: none;
}
QPushButton[seg="last"] {
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
    border-left: none;
}
QPushButton#back {
    background-color: rgb(160, 175, 160);
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
