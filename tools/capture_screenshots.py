"""Capture the real Qt workspace for README images, without desktop/private content.

Run from an installed development environment: python tools/capture_screenshots.py
"""

import os
from pathlib import Path

from PySide6.QtWidgets import QApplication

from surfaces.app import configure_app
from surfaces.persistence import load_project
from surfaces.window import MainWindow

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication([])
    configure_app(app)
    output = ROOT / "docs" / "images"
    output.mkdir(parents=True, exist_ok=True)
    scenes = [
        ("pt-au-random", "workspace.png", 1),
        ("nife2o4-001-inverse", "compound-workspace.png", 0),
    ]
    for stem, filename, tab in scenes:
        window = MainWindow()
        window.project = load_project(ROOT / "examples" / f"{stem}.surfaces.json")
        window.refresh()
        window.resize(1360, 900)
        window.tabs.setCurrentIndex(tab)
        if tab == 1:
            window.composition_panel.mode.setCurrentIndex(1)
        window.show()
        app.processEvents()
        if not window.grab().save(str(output / filename), "PNG"):
            raise OSError(f"Could not write screenshot: {filename}")
        window.dirty = False
        window.close()
        app.processEvents()
        print(f"Saved {output.relative_to(ROOT) / filename}")


if __name__ == "__main__":
    main()
