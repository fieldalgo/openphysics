# Steady outward-flux and convection documents

[한국어](locales/ko/pages/thermal_steady_boundary2d.md)

## Contract and implementation status

This page describes the boundary-extension input/output contract for
`thermal.steady2d`. The [existing steady guide](thermal_steady2d.md) describes
the legacy headless path. At the documentation base
`6d6eac56d1dddb8bdfe3f23d6db78d674487a42b`, that public reader/runtime
does not yet implement this extension. The independent boundary helper at
`1c408be05e8f103e8436502610e03c763493d200` implements input/mesh checks,
not a public JSON/CLI solve or save. Runtime and schema integration are separate.
The example below is a contract example, not an observed successful run.
No new source, installed, CI or platform acceptance is asserted by this draft.

## Inputs and supported scope

Use format `"openphysics": "0.2"`, one `thermal.steady2d` physics,
a homogeneous rectangle, P1 triangles, constant isotropic
`conductivity_w_mk > 0` in W/(m K), and signed constant
`heat_source_w_m3` in W/m³ (default zero). Declare length units and
`temperature: "K"`; geometry is converted to metres, while SI suffixes
are independent of the declared length unit. Mesh subdivisions are positive,
nonboolean JSON integers. Study is single and plots are false.

| Physics field | Contract |
| --- | --- |
| `dirichlet_temperature_k` | Required side-to-temperature mapping; finite input K >= 0 |
| `outward_flux_w_m2` | Optional side-to-signed-constant g mapping, W/m² |
| `convection` | Optional side-to-object mapping with exactly `h_w_m2k` and `ambient_temperature_k` |
| `h_w_m2k` | Finite h >= 0, W/(m² K) |
| `ambient_temperature_k` | Finite ambient K >= 0, including when h=0 |

Side names are exactly left/right/bottom/top. Missing natural conditions mean
insulation. Null, booleans in numeric fields, nonfinite numbers, unknown keys,
callbacks and arrays instead of side constants are rejected. Signed sources
and outward flux are valid. Input nonnegative Kelvin is a document policy;
finite negative computed temperatures are retained, without clamp.

Equal prescribed corner temperatures deduplicate; conflicting values reject.
A side may carry both flux and convection, which add. Each condition kind must
select complete unique exterior edges, not interior or repeated/reversed edges.
An edge with both endpoints Dirichlet rejects even for zero flux or h.
One Dirichlet endpoint is allowed and retains the full consistent edge load;
side-name disjointness alone does not prove endpoint disjointness.

Empty Dirichlet is valid only with positive h on a real nonempty boundary.
Zero h does not anchor temperature. Compatible pure Neumann data still have
a constant nullspace and are rejected, as are incompatible data. No artificial
pin or mean-temperature gauge is inserted. Arbitrary/disconnected geometry,
temperature-dependent material, transient flux/Robin, coupling and Studio
thermal rendering are outside this contract.

## Signs, units and balance

Positive g is heat leaving the domain. Robin heat is positive outward when
T exceeds ambient Ta. With q=-k grad(T), the weak form is:

```text
q.n = g + h*(T-Ta)
A = K+H
rhs = fQ+B-G
G_i = integral_boundary(g*N_i)
B_i = integral_boundary(h*Ta*N_i)
C = H*T-B
r = (K+H)*T-(fQ+B-G)
reaction = r on Dirichlet nodes, zero on free nodes
total_outward = sum(G+C-reaction)
sum(fQ) = total_outward
```

K and H have units W/(m K). All nodal loads, rhs, residual, reaction and
integrated heat rates are W/m of out-of-plane depth; q is W/m².
`load_w_per_m` remains the volumetric source fQ, not the combined rhs.
The thermostat contribution alone is -sum(reaction); it is not total outward
heat when flux or convection is present. No transient storage or heat-content
quantity is introduced.

For a straight edge of length ell, consistent line integration gives:

```text
H_e = h*ell/6 * [[2,1],[1,2]]
G_e = g*ell/2 * [1,1]
B_e = h*Ta*ell/2 * [1,1]
```

Do not lump the boundary mass or discard fixed-end loads. The engine's shifted
evaluation and physical residual/balance guards remain authoritative.

## Contract example

This unit-square linear solution has T=300-7x K and qx=14 W/m².
On the right, g=2 and h*(T-Ta)=12; the left thermostat contributes
-14 W/m. These are analytical expectations, not measurements.

```json
{
  "openphysics": "0.2",
  "name": "Steady additive boundary contract",
  "units": {"length": "m", "temperature": "K"},
  "geometry": {"domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1}},
  "materials": {},
  "physics": {"heat": {
    "type": "thermal.steady2d",
    "conductivity_w_mk": 2,
    "heat_source_w_m3": 0,
    "dirichlet_temperature_k": {"left": 300},
    "outward_flux_w_m2": {"right": 2},
    "convection": {"right": {"h_w_m2k": 1, "ambient_temperature_k": 281}}
  }},
  "mesh": {"subdivisions": [8, 8]},
  "study": {"type": "single"},
  "results": {"save_fields": true, "plots": false}
}
```

## Version and raw-field contract

Presence of either new mapping key, even an empty object, selects
`thermal.steady2d-result-v2` and `thermal2d-p1-node-cell-boundary-v2`.
Absence of both retains legacy v1 identifiers and nine arrays. Do not insert
empty defaults or infer versions from nonempty values. Null is invalid.
Input format remains 0.2.

The nine legacy arrays retain their units and meanings. V2 adds four nodal
arrays of shape (N,) and unit W/m:

| Array | Meaning |
| --- | --- |
| `prescribed_outward_load_w_per_m` | G |
| `ambient_load_w_per_m` | B |
| `convective_outward_w_per_m` | C |
| `system_rhs_w_per_m` | fQ+B-G |

For Robin-only anchoring, both Dirichlet arrays have shape (0,); node IDs
remain integer. Full residual uses A and rhs above. Consumers must check
format/layout, units, shapes, finite numeric types and metadata, using
`allow_pickle=False`. Missing v2 fields must not be replaced with invented
zeros. Exact public result properties, summary diagnostics and save metadata
must be checked against the runtime candidate before this draft is finalized.

## Geometry, lifetime and validation limits

Finite coordinates alone do not guarantee distinguishable sides. The helper
uses 64 machine eps times the larger absolute coordinate/extent per axis.
It rejects a tolerance reaching half an extent, overlapping side-edge
classification, incomplete rectangles and incorrect node/edge tags.
Dirichlet identity comes from verified exterior-edge endpoints, not a broad
coordinate mask that can include nearby interior nodes. Large origins and
very short edges may be rejected for insufficient coordinate precision;
choose a smaller coordinate origin rather than relaxing geometry guards.

The runtime must bind saved metadata to the original calculation and preserve
the [fresh-output ownership contract](thermal_steady2d.md#output-ownership-and-failures).
Set output options before running. Fields-disabled saves still require raw and
finite-JSON checks; no atomic publication, hostile-writer protection or crash
rollback is implied. Exact snapshot enforcement awaits actual runtime review.

Preserve n8/16/32/64 final-two temperature L2 order >=1.8 and flux order >=0.9,
normalized residual/balance 1e-10 and SI similarity 1e-9. Existing quadrature
and independent negative controls remain separate gates. Constant JSON boundary
data do not serialize sine/callback MMS. Test declarations, helper diagnostics,
public API/CLI, installed consumers and exact CI are different evidence levels.
Linux results do not establish Windows/macOS acceptance.
