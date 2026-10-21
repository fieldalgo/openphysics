# Model a two-material wall, run it and inspect the heat flow

**English** | [한국어](../../locales/ko/pages/packages/simcase/layered_wall_tutorial.md)

[Documentation home](../../README.md)

This walkthrough connects geometry, material regions, meshing, convection and saved
results. The coefficients are illustrative, not certified properties of a named product.
Start with the [first heat calculation](../galerkin/thermal_tutorial.md) if the engine is new to you.

## 1. Install the document runner

Use Python 3.12 or newer in an activated virtual environment, from the repository root.
Install the local dependencies together; the extra supplies meshio for optional export.

```sh
python -m pip install -e packages/galerkin -e packages/meshine -e packages/physmat -e 'packages/simcase[export]'
python -m simcase validate examples/simcase/layered_wall.json
python examples/simcase/layered_wall.py out/wall-base --export
```

Use a new or empty output directory. The script solves once, saves the result, and
writes `view.vtu`. Without `--export`, meshio is not needed. Generated output under
`out/` is local; do not treat it as evidence included in a fresh clone.
The file is a repository tutorial input, not a name registered with `simcase example`.

## 2. Read the model in physical order

Open [layered_wall.json](../../../examples/simcase/layered_wall.json).

| Part | Meaning |
|---|---|
| Domain | 40 mm wide, 10 mm high |
| `background` region | Material `low_k`, k=1 W/(m K) |
| `left_layer` shape | The first 10 mm of the width, material `high_k`, k=10 W/(m K) |
| Left boundary | Temperature fixed at 350 K |
| Right boundary | Convection h=50 W/(m² K), ambient 300 K |
| Top and bottom | Unspecified natural edges, hence insulated |
| Mesh | Target size 2 mm, requested minimum angle 28 degrees |

A **region name** identifies geometry; a **material name** identifies its property
record. Several regions may use one material. If you add a source map, its keys are
region names such as `left_layer`, not material names such as `high_k`.
Geometry and mesh sizes follow `units.length`; properties ending in `_w_mk`,
`_w_m3`, `_w_m2k` and `_k` retain SI units. The runner sends metre coordinates to
the thermal engine. Do not manually convert only half the document.

Later shapes replace overlapping parts of earlier ones. The background occupies
the remaining domain, and mesh edges follow region interfaces. A covered shape
can disappear from the mesh; inspect the log and summary, not only the drawing.
Both layers assume perfect thermal contact, with no interface resistance.

## 3. Check a prediction before trusting the picture

For no internal source and insulated top/bottom, this is a series thermal resistance:

```text
R_per_area = 0.01/10 + 0.03/1 + 1/50 = 0.051 m² K/W
q_x = (350-300)/R_per_area = 980.392157 W/m²
T_interface = 350 - q_x*(0.01/10) = 349.019608 K
T_right = 300 + q_x/50 = 319.607843 K
heat_per_depth = q_x*0.01 = 9.803922 W/m
```

The script prints a temperature range about 319.607843–350 K and equal thermostat
input and convective output about 9.803922 W/m. A 1 mm extrusion depth carries
0.009803922 W. Triangle counts may vary; they are not acceptance values.

The exact temperature is piecewise linear, represented by the interface-aligned
P1 mesh. Agreement here checks mapping, units, signs and Robin assembly; it does
not prove convergence for general shapes, sources or contact models.

## 4. Change one design choice

Copy the JSON to a local file and use `python -m simcase validate` and
`python -m simcase run <your-file.json> -o <new-output>` for that copy. The helper
script always loads its neighboring repository JSON; it does not read your copy.

- Change `low_k` from 1 to 2 W/(m K). Recompute the series resistance first;
  the heat flow increases. Update every other input only when physically intended.
- Move the interface by changing `left_layer.w` from 10 to 15 mm.
  The two thicknesses become 0.015 and 0.025 m; the outer width stays 40 mm.
- Add `heat_source_w_m3: {"left_layer": 200000}` in the physics object.
  The no-source formula above no longer applies. Compare total source input,
  thermostat reaction and convective output instead; then perform refinement.

For a mesh-only repeat of the original input, run:

```sh
python examples/simcase/layered_wall.py out/wall-fine --mesh-size-mm 1 --export
```

Keep the run directories separate. Read [saved results and ParaView](../../results/saved-results.md)
next, then [convergence checks](../../validation/convergence.md).
This tutorial runs the region/convection model from Python and the CLI; Studio also
validates, runs and shows it as a [region document](thermal_studio.md#region-documents)
within its region limits.
The exact supported shapes, mappings and limitations remain in the
[region-document contract](thermal_regions2d.md).
