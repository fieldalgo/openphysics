# Read saved fields and export them to ParaView

**English** | [한국어](../locales/ko/pages/results/saved-results.md)

[Documentation home](../README.md)

Use the [two-layer wall](../packages/simcase/layered_wall_tutorial.md) to produce
`out/wall-base/`. This guide concerns saved simcase results, not the experimental
workspace's input/session format. Exporting a picture is not saving a reproducible calculation.

## Keep the original result bundle

| File | Keep it for |
|---|---|
| `model.json` | The model document saved with this solve |
| `summary.json` | Result/layout versions, units, locations, shapes and region mapping |
| `fields.npz` | Numeric fields and layout metadata; requires `save_fields: true` |
| `log.txt` | Run diagnostics |
| `view.vtu` | Optional viewing copy; does not replace the files above |

Use a distinct new or empty directory per run. For this wall, existing result
files are protected rather than overwritten. Do not edit a result's document
or mesh after solving and then save it as if the edited model had been solved;
rerun from the changed input. The bundle does not by itself establish a complete
Git/dependency provenance record: record the code revision, environment and
external data versions alongside it when reproducing a numerical claim.

## Read arrays with their association and units

Run this block from the repository root after the wall example:

```python
import json
from pathlib import Path
import numpy as np

folder = Path("out/wall-base")
summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
print(summary["field_layout"])
print(summary["regions"])
with np.load(folder / "fields.npz", allow_pickle=False) as fields:
    print(summary["field_units"]["temperature"])           # K
    print("Temperature (K):", fields["temperature"].min(), fields["temperature"].max())
    print("Thermostat input (W/m):", fields["reaction_heat_rate_per_depth"].sum())
    print("Convection out (W/m):", fields["outward_convective_heat_rate_per_depth"].sum())
```

Array names carry no unit: `summary["field_units"]` gives each array's unit
(`temperature` in K, `heat_flux` in W/m^2, the `_per_depth` rates in W/m).
`temperature` is nodal; `heat_flux` is a cell vector. `triangle_regions`
is a cell ID into `summary["region_names"]` (no unit), not a material ID or a temperature.
The region entry then names its material. Two regions may share a material.
Read `field_units`, `field_locations`, `field_shapes` and `field_layout` before
writing a general consumer; not every physics produces the same arrays.

## Open the viewing copy

The example's `--export` already creates `view.vtu`. To export an existing saved
result without solving again, choose a different, nonexistent filename:

```python
from simcase.export import export_fields
export_fields("out/wall-base/fields.npz", "out/wall-base/second-view.vtu")
```

In ParaView, open the VTU and Apply. Color by point data `temperature`, then by
cell data `triangle_regions` to inspect interfaces. Show mesh edges if necessary.
For flux choose cell data `heat_flux`, its x component or magnitude. The VTU's
FieldData `units` and `conventions` record each array's unit and sign sentence.
Changing cell data to point data smooths a derived display; it does not improve
solver accuracy. Compare runs using the same color range. Region names, properties
and boundary tags are not all copied into VTU; keep the NPZ and summary.

## Time histories

For a saved supported transient heat layout, `export_time_series` writes a VTU
per stored time and a PVD collection. It does not interpolate or rerun the solver.
Open the PVD in ParaView and use its time controls. Move the collection and its
VTU files together. Time is in seconds, not the frame number. The initial frame
has temperature/flux but no completed-step reaction, residual or storage-rate arrays,
nor the boundary layout's per-step load arrays.
See the complete [transient export commands](../packages/simcase/overview.md#viewing-in-paraview).

## Check export support before choosing the viewer

| Saved layout family | VTU / PVD |
|---|---|
| Rectangular steady heat, Dirichlet/insulated | VTU |
| Rectangular steady heat with flux/convection (`thermal2d-p1-node-cell-boundary-v3`), including its load arrays | VTU |
| Steady material-region heat (`thermal2d-p1-node-cell-regions-v2`, axisymmetric `thermal-axisymmetric-p1-node-cell-regions-v2`), including its flux/convection fields | VTU |
| Rectangular or region transient heat | VTU for one time, PVD for all stored times |
| Rectangular transient heat with flux/convection (`thermal2d-transient-p1-node-cell-boundary-v2`), including its two per-step load arrays | VTU for one time, PVD for all stored times |
| Heat, electric, Joule and mechanics layouts saved before format 0.3 (`RETIRED_LAYOUTS`, such as `thermal2d-p1-node-cell-regions-v1`, `electric-joule2d-p1-v1` or `mechanics2d-p1-v1`) | Refused by name; re-create the document in format 0.3 and run it again |
| Vacuum PEC cavity | VTU |
| Electric conduction and Joule heating (`electric-joule2d-p1-v2`; regions `electric2d-p1-node-cell-regions-v2`, `electric-joule2d-p1-node-cell-regions-v2`) | VTU |
| Rectangular elasticity and thermoelasticity (`mechanics2d-p1-v2`, `thermoelastic2d-p1-v2`), strain and stress as named component scalars | VTU |
| Region elasticity and thermoelasticity (`mechanics2d-p1-regions-v2`, `thermoelastic2d-p1-regions-v2`) | Not exported yet (refused as an unsupported layout); read `fields.npz` |
| Cavity with materials and lossy walls (`cavity3d-edge-complex-v1`) | VTU, complex fields as `_real`/`_imag` pairs |
| Waveguide modes (`em.modes2d`, `em-modes2d-p1-node-centroid-v1`) | VTU for a single point, PVD for a sweep (`export_sweep`); nodes converted to metres, complex modes as `_real`/`_imag` pairs; subspace sweeps (`em-modes2d-subspace-raw-v1`) and results saved without `field_layout` refused |

The region path and rectangle boundary-v3 path have different layouts despite
similar physical conditions. Unsupported export does not mean the solver failed.
See [region export](../packages/simcase/thermal_regions2d.md#vtu-and-pvd-export)
and [result reliability](index.md) for exact scope and interpretation.
