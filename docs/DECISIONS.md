# Decisions and assumptions

## Confirmed by the user

- Scientific figures and structure exploration are the main intended use.
- Default style is a light, restrained scientific interface.
- PySide UI, ASE foundation, and root `run_app.py` entry point.
- Monometallic and flexible multimetallic surfaces: random, explicit, and layered.
- Element-dependent atomic dimensions and high-quality visualization.
- PNG, TIFF, PDF, SVG; configurable dimensions and background transparency.

## Initial implementation choices

- Use PySide6 and a `src/surfaces` package with Python 3.11+.
- Start with FCC Pt (100), then expand surface families.
- Use orthographic projection by default for scientific figures.
- Use ASE covalent radii as the initial named visual convention; allow overrides.
- Persist realized alloy assignments, and use seeded largest-remainder allocation.
- Include project save/load and undo/redo to make exploration reproducible.

These choices may evolve with evidence. Record the reason when changing one.

## Follow-up decisions

- Rendering expansion: measure whether a dedicated 3D backend is worthwhile for
  larger scenes or exact intersecting-sphere occlusion; the chosen painter backend
  and its verified vector export path are described below.
- Supported operating systems and packaging targets; no platform-specific behavior
  should be introduced by accident.
- Supported workload: expand benchmarks before promising an interactive frame rate
  at the documented atom-count guardrails.
- Additional radius conventions and sources; distinguish covalent, metallic,
  and van der Waals meanings instead of combining tables silently.
- Structure import/export formats beyond figure export, if requested.

The project owner selected the MIT license for the public source repository.
Do not publish packages or create remote repositories without user authorization.

## Implemented decisions — 2026-10-13

- Selected a shared QPainter sphere renderer for the viewport, raster output,
  QPdfWriter, and QSvgGenerator. Verified PDF/SVG with no embedded images and visually
  compared reopened vectors with PNG/TIFF. It supports the figure-oriented workflow;
  overlapping-sphere occlusion and perspective projection remain approximations.
- Annotation font sizes use scene pixels, rather than device-dependent points,
  keeping proportions consistent at different output DPI. Text and strokes scale
  with figure width. Solid background colors use #RRGGBB; transparent export omits
  the fill entirely.
- Camera presets follow the oriented surface frame, including rotated imported
  cells. Cartesian axes remain world x/y/z.
- Adopted JSON project schema version 1. There is no older released schema to
  migrate; unknown versions are rejected rather than guessed. Imports deliberately
  retain geometry/species only and record omitted simulation constraints.
- Physical atoms are limited to 20,000 and displayed atoms to 40,000. Large layer and
  site tables use Qt models rather than allocating widgets per atom/plane. Raster
  exports are limited to 24 megapixels. Expensive builds, species assignments,
  loading/saving, exports, and previews run in workers while project mutations are
  disabled. Preview requests are coalesced to avoid stale results.
- Initial validation platform is macOS / Python 3.13 / PySide6 6.12 / ASE 3.29.
  Portable APIs are used, but Windows/Linux native QA and distribution packages
  remain future work.

## Compound models — 2026-10-13

- Formula plus explicit prototype defines a compound. Formula syntax is deliberately
  restricted to fully occupied integer compositions; no phase search or chemical
  stability inference is performed. The catalog has 14 examples across nine prototypes.
- PtO uses the P4₂/mmc (131) Pt/O basis reported by Li et al. (2020), with sourced
  experimental starting a/c. Other numerical catalog defaults are labeled illustrative.
- NiFe2O4 defaults to inverse spinel. The Fd-3m parent (227, setting 2) basis contains
  8 tetrahedral, 16 octahedral, and 32 oxygen sites. Seeded explicit A/B exchanges give
  an inversion fraction in steps of 1/8. The realized parent cell is repeated; its
  individual ordering is not asserted to preserve the parent space group.
- Compound cuts preserve full-cell stoichiometry and ASE multilayer registry. A phase
  selects a window through an extended stack, rather than vertically repeating an
  already-oriented cell. Polar/asymmetric cuts remain possible and unassessed.
- Project schema 2 adds compound recipe fields, with a geometry-preserving schema-1
  migration. The original elemental sample projects intentionally remain version 1
  to exercise backward compatibility.
- The Generate action stays outside the scrolling construction form so compound
  parameters do not push the primary action out of view.
# Python 3.11 Qt compatibility

The first hosted Linux run with PySide6 6.12.0 aborted during interpreter
finalization with `none_dealloc`, after completing the Qt tests. Python 3.13
on macOS and Windows completed shutdown normally. Temporarily constrain PySide6
to releases before 6.12 on Python 3.11; newer Python versions retain the existing
range. Keep Python 3.11 and the full Qt suite in CI to verify this workaround.
Revisit the constraint when a corrected binding release is verified on Python 3.11.
