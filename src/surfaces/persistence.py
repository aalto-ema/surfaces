"""Versioned JSON projects, strict validation, and atomic file replacement."""

import json
import math
import os
import tempfile
from dataclasses import asdict, fields
from pathlib import Path

import numpy as np
from ase import Atoms

from surfaces.model import (
    MAX_DISPLAY_ATOMS,
    MAX_PHYSICAL_ATOMS,
    Appearance,
    Camera,
    ExportSettings,
    Project,
    StructureSpec,
)
from surfaces.structures import validate_atoms, validate_element, validate_spec

SCHEMA_VERSION = 2


def atomic_write(path: str | Path, writer) -> None:
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.stem}-", suffix=path.suffix, dir=path.parent
    )
    os.close(descriptor)
    try:
        writer(Path(temporary))
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def atom_data(atoms: Atoms) -> dict:
    return {
        "numbers": atoms.numbers.tolist(),
        "positions": atoms.positions.tolist(),
        "cell": atoms.cell.array.tolist(),
        "pbc": atoms.pbc.tolist(),
        "site_ids": list(map(str, atoms.arrays["site_ids"])),
    }


def atoms_from_data(data: dict) -> Atoms:
    if not isinstance(data, dict) or set(data) != {
        "numbers",
        "positions",
        "cell",
        "pbc",
        "site_ids",
    }:
        raise ValueError("Invalid structure record.")
    numbers = data["numbers"]
    if not isinstance(numbers, list) or not 1 <= len(numbers) <= MAX_PHYSICAL_ATOMS:
        raise ValueError(f"Project needs 1–{MAX_PHYSICAL_ATOMS:,} atoms.")
    if any(type(n) is not int or not 1 <= n <= 118 for n in numbers):
        raise ValueError("Atomic numbers must be valid integers.")
    if (
        not isinstance(data["pbc"], list)
        or len(data["pbc"]) != 3
        or any(type(n) is not bool for n in data["pbc"])
    ):
        raise ValueError("Periodicity must contain three booleans.")
    positions = np.asarray(data["positions"], dtype=float)
    cell = np.asarray(data["cell"], dtype=float)
    if positions.shape != (len(numbers), 3) or cell.shape != (3, 3):
        raise ValueError("Invalid position or cell dimensions.")
    ids = data["site_ids"]
    if (
        not isinstance(ids, list)
        or len(ids) != len(numbers)
        or any(not isinstance(i, str) or not i or len(i) > 128 for i in ids)
    ):
        raise ValueError("Invalid site identity record.")
    atoms = Atoms(numbers=numbers, positions=positions, cell=cell, pbc=data["pbc"])
    atoms.set_array("site_ids", np.asarray(ids))
    validate_atoms(atoms)
    return atoms


def record(cls, data: dict):
    if not isinstance(data, dict):
        raise ValueError(f"Invalid {cls.__name__} settings.")
    allowed = {f.name for f in fields(cls)}
    if set(data) - allowed:
        raise ValueError(f"Unknown {cls.__name__} fields; this file may need a newer application.")
    return cls(**data)


def finite_range(value, low, high, label):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number.")
    if not low <= value <= high:
        raise ValueError(f"{label} must be between {low} and {high}.")


def validate_export(settings: ExportSettings) -> None:
    if settings.format not in ("PNG", "TIFF", "PDF", "SVG"):
        raise ValueError("Unsupported export format.")
    if settings.unit not in ("px", "mm", "in", "pt"):
        raise ValueError("Unsupported export size unit.")
    finite_range(settings.width, 0.01, 20000, "Width")
    finite_range(settings.height, 0.01, 20000, "Height")
    finite_range(settings.dpi, 36, 1200, "DPI")
    if type(settings.dpi) is not int:
        raise ValueError("DPI must be an integer.")
    finite_range(settings.margin, 0, 30, "Margin")
    for name in ("transparent", "legend", "axes"):
        if type(getattr(settings, name)) is not bool:
            raise ValueError(f"{name} must be a boolean.")


def validate_display(project: Project) -> None:
    import re

    camera, appearance = project.camera, project.appearance
    finite_range(camera.azimuth, -1e9, 1e9, "Azimuth")
    finite_range(camera.elevation, -90, 90, "Elevation")
    finite_range(camera.zoom, 0.15, 8, "Zoom")
    finite_range(camera.pan_x, -100, 100, "Pan x")
    finite_range(camera.pan_y, -100, 100, "Pan y")
    if camera.projection not in ("Orthographic", "Perspective"):
        raise ValueError("Unknown camera projection.")
    finite_range(appearance.radius_scale, 0.1, 3, "Radius scale")
    for name in ("cell", "axes", "legend", "outlines", "shading"):
        if type(getattr(appearance, name)) is not bool:
            raise ValueError(f"{name} must be a boolean.")
    for n in (appearance.copies_x, appearance.copies_y):
        if type(n) is not int or not 1 <= n <= 5:
            raise ValueError("Display copy counts must be integers between 1 and 5.")
    if len(project.atoms) * appearance.copies_x * appearance.copies_y > MAX_DISPLAY_ATOMS:
        raise ValueError(f"Project exceeds {MAX_DISPLAY_ATOMS:,} displayed atoms; reduce copies.")
    if not isinstance(appearance.colors, dict) or not isinstance(appearance.radii, dict):
        raise ValueError("Element appearance settings must be dictionaries.")
    for color in [appearance.background, *appearance.colors.values()]:
        if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValueError("Colors must use #RRGGBB notation.")
    for symbol, radius in appearance.radii.items():
        validate_element(symbol)
        finite_range(radius, 0.01, 20, f"{symbol} radius")
    for symbol in appearance.colors:
        validate_element(symbol)
    validate_export(project.export)
    if not isinstance(project.export_presets, dict):
        raise ValueError("Export presets must be a dictionary.")
    for name, data in project.export_presets.items():
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            raise ValueError("Invalid export preset name.")
        validate_export(record(ExportSettings, data))


def to_data(project: Project) -> dict:
    validate_display(project)
    if project.spec:
        validate_spec(project.spec)
    validate_atoms(project.atoms)
    validate_atoms(project.original)
    validate_operations(project.operations, set(map(str, project.atoms.arrays["site_ids"])))
    return {
        "schema_version": SCHEMA_VERSION,
        "title": project.title,
        "atoms": atom_data(project.atoms),
        "original": atom_data(project.original),
        "spec": asdict(project.spec) if project.spec else None,
        "provenance": project.provenance,
        "operations": project.operations,
        "camera": asdict(project.camera),
        "appearance": asdict(project.appearance),
        "export": asdict(project.export),
        "export_presets": project.export_presets,
    }


def validate_operations(operations, site_ids):
    if not isinstance(operations, list):
        raise ValueError("Operation history must be a list.")
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("kind") not in (
            "composition",
            "explicit",
            "layered",
            "reset_to_original",
        ):
            raise ValueError("Invalid composition operation record.")
        if "assignments" in operation:
            assignments = operation["assignments"]
            if not isinstance(assignments, dict) or not set(assignments) <= site_ids:
                raise ValueError("Composition history references invalid site identities.")
            for symbol in assignments.values():
                if not isinstance(symbol, str):
                    raise ValueError("Assignment species must be chemical symbols.")
                validate_element(symbol)
        if operation["kind"] == "layered":
            validate_operations(operation.get("layers"), site_ids)


def save_project(project: Project, path: str | Path) -> None:
    data = to_data(project)
    encoded = json.dumps(data, indent=2, allow_nan=False, ensure_ascii=False)
    atomic_write(path, lambda target: target.write_text(encoded, encoding="utf-8"))


def from_data(data: dict) -> Project:
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int:
        raise ValueError("This is not a Surfaces project.")
    if data["schema_version"] not in (1, SCHEMA_VERSION):
        raise ValueError(
            f"Unsupported project version {data['schema_version']}. "
            "This app supports versions 1 and 2."
        )
    try:
        atoms, original = atoms_from_data(data["atoms"]), atoms_from_data(data["original"])
        if list(atoms.arrays["site_ids"]) != list(original.arrays["site_ids"]):
            raise ValueError("Original and edited structures must have matching ordered site IDs.")
        if (
            not np.array_equal(atoms.positions, original.positions)
            or not np.array_equal(atoms.cell.array, original.cell.array)
            or not np.array_equal(atoms.pbc, original.pbc)
        ):
            raise ValueError("Species edits must preserve original geometry and periodicity.")
        spec = record(StructureSpec, data["spec"]) if data.get("spec") else None
        if spec:
            if data["schema_version"] == 1 and spec.crystal not in ("fcc", "bcc", "hcp"):
                raise ValueError("Version 1 projects cannot contain compound recipes.")
            if (
                not isinstance(spec.miller, list)
                or len(spec.miller) != 3
                or any(type(n) is not int for n in spec.miller)
                or not any(spec.miller)
            ):
                raise ValueError("Invalid recipe Miller indices.")
            spec.miller = tuple(spec.miller)
            finite_range(spec.a, 0.01, 100, "Lattice a")
            finite_range(spec.c, 0, 100, "Lattice c")
            finite_range(spec.vacuum, 0, 1000, "Vacuum")
            for n in (spec.nx, spec.ny, spec.layers):
                if type(n) is not int or not 1 <= n <= 200:
                    raise ValueError("Invalid recipe repeat/layer count.")
            validate_spec(spec)
        if not isinstance(data.get("provenance", {}), dict) or not isinstance(
            data.get("operations", []), list
        ):
            raise ValueError("Invalid provenance or operation history.")
        if not isinstance(data.get("title"), str) or not 1 <= len(data["title"]) <= 500:
            raise ValueError("Invalid project title.")
        project = Project(
            atoms,
            original,
            spec,
            data.get("provenance", {}),
            data.get("operations", []),
            record(Camera, data.get("camera", {})),
            record(Appearance, data.get("appearance", {})),
            record(ExportSettings, data.get("export", {})),
            data.get("export_presets", {}),
            data["title"],
        )
        validate_operations(project.operations, set(map(str, atoms.arrays["site_ids"])))
        validate_display(project)
        return project
    except (KeyError, TypeError, IndexError) as exc:
        raise ValueError(f"Incomplete or malformed project: {exc}") from exc


def load_project(path: str | Path) -> Project:
    path = Path(path)
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Project exceeds the 64 MiB file limit.")
    data = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"Invalid JSON number: {value}")
        ),
    )
    return from_data(data)
