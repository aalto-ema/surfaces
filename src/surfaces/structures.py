"""Validated ASE slab construction, import normalization and site identity."""

import math
from uuid import uuid4

import numpy as np
from ase import Atoms
from ase.build import bcc100, bcc110, bcc111, bulk, fcc100, fcc110, fcc111, hcp0001, surface
from ase.data import atomic_numbers, covalent_radii, reference_states
from ase.io import read

from surfaces.model import MAX_PHYSICAL_ATOMS, Project, StructureSpec


def validate_element(symbol: str) -> str:
    if not isinstance(symbol, str):
        raise ValueError("Element must be a chemical symbol such as Pt or Au.")
    symbol = symbol.strip()
    if symbol not in atomic_numbers or atomic_numbers[symbol] == 0:
        raise ValueError(f"Unknown element {symbol!r}; use a chemical symbol such as Pt or Au.")
    radius = float(covalent_radii[atomic_numbers[symbol]])
    if not math.isfinite(radius) or radius <= 0:
        raise ValueError(f"No usable covalent radius is available for {symbol}.")
    return symbol


def reference_lattice(symbol: str, crystal: str) -> tuple[float, float, str] | None:
    validate_element(symbol)
    state = reference_states[atomic_numbers[symbol]]
    if not state or state.get("symmetry") != crystal or "a" not in state:
        return None
    a = float(state["a"])
    c = a * float(state.get("c/a", math.sqrt(8 / 3))) if crystal == "hcp" else 0.0
    return a, c, "ASE elemental reference state; editable, unrelaxed starting lattice"


def surface_frame(atoms: Atoms) -> np.ndarray:
    """Orthonormal a / in-plane / oriented-normal frame, with Cartesian fallback."""
    normal = np.cross(atoms.cell[0], atoms.cell[1])
    if np.linalg.norm(normal) < 1e-10:
        return np.eye(3)
    normal = normal / np.linalg.norm(normal)
    if np.dot(normal, atoms.cell[2]) < 0:
        normal = -normal
    first = atoms.cell[0] / np.linalg.norm(atoms.cell[0])
    second = np.cross(normal, first)
    return np.array([first, second, normal])


def layer_indices(atoms: Atoms, tolerance: float = 1e-4) -> np.ndarray:
    """Cluster planes bottom-to-top along the oriented a×b surface normal."""
    if not len(atoms):
        return np.array([], dtype=int)
    normal = surface_frame(atoms)[2]
    heights = atoms.positions @ normal
    result = np.empty(len(atoms), dtype=int)
    level, anchor = -1, -np.inf
    for index in np.argsort(heights, kind="stable"):
        if heights[index] - anchor > tolerance:
            level += 1
            anchor = heights[index]
        result[index] = level
    return result


def assign_ids(atoms: Atoms) -> None:
    prefix = uuid4().hex[:12]
    atoms.set_array("site_ids", np.array([f"{prefix}:{i + 1}" for i in range(len(atoms))]))


def validate_atoms(atoms: Atoms) -> None:
    if len(atoms) == 0:
        raise ValueError("The structure must contain at least one atom.")
    if len(atoms) > MAX_PHYSICAL_ATOMS:
        raise ValueError(f"This version accepts up to {MAX_PHYSICAL_ATOMS:,} physical atoms.")
    if not np.isfinite(atoms.positions).all() or not np.isfinite(atoms.cell.array).all():
        raise ValueError("Positions and cell vectors must be finite.")
    for symbol in set(atoms.get_chemical_symbols()):
        validate_element(symbol)
    if "site_ids" in atoms.arrays:
        ids = atoms.arrays["site_ids"]
        if ids.ndim != 1 or len(set(ids)) != len(atoms) or any(not str(i) for i in ids):
            raise ValueError("Site IDs must be unique, nonempty strings.")


def validate_spec(spec: StructureSpec) -> None:
    if spec.particle is not None:
        from surfaces.particles import validate_particle

        validate_particle(spec)
        return

    from surfaces.compounds import PROTOTYPES, parse_formula, validate_compound_spec

    if spec.crystal in PROTOTYPES:
        validate_compound_spec(spec)
    elif spec.crystal in ("fcc", "bcc", "hcp"):
        if isinstance(spec.element, str) and spec.element.strip() not in atomic_numbers:
            _, counts = parse_formula(spec.element)
            if len(counts) > 1:
                raise ValueError(
                    "A compound needs a crystal prototype. Choose one from "
                    "Compound examples, or select a matching prototype in the dropdown."
                )
        validate_element(spec.element)
    else:
        raise ValueError("Choose FCC, BCC, HCP, or a supported compound prototype.")
    if not math.isfinite(spec.a) or not 0.01 <= spec.a <= 100:
        raise ValueError("Lattice a must be positive and finite (0.01–100 Å).")
    if spec.crystal == "hcp" and (not math.isfinite(spec.c) or spec.c <= 0):
        raise ValueError("HCP lattice c must be positive and finite.")
    if not math.isfinite(spec.vacuum) or not 0 <= spec.vacuum <= 1000:
        raise ValueError("Vacuum per side must be nonnegative and finite (0–1,000 Å).")
    if any(type(n) is not int or n < 1 for n in (spec.nx, spec.ny, spec.layers)):
        raise ValueError("Repeat counts and layer count must be positive integers.")
    if spec.nx > 100 or spec.ny > 100 or spec.layers > 200:
        raise ValueError("In-plane repeats are limited to 100 and layers/cut cells to 200.")
    if len(spec.miller) != 3 or any(type(n) is not int for n in spec.miller):
        raise ValueError("Miller indices must be three integers.")
    if spec.miller == (0, 0, 0):
        raise ValueError("Miller indices cannot all be zero.")
    if max(abs(n) for n in spec.miller) > 12:
        raise ValueError("Use Miller indices between −12 and 12.")
    if spec.nx * spec.ny * spec.layers > 25_000:
        raise ValueError("Reduce repeats/layers: the conservative build limit is 25,000 units.")


def build_project(spec: StructureSpec) -> Project:
    from surfaces.compounds import PROTOTYPES, compound_slab

    validate_spec(spec)
    if spec.particle is not None:
        from surfaces.particles import build_particle

        return build_particle(spec)
    if spec.crystal in PROTOTYPES:
        atoms, provenance = compound_slab(spec)
        assign_ids(atoms)
        validate_atoms(atoms)
        provenance.update(
            {
                "lattice_source": spec.lattice_source,
                "normal": "oriented cell a × b",
                "vacuum": "Å per side",
                "relaxed": False,
                "atomic_planes": int(layer_indices(atoms).max()) + 1,
            }
        )
        return Project(
            atoms,
            atoms.copy(),
            spec,
            provenance,
            title=f"{spec.element} · {spec.crystal} ({' '.join(map(str, spec.miller))})",
        )
    builders = {
        ("fcc", (1, 0, 0)): fcc100,
        ("fcc", (1, 1, 0)): fcc110,
        ("fcc", (1, 1, 1)): fcc111,
        ("bcc", (1, 0, 0)): bcc100,
        ("bcc", (1, 1, 0)): bcc110,
        ("bcc", (1, 1, 1)): bcc111,
        ("hcp", (0, 0, 1)): hcp0001,
    }
    builder = builders.get((spec.crystal, spec.miller))
    kwargs = {"a": spec.a, "vacuum": spec.vacuum, "periodic": False}
    if spec.crystal == "hcp":
        kwargs["c"] = spec.c
    if builder:
        if builder in (fcc111, bcc110, bcc111, hcp0001):
            kwargs["orthogonal"] = False
        atoms = builder(spec.element, size=(spec.nx, spec.ny, spec.layers), **kwargs)
        convention = "ASE specialized surface builder; layers count atomic planes"
        builder_name = builder.__name__
    else:
        lattice = bulk(
            spec.element,
            spec.crystal,
            a=spec.a,
            c=spec.c if spec.crystal == "hcp" else None,
            cubic=spec.crystal != "hcp",
        )
        atoms = surface(lattice, spec.miller, spec.layers, vacuum=spec.vacuum)
        atoms = atoms.repeat((spec.nx, spec.ny, 1))
        convention = (
            "Conventional cubic bulk cell"
            if spec.crystal != "hcp"
            else "ASE hexagonal bulk cell, three-index (h k l), not four-index notation"
        )
        convention += "; layers count cut-cell repeats, which may contain several atomic planes"
        builder_name = "ase.build.surface"
    assign_ids(atoms)
    validate_atoms(atoms)
    return Project(
        atoms,
        atoms.copy(),
        spec,
        {
            "builder": builder_name,
            "cell_convention": convention,
            "lattice_source": spec.lattice_source,
            "normal": "oriented cell a × b",
            "vacuum": "Å per side",
            "relaxed": False,
            "atomic_planes": int(layer_indices(atoms).max()) + 1,
        },
        title=f"{spec.element} · {spec.crystal.upper()} ({' '.join(map(str, spec.miller))})",
    )


def import_project(path: str) -> Project:
    atoms = read(path, index=-1)
    validate_atoms(atoms)
    assign_ids(atoms)
    omitted_constraints = len(atoms.constraints)
    atoms.set_constraint()
    atoms.calc = None
    return Project(
        atoms,
        atoms.copy(),
        None,
        {
            "source_file": path,
            "builder": "ASE import",
            "cell_convention": "Imported cell; layers clustered along oriented a × b",
            "relaxed": "unknown",
            "atomic_planes": int(layer_indices(atoms).max()) + 1,
            "scope": "Geometry and species only; simulation constraints/calculators are omitted",
            "omitted_constraints": omitted_constraints,
        },
        title=f"{atoms.get_chemical_formula()} · imported",
    )
