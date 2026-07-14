import argparse
import sys

from PySide6.QtWidgets import QApplication

from grbl_turn.ui.main_window import MainWindow
from grbl_turn.ui.theme import STYLESHEET


def main() -> None:
    parser = argparse.ArgumentParser(description="Conversational lathe GUI "
                                     "for ESP32 GRBL controllers")
    parser.add_argument("--sim", action="store_true",
                        help="preselect the built-in GRBL simulator")
    parser.add_argument("--fullscreen", action="store_true",
                        help="fill the screen (automatic on small displays)")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setApplicationName("grbl_turn")
    app.setStyleSheet(STYLESHEET)

    win = MainWindow()
    if args.sim:
        win.connect_bar.kind.setCurrentIndex(2)
    # kiosk-style on the 7" touch screen, windowed on desktops
    geo = app.primaryScreen().availableGeometry()
    if args.fullscreen or (geo.width() <= 820 and geo.height() <= 500):
        win.showFullScreen()
    else:
        win.resize(min(900, geo.width()), min(560, geo.height()))
        win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
