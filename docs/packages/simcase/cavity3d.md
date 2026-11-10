# Rectangular cavity document and results

[한국어](../../locales/ko/pages/packages/simcase/cavity3d.md)

An `em.cavity3d` document holds one rectangular-box study. The case described
first is a vacuum box with perfect electric conductor (PEC) conditions on all
six faces; [Materials and conducting walls](#materials-and-conducting-walls)
adds constant, possibly lossy materials in axis-aligned boxes, a filled
background and finite-conductivity walls. Engine integration checks cover CLI
execution, unit conversion and saved-field reconstruction; these checks are
separate from the engine's numerical convergence acceptance.

## Input

The example is `examples/simcase/cavity_box.json`, also available from
`python -m simcase example cavity_box`. The headless workflow is:

```bash
python -m simcase example cavity_box > cavity.json
python -m simcase validate cavity.json
python -m simcase run cavity.json -o cavity_results
```

The documents are [format 0.3](document_format.md): every value carries its unit
(`"250 MHz"`, `"58 MS/m"`) and keys are registry quantity names. A format 0.2
cavity document is refused by name (`E-FORMAT`); its `units` block, `target_frequency_hz`,
`num_modes`, `conductivity_s_per_m` and `mesh.subdivisions` are unknown keys whose
message names the new key. `geometry.length_unit` is required, also when it is `"m"`
(menu `pm nm Angstrom um mm cm m in mil`). The six `geometry.domain` bounds `xmin`,
`xmax`, `ymin`, `ymax`, `zmin`, `zmax` are plain numbers in that unit; each is put on
the integer picometre grid once, each maximum must exceed its minimum, and a nonzero
origin is allowed. A 3D domain takes no `depth` (`E-KEY-UNKNOWN`). For the vacuum PEC
case, `geometry.background` is `{"material": "physmat:vacuum"}` (required: a missing
background is `E-KEY-MISSING`), `geometry.shapes` is empty, and `materials` is empty.
A box-only [version 1](geometry_document.md) `3d` component is read as this flat block.
Box-shaped materials, a filled background and finite-conductivity walls are
described in [Materials and conducting walls](#materials-and-conducting-walls);
arbitrary geometry and other boundary types are unsupported.

There must be exactly one named physics entry:

```json
{
  "physics": {
    "em1": {
      "type": "em.cavity3d",
      "boundary": "pec",
      "search": "near_target",
      "target_frequency": "250 MHz",
      "mode_count": 5
    }
  },
  "mesh": {"subdivision_count": [6, 6, 6]},
  "study": {"type": "single"},
  "results": {"save_fields": true, "plots": false}
}
```

| Key | Value |
|---|---|
| `type`, `search` | `"em.cavity3d"`, `"near_target"` (both required) |
| `target_frequency` | required, > 0 (menu `Hz kHz MHz GHz THz`; `"250 mHz"` is millihertz and refused, a bare number is `E-UNIT-MISSING`) |
| `mode_count` | required, a JSON integer ≥ 1 (`2.0` and booleans are refused) |
| `boundary` | required: `"pec"`, or `{"electrical_conductivity": ...}` ([conducting walls](#materials-and-conducting-walls)) |
| `mesh.subdivision_count` | required, `[nx, ny, nz]`, positive integers |

The structured mesh has `6 * nx * ny * nz` tetrahedra. `mesh.element_size`,
`minimum_angle`, grading, wavelengths, 2D formulations, sweeps and unrecognized cavity
settings are refused, so an unsupported request cannot silently change the problem.
A cavity has no tagged length, so its scale check is `W-CAVITY-SCALE`: a warning when
the largest domain side times `target_frequency / c` lies outside 0.1 to 100 (the
example's 1 m cube near 250 MHz gives 0.834; the same numbers declared in `mm` give
8.3e-4). The value is printed in the `extent` line of `validate` and of the log.

Defaults only supply an empty `materials`, the single study, and `results` with
`save_fields=true`, `plots=false`; each is recorded in `defaults_applied`. The cavity
input does not inherit any 2D wavelength, mesh-size or formulation defaults. Plotting
and the Studio 3D renderer are unavailable; explicit `plots=true` is refused.
Studio does not list this example and rejects cavity mesh/run requests.
`build_mesh` and `solve_point` remain 2D stages; the cavity entry point is `run`.

## Search and failure semantics

The requested modes are positive Maxwell modes found near the specified target.
The engine contract ranks candidates by distance in squared frequency
(or equivalently vacuum wavenumber squared), then returns the selected modes
in ascending frequency. This is a bounded candidate search, not a guarantee of
the lowest modes or of a complete spectral interval. In particular, a target
far above the fundamental does not request all modes below it.

Zero/gradient modes are excluded. Degenerate eigenvectors are retained as
separate modes, without frequency deduplication; `mode_count` counts vectors,
not distinct frequency values. A count can cut a degenerate cluster. Individual
vectors within a degenerate subspace and their signs are not stable labels.
Mesh refinement can split a continuum degeneracy. Check cluster multiplicities
and convergence, rather than assuming an exact frequency match identifies a
unique mode.

Invalid documents fail validation with a code and a path. Solver nonconvergence,
insufficient positive candidates, or a failed numerical residual check must fail
the run rather than write a partially successful result. CLI document errors return
status 2; solver errors return status 1. A failed solve creates no output directory.

## Result files and array units

A successful `run(doc)` returns `CavityRunResult`, distinct from the 2D
`RunResult`. `result.resonant_frequency` is the frequency vector in Hz,
`result.mass_normalized_electric_field` and
`result.mass_normalized_electric_field_line_integral` the saved fields,
`result.cavity` the galerkin result (in the solver's own convention), and
`result.save(directory)` writes:

- `model.json`: the authored document (its bytes, when it was read from a file).
- `summary.json`: the results as `{"value", "unit"}` objects and tagged arrays
  (`{"unit", "values"}`), mesh counts, the search target and mode counts, and the
  common blocks `diagnostics`, `defaults_applied`, `resolved_inputs`, `extent` and
  `timing.wall_time.mesh_and_solve` (seconds).
- `log.txt`: the extent line, the document summary, the frequencies and every diagnostic.
- `fields.npz`, only if `save_fields=true`: the arrays below and `metadata_json` (the
  summary's metadata as JSON text), readable with `numpy.load(path, allow_pickle=False)`.

There is no `results.png`. The CLI prints only the file names enabled by the
results settings. **All cavity result coordinates and dimensional arrays are SI**, and
`field_units`, `field_locations`, `field_shapes` and `field_components` name each array's
unit, location, shape and components. No key carries a unit suffix and no `*_unit` key
remains.

| NPZ key | Shape | Meaning / unit |
|---|---|---|
| `node_coordinates` | `(N, 3)` | Coordinates in m, including the document origin |
| `tetrahedra` | `(T, 4)` | Zero-based node indices |
| `edges` | `(E, 2)` | Global edges from lower to higher node index |
| `tet_edges` | `(T, 6)` | Local-to-global edge indices |
| `edge_signs` | `(T, 6)` | Local versus global edge orientation signs |
| `pec_edge_ids` | `(P,)` | Indices of constrained edges in `edges` |
| `resonant_frequency` | `(K,)` | Resonant frequencies, Hz |
| `wavenumber_squared` | `(K,)` | Vacuum wavenumber squared, 1/m^2 |
| `relative_residual` | `(K,)` | Dimensionless algebraic residuals |
| `mass_normalized_electric_field_line_integral` | `(E, K)` | Edge integrals, 1/m^(1/2), under SI mass normalization |
| `mass_normalized_electric_field` | `(K, T, 3)` | Electric field at tetrahedron centroids, 1/m^(3/2) |

Text scalars accompany these arrays: field layout `cavity3d-edge-v2`, normalization
`electric_mass_orthonormal_si`, `search`, `edge_orientation="low_node_index_to_high_node_index"`,
`electric_field_location="tetrahedron_centroid"`,
`cluster_completeness="not_certified"` and
`mode_count_policy="exact_count_may_split_cluster"`. The target (`target_frequency`, Hz)
and the counts (`mode_count`, `returned_mode_count`) are in the summary and in
`metadata_json`. The six local edges follow galerkin's tetrahedral order `(0,1)`, `(0,2)`,
`(0,3)`, `(1,2)`, `(1,3)`, `(2,3)`; signs map these local directions to the
stored global directions. Cavity output has no effective index or triangle/nodal-scalar arrays.
Results saved before the units and naming batch (`cavity3d-edge-v1`,
`cavity3d-edge-complex-v1`) are refused by name by `simcase.export`; re-run the document.

The normalization is `q.T @ M_SI @ q = I` for the vacuum electric mass
matrix. The fields therefore have arbitrary normalized amplitude, **not V/m**
(`amplitude` in the summary says so).
Raw edge integrals and centroid fields are different arrays with different
units; neither may be interpreted as nodal values. Residuals apply to free
edges of the PEC-reduced generalized eigenproblem: `||S q - lambda M q||_2 /
(||S q||_2 + |lambda| ||M q||_2)`, with failure limit `1e-8`. Selected-mode
mass orthogonality has maximum absolute error at most `1e-7`. Tiny numerical
kernel eigenvalues are screened at `1e-8` times the analytic fundamental
squared wavenumber in normalized box coordinates, independent of the target.

Use a fresh output directory for each cavity run. Before writing any files,
`save()` rejects a directory containing `summary.json`, `model.json`, `log.txt`,
`fields.npz`, or `results.png` (including directories or dangling symlinks at
those names). It raises `FileExistsError`; the CLI reports the error and exits
with status 1. This also applies to the default `<model>_results` path: use
`-o another_directory` for a repeated run. Existing results and unrelated user
files are preserved. A directory containing only unrelated files is allowed.
Do not write concurrent runs to the same directory.

With `save_fields=false`, the NPZ file is omitted entirely. `summary.json` still
retains frequencies, wavenumbers, residuals, normalization, SI units, the target,
both counts and both cluster/count policy fields.

The shape numbers mean the same box in any `length_unit`: the metre cube written
with maxima `1000` in `"mm"` has the same picometre bounds, so the solver receives the
same doubles and the saved results are bitwise the same. Changing the physical box
size without changing the target changes the search problem as well as the spectrum;
scale the target inversely when comparing geometrically similar mode sets.

## Materials and conducting walls

The same `em.cavity3d` study accepts constant, isotropic, possibly lossy materials in
axis-aligned boxes and finite-conductivity walls. Such a document runs
`galerkin.solve_material_cavity_box` and writes the complex layout below. A document
with a `physmat:vacuum` background, no shapes and `"boundary": "pec"` keeps
the original solver and the vacuum layout above. The example is
`examples/simcase/cavity_lossy_slab.json` (`python -m simcase example cavity_lossy_slab`):

```json
{
  "geometry": {
    "length_unit": "m",
    "domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 0.8, "zmin": 0, "zmax": 0.6},
    "background": {"material": "physmat:vacuum"},
    "shapes": [{"type": "box", "name": "slab", "material": "lossy_dielectric",
                "xmin": 0, "xmax": 1, "ymin": 0, "ymax": 0.8, "zmin": 0, "zmax": 0.3}]
  },
  "materials": {"lossy_dielectric": {"relative_permittivity": {"re": 4.0, "im": 0.04}}},
  "physics": {"em1": {"type": "em.cavity3d",
                      "boundary": {"electrical_conductivity": "58 MS/m"},
                      "search": "near_target", "target_frequency": "150 MHz",
                      "mode_count": 3}},
  "mesh": {"subdivision_count": [8, 8, 8]}
}
```

**Time convention** `exp(-i omega t)`, as every complex value of a format 0.3
document and result. A complex constant is a number or `{"re": .., "im": ..}` with
`re > 0` and `im >= 0`: a positive imaginary part is loss, and a dielectric with loss
tangent `t` is `{"re": eps', "im": eps' * t}`. A negative imaginary part is gain and is
refused (`E-GAIN`, whose message says how to convert a value written for
exp(+j omega t): negate the imaginary part). A format 0.2 `[re, im]` pair is
`{"re": re, "im": -im}` and is itself refused (`E-VALUE-FORM`). `allow_gain` is refused
by name: the cavity solvers are passive.

- `materials.<name>`: `relative_permittivity` (required) and `relative_permeability`
  (default 1, echoed in `defaults_applied`). As in every format 0.3 document, another
  registry property of the record (such as `refractive_index`) is checked and reported as
  not read (`I-UNUSED-PROPERTY`); `loss_tangent` is refused, and the 0.2 keys `n`, `k` and
  `sellmeier` are unknown keys. A local material may be called `vacuum`; it is an
  ordinary record (the library vacuum is `physmat:vacuum`), so another name is clearer.
- `geometry.background.material`: `"physmat:vacuum"` or a local material filling the box.
  Any other library name is refused (`E-CONTRACT`: the cavity takes constant
  `relative_permittivity` only).
- `geometry.shapes`: boxes `{"type": "box", "name", "material", "xmin", ..., "zmax"}`
  in `length_unit` and the document frame, each with a local material (`physmat:vacuum`
  is the background only). Names are unique. Each box lies inside the domain, and every
  face lies on a mesh grid plane: a multiple of `extent / subdivisions` from the domain
  minimum, relative tolerance `1e-9` of one cell, evaluated on the picometre values.
  Otherwise validation fails and names the spacing. Later boxes override earlier ones;
  each tetrahedron takes the material at its centroid.
- `physics.<name>.boundary`: `"pec"`, or `{"electrical_conductivity": "58 MS/m"}` for all
  six walls, or `{"electrical_conductivity": {"zmax": "58 MS/m", ...}}` with keys `xmin, xmax,
  ymin, ymax, zmin, zmax`, where unnamed walls stay PEC (menu `S/m kS/m MS/m S/cm`; a value
  must be > 0). Walls use the Leontovich surface impedance; each mode is converged by
  fixed-point iteration.

The numerical method, gates and validation are in the engine's
[material cavity contract](../galerkin/material_cavity.md). The engine works in
exp(+j omega t); simcase conjugates each complex value once at its boundary (the
material values going in, the results coming out), so the solver receives the same
doubles as before the units batch and every saved complex array is the conjugate of
the engine's.

### Complex results

`result.resonant_frequency` is complex for these studies; a decaying mode has
`Im f < 0`. `summary.json` carries a top-level `time_convention: "exp(-i omega t)"`, and
every complex entry is `{"re": [...], "im": [...], "unit", "time_convention"}`:

- `resonant_frequency` (Hz) and `wavenumber_squared` (1/m^2), complex;
- `quality_factor`, `Q = Re f / (-2 Im f)` (`> 0` when lossy), `null` for a lossless mode;
- `relative_residual` and `iteration_count` (fixed-point iterations per mode);
- `lossless`, the document `boundary`, `background` and `materials` (complex values as
  complex objects);
- `electrical_conductivity` by document wall name (`{"value", "unit": "S/m"}`, `null` for PEC).

`fields.npz` uses `field_layout="cavity3d-edge-complex-v2"`. It keeps the vacuum
layout's mesh, topology and orientation keys and text scalars, and adds or changes:

| NPZ key | Shape | Meaning / unit |
|---|---|---|
| `resonant_frequency` | `(K,)` complex | Complex frequencies, Hz |
| `wavenumber_squared` | `(K,)` complex | `k0^2`, 1/m^2 |
| `quality_factor` | `(K,)` | Dimensionless; `inf` when lossless |
| `mass_normalized_electric_field_line_integral` | `(E, K)` complex | 1/m^(1/2) |
| `mass_normalized_electric_field` | `(K, T, 3)` complex | 1/m^(3/2) at centroids |
| `relative_permittivity`, `relative_permeability` | `(T,)` complex | Material per tetrahedron |
| `wall_names`, `electrical_conductivity` | `(6,)` | `xmin..zmax`; S/m, `nan` for PEC |
| `iteration_count` | `(K,)` | Count |

Here `pec_edge_ids` lists only the edges of PEC walls; edges of conducting walls
are unknowns. The normalization is `vacuum_mass_hermitian_unit_si`: `q^H M0 q = 1`
with the vacuum edge mass `M0`, and the largest-magnitude coefficient of each mode
is real and positive. The amplitude is arbitrary and is **not V/m**. Arrays load with
`numpy.load(path, allow_pickle=False)`. `simcase.export.export_fields` writes this
layout to VTU with each complex mode as the cell data
`mass_normalized_electric_field_mode_<k>_real` and `..._imag` (same normalization and
`exp(-i omega t)`, so `real*cos(omega*t) + imag*sin(omega*t)` is the instantaneous field) and
the material arrays as `_real`/`_imag` pairs; the VTU FieldData block names each
array's unit and the time convention; see
[Viewing in ParaView](overview.md#viewing-in-paraview).

Tests in `tests/simcase/test_cavity3d_materials.py` check:

- validation of every field, each refusal with its code and path;
- that a document run equals the direct engine call, and the public values are its conjugate;
- that millimetres with a translated origin give the same SI result;
- the mapping of a single wall onto the engine wall and onto PEC edges;
- that a filled background equals the vacuum spectrum divided by the relative permittivity;
- that complex NPZ and JSON output load without pickle;
- `null` Q for lossless studies;
- that the vacuum PEC document keeps the original solver;
- that a local material named `vacuum` is an ordinary record;
- CLI runs, a missing engine API and Studio rejection.

`tests/simcase/test_units_cavity.py` checks the units and naming rules for this kind: the
same value in any unit spelling or `length_unit` gives the same solver inputs and saved
arrays, `W-CAVITY-SCALE`, the refusals with their codes and paths, diagnostics on every
surface, result names and units, the complex convention and the export.

Studio does not list or run these studies. Plotting stays unavailable.

## Integration validation and numerical limitation

With the cavity-enabled galerkin implementation, run from the repository root:

```bash
python -m pytest -q tests/simcase/test_cavity3d_integration.py
```

The seven integration cases passed for simcase revision `ba1c8a7` combined with
galerkin revision `a660233` (and previously for `cd4071a` with `3b850a8`), with
the format 0.2 documents of that time. They exercise a translated cube, reference-frequency
smoke checks for its first two complete reference clusters, metre/mm/um/nm
representations, real CLI execution with and without fields, and reconstruction
from NPZ loaded with `allow_pickle=False`. Reassembled topology, centroid fields,
PEC coefficients, free-edge residuals and mass orthogonality are checked. The
coarse reference-frequency check is not a mesh-convergence acceptance gate. Since the
units batch the same cases read format 0.3 documents, and the metre/mm/um/nm
representations are compared bitwise.

At the earlier galerkin revision `3b850a8`, the fixed rectangular-box 111-cluster
mean convergence gate failed: the last observed order was about 1.2284, below the
required 1.8. Revision `a660233` changes the cavity mesh to balance reflection
directions; the product integration cases also pass with this mesh. Document
execution and file reconstruction do not independently certify mesh convergence
or overall feature acceptance. For numerical validation evidence, see the
[engine's validation notes](https://github.com/fieldalgo/openphysics/blob/2efbc413df5d3d36bcc4c9879b34ed88213b9217/packages/galerkin/docs/cavity_solver.md).
