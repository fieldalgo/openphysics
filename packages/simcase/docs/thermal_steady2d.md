# Headless steady heat in a rectangle

[한국어](locales/ko/pages/thermal_steady2d.md)

This page describes the legacy v1 path without the new natural-boundary keys.
The [boundary extension guide](thermal_steady_boundary2d.md) documents the
submitted constant outward-flux/convection candidate. New-key presence, even
an empty mapping, selects v2. Robin-only anchoring with empty Dirichlet,
additional raw fields and total outward heat are defined there.
Candidate implementation is distinct from incomplete P2 numerical/installed acceptance.

`thermal.steady2d` solves `-div(k grad T) = Q` in a single homogeneous
2D rectangle of unit out-of-plane thickness. It uses the existing P1 thermal
engine. This document describes the headless API and CLI; Studio rejects these
models and clears older optical results. There is no thermal Studio editor or
renderer in this version.

## Input

Use document format `"openphysics": "0.2"`. Declare `units.length` (for example
`m`, `mm`, or `um`) and `units.temperature: "K"`. Geometry bounds use that length
unit. The adapter converts geometry to metres before meshing and assembly.
Fixed suffixes have SI meaning regardless of the document length unit:

- `conductivity_w_mk`: finite positive constant, W/(m K).
- `heat_source_w_m3`: finite signed constant, W/m³; default zero.
- `dirichlet_temperature_k`: nonempty mapping from `left`, `right`, `bottom`,
  or `top` to finite nonnegative kelvin. Unspecified exterior sides are insulated.

Adjacent prescribed sides share corner nodes. Equal corner values are deduplicated;
conflicting values are rejected, independent of mapping order. Zero kelvin is a
valid prescribed value. The rectangle is connected and the nonempty Dirichlet set
removes its constant nullspace. The underlying engine also checks component
constraints; arbitrary disconnected meshes are outside this document format.

`mesh` contains only `subdivisions: [nx, ny]`, with nonboolean positive JSON
integers. `4` is accepted; `4.0`, `true`, zero and negative counts are rejected.
`geometry` contains only four finite, strictly ordered `domain` bounds.
`materials` is empty, there is exactly one physics, and `study` is
`{"type":"single"}`. `results` accepts boolean `save_fields` and `plots`;
`plots` must be false (the default). Optical material/dispersion/wavelength keys,
shapes, sweeps, extra keys, region-dependent k, transient, coupled
and 3D requests are rejected on this steady path. Natural boundary keys use the
separate boundary-extension contract, rather than the legacy v1 validator.

Generate the complete examples and run them:

```sh
simcase example thermal_slab > slab.json
simcase validate slab.json
simcase run slab.json -o slab_results
simcase example thermal_mixed > mixed.json
simcase run mixed.json -o mixed_results
```

The examples use L=0.03 m, H=0.02 m, k=12.5 W/(m K), TL=280 K and TR=315 K.
Top and bottom are insulated. For `thermal_slab`, Q=0; for `thermal_mixed`,
Q=100000 W/m³. Their independent solutions are

`T(x) = TL + (TR-TL)x/L + Q x(L-x)/(2k)` and
`qx(x) = -k(TR-TL)/L - Q(L-2x)/2`, `qy = 0`.

The mixed example's signed net outward heat is QLH=60 W/m of depth. Individual
boundary heats can have opposite signs. Changing bounds from mm to um while
representing the same physical rectangle must leave every SI result unchanged.

## API and raw result

```python
from simcase import Document, ThermalRunResult, run
result = run(Document.load("mixed.json"), verbose=False)
assert isinstance(result, ThermalRunResult)
result.save("fresh_results")
```

`result_format` is `thermal.steady2d-result-v1`; `field_layout` is
`thermal2d-p1-node-cell-v1`. These identify the thermal output independently of
input format 0.2 and optical/cavity result formats. No neff, wavelength or modal
normalization is attached to temperature.

| NPZ key | Shape | Location | Unit |
| --- | --- | --- | --- |
| `nodes_m` | (N,2) | nodes, SI coordinates | m |
| `triangles` | (M,3) | integer node connectivity, CCW | 1 |
| `temperature_k` | (N,) | nodes | K |
| `heat_flux_w_m2` | (M,2) | triangle centroids, q=-k grad T | W/m² |
| `load_w_per_m` | (N,) | nodal assembled source | W/m |
| `reaction_w_per_m` | (N,) | nodes, inward support reaction | W/m |
| `residual_w_per_m` | (N,) | full assembled K T - load residual | W/m |
| `dirichlet_node_ids` | (D,) | sorted unique prescribed node indices | 1 |
| `dirichlet_temperature_k` | (D,) | matching prescribed values | K |

The result properties are `mesh_nodes_m`, `mesh_triangles`, and the seven physical
or Dirichlet array names above. Reactions equal `K T - load` on prescribed nodes;
free reactions are zero. The full residual retains the fixed-node reactions and
roundoff-sized free entries. Net outward heat is the **negative** sum of reactions on
unique prescribed nodes. Nodal W/m quantities integrate per unit depth; flux is
W/m². Element flux is discontinuous across element boundaries and is not a nodal
field. Flux/residual use the engine's equivalent component-offset coordinates.

`summary.json` records the format/layout IDs, original document units, SI mesh
unit, all nine array units/locations/shapes, fixed-node count, temperatures,
source/outward/balance diagnostics and timings. Numeric values must be finite.
`fields.npz` also contains Unicode scalar identifiers and `metadata_json`, without
object arrays. Consumers must use `numpy.load(path, allow_pickle=False)` and
validate identifiers before interpreting arrays. `save_fields=false` omits the
entire NPZ while retaining summary, model and log; raw numeric/shape checks and
finite-JSON validation still apply. Stored geometry is SI, not document units.

## Output ownership and failures

The target must not exist, including an empty directory, existing file or dangling
symlink. The CLI checks this before solving; save claims a fresh target with an
exclusive mkdir. Competing fresh-save claims have one winner; a losing claim does
not clean up the winner. This does not authorize another writer inside the output.
The caller must prevent external writers from changing the output directory or
its entries for the **entire save, including all failure cleanup**. This is a
non-adversarial, caller-exclusive fresh-output contract.

The owner writes `.incomplete`, model/log and optional NPZ, then `summary.json`
last. Before removing the marker, finish checks recorded artifacts for presence
and observed identity. Observed missing artifacts prevent completion. Constructor
handle-acquisition failure attempts removal only of the observed same empty target
and retains the original exception.

Cleanup uses observed ownership checks and never recursively deletes a directory.
A foreign/replaced file or target observed before a check is preserved. **The
check and subsequent open/unlink are separate operations**: replacement between
check and use is not protected atomically. An external writer can cause writes
to a replaced target or deletion of a replacement during cleanup. Inode pins
prevent reuse from being mistaken for identity; they do not eliminate this race.
If cleanup cannot finish, incomplete output may remain. Consumers should require
both summary and absence of `.incomplete` under the same exclusivity assumption.
This is not atomic multi-file publication, adversarial race protection or crash
rollback. Independent source/installed counterexamples demonstrate the check/use
limitation; see the [independent report](https://github.com/fieldalgo/openphysics/blob/e9183fc8f5444422c7a5e167c878d2d5804a6611/packages/simcase/docs/thermal_simcase_independent_validation.md).
That limitation is separate from the two historical Windows fixture-operation
failures; it does not establish their cause.
Ownership uses POSIX file descriptors and a narrow Windows adapter. Windows
file identities are pinned by temporary hard links in exclusively created sibling
directories, not by file handles retained after writing. This keeps the original
file allocated even if its output name is replaced. The filesystem must support
same-volume hard links; otherwise saving fails with a chained `OSError`, without
silently weakening identity checks. These temporary siblings require a writable
output parent and caller-exclusive control until save/cleanup completes. Only
the observed owned link and its empty directory are removed; unexpected contents
are preserved. A crash can leave pin directories; this is not crash rollback.
Directory handles still use stdlib ctypes and `FILE_FLAG_BACKUP_SEMANTICS`; all native file
opens request read/write/delete sharing; actual operation availability must be
verified separately under the caller-exclusive contract. New files use
`CREATE_NEW`. Platform-specific execution evidence must be checked separately.
The Windows API contracts are documented by Microsoft:
[CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
and [directory handles](https://learn.microsoft.com/en-us/windows/win32/fileio/obtaining-a-handle-to-a-directory).
Microsoft also documents restrictions on replacing open destination files and
renaming directories containing open files in
[FILE_RENAME_INFORMATION](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_rename_information).
Delete sharing alone must not be assumed to remove those restrictions.

CLI exit codes are 0 for success, 2 for invalid input, and 1 for solver/save
failure (including finite-JSON rejection). Expected failures produce an error
without a traceback. Existing EM/cavity output behavior is retained.

## Acceptance evidence and limits

Dedicated tests independently compare the affine slab, mixed closed form and
reaction signs, not just engine-to-adapter equality. Fixed refinement counts
8/16/32/64 require the final two L2-temperature orders at least 1.8 and flux
orders at least 0.9; the mixed source/outward heat is 60 W/m. SI invariance is
1e-9; normalized array/reaction checks are 1e-10. Tests cover corner conflicts,
strict input types, finite/shape/connectivity/CCW raw checks, no-pickle consumers,
fields-disabled saves, existing targets, partial failures, replaced files and
directories, concurrent writers, CLI errors and stale Studio replies.
These gates do not replace full package/installed regression checks. No thermal
plot, performance baseline or unsupported boundary/material model is claimed.

Failure-injection checks record OS errno/winerror/message and fixture stages.
They require the intended post-NPZ injected error after replacement has completed;
an OS rename/replace refusal is a fixture-precondition failure, not successful
cleanup protection or proof that cleanup deleted a replacement.

The handle-free file-pin candidate `d89ce964b71ac3c47cd1bed47118653374967fbb`
passed the narrow Windows Server 2022 / CPython 3.12.10 installed API/CLI/save
gate: 36 passed and 62 deselected, plus 3 source target-protection cases passed
and 14 deselected. The unchanged five fault stages include both formerly refused
rename/replace operations; seven additional link-pin cases are included.
See [the exact run](https://github.com/fieldalgo/openphysics/actions/runs/38857948286).
This is not full Windows regression, macOS acceptance, or a promise for filesystems
without hard-link support. Earlier failures remain historical evidence.

