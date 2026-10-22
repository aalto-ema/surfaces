"""Shared vector sphere renderer for interactive views and figure devices."""

import math
from dataclasses import dataclass

import numpy as np
from ase.data import atomic_numbers, covalent_radii
from ase.data.colors import jmol_colors
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from surfaces.model import Project
from surfaces.structures import surface_frame


@dataclass
class ProjectedAtom:
    x: float
    y: float
    radius: float
    depth: float
    site_id: str
    symbol: str
    copy: tuple[int, int]


def element_color(project: Project, symbol: str) -> QColor:
    if symbol in project.appearance.colors:
        return QColor(project.appearance.colors[symbol])
    # Restrained, readily distinguishable metals; remaining elements use Jmol.
    metals = {
        "Pt": "#91a0b5",
        "Au": "#e9b74c",
        "Ag": "#c2ceda",
        "Cu": "#cf8158",
        "Pd": "#718f9e",
        "Ni": "#73a48a",
        "Fe": "#bd776e",
        "Co": "#8187bd",
    }
    if symbol in metals:
        return QColor(metals[symbol])
    number = atomic_numbers[symbol]
    if number >= len(jmol_colors):
        return QColor("#a8b3c3")  # Explicit neutral palette for elements absent from Jmol.
    return QColor.fromRgbF(*map(float, jmol_colors[number]))


def element_radius(project: Project, symbol: str) -> float:
    radius = project.appearance.radii.get(symbol, float(covalent_radii[atomic_numbers[symbol]]))
    if not math.isfinite(radius) or radius <= 0:
        raise ValueError(f"{symbol} radius must be positive and finite.")
    return radius * project.appearance.radius_scale


def basis(project: Project) -> np.ndarray:
    az, el = np.radians([project.camera.azimuth, project.camera.elevation])
    direction = np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])
    right = np.array([-np.sin(az), np.cos(az), 0])
    frame = surface_frame(project.atoms)
    direction = direction @ frame
    right = right @ frame
    up = np.cross(direction, right)
    return np.array([right, up, direction]).T


def legend_layout(project: Project, width: float, height: float):
    symbols = sorted(set(project.atoms.get_chemical_symbols()))
    if project.mesh is not None and project.appearance.render_style == "surface":
        symbols = [project.mesh.element]
    columns = max(1, int((width - 32) // 72))
    rows = math.ceil(len(symbols) / columns)
    footer = min(rows * 28 + 12, height * 0.4)
    return symbols, columns, rows, footer


def project_scene(
    project: Project, width: float, height: float, margin: float = 8, legend: bool | None = None
) -> tuple[list[ProjectedAtom], np.ndarray]:
    """Return depth-sorted atoms and cell edges in the drawing coordinate system."""
    appearance = project.appearance
    positions, symbols, ids, copies = [], [], [], []
    original_ids = project.atoms.arrays["site_ids"]
    for i in range(appearance.copies_x):
        for j in range(appearance.copies_y):
            delta = (i - (appearance.copies_x - 1) / 2) * project.atoms.cell[0] + (
                j - (appearance.copies_y - 1) / 2
            ) * project.atoms.cell[1]
            positions.extend(project.atoms.positions + delta)
            symbols.extend(project.atoms.get_chemical_symbols())
            ids.extend(map(str, original_ids))
            copies.extend([(i, j)] * len(project.atoms))
    positions = np.asarray(positions)
    radii = np.array([element_radius(project, s) for s in symbols])
    center = (positions.min(axis=0) + positions.max(axis=0)) / 2
    projected = (positions - center) @ basis(project)
    corners = np.array(
        [
            i * project.atoms.cell[0] + j * project.atoms.cell[1] + k * project.atoms.cell[2]
            for i in (0, 1)
            for j in (0, 1)
            for k in (0, 1)
        ]
    )
    cell = (corners - center) @ basis(project)
    if project.camera.projection == "Perspective":
        distance = max(float(np.linalg.norm(np.ptp(positions, axis=0))) * 2.5, 10)
        factors = distance / np.maximum(distance - projected[:, 2], distance * 0.1)
        projected[:, :2] *= factors[:, None]
        radii *= factors
        cell[:, :2] *= (distance / np.maximum(distance - cell[:, 2], distance * 0.1))[:, None]
    low = (projected[:, :2] - radii[:, None]).min(axis=0)
    high = (projected[:, :2] + radii[:, None]).max(axis=0)
    if appearance.cell:
        low = np.minimum(low, cell[:, :2].min(axis=0))
        high = np.maximum(high, cell[:, :2].max(axis=0))
    show_legend = appearance.legend if legend is None else legend
    inset = min(width, height) * margin / 100
    footer = legend_layout(project, width, height)[3] if show_legend else 0
    usable = np.array([width - 2 * inset, height - 2 * inset - footer])
    scale = float(np.min(usable / np.maximum(high - low, 1e-6))) * project.camera.zoom
    midpoint = (low + high) / 2
    origin = np.array(
        [
            width / 2 + width * project.camera.pan_x,
            (height - footer) / 2 + height * project.camera.pan_y,
        ]
    )
    xy = (projected[:, :2] - midpoint) * scale
    xy[:, 1] *= -1
    xy += origin
    cell_xy = (cell[:, :2] - midpoint) * scale
    cell_xy[:, 1] *= -1
    cell_xy += origin
    result = [
        ProjectedAtom(
            float(xy[n, 0]),
            float(xy[n, 1]),
            float(radii[n] * scale),
            float(projected[n, 2]),
            ids[n],
            symbols[n],
            copies[n],
        )
        for n in np.argsort(projected[:, 2], kind="stable")
    ]
    return result, cell_xy


def draw_scene(
    painter: QPainter,
    project: Project,
    width: float,
    height: float,
    *,
    transparent: bool = False,
    margin: float = 8,
    legend: bool | None = None,
    axes: bool | None = None,
    selected: set[str] | None = None,
) -> list[ProjectedAtom]:
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    if not transparent:
        painter.fillRect(QRectF(0, 0, width, height), QColor(project.appearance.background))
    if project.mesh is not None and project.appearance.render_style == "surface":
        from surfaces.surface_rendering import draw_surface

        draw_surface(painter, project, width, height, margin, legend)
        atoms, cell = [], np.zeros((8, 2))
    else:
        atoms, cell = project_scene(project, width, height, margin, legend)
    if project.appearance.cell and atoms:
        painter.setPen(QPen(QColor("#99a6b6"), 1.2, Qt.PenStyle.DashLine))
        for a in range(8):
            for bit in (1, 2, 4):
                b = a ^ bit
                if a < b:
                    painter.drawLine(QPointF(*cell[a]), QPointF(*cell[b]))
    for atom in atoms:
        color = element_color(project, atom.symbol)
        painter.setPen(
            QPen(color.darker(145), max(0.6, atom.radius * 0.015))
            if project.appearance.outlines
            else Qt.PenStyle.NoPen
        )
        if project.appearance.shading:
            gradient = QRadialGradient(
                QPointF(atom.x, atom.y),
                atom.radius * 1.05,
                QPointF(atom.x - atom.radius * 0.32, atom.y - atom.radius * 0.38),
            )
            gradient.setColorAt(0, color.lighter(145))
            gradient.setColorAt(0.55, color)
            gradient.setColorAt(1, color.darker(145))
            painter.setBrush(gradient)
        else:
            painter.setBrush(color)
        painter.drawEllipse(QPointF(atom.x, atom.y), atom.radius, atom.radius)
        if selected and atom.site_id in selected:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#2563eb"), 2.2))
            painter.drawEllipse(QPointF(atom.x, atom.y), atom.radius + 2, atom.radius + 2)
    font = QFont("Arial")
    font.setPixelSize(16)  # Scene units: identical text proportions on every paint device.
    painter.setFont(font)
    foreground = (
        QColor("#e5ebf5")
        if QColor(project.appearance.background).lightnessF() < 0.4
        else QColor("#39475a")
    )
    if project.appearance.legend if legend is None else legend:
        unique, columns, rows, footer = legend_layout(project, width, height)
        row_height = (footer - 12) / rows
        font.setPixelSize(max(6, min(16, round(row_height * 0.6))))
        painter.setFont(font)
        for index, symbol in enumerate(unique):
            row, column = divmod(index, columns)
            count = min(columns, len(unique) - row * columns)
            x = (width - count * 72) / 2 + 12 + column * 72
            y = height - footer + 6 + row_height * (row + 0.5)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(element_color(project, symbol))
            radius = min(6, row_height * 0.2)
            painter.drawEllipse(QPointF(x, y), radius, radius)
            painter.setPen(foreground)
            painter.drawText(
                QRectF(x + 13, y - row_height / 2, 55, row_height),
                Qt.AlignmentFlag.AlignVCenter,
                symbol,
            )
        font.setPixelSize(16)
        painter.setFont(font)
    if project.appearance.axes if axes is None else axes:
        matrix = basis(project)
        for vector, label, color in zip(
            np.eye(3), ("x", "y", "z"), ("#bf6262", "#538b73", "#557fba"), strict=True
        ):
            direction = vector @ matrix
            start = QPointF(48, height - 70)
            end = start + QPointF(direction[0] * 28, -direction[1] * 28)
            painter.setPen(QPen(QColor(color), 1.8))
            painter.drawLine(start, end)
            painter.drawText(end + QPointF(3, -3), label)
    return atoms


class Viewport(QWidget):
    selectionChanged = Signal(set)
    cameraChanged = Signal()

    def __init__(self, project: Project):
        super().__init__()
        self.project = project
        self.selected: set[str] = set()
        self.projected: list[ProjectedAtom] = []
        self.press = None
        self.last = None
        self.dragged = False
        self.setMinimumSize(360, 300)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip(
            "Drag to orbit · Shift-drag or middle-drag to pan · Scroll to zoom\n"
            "Click to select · Ctrl/⌘-click for multiple sites"
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        scale = self.width() / 1000
        painter.scale(scale, scale)
        self.projected = draw_scene(
            painter, self.project, 1000, self.height() / scale, selected=self.selected
        )
        painter.end()

    def fit(self):
        self.project.camera.zoom = 1
        self.project.camera.pan_x = self.project.camera.pan_y = 0
        self.cameraChanged.emit()
        self.update()

    def preset(self, name: str):
        az, el = {"Top": (-90, 90), "Side": (-90, 0), "Isometric": (-32, 35)}[name]
        self.project.camera.azimuth, self.project.camera.elevation = az, el
        self.fit()

    def mousePressEvent(self, event):
        self.setFocus()
        self.press = self.last = event.position()
        self.dragged = False

    def mouseMoveEvent(self, event):
        if self.last is None:
            return
        delta = event.position() - self.last
        if (event.position() - self.press).manhattanLength() > 4:
            self.dragged = True
        if event.buttons() & Qt.MouseButton.MiddleButton or (
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self.project.camera.pan_x += delta.x() / self.width()
            self.project.camera.pan_y += delta.y() / self.height()
        elif event.buttons() & Qt.MouseButton.LeftButton:
            self.project.camera.azimuth += delta.x() * 0.4
            self.project.camera.elevation = max(
                -90, min(90, self.project.camera.elevation + delta.y() * 0.4)
            )
        self.last = event.position()
        self.cameraChanged.emit()
        self.update()

    def mouseReleaseEvent(self, event):
        if not self.dragged and event.button() == Qt.MouseButton.LeftButton:
            scale = self.width() / 1000
            x, y = event.position().x() / scale, event.position().y() / scale
            picked = next(
                (
                    a
                    for a in reversed(self.projected)
                    if (a.x - x) ** 2 + (a.y - y) ** 2 <= a.radius**2
                ),
                None,
            )
            additive = event.modifiers() & (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier
            )
            if not additive:
                self.selected.clear()
            if picked:
                if additive and picked.site_id in self.selected:
                    self.selected.remove(picked.site_id)
                else:
                    self.selected.add(picked.site_id)
            self.selectionChanged.emit(set(self.selected))
            self.update()
        self.last = None

    def wheelEvent(self, event):
        self.project.camera.zoom = max(
            0.15, min(8, self.project.camera.zoom * math.exp(event.angleDelta().y() / 900))
        )
        self.cameraChanged.emit()
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.selected.clear()
            self.selectionChanged.emit(set())
            self.update()
        elif event.key() == Qt.Key.Key_F:
            self.fit()
        else:
            super().keyPressEvent(event)
