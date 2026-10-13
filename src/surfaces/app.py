"""Desktop application entry point."""

import sys

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from surfaces.ui_common import STYLE
from surfaces.window import MainWindow


def configure_app(app: QApplication) -> None:
    app.setApplicationName("Surfaces")
    app.setOrganizationName("Surfaces")
    app.setStyle("Fusion")
    palette = QPalette()
    for role, color in {
        QPalette.ColorRole.Window: "#f3f5f8",
        QPalette.ColorRole.WindowText: "#243247",
        QPalette.ColorRole.Base: "#ffffff",
        QPalette.ColorRole.AlternateBase: "#f3f5f8",
        QPalette.ColorRole.Text: "#243247",
        QPalette.ColorRole.Button: "#f6f8fc",
        QPalette.ColorRole.ButtonText: "#243247",
        QPalette.ColorRole.Highlight: "#dceaff",
        QPalette.ColorRole.HighlightedText: "#203149",
    }.items():
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setStyleSheet(STYLE)


def main() -> int:
    app = QApplication(sys.argv)
    configure_app(app)
    window = MainWindow()
    window.show()
    return app.exec()
