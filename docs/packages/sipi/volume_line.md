# Matched finite-metal and dielectric line model

**English** | [한국어](../../locales/ko/pages/packages/sipi/volume_line.md)

[Conductor diffusion](conductor_diffusion.md) · [Dielectric materials](dielectrics.md) ·
[Uniform-line networks](network.md)

`sipi.volume_line` extracts DC/AC R and total L inside finite conductors, and
C/G in the dielectric surrounding **those same metal surfaces**. A strict
`sipi.volume-line/1` JSON document saves the geometry, material models,
conductivity, volume-mesh controls, frequencies, length and reference impedance.
It describes a finite dielectric box in vacuum, with finite reference plates;
it does not substitute the older box-ground dielectric extraction.

```python
from sipi import CrossSectionDocument, microstrip
from sipi.volume_line import VolumeLineDocument

section = microstrip(width=.4e-3, substrate_height=.5e-3, thickness=.1e-3,
                     eps_r=4, tan_delta=.02, air_height=.5e-3, box_width=2e-3)
doc = VolumeLineDocument(CrossSectionDocument(section), [0, 1e3, 1e5],
    materials={}, conductivity=58e6, relative_permeability=1, length=.1, z_ref=50,
    mesh=dict(ground_thickness=.1e-3, padding=2e-3, metal_size=12.5e-6,
              far_size=.125e-3, grade=.05, min_angle=28))
result = VolumeLineDocument.loads(doc.dumps()).analyze()
print(result.R, result.L, result.G, result.C)  # per-metre SI, (F,N,N)
print(result.network.s)                     # (F,2N,2N)
```

The executable [example](../../../examples/sipi/volume_line.py) round-trips the
input and reports sampled values. This is a quasi-TEM/MQS approximation with
explicit resolution and material limits, not a full-wave or broadband accuracy
certificate. Refine metal and exterior meshes and enlarge the box independently.

## Shared physical geometry

`mesh_conductor_section(..., dielectric_interfaces=True)` preserves all metal
polygons and additionally conforms to the layer heights and the two vertical
walls of the dielectric box. Layers occupy only `[-width/2,width/2] × [0,height]`
minus the metal; the rest of the nonconducting volume is vacuum. Ground plate
thickness and magnetic padding follow the [volume conductor contract](conductor_diffusion.md).
The option defaults to False in the standalone magnetic mesh API, preserving
its original mesh behavior. The line document always enables it.

`dielectric_view(volume)` removes metal triangles, compacts surviving node
indices, and maps the surviving **same coordinates** of each electrode to
signal/reference potential sets. It returns `(mesh, signals, ground,
original_nonmetal_triangle_ids)`. No interpolation or second geometric mesher
is used. All metal interiors remain in the magnetic solve.

The outer electric boundary has zero normal D; the outer magnetic boundary
fixes Az=0. These are explicit finite-domain approximations, not identical
field boundary equations. All grounded plates/traces form one common reference.
Dielectric material interfaces do not change conductivity: it is zero outside
metal, with one common positive value inside. Relative permeability is uniform
throughout the entire magnetic domain. Mesh and boundary convergence are separate.

`volume_line(volume, frequency, materials=..., conductivity=..., length=...,
z_ref=50, relative_permeability=1, keep_fields=False)` is the direct mesh API.
The `MeshedConductors.layer_triangles` mapping must identify the disjoint
nonmetal triangle sets for every material; any unlisted nonmetal triangles are
vacuum. `materials` must specify every mapped layer exactly once, using the
supported [dielectric models](dielectrics.md). An explicit mesh-level caller
owns the region classification; the library does not infer a material from
coordinates in this path. Fractional/boolean region indices are rejected before
snapshotting instead of silently truncating them to integers.

For each requested frequency, C* is the complex electrostatic capacitance of
the dielectric submesh. C=Re C*, G=−ω Im C* for exp(+jωt). The network uses the
volume-current R and **total L once**, without adding µεC0⁻¹ again. The conductor
skin-depth, good-conductor, current, energy and reciprocity gates remain active.
The DC network retains finite series resistance. There is no implicit ideal
through, surface/volume switching or roughness extrapolation.

## Versioned document and output

All keys are exact: unknown/missing fields, duplicate JSON keys, nonfinite
numbers, booleans as numbers, and unknown schema versions are rejected.

| Top-level key | Contract |
|---|---|
| `schema` | Exactly `sipi.volume-line/1` |
| `cross_section` | Existing `sipi.cross-section/1` or `/2`, length unit m; original version preserved, including rectangular v2. Its `mesh` must be empty because dielectric-only meshing controls do not apply here. Every trace needs positive thickness. |
| `mesh` | All six keys: `ground_thickness`, `padding`, `metal_size`, `far_size`, `grade`, `min_angle`. Positive finite lengths/angle, grade>=0, far_size>=metal_size, angle<34. |
| `materials` | Layer name → versioned dielectric model. Omitted layer entries resolve to the section's constant eps_r/tan_delta and are saved explicitly. Unknown names and table extrapolation/DC errors fail before meshing. |
| `conductor` | Exactly positive `conductivity` (S/m) and `relative_permeability` (uniform); no roughness parameters. |
| `frequency_hz` | Nonempty, nonnegative, strictly increasing Hz array |
| `length_m`, `reference_ohms` | Nonnegative length and positive scalar real reference impedance |

`dumps()` produces input JSON only; `loads()` and `from_dict()` use the same
validation. No file/network I/O occurs. Caller mutation of a dictionary or a
returned section cannot change the saved document. `analyze(keep_fields=True)`
retains Az/J via the conductor result; the default avoids those large arrays.
Inputs can be valid before meshing but still fail the actual metal-edge/skin
resolution gate after meshing; that failure is not returned as a success.

`VolumeLineResult` contains `conductor`, complex `(F,N,N)` `C_complex`, and
`network`. Properties `frequency`, `names`, `R`, `L`, `G`, `C` use the same
signal order. `input_json` holds the resolved document when analyzed through
`VolumeLineDocument`, and is None for the direct API. C* is copied/read-only;
the conductor result keeps its own immutable snapshots and diagnostics.
Directly constructing a result is not a validation certificate. Port order and
Touchstone export follow the [network contract](network.md).

## Validation and limitations

Tests: `tests/sipi/test_volume_line.py`, plus the conductor-volume/mesh tests.
Python 3.12.14, NumPy 2.5.4, SciPy 1.18.1 and test-only scikit-fem 12.0.2.
No new runtime dependency is introduced.

| Check | Acceptance and measured result |
|---|---|
| Finite coax, a=.5/b=1.5/c=2 mm | C*=2πε*/ln(b/a); radial 8/16/32 with 256 angular cells gives decreasing error, finest <.1%. Uniform Debye scaling C*=ε*(f)C0 agrees within 1e-10. |
| Complex electric solve on the same coax mesh | Independently assembled scikit-fem complex P1 Dirichlet solve: C* relative difference 4.00e-15, criterion 1e-9. Same-mesh agreement alone does not establish mesh accuracy. |
| Identical series model | R/L match standalone volume impedance within 1e-12; total L is not double-counted. |
| Layer boundary cutting a taper | Exact dielectric polygon area within 1e-10; electrode coordinate sets preserved exactly after removing metal triangles. |
| Finite-box microstrip, metal 50→25→12.5 µm, exterior sizes .5→.25→.125 mm, grade .2→.1→.05 | C change 1.3478%→.53066%; G 1.7727%→.75816%. Finest changes meet the original 1% criterion. The coarser pair did not. |
| Finest microstrip, padding 2→4 mm | C change .24126%, G .04903%, both <2%; finite-boundary error remains separate. |
| Closed grounded box with Debye dielectric | C* agrees with the existing dielectric solver on a different refined mesh within 1%. This comparison applies to the closed-box geometry, not open infinite grounds. |
| JSON and networks | R/L/G/C round-trip within 1e-12 and S within 1e-10; one geometric mesh per analysis; rectangular v1/v2 and taper v2 preserved; asymmetric two-signal port order, reciprocity/passivity within 1e-10. |

The initial coax mesh (8 radial, 128 angular) missed the .1% criterion at .22878%.
It was refined, with no tolerance relaxation. The finite-box material definition
and electric boundary differ from older open-box extraction, so their values
must not be silently interchanged. This document is separate from surface-model
input contracts. Nonuniform conductor conductivity/permeability, conductor
roughness, radiation, arbitrary mask contours, and 3D transitions are not
implemented. Material fits still need independent measured validation.
