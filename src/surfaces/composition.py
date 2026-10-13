"""Deterministic species assignments on an unchanged ideal lattice."""

import math

import numpy as np
from ase import Atoms

from surfaces.structures import layer_indices, validate_element


def allocate(count: int, mixture: list[tuple[str, float]]) -> tuple[list[str], np.ndarray]:
    symbols = [validate_element(s) for s, _ in mixture]
    if not symbols or len(set(symbols)) != len(symbols):
        raise ValueError("Add distinct element symbols to the composition table.")
    weights = np.array([w for _, w in mixture], dtype=float)
    if not np.isfinite(weights).all() or (weights < 0).any() or weights.sum() <= 0:
        raise ValueError("Fractions must be finite, nonnegative, with a positive total.")
    if not math.isclose(float(weights.sum()), 100.0, abs_tol=0.001):
        raise ValueError(
            f"Composition percentages must sum to 100%; current sum is {weights.sum():g}%."
        )
    exact = weights / weights.sum() * count
    counts = np.floor(exact).astype(int)
    # Stable sorting breaks fractional ties by displayed element order.
    for index in np.argsort(-(exact - counts), kind="stable")[: count - counts.sum()]:
        counts[index] += 1
    return symbols, counts


def indices_for_ids(atoms: Atoms, ids: set[str]) -> np.ndarray:
    if not ids:
        raise ValueError("Select at least one physical site.")
    mapping = {str(value): i for i, value in enumerate(atoms.arrays["site_ids"])}
    missing = ids - mapping.keys()
    if missing:
        raise ValueError("A selected site no longer exists. Select sites again.")
    # Canonical structure order makes selection-order changes irrelevant to a seed.
    return np.array(sorted(mapping[value] for value in ids), dtype=int)


def substitute(
    atoms: Atoms, mixture: list[tuple[str, float]], seed: int = 0, ids: set[str] | None = None
) -> tuple[Atoms, dict]:
    if type(seed) is not int or seed < 0 or seed > 2**32 - 1:
        raise ValueError("Seed must be an integer between 0 and 4,294,967,295.")
    indices = np.arange(len(atoms)) if ids is None else indices_for_ids(atoms, ids)
    symbols, counts = allocate(len(indices), mixture)
    assigned = np.repeat(symbols, counts)
    np.random.default_rng(seed).shuffle(assigned)
    result = atoms.copy()
    numbers = result.numbers.copy()
    from ase.data import atomic_numbers

    numbers[indices] = [atomic_numbers[s] for s in assigned]
    result.set_atomic_numbers(numbers)
    operation = {
        "kind": "composition",
        "mixture_percent": [list(row) for row in mixture],
        "seed": seed,
        "counts": dict(zip(symbols, counts.tolist(), strict=True)),
        "assignments": {
            str(atoms.arrays["site_ids"][i]): str(s) for i, s in zip(indices, assigned, strict=True)
        },
    }
    return result, operation


def explicit(atoms: Atoms, assignments: dict[str, str]) -> tuple[Atoms, dict]:
    indices = indices_for_ids(atoms, set(assignments))
    for symbol in assignments.values():
        validate_element(symbol)
    result = atoms.copy()
    from ase.data import atomic_numbers

    numbers = result.numbers.copy()
    for index in indices:
        numbers[index] = atomic_numbers[assignments[str(atoms.arrays["site_ids"][index])]]
    result.set_atomic_numbers(numbers)
    return result, {"kind": "explicit", "assignments": dict(assignments)}


def layered(atoms: Atoms, recipes: dict[int, list[tuple[str, float]]], seed: int = 0):
    layers = layer_indices(atoms)
    if not recipes:
        raise ValueError("Define at least one layer.")
    result = atoms.copy()
    operations = []
    for layer, mixture in sorted(recipes.items()):
        indices = np.flatnonzero(layers == layer)
        if not len(indices):
            raise ValueError(f"Layer {layer + 1} does not exist.")
        ids = set(map(str, atoms.arrays["site_ids"][indices]))
        result, operation = substitute(result, mixture, (seed + layer) % 2**32, ids)
        operation["layer_bottom_to_top"] = layer + 1
        operations.append(operation)
    return result, {"kind": "layered", "seed": seed, "layers": operations}
