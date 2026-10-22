import json
from dataclasses import replace

import numpy as np
import pytest
from ase.cluster import wulff_construction
from ase.cluster.cubic import BodyCenteredCubic, FaceCenteredCubic, SimpleCubic
from scipy.spatial import cKDTree

from surfaces.model import ParticleSpec, StructureSpec
from surfaces.particles import SHAPES, particle_frame
from surfaces.persistence import from_data, to_data
from surfaces.structures import build_project


def recipe(shape="cube", **kwargs):
    return StructureSpec(element="Au", a=4.08, particle=ParticleSpec(shape=shape, **kwargs))


def centered(atoms):
    return atoms.positions - (atoms.positions.max(0) + atoms.positions.min(0)) / 2


@pytest.mark.parametrize("shape", [s for s in SHAPES if s not in ("helicoid_iii", "chiral_rod")])
def test_all_shapes_finite_identified_reproducible_and_roundtrip(shape):
    spec = recipe(shape)
    project = build_project(spec)
    assert 1 < len(project.atoms) <= 20_000
    assert not project.atoms.pbc.any()
    assert len(set(project.atoms.arrays["site_ids"])) == len(project.atoms)
    np.testing.assert_allclose(project.atoms.positions.min(0), spec.vacuum)
    np.testing.assert_allclose(
        project.atoms.cell.lengths() - project.atoms.positions.max(0), spec.vacuum
    )
    repeated = build_project(spec)
    np.testing.assert_allclose(project.atoms.positions, repeated.atoms.positions)
    assert not set(project.atoms.arrays["site_ids"]) & set(repeated.atoms.arrays["site_ids"])
    restored = from_data(json.loads(json.dumps(to_data(project))))
    assert restored.spec == spec
    np.testing.assert_array_equal(restored.atoms.positions, project.atoms.positions)
    assert restored.provenance == json.loads(json.dumps(to_data(project)))["provenance"]
    assert project.provenance["achieved_atoms"] == len(project.atoms)
    assert project.provenance["relaxed"] is False


@pytest.mark.parametrize(
    "crystal,builder", [("fcc", FaceCenteredCubic), ("bcc", BodyCenteredCubic), ("sc", SimpleCubic)]
)
@pytest.mark.parametrize(
    "shape,surfaces,layers",
    [
        ("cube", [(1, 0, 0)], [4]),
        ("octahedron", [(1, 1, 1)], [4]),
        ("cuboctahedron", [(1, 0, 0), (1, 1, 1)], [4, 4]),
        ("facets", [(1, 0, 0), (1, 1, 1)], [6, 4]),
    ],
)
def test_faceted_geometry_agrees_with_ase(crystal, builder, shape, surfaces, layers):
    if shape == "cuboctahedron" and crystal != "fcc":
        with pytest.raises(ValueError, match="FCC"):
            build_project(replace(recipe(shape), crystal=crystal))
        return
    result = build_project(replace(recipe(shape), crystal=crystal)).atoms
    expected = builder("Au", surfaces, layers, latticeconstant=4.08)
    np.testing.assert_allclose(centered(result), centered(expected), atol=1e-10)
    np.testing.assert_array_equal(result.numbers, expected.numbers)


def test_fcc_cuboctahedron_retains_squares_and_triangles():
    from scipy.spatial import ConvexHull

    atoms = build_project(recipe("cuboctahedron")).atoms
    normals = ConvexHull(atoms.positions).equations[:, :3]
    nonzero = np.sum(abs(normals) > 1e-6, axis=1)
    assert set(nonzero) == {1, 3}
    assert len({tuple(np.round(n, 6)) for n in normals}) == 14


@pytest.mark.parametrize("crystal", ["fcc", "bcc", "sc"])
@pytest.mark.parametrize("rounding", ["closest", "above", "below"])
def test_wulff_size_energies_and_geometry_match_ase(rounding, crystal):
    spec = recipe(
        "wulff",
        target_atoms=500,
        rounding=rounding,
        illustrative=False,
        energy_unit="J/m²",
        energy_source="User test values, not material reference data",
    )
    spec.crystal = crystal
    result = build_project(spec)
    expected = wulff_construction(
        "Au",
        [(1, 0, 0), (1, 1, 1)],
        [1.0, 0.9],
        500,
        crystal,
        rounding=rounding,
        latticeconstant=4.08,
    )
    np.testing.assert_allclose(centered(result.atoms), centered(expected), atol=1e-10)
    assert result.provenance["requested_atoms"] == 500
    assert result.provenance["energy_unit"] == "J/m²"
    assert result.provenance["energy_source"] == spec.particle.energy_source
    assert result.provenance["illustrative_energies"] is False
    if rounding == "above":
        assert len(result.atoms) >= 500
    elif rounding == "below":
        assert len(result.atoms) <= 500


@pytest.mark.parametrize("axis", ["001", "110", "111"])
def test_sphere_radius_and_orientation_preserve_crystal_distances(axis):
    spec = recipe("sphere", width=20, axis=axis)
    xyz = centered(build_project(spec).atoms)
    assert np.linalg.norm(xyz, axis=1).max() <= 10 + 1e-8
    distances = cKDTree(xyz).query(xyz, k=2)[0][:, 1]
    np.testing.assert_allclose(distances, spec.a / np.sqrt(2))
    frame = particle_frame(axis)
    np.testing.assert_allclose(frame @ frame.T, np.eye(3), atol=1e-10)
    assert np.linalg.det(frame) == pytest.approx(1)


def test_111_triangle_is_a_thin_single_crystal_prism():
    spec = recipe("triangle", axis="111", width=28, thickness=8)
    atoms = build_project(spec).atoms
    assert np.ptp(atoms.positions[:, 2]) <= 8 + 1e-8
    assert np.ptp(atoms.positions[:, 0]) > 16
    nearest = cKDTree(atoms.positions).query(atoms.positions, k=2)[0][:, 1]
    np.testing.assert_allclose(nearest, spec.a / np.sqrt(2))
    assert "[111]" in build_project(spec).provenance["orientation"]


@pytest.mark.parametrize("shape", ["twisted_rod", "helicoid"])
def test_twist_sign_produces_distinct_mirror_partners(shape):
    positive = centered(build_project(recipe(shape, twist=120)).atoms)
    negative = centered(build_project(recipe(shape, twist=-120)).atoms)
    mirrored = positive.copy()
    mirrored[:, 1] *= -1
    assert len(positive) == len(negative)
    np.testing.assert_allclose(cKDTree(negative).query(mirrored)[0], 0, atol=1e-8)
    assert cKDTree(negative).query(positive)[0].max() > 0.1


def test_twisted_rod_has_specified_continuous_rotation():
    straight = centered(build_project(recipe("prism")).atoms)
    twisted = centered(build_project(recipe("twisted_rod")).atoms)
    angle = np.radians(120) * straight[:, 2] / 60
    expected = straight.copy()
    expected[:, 0] = straight[:, 0] * np.cos(angle) - straight[:, 1] * np.sin(angle)
    expected[:, 1] = straight[:, 0] * np.sin(angle) + straight[:, 1] * np.cos(angle)
    np.testing.assert_allclose(twisted, expected, atol=1e-9)


def test_helicoid_keeps_atoms_on_undeformed_parent_lattice():
    xyz = centered(build_project(recipe("helicoid")).atoms)
    # FCC sites lie on a half-a grid; nearest-neighbor distances remain unchanged.
    np.testing.assert_allclose(xyz / (4.08 / 2), np.round(xyz / (4.08 / 2)), atol=1e-8)
    distances = cKDTree(xyz).query(xyz, k=2)[0][:, 1]
    np.testing.assert_allclose(distances, 4.08 / np.sqrt(2))


@pytest.mark.parametrize(
    "change",
    [
        {"shape": "unknown"},
        {"width": float("nan")},
        {"length": -1},
        {"shells": True},
        {"axis": "123"},
        {"twist": 400},
        {"target_atoms": 20001},
        {"rounding": "ignore"},
        {"energy_unit": "eV/atom"},
        {"energy_source": ""},
        {"illustrative": "yes"},
        {"facets": []},
        {"facets": [{"miller": [0, 0, 0], "layers": 4, "energy": 1}]},
        {"facets": [{"miller": [2, 0, 0], "layers": 4, "energy": 1}]},
        {"facets": [{"miller": [1, 0, 0], "layers": 4, "energy": -1}]},
    ],
)
def test_bad_particle_recipes_rejected_on_build_and_load(change):
    spec = recipe("wulff")
    bad = replace(spec, particle=replace(spec.particle, **change))
    with pytest.raises(ValueError):
        build_project(bad)
    data = json.loads(json.dumps(to_data(build_project(spec))))
    data["spec"]["particle"].update(change)
    with pytest.raises(ValueError):
        from_data(data)


@pytest.mark.parametrize("crystal,element", [("hcp", "Au"), ("spinel", "NiFe2O4"), ("fcc", "PtO")])
def test_unsupported_parent_does_not_become_elemental_approximation(crystal, element):
    with pytest.raises(ValueError):
        build_project(replace(recipe(), crystal=crystal, element=element))


def test_envelope_resource_limit_before_repeating(monkeypatch):
    from ase import Atoms

    def repeat(*args, **kwargs):
        pytest.fail("Oversized envelope reached allocation")

    monkeypatch.setattr(Atoms, "repeat", repeat)
    with pytest.raises(ValueError, match="250,000"):
        build_project(recipe("sphere", width=500))


def test_facet_resource_limit_before_candidate_allocation(monkeypatch):
    from surfaces import particles

    monkeypatch.setattr(particles, "MAX_CANDIDATES", 100)
    with pytest.raises(ValueError, match="250,000"):
        build_project(recipe("cube", shells=4))


def test_alloy_assignment_preserves_particle_geometry_and_identity():
    from surfaces.composition import substitute

    project = build_project(recipe())
    original = project.atoms.copy()
    project.atoms, operation = substitute(original, [("Au", 70), ("Pt", 30)], seed=7)
    project.operations.append(operation)
    assert operation["counts"]["Pt"] > 0
    np.testing.assert_array_equal(project.atoms.positions, original.positions)
    np.testing.assert_array_equal(project.atoms.arrays["site_ids"], original.arrays["site_ids"])
    restored = from_data(json.loads(json.dumps(to_data(project))))
    np.testing.assert_array_equal(restored.atoms.numbers, project.atoms.numbers)
    assert not restored.atoms.pbc.any()


def test_finite_particle_rejects_periodic_display_copies_on_save_and_load():
    project = build_project(recipe())
    project.appearance.copies_x = 2
    with pytest.raises(ValueError, match="periodicity"):
        to_data(project)
    project.appearance.copies_x = 1
    data = json.loads(json.dumps(to_data(project)))
    data["appearance"]["copies_y"] = 2
    with pytest.raises(ValueError, match="periodicity"):
        from_data(data)


def test_legacy_schemas_and_all_committed_examples_still_open():
    from pathlib import Path

    from surfaces.persistence import load_project

    for path in Path("examples").glob("*.surfaces.json"):
        project = load_project(path)
        assert len(project.atoms)
        assert to_data(project)["schema_version"] == 4


def test_final_count_limit_and_single_atom_envelope():
    with pytest.raises(ValueError, match="20,000"):
        build_project(recipe("cube", shells=30))
    single = build_project(recipe("sphere", width=0.1))
    assert len(single.atoms) == 1
    assert single.provenance["minimum_distance_angstrom"] is None
