# Architecture

## Modules

The source package is `src/surfaces`. Introduce modules as features need them:

| Module | Responsibility |
| --- | --- |
| `app.py` | Application lifecycle and top-level wiring |
| `domain/` | Validated specifications, project state, IDs, units |
| `structures/` | ASE builders, layers, composition assignment |
| `scene/` | Render-ready atoms, camera, picking, display replication |
| `rendering/` | Viewport and shared drawing/projection code |
| `exporting/` | Format adapters, sizing, safe output writing |
| `persistence/` | Versioned project serialization and migrations |
| `ui/` | Widgets, panels, commands, design tokens |

Avoid creating empty frameworks in advance. ASE is the source of truth for positions,
species, cell, and periodicity. Domain services can be exercised without a QApplication.

## State and commands

Maintain one project state, with explicit snapshots or commands for undoable edits.
A recipe describes generation; the realized structure records the result. Do not
regenerate a saved alloy merely on opening a project. Store persistent site IDs in
an ASE array and validate their uniqueness. Scene replication uses derived copy IDs
that refer back to the physical atom. Validate IDs when importing external structures.

Composition rules reference IDs or layers, not incidental renderer ordering.
Geometry regeneration either remaps IDs with a documented method or invalidates
dependent selections with a clear user-facing explanation.

Camera and appearance belong to serializable state. Renderers consume a scene
snapshot and never mutate geometry. Centralize projection, depth ordering, atom
radii, color handling, visible bounds, and framing.

## Rendering approach

Begin by evaluating a shared Qt QPainter path for orthographic publication scenes:
project atoms, depth-sort circles/spheres, and draw to both viewport and export
devices. Qt supplies PDF and SVG paint devices; Pillow can supply TIFF encoding
when needed. Validate actual vector content and transparency rather than assuming
the file extension proves capability.

Simple depth-sorted spheres are an approximation for occlusion. Check intersecting
spheres, tilted slabs, outlines, and dense scenes. If this fails the required visual
quality or interaction performance, evaluate a dedicated 3D renderer with measured
examples. Keep the scene contract renderer-independent. A GPU preview still needs
a deliberate publication-export path, with disclosed differences and visual checks.

Choose the renderer after comparing a Pt (100) slab, a layered bimetallic slab,
and a seeded alloy in top, side, and tilted views. Record the decision. Do not
silently embed a screenshot inside every PDF/SVG.

## Threading and files

Keep Qt widgets on the main thread. Expensive structure/export work uses copied
inputs in workers; return results through signals. Reject stale worker results when
the project revision changes. Support progress/cancellation where worthwhile.

Write exports and projects to temporary sibling files, then replace the destination
only on successful completion. Keep file format suffixes compatible with encoders.
Do not overwrite without the user's explicit save-dialog confirmation.

## Tests

Use pytest for domain behavior and pytest-qt for meaningful Qt interactions.
Test geometry against ASE reference construction and geometric invariants, not
just self-generated snapshots. Exercise round trips, composition count constraints,
unchanged positions after substitutions, seeds, error paths, and durable identities.
For exports, reopen raster files and inspect dimensions, alpha and content; parse
SVG and inspect PDF page dimensions/content. Supplement these checks with visual
inspection because valid files can still be aesthetically poor.

## Primary references

- [ASE surface builders](https://docs.ase-lib.org/_modules/ase/build/surface.html)
- [ASE generic surface construction](https://docs.ase-lib.org/_modules/ase/build/general_surface.html)
- [Qt SVG generation](https://doc.qt.io/qtforpython-6/PySide6/QtSvg/QSvgGenerator.html)
- [Qt PDF writing](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QPdfWriter.html)

Consult current primary documentation when implementing APIs or resolving scientific
conventions. These references inform the plan, not a claim of implemented support.

## Implemented module map

The compact implementation uses flat modules until a package split is justified:
`model.py` owns dataclasses; `structures.py` handles ASE and surface frames;
`composition.py` owns species assignment; `rendering.py` owns projection/drawing and
viewport interactions; `exporting.py` owns format devices; `persistence.py` owns
validated JSON and atomic writes; `window.py` wires the workspace; `*_ui.py` files
implement focused panels/dialogs. `ui_common.py` owns styling, reusable controls,
and worker lifecycle. Worker inputs are copies and project UI is disabled until
completion, so concurrent user edits cannot invalidate saved/exported snapshots.

Project schema version 1 contains `atoms` and `original` records (numbers, positions,
cell, pbc, site IDs), optional `spec`, provenance, composition operations, camera,
appearance, export settings, and presets. Load validates IDs, dimensions, finite
values, enums, matching original geometry, and operation references. No executable
payload or pickle is used. Unknown schema versions receive a clear error.

## Compound extension and schema 2

`compounds.py` owns the catalog, flat-integer formula validation, explicit prototype
bases, seeded spinel occupations, and compound cut windows. `compound_ui.py` owns
searchable examples and model limits. `StructureSpec.crystal` chooses either an
existing elemental family or a compound prototype; the legacy `element` field stores
an element symbol or a compound formula. New fields are `internal_u`, `inversion`,
`seed`, and `termination`. App controls expose only fields used by the selected model.

ASE bulk/space-group builders construct complete bases. Surface construction uses
an extended multilayer ASE stack before selecting the complete-cell cut window and
repeating in-plane. This preserves lateral registry for oblique cuts. The slab is
then made nonperiodic normal to the surface and centered with per-side vacuum.
Atom IDs are assigned only after the geometry is finalized.

Schema 2 saves these construction fields and realized geometry. Schema 1 elemental
projects migrate in memory through dataclass defaults, preserving atom identities,
geometry, species, and view state. Saving writes schema 2. Recipes are validated
through the shared `validate_spec` path; loading never regenerates a compound or alloy.
