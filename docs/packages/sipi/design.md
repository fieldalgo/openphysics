# Cross-section templates, documents and impedance design

**English** | [한국어](../../locales/ko/pages/packages/sipi/design.md)

[SIPI overview](overview.md)

These APIs use the ordinary quasi-static engine; they add input reproducibility
and bounded search, not additional physics. All lengths are metres, impedances
and residual tolerances are ohms. See the overview for physical limitations.

## Templates

Each function returns a `CrossSection`. Required arguments are keyword-only.

| Function | Required inputs | Geometry |
|---|---|---|
| `microstrip` | `width`, `substrate_height`, `eps_r` | Surface signal above a bottom ground plane |
| `stripline` | `width`, `plane_spacing`, `eps_r` | Signal centred between two ground planes in one dielectric |
| `coupled_microstrip` | `width`, `gap`, `substrate_height`, `eps_r` | Two equal-width surface signals; `gap` is edge to edge |
| `grounded_coplanar` | `width`, `gap`, `ground_width`, `substrate_height`, `eps_r` | Surface signal between finite-width grounds, with a bottom ground plane |

All accept `thickness=0`, `tan_delta=0` and `box_width=None`. Surface templates
also accept `air_height=None`, defaulting to `10 * substrate_height + thickness`.
Stripline plane spacing includes the conductor thickness. Every side wall is
open (zero normal displacement); the stripline top is grounded and other tops
are open. Default box widths are `max(20*h, 4*w)` for microstrip,
`max(12*b, 4*w)` for stripline, `max(20*h, 4*(2*w+gap))` for a pair and
`max(20*h, 4*w, w+2*gap+2*ground_width+4*h)` for coplanar geometry.

These defaults are starting domains, not truncation guarantees. Enlarge the box
and air independently to check truncation; also enlarge coplanar ground width.
Zero thickness is allowed, but width, gap and dielectric dimensions must be
positive. Invalid or overlapping geometry raises before meshing. Names are
`signal`, or the ordered pair `positive`, `negative`; coplanar reference traces
are `ground_left`, `ground_right`. Layers are `substrate`, `air`, or `dielectric`.

## Input document

```python
from sipi import CrossSectionDocument, microstrip

doc = CrossSectionDocument(microstrip(
    width=1e-3, substrate_height=1e-3, eps_r=4.3, thickness=35e-6),
    mesh={"edge_size": 3.5e-6, "far_size": 0.5e-3, "grade": 0.15})
text = doc.dumps()
restored = CrossSectionDocument.loads(text)
line = restored.analyze()
```

The JSON root has exactly these required fields:

| Field | Contract |
|---|---|
| `schema` | `"sipi.cross-section/1"` |
| `length_unit` | `"m"`; no implicit conversion |
| `layers` | Nonempty ordered array of `{name, thickness, eps_r, tan_delta}` |
| `traces` | Nonempty ordered array of `{name, x, width, y, thickness, ground}` |
| `box` | `{width, bottom, top, sides}`; boundaries are `"open"` or `"ground"` |
| `mesh` | Object with optional `edge_size`, `far_size`, `grade`, `min_angle` |

Names are nonblank strings and unique within each array. Numbers must be finite
real values, never booleans or numeric strings; `ground` must be a boolean.
Unknown or missing fields, unknown versions, duplicate JSON keys and nonfinite
numbers are rejected. Geometry follows the `CrossSection` contract. Mesh lengths
are positive with resolved `edge_size <= far_size`, `grade >= 0` and
`0 < min_angle < 34` degrees (default 28). Null mesh options are rejected; omit
an option to use its default. `section.mesh_settings(**options)` resolves and
validates all mesh defaults without generating a mesh.

`from_dict` and `to_dict` operate on plain objects. The document snapshots inputs;
`section`, `mesh_options` and `to_dict()` return fresh values. `dumps()` returns
deterministic JSON and never writes a file. Results are not saved in this input
schema. Omitted mesh settings use the installed engine's defaults; to archive
explicit settings, construct with `mesh=section.mesh_settings()` and record the
engine version alongside the document. Defaults and numerical implementations
can change between versions.

## Target impedance

```python
from sipi import seek_impedance, stripline

result = seek_impedance(
    lambda w: stripline(width=w, plane_spacing=1e-3, eps_r=4),
    (0.3e-3, 0.8e-3), 50.0,
    mesh={"edge_size": 0.5e-6, "far_size": 0.125e-3, "grade": 0.075},
    tolerance=0.1, max_evaluations=20)
print(result.parameter, result.impedance, result.refined_impedance)
```

`factory(parameter)` returns a valid `CrossSection`. Bounds must be positive,
finite and increasing, in the parameter's units. `quantity="z0"` selects a
single signal; `"z_diff"` selects a symmetric pair through `even_odd()`, including
its symmetry checks. Target and tolerance must be positive finite ohms.

The search evaluates both endpoints and accepts an endpoint within tolerance;
otherwise opposite endpoint residual signs are required. Bisection stops only
when the actual impedance residual is within tolerance. One solve is reserved
for a refinement with `edge_size`, `far_size` and `grade` halved. Both requested
and refined impedances must meet the target tolerance. `max_evaluations` counts
all solves, including the final refinement, and must be an integer of at least 3.

`ImpedanceDesign` contains the parameter, target, quantity, requested and refined
impedances, input document and evaluation history. `residual`,
`refined_residual` and `mesh_change` keep the target error and mesh change
distinct. The document is the requested-mesh input. `GoalSeekError.history`
records completed evaluations when a bracket, evaluation budget, parameter
resolution or refinement check fails. Invalid input and factory/solver errors
propagate; a failure is never returned as a successful design. On a refinement
failure, tighten mesh settings and rerun. This is a numerical target check, not
a manufacturing-tolerance guarantee or a proof of monotonicity for arbitrary
factories. Box/material uncertainty needs separate analysis.

## Validation

`tests/sipi/test_design_documents.py` checks all four templates against explicit
geometry and checks that JSON round trips preserve C, C0, L and dielectric-loss
matrices. Invalid fields, mutation isolation and search failure paths are covered.
The real-FEM 50-ohm stripline search is compared with an independently rooted
Cohn conformal-map formula: width must agree within 1%, and both mesh residuals
must be at most 0.1 ohm. These thresholds were set before running the test.
The 47 tests passed on Linux, Python 3.12.14, NumPy 2.5.4 and SciPy 1.18.1;
platform and installed-package acceptance is handled separately by required CI.
Existing physical reference thresholds are unchanged. No new external dependency
or independent validation of coplanar physics is claimed by template equivalence.
