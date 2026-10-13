import numpy as np
import pytest

from surfaces.model import StructureSpec
from surfaces.rendering import project_scene
from surfaces.structures import build_project


@pytest.mark.parametrize("az,el", [(-90, 90), (-90, 0), (-32, 35), (100, -35)])
@pytest.mark.parametrize("projection", ["Orthographic", "Perspective"])
def test_fit_includes_atomic_extents_in_all_views(az, el, projection):
    p = build_project(StructureSpec())
    p.camera.azimuth, p.camera.elevation, p.camera.projection = az, el, projection
    atoms, _ = project_scene(p, 1000, 750)
    for atom in atoms:
        assert atom.x - atom.radius > 0
        assert atom.x + atom.radius < 1000
        assert atom.y - atom.radius > 0
        assert atom.y + atom.radius < 710  # Reserved legend footer.
    assert all(a.depth <= b.depth for a, b in zip(atoms, atoms[1:], strict=False))


def test_display_replicas_and_appearance_do_not_mutate_geometry():
    p = build_project(StructureSpec())
    xyz = p.atoms.positions.copy()
    p.appearance.copies_x = 2
    p.appearance.radii["Pt"] = 2
    atoms, _ = project_scene(p, 1000, 750)
    assert len(atoms) == 200
    assert len({a.site_id for a in atoms}) == 100
    np.testing.assert_array_equal(xyz, p.atoms.positions)


def test_top_view_follows_rotated_imported_surface_normal():
    p = build_project(StructureSpec())
    p.camera.elevation = 90
    original, _ = project_scene(p, 1000, 750)
    p.atoms.rotate(67, "x", rotate_cell=True)
    rotated, _ = project_scene(p, 1000, 750)
    first = {a.site_id: (a.x, a.y, a.radius) for a in original}
    second = {a.site_id: (a.x, a.y, a.radius) for a in rotated}
    for site in first:
        np.testing.assert_allclose(first[site], second[site], atol=1e-10)


def test_many_elements_wrap_legend_and_missing_jmol_color_is_safe():
    from surfaces.rendering import element_color, legend_layout

    p = build_project(StructureSpec())
    p.atoms.numbers[:20] = np.arange(1, 21)
    symbols, columns, rows, footer = legend_layout(p, 1000, 750)
    assert len(symbols) == 21
    assert rows == 2
    assert columns == 13
    assert footer == 68
    assert element_color(p, "Og").isValid()
    scene, _ = project_scene(p, 1000, 750)
    assert max(atom.y + atom.radius for atom in scene) < 750 - footer
