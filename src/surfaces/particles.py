"""Finite ASE clusters and explicit geometric envelopes, independent of Qt."""

import math
from dataclasses import asdict

import numpy as np
from ase import Atoms
from ase.build import bulk
from ase.cluster import wulff_construction
from ase.cluster.cubic import (
    BodyCenteredCubicFactory,
    FaceCenteredCubicFactory,
    SimpleCubicFactory,
)
from scipy.spatial import cKDTree

from surfaces.model import MAX_PHYSICAL_ATOMS, ParticleSpec, StructureSpec

MAX_CANDIDATES = 250_000
SHAPES = {
    "helicoid_iii": "Grooved cubic helicoid · 432 model",
    "chiral_rod": "Fourfold ridged chiral nanorod",
    "cube": "Cube · {100}",
    "octahedron": "Octahedron · {111}",
    "cuboctahedron": "Cuboctahedron · {100} + {111}",
    "facets": "Custom facet layers",
    "wulff": "Wulff · supplied energies",
    "sphere": "Sphere",
    "ellipsoid": "Ellipsoid",
    "rod": "Cylindrical nanorod",
    "prism": "Rectangular nanorod",
    "triangle": "Triangular nanoplate",
    "hexagon": "Hexagonal nanoplate",
    "twisted_rod": "Twisted rectangular nanorod",
    "helicoid": "Helicoidal ribbon · lattice cut",
}
FACET_SHAPES = {"cube", "octahedron", "cuboctahedron", "facets", "wulff"}
LIMITS = (
    "Elemental FCC, BCC or SC parent lattices only; compounds are not approximated. "
    "All particles are finite, ideal and unrelaxed. Shapes do not establish stability, "
    "segregation or environmental equilibrium. Twisted rods deform the lattice; "
    "helicoidal ribbons cut an undeformed lattice with a rotating envelope. Neither "
    "is a validated growth model or an experimentally assigned helicoid phase. "
    "Curved/deformed boundaries have no single Miller facet. Dimensions bound atom "
    "centers, not rendered atomic radii. Maximum 20,000 retained atoms."
)


def _number(value, low, high, name):
    if (
        isinstance(value, bool)
        or not isinstance(value, (float, int))
        or not math.isfinite(value)
        or not low <= value <= high
    ):
        raise ValueError(f"{name} must be finite and between {low} and {high}.")


def validate_particle(spec: StructureSpec) -> None:
    from surfaces.structures import validate_element

    p = spec.particle
    if not isinstance(p, ParticleSpec):
        raise ValueError("Invalid nanoparticle recipe.")
    if spec.crystal not in ("fcc", "bcc", "sc"):
        raise ValueError("Nanoparticles require an elemental FCC, BCC or SC parent lattice.")
    validate_element(spec.element)
    _number(spec.a, 0.01, 100, "Lattice a (Å)")
    _number(spec.vacuum, 0.1, 1000, "Finite-cell padding (Å)")
    if p.shape not in SHAPES:
        raise ValueError("Unknown nanoparticle shape.")
    for name in ("width", "length", "thickness"):
        _number(
            getattr(p, name),
            0.1,
            5000 if p.shape in ("helicoid_iii", "chiral_rod") else 500,
            f"{name.capitalize()} (Å)",
        )
    _number(p.twist, -360, 360, "Total twist (degrees)")
    if p.axis not in ("001", "110", "111"):
        raise ValueError("Choose a parent [001], [110] or [111] particle axis.")
    if type(p.shells) is not int or not 1 <= p.shells <= 30:
        raise ValueError("Facet shells must be an integer between 1 and 30.")
    if type(p.target_atoms) is not int or not 1 <= p.target_atoms <= MAX_PHYSICAL_ATOMS:
        raise ValueError("Wulff target must be 1–20,000 atoms.")
    if p.rounding not in ("closest", "above", "below"):
        raise ValueError("Invalid Wulff rounding choice.")
    if p.energy_unit not in ("relative", "J/m²", "eV/Å²"):
        raise ValueError("Use relative energies, J/m² or eV/Å² consistently.")
    if not isinstance(p.energy_source, str) or len(p.energy_source) > 2000:
        raise ValueError("Invalid surface-energy source.")
    if type(p.illustrative) is not bool:
        raise ValueError("Illustrative energy flag must be a boolean.")
    if p.shape == "wulff" and not p.energy_source.strip():
        raise ValueError("Record an energy source or explicitly describe illustrative ratios.")
    if not isinstance(p.facets, list) or not 1 <= len(p.facets) <= 12:
        raise ValueError("Supply 1–12 facet-family rows.")
    families = set()
    for row in p.facets:
        if not isinstance(row, dict) or set(row) != {"miller", "layers", "energy"}:
            raise ValueError("Each facet row needs Miller indices, layers and energy.")
        h = row["miller"]
        if (
            not isinstance(h, (list, tuple))
            or len(h) != 3
            or any(type(i) is not int or not 0 <= i <= 3 for i in h)
            or not any(h)
            or math.gcd(*h) != 1
        ):
            raise ValueError("Facet families need reduced nonnegative indices 0–3, e.g. 1 0 0.")
        family = tuple(sorted(h))
        if family in families:
            raise ValueError("Do not repeat symmetry-equivalent facet families.")
        families.add(family)
        if type(row["layers"]) is not int or not 1 <= row["layers"] <= 30:
            raise ValueError("Facet layers must be integers between 1 and 30.")
        _number(row["energy"], 0.001, 1000, "Surface energy / ratio")
    if p.shape == "wulff":
        energies = [row["energy"] for row in p.facets]
        if max(energies) / min(energies) > 20:
            raise ValueError("Surface-energy ratios above 20 are outside the bounded builder.")
    for name, low, high in [
        ("gap_depth", 0.05, 0.40),
        ("gap_width", 0.03, 0.25),
        ("groove_angle", 5, 60),
        ("ridge_height", 0.05, 0.45),
        ("ridge_width", 0.15, 0.8),
        ("cap_fraction", 0.05, 0.3),
    ]:
        _number(getattr(p, name), low, high, name)
    if type(p.handedness) is not int or p.handedness not in (-1, 1):
        raise ValueError("Handedness must be +1 or −1.")
    if type(p.atomistic) is not bool or type(p.crossed_ridges) is not bool:
        raise ValueError("Atomistic and crossed-ridge settings must be booleans.")
    if type(p.mesh_resolution) is not int or not 32 <= p.mesh_resolution <= 80:
        raise ValueError("Surface resolution must be an integer between 32 and 80.")
    if p.shape in ("helicoid_iii", "chiral_rod"):
        if spec.crystal != "fcc" or p.axis != "001":
            raise ValueError(
                "Reference-inspired chiral models use an FCC parent with [001] along z."
            )
        if p.shape == "chiral_rod" and (p.length < p.width or not 5 <= p.twist <= 120):
            raise ValueError(
                "Ridged rods need length ≥ width and a ridge rotation of 5–120°. "
                "Use handedness to reverse sign."
            )
    if p.shape in ("twisted_rod", "helicoid"):
        if abs(p.twist) < 1:
            raise ValueError("Chiral constructions need a signed twist of at least 1°.")
        if p.width <= p.thickness:
            raise ValueError("Use width greater than thickness for a visibly anisotropic twist.")


class _Bounded:
    """Guard ASE's allocation before its factory constructs candidate atoms."""

    def make_cluster(self, vacuum):
        count = math.prod(map(int, self.size)) * len(self.atomic_basis)
        if count > MAX_CANDIDATES:
            raise ValueError("Facet build exceeds 250,000 candidate sites; reduce layers/size.")
        return super().make_cluster(vacuum)


class _FCC(_Bounded, FaceCenteredCubicFactory):
    pass


class _BCC(_Bounded, BodyCenteredCubicFactory):
    pass


class _SC(_Bounded, SimpleCubicFactory):
    pass


def particle_frame(axis: str) -> np.ndarray:
    """Rows map cubic Cartesian coordinates onto a right-handed particle frame."""
    z = np.array([int(i) for i in axis], dtype=float)
    z /= np.linalg.norm(z)
    x = np.array([1.0, -1.0, 0.0]) if axis != "001" else np.array([1.0, 0.0, 0.0])
    x /= np.linalg.norm(x)
    return np.array([x, np.cross(z, x), z])


def _faceted(spec):
    p = spec.particle
    factory = {"fcc": _FCC, "bcc": _BCC, "sc": _SC}[spec.crystal]()
    rows = p.facets
    if p.shape == "cube":
        surfaces, layers = [(1, 0, 0)], [p.shells]
    elif p.shape == "octahedron":
        surfaces, layers = [(1, 1, 1)], [p.shells]
    elif p.shape == "cuboctahedron":
        if spec.crystal != "fcc":
            raise ValueError("The cuboctahedron preset uses FCC layer spacing; use custom facets.")
        surfaces, layers = [(1, 0, 0), (1, 1, 1)], [p.shells, p.shells]
    else:
        surfaces = [tuple(row["miller"]) for row in rows]
        layers = [row["layers"] for row in rows]
    info = {"facet_families": surfaces, "requested_center_to_facet_layers": layers}
    if p.shape == "wulff":
        try:
            atoms = wulff_construction(
                spec.element,
                surfaces,
                [row["energy"] for row in rows],
                p.target_atoms,
                factory,
                rounding=p.rounding,
                latticeconstant=spec.a,
                maxiter=100,
            )
        except RuntimeError as exc:
            raise ValueError(
                "Wulff iteration did not converge; change size or energy ratios."
            ) from exc
        info.update(
            {
                "requested_atoms": p.target_atoms,
                "rounding": p.rounding,
                "surface_energies": [row["energy"] for row in rows],
                "energy_unit": p.energy_unit,
                "energy_source": p.energy_source,
                "illustrative_energies": p.illustrative,
            }
        )
        info.pop("requested_center_to_facet_layers")
    else:
        atoms = factory(spec.element, surfaces, layers, latticeconstant=spec.a)
    info["builder"] = "ASE cluster Wulff" if p.shape == "wulff" else "ASE cubic cluster layers"
    atoms = Atoms(numbers=atoms.numbers, positions=atoms.positions)
    return atoms, info


def _envelope(spec):
    p = spec.particle
    # Bound all rotated envelopes by a sphere before allocating the parent lattice.
    if p.shape == "sphere":
        extents = np.array([p.width, p.width, p.width]) / 2
    elif p.shape in ("triangle", "hexagon"):
        extents = np.array([p.width * 2 / np.sqrt(3), p.width * 2 / np.sqrt(3), p.thickness]) / 2
    elif p.shape in ("rod",):
        extents = np.array([p.width, p.width, p.length]) / 2
    else:
        extents = np.array([p.width, p.thickness, p.length]) / 2
    frame = particle_frame(p.axis)
    # Twisting sweeps the rectangular cross section through its circumcircle.
    if p.shape in ("twisted_rod", "helicoid"):
        radius = np.hypot(extents[0], extents[1])
        extents[:2] = radius
    bounds = np.abs(frame).T @ extents
    repeats = 2 * np.ceil(bounds / spec.a).astype(int) + 3
    parent = bulk(spec.element, spec.crystal, a=spec.a, cubic=True)
    count = math.prod(map(int, repeats)) * len(parent)
    if count > MAX_CANDIDATES:
        raise ValueError(
            "Envelope needs over 250,000 lattice sites; reduce dimensions or increase a."
        )
    atoms = parent.repeat(tuple(map(int, repeats)))
    atoms.positions -= (repeats // 2) * spec.a
    xyz = atoms.positions @ frame.T
    x, y, z = xyz.T
    halfw, halft, halfl = p.width / 2, p.thickness / 2, p.length / 2
    tol = 1e-8
    if p.shape == "sphere":
        keep = np.linalg.norm(xyz, axis=1) <= halfw + tol
    elif p.shape == "ellipsoid":
        keep = (x / halfw) ** 2 + (y / halft) ** 2 + (z / halfl) ** 2 <= 1 + tol
    elif p.shape == "rod":
        keep = (np.hypot(x, y) <= halfw + tol) & (np.abs(z) <= halfl + tol)
    elif p.shape in ("triangle", "hexagon"):
        sides = 3 if p.shape == "triangle" else 6
        # width = triangle side length or hexagon vertex-to-vertex diameter.
        apothem = p.width / (2 * np.sqrt(3)) if sides == 3 else halfw * np.sqrt(3) / 2
        normals = np.array([(np.cos(t), np.sin(t)) for t in np.arange(sides) * 2 * np.pi / sides])
        keep = (xyz[:, :2] @ normals.T <= apothem + tol).all(axis=1) & (np.abs(z) <= halft + tol)
    else:
        if p.shape == "helicoid":
            theta = np.radians(p.twist) * z / p.length
            x, y = x * np.cos(theta) + y * np.sin(theta), -x * np.sin(theta) + y * np.cos(theta)
        keep = (np.abs(x) <= halfw + tol) & (np.abs(y) <= halft + tol) & (np.abs(z) <= halfl + tol)
    atoms = Atoms(numbers=atoms.numbers[keep], positions=xyz[keep])
    if p.shape == "twisted_rod":
        x, y, z = atoms.positions.T.copy()
        theta = np.radians(p.twist) * z / p.length
        atoms.positions[:, 0] = x * np.cos(theta) - y * np.sin(theta)
        atoms.positions[:, 1] = x * np.sin(theta) + y * np.cos(theta)
    return atoms, {
        "builder": "ASE bulk → analytic envelope",
        "parent_to_particle_frame": frame.tolist(),
    }


def build_particle(spec: StructureSpec):
    from surfaces.model import Project
    from surfaces.structures import assign_ids, validate_atoms

    validate_particle(spec)
    p = spec.particle
    if p.shape in ("helicoid_iii", "chiral_rod"):
        from surfaces.morphology import build_morphology

        return build_morphology(spec)
    atoms, info = _faceted(spec) if p.shape in FACET_SHAPES else _envelope(spec)
    validate_atoms(atoms)
    nn = spec.a * {"fcc": 1 / np.sqrt(2), "bcc": np.sqrt(3) / 2, "sc": 1}[spec.crystal]
    nearest = (
        float(cKDTree(atoms.positions).query(atoms.positions, k=2)[0][:, 1].min())
        if len(atoms) > 1
        else None
    )
    if p.shape == "twisted_rod" and nearest is not None and nearest < 0.55 * nn:
        raise ValueError("Twist produces severe short contacts; reduce twist or increase length.")
    atoms.pbc = False
    atoms.cell = np.diag(np.ptp(atoms.positions, axis=0) + 2 * spec.vacuum)
    atoms.center()
    assign_ids(atoms)
    info.update(
        {
            "kind": "nanoparticle",
            "shape": p.shape,
            "recipe": asdict(p),
            "parent_crystal": spec.crystal,
            "lattice_source": spec.lattice_source,
            "cell_convention": "Finite Cartesian bounding box with padding; no periodicity",
            "orientation": "Cubic [100]/[010]/[001]"
            if p.shape in FACET_SHAPES
            else f"particle z along parent [{p.axis}]",
            "dimensions_angstrom": np.ptp(atoms.positions, axis=0).tolist(),
            "achieved_atoms": len(atoms),
            "relaxed": False,
            "minimum_distance_angstrom": nearest,
            "bulk_nearest_neighbor_angstrom": nn,
            "twist_convention": (
                "theta(z) = total_twist * z / requested_length; positive is right-hand about +z"
            ),
            "limits": LIMITS,
        }
    )
    return Project(atoms, atoms.copy(), spec, info, title=f"{spec.element} · {SHAPES[p.shape]}")
