# Steady heat on a 3D component (`thermal.steady3d`)

**English** | [한국어](../../locales/ko/pages/packages/simcase/thermal_steady3d.md)

[Documentation home](../../README.md)

`thermal.steady3d` solves steady heat conduction, −∇·(k∇T) = Q, on one `3d` component of
a version 1 geometry block ([geometry document](geometry_document.md)), in format 0.3
documents. It is a thin kind: it takes the keys of
[`thermal.steady2d` on regions](thermal_regions2d.md) that apply in 3D, meshes the component
on one of the stage 5 routes and solves with `galerkin.solve_steady_heat_3d`. Studio does not
open it yet.

```json
{
  "openphysics": "0.3",
  "name": "three-layer slab",
  "geometry": {"version": 1, "components": {"pkg": {
    "dimension": "3d", "length_unit": "mm",
    "domain": {"xmin": 0, "xmax": 10, "ymin": 0, "ymax": 10, "zmin": 0, "zmax": 2.5},
    "background": {"material": null},
    "features": [{"name": "stack", "type": "layers", "z0": 0, "layers": [
      {"name": "a", "thickness": 1, "material": "lower"},
      {"name": "b", "thickness": 0.5, "material": "core"},
      {"name": "c", "thickness": 1, "material": "upper"}]}]}}},
  "materials": {"lower": {"thermal_conductivity": "1 W/(m K)"},
                "core": {"thermal_conductivity": "0.01 W/(m K)"},
                "upper": {"thermal_conductivity": "1 W/(m K)"}},
  "physics": {"heat": {"type": "thermal.steady3d",
                       "prescribed_temperature": {"z0": "300 K", "z1": "301 K"}}},
  "mesh": {"element_size": "0.4 mm"}
}
```

```python
from simcase import Document, run
result = run(Document.load("slab3d.json"))
result.temperature, result.reaction_heat_rate     # per node, K and W
result.save("out/")                               # summary.json, fields.npz, model.json, log.txt
```

## Mesh routes

The route follows the contract's [mesher route](geometry_document.md#stage-5-compile-conditions-amended-2026-11-27):

| Component | Route | Exterior tags |
|---|---|---|
| one `layers` feature of slab layers | `meshine.extrude`: the domain rectangle meshed by meshine at the element size, extruded through the layer levels in sub-layers at most that thick | `z0`, `z1`, and the footprint's sides `left`, `right`, `bottom`, `top` |
| anything else of the [boxes and slab layers](geometry_engine3d.md) slice 1 takes | `simcase.build_mesh3d` through meshloom (**experimental**) | `x0`–`z1` on the domain faces, `void` elsewhere, or `boundary_tags` |
| a cylinder or spheres in one of [meshloom's builder shapes](geometry_engine3d.md#cylinders-and-spheres-in-builder-shapes-slice-3) | "builder": `simcase.build_mesh3d` through the builder (**experimental**) | `x0`–`z1` on the domain faces, `void` elsewhere; parts `<id>.side`, `<id>.bottom`, `<id>.top`, `<id>.surface` |

The result's `route` (and the summary's `mesh_route`) says which route ran. A lone `layers`
feature with footprint layers is not taken yet. On the extrude route the faces carry their
tags only, so `selections` and `boundary_tags` are refused there.

## On an existing mesh

The mesh and the solve can run apart, for example the mesh in another process (Studio's
[3D heat run](studio_3d.md#run) does this):

- `simcase.build_thermal3d_mesh(document, component=None)` makes the mesh the kind solves on, by
  the route table above: the `meshine.extrude` `galerkin.Mesh3D` for a lone slab `layers`
  component, otherwise `build_mesh3d`'s `Mesh3DResult`. The document needs no physics block;
  on the extrude route the size is `mesh.element_size` converted as the document reader
  converts it.
- `simcase.solve_thermal3d(doc, mesh, verbose=True)` solves a `thermal.steady3d` document on
  that mesh and returns the result `simcase.run` returns, bit for bit (nodes, tetrahedra,
  temperature, reaction heat rate and every summary value), with no mesh time. `run` itself
  is now the mesh step and then this same solve. A mesh of the other route or of another
  component is refused by name (`E-CONTRACT`).
- `simcase.mesh3d_to_arrays(mesh)` and `simcase.mesh3d_from_arrays(arrays, document=None)` write a
  `Mesh3DResult` or a `galerkin.Mesh3D` as a flat `{name: ndarray}` of numeric and string arrays
  (format `openphysics-mesh3d-arrays-v1` in the `meta` array; names carry an index, never a tag),
  which `numpy.savez` writes and `numpy.load(..., allow_pickle=False)` reads, and read it back bit
  for bit. On the meshloom route the exact complex is rebuilt from the document's geometry; the
  hand-off and meshloom's raw output are not kept.

`tests/simcase/test_thermal_steady3d_on_mesh.py` checks the solve against `simcase.run` and the
array round trip, both bitwise, on all three routes.

## Keys

| Key | Meaning |
|---|---|
| `physics.<name>.prescribed_temperature` | `{boundary name: temperature}`. On the meshloom route a name is resolved by the [selector rules](geometry_document.md#selector-rules-frozen): a tag, a named boundary selection, a provenance name (`domain.z0`, `via.x1`, `stack.c.top`) or a feature id. On the extrude route it is one of the tags above. On the builder route it is a tag, an exterior part (`via.bottom`, `sa.surface`, `domain.z0`) or a feature id (all its parts). Required: at least one. |
| `physics.<name>.heat_source_density` | one value, or `{region: value}` over the meshed regions; absent: no source |
| `materials.<m>.thermal_conductivity` | the conductivity of every region whose material is `m` |
| `mesh.element_size` | required; on the meshloom route also `mesh.element_count_limit` and `mesh.controls` `element_size`, as [build_mesh3d](geometry_engine3d.md#use) takes them |

Every exterior face that no `prescribed_temperature` names is insulated; each default tag
left unnamed is reported once as `I-DEFAULT-BOUNDARY`. A node fixed by two names must get one
temperature.

Refused by name:
- a fixed temperature on an interior face (`E-CONTRACT`): `Fixed temperature needs an outer
  face; <name> is inside` — galerkin fixes exterior nodes only;
- a name that selects no face and a source on a region that is not meshed (`E-SELECTION-UNKNOWN`);
- `inward_heat_flux`, `convection` and the other keys of the 2D kind (`E-KEY-UNKNOWN`), and
  `thermal_conductivity` on the physics entry (it comes from `materials`);
- a material without `thermal_conductivity` (`E-PROPERTY-MISSING`);
- a `2d` or axisymmetric component, or more than one component;
- `mesh.subdivision_count`, `minimum_angle` and `grading`;
- any study other than `{"type": "single"}`, and `results.plots`.

## Results

`summary.json` has `result_format` `thermal.steady3d-result-v1` and `field_layout`
`thermal3d-p1-node-tet-regions-v1`, with the shared envelope of format 0.3 results
(diagnostics, defaults, resolved inputs, extent, timing), `mesh_route`, the regions (material,
tetrahedra, volume), the materials, the prescribed temperatures, `reaction_heat_rate_by_boundary`
(W per `prescribed_temperature` name; a node fixed by two names counts under the first),
`generated_heat_rate`, `outward_reaction_heat_rate`, `heat_rate_imbalance`,
`relative_conservation_residual`, the temperature and conductivity extremes, and the mesh
counts and tags. Rates are totals in W, under the plain names (there is no depth).

`fields.npz` holds:

| Array | Shape | Unit | Location |
|---|---|---|---|
| `node_coordinates` | (N, 3) | m | nodes |
| `tetrahedra` | (T, 4) | — | tetrahedron connectivity |
| `tetrahedron_regions` | (T,) | — | index into `region_names` |
| `temperature` | (N,) | K | nodes |
| `heat_flux` | (T, 3) | W/m² | tetrahedron centroids |
| `generated_heat_rate`, `reaction_heat_rate`, `residual_heat_rate` | (N,) | W | nodes |
| `prescribed_node_ids`, `prescribed_temperature` | (P,) | —, K | prescribed nodes |

`simcase export` does not take this layout yet; read `fields.npz`.

## Validation

Measured on Linux (2026-11-27), `tests/simcase/test_thermal_steady3d.py`:

| Check | Case | Threshold | Measured |
|---|---|---|---|
| P1 through the kind | the document above (E1) at h = 0.8 and 0.4 mm, against `refsol.thermal3d.layered_slab` | max nodal \|T_h − T\| ≤ 1e-10; top heat rate (reaction on `z1`) relative error ≤ 1e-9 | 1.4e-12 and 3.4e-12; 2.5e-11 and 4.8e-12 (7,680 and 49,152 tetrahedra; T is near 300 K) |
| Bit identity, extrude route | E1 against `meshine.extrude` + `solve_steady_heat_3d` called directly | the same SHA-256 of nodes, tetrahedra, temperature and reaction heat rate | the same |
| Bit identity, meshloom route | E1 with a copper box in the core layer against `build_mesh3d` + `solve_steady_heat_3d` | the same SHA-256 | the same |

Builder route (stage 5, slice 4b; `tests/simcase/test_thermal_steady3d_builders.py`). The physics is
gated on `build_mesh3d` + `solve_steady_heat_3d` called directly, and the kind must equal it:

| Check | Case | Threshold | Measured (Linux, 2026-11-27) |
|---|---|---|---|
| P2 (main) | E2: C4 in m, slab [−1,1]² × [0,1] with k = 1 W/(m K), via r = 0.3 with k = 100 W/(m K), T = 300 K on `z0` and 301 K on `z1`; Q = ΔT/L (k_v πr² + k_s(A − πr²)) = 31.99 W; h 0.2, 0.1, 0.05 | e_Q(0.05) ≤ 1e-2; slope against the ring chord s = 2πr/m (m from `I-SURFACE-SAMPLED`) ≥ 1.5 | e_Q 1.68e-2, 7.51e-3, 2.71e-3 (m = 16, 24, 40); slope 1.99 |
| P3 (main) | E3: C11 with a hole r = 0.5, k = 1 on (0.5, 0.75), k = 4 on (0.75, 1), T = 301 K inside and 300 K outside; Q = 16π/3 W; h 0.2, 0.1, 0.05 | e_Q(0.05) ≤ 5e-3; slope against h ≥ 1.6 | e_Q 3.25e-2, 1.05e-2, 2.07e-3; slope 1.99 |
| P3(a) | E3: Q_h against V24's C_h = uᵀKu on the same mesh (Σ k_T \|∇u_T\|² V_T, u = T − 300 K) | ≤ 1e-9 relative (PR at 0.2, 0.1; main at all three) | 3.8e-14, 5.0e-15 |
| The kind | E2 and E3 through `thermal.steady3d` against the direct path | Q_h and nodal T within 1e-12 relative | identical (0) |
| Refusal | a fixed temperature on `via.side` (E2) or `sb.surface` (E3) | `Fixed temperature needs an outer face; <name> is inside` (`E-CONTRACT`) | as stated |

## Limits

- Steady conduction with prescribed temperatures and volumetric sources only: no flux,
  convection, transient or coupling yet. Studio does not open the kind.
- The meshloom route is experimental until meshloom's acceptance, and takes boxes and slab
  layers ([3D boxes and slab layers](geometry_engine3d.md)); the extrude route takes a lone
  stack of slab layers. The builder route takes meshloom's four builder shapes with one
  element size; its result's `mesh_route` is `"builder"` and its diagnostics carry
  `I-MESH-ESTIMATE` and one `I-SURFACE-SAMPLED` per sampled surface.
- `simcase export` refuses the layout as unsupported.
