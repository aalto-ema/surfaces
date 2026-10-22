import json
from collections import Counter
from dataclasses import replace

import numpy as np
import pytest
from scipy.spatial import cKDTree

from surfaces.model import ParticleSpec, StructureSpec
from surfaces.morphology import ROTATIONS, bounds, envelope_field
from surfaces.persistence import from_data, to_data
from surfaces.structures import build_project


def spec(shape="helicoid_iii", **changes):
    p = ParticleSpec(shape=shape, mesh_resolution=32, twist=45, **changes)
    return StructureSpec(element="Au", crystal="fcc", a=4.08, particle=p)


def json_data(project):
    return json.loads(json.dumps(to_data(project)))


def test_cubic_envelope_has_24_proper_rotations_and_is_chiral():
    p = spec().particle
    points = np.random.default_rng(9).uniform(-0.55, 0.55, (1200, 3)) * p.width
    expected = envelope_field(points, p)
    assert len(ROTATIONS) == 24
    for rotation in ROTATIONS:
        assert np.linalg.det(rotation) == pytest.approx(1)
        np.testing.assert_allclose(envelope_field(points @ rotation, p), expected, atol=1e-12)
    mirror = points * [-1, 1, 1]
    other = replace(p, handedness=-1)
    np.testing.assert_allclose(envelope_field(mirror, other), expected, atol=1e-12)
    assert np.max(abs(envelope_field(mirror, p) - expected)) > 0.01


def test_rod_has_fourfold_and_twofold_rotations_and_mirror_partners():
    p = spec("chiral_rod").particle
    points = np.random.default_rng(12).uniform(-0.55, 0.55, (1200, 3)) * [
        p.width,
        p.width,
        p.length,
    ]
    expected = envelope_field(points, p)
    z90 = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])
    np.testing.assert_allclose(envelope_field(points @ z90, p), expected, atol=1e-12)
    np.testing.assert_allclose(envelope_field(points * [1, -1, -1], p), expected, atol=1e-12)
    mirrored = points * [-1, 1, 1]
    np.testing.assert_allclose(
        envelope_field(mirrored, replace(p, handedness=-1)), expected, atol=1e-12
    )
    assert np.max(abs(envelope_field(mirrored, p) - expected)) > 0.01
    crossed = replace(p, crossed_ridges=True)
    np.testing.assert_allclose(
        envelope_field(mirrored, crossed), envelope_field(points, crossed), atol=1e-12
    )


@pytest.mark.parametrize("shape", ["helicoid_iii", "chiral_rod"])
def test_surface_closed_core_solid_and_atoms_undeformed(shape):
    recipe = spec(shape)
    project = build_project(recipe)
    mesh = project.mesh
    edges = Counter(
        tuple(sorted(edge))
        for face in mesh.faces
        for edge in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0]))
    )
    assert set(edges.values()) == {2}
    assert len(project.atoms) > 0
    assert not project.atoms.pbc.any()
    assert project.appearance.render_style == "surface"
    xyz = project.atoms.positions - bounds(recipe.particle) - recipe.vacuum
    assert (envelope_field(xyz, recipe.particle) <= 1e-8).all()
    np.testing.assert_allclose(xyz / (recipe.a / 2), np.round(xyz / (recipe.a / 2)), atol=1e-10)
    nearest = cKDTree(xyz).query(xyz, k=2)[0][:, 1]
    assert nearest.min() == pytest.approx(recipe.a / np.sqrt(2))
    assert envelope_field(np.array([[0.0, 0.0, 0.0]]), recipe.particle)[0] < 0
    assert project.provenance["lattice_deformation"] is False
    restored = from_data(json_data(project))
    assert restored.spec == project.spec
    np.testing.assert_array_equal(restored.mesh.faces, mesh.faces)
    np.testing.assert_allclose(restored.mesh.vertices, mesh.vertices)


@pytest.mark.parametrize("shape", ["helicoid_iii", "chiral_rod"])
def test_experimental_scale_continuum_has_no_fake_atoms(shape):
    recipe = spec(shape, atomistic=False)
    recipe.particle.width = 1500
    recipe.particle.length = 3000
    project = build_project(recipe)
    assert len(project.atoms) == len(project.original) == 0
    assert project.mesh is not None
    assert "continuum" in project.provenance["representation"]
    restored = from_data(json_data(project))
    assert len(restored.atoms) == 0
    assert restored.appearance.render_style == "surface"
    restored.appearance.render_style = "atoms"
    with pytest.raises(ValueError, match="continuum"):
        to_data(restored)
    recipe.particle.atomistic = True
    with pytest.raises(ValueError, match="Disable 'Build ASE atoms'"):
        build_project(recipe)


@pytest.mark.parametrize(
    "field,value",
    [
        ("gap_depth", 0.49),
        ("gap_width", float("nan")),
        ("groove_angle", 0),
        ("ridge_width", 0),
        ("ridge_height", 0.9),
        ("mesh_resolution", 1000),
        ("handedness", 0),
        ("atomistic", 1),
        ("crossed_ridges", "yes"),
    ],
)
def test_invalid_morphology_settings_rejected(field, value):
    recipe = spec()
    setattr(recipe.particle, field, value)
    with pytest.raises(ValueError):
        build_project(recipe)


def test_malformed_mesh_rejected_on_load():
    data = json_data(build_project(spec()))
    data["mesh"]["faces"][0][0] = 10**9
    with pytest.raises(ValueError, match="mesh"):
        from_data(data)
    data = json_data(build_project(spec(atomistic=False)))
    data["atoms"]["cell"][0][0] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        from_data(data)


def test_envelope_parameters_change_grooves_without_hollowing_core():
    p = spec().particle
    points = np.random.default_rng(4).uniform(-0.5, 0.5, (5000, 3)) * p.width
    narrow = envelope_field(points, replace(p, gap_depth=0.1)) < 0
    deep = envelope_field(points, replace(p, gap_depth=0.35)) < 0
    assert np.count_nonzero(deep) < np.count_nonzero(narrow)
    assert not np.any(deep & ~narrow)
    core = points[np.max(abs(points), axis=1) < p.width * 0.18]
    assert (envelope_field(core, p) < 0).all()
