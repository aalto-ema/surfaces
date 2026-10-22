from collections import Counter
from dataclasses import replace

import numpy as np
import pytest
from ase.neighborlist import neighbor_list

from surfaces.compounds import EXAMPLES, build_compound_bulk, parse_formula
from surfaces.model import StructureSpec
from surfaces.persistence import load_project, save_project
from surfaces.structures import build_project, layer_indices


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda e: e.formula)
def test_example_bulk_and_slab_stoichiometry_and_vacuum(example):
    spec = example.spec()
    bulk, info = build_compound_bulk(spec)
    project = build_project(spec)
    bulk_counts = Counter(bulk.get_chemical_symbols())
    slab_counts = Counter(project.atoms.get_chemical_symbols())
    factor = spec.nx * spec.ny * spec.layers
    assert slab_counts == {s: n * factor for s, n in bulk_counts.items()}
    assert project.provenance["bulk_formula_ratio"] == parse_formula(example.formula)[1]
    assert list(project.atoms.pbc) == [True, True, False]
    assert project.atoms.positions[:, 2].min() == pytest.approx(spec.vacuum)
    assert project.atoms.cell[2, 2] - project.atoms.positions[:, 2].max() == pytest.approx(
        spec.vacuum
    )
    assert len(set(project.atoms.arrays["site_ids"])) == len(project.atoms)
    assert len(set(layer_indices(project.atoms))) > spec.layers


def test_pto_published_wyckoff_basis_and_coordination():
    atoms, _ = build_compound_bulk(EXAMPLES[0].spec())
    assert Counter(atoms.get_chemical_symbols()) == {"Pt": 2, "O": 2}
    pt = atoms.get_scaled_positions()[atoms.numbers == 78]
    oxygen = atoms.get_scaled_positions()[atoms.numbers == 8]
    np.testing.assert_allclose(pt, [(0, 0.5, 0), (0.5, 0, 0.5)])
    np.testing.assert_allclose(oxygen, [(0, 0, 0.25), (0, 0, 0.75)])
    first, second = neighbor_list("ij", atoms, 2.1)
    oxygen_neighbors = np.bincount(first[atoms.numbers[second] == 8], minlength=len(atoms))
    assert oxygen_neighbors[atoms.numbers == 78].tolist() == [4, 4]


def test_inverse_spinel_occupancy_coordination_and_seed():
    spec = EXAMPLES[1].spec()
    atoms, info = build_compound_bulk(spec)
    assert info["tetrahedral_counts"] == {"Fe": 8}
    assert info["octahedral_counts"] == {"Ni": 8, "Fe": 8}
    assert Counter(atoms.get_chemical_symbols()) == {"Ni": 8, "Fe": 16, "O": 32}
    first, second = neighbor_list("ij", atoms, 2.5)
    coordination = np.bincount(first[atoms.numbers[second] == 8], minlength=len(atoms))
    assert set(coordination[atoms.numbers == 28]) == {6}
    assert Counter(coordination[atoms.numbers == 26]) == {4: 8, 6: 8}
    identical, _ = build_compound_bulk(spec)
    np.testing.assert_array_equal(atoms.numbers, identical.numbers)
    other, _ = build_compound_bulk(replace(spec, seed=43))
    assert not np.array_equal(atoms.numbers, other.numbers)
    np.testing.assert_array_equal(atoms.positions, other.positions)
    _, normal = build_compound_bulk(replace(spec, inversion=0))
    assert normal["tetrahedral_counts"] == {"Ni": 8}
    assert normal["octahedral_counts"] == {"Fe": 16}
    _, partial = build_compound_bulk(replace(spec, inversion=0.3))
    assert partial["spinel_inversion_achieved"] == 0.25
    assert partial["spinel_inversion_requested"] == 0.3


@pytest.mark.parametrize("miller", [(0, 0, 1), (1, 1, 0), (1, 1, 1), (-1, 0, 1)])
def test_cut_phase_preserves_counts_and_changes_termination(miller):
    spec = replace(EXAMPLES[0].spec(), miller=miller, nx=1, ny=1, layers=2)
    original = build_project(spec)
    shifted = build_project(replace(spec, termination=0.63))
    assert Counter(original.atoms.get_chemical_symbols()) == Counter(
        shifted.atoms.get_chemical_symbols()
    )
    assert not np.allclose(original.atoms.positions, shifted.atoms.positions)
    assert shifted.provenance["cut_phase"] == 0.63
    assert shifted.atoms.positions[:, 2].min() == pytest.approx(8)


@pytest.mark.parametrize("formula", ["NiFe2O4", "PtO", "Fe3O4", "Ni2Fe4O8", "O4Fe2Ni"])
def test_flat_integer_formulas(formula):
    normalized, counts = parse_formula(formula)
    assert counts and normalized
    if formula == "Ni2Fe4O8":
        assert normalized == "NiFe2O4"


@pytest.mark.parametrize(
    "formula",
    [
        "",
        "XxO",
        "Ni0Fe2O4",
        "Ni0.5Fe2O4",
        "Ni(OH)2",
        "NiFe2O4+",
        "NiFe2O₄",
        "FeOFe2O3",
        "Ni1001O",
        "Pt O",
    ],
)
def test_unsupported_formula_syntax_fails(formula):
    with pytest.raises(ValueError):
        parse_formula(formula)


@pytest.mark.parametrize(
    "change",
    [
        dict(crystal="fcc", element="PtO"),
        dict(element="PtO2"),
        dict(internal_u=0.5),
        dict(inversion=1.1),
        dict(termination=1),
        dict(seed=-1),
    ],
)
def test_mismatched_and_invalid_compound_specs(change):
    spec = EXAMPLES[1].spec()
    with pytest.raises(ValueError):
        build_project(replace(spec, **change))


def test_compound_count_limit_is_checked_before_repetition():
    with pytest.raises(ValueError, match="20,000"):
        build_project(replace(EXAMPLES[1].spec(), nx=20, ny=20, layers=2))


def test_compound_project_roundtrip_and_legacy_projects(tmp_path):
    spec = replace(EXAMPLES[1].spec(), inversion=0.5, seed=100, termination=0.17)
    project = build_project(spec)
    path = tmp_path / "compound.surfaces.json"
    save_project(project, path)
    restored = load_project(path)
    assert restored.spec == spec
    assert restored.provenance == project.provenance
    np.testing.assert_array_equal(restored.atoms.numbers, project.atoms.numbers)
    np.testing.assert_array_equal(restored.atoms.positions, project.atoms.positions)
    legacy = load_project("examples/pt100.surfaces.json")
    assert legacy.spec == StructureSpec()


@pytest.mark.parametrize(
    "example_index,miller", [(0, (1, 1, 1)), (1, (1, 1, 0)), (9, (1, 0, 1)), (11, (-1, 0, 1))]
)
def test_default_cuts_preserve_ase_multilayer_registry(example_index, miller):
    from ase.build import surface

    spec = replace(EXAMPLES[example_index].spec(), miller=miller, layers=3)
    lattice, _ = build_compound_bulk(spec)
    reference = surface(lattice, miller, spec.layers, vacuum=spec.vacuum)
    reference = reference.repeat((spec.nx, spec.ny, 1))
    result = build_project(spec).atoms
    np.testing.assert_allclose(result.positions, reference.positions, atol=1e-8)
    np.testing.assert_allclose(result.cell, reference.cell, atol=1e-8)
    np.testing.assert_array_equal(result.numbers, reference.numbers)


def test_cut_phases_within_one_plane_gap_are_equivalent_after_centering():
    spec = replace(EXAMPLES[0].spec(), nx=1, ny=1)
    first = build_project(replace(spec, termination=0.1)).atoms
    second = build_project(replace(spec, termination=0.2)).atoms
    np.testing.assert_allclose(first.positions, second.positions)
    np.testing.assert_array_equal(first.numbers, second.numbers)


def test_cut_normalizes_periodic_upper_boundary_roundoff(monkeypatch):
    from surfaces import compounds

    spec = replace(EXAMPLES[0].spec(), miller=(1, 1, 1), nx=1, ny=1, layers=2)
    reference = build_project(spec).atoms
    ase_surface = compounds.surface

    def wrapped_surface(*args, **kwargs):
        atoms = ase_surface(*args, **kwargs)
        heights = atoms.positions[:, 2]
        bottom = np.flatnonzero(
            np.isclose(heights, 0, atol=1e-9)
            | np.isclose(heights, atoms.cell[2, 2], atol=1e-9, rtol=0)
        )
        assert len(bottom)
        atoms.positions[bottom[0], 2] = atoms.cell[2, 2] - 1e-12
        return atoms

    monkeypatch.setattr(compounds, "surface", wrapped_surface)
    result = build_project(spec).atoms
    np.testing.assert_array_equal(result.numbers, reference.numbers)
    np.testing.assert_allclose(result.positions, reference.positions, atol=1e-9)


def test_invalid_compound_recipe_rejected_on_load(tmp_path):
    import json

    project = build_project(EXAMPLES[1].spec())
    path = tmp_path / "bad-compound.surfaces.json"
    save_project(project, path)
    data = json.loads(path.read_text())
    data["spec"]["internal_u"] = 0.7
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="internal coordinate u"):
        load_project(path)


def test_legacy_project_save_upgrades_schema_without_changing_atoms(tmp_path):
    import json
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "examples" / "pt100.surfaces.json"
    before = load_project(source)
    path = tmp_path / "upgraded.surfaces.json"
    save_project(before, path)
    assert json.loads(path.read_text())["schema_version"] == 3
    after = load_project(path)
    np.testing.assert_array_equal(before.atoms.numbers, after.atoms.numbers)
    np.testing.assert_array_equal(before.atoms.positions, after.atoms.positions)
    np.testing.assert_array_equal(before.atoms.arrays["site_ids"], after.atoms.arrays["site_ids"])
