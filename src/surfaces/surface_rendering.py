"""Shared vector triangle renderer for morphology previews and all figure devices."""

import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF


def surface_projection(project, width, height, margin=8, legend=None):
    from surfaces.rendering import basis, legend_layout

    vertices = project.mesh.vertices
    matrix = basis(project)
    center = (vertices.min(0) + vertices.max(0)) / 2
    projected = (vertices - center) @ matrix
    if project.camera.projection == "Perspective":
        distance = max(float(np.linalg.norm(np.ptp(vertices, axis=0))) * 2.5, 10)
        projected[:, :2] *= (distance / np.maximum(distance - projected[:, 2], distance * 0.1))[
            :, None
        ]
    low, high = projected[:, :2].min(0), projected[:, :2].max(0)
    inset = min(width, height) * margin / 100
    show_legend = project.appearance.legend if legend is None else legend
    footer = legend_layout(project, width, height)[3] if show_legend else 0
    scale = (
        min(
            (width - 2 * inset) / max(high[0] - low[0], 1e-9),
            (height - 2 * inset - footer) / max(high[1] - low[1], 1e-9),
        )
        * project.camera.zoom
    )
    xy = (projected[:, :2] - (low + high) / 2) * scale
    xy[:, 1] *= -1
    xy += [
        width / 2 + width * project.camera.pan_x,
        (height - footer) / 2 + height * project.camera.pan_y,
    ]
    return xy, projected[:, 2], matrix


def draw_surface(painter, project, width, height, margin=8, legend=None):
    from surfaces.rendering import element_color

    painter.save()
    # Shared triangle edges must not independently blend against the background.
    # Raster exports supersample the completed surface before downsampling.
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    xy, depths, matrix = surface_projection(project, width, height, margin, legend)
    mesh = project.mesh
    triangles = mesh.vertices[mesh.faces]
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    normals /= np.maximum(np.linalg.norm(normals, axis=1)[:, None], 1e-20)
    # Outward direction independent of marching-cubes orientation convention.
    center = (mesh.vertices.min(0) + mesh.vertices.max(0)) / 2
    # Choose the global winding from signed volume, preserving concave normals.
    volume = np.einsum(
        "ij,ij->i",
        triangles[:, 0] - center,
        np.cross(triangles[:, 1] - center, triangles[:, 2] - center),
    ).sum()
    if volume < 0:
        normals *= -1
    face_normals = normals @ matrix
    visible = face_normals[:, 2] > 1e-10
    if project.camera.projection == "Perspective":
        distance = max(float(np.linalg.norm(np.ptp(mesh.vertices, axis=0))) * 2.5, 10)
        positions = (triangles.mean(1) - center) @ matrix
        eye = np.array([0, 0, distance]) - positions
        visible = np.einsum("ij,ij->i", face_normals, eye) > 0
    # Area-independent vertex normals smooth the curved envelope while keeping
    # the triangulated export explicit. Flat regions retain a constant normal.
    vertex_normals = np.zeros_like(mesh.vertices)
    for corner in range(3):
        np.add.at(vertex_normals, mesh.faces[:, corner], normals)
    vertex_normals /= np.maximum(np.linalg.norm(vertex_normals, axis=1)[:, None], 1e-20)
    normals = vertex_normals[mesh.faces].mean(axis=1)
    normals /= np.maximum(np.linalg.norm(normals, axis=1)[:, None], 1e-20)
    view_normals = normals @ matrix
    light = np.array([-0.35, 0.5, 0.8])
    light /= np.linalg.norm(light)
    diffuse = np.maximum(view_normals @ light, 0)
    specular = np.maximum(view_normals @ np.array([-0.15, 0.25, 0.9566]), 0) ** 24
    rgb = np.array(element_color(project, mesh.element).getRgbF()[:3])
    painter.setPen(Qt.PenStyle.NoPen)
    order = np.argsort(depths[mesh.faces].mean(1), kind="stable")
    for index in order[visible[order]]:
        brightness = 0.38 + 0.65 * diffuse[index]
        color = np.clip(rgb * brightness + 0.24 * specular[index], 0, 1)
        if not project.appearance.shading:
            color = rgb
        shade = QColor.fromRgbF(*map(float, color))
        painter.setBrush(shade)
        # A subpixel same-color edge seals antialias seams between adjacent faces.
        painter.setPen(QPen(shade, 0.35))
        painter.drawPolygon(QPolygonF([QPointF(*point) for point in xy[mesh.faces[index]]]))
    painter.restore()
