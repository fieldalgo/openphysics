# Rectangular cavity document and results

The product contract supports one `em.cavity3d` study: a vacuum rectangular
box with perfect electric conductor (PEC) conditions on all six faces. The
public API contract is defined below. Actual engine integration checks cover
CLI execution, unit conversion and saved-field reconstruction; these checks
are separate from the engine's numerical convergence acceptance.

## Input

The example is `examples/cavity_box.json`, also available from
`python -m simcase example cavity_box`. The intended headless workflow is:

```bash
python -m simcase example cavity_box > cavity.json
python -m simcase validate cavity.json
# Requires the matching galerkin cavity API:
python -m simcase run cavity.json -o cavity_results
```

The input retains `"openphysics": "0.2"`. Declare `units.length` explicitly,
including when it is `"m"`. The six `geometry.domain` coordinates are `xmin`,
`xmax`, `ymin`, `ymax`, `zmin`, `zmax`, in that declared length unit. Each maximum
must exceed its minimum; a nonzero origin is allowed. `geometry.background` is
`{"material": "vacuum"}`, `geometry.shapes` is empty, and `materials` is empty.
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
      "target_frequency_hz": 250000000.0,
      "num_modes": 5
    }
  },
  "mesh": {"subdivisions": [6, 6, 6]},
  "study": {"type": "single"},
  "results": {"save_fields": true, "plots": false}
}
```

All five physics fields are explicit. The target frequency is always in Hz,
independent of `units.time`; the `_hz` suffix is a fixed SI-unit field.
Subdivision counts and mode count must be positive integers (booleans are
rejected). The structured mesh has `6 * nx * ny * nz` tetrahedra. `mesh.size`,
grading, wavelength, 2D formulation, sweeps and unrecognized cavity settings
are rejected, so an unsupported request cannot silently change the problem.

Defaults only supply empty shapes/materials, vacuum background, the single
study, and `results` with `save_fields=true`, `plots=false`. The cavity input
does not inherit any 2D wavelength, mesh-size or formulation defaults. Plotting
and the Studio 3D renderer are unavailable; explicit `plots=true` is rejected.
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
separate modes, without frequency deduplication; `num_modes` counts vectors,
not distinct frequency values. A count can cut a degenerate cluster. Individual
vectors within a degenerate subspace and their signs are not stable labels.
Mesh refinement can split a continuum degeneracy. Check cluster multiplicities
and convergence, rather than assuming an exact frequency match identifies a
unique mode.

Invalid documents fail validation. Solver nonconvergence, insufficient positive
candidates, or a failed numerical residual check must fail the run rather than
write a partially successful result. CLI document errors return status 2;
solver errors return status 1. A failed solve creates no output directory.

## Result files and array units

A successful `run(doc)` returns `CavityRunResult`, distinct from the 2D
`RunResult`. `result.frequencies_hz` exposes the frequency vector, `result.cavity`
holds the reusable galerkin result, and `result.save(directory)` writes:

- `model.json`: the validated document, still in its declared input units.
- `summary.json`: frequency/eigenvalue/residual vectors, explicit array units,
  mesh counts, search target, requested/returned mode counts and timing seconds.
- `log.txt`: document summary and frequencies.
- `fields.npz`, only if `save_fields=true`: the arrays below, readable with
  `numpy.load(path, allow_pickle=False)`.

There is no `results.png`. The CLI prints only the file names enabled by the
results settings. The document declaration is preserved in `summary.units`,
but **all cavity result coordinates and dimensional arrays are SI**. Output
`mesh_length_unit="m"` must be used when interpreting coordinates.

| NPZ key | Shape | Meaning / unit |
|---|---|---|
| `nodes` | `(N, 3)` | Coordinates in metres, including the document origin |
| `tetrahedra` | `(T, 4)` | Zero-based node indices |
| `edges` | `(E, 2)` | Global edges from lower to higher node index |
| `tet_edges` | `(T, 6)` | Local-to-global edge indices |
| `edge_signs` | `(T, 6)` | Local versus global edge orientation signs |
| `pec_edge_ids` | `(P,)` | Indices of constrained edges in `edges` |
| `frequencies_hz` | `(K,)` | Resonant frequencies in Hz |
| `eigenvalues_m2` | `(K,)` | Vacuum wavenumber squared, m^-2 |
| `relative_residuals` | `(K,)` | Dimensionless algebraic residuals |
| `edge_coefficients` | `(E, K)` | Edge integrals in m^-1/2 under SI mass normalization |
| `electric_field` | `(K, T, 3)` | Electric field at tetrahedron centroids, m^-3/2 |

Scalar string/number metadata accompanies these arrays: field layout
`cavity3d-edge-v1`, `mesh_length_unit`, `frequency_unit`,
`eigenvalue_unit`, `edge_coefficient_unit`, `electric_field_unit`, normalization
`electric_mass_orthonormal_si`, `search`, `target_frequency_hz`, and
`requested_modes`, `returned_modes`, `edge_orientation="low_node_index_to_high_node_index"`,
`electric_field_location="tetrahedron_centroid"`, and
`cluster_completeness="not_certified"` and
`mode_count_policy="exact_count_may_split_cluster"`.
The six local edges follow galerkin's tetrahedral order `(0,1)`, `(0,2)`,
`(0,3)`, `(1,2)`, `(1,3)`, `(2,3)`; signs map these local directions to the
stored global directions. Cavity output has no `neff` or triangle/nodal-scalar arrays.

The normalization is `q.T @ M_SI @ q = I` for the vacuum electric mass
matrix. The fields therefore have arbitrary normalized amplitude, **not V/m**.
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
retains frequencies, eigenvalues, residuals, normalization, SI units, target,
requested/returned counts and both cluster/count policy fields.

Equivalent length-unit declarations require rescaling every domain coordinate.
For example, the metre cube can be expressed with maxima `1000` in `"mm"` and
the same subdivisions and target in Hz. The physical SI output should then be
unchanged. Changing the physical box size without changing the target changes
the search problem as well as the spectrum; scale the target inversely when
comparing geometrically similar mode sets.

## Materials and conducting walls

The same `em.cavity3d` study accepts constant, isotropic, possibly lossy materials in
axis-aligned boxes and finite-conductivity walls. Such a document runs
`galerkin.solve_material_cavity_box` and writes the complex layout below. A document
with a vacuum background, no shapes, no materials and `"boundary": "pec"` keeps
the original solver and the vacuum layout above. The example is
`examples/cavity_lossy_slab.json` (`python -m simcase example cavity_lossy_slab`):

```json
{
  "geometry": {
    "domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 0.8, "zmin": 0, "zmax": 0.6},
    "background": {"material": "vacuum"},
    "shapes": [{"type": "box", "name": "slab", "material": "lossy_dielectric",
                "xmin": 0, "xmax": 1, "ymin": 0, "ymax": 0.8, "zmin": 0, "zmax": 0.3}]
  },
  "materials": {"lossy_dielectric": {"relative_permittivity": [4.0, -0.04]}},
  "physics": {"em1": {"type": "em.cavity3d",
                      "boundary": {"conductivity_s_per_m": 58000000.0},
                      "search": "near_target", "target_frequency_hz": 150000000.0,
                      "num_modes": 3}},
  "mesh": {"subdivisions": [8, 8, 8]}
}
```

**Time convention** `exp(+j*omega*t)`. A complex constant is a real number or a
`[real, imag]` pair with `real > 0` and `imag <= 0` (passive); a dielectric with loss
tangent `t` is `[eps', -eps' * t]`.

- `materials.<name>`: `relative_permittivity` (required) and `relative_permeability`
  (default 1). The name `vacuum` is reserved; other keys, including the 2D `n`, `k`
  and `sellmeier`, are rejected.
- `geometry.background.material`: `"vacuum"` or a defined material filling the box.
- `geometry.shapes`: boxes `{"type": "box", "name", "material", "xmin", ..., "zmax"}`
  in the declared length unit and document frame. Names are unique. Each box lies
  inside the domain, and every face lies on a mesh grid plane: a multiple of
  `extent / subdivisions` from the domain minimum, relative tolerance `1e-9` of one
  cell. Otherwise validation fails and names the spacing. Later boxes override
  earlier ones; each tetrahedron takes the material at its centroid.
- `physics.<name>.boundary`: `"pec"`, or `{"conductivity_s_per_m": sigma}` for all six
  walls, or `{"conductivity_s_per_m": {"zmax": sigma, ...}}` with keys `xmin, xmax,
  ymin, ymax, zmin, zmax`, where unnamed walls stay PEC. Conductivity is always S/m,
  independent of `units`. Walls use the Leontovich surface impedance
  `Zs = sqrt(j omega mu0 / sigma)`; each mode is converged by fixed-point iteration.

The numerical method, gates and validation are in the engine's
[material cavity contract](https://github.com/fieldalgo/openphysics/blob/main/packages/galerkin/docs/material_cavity.md).

### Complex results

`result.frequencies_hz` is complex for these studies. `summary.json` stores
JSON-safe real arrays:

- `resonant_frequencies_hz` (Re f) and `frequencies_hz_imag` (Im f, positive when lossy);
- `quality_factors`, `Q = Re f / (2 Im f)`, or `null` for a lossless mode;
- `eigenvalues_m2_real` and `eigenvalues_m2_imag`;
- `relative_residuals`;
- `fixed_point_iterations`;
- `lossless`, `time_convention`, the document `boundary`, `background` and `materials`;
- `wall_conductivity_s_per_m` by document wall name (`null` for PEC).

`fields.npz` uses `field_layout="cavity3d-edge-complex-v1"`. It keeps the vacuum
layout's mesh, topology and orientation keys and metadata strings, and adds or changes:

| NPZ key | Shape | Meaning / unit |
|---|---|---|
| `frequencies_hz` | `(K,)` complex | Complex frequencies, Hz |
| `eigenvalues_m2` | `(K,)` complex | `k0^2`, m^-2 |
| `quality_factors` | `(K,)` | Dimensionless; `inf` when lossless |
| `edge_coefficients` | `(E, K)` complex | m^-1/2 |
| `electric_field` | `(K, T, 3)` complex | m^-3/2 at centroids |
| `tet_relative_permittivity`, `tet_relative_permeability` | `(T,)` complex | Material per tetrahedron |
| `wall_names`, `wall_conductivity_s_per_m` | `(6,)` | `xmin..zmax`; S/m, `nan` for PEC |
| `fixed_point_iterations` | `(K,)` | Count |

Here `pec_edge_ids` lists only the edges of PEC walls; edges of conducting walls
are unknowns. The normalization is `vacuum_mass_hermitian_unit_si`: `q^H M0 q = 1`
with the vacuum edge mass `M0`, and the largest-magnitude coefficient of each mode
is real and positive. The amplitude is arbitrary and is **not V/m**. Arrays load with
`numpy.load(path, allow_pickle=False)`.

Tests in `tests/simcase/test_cavity3d_materials.py` check:

- validation of every new field;
- that a document run equals the direct engine call;
- that millimetres with a translated origin give the same SI result;
- the mapping of a single wall onto the engine wall and onto PEC edges;
- that a filled background equals the vacuum spectrum divided by `eps_r`;
- that complex NPZ and JSON output load without pickle;
- `null` Q for lossless studies;
- that the vacuum PEC document keeps the original solver;
- CLI runs, a missing engine API and Studio rejection.

Studio does not list or run these studies. Plotting stays unavailable.

## Integration validation and numerical limitation

With the cavity-enabled galerkin implementation, run from the repository root:

```bash
python -m pytest -q tests/simcase/test_cavity3d_integration.py
```

The seven integration cases passed for simcase revision `ba1c8a7` combined with
galerkin revision `a660233` (and previously for `cd4071a` with `3b850a8`).
They exercise a translated cube, reference-frequency
smoke checks for its first two complete reference clusters, metre/mm/um/nm
representations, real CLI execution with and without fields, and reconstruction
from NPZ loaded with `allow_pickle=False`. Reassembled topology, centroid fields,
PEC coefficients, free-edge residuals and mass orthogonality are checked. The
coarse reference-frequency check is not a mesh-convergence acceptance gate.

At the earlier galerkin revision `3b850a8`, the fixed rectangular-box 111-cluster
mean convergence gate failed: the last observed order was about 1.2284, below the
required 1.8. Revision `a660233` changes the cavity mesh to balance reflection
directions; the product integration cases also pass with this mesh. Document
execution and file reconstruction do not independently certify mesh convergence
or overall feature acceptance. For numerical validation evidence, see the
[engine's validation notes](https://github.com/fieldalgo/openphysics/blob/2efbc413df5d3d36bcc4c9879b34ed88213b9217/packages/galerkin/docs/cavity_solver.md).
