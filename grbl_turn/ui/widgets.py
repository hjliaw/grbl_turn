"""Small shared touch-friendly widgets."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (QComboBox, QStyle, QStyleOptionComboBox,
                               QStylePainter)


class TouchCombo(QComboBox):
    """QComboBox whose popup is wide enough for its items: the popup
    inherits the closed box's width, but the stylesheet renders items
    bigger (48px rows, 18px text) than the box, eliding long entries."""

    def showPopup(self) -> None:
        view = self.view()
        view.setMinimumWidth(max(view.sizeHintForColumn(0) + 28,
                                 self.width()))
        super().showPopup()


class NumericCombo(TouchCombo):
    """TouchCombo for numeric choices: drop-down arrow on the left,
    current value right-aligned to match the numeric edits."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QComboBox { padding-left: 30px; padding-right: 10px; }"
            "QComboBox::drop-down {"
            "  subcontrol-origin: border;"
            "  subcontrol-position: center left;"
            "  width: 24px; }")

    def paintEvent(self, event) -> None:
        painter = QStylePainter(self)
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        text = opt.currentText
        opt.currentText = ""
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, opt)
        rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox, opt,
            QStyle.SubControl.SC_ComboBoxEditField, self)
        painter.drawItemText(rect,
                             Qt.AlignmentFlag.AlignRight
                             | Qt.AlignmentFlag.AlignVCenter,
                             self.palette(), self.isEnabled(), text,
                             QPalette.ColorRole.ButtonText)
