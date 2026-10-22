# Product specification

## Audience and priorities

The main use is scientific figures and structure exploration. Prioritize correct,
inspectable geometry, easy composition editing, excellent visualization, and
publication-ready exports. Simulation preparation may follow; calculators,
relaxation, and simulation job management are outside the initial scope.

## Surface creation

The first reference workflow is a monometallic FCC Pt (100) slab. Inputs include
element, crystal structure, Miller indices, lattice parameters, in-plane repeat
counts, number of atomic layers, and vacuum thickness. Show units and derived atom
counts. Provide sensible editable defaults with their provenance. ASE reference
values are starting points, not experimentally verified constants for every case.

Start with FCC low-index surfaces. Expand to BCC, HCP, generic Miller cuts, and
imported structures after the core workflow works. Unsupported combinations need
clear explanations. Show the bulk cell convention, surface normal, cell vectors,
periodic directions, and layer ordering in an accessible details view.

Vacuum is space on each side of the slab when using ASE centering; label the
parameter accordingly. Do not change this meaning between builders. Physical slab
generation and repetition shown for visual context must remain distinguishable.

## Composition editing

Support these modes through one composition panel:

- Single element: assign the whole slab.
- Random alloy: elements, target fractions, seed, and scope (whole slab, layers,
  or selected sites). Show achieved integer counts and achieved fractions.
- Explicit sites: click atoms and assign an element; allow a simple site table
  for precise editing and multiple selection.
- Layered structure: an ordered bottom-to-top layer table with a single element
  or a random mixture per layer.

Apply operations sequentially to the current structure; the UI explains which
sites each operation will replace. Selection and layer constraints must be visible.
Offer undo/redo and a reset to the original generated slab. No cryptic text syntax
is required for basic usage. Advanced structured recipes can be added later.

Use largest-remainder allocation for integer composition counts, with ties broken
by displayed element order. Shuffle site assignments with a local seeded generator.
Persist the actual assignment, since a seed alone is not portable across algorithm
changes. Reassigning species preserves lattice geometry unless a separate, explicit
geometry operation is performed.

Each element has its own named radius and color. Default radii are ASE covalent
radii; the UI labels the convention and permits overrides. This is a reproducible
visual model of atomic size, not a claim about exact metallic or ionic radii.

## Visualization

Provide a spacious central viewport, top/side/isometric presets, orbit, pan, zoom,
fit-to-slab, and projection selection. Default to orthographic projection for
figures. Support cell outlines, optional axes and element legend, background choice,
per-element appearance, and radius scaling without changing atomic coordinates.

Atom picking must select the frontmost visible atom. Stable site IDs and layer
information appear in the selection inspector. Keep a clear distinction between
editing a physical atom and picking a displayed periodic copy.

## Export

Required formats: PNG, TIFF, PDF, SVG. Provide solid or transparent background,
canvas size, margin, projection, and optional legend/axes. Raster size is specified
in pixels or converted from physical dimensions and DPI, with final pixels shown
before saving. Vector size is specified in mm/inches or points; DPI applies only
to embedded raster content. Persist export presets.

Preserve the current camera and appearance, frame intentionally, avoid clipping,
and exclude editing overlays by default. The preview shows export framing.
Confirm overwriting existing files. Failures preserve the existing file and provide
an actionable message. Verify each backend's transparency and color behavior.

## Persistence

Save a versioned project containing the realized ASE structure, stable site IDs,
construction recipe and provenance, composition operations and assignments,
appearance, camera, and export settings. Use a documented data format without
pickle or executable payloads. Validate loaded data and handle schema migrations.

## Delivery milestones

1. ASE Pt (100) slab builder, orthographic viewport, element radii/colors, camera
   presets, and verified PNG export; a complete useful vertical slice.
2. Exact seeded alloys, direct site editing, layer composition, undo/redo, and
   project save/load.
3. Verified TIFF/PDF/SVG exports, transparent output, physical sizing, presets,
   and final visual polish. All required formats must work before calling the
   initial product complete.
4. Additional crystal families, custom Miller surfaces, and structure import.

For every milestone, validate the scientific result and inspect the desktop UI and
representative exported figures. Benchmark responsive interaction on documented
hardware and slab sizes before setting hard performance guarantees.

## Implementation status — 2026-10-13

All four delivery milestones above have an implementation, including ASE imports
and FCC/BCC/HCP generic cuts. The README documents the workflows, scientific
conventions, output behavior, workload limits, and renderer approximations. Native
macOS QA and automated offscreen Qt/domain/export checks accompany the implementation;
packaging and native QA for additional platforms remain outside this first delivery.

## Compound workflow

Compounds are constructed from a formula and an explicit prototype, not alloy
percentages on an elemental lattice. The Structure panel exposes a searchable catalog
with 14 examples, including tetragonal PtO and inverse-spinel NiFe2O4. Supported
prototypes are cooperite, rocksalt, zincblende, cesiumchloride, wurtzite, rutile,
fluorite, cubic perovskite, and spinel. Lattice/basis parameters remain editable.
Spinels use a seeded 56-atom conventional cell, with inversion realized in 1/8 steps.
Compound thickness counts full oriented cells. A cut-phase control shifts a
stoichiometric window through an ASE stack to explore alternative terminations.

The [compound guide](COMPOUNDS.md) records examples, supported formula syntax,
site conventions, quantitative limits, and model assumptions. Bulk ratios do not
imply charge-balanced or nonpolar exposed surfaces. Scientific stability, magnetic
order, formal charges, relaxation, reconstruction, and fractional occupancies are
outside this geometry/figure workflow. Prepared fully occupied slabs can be imported
for other phases and terminations. Existing selection, composition, save/load, undo,
appearance, and figure exports work on the realized compound atoms.

## Nanoparticle extension — 2026-10-22

The Structure panel opens a nanoparticle studio with asynchronous preview, counts,
actual spans, minimum separation, and an explicit use action. Thirteen modes cover
ASE facet/Wulff clusters and geometric spheres, ellipsoids, rods, plates, twisted
rods and lattice-cut helicoidal ribbons. Elemental FCC/BCC/SC parents are supported;
compound/twinned particles are not synthesized. Wulff energies are supplied with
sources and an illustrative flag. Finite particles reuse composition, undo, picking,
appearance and figure export; periodic display copies are disabled. Version 3 saves
recipes and realized coordinates. See [Nanoparticle conventions and limits](NANOPARTICLES.md).

## Solid chiral morphology extension — 2026-10-22

The studio now also offers reference-inspired 432 grooved cubic models and fourfold
ridged nanorods. These represent compact cores with chiral surface features, with
adjustable gaps/ridges, caps and handedness. Solid surface and ASE atom views share
one camera and export path. Optional lattice filling is finite, undeformed FCC;
continuum-only mode supports larger sizes without atoms or site composition. The
app labels the shapes as parametric approximations, not experimental reconstructions.
See [Chiral morphology models](CHIRAL_MORPHOLOGIES.md).
