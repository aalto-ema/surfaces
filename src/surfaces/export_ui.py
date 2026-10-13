"""Physical sizing, export presets, and a responsive figure preview."""

import copy
import io
from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from surfaces.exporting import ExportDimensions, export_figure, raster_image
from surfaces.model import ExportSettings
from surfaces.ui_common import Tasks, decimal, heading, integer


class FigurePreview(QWidget):
    def __init__(self):
        super().__init__()
        self.pixmap = None
        self.setMinimumSize(400, 320)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor("#e5eaf1"))
        if self.pixmap is None:
            return
        size = self.pixmap.size().scaled(
            self.size() - QSize(30, 30), Qt.AspectRatioMode.KeepAspectRatio
        )
        x, y = (self.width() - size.width()) // 2, (self.height() - size.height()) // 2
        painter.save()
        painter.setClipRect(x, y, size.width(), size.height())
        for row in range(y, y + size.height(), 14):
            for col in range(x, x + size.width(), 14):
                color = "#ffffff" if ((row - y) // 14 + (col - x) // 14) % 2 else "#dce1e9"
                painter.fillRect(col, row, 14, 14, QColor(color))
        painter.drawPixmap(x, y, size.width(), size.height(), self.pixmap)
        painter.restore()
        painter.end()


class ExportDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.project = copy.deepcopy(window.project)
        self.setWindowTitle("Export scientific figure")
        self.resize(1000, 680)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(180)
        self.timer.timeout.connect(self.make_preview)
        self.tasks = Tasks(self)
        self.tasks.result.connect(self.preview_ready)
        self.tasks.error.connect(self.preview_error)
        self.tasks.idle.connect(self.preview_idle)
        self.dismiss_requested = False
        self.pending = False
        self.valid = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.addWidget(heading("Export figure"))
        outer.addWidget(
            heading(
                "Drawn from the same scene and camera. PNG/TIFF are antialiased; "
                "PDF/SVG retain vector spheres and annotations.",
                True,
            )
        )
        main = QHBoxLayout()
        controls = QVBoxLayout()
        form = QFormLayout()
        form.setSpacing(12)
        self.format = QComboBox()
        self.format.addItems(["PNG", "TIFF", "PDF", "SVG"])
        self.unit = QComboBox()
        self.unit.addItems(["px", "mm", "in", "pt"])
        self.width = decimal(1800, 0.01, 20000, "", 3)
        self.height = decimal(1400, 0.01, 20000, "", 3)
        self.dpi = integer(300, 36, 1200)
        self.margin = decimal(8, 0, 30, " %", 1)
        self.transparent = QCheckBox("Transparent / unpainted background")
        self.legend = QCheckBox("Element legend")
        self.axes = QCheckBox("Cartesian axes")
        self.preset = QComboBox()
        self.preset.addItem("Custom settings")
        self.preset.addItems(sorted(self.project.export_presets))
        for label, widget in [
            ("Preset", self.preset),
            ("Format", self.format),
            ("Size units", self.unit),
            ("Width", self.width),
            ("Height", self.height),
            ("DPI", self.dpi),
            ("Margin", self.margin),
        ]:
            form.addRow(label, widget)
        controls.addLayout(form)
        for widget in (self.transparent, self.legend, self.axes):
            controls.addWidget(widget)
        self.dimensions = heading("", True)
        controls.addWidget(self.dimensions)
        controls.addWidget(
            heading(
                "Vector sizing uses physical dimensions. PDF transparency "
                "means no page background fill. Camera zoom and pan are retained.",
                True,
            )
        )
        save_preset = QPushButton("Save these settings as a preset…")
        save_preset.clicked.connect(self.save_preset)
        controls.addWidget(save_preset)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setProperty("role", "error")
        controls.addWidget(self.error)
        controls.addStretch()
        control_widget = QWidget()
        control_widget.setLayout(controls)
        control_widget.setFixedWidth(305)
        main.addWidget(control_widget)
        self.preview = FigurePreview()
        main.addWidget(self.preview, 1)
        outer.addLayout(main, 1)
        footer = QHBoxLayout()
        footer.addWidget(heading("Checkerboard indicates transparency; it is not exported.", True))
        footer.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        self.export_button = QPushButton("Export figure…")
        self.export_button.setProperty("primary", True)
        self.export_button.clicked.connect(self.export)
        footer.addWidget(self.export_button)
        outer.addLayout(footer)
        self.set_settings(self.project.export)
        self.previous_unit = self.unit.currentText()
        self.unit.currentTextChanged.connect(self.unit_changed)
        self.preset.currentTextChanged.connect(self.load_preset)
        for widget in (self.width, self.height, self.dpi, self.margin):
            widget.valueChanged.connect(self.schedule_preview)
        self.format.currentTextChanged.connect(self.schedule_preview)
        for widget in (self.transparent, self.legend, self.axes):
            widget.toggled.connect(self.schedule_preview)
        self.schedule_preview()

    def settings(self):
        return ExportSettings(
            self.format.currentText(),
            self.width.value(),
            self.height.value(),
            self.unit.currentText(),
            self.dpi.value(),
            self.transparent.isChecked(),
            self.margin.value(),
            self.legend.isChecked(),
            self.axes.isChecked(),
        )

    def set_settings(self, settings):
        for widget in (
            self.format,
            self.unit,
            self.width,
            self.height,
            self.dpi,
            self.margin,
            self.transparent,
            self.legend,
            self.axes,
        ):
            widget.blockSignals(True)
        self.format.setCurrentText(settings.format)
        self.unit.setCurrentText(settings.unit)
        self.width.setValue(settings.width)
        self.height.setValue(settings.height)
        self.dpi.setValue(settings.dpi)
        self.margin.setValue(settings.margin)
        self.transparent.setChecked(settings.transparent)
        self.legend.setChecked(settings.legend)
        self.axes.setChecked(settings.axes)
        for widget in (
            self.format,
            self.unit,
            self.width,
            self.height,
            self.dpi,
            self.margin,
            self.transparent,
            self.legend,
            self.axes,
        ):
            widget.blockSignals(False)
        self.previous_unit = settings.unit

    def unit_changed(self, name):
        factors = {"px": 25.4 / self.dpi.value(), "mm": 1, "in": 25.4, "pt": 25.4 / 72}
        ratio = factors[self.previous_unit] / factors[name]
        self.width.setValue(self.width.value() * ratio)
        self.height.setValue(self.height.value() * ratio)
        self.previous_unit = name
        self.schedule_preview()

    def load_preset(self, name):
        if name in self.project.export_presets:
            self.set_settings(ExportSettings(**self.project.export_presets[name]))
            self.schedule_preview()

    def save_preset(self):
        try:
            ExportDimensions(self.settings())
        except ValueError as exc:
            self.error.setText(str(exc))
            return
        name, accepted = QInputDialog.getText(self, "Save export preset", "Preset name:")
        name = name.strip()
        if not accepted or not name:
            return
        if len(name) > 100:
            self.error.setText("Use a preset name of at most 100 characters.")
            return
        if (
            name in self.project.export_presets
            and QMessageBox.question(self, "Replace preset?", f"Replace “{name}”?")
            != QMessageBox.StandardButton.Yes
        ):
            return
        data = asdict(self.settings())
        self.window.record()
        self.window.project.export_presets[name] = data
        self.project.export_presets[name] = data
        if self.preset.findText(name) < 0:
            self.preset.addItem(name)
        self.preset.setCurrentText(name)
        self.window.refresh()

    def schedule_preview(self, *args):
        self.export_button.setEnabled(False)
        self.valid = False
        self.pending = True
        self.timer.start()

    def make_preview(self):
        if self.tasks.thread is not None:
            return
        self.pending = False
        settings = self.settings()
        try:
            dims = ExportDimensions(settings)
            self.dimensions.setText(
                f"{dims.width_px} × {dims.height_px} px\n"
                f"{dims.width_mm:.2f} × {dims.height_mm:.2f} mm · {settings.dpi} dpi"
            )
        except ValueError as exc:
            self.preview_error(str(exc))
            return
        self.error.setText("Rendering preview…")

        def work():
            image = raster_image(self.project, settings, preview=True)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            return buffer.getvalue()

        self.tasks.start(work)

    def preview_ready(self, data):
        if not self.pending:
            self.preview.pixmap = QPixmap.fromImage(QImage.fromData(data))
            self.preview.update()
            self.error.clear()
            self.valid = True

    def preview_error(self, message):
        self.error.setText(message)
        self.valid = False

    def preview_idle(self):
        if self.dismiss_requested:
            super().reject()
        elif self.pending:
            self.make_preview()
        else:
            self.export_button.setEnabled(self.valid)

    def reject(self):
        self.timer.stop()
        if self.tasks.thread is not None:
            self.dismiss_requested = True
        else:
            super().reject()

    def closeEvent(self, event):
        if self.tasks.thread is not None:
            self.dismiss_requested = True
            event.ignore()
        else:
            event.accept()

    def export(self):
        settings = self.settings()
        suffix = {"PNG": ".png", "TIFF": ".tiff", "PDF": ".pdf", "SVG": ".svg"}[settings.format]
        path, _ = QFileDialog.getSaveFileName(
            self, "Export figure", f"surface{suffix}", f"{settings.format} figure (*{suffix})"
        )
        if not path:
            return
        if not path.lower().endswith(suffix):
            path += suffix
            if (
                Path(path).exists()
                and QMessageBox.question(self, "Replace figure?", f"Replace {Path(path).name}?")
                != QMessageBox.StandardButton.Yes
            ):
                return
        self.window.record()
        self.window.project.export = settings
        snapshot = copy.deepcopy(self.window.project)

        def complete(result):
            self.window.completed_message = f"Figure exported to {result}"

        self.accept()
        self.window.run_task(
            lambda: export_figure(snapshot, settings, path),
            complete,
            f"Exporting {settings.format} figure…",
        )
