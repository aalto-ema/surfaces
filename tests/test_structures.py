import numpy as np
import pytest
from ase.build import fcc100

from surfaces.model import StructureSpec
from surfaces.structures import build_project, layer_indices


def test_pt100_matches_ase_and_has_stable_ids():
    p = build_project(StructureSpec())
    reference = fcc100("Pt", size=(5, 5, 4), a=3.92, vacuum=8)
    np.testing.assert_allclose(p.atoms.positions, reference.positions)
    np.testing.assert_allclose(p.atoms.cell, reference.cell)
    assert list(p.atoms.pbc) == [True, True, False]
    assert len(set(p.atoms.arrays["site_ids"])) == 100
    assert np.bincount(layer_indices(p.atoms)).tolist() == [25] * 4
    assert p.atoms.positions[:, 2].min() == pytest.approx(8)


@pytest.mark.parametrize(
    "crystal,miller,a,c",
    [
        ("fcc", (1, 1, 1), 3.92, 0),
        ("bcc", (1, 1, 0), 2.87, 0),
        ("hcp", (0, 0, 1), 2.95, 4.68),
        ("fcc", (2, 1, 1), 3.92, 0),
        ("hcp", (1, 0, 0), 2.95, 4.68),
    ],
)
def test_other_builders(crystal, miller, a, c):
    p = build_project(StructureSpec(crystal=crystal, miller=miller, a=a, c=c))
    assert len(p.atoms) > 0
    assert np.isfinite(p.atoms.positions).all()
    assert p.atoms.positions[:, 2].min() == pytest.approx(8)


@pytest.mark.parametrize(
    "change",
    [
        {"miller": (0, 0, 0)},
        {"a": -1},
        {"vacuum": -1},
        {"element": "Bad"},
        {"nx": 0},
        {"a": float("nan")},
    ],
)
def test_bad_spec_is_rejected(change):
    with pytest.raises(ValueError):
        build_project(StructureSpec(**change))


def test_import_preserves_cell_and_species_but_omits_simulation_constraints(tmp_path):
    from ase.constraints import FixAtoms
    from ase.io import write

    from surfaces.structures import import_project

    atoms = fcc100("Pt", size=(2, 3, 4), a=3.92, vacuum=8)
    atoms[0].symbol = "Au"
    atoms.set_constraint(FixAtoms(indices=[0, 1]))
    atoms.rotate(34, "x", rotate_cell=True)
    path = tmp_path / "surface.traj"
    write(path, atoms)
    p = import_project(str(path))
    np.testing.assert_allclose(p.atoms.cell, atoms.cell)
    np.testing.assert_allclose(p.atoms.positions, atoms.positions)
    np.testing.assert_array_equal(p.atoms.numbers, atoms.numbers)
    assert p.spec is None
    assert p.provenance["omitted_constraints"] == 1
    assert not p.atoms.constraints
    assert np.bincount(layer_indices(p.atoms)).tolist() == [6] * 4


@pytest.mark.parametrize(
    "crystal,miller",
    [("bcc", (1, 0, 0)), ("bcc", (1, 1, 1)), ("fcc", (1, 1, 0)), ("fcc", (-1, 1, 1))],
)
def test_remaining_low_index_and_signed_cuts(crystal, miller):
    p = build_project(StructureSpec(crystal=crystal, miller=miller))
    assert len(p.atoms) == 100 or p.provenance["builder"] == "ase.build.surface"
    assert p.atoms.positions[:, 2].min() == pytest.approx(8)
