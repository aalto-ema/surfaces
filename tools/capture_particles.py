"""Capture real particle UI and ASE/QPainter gallery for project documentation."""

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
from surfaces.persistence import save_project  # noqa: E402
from surfaces.structures import build_project  # noqa: E402
from surfaces.window import MainWindow  # noqa: E402


def wait(app, dialog):
    deadline = time.monotonic() + 20
    while dialog.tasks.thread is not None:
        if time.monotonic() > deadline:
            raise RuntimeError("Particle preview timed out")
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()
    if not dialog.valid:
        raise RuntimeError(dialog.error.text())


def main():
    root = Path(__file__).resolve().parents[1]
    images = root / "docs" / "images"
    images.mkdir(exist_ok=True)
    app = QApplication([])
    configure_app(app)
    window = MainWindow()
    dialog = ParticleDialog(window)
    dialog.show()
    wait(app, dialog)
    dialog.shape.setCurrentIndex(dialog.shape.findData("twisted_rod"))
    dialog.twist.setValue(180)
    dialog.build_preview()
    wait(app, dialog)
    dialog.grab().save(str(images / "nanoparticle-studio.png"))
    dialog.reject()
    gallery = Image.new("RGB", (1440, 1380), "#f3f5f8")
    draw = ImageDraw.Draw(gallery)
    font = ImageFont.load_default(size=22)
    small = ImageFont.load_default(size=16)
    examples = [
        ("cube", "Au cube · {100}"),
        ("octahedron", "Au octahedron · {111}"),
        ("cuboctahedron", "Au cuboctahedron · {100}/{111}"),
        ("sphere", "Lattice-cut sphere"),
        ("rod", "Cylindrical nanorod · [001]"),
        ("triangle", "Triangular nanoplate · [111]"),
        ("wulff", "Wulff · illustrative ratios"),
        ("twisted_rod", "Twisted rod · +180°"),
        ("helicoid", "Helicoidal ribbon · +180°"),
    ]
    for i, (shape, label) in enumerate(examples):
        spec = StructureSpec(
            element="Au",
            a=4.08,
            lattice_source="Editable Au FCC preset 4.08 Å; illustrative geometry",
            particle=ParticleSpec(
                shape=shape, axis="111" if shape == "triangle" else "001", twist=180
            ),
        )
        project = build_project(spec)
        project.appearance.legend = False
        if shape == "triangle":
            project.camera.elevation = 72
        image = raster_image(project, ExportSettings(width=456, height=370, legend=False))
        x, y = (i % 3) * 480 + 12, (i // 3) * 460 + 12
        gallery.paste(image.convert("RGB"), (x, y))
        draw.text((x + 8, y + 380), label, fill="#203149", font=font)
        draw.text(
            (x + 8, y + 413),
            f"{len(project.atoms):,} atoms · ideal / unrelaxed",
            fill="#52627a",
            font=small,
        )
        if shape in ("cube", "twisted_rod", "wulff"):
            save_project(project, root / "examples" / f"au-{shape.replace('_', '-')}.surfaces.json")
    gallery.save(images / "nanoparticle-gallery.png")
    window.dirty = False
    window.close()


if __name__ == "__main__":
    main()
