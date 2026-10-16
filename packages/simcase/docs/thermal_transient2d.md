# Transient heat: Python and document interface boundaries

[한국어](locales/ko/pages/thermal_transient2d.md)

## Implementation boundary

At source snapshot `d5d2f0886e49df0e1a96731270602340329f9192`,
transient heat is available through the explicit Python engine API
`galerkin.transient_heat.solve_transient_heat`. The document runner accepts
`em.modes2d`, `em.cavity3d` and `thermal.steady2d`; it does not yet accept
a transient heat document. A Python engine result is not a document-runner
result or a supported saved-document format.

This page records the boundaries that a transient document adapter must preserve.
It does not specify an accepted JSON schema, public adapter result class,
CLI example name or saved format identifier. Consult the implementation and
its exact validation evidence before using a document interface. No numerical,
installed-distribution or platform pass follows from this document.

| Interface | Available at the named snapshot | Boundary |
|---|---|---|
| Explicit transient Python engine | Fixed conforming P1 triangles, consistent mass, backward Euler | Constant homogeneous isotropic conductivity and volumetric heat capacity; explicit requested times |
| Headless JSON / API / CLI | Steady rectangular heat documents only | A transient solver import does not enable a transient study in the runner |
| Saved heat documents | Existing steady result contract | Do not interpret a steady temperature array as a time history |
| Studio | No thermal editor or renderer | Optical views must not display thermal histories as optical results |
| Thermal–mechanical workflow | Separate steady one-way contract | No automatic transient coupling |

The engine [usage contract](https://github.com/fieldalgo/openphysics/blob/main/packages/galerkin/docs/transient_heat.md),
[producer validation](https://github.com/fieldalgo/openphysics/blob/main/packages/galerkin/docs/transient_heat_validation.md)
and [independent acceptance](https://github.com/fieldalgo/openphysics/blob/main/packages/galerkin/docs/transient_heat_independent_validation.md)
are in a separate package and require network access. They preserve historical
submission evidence separately from later exact-commit validation. The existing
[steady document contract](thermal_steady2d.md) is not a transient schema.

## Units and numerical invariants

The standalone engine consumes explicit SI values. A document adapter must
declare and validate any supported input-unit conversions before constructing
the mesh; it must not infer units from numerical magnitudes or file names.

| Quantity | Engine contract |
|---|---|
| Coordinates | m |
| Requested time and time increments | s; finite strictly increasing times and positive finite increments |
| Initial and prescribed temperature | K; finite real values |
| Conductivity | Positive constant k, W/(m K) |
| Volumetric heat capacity | Positive constant c, J/(m³ K) |
| Volumetric source | Q, W/m³; signed heating or cooling |
| Element heat flux | q=-k grad T, W/m² |
| Nodal source load, storage rate, residual and reaction | W/m of out-of-plane depth |
| Heat content | H=1ᵀMT, J/m |
| Quadratic functional | V=.5TᵀMT, J K/m; not stored heat |

The linear mathematical engine accepts finite negative Kelvin and does not
clamp computed values or promise a discrete maximum principle. This does not
certify physical material validity. The separate heat-to-mechanics transfer
still rejects negative Kelvin. An adapter must expose its own input policy
explicitly and must not silently change the engine solution.

Initial values and the first prescribed boundary samples must satisfy the
engine's agreement tolerance. Accepted initial values are retained exactly;
there is no projection or overwrite. Fully insulated transient components are
well posed through the mass/time term; do not import the steady solver's
Dirichlet-anchor requirement.

## Initial frame and step histories

N is the number of nodes, M the number of triangles and Nt the requested times.
An adapter must preserve the distinction between values at every requested
time and rates on the Nt-1 evolution steps.

| Engine array | Shape | Interpretation |
|---|---|---|
| time_s | (Nt,) | Requested times, including the initial time |
| temperature_k | (Nt,N) | Nodal temperatures, including the exact initial frame |
| heat_flux_w_m2 | (Nt,M,2) | Element flux, including the initial frame |
| source_load_w_per_m | (Nt,N) | Assembled source; initial f0 is diagnostic |
| reaction_w_per_m / residual_w_per_m / storage_rate_w_per_m | (Nt-1,N) | Step quantities; no invented initial reaction or rate |
| heat_content_j_per_m / quadratic_functional_jk_per_m | (Nt,) | Distinct H and V histories |
| nodes_m / triangles | (N,2) / (M,3) | Geometry and connectivity required to locate fields |

Positive prescribed-temperature reaction injects heat. On each evolution step,
outward thermostat heat is minus the sum of those reactions:

```text
(H_n-H_n-1)/dt_n = sum(source_load_n) + sum(reaction_n)
outward_D,n = -sum(reaction_n)
           = sum(source_load_n) - sum(storage_rate_n)
```

The weak nodal thermostat rate is distinct from a direct normal integral of
the recovered element flux. Multiplying per-depth rates and H by a physical
thickness in m gives W and J; temperature and flux are not multiplied.

## Execution, saving and evidence

Use the engine example through the Python interpreter of the active environment.
Run the following Python snippet from the repository root:

```python
import os
from pathlib import Path
import subprocess
import sys

env = os.environ.copy()
for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    env[name] = "1"
subprocess.run(
    [sys.executable, "packages/galerkin/examples/transient_heat_convergence.py"],
    cwd=Path.cwd(), env=env, check=True)
```

This runs the existing full engine convergence example, not a transient
headless CLI. It can require substantial memory and computation. A reproduction
command is not evidence that it was executed on any platform.

The engine retains full histories with O(Nt*(N+M)) storage, plus sparse factors,
temporary arrays and final copies. A document serializer may require additional
memory; no streaming, restart or memory bound should be inferred.

For any saved-document interface, the field layout, units, JSON-finite values,
non-object arrays and safe loading without pickle must be specified and tested.
Fresh-output ownership, replacement protection and cleanup must be verified on
the actual adapter. Existing steady save evidence is not proof of a new
transient save implementation. Keep exclusive control of owned output paths
until saving and cleanup finish; hostile filesystem races and atomic rollback
are outside the existing ownership contract.

## Scope and validation boundaries

A rectangular document subset must not imply arbitrary-mesh serialization,
transient flux/Robin boundaries, radiation, changing or temperature-dependent
materials, adaptive stepping, a thermal renderer, persistence/restart of the
solver, or automatic coupling. New document validation must preserve the
existing engine's frozen temporal, spatial, quadrature and separation gates.

Record source checks, isolated installed consumers, archive bytes/links,
numerical gates and OS-sensitive save tests separately. Use actual exits,
failures and skips. Linux success, metadata classifiers and universal wheels
are not Windows/macOS acceptance. Inclusion in a manifest is an implemented
packaging rule, not proof that a built archive or installed consumer passed.
