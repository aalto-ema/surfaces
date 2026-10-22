# Coding guidance

## Product intent

Build a polished desktop app for scientific figures and exploration of crystalline
material surfaces. Use PySide6 for the UI and ASE (`ase.Atoms`) as the scientific
foundation. The default visual direction is light, restrained, and scientific.
An FCC Pt (100) slab is the first end-to-end reference case.

Read `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`, and `docs/DESIGN.md` before making
substantial changes. Keep those documents consistent with implemented behavior.
`README.md` must distinguish available features from planned ones.

## Working practices

- Inspect existing code and local instructions before editing. Preserve user work.
- Finish coherent changes; do not leave fake controls or claim planned features work.
- Use Python 3.11+, type hints, small modules, and explicit units and data contracts.
- Prefer established libraries to handwritten crystallographic calculations.
- Keep scientific logic independent of Qt; UI widgets must not own scientific state.
- Add dependencies only for a concrete need. Record major choices and tradeoffs in
  `docs/DECISIONS.md`. Do not switch UI frameworks or silently replace ASE.
- Keep root `run_app.py` usable from any working directory. Resolve assets relative
  to packages, never the shell's working directory.
- Use `python -m ruff check .` and `python -m ruff format --check .` when available.
  Run meaningful tests for changed behavior. Explain unavailable checks candidly.
- Do not add tests that merely duplicate implementation. Scientific calculations,
  composition assignment, serialization, and export semantics need behavioral tests.
- Verify UI and figures visually as well as programmatically. Include actual output
  checks when modifying rendering; a successful save call is insufficient evidence.

## Scientific correctness

- Store geometry in ASE, distances in ångströms, and angles in degrees at boundaries.
- Validate element symbols, lattice parameters, Miller indices, repeat counts,
  layer counts, vacuum, composition, and site selections before generation.
- Treat Miller indices as indices relative to a stated bulk cell. Respect different
  crystallographic conventions; do not route every lattice through an FCC builder.
- Record builder, cell convention, lattice constants and their source, periodicity,
  termination where applicable, and all composition rules in the project model.
- Keep display replication separate from the physical slab and its atom identities.
- For alloys, distinguish assigning elements on an ideal lattice from relaxation.
  Do not imply substitutions alone produce a relaxed or equilibrium structure.
- For compounds, require a formula and explicit prototype/basis. Read
  `docs/COMPOUNDS.md`; never synthesize an oxide by treating its formula as one atom
  or randomly assigning its bulk element ratio to a monometallic lattice.
- Preserve ASE multilayer registry for compound cuts. Do not repeat a one-cell
  slab after ASE has made its c vector perpendicular for an oblique Miller cut.
  Validate formula ratios, sublattice counts/coordination, and representative cuts.
- Keep the searchable compound catalog and documented examples consistent. Label
  illustrative parameters, spinel inversion quantization, finite periodic ordering,
  and unassessed polar/asymmetric terminations explicitly. Do not infer phase stability,
  charge balance, ionic radii, or magnetic order from an element-only geometry.
- Atomic radii are model-dependent. Default to named, documented covalent radii
  from ASE, with per-element overrides and a separate global display scale. Never
  call a single radius table an exact atomic size. Missing values need a clear UI
  error or an explicit user-provided radius, not an unnoticed arbitrary fallback.
- Keep geometry unchanged by visual radius, color, camera, or lighting edits.
- Random composition uses a local seeded generator. Persist both the seed and
  realized site assignments. Specify the integer rounding policy for fractions.
- Use persistent atom/site IDs. Do not treat transient array indices as durable IDs.
  Preserve IDs through edits and record how regeneration affects existing selections.
- Layer order is bottom-to-top along the documented surface normal; show that order
  in the UI. Handle floating-point tolerances when identifying layers.

## Visual and export quality

- Share scene data, camera, radii, colors, and composition between preview and export.
- Never implement publication exports as screenshots of a widget.
- Support PNG, TIFF, PDF, and SVG with explicit size and background settings.
- Raster exports need exact pixel dimensions, optional physical size and DPI, clean
  antialiasing, and tested alpha. Vector exports need explicit physical dimensions.
- SVG/PDF must retain vector atoms, outlines, and text where the scene supports it.
  Any rasterized rendering mode must be clearly disclosed before export.
- Transparent output must omit background fills. Verify format-specific support;
  PDF page transparency means no painted background, not a raster alpha channel.
- Keep selection highlights and UI overlays out of exports unless explicitly enabled.
- Favor consistent design tokens and reusable controls over per-widget styling.
- Use responsive layouts, keyboard navigation, visible focus, undo for edits, and
  actionable validation. Expensive builds/exports must not block the Qt UI thread.

## Verification priorities

Test Pt FCC (100) geometry against ASE, layer/site identity, exact alloy counts,
seed reproducibility, explicit and layered substitutions, project round trips,
camera consistency, clipping, raster dimensions and alpha, TIFF readability,
and valid PDF/SVG outputs. Use temporary paths, never repository-root output files.
Use Qt offscreen mode for suitable automated checks and manually inspect the actual
desktop UI for interaction and platform rendering. Avoid brittle pixel-perfect
assertions unless rendering conditions are controlled.

## Chiral morphology models

- Keep reference-inspired 432 grooved envelopes and fourfold ridged rods distinct
  from validated experimental reconstructions and legacy ribbon/lattice-twist models.
  Record the actual envelope equations and geometric handedness; do not infer a
  D/L-ligand assignment, growth mechanism, strain or optical response.
- Continuum-only projects have a validated surface mesh and zero generated atoms.
  Never add proxy atoms, report a downsampled count as physical, or enable site
  composition without ASE sites. Uniform surface color is not an alloy composition map.
- Surface/atom representations share coordinates, camera and export devices. Preserve
  vector surface triangles in SVG/PDF. Verify mesh closure, symmetry/mirror behavior,
  undeformed lattice filling, persistence, alpha and final visual output.
