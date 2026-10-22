"""Reference-inspired chiral envelopes; no lattice deformation or growth inference.

The cubic model is constructed from the orbit of one slanted edge groove under
all 24 proper cubic rotations. It is an explicit approximation, not a recovered
experimental Helicoid III surface or a reproduction of a proprietary CAD file.
"""

from itertools import permutations, product

import numpy as np
from ase import Atoms
from ase.build import bulk
from skimage.measure import marching_cubes

from surfaces.model import MAX_PHYSICAL_ATOMS, Project, SurfaceMesh

MORPHOLOGIES = {"helicoid_iii", "chiral_rod"}
REFERENCES = {
    "helicoid_iii": "https://doi.org/10.1038/s41467-023-39255-1",
    "chiral_rod": "https://doi.org/10.1002/adma.202208299",
}


def cubic_rotations() -> np.ndarray:
    rotations = []
    for permutation in permutations(range(3)):
        for signs in product((-1, 1), repeat=3):
            matrix = np.eye(3)[list(permutation)] * np.array(signs)[:, None]
            if np.linalg.det(matrix) > 0:
                rotations.append(matrix)
    return np.array(rotations)


ROTATIONS = cubic_rotations()


def bounds(p):
    return np.array([p.width, p.width, p.width if p.shape == "helicoid_iii" else p.length]) / 2


def envelope_field(points: np.ndarray, p) -> np.ndarray:
    """Negative inside; coordinates in Å, normalized internally for scale invariance."""
    xyz = np.asarray(points, dtype=float) / p.width
    if p.shape == "helicoid_iii":
        outer = np.max(np.abs(xyz), axis=-1) - 0.5
        groove = np.full(outer.shape, np.inf)
        slope = p.handedness * np.tan(np.radians(p.groove_angle))
        for rotation in ROTATIONS:
            x, y, t = (xyz @ rotation.T).T
            u, v = (x + y) / np.sqrt(2), (x - y) / np.sqrt(2)
            # An odd center line and even taper preserve the edge's twofold rotation.
            taper = np.maximum(0, 1 - (t / 0.58) ** 4)
            center = slope * (t + 0.5 * t**3)
            cut = np.maximum.reduce(
                [
                    np.sqrt(0.5) - p.gap_depth * taper - u,
                    np.abs(v - center) - p.gap_width / 2,
                    np.abs(t) - 0.5,
                ]
            )
            groove = np.minimum(groove, cut)
        return np.maximum(outer, -groove)
    x, y, _ = xyz.T
    z = np.asarray(points)[:, 2] / p.length
    theta = np.arctan2(y, x)
    alpha = p.handedness * np.radians(p.twist) * z

    def ridges(angle):
        return np.exp(-((np.sin(2 * (theta - angle - np.pi / 4)) / p.ridge_width) ** 2))

    bump = ridges(alpha)
    if p.crossed_ridges:
        bump = np.maximum(bump, ridges(-alpha))
    # Solid circular seed core plus four continuous tilted ridges, no atomic twist.
    radius = 0.5 * (1 - p.ridge_height + p.ridge_height * bump)
    end = np.clip((np.abs(z) - (0.5 - p.cap_fraction)) / p.cap_fraction, 0, 1)
    radius *= 1 - 0.3 * end
    return np.maximum(np.hypot(x, y) - radius, np.abs(z) - 0.5)


def build_surface(p, symbol: str) -> SurfaceMesh:
    extent = bounds(p) * 1.12
    # Equal normalized resolution per axis: mesh cost is independent of physical size.
    n = p.mesh_resolution
    axes = [np.linspace(-value, value, n) for value in extent]
    grid = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1)
    values = envelope_field(grid.reshape(-1, 3), p).reshape((n, n, n))
    spacing = tuple(float(axis[1] - axis[0]) for axis in axes)
    vertices, faces, _, _ = marching_cubes(values, level=0, spacing=spacing, allow_degenerate=False)
    vertices -= extent
    mesh = SurfaceMesh(vertices=vertices, faces=faces.astype(np.int32), element=symbol)
    validate_mesh(mesh)
    return mesh


def validate_mesh(mesh: SurfaceMesh) -> None:
    from surfaces.structures import validate_element

    validate_element(mesh.element)
    v, f = mesh.vertices, mesh.faces
    if (
        not isinstance(v, np.ndarray)
        or v.ndim != 2
        or v.shape[1] != 3
        or not 4 <= len(v) <= 100_000
        or not np.isfinite(v).all()
        or not isinstance(f, np.ndarray)
        or f.ndim != 2
        or f.shape[1] != 3
        or not 4 <= len(f) <= 200_000
        or not np.issubdtype(f.dtype, np.integer)
        or np.any(f < 0)
        or np.any(f >= len(v))
    ):
        raise ValueError("Invalid or oversized surface mesh.")
    area = np.linalg.norm(np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]]), axis=1)
    if np.any(area < 1e-15):
        raise ValueError("Surface mesh contains degenerate triangles.")


def fill_lattice(spec) -> Atoms:
    from surfaces.particles import MAX_CANDIDATES

    p = spec.particle
    half = bounds(p)
    repeats = 2 * np.ceil(half / spec.a).astype(int) + 3
    parent = bulk(spec.element, spec.crystal, a=spec.a, cubic=True)
    if int(np.prod(repeats)) * len(parent) > MAX_CANDIDATES:
        raise ValueError(
            "Too large for ASE atom filling. Disable 'Build ASE atoms' for a "
            "continuum surface at this size."
        )
    atoms = parent.repeat(tuple(map(int, repeats)))
    atoms.positions -= (repeats // 2) * spec.a
    atoms = atoms[envelope_field(atoms.positions, p) <= 1e-9]
    if not 1 <= len(atoms) <= MAX_PHYSICAL_ATOMS:
        raise ValueError(
            "ASE filling requires 1–20,000 atoms. Reduce size or disable 'Build ASE atoms'."
        )
    return atoms


def build_morphology(spec) -> Project:
    from surfaces.structures import assign_ids

    p = spec.particle
    mesh = build_surface(p, spec.element)
    atoms = fill_lattice(spec) if p.atomistic else Atoms()
    # One common origin and bounding cell for both representations.
    extent = bounds(p)
    offset = extent + spec.vacuum
    mesh.vertices += offset
    atoms.positions += offset
    atoms.cell = np.diag(2 * extent + 2 * spec.vacuum)
    atoms.pbc = False
    assign_ids(atoms)
    title = (
        "432 grooved cubic helicoid · model"
        if p.shape == "helicoid_iii"
        else "Fourfold ridged nanorod · model"
    )
    info = {
        "kind": "nanoparticle",
        "builder": "Analytic envelope → marching cubes / optional ASE lattice fill",
        "shape": p.shape,
        "representation": "surface + ASE atoms" if p.atomistic else "continuum surface only",
        "reference": REFERENCES[p.shape],
        "model_status": (
            "Reference-inspired parametric approximation; not a validated "
            "experimental reconstruction"
        ),
        "symmetry": "432 (proper cubic rotations)"
        if p.shape == "helicoid_iii"
        else (
            "mirror-symmetric crossed ridges" if p.crossed_ridges else "422 fourfold ridged model"
        ),
        "handedness": p.handedness,
        "lattice_deformation": False,
        "relaxed": False,
        "achieved_atoms": len(atoms),
        "mesh_triangles": len(mesh.faces),
        "dimensions_angstrom": np.ptp(mesh.vertices, axis=0).tolist(),
        "lattice_source": spec.lattice_source,
        "minimum_distance_angstrom": None,
        "limits": (
            "Surface geometry is approximate. No growth, strain, optical or "
            "ligand-handedness prediction. Uniform surface color does not "
            "represent site-resolved alloy composition. Atomistic filling is "
            "an undeformed FCC lattice inside the same envelope."
        ),
    }
    if len(atoms) > 1:
        from scipy.spatial import cKDTree

        info["minimum_distance_angstrom"] = float(
            cKDTree(atoms.positions).query(atoms.positions, k=2)[0][:, 1].min()
        )
    project = Project(atoms, atoms.copy(), spec, info, title=f"{spec.element} · {title}", mesh=mesh)
    project.appearance.render_style = "surface"
    project.camera.elevation = 25
    project.camera.azimuth = -55
    return project
