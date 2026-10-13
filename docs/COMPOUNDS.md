# Compound surfaces: examples and limits

The app builds compounds from a **formula plus an explicit crystal prototype**.
Open **Structure → Compound examples and limits…**, search for a formula, choose
**Use example**, inspect the parameters, then **Generate surface**. The Generate
button remains visible while the construction controls scroll.

You can also enter a formula in **Element / formula** and select a matching
**Crystal / prototype** manually. **Use matching compound preset** fills catalog
parameters when the normalized formula and prototype match. Other formulas with
compatible stoichiometry work with user-supplied parameters; the app does not infer
that a chosen phase is stable or even experimentally observed for those elements.

![Compound surface workspace](images/compound-workspace.png)

## Example catalog

All lengths below are in ångströms; `u` is a dimensionless fractional coordinate.
Except for the explicitly sourced PtO starting lattice, values are **illustrative
editable defaults**, not specimen-specific experimental constants. Source links
identify the structural model or builder, not a validation of every numerical value.

| Formula | Prototype | a (Å) | c (Å) | u | Spinel inversion | Notes |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| PtO | cooperite | 3.04 | 5.34 | — | — | Platinum monoxide: tetragonal PtO-type basis, not oxygen assigned to FCC Pt. |
| NiFe2O4 | spinel | 8.34 | — | 0.261 | 1 | Nickel ferrite: inverse occupancy. Fe on tetrahedral sites; equal Ni/Fe counts on octahedral sites. |
| CoFe2O4 | spinel | 8.39 | — | 0.261 | 1 | Cobalt ferrite: illustrative fully inverse model; actual inversion is sample-dependent. |
| MgAl2O4 | spinel | 8.08 | — | 0.261 | 0 | Normal spinel: Mg on tetrahedral and Al on octahedral sites. |
| Fe3O4 | spinel | 8.4 | — | 0.2545 | 1 | Magnetite geometry. Fe valences and magnetic order are not represented. |
| NiO | rocksalt | 4.17 | — | — | — | Cubic ideal nickel monoxide. Magnetic/rhombohedral distortions are omitted. |
| MgO | rocksalt | 4.21 | — | — | — | Magnesium oxide with distinct cation and anion sublattices. |
| NaCl | rocksalt | 5.64 | — | — | — | Sodium chloride: sixfold-coordinated AB structure. |
| ZnS | zincblende | 5.41 | — | — | — | Cubic zinc sulfide polymorph with tetrahedral coordination. |
| ZnO | wurtzite | 3.25 | 5.21 | 0.382 | — | Hexagonal zinc oxide; three-index Miller notation, not four-index notation. |
| CsCl | cesiumchloride | 4.12 | — | — | — | CsCl-type cubic AB basis; not the rocksalt AB geometry. |
| TiO2 | rutile | 4.594 | 2.959 | 0.305 | — | Rutile polymorph. Anatase and brookite are different, unsupported prototypes. |
| CaF2 | fluorite | 5.46 | — | — | — | Fluorite AB2; cations and anions occupy different sublattices. |
| SrTiO3 | perovskite | 3.905 | — | — | — | Ideal cubic perovskite; octahedral tilts and low-temperature distortions omitted. |

Ready-to-open projects are provided in `examples/pto001.surfaces.json` and
`examples/nife2o4-001-inverse.surfaces.json`. Both start with a (001) cut, 2 × 2
in-plane repeats, two complete cut cells, and 8 Å vacuum on each side.

## Formula and prototype rules

- Flat chemical formulas with positive integer counts are accepted: `PtO`,
  `NiFe2O4`, `SrTiO3`. Overall multiples are reduced (`Ni2Fe4O8` → `NiFe2O4`).
  Element symbols are case-sensitive and each element is written once.
- AB prototypes: cooperite, rocksalt, zincblende, cesiumchloride, wurtzite. The first
  formula element is the A basis species and the second is B. Swapping them can
  change site chemistry, particularly for cooperite.
- AB2 prototypes: rutile and fluorite. The count-1 species is A, count-2 species B.
  Stoichiometry does not distinguish polymorphs: TiO2/rutile does not produce anatase.
- ABO3: ideal cubic perovskite. The first non-oxygen element is A (corner site), the
  second is B (body-center site), and oxygen occupies face centers. Distinct A/B
  cations are required. `SrTiO3` and `TiSrO3` specify different site assignments.
- AB2O4: spinel. The count-1 cation is A, count-2 cation B, and O is the anion.
  A3O4 compounds such as Fe3O4 use the same element for both cation slots; formal
  valence distinctions are not represented.
- Charges, noninteger counts, mixed-occupancy notation, parentheses, hydrates,
  isotope labels, internal spaces, and Unicode subscripts are unsupported. For
  example, use `NiFe2O4`, not `NiFe2O₄`; `Ni(OH)2` is not accepted by this workflow.
  Counts are limited to 1–1,000 per written element and formula length to 80 characters.

## Cell, surface, and termination limits

ASE constructs an explicit multi-species bulk basis before cutting. The builders
use conventional cubic cells where applicable, a tetragonal cell for cooperite and
rutile, and the hexagonal cell for wurtzite. Miller indices refer to that stated cell.
The app uses three-index notation; four-index Miller–Bravais notation is unsupported.

**Layers / cut repeats counts full oriented bulk cells for compounds**, not atomic
planes. Details and the composition layer table show the actual planes, ordered
bottom → top along the surface normal. Tilted cuts use ASE's multilayer stacking to
preserve lateral registry. A complete-cell cut window retains bulk stoichiometry;
individual exposed planes and top/bottom species need not have the bulk ratio.

**Compound cut phase**, from 0 inclusive to 1 exclusive, shifts the lower boundary
by that fraction of one oriented cut-cell period. The upper boundary moves with it.
Atoms are taken from an extended ASE stack, then the slab is centered with vacuum.
This preserves atom counts and the correct lattice stacking. It offers alternative
terminations within a fixed stoichiometric thickness; it does not enumerate every
possible reconstructed or nonstoichiometric surface. Phases within the same gap
between atomic planes can yield identical centered slabs.

The app does **not** ensure identical top/bottom terminations, charge neutrality of
individual planes, nonpolarity, zero dipole, thermodynamic stability, or a relaxed
surface. Use a prepared fully occupied slab for a specific termination, reconstruction,
vacancy geometry, other space group, or relaxed structure. Existing **Import structure**
loads the last frame of CIF/XYZ and other ASE formats; it displays the imported
geometry and does not automatically cut a bulk CIF. Partial occupancies are not modeled;
prepare an explicit fully occupied structure before importing.

Lattice `a` and required `c` are editable in the range 0.01–100 Å. Cubic models use
`b = c = a`; tetragonal models use `b = a`; wurtzite uses the hexagonal angle convention.
Arbitrary independent cell angles/parameters are not editable in these prototypes.
Internal-coordinate guardrails are `u = 0.24–0.27` for spinel (setting 2), `0.25–0.35`
for rutile, and `0.30–0.45` for wurtzite; other basis geometries require an imported slab.

## Spinel cation occupations

The parent spinel basis uses space group 227, **setting 2**, with eight tetrahedral,
16 octahedral, and 32 oxygen sites per conventional cell. `u` uses that origin convention.
For a formula AB2O4, inversion x means:

- x = 0: A occupies all tetrahedral sites; B occupies all octahedral sites.
- x = 1: B occupies tetrahedral sites; octahedral sites have equal A/B counts.
- Intermediate x: exchange `round(8 × x)` A/B pairs, rounding halves upward.
  Thus x is realized in steps of 1/8; x = 0.30 gives x = 0.25. Details records both values.

A local seed selects explicit occupied sites. The realized **single conventional
bulk cell** is then repeated periodically. This is a reproducible finite ordering
model, not fractional occupancy, random disorder throughout a macroscopic slab, or
an optimized cation ordering. The chemical ratio stays AB2O4. Explicit occupations
may reduce symmetry relative to the Fd-3m parent; no resulting space group is inferred.
NiFe2O4's catalog example chooses x = 1. Fe3O4 cannot visualize distinct Fe valences
with the current element-only atom model, even when x is specified.

## Editing, figures, and reproducibility

Species edits and random-alloy operations still target physical atoms. On a compound,
these can change stoichiometry and site chemistry; they do not validate charge balance.
Choose selected layers/sites deliberately. **Reset to original species** restores the
constructed compound. Covalent radii remain the default; ionic/oxidation-state radii,
bonds, formal charges, magnetic moments, and electron density are not modeled.

Save/load, undo/redo, atom selection, element styling, and PNG/TIFF/PDF/SVG export
work with compounds through the same scene model. Project schema 2 records the
formula/prototype, u, inversion, seed, cut phase, construction provenance, and realized
atoms. Version 1 elemental projects load with default new fields and save as version 2,
without regenerating their geometry. Sublattice occupations can be inspected in the
construction provenance; generic imported ASE arrays are not retained in project files.

Existing practical limits remain: 20,000 physical atoms, 40,000 displayed atoms,
in-plane repeat counts ≤100, cut repeats ≤200, 8-bit RGBA raster output up to 24 MP,
and 30 undo snapshots. Spinels contain many atoms per cell, so counts grow quickly:
NiFe2O4 with 2 × 2 × 2 cut-cell repeats contains 448 atoms.

## Model references

- [ASE bulk builders](https://docs.ase-lib.org/ase/build/build.html) and
  [space-group construction](https://docs.ase-lib.org/ase/spacegroup/spacegroup.html)
  provide the construction APIs and explicit basis conventions.
- [Li, Xia, and Srivastava (2020), tetragonal PtO](https://www.frontiersin.org/journals/chemistry/articles/10.3389/fchem.2020.00704/full)
  describes the P4₂/mmc structure, Pt/O basis, and experimental starting lattice
  used for the PtO example.
- [Dey et al. (2019), nickel ferrite](https://arxiv.org/abs/1903.01739)
  provides context for the inverse-spinel parent model and the limitations of assuming
  that one cubic ideal structure describes every temperature and cation ordering.

The catalog is implemented in `src/surfaces/compounds.py`; when adding an example,
keep this table and its notes consistent with the runtime catalog.
