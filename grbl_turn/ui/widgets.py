"""Small shared touch-friendly widgets."""

from PySide6.QtWidgets import QComboBox


class TouchCombo(QComboBox):
    """QComboBox whose popup is wide enough for its items: the popup
    inherits the closed box's width, but the stylesheet renders items
    bigger (48px rows, 18px text) than the box, eliding long entries."""

    def showPopup(self) -> None:
        view = self.view()
        view.setMinimumWidth(max(view.sizeHintForColumn(0) + 28,
                                 self.width()))
        super().showPopup()
