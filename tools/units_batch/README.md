# Units-batch equivalence harness

The units and naming batch rewrites simcase documents from `"openphysics": "0.2"` to
`"0.3"` (values carry their units, full quantity names, a `length_unit` per geometry
component, no `units` block) while keeping today's document skeleton. This folder checks
that nothing else moves: every shipped example and every frozen fixture, as a 0.2 document
on the baseline code, must hand the solvers and the mesher the same inputs and save the same
bytes as its 0.3 twin on the new code, under a closed list of transforms (check P2-1 of the
batch). Compared with itself (the same 0.2 documents on both sides), it is the identity check
of a refactor (P2-3), and the later galerkin step re-runs it with the batch head as baseline.

Nothing here ships. No package under `packages/` imports these files;
`tests/simcase/test_units_batch_equivalence.py` asserts it, and the folder has no
`__init__.py`, so it is not a package.

| Path | What it holds |
|---|---|
| `record.py` | Runs documents against one source tree and records every solver and mesher input and every saved byte |
| `compare.py` | Compares two recordings, identity or through the layout maps |
| `convert_v02.py` | Converts a 0.2 document to 0.3 (the converted corpus) |
| `maps/corpus.json` | How each physics type is compared: `identity` or `layout` |
| `maps/<old field layout>.json` | One map per saved layout, added by the commit that converts that kind |
| `fixtures/v02/` | Frozen 0.2 documents for forms no example covers, taken from the tests; read only by the baseline code |
| `fixtures/v03/` | Their 0.3 twins, added by the commit that converts each kind |

## Running it

The test runs the whole comparison when `OPENPHYSICS_BATCH_BASELINE` names the baseline,
the merge base with `main`; without it the test is skipped and reported as not run:

```bash
OPENPHYSICS_BATCH_BASELINE=$(git merge-base HEAD origin/main) \
  python -m pytest -q -ra tests/simcase/test_units_batch_equivalence.py
```

It checks out the baseline in a temporary `git worktree`, records the baseline's
`examples/simcase/*.json` and `fixtures/v02/` there and this checkout's examples and
twins here, compares them and removes the worktree. `OPENPHYSICS_BATCH_REPORT=<folder>`
keeps the report, the plan and both manifests. The same steps by hand, from the
repository root:

```bash
git worktree add --detach <tmp>/base <baseline>
python -I tools/units_batch/record.py --root <tmp>/base --out <tmp>/old <tmp>/base/examples/simcase/*.json
python -I tools/units_batch/record.py --root . --out <tmp>/new examples/simcase/*.json
python tools/units_batch/compare.py --old <tmp>/old --new <tmp>/new --identity --report <tmp>/report.json
git worktree remove --force <tmp>/base
```

Documents are given as paths (the id is the file stem) or as `id=path`, or one per line in a
file passed with `--docs`. The output folders must be new or empty and outside the recorded
tree. Run both sides on one machine with the same interpreter and wheels, one BLAS thread
(`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`) and `MPLBACKEND=Agg`; the
test sets them. Bit equality is claimed only between two runs on the same machine.

**CI.** The `units-batch-equivalence` job of `.github/workflows/validate.yml` runs this test
on Ubuntu 24.04, macOS 15 and Windows 2022, one at a time, with the merge base as baseline. It
runs only on manual dispatch (`gh workflow run validate.yml --ref <branch>`), is not part of
the required `tests` check, and each platform is reported on its own. Record the run's
`github.sha` with the result: it must be the commit the result is claimed for.

## What is recorded

`record.py` puts `<root>/packages/*/src` first on `sys.path` and stops unless `simcase`,
`galerkin`, `meshine` and `physmat` were imported from there. It imports every submodule of
those four packages (`simcase.studio` excepted) and replaces each module attribute that is
one of these callables with a recording wrapper:

- `meshine.generate`; `galerkin.rectangle_mesh`;
- the galerkin solvers `solve_steady_heat`, `solve_transient_heat`, `solve_steady_electric`,
  `solve_steady_joule_heat`, `solve_temperature_joule_heat`, `solve_elasticity`,
  `freeze_temperature`, `solve_thermoelasticity`, `solve_cavity_box`,
  `solve_material_cavity_box`;
- `simcase.physics_em_modes2d.solve`; galerkin `solve_modes`, `assemble_mode_system`,
  `mode_coordinates`, `solve_scalar_coordinates`, `scalar_coordinate_system`,
  `assemble_stiffness`, `assemble_mass` and every public function of `galerkin.mode_overlap`;
  scipy's `eigs` and `eigsh` where galerkin and simcase bind them (shift, start vector and
  operator included);
- physmat `Material.eps` and `Material.index`; the tracking settings
  (`tracking_settings`, `subspace_settings`) and the `ModeTracker` and `SubspaceTracker`
  arguments (settings, solver mesh, physical weights).

Each call is stored with its nesting depth, its arguments before the call and the callbacks
it made. The result is stored for the meshers, the tracking settings and physmat's material
values; a solver's own result is compared through the saved arrays instead, because the
unselected candidates of an eigensolve (a near-null spurious mode and its neighbours) change in
their last bits from run to run on identical inputs (measured on `em_gaussian_overlap_vector`:
six runs, six different candidate arrays, identical saved arrays). The canonical forms:

- arrays as `(dtype, shape, sha256 of tobytes())`; sparse matrices by their stored arrays;
  a scipy `LinearOperator` by its shape, dtype and its product with a vector of ones;
- floats as `float.hex`, every real scalar with its Python type (`int` and `float` compare by
  value; a type difference is listed, not failed);
- mappings as ordered item lists (galerkin sums boundary entries in mapping order). The only
  exceptions are a galerkin `Mesh`'s `provenance_edges` and `selection_edges`: lookup tables
  no solver iterates, whose order follows set iteration and changes with hash randomization
  (measured on `thermoelastic_regions`);
- a meshine `Domain` as its default size, tolerances and pending regions in order, each with
  its name, size and loops (vertex coordinates in `float.hex`, a `Circle` as centre, radius
  and vertex count); its boundary namer as the string, or the names it gives at the midpoint
  of every input-loop segment and every output boundary edge; its size function on a 17 x 17
  grid of the domain box and at the output nodes; the mesher's nodes and triangles are also
  kept in `mesher_outputs.npz`;
- a callback of position or time by the number of its required positional parameters, as
  galerkin tells them apart: (points) and (time), (points, normals) or (points, normals,
  time), sampled at the mesh nodes, a 17 x 17 grid of the mesh box and the call's times;
  every call the solver makes to it is folded into a SHA-256 digest with its count;
- a temperature-dependent conductivity model as its valid range in `float.hex`, its values
  at 65 temperatures across that range, and the digest of every evaluation the solver made;
- physmat materials as their name and optical model (the record's citation and datum are
  metadata, not inputs).

Then the recorder saves the result (`result.save`), tries all three VTU exports
(`export_fields`, `export_time_series`, `export_sweep`; a refusal is recorded with its
exception) and stores the hashes of every saved file and `fields.npz` array, the parsed VTU
and PVD content, the document's notes and picometre roundings, the failure evidence of a
failed temperature-dependent Joule solve, and any binding the wrappers missed.

## What is compared

`compare.py --identity` compares every document of two recordings as equal documents;
`--plan plan.json` gives each document `identity` or `layout`. A document passes when:

- the call sequences are equal entry by entry;
- every `fields.npz` array has the same dtype, shape and bytes (after its map rule);
- every `summary.json`, `metadata_json` and failure-evidence leaf is equal under
  `float.hex`; `timings_s`, `timing` and `software_versions` are excluded, as are `log.txt`
  and `results.png` (only their presence is compared);
- the VTU exports agree array by array, the PVD time steps under `float.hex`, and a refused
  export is refused with the same exception;
- neither side has a picometre rounding, a load or recorder error, or a missed binding.

A layout map (`maps/<old field layout>.json`, format `openphysics-units-batch-map-v1`) is
closed: every old array and summary leaf is mapped or removed, and every new one is mapped or
listed as added. Its fields are `old_layout`, `new_layout`; `arrays` (`{old, new, f}`, `f` in
`=`, `neg` (`0.0 - x`), `conj`, `L1` (`x * 1e-6`), `L2` (`x * 1e-12`), `L1*conj`,
`L2*conj`, and `kernel-L1` for the nanometre and metre em fixtures, whose new nodes are the
recorded micrometre mesher nodes times 1e-6); `arrays_removed` (`{old, check}`, `check` in
`unit-metadata`, `time-tail`, `equals`) and `arrays_added` (regular expressions); `summary`
(dotted path patterns with `*` for one key, `[]` for one list index, `**` for the rest and
`["a.b"]` for a literal key; `f` in `=`, `neg`, `conj`, `L1`, `L1*conj`, `rad`
(`math.radians(old)`), `qdeg` (`q(f"{old!r} deg", "minimum_angle")`) or `removed` with a
check; the first matching rule applies); `summary_added` (beside the always allowed
`diagnostics`, `defaults_applied`, `resolved_inputs`, `extent`, `field_components`,
`time_convention`, `propagation`, each with everything under it); `identifiers` (identifier
strings, not compared); `vtu` and `vtu_added`; and `exceptions`.

`maps/corpus.json` names the mode of each physics type. A kind whose commit converts some
geometry forms only gives an object keyed by the 0.2 document's form instead: `rect` (a flat
rectangle), `regions` (shapes, a background material or a materials table) and `v1` (a version 1
geometry block). The heat rectangle commit (C5a) sets `rect` to `layout` for `thermal.steady2d`
and `thermal.transient2d` and keeps `regions` and `v1` in identity mode; it adds the four heat
rectangle maps and the twins `fixtures/v03/heat_transient_rectangle_sampled.json` and
`heat_transient_rectangle_sampled_boundary.json`.

The only comparisons that are not bitwise are the three pre-registered ones, each within 4
ulp: `propagation_loss` against 100 times the old `propagation_loss_db_cm`, `bend_loss`
against the old `bend_loss_db_90deg`, and `group_index_length_frame` (the group index of the
nanometre and metre em fixtures only). Each is also to be checked bitwise against its
defining formula on the new arrays; that check is added with the em commit, which writes the
formula. `compare.py` refuses any other transform or exception.

## The converter

`convert_v02.py` is a closed rule table: every key a 0.2 validator accepts is renamed, given
its unit or refused by name, and an unknown key is an error. Values whose 0.2 key carried
their SI unit are written as their `repr` digits in the canonical unit (`"45 W/(m K)"`);
document lengths keep their number in the old `units.length` when the quantity's menu takes
that unit, else the same exact value in a menu unit; shape numbers stay bare. The two
`outward_` inputs become `inward_heat_flux` and `inward_current_density` with `0.0 - x`;
cavity `[re, im]` becomes `{"re": re, "im": 0.0 - im}`; a Sellmeier `C` becomes
`resonance_wavelength_squared` and `range: [0, hi]` becomes `[null, hi]`; dimensional
defaults are written (em wavelength 1.55 and mesh size 0.2 in document units, the em
background `physmat:vacuum`, `bend_origin` 0, the Joule `temperature_tolerance` 1e-8 K);
em library names become `physmat:<Name>`, and local names equal to a library name are
renamed (`SiO2` to `oxide`, `Si` to `silicon`); a value outside its plausibility band is
written with `accept`. `--check` reads every written value back through `physmat.units` and
requires the old SI double (unit-suffixed keys) or the old exact length.

It covers all nine kinds in every form the examples and fixtures use: flat rectangles, flat
regions, version 1 `2d` and `axisymmetric` components and the cavity box. Not covered (an
error): version 1 `extrude` and `layers` features, a `units.length` outside the 0.3 length
units, and a study parameter other than the wavelength. That a converted document resolves
to the old SI tree (P2-2) needs the 0.3 reader and is checked by each kind's commit.

## Fixtures

Frozen at the baseline commit from the test builders named below (the build ran the builder
functions and wrote their documents as JSON); `derived` marks a document no test builds,
made from the named one to cover a listed form.

| Fixture | Source |
|---|---|
| `heat_axisymmetric_cylinder`, `_transient` | `test_thermal_axisymmetric_regions.py`: `cylinder()`, `cylinder_transient()` |
| `heat_axisymmetric_core_shell` | the same file, G4-2 (core 2 W/(m K), shell 0.5 W/(m K), size 0.05 mm) |
| `heat_axisymmetric_core_shell_transient` | derived: G4-2 with `cylinder_transient`'s changes (core c = 3.4e6 J/(m^3 K), size 0.1 mm, times 0, 1, 2 s) |
| `heat_regions_canonical_steady`, `_transient` | `test_thermal_length_canonical.py`: `_problem()`, `_problem(transient=True)` |
| `heat_v1_interior_dirichlet` | `test_thermal_named_boundaries.py`, G6-2: the fixed `seam` selection |
| `heat_transient_rectangle_sampled` | `test_transient_boundary.py`: `dirichlet_only_documents()["sampled"]` |
| `heat_transient_rectangle_sampled_boundary` | derived: `transient_thermal_boundary` with sampled `values_k` on `left` |
| `heat_transient_regions_sampled` | derived: `test_thermal_named_boundaries.plate` with a void hole tagged `inner`; sampled `values_k` on `left` and on `inner` |
| `electric_e1_series`, `electric_e2_parallel` | `test_electric_regions.py`, E1 and E2 |
| `electric_e3_coax_0p8` | the same file, `coax(0.8)` (the coarsest E3 size) |
| `electric_current_terminal` | the same file, the current on the exterior `inner` tag |
| `joule_j1_series`, `joule_j4_convective`, `joule_j2_coax_0p4` | `test_joule_regions.py`: `strip(SERIES)`, `strip(CONVECTIVE)`, `coax(0.4)` |
| `joule_current_terminal` | the same file, the current-driven terminal |
| `joule_rectangle_robin_and_flux` | `test_electric_joule.py`, `test_current_driven_robin_and_flux` |
| `joule_temperature_iteration_failure` | the same file, `test_failed_solve_cli_evidence` (iterations): a failed solve and its evidence |
| `mechanics_j1_stress`, `_strain`; `mechanics_k1_stress`, `_strain` | `test_mechanics.py`, J1 and K1 |
| `mechanics_r1_elastic_*`, `mechanics_r1_thermoelastic_*` | `test_mechanics_regions.py`, R1 (both planes) |
| `mechanics_r2_v1_stress`, `mechanics_r2_flat_strain` | the same file, R2 (version 1 and flat blocks) |
| `mechanics_r4_bore_0p5` | the same file, R4 at 0.5 mm with the `bore` selection |
| `mechanics_r5_stress`, `_strain`, `mechanics_r5b` | the same file, R5 and R5b |
| `mechanics_unit_variant_*` | the same file, the two physics variants of the length-unit test |
| `em_sellmeier_range` | `test_length_canonical.py`, `_rib_with_polygon_and_sellmeier()` |
| `em_sellmeier_open_lower_bound` | derived: the same with `range: [0.0, 6.7]` |
| `em_lossy_film_vector` | `test_lossy_modes.py`, `document("vector")` (`{"n": 3.48, "k": 0.01}`) |
| `em_lossy_scalar_tracked_sweep` | the same file, the scalar sweep of `test_complex_sweep_keeps_imaginary_derivative` |
| `em_pml_scalar`, `em_pml_bent_vector` | `test_pml_contract.py`, `document("scalar")`, `document("vector", bend=True)` |
| `em_gaussian_overlap_scalar`, `_vector` | `test_modes_postprocessing.py`, `slab_document(..., 0.04)` |
| `em_length_nm_*`, `em_length_m_*` | `test_length_canonical.py`, `_written_in` of `FIBER`, the Sellmeier rib, `VECTOR_SLAB` and `VECTOR_FIBER_SUBSPACE_SWEEP` |
| `cavity_wall_conductivity`, `cavity_dielectric_background` | `test_cavity3d_materials.py`, the single-wall and background tests |
| `cavity_complex_permeability` | derived: `_small(slab_document())` with `relative_permeability: [1.5, -0.01]` |

The rectangle fixtures J1 and K1 are recorded as written; whether their corners and lengths
keep today's doubles under the 0.3 reader is measured by the mechanics commit, and a fixture
that does not leaves P2-1 with its reason.

`make_fixtures.py` records how `fixtures/v02/` was built: it imports the test builders of 627eb28, so it runs only
against a checkout of that commit. The fixtures are frozen and are not regenerated.
