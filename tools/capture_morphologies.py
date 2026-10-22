"""Reproduce chiral morphology figures from actual generated surfaces, not references."""

import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from surfaces.app import configure_app  # noqa: E402
from surfaces.exporting import raster_image  # noqa: E402
from surfaces.model import ExportSettings, ParticleSpec, StructureSpec  # noqa: E402
from surfaces.particle_ui import ParticleDialog  # noqa: E402
from surfaces.structures import build_project  # noqa: E402
from surfaces.window import MainWindow  # noqa: E402


def wait(app, dialog):
    deadline = time.monotonic() + 30
    while dialog.tasks.thread is not None:
        if time.monotonic() > deadline:
            raise RuntimeError("Preview timeout")
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()
    if not dialog.valid:
        raise RuntimeError(dialog.error.text())


def main():
    root = Path(__file__).resolve().parents[1]
    directory = root / "docs" / "images"
    app = QApplication([])
    configure_app(app)
    window = MainWindow()
    dialog = ParticleDialog(window)
    dialog.show()
    wait(app, dialog)
    dialog.shape.setCurrentIndex(dialog.shape.findData("helicoid_iii"))
    dialog.width.setValue(1000)
    dialog.atomistic.setChecked(False)
    dialog.build_preview()
    wait(app, dialog)
    dialog.grab().save(str(directory / "chiral-studio.png"))
    dialog.reject()
    image = Image.new("RGB", (1500, 1120), "#f3f5f8")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=23)
    small = ImageFont.load_default(size=17)
    models = [
        ("helicoid_iii", 1, False, "432 grooved cube · + hand"),
        ("helicoid_iii", -1, False, "432 grooved cube · mirror"),
        ("helicoid_iii", 1, False, "Deeper, wider grooves"),
        ("chiral_rod", 1, False, "Fourfold ridged rod · + hand"),
        ("chiral_rod", -1, False, "Fourfold ridged rod · mirror"),
        ("chiral_rod", 1, True, "Mirror-symmetric crossed ridges"),
    ]
    for i, (shape, hand, crossed, label) in enumerate(models):
        particle = ParticleSpec(
            shape=shape,
            width=1000 if i < 3 else 450,
            length=1200,
            handedness=hand,
            twist=60,
            crossed_ridges=crossed,
            atomistic=False,
            mesh_resolution=64,
        )
        if i == 2:
            particle.gap_depth, particle.gap_width = 0.35, 0.16
        project = build_project(StructureSpec(element="Au", a=4.08, particle=particle))
        project.appearance.legend = False
        figure = raster_image(project, ExportSettings(width=480, height=450, legend=False))
        x, y = (i % 3) * 500 + 10, (i // 3) * 560 + 10
        image.paste(figure.convert("RGB"), (x, y))
        draw.text((x + 8, y + 465), label, font=font, fill="#203149")
        draw.text(
            (x + 8, y + 500), "Continuum model · reference-inspired", font=small, fill="#52627a"
        )
    image.save(directory / "chiral-morphology-gallery.png")
    window.dirty = False
    window.close()


if __name__ == "__main__":
    main()
