"""Explicit crystal prototypes for integer-stoichiometry compounds.

A formula selects species/counts, never a crystal structure automatically.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import reduce

import numpy as np
from ase import Atoms
from ase.build import bulk, surface
from ase.data import atomic_numbers
from ase.spacegroup import crystal

from surfaces.model import MAX_PHYSICAL_ATOMS, StructureSpec
from surfaces.structures import validate_element

PROTOTYPES = {
    "cooperite": ("AB", "Tetragonal P4₂/mmc (131); a and c; PtO-type basis"),
    "rocksalt": ("AB", "Conventional cubic Fm-3m (225); a; NaCl-type basis"),
    "zincblende": ("AB", "Conventional cubic F-43m (216); a; tetrahedral AB basis"),
    "cesiumchloride": ("AB", "Cubic Pm-3m (221); a; CsCl-type basis"),
    "wurtzite": ("AB", "Hexagonal P6₃mc (186); a, c, and internal coordinate u"),
    "rutile": ("AB2", "Tetragonal P4₂/mnm (136); a, c, and anion coordinate u"),
    "fluorite": ("AB2", "Conventional cubic Fm-3m (225); a; CaF2-type basis"),
    "perovskite": ("ABO3", "Ideal cubic Pm-3m (221); a; distinct A and B cations"),
    "spinel": ("AB2O4", "Conventional cubic spinel parent Fd-3m (227), setting 2; a and oxygen u"),
}
C_AXIS_PROTOTYPES = {"cooperite", "wurtzite", "rutile"}
U_PROTOTYPES = {"wurtzite", "rutile", "spinel"}

ASE_SOURCE = "https://docs.ase-lib.org/ase/build/build.html"
PTO_SOURCE = "https://www.frontiersin.org/journals/chemistry/articles/10.3389/fchem.2020.00704/full"
SPINEL_SOURCE = "https://arxiv.org/abs/1903.01739"
SPACEGROUP_SOURCE = "https://docs.ase-lib.org/ase/spacegroup/spacegroup.html"


@dataclass(frozen=True)
class CompoundExample:
    formula: str
    prototype: str
    a: float
    c: float = 0.0
    u: float = 0.25
    inversion: float = 0.0
    description: str = ""
    source: str = ASE_SOURCE
    parameter_note: str = "Illustrative editable starting parameters; not a validated specimen."

    def spec(self) -> StructureSpec:
        return StructureSpec(
            element=self.formula,
            crystal=self.prototype,
            miller=(0, 0, 1),
            a=self.a,
            c=self.c,
            nx=2,
            ny=2,
            layers=2,
            vacuum=8,
            lattice_source=self.parameter_note,
            internal_u=self.u,
            inversion=self.inversion,
            seed=42,
        )


EXAMPLES = (
    CompoundExample(
        "PtO",
        "cooperite",
        3.04,
        5.34,
        description="Platinum monoxide: tetragonal PtO-type basis, not oxygen assigned to FCC Pt.",
        source=PTO_SOURCE,
        parameter_note="PtO starting a=3.04 Å, c=5.34 Å from experimental values discussed "
        "by Li et al. (2020); "
        "ideal, unrelaxed surface cut.",
    ),
    CompoundExample(
        "NiFe2O4",
        "spinel",
        8.34,
        u=0.261,
        inversion=1,
        description="Nickel ferrite: inverse occupancy. Fe on tetrahedral sites; "
        "equal Ni/Fe counts on octahedral sites.",
        source=SPINEL_SOURCE,
    ),
    CompoundExample(
        "CoFe2O4",
        "spinel",
        8.39,
        u=0.261,
        inversion=1,
        description="Cobalt ferrite: illustrative fully inverse model; "
        "actual inversion is sample-dependent.",
        source=SPACEGROUP_SOURCE,
    ),
    CompoundExample(
        "MgAl2O4",
        "spinel",
        8.08,
        u=0.261,
        description="Normal spinel: Mg on tetrahedral and Al on octahedral sites.",
        source=SPACEGROUP_SOURCE,
    ),
    CompoundExample(
        "Fe3O4",
        "spinel",
        8.40,
        u=0.2545,
        inversion=1,
        description="Magnetite geometry. Fe valences and magnetic order are not represented.",
        source=SPACEGROUP_SOURCE,
    ),
    CompoundExample(
        "NiO",
        "rocksalt",
        4.17,
        description="Cubic ideal nickel monoxide. Magnetic/rhombohedral distortions are omitted.",
    ),
    CompoundExample(
        "MgO",
        "rocksalt",
        4.21,
        description="Magnesium oxide with distinct cation and anion sublattices.",
    ),
    CompoundExample(
        "NaCl", "rocksalt", 5.64, description="Sodium chloride: sixfold-coordinated AB structure."
    ),
    CompoundExample(
        "ZnS",
        "zincblende",
        5.41,
        description="Cubic zinc sulfide polymorph with tetrahedral coordination.",
    ),
    CompoundExample(
        "ZnO",
        "wurtzite",
        3.25,
        5.21,
        u=0.382,
        description="Hexagonal zinc oxide; three-index Miller notation, not four-index notation.",
    ),
    CompoundExample(
        "CsCl",
        "cesiumchloride",
        4.12,
        description="CsCl-type cubic AB basis; not the rocksalt AB geometry.",
    ),
    CompoundExample(
        "TiO2",
        "rutile",
        4.594,
        2.959,
        u=0.305,
        description="Rutile polymorph. Anatase and brookite are different, unsupported prototypes.",
        source=SPACEGROUP_SOURCE,
    ),
    CompoundExample(
        "CaF2",
        "fluorite",
        5.46,
        description="Fluorite AB2; cations and anions occupy different sublattices.",
    ),
    CompoundExample(
        "SrTiO3",
        "perovskite",
        3.905,
        description="Ideal cubic perovskite; octahedral tilts and low-temperature "
        "distortions omitted.",
        source=SPACEGROUP_SOURCE,
    ),
)


def parse_formula(text: str) -> tuple[str, dict[str, int]]:
    """Accept a flat, integer formula; reduce overall multiples while preserving order."""
    if not isinstance(text, str) or not text.strip() or len(text.strip()) > 80:
        raise ValueError("Enter a short formula such as PtO or NiFe2O4.")
    text = text.strip()
    if not re.fullmatch(r"(?:[A-Z][a-z]?(?:[1-9][0-9]*)?)+", text):
        raise ValueError(
            "Use a flat formula with positive integer counts, such as NiFe2O4. "
            "Charges, decimals, parentheses, hydrates, and isotope labels are unsupported."
        )
    counts = {}
    for symbol, number in re.findall(r"([A-Z][a-z]?)([0-9]*)", text):
        validate_element(symbol)
        if symbol in counts:
            raise ValueError("Write each element once; use Fe3O4 rather than FeOFe2O3.")
        count = int(number or 1)
        if count > 1000:
            raise ValueError("Formula counts are limited to 1–1,000 per element.")
        counts[symbol] = count
    divisor = reduce(math.gcd, counts.values())
    counts = {symbol: number // divisor for symbol, number in counts.items()}
    formula = "".join(symbol + (str(n) if n != 1 else "") for symbol, n in counts.items())
    return formula, counts


def prototype_species(formula: str, prototype: str) -> tuple[str, ...]:
    """Resolve chemically explicit A/B slots; no phase inference or fractional species."""
    _, counts = parse_formula(formula)
    species = tuple(counts)
    values = tuple(counts.values())
    if prototype not in PROTOTYPES:
        raise ValueError("Choose a supported compound crystal prototype.")
    if prototype in ("cooperite", "rocksalt", "zincblende", "cesiumchloride", "wurtzite"):
        if values == (1, 1):
            return species
    elif prototype in ("rutile", "fluorite"):
        if sorted(values) == [1, 2]:
            return (
                next(s for s in species if counts[s] == 1),
                next(s for s in species if counts[s] == 2),
            )
    elif prototype == "perovskite":
        cations = [s for s in species if s != "O"]
        if len(cations) == 2 and counts.get("O") == 3 and all(counts[s] == 1 for s in cations):
            return (*cations, "O")  # The displayed formula order explicitly defines A then B.
    elif prototype == "spinel":
        cations = [s for s in species if s != "O"]
        if len(cations) == 1 and counts[cations[0]] == 3 and counts.get("O") == 4:
            return (cations[0], cations[0], "O")
        if (
            len(cations) == 2
            and counts.get("O") == 4
            and sorted(counts[s] for s in cations) == [1, 2]
        ):
            return (
                next(s for s in cations if counts[s] == 1),
                next(s for s in cations if counts[s] == 2),
                "O",
            )
    pattern = PROTOTYPES[prototype][0]
    raise ValueError(
        f"{formula} does not match {prototype} ({pattern}). Choose another prototype "
        "or import a prepared, fully occupied slab from CIF/XYZ."
    )


def validate_compound_spec(spec: StructureSpec) -> None:
    prototype_species(spec.element, spec.crystal)
    if not math.isfinite(spec.a) or not 0.01 <= spec.a <= 100:
        raise ValueError("Lattice a must be within 0.01–100 Å.")
    if spec.crystal in C_AXIS_PROTOTYPES and (
        not math.isfinite(spec.c) or not 0.01 <= spec.c <= 100
    ):
        raise ValueError("This prototype needs a positive lattice c (0.01–100 Å).")
    if spec.crystal in U_PROTOTYPES:
        bounds = {"spinel": (0.24, 0.27), "rutile": (0.25, 0.35), "wurtzite": (0.3, 0.45)}
        low, high = bounds[spec.crystal]
        if not math.isfinite(spec.internal_u) or not low <= spec.internal_u <= high:
            raise ValueError(
                f"{spec.crystal} internal coordinate u must be within {low}–{high}; "
                "use a prepared slab for other structures."
            )
    if not math.isfinite(spec.inversion) or not 0 <= spec.inversion <= 1:
        raise ValueError("Spinel inversion must be within 0 (normal) and 1 (inverse).")
    if type(spec.seed) is not int or not 0 <= spec.seed <= 2**31 - 1:
        raise ValueError("Cation seed must be an integer from 0 to 2,147,483,647.")
    if not math.isfinite(spec.termination) or not 0 <= spec.termination < 1:
        raise ValueError("Cut phase must be within 0 (inclusive) and 1 (exclusive).")


def build_compound_bulk(spec: StructureSpec) -> tuple[Atoms, dict]:
    validate_compound_spec(spec)
    formula, counts = parse_formula(spec.element)
    slots = prototype_species(formula, spec.crystal)
    a = spec.a
    info = {
        "compound_model_version": 1,
        "compound_formula": formula,
        "bulk_formula_ratio": counts,
        "prototype": spec.crystal,
        "prototype_description": PROTOTYPES[spec.crystal][1],
        "structure_limits": "Ideal prototype, fully occupied sites; no charge, magnetism, "
        "relaxation, reconstruction, or surface-stability prediction.",
    }
    info["builder_reference"] = (
        ASE_SOURCE
        if spec.crystal in ("rocksalt", "zincblende", "cesiumchloride", "fluorite", "wurtzite")
        else SPACEGROUP_SOURCE
    )
    matching_example = next(
        (e for e in EXAMPLES if e.formula == formula and e.prototype == spec.crystal), None
    )
    if matching_example:
        info["catalog_model_reference"] = matching_example.source
    if spec.crystal in ("rocksalt", "zincblende", "cesiumchloride", "fluorite"):
        name = slots[0] + slots[1] + ("2" if spec.crystal == "fluorite" else "")
        atoms = bulk(name, spec.crystal, a=a, cubic=True)
    elif spec.crystal == "wurtzite":
        atoms = bulk("".join(slots), "wurtzite", a=a, c=spec.c, u=spec.internal_u)
    elif spec.crystal == "cooperite":
        atoms = crystal(
            slots,
            basis=[(0, 0.5, 0), (0, 0, 0.25)],
            spacegroup=131,
            cellpar=[a, a, spec.c, 90, 90, 90],
            onduplicates="error",
        )
        info["basis_reference"] = PTO_SOURCE
    elif spec.crystal == "rutile":
        u = spec.internal_u
        atoms = crystal(
            slots,
            basis=[(0, 0, 0), (u, u, 0)],
            spacegroup=136,
            cellpar=[a, a, spec.c, 90, 90, 90],
            onduplicates="error",
        )
    elif spec.crystal == "perovskite":
        atoms = crystal(
            slots,
            basis=[(0, 0, 0), (0.5, 0.5, 0.5), (0.5, 0.5, 0)],
            spacegroup=221,
            cellpar=[a, a, a, 90, 90, 90],
            onduplicates="error",
        )
    else:
        atoms = crystal(
            slots,
            basis=[(0.125, 0.125, 0.125), (0.5, 0.5, 0.5), (spec.internal_u,) * 3],
            spacegroup=227,
            setting=2,
            cellpar=[a, a, a, 90, 90, 90],
            onduplicates="error",
        )
        kinds = atoms.arrays["spacegroup_kinds"]
        tetra, octa = np.flatnonzero(kinds == 0), np.flatnonzero(kinds == 1)
        if (len(tetra), len(octa), len(atoms)) != (8, 16, 56):
            raise ValueError("Spinel basis did not produce the expected 8/16/32 sites.")
        exchanged = int(math.floor(spec.inversion * 8 + 0.5))
        rng = np.random.default_rng(spec.seed)
        tetra_selected = rng.permutation(tetra)[:exchanged]
        octa_selected = rng.permutation(octa)[:exchanged]
        atoms.numbers[tetra_selected] = atomic_numbers[slots[1]]
        atoms.numbers[octa_selected] = atomic_numbers[slots[0]]
        info.update(
            {
                "spinel_inversion_requested": spec.inversion,
                "spinel_inversion_achieved": exchanged / 8,
                "cation_seed": spec.seed,
                "cation_model": "Explicit seeded occupations in one 56-atom parent cell; "
                "the realized cell is repeated periodically, not fractional occupancy.",
                "tetrahedral_counts": dict(Counter(atoms[i].symbol for i in tetra)),
                "octahedral_counts": dict(Counter(atoms[i].symbol for i in octa)),
                "parent_symmetry": "Fd-3m setting 2; explicit cation ordering can reduce symmetry",
            }
        )
    info["bulk_atoms"] = len(atoms)
    actual = dict(Counter(atoms.get_chemical_symbols()))
    divisor = reduce(math.gcd, actual.values())
    if {s: n // divisor for s, n in actual.items()} != counts:
        raise ValueError("The prototype basis does not match the requested formula.")
    return atoms, info


def compound_slab(spec: StructureSpec) -> tuple[Atoms, dict]:
    lattice, info = build_compound_bulk(spec)
    projected_count = len(lattice) * spec.nx * spec.ny * spec.layers
    if projected_count > MAX_PHYSICAL_ATOMS:
        raise ValueError(
            f"This compound would have {projected_count:,} atoms. "
            f"Reduce repeats/cut cells to stay below {MAX_PHYSICAL_ATOMS:,}."
        )
    # Let ASE stack before making c perpendicular: repeating an already-oriented
    # one-cell slab would lose lateral registry for oblique Miller cuts.
    extended = surface(lattice, spec.miller, spec.layers + 1, periodic=True)
    period = extended.cell[2, 2] / (spec.layers + 1)
    lower = spec.termination * period
    upper = (spec.layers + spec.termination) * period
    epsilon = period * 1e-9
    heights = extended.positions[:, 2]
    keep = (heights >= lower - epsilon) & (heights < upper - epsilon)
    oriented = extended[keep]
    if len(oriented) != len(lattice) * spec.layers:
        raise ValueError(
            "Cut window did not preserve complete-cell stoichiometry. "
            "Try a phase away from an atomic plane."
        )
    oriented.cell[2] = (0, 0, spec.layers * period)
    atoms = oriented.repeat((spec.nx, spec.ny, 1))
    atoms.pbc = (True, True, False)
    atoms.center(vacuum=spec.vacuum, axis=2)
    actual = dict(Counter(atoms.get_chemical_symbols()))
    divisor = reduce(math.gcd, actual.values())
    info.update(
        {
            "builder": "ASE bulk/spacegroup crystal → surface → complete cut-cell repeats",
            "cell_convention": PROTOTYPES[spec.crystal][1] + "; Miller indices refer to that "
            "bulk cell; layers count full oriented cells, not atomic planes",
            "cut_phase": spec.termination,
            "termination_limits": "Phase shifts a stoichiometric cut window through an ASE stack. "
            "Stoichiometry is preserved; polar/asymmetric terminations "
            "are possible and are not electrostatically assessed.",
            "slab_formula_ratio": {s: n // divisor for s, n in actual.items()},
        }
    )
    return atoms, info
