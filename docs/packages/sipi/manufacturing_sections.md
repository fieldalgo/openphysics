# Tapered conductors and planar coating

**English** | [한국어](../../locales/ko/pages/packages/sipi/manufacturing_sections.md)

[Overview](overview.md) · [Templates and JSON](design.md)

`Trace(..., top_width=...)` describes a **centred trapezoid**, not an equivalent
rectangular width. `width` is the bottom width, `top_width` the top width, `x`
the shared centre, `y` the bottom and `thickness` the vertical height, all in m.
Top width must be finite and positive. Either top or bottom may be wider.
A zero-thickness trace can only have equal widths. `top_width=None` retains
all existing rectangular behavior. Ground traces can also be tapered.

```python
from sipi import CrossSectionDocument, microstrip
from sipi.templates import coated_microstrip

bare = microstrip(width=0.6e-3, top_width=0.4e-3, thickness=0.1e-3,
                  substrate_height=1e-3, eps_r=4)
coated = coated_microstrip(width=0.6e-3, top_width=0.4e-3, thickness=0.1e-3,
                          substrate_height=1e-3, eps_r=4,
                          coating_height=0.2e-3, coating_eps_r=3.5,
                          coating_tan_delta=0.02)
document = CrossSectionDocument(coated)
restored = CrossSectionDocument.loads(document.dumps())
parameters = restored.analyze()
```

The four original template functions accept optional `top_width` for their
signal conductors. Coupled pair `gap` and coplanar clearance refer to **bottom
edges**; widening a top can shrink the actual gap or cause overlap, which is
rejected before meshing. Coplanar template grounds stay rectangular. Box-width
defaults retain their original bottom-width formulas; enlarge the box explicitly
if the top widths need more room. Direct `CrossSection` accepts arbitrary
nonoverlapping combinations of these centred traces and horizontal layers.
`x0`/`x1` remain bottom-face endpoints; `xmin`/`xmax` are the full horizontal extent.

`coated_microstrip` is available from `sipi.templates`. `coating_height` is the
flat coating surface's height above the substrate, **including the conductor
thickness**, and must exceed that thickness. The coating fills the spaces beside
and above the conductor; a distinct air layer is above it. `coating_eps_r>=1`,
`coating_tan_delta>=0` and ordinary substrate loss tangent are separate. Other
surface-template arguments have the same meaning. This is a planar filling
model, not a conformal coating, local resist pocket, meniscus or arbitrary mask.

## Geometry and meshing

Layers and conductor bottom/top faces split the domain into horizontal slabs.
Within a slab, straight conductor faces bound exact dielectric polygons. Shared
layer segments are constrained and materials assigned by slab. A conductor is
a hole in the dielectric, including where it crosses a material interface.
Infinitely thin strips remain constrained line segments. Distance to the actual
polygon drives grading and identifies conductor boundary nodes. Placement uses
actual overlapping vertical spans, rather than rejecting overlapping bounding
boxes that contain disjoint trapezoids.

When every trace is rectangular, the original rectangular partition is used
unchanged, including an explicitly equal top width. Tapered defaults include
both face widths and the actual inter-trace distance among mesh features, with
the existing positive-thickness/10 cap. Explicit mesh settings keep their meaning.
Thin layers, narrow gaps, strong taper and small top widths can be expensive;
mesher failures are propagated rather than replaced by a rectangular model.
Check edge/far/grade refinement and domain truncation for each design.

The executable [coated-trace example](../../../examples/sipi/coated_trace.py)
saves/restores the input and compares the initial and halved mesh.

## JSON versions

- `sipi.cross-section/1` is unchanged: the trace fields are
  `{name,x,width,y,thickness,ground}`. Unknown `top_width` is rejected in v1.
- `sipi.cross-section/2` adds **required** `top_width` to **every** trace, with
  equal bottom/top widths for rectangular members. Other fields and SI units
  are unchanged. Null, boolean or missing top widths are rejected.
- Constructing a document emits v2 only if any trace has unequal widths;
  rectangular models continue to emit v1. Reading v2 and then dumping that
  document preserves v2. Both versions retain strict duplicate/unknown fields,
  finite-number validation and copied input snapshots.
- Coating uses ordinary layers and needs no extra schema fields. Old v1-only
  consumers must reject a tapered v2 document; do not silently flatten it.

## Validation

`tests/sipi/test_manufacturing_sections.py` fixes these acceptance criteria:
rectangular-limit nodes/triangles/C exactly equal; exact dielectric area relative
1e-12; no elements in the conductor or crossing a dielectric interface; correct
signal tags; thin-strip coexistence; upper/lower reflection and all-three-settings
halving impedance changes <=0.5%; homogeneous C/C0=eps_r within 1e-9; tapered
capacitance between nested narrow/wide rectangular conductors. An eps_r=1 coating
recovers the uncoated domain within 0.5%, and increasing coating permittivity
increases C and lowers Z.

The first 15 checks passed on Linux, Python 3.12.14, NumPy 2.5.4 and SciPy 1.18.1.
For a homogeneous stripline with 0.6/0.3 mm faces, thickness 0.4 mm, 2 mm plane
spacing and eps_r=4: Z was 48.12452 ohms at edge 5 um, far 0.25 mm, grade 0.15;
48.18408 after halving all three, and 48.18417 with the top/bottom widths swapped.
Thus mesh change was 0.124% and reflection difference 0.00018%. An air-equivalent
coating gave 93.28491 vs 93.28555 ohms without that interface. These are specific
cases, not universal error bounds.

The existing test-only BSD scikit-fem **12.0.2** assembles and solves the same
P1 mesh independently for two asymmetric tapered conductors crossing an eps_r=4/6
interface. The capacitance comparison criterion is relative 1e-9. The lossless
observation was 7.46e-15; the complex-C observation with dielectric loss was 1.39e-14.
This same-discretization check is algorithmic evidence, not a convergence proof.
Required CI installs the reference through the existing galerkin comparison extra;
local tests skip it when unavailable unless `OPENPHYSICS_REQUIRE_CROSSCHECK=1`.
No new runtime dependency is introduced. Existing physical thresholds/goldens remain.

```bash
OPENPHYSICS_REQUIRE_CROSSCHECK=1 OPENBLAS_NUM_THREADS=1 \
  python -m pytest -q tests/sipi/test_manufacturing_sections.py
```

These models do not add arbitrary polygons, offset top faces, curved corners,
conductor loss, frequency dispersion, manufacturing distributions or website support.
