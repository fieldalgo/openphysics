# Polygon conductors, local dielectrics and surface masks

**English** | [한국어](../../locales/ko/pages/packages/sipi/polygon_sections.md)

[Overview](overview.md) · [Templates and JSON](design.md) · [Tapered traces](manufacturing_sections.md)

`PolygonTrace(name, vertices, ground=False)` describes a finite simple conductor
in the cross-section's metre coordinates. Vertices may run clockwise or
counterclockwise and the outline may be concave. The closing vertex is implicit.
Repeated vertices, zero area, self intersections, conductor contacts and overlaps
are rejected. No equivalent rectangle replaces the polygon. Holes inside a
conductor, curved boundaries and CAD import are outside this API.

`DielectricRegion(name, vertices, eps_r=1, tan_delta=0)` describes a local material
with the same simple-polygon rules. Pass regions to
`CrossSection(..., dielectric_regions=[...])`. Their interiors must be disjoint;
they may share edges, cross layer interfaces and touch the box. They override
underlying layers, while metal interiors take precedence over all dielectrics.
A region must remain inside the box and have positive dielectric area after
metal removal. Layer and region names must be unique together.

```python
from sipi import CrossSection, Layer, PolygonTrace, DielectricRegion, CrossSectionDocument

section = CrossSection(
    [Layer('substrate', 1e-3, 4), Layer('air', 1e-3)],
    [PolygonTrace('signal', [(-.3e-3, 1e-3), (.3e-3, 1e-3),
                             (.2e-3, 1.2e-3), (-.25e-3, 1.2e-3)])],
    4e-3,
    dielectric_regions=[DielectricRegion('mask',
        [(-.4e-3, 1e-3), (.4e-3, 1e-3), (.4e-3, 1.3e-3), (-.4e-3, 1.3e-3)], 3.5, .02)])
document = CrossSectionDocument(section, mesh=dict(edge_size=5e-6, far_size=.2e-3, grade=.15))
restored = CrossSectionDocument.loads(document.dumps())
parameters = restored.analyze()
```

## Masks and additional templates

The following functions are in `sipi.templates`:

| Function | Geometry / additional inputs |
|---|---|
| `with_surface_mask(section, thickness, eps_r, tan_delta=0, gap_fill_height=0)` | Keyword-only mask inputs; offsets top and side faces of finite coplanar rectangular/tapered traces, including coplanar ground traces |
| `offset_stripline` | `stripline` inputs plus required `trace_height`, the bottom face height above the lower plane |
| `coupled_stripline` | `stripline` inputs plus required horizontal bottom-edge `gap`, optional `trace_height`; equal widths, positive/negative names |
| `broadside_stripline` | Required `width`, vertical metal-to-metal `gap`, `plane_spacing`, `eps_r`, positive `thickness`; optional signed horizontal `offset`, `tan_delta`, `box_width`; rectangular lower/upper positive/negative traces |

The new stripline templates use a homogeneous dielectric between two ground
planes. Custom layer stacks, unequal widths and polygons use `CrossSection`.
The mask template requires a common conductor bottom on a layer interface.
Coating faces are parallel offsets with **straight mitred corners, mitre limit
5**; this is an explicit polygon approximation, not a predicted meniscus or a
rounded manufacturing profile. The part below the common bottom is removed.
No lateral or top clipping is hidden: an out-of-box mask is rejected. Existing
local regions are preserved and must not overlap it.

`gap_fill_height` optionally adds a flat fill from that bottom across the full
box width, merging it with the side/top coating. A connected result is named
`mask`; disconnected regions are `mask_1`, `mask_2`, ... in left-to-right bounding
box order. Geometry changes can change that partition and therefore its names.
Each name accepts its own dielectric model. Resulting mask polygons containing
holes are rejected; supply a partition into simple regions for such geometry.

```python
from sipi.templates import coupled_microstrip, with_surface_mask
pair = coupled_microstrip(width=.4e-3, gap=.2e-3, substrate_height=1e-3,
                          eps_r=4, thickness=.1e-3, air_height=1e-3, box_width=4e-3)
masked = with_surface_mask(pair, thickness=.03e-3, eps_r=3.5,
                           tan_delta=.02, gap_fill_height=.08e-3)
```

## Geometry and engine composition

Polygon intersections partition each layer and local material. Mesh constraints
follow the actual conductor and dielectric boundaries, including crossings and
concave corners. Zero-thickness `Trace` strips can coexist: horizontal splitting
and endpoint constraints preserve their full length through local materials.
Sections with neither polygons nor local regions retain the original rectangular
or tapered meshing path. Polygon representations of rectangles use an independent
partition and need not produce identical meshes.

Default refinement includes polygon minimum vertex/edge clearance and local
region clearance. Local region vertices also attract corner refinement. Tiny
gaps, nearly collinear vertices and sharp angles can be expensive or fail meshing;
errors propagate. Explicit edge/far/grade refinement and box enlargement remain
necessary for each design; the sampled tests do not certify arbitrary shapes.

`section.materials` lists layers followed by local regions. `dispersive_line` and
`TransmissionLineDocument` accept models for either kind by name; unspecified
materials retain their constant values. `mesh_conductor_section` includes exact
polygon metal interiors, and `VolumeLineDocument` carries the same local materials
on the matched dielectric mesh. Magnetic-only meshes do not add material edges.
Surface loss uses polygon minimum clearance instead of a bounding-box width for
the skin-depth gate. The existing delta <= dimension/5 and 5% integrated-current
gates remain; clearance is not a curvature or resistance-error guarantee.

## JSON v3

`sipi.cross-section/3` retains `length_unit`, `layers`, `box`, `mesh` and `traces`
and **requires** `dielectric_regions` (possibly empty).

- Polygon trace: `{kind: "polygon", name, vertices, ground}`.
- Rectangular/tapered trace: `{kind: "trapezoid", name, x, width, y, thickness,
  top_width, ground}`; rectangles have equal bottom and top widths.
- Local region: `{name, vertices, eps_r, tan_delta}`.
- `vertices` contains finite `[x,y]` pairs, with no repeated closing vertex.
  No holes, radius, rotation, implicit units or unknown fields are accepted.

Construction emits v3 when a polygon or local region is present; other inputs
continue to emit v1 or v2. Reading and saving an explicit v3 document preserves
its version, even for rectangles. Existing transmission-line and volume-line
schemas embed v3 unchanged; they do not need a new outer schema. Old consumers
must reject v3 instead of flattening it. This change does not update browser
consumers or provide UI/EXE support.

## Validation and limits

`tests/sipi/test_polygon_sections.py` checks exact dielectric, mask and metal areas
(relative 1e-12), material boundary conformity, immutable inputs, thin strips,
contact rejection, strict v3 round trips, local dispersive materials, volume DC
resistance (analytic 1e-9), surface gates, template symmetry and permittivity
monotonicity. Rectangular polygon equivalence, reflected geometry and halved
edge/far/grade impedance differences must be below 0.5%. Homogeneous C/C0 must
match eps_r within 1e-9. Internal volume labels cannot alias user material names.

On Linux / Python 3.12.14 / NumPy 2.5.4 / SciPy 1.18.1 / Shapely 2.2.0, the
rectangular and polygonal representations gave 44.550999 and 44.550400 ohms.
The concave signal with a local mask gave 51.529417 ohms at edge 10 um,
far 0.2 mm, grade .15; 51.581918 after halving all three (0.102% change), and
51.582412 after reflection. These are measured cases, not global error bounds.
Independent scikit-fem 12.0.2 complex P1 assembly on the same mesh differed in
complex C by 5.44e-15 (criterion 1e-9). The test emits a standard comparison
record; shared-mesh agreement is distinct from convergence evidence. New code
has been exercised locally on Linux; no new Windows/macOS execution claim.
All 25 new checks passed from source and from locally built SIPI/meshine/galerkin
wheels. The combined SIPI and related documentation/reference-tool regression
passed 673 checks with no skips (402.90 s); this is not full-repository CI.

```bash
OPENPHYSICS_REQUIRE_CROSSCHECK=1 OPENBLAS_NUM_THREADS=1 \
  python -m pytest -q tests/sipi/test_polygon_sections.py
```

Run the [polygon/mask example](../../../examples/sipi/polygon_mask.py) to save and
restore both geometries and print a mesh-refinement comparison. SIPI now declares
its own Shapely requirement (`>=2.0.2`), using the existing reviewed Python API;
no upstream code or binaries are copied. See the [license inventory](../../third-party.md)
for Shapely's BSD terms and its dynamically loaded GEOS components.
