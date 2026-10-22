"""Serializable scientific and display state, independent of Qt."""

from dataclasses import dataclass, field

from ase import Atoms

MAX_PHYSICAL_ATOMS = 20_000
MAX_DISPLAY_ATOMS = 40_000


@dataclass
class ParticleSpec:
    shape: str = "cube"
    shells: int = 4
    width: float = 24.0
    length: float = 60.0
    thickness: float = 10.0
    axis: str = "001"
    twist: float = 120.0
    target_atoms: int = 1000
    rounding: str = "closest"
    energy_unit: str = "relative"
    energy_source: str = "Illustrative ratios; replace with verified surface energies"
    illustrative: bool = True
    facets: list[dict] = field(
        default_factory=lambda: [
            {"miller": [1, 0, 0], "layers": 6, "energy": 1.0},
            {"miller": [1, 1, 1], "layers": 4, "energy": 0.9},
        ]
    )


@dataclass
class StructureSpec:
    element: str = "Pt"
    crystal: str = "fcc"
    miller: tuple[int, int, int] = (1, 0, 0)
    a: float = 3.92
    c: float = 0.0
    nx: int = 5
    ny: int = 5
    layers: int = 4
    vacuum: float = 8.0
    lattice_source: str = "Editable Pt reference preset (3.92 Å)"
    internal_u: float = 0.25
    inversion: float = 0.0
    seed: int = 42
    termination: float = 0.0
    particle: ParticleSpec | None = None


@dataclass
class Camera:
    azimuth: float = -32.0
    elevation: float = 58.0
    projection: str = "Orthographic"
    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0


@dataclass
class Appearance:
    radius_scale: float = 0.85
    colors: dict[str, str] = field(default_factory=dict)
    radii: dict[str, float] = field(default_factory=dict)
    background: str = "#ffffff"
    cell: bool = False
    axes: bool = False
    legend: bool = True
    outlines: bool = True
    shading: bool = True
    copies_x: int = 1
    copies_y: int = 1


@dataclass
class ExportSettings:
    format: str = "PNG"
    width: float = 1800
    height: float = 1400
    unit: str = "px"
    dpi: int = 300
    transparent: bool = False
    margin: float = 8.0
    legend: bool = True
    axes: bool = False


@dataclass
class Project:
    atoms: Atoms
    original: Atoms
    spec: StructureSpec | None
    provenance: dict = field(default_factory=dict)
    operations: list[dict] = field(default_factory=list)
    camera: Camera = field(default_factory=Camera)
    appearance: Appearance = field(default_factory=Appearance)
    export: ExportSettings = field(default_factory=ExportSettings)
    export_presets: dict[str, dict] = field(default_factory=dict)
    title: str = "Pt · FCC (100)"
