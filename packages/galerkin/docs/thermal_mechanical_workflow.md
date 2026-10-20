# Explicit steady heat → thermoelastic mechanics

[한국어](locales/ko/pages/thermal_mechanical_workflow.md)

This Python-only workflow calls the existing heat solver, freezes its nodal
Kelvin field, then calls the existing prescribed-temperature mechanical stage
on one isolated reference mesh. It is steady, one-way and small-strain; it is
not a thermodynamically coupled or transient solver. Import the submodule
explicitly. No top-level export, model schema, CLI, Studio, persistence, Robin,
flux, mechanical traction, remeshing, temperature-dependent material or 3D
feature is added. k, E, nu, alpha and a constant heat source may each be one
scalar or a `{region name: value}` mapping; the per-region contract, manifest
record (`{'kind': 'per_region', ...}` for the source, sorted dictionaries for
materials) and its coupled composite-cylinder validation are in
[multimaterial](multimaterial.md).

## API and SI boundary

```python
from galerkin.mesh import rectangle_mesh
from galerkin.thermal_mechanical import solve_steady_thermoelasticity

n = 8
mesh = rectangle_mesh(1., 1., n, n)
thermal = {int(i): 303.15 for i in mesh.boundary['left']}
thermal.update({int(i): 323.15 for i in mesh.boundary['right']})
result = solve_steady_thermoelasticity(
    mesh, units={'length': 'm', 'temperature': 'K'},
    conductivity=10., thermal_dirichlet=thermal, heat_source=0.,
    young_modulus=70e9, poisson_ratio=.3, plane='strain',
    thermal_expansion_per_k=12e-6, reference_temperature_k=293.15,
    mechanical_dirichlet={(0, 0): 0., (0, 1): 0., (n, 1): 0.},
    body_force=(0., 0.))
```

Full signature:

```python
solve_steady_thermoelasticity(
    mesh, *, units, conductivity, thermal_dirichlet, heat_source=0.0,
    young_modulus, poisson_ratio, plane, thermal_expansion_per_k,
    reference_temperature_k, mechanical_dirichlet, body_force=(0., 0.))
```

| Input | Meaning and validation |
| --- | --- |
| mesh | galerkin Mesh, nodes (N,2) m, integer triangles (M,3); reference geometry |
| units | exactly `{'length':'m','temperature':'K'}`; no extra keys or inferred conversion |
| conductivity | finite constant k>0, W/(m K), or `{region name: k}` over `mesh.region_names` |
| thermal_dirichlet | exterior integer node → finite absolute K; remainder insulated |
| heat_source | finite signed scalar, `{region name: Q}`, or callback (Q,2) metre points → (Q,) W/m³ |
| young_modulus / poisson_ratio | finite E>0 Pa / -1<nu<0.5; each a scalar or `{region name: value}` |
| plane | explicitly `stress` or `strain` |
| thermal_expansion_per_k | finite signed **linear** alpha, 1/K; zero/negative allowed; scalar or `{region name: alpha}` |
| reference_temperature_k | required finite nonnegative absolute K, no implicit reference |
| mechanical_dirichlet | exterior (node,component) → displacement m; component0=x,1=y |
| body_force | finite (2,) or callback (Q,2) metre points → (Q,2) N/m³ |

Each heat component needs a Dirichlet anchor; each mechanical component needs
three independent rigid-mode constraints. Remaining mechanical components have
zero **total thermoelastic natural traction**, not zero elastic-only traction.
Thermal tags do not imply mechanical fixing. No springs or fallback supports
are added. Existing geometry, material, residual and constraint checks remain.
Near-incompressible plane-strain P1 locking remains a limitation.

The caller converts mm/um descriptions to metres before entry, including body
force coordinates and displacement supports. Other numeric inputs retain the
fixed SI units above. False metre/K labels cannot be detected from arrays:
a supplied20 is20K, not automatically Celsius. A caller-side Mesh constructor
may already have cast fractional indices or repaired orientation; lost history
cannot be recovered. The workflow checks its copied raw arrays before its own
constructor can cast indices or flip triangles: fractional/boolean connectivity,
nonfinite coordinates and nonpositive orientation are rejected, not repaired.
Existing component validators then reject nonconformity, overlap and bad supports.

## Isolation, transfer and lifetime

Nodes, connectivity, boundary arrays, region metadata, constant materials,
constant body force and support maps are copied. Both stages use the **same
private Mesh object**, preserving node/element order and undeformed coordinates.
Detected private mesh/boundary/region mutation during execution fails the stage.
Changing the caller's original arrays from a callback cannot alter those copies.
Callbacks themselves remain external mutable code; their behavior and side
effects are not authenticated, copied, made pure or made thread safe.

After heat succeeds, its temperature must be a finite real (N,) array. Negative
Kelvin is an explicit `transfer` error reporting minimum/node. Nonfinite entries
report a node; shape/type errors identify the expected contract. The heat solver
mathematically permits negative temperatures, but this workflow's snapshot domain
does not. There is no clamp, absolute value, hidden offset, Tref shift or tolerance
exemption. Mechanics is not called after a heat/transfer failure.

The snapshot is an exact nodal-P1 copy with canonical little-endian float64/int64,
immutable bytes backing, schema1, m/K and reproducible framed FNV-1a64 checksums.
It binds exact coordinates/connectivity/node and element order; equivalent
copied mesh arrays work, reordered/scaled/remeshed arrays do not. No interpolation
or automatic permutation is performed. Boundary/configuration data are separately
recorded in the manifest rather than certified by the snapshot mesh checksum.

`heat.temperature` can be changed after return without changing the already
frozen snapshot. Re-freezing is an explicit new transfer. Component result arrays
and the owned reference Mesh retain their existing mutability. The aggregate does
not revalidate them whenever a property is read; a completed execution manifest
is **not post-return integrity certification**. The immutable snapshot survives
its original inputs. Passing a subsequently changed mesh to the mechanical API
is checked by that API, but merely editing the returned Mesh does not retroactively
change or recertify the completed run.

## Aggregate and canonical manifest

`SteadyThermoelasticResult` has:

| Member | Contract |
| --- | --- |
| reference_mesh | isolated owned Mesh; SI reference nodes, mutable after return |
| heat | existing SteadyHeatResult; temperature/flux/load/reaction/residual |
| temperature_snapshot | immutable TemperatureSnapshot actually passed to mechanics |
| mechanics | existing ThermoelasticResult; fields, separate loads, reactions, physical energy |
| manifest_json | immutable canonical JSON string |
| manifest | freshly decoded dictionary on every access |

```python
metadata = result.manifest
metadata['units']['length'] = 'mm'
assert result.manifest['units']['length'] == 'm'
assert result.mechanics.temperature_snapshot is result.temperature_snapshot
```

JSON uses sorted keys, compact separators and finite numbers. Schema is
`galerkin-steady-thermoelasticity-v1`. It records declared SI units,
materials (a float, or a `{region name: float}` dictionary with sorted keys),
reference/plane, sorted supports, sources/body force (`{'kind': 'constant',
'value': ...}`, `{'kind': 'per_region', 'value': {...}}` for a region source, or
callable labels), mesh counts/boundary/region metadata, mesh/temperature/snapshot
hashes, exact-copy transfer policy, completed stage statuses and quantity units.
No moving Git revision is asserted as the whole runtime version; exact source
manifests belong in external validation evidence.

Origin is `workflow_owned_heat_call`: this invocation called the heat component.
Authentication is `not_certified`. Callable inputs are `caller_provided`,
`fingerprinted: false`; no repr/address or fabricated code fingerprint is used.
Checksums are reproducibility identifiers, not signatures or proof of physical
units, external source or callback purity. The workflow does not accept a manual
heat-result shortcut and never upgrades an externally supplied field to certified
heat origin. Post-return mutable arrays may no longer match recorded hashes.

## Stage errors and failure boundary

`WorkflowStageError` is a ValueError with `.stage` and the original exception in
`.__cause__`. Stages are `input`, `heat`, `transfer`, `mechanics`, `manifest`.
Input checks/copies precede heat. Component heat validation/solve failure is heat;
freeze/domain failure is transfer; component mechanical validation/solve failure
is mechanics; canonical serialization failure is manifest. Detected private mesh
mutation is labelled at the component boundary where it was observed.

```python
from galerkin.thermal_mechanical import WorkflowStageError
try:
    solve_steady_thermoelasticity(mesh, **parameters)
except WorkflowStageError as error:
    print(error.stage, str(error), type(error.__cause__).__name__)
```

Here `parameters` denotes a complete argument dictionary from the signature.
No successful aggregate is returned after any stage fails. This API introduces
no partial-result, save, cleanup or persistence contract. Ordinary Python call
binding errors (missing/unknown arguments) occur before pipeline execution;
KeyboardInterrupt/SystemExit are not converted into workflow failures.

## Physics and separate accounting

Heat solves `-div(k grad T)=Q`; q=-k grad T. With heat reaction rT on fixed
nodes, `sum(load)+sum(reaction)=0`, signed net outward heat=-sum(reaction).
Heat nodal load/reaction/residual are W/m of depth; flux is W/m².

For mechanics let a=alpha(T-Tref), e=(exx,eyy,gamma_xy), gamma_xy=2epsilon_xy,
m=(1,1,0), mu=E/[2(1+nu)], lambda=E nu/[(1+nu)(1-2nu)]. The parent3D law is
sigma=2mu(epsilon-aI)+lambda tr(epsilon-aI)I. In-plane stress is D e-q m,
with q=E a/(1-nu) PS and E a/(1-2nu) PE. PS sigma_zz=0 and
`epsilon_zz=((1+nu)a-nu(exx+eyy))/(1-nu)`; PE epsilon_zz=0 and
`sigma_zz=lambda(exx+eyy)-E a/(1-2nu)`.

Thermal weak load is positive `g=integral B^T q m dA`, and is not a physical
external body force. A body-force-only replacement loses boundary terms and
uniform free expansion. Physical thermal strain remains aI in3D, including z;
PE effective (1+nu)a is only a reduced load representation.

Total strain is cell-constant; thermal/elastic strain, stress, sigma_zz and
epsilon_zz are centroid samples. Stress generally varies linearly in a cell
because T is P1. Use the snapshot's P1 T and cell displacement strain to recover
pointwise stress; do not interpret centroid samples as the complete constant
field. Plane stress is a local reduction, not reconstructed3D warping.

Mechanical external load, thermal-equivalent load, reaction and residual are
separate N/m of depth. `load_total` is external+thermal. Reaction equals
Ku-f-g on fixed components, zero on free; full residual retains all components.
Physical elastic energy U is J/m, from original3D elastic energy:

```text
PS: psi=.5(e-a m)^T Dps(e-a m)
PE: psi=.5(e-(1+nu)a m)^T Dpe(e-(1+nu)a m)+.5 E a²
U=.5 u^T K u-u^T g+CT
u^T K u=u^T(f+g+r)
2U=u^T f+u_D^T r_D-u^T g+2CT
```

CT is integral E a²/(1-nu) dA PS or1.5 E a²/(1-2nu) dA PE.
P1 temperature requires degree-two exact energy quadrature, not squared centroid
T. Nonzero prescribed displacement requires support work. These are endpoint
mechanical identities at fixed T, not total thermodynamic balance or heating-path
work. `T^T KT T` is W K/m, not elastic energy or stored heat. Multiply per-depth
forces/energy by physical thickness only in an explicit external operation.

## Reproduction and predeclared numerical gates

From an exact source checkout root with existing dependencies:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
PYTHONPATH=packages/galerkin \
python packages/galerkin/examples/thermal_mechanical_workflow.py

OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python -m pytest -q tests/galerkin/test_thermal_mechanical_workflow.py \
  tests/galerkin/test_thermal_mechanical_workflow_physics.py
```

The example uses linear conduction T=Tref+10+20x, Q=0, k=10 on a1m square.
Compatible continuum free expansion has
vx=alpha10x+.5alpha20(x²-y²), vy=alpha10y+alpha20xy;
PS u=v, PE u=(1+nu)v. Quadratic displacement has FE error; linear heat is P1-exact.
Uniform20K heating gives PS u=a(x,y), zero stress/U; PE u=(1+nu)a(x,y),
sigma_zz=-Ea and U=.5 E a² area. Full exterior fixing instead gives -24MPa PS
or -42MPa PE normal stress for E70GPa, nu.3, alpha12e-6/K.

Producer numerical tests use these cases and sine MMS T=Tref+20sin(pi x)sin(pi y),
u=(1e-4,.6e-4)sin(pi x)sin(pi y), k10/E70GPa/nu.3/alpha12e-6 on a1m square.
Heat source comes from -k Laplacian(T); mechanical body force comes from
-div(total analytic stress), with both displacement components fixed on the
exterior for the sine case. Original3D tensor law and independent quadrature are
used, without production constitutive/assembly helpers or refsol imports.

Fixed n=8/16/32/64, **all three adjacent intervals**, both planes:

- L2 temperature/displacement order>=1.8; gradient/strain/full3D stress including
  sigma_zz/mechanical energy-norm order>=.9. Exact-zero linear heat/transfer uses
  exactness checks, not fabricated slopes.
- Separately compare numerical heat T_h, analytic nodal I_h T, u_h[T_h] and
  u_h[I_h T] to analytic fields. Snapshot nodal transfer is exact array equality.
  Heat-induced mechanical change obeys its elastic dual-norm bound; norm errors
  do not add as scalar magnitudes even when vector errors decompose.
- Uniform normalized fields/side reactions/physical U<=1e-10; independent weak
  loads, original3D stress/U and support-work audit<=1e-10; heat balance<=1e-10,
  mechanical force/moment<=1e-9. Correctly converted units agree<=1e-9.
- Norm quadrature8x8/10x10 differs<1% of measured error; analytic physical U
 12x12/16x16 differs<=1e-8 fixed energy scale. Physical U error decreases
  monotonically to<=.02 normalized; no invented raw-energy order2 gate.

Smooth convex-square P1 theory motivates first-order gradients and second-order
L2 convergence; thresholds are not fitted after observations. Tests preserve
component gates and include copy/stale/invalid/component supports, cooling,
negative/zero alpha, common reference shift, side reactions, nonzero support work
and actual direct-math wrong-PE/centroid-energy negative controls. These producer
checks are separate from independent acceptance and release/installed evidence.
No Windows, Actions or performance success is implied by the guide or by an
example. The guide and examples are not shipped in the distributions.
