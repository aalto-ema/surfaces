"""Publication exports drawn directly from the shared scene, never widget captures."""

import copy
import math
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QMarginsF, QRect, QSize, QSizeF
from PySide6.QtGui import QImage, QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtSvg import QSvgGenerator

from surfaces.model import ExportSettings, Project
from surfaces.persistence import atomic_write, validate_export
from surfaces.rendering import draw_scene


class ExportDimensions:
    def __init__(self, settings: ExportSettings):
        validate_export(settings)
        factors = {"px": 25.4 / settings.dpi, "mm": 1, "in": 25.4, "pt": 25.4 / 72}
        self.width_mm = settings.width * factors[settings.unit]
        self.height_mm = settings.height * factors[settings.unit]
        self.width_px = max(1, round(self.width_mm / 25.4 * settings.dpi))
        self.height_px = max(1, round(self.height_mm / 25.4 * settings.dpi))
        if not 0.15 <= self.width_mm / self.height_mm <= 6:
            raise ValueError("Use a canvas aspect ratio between 0.15 and 6 for readable framing.")
        if settings.format in ("PNG", "TIFF") and (
            self.width_px * self.height_px > 24_000_000
            or max(self.width_px, self.height_px) > 20_000
        ):
            raise ValueError(
                "Raster exports are limited to 24 megapixels and 20,000 pixels per side."
            )
        if not all(math.isfinite(n) and n > 0 for n in (self.width_mm, self.height_mm)):
            raise ValueError("Canvas dimensions must be positive and finite.")


def paint_device(device, project: Project, settings: ExportSettings, width, height):
    painter = QPainter()
    if not painter.begin(device):
        raise OSError("Could not initialize the figure drawing device.")
    try:
        painter.scale(width / 1000, width / 1000)
        draw_scene(
            painter,
            project,
            1000,
            height * 1000 / width,
            transparent=settings.transparent,
            margin=settings.margin,
            legend=settings.legend,
            axes=settings.axes,
        )
    finally:
        painter.end()


def raster_image(project: Project, settings: ExportSettings, *, preview=False) -> Image.Image:
    dimensions = ExportDimensions(settings)
    w, h = dimensions.width_px, dimensions.height_px
    if preview:
        factor = min(1, 1600 / w, 1300 / h)
        w, h = max(1, round(w * factor)), max(1, round(h * factor))
    supersample = 2 if w * h <= 6_000_000 else 1
    image = QImage(w * supersample, h * supersample, QImage.Format.Format_RGBA8888)
    if image.isNull():
        raise MemoryError("Not enough memory for this canvas. Choose smaller dimensions.")
    image.fill(0)
    paint_device(image, project, settings, image.width(), image.height())
    result = Image.frombytes(
        "RGBA",
        (image.width(), image.height()),
        bytes(image.constBits()),
        "raw",
        "RGBA",
        image.bytesPerLine(),
    )
    if supersample > 1:
        result = result.resize((w, h), Image.Resampling.LANCZOS)
    return result


def export_figure(project: Project, settings: ExportSettings, path: str | Path) -> Path:
    dimensions = ExportDimensions(settings)
    project = copy.deepcopy(project)
    path = Path(path)

    def write(target):
        if settings.format in ("PNG", "TIFF"):
            image = raster_image(project, settings)
            options = {"dpi": (settings.dpi, settings.dpi)}
            if settings.format == "TIFF":
                options["compression"] = "tiff_lzw"
            image.save(target, format=settings.format, **options)
        elif settings.format == "SVG":
            generator = QSvgGenerator()
            generator.setFileName(str(target))
            generator.setSize(QSize(dimensions.width_px, dimensions.height_px))
            generator.setViewBox(QRect(0, 0, dimensions.width_px, dimensions.height_px))
            generator.setResolution(settings.dpi)
            generator.setTitle(project.title)
            generator.setDescription(
                "Vector surface triangles · reference-inspired morphology"
                if project.mesh is not None and project.appearance.render_style == "surface"
                else "ASE structure · vector spheres · covalent radii"
            )
            paint_device(generator, project, settings, dimensions.width_px, dimensions.height_px)
            # Explicit physical dimensions avoid conversion rounding in the SVG device.
            tree = ET.parse(target)
            tree.getroot().set("width", f"{dimensions.width_mm:.8g}mm")
            tree.getroot().set("height", f"{dimensions.height_mm:.8g}mm")
            tree.write(target, encoding="utf-8", xml_declaration=True)
        else:
            writer = QPdfWriter(str(target))
            writer.setTitle(project.title)
            writer.setCreator("Surfaces · ASE / PySide6")
            writer.setResolution(settings.dpi)
            writer.setPageSize(
                QPageSize(
                    QSizeF(dimensions.width_mm, dimensions.height_mm),
                    QPageSize.Unit.Millimeter,
                    "Figure",
                    QPageSize.SizeMatchPolicy.ExactMatch,
                )
            )
            writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)
            paint_device(writer, project, settings, writer.width(), writer.height())
            del writer  # Finish the PDF stream before atomic replacement.
        if not target.exists() or target.stat().st_size == 0:
            raise OSError("The export device did not produce a valid file.")

    atomic_write(path, write)
    return path
