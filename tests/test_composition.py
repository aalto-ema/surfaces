import numpy as np
import pytest

from surfaces.composition import allocate, explicit, layered, substitute
from surfaces.model import StructureSpec
from surfaces.structures import build_project, layer_indices


def test_largest_remainder_ties_and_percent_validation():
    symbols, counts = allocate(3, [("Pt", 50), ("Au", 50)])
    assert symbols == ["Pt", "Au"]
    assert counts.tolist() == [2, 1]
    for mixture in [[("Pt", 20)], [("Pt", 50), ("Pt", 50)], [("Pt", -1), ("Au", 101)]]:
        with pytest.raises(ValueError):
            allocate(3, mixture)


def test_seeded_assignment_preserves_geometry_and_global_rng():
    atoms = build_project(StructureSpec()).atoms
    np.random.seed(5)
    expected = np.random.random()
    np.random.seed(5)
    first, op = substitute(atoms, [("Pt", 70), ("Au", 30)], 42)
    second, _ = substitute(atoms, [("Pt", 70), ("Au", 30)], 42)
    assert np.random.random() == expected
    assert first.get_chemical_symbols().count("Au") == 30
    np.testing.assert_array_equal(first.numbers, second.numbers)
    np.testing.assert_array_equal(first.positions, atoms.positions)
    np.testing.assert_array_equal(first.cell, atoms.cell)
    np.testing.assert_array_equal(first.arrays["site_ids"], atoms.arrays["site_ids"])
    assert len(op["assignments"]) == 100
    assert atoms.get_chemical_symbols().count("Au") == 0


def test_selected_and_layered_assignments():
    atoms = build_project(StructureSpec()).atoms
    site = str(atoms.arrays["site_ids"][0])
    edited, _ = explicit(atoms, {site: "Cu"})
    assert edited[0].symbol == "Cu"
    edited, _ = layered(edited, {3: [("Au", 100)], 0: [("Pt", 50), ("Cu", 50)]}, seed=9)
    layers = layer_indices(edited)
    assert set(edited.symbols[np.flatnonzero(layers == 3)]) == {"Au"}
    assert np.count_nonzero(edited.numbers[np.flatnonzero(layers == 0)] == 29) == 12
    np.testing.assert_array_equal(edited.positions, atoms.positions)
    with pytest.raises(ValueError):
        explicit(atoms, {"missing": "Au"})
