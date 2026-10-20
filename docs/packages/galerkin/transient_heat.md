# Transient heat on a fixed P1 mesh

[전체 한국어판](../../locales/ko/pages/packages/galerkin/transient_heat.md) · [Validation](transient_heat_validation.md)

**At a glance**

- **What it does:** `galerkin.transient_heat.solve_transient_heat` advances 2D heat conduction, c·dT/dt − div(k·grad T) = Q, on a fixed conforming P1 triangle mesh with consistent mass and backward Euler. Inputs are constant isotropic k [W/(m K)] and c [J/(m³ K)], a source Q [W/m³], explicit times [s], an initial field [K] and fixed Dirichlet nodes with time-dependent temperatures; other boundaries are insulated.
- **Limits:** no prescribed flux or Robin boundary, restart or automatic heat-to-mechanics coupling. Finite negative Kelvin is not clamped, and no discrete maximum principle is promised.
- **Validation:** the [validation contract](transient_heat_validation.md) and [independent acceptance](transient_heat_independent_validation.md) fix backward-Euler order 0.9–1.1 against the exact discrete eigenmode product, and temperature L2 order ≥ 1.8 and flux L2 order ≥ 0.9 on a manufactured sine solution. The historical notes below are kept as recorded; for a specific commit, see its CI run.

## Current checkout and evidence

This page describes the implementation in this checkout. Named historical snapshots retain their original results and limitations. For validation of another commit, inspect that commit's CI logs and artifacts.

**Historical initial submission (d21): source and static review only.** Python parsing,
imports, compilation and collection had not been executed at that submission.
That historical status is retained; no earlier numerical pass is inferred.

**Bounded follow-up, 2026-10-16:** exact code snapshots
d21e083d9723eec71ab5e32777ecd331d75cd981 and
b2f420f4d540503ad3711bdab996e12dcbce9e9d each compiled all five new Python
files and imported the engine/reference submodules successfully. Targeted
collect-only found 70 identical node IDs per snapshot: 58 producer cases and
12 reference cases. **Collected does not mean passed: no test body ran.**
A fresh, Git-blob-verified 38-file source subset and fresh venv used Python3.12.14,
pytest9.1.1, NumPy2.5.4 and SciPy1.18.1 with existing runtime packages; imports
were from those exact source snapshots, not an installed-wheel proof.
This did not recover an old checkout, venv or historical execution records.

**Actual small-body follow-up, 2026-10-16:** exact
b2f420f4d540503ad3711bdab996e12dcbce9e9d ran the two targeted files once:
**70 passed (58 producer + 12 reference), exit0, no failures/errors/skips**.
This is distinct from the earlier 70 collected. The original stdout, stderr,
JUnit bytes, hashes, resource preflight and module origins were preserved.
The same Python3.12.14/pytest9.1.1/NumPy2.5.4/SciPy1.18.1 source environment
used BLAS/OMP/MKL1; no test count or tolerance was reduced. No solver fix or
test rerun was needed. The d21 snapshot did not separately run test bodies.

At that historical checkpoint, the fixed temporal/PDE spatial/5% separation gates,
complete source regression, installed sdist/wheel proof, independent acceptance and
platform tests were unexecuted. The 70 small controls are not complete physical
acceptance. Use the exact current CI evidence to assess the present checkout;
the commands below define reproduction, not a new pass result.

## Explicit submodule and minimal use

```python
import numpy as np
from galerkin.mesh import rectangle_mesh
from galerkin.transient_heat import solve_transient_heat

mesh = rectangle_mesh(1., 1., 4, 4)  # metres
result = solve_transient_heat(
    mesh, conductivity=2.5, volumetric_heat_capacity=4.0,
    time_s=np.array([0., .1, .3]),
    initial_temperature_k=np.full(mesh.num_nodes, 300.),
    dirichlet={}, heat_source=8.0)
outward_dirichlet_w_per_m = -result.reaction_w_per_m.sum(axis=1)
```

The mathematical target in this insulated constant-source example is
T=300+(8/4)*t K, with zero flux and no thermostat reaction. This is an exact
reference expectation, **not an observed execution result**.

The exact keyword-only API is:

```text
solve_transient_heat(
    mesh, *, conductivity, volumetric_heat_capacity,
    time_s, initial_temperature_k, dirichlet, heat_source=0.0)
```

Import this submodule explicitly; no automatic top-level export is added.
The model is c*dT/dt-div(k*grad T)=Q, constant isotropic k>0, c>0 (one
material, or piecewise constant on named regions as described in
[multimaterial](multimaterial.md); the gates on this page use one material), fixed conforming CCW scalar P1 triangles, consistent mass and backward
Euler. Unselected natural boundaries are insulated. A fully insulated or
disconnected component needs no Dirichlet anchor: M/dt+K is positive definite
on valid used-node geometry. Do not copy a steady mandatory-anchor rule.

## Inputs and units

| Input | Contract |
|---|---|
| mesh | galerkin Mesh, finite coordinates in m; used-node, conforming, nonoverlapping manifold CCW triangles |
| conductivity | finite positive scalar k, W/(m K), or `{region name: k}` |
| volumetric_heat_capacity | finite positive scalar c, J/(m³ K), or `{region name: c}` |
| time_s | finite real 1D seconds, at least two, nonnegative, strictly increasing with finite positive differences |
| initial_temperature_k | finite real exactly (N,) K at time_s[0] |
| dirichlet | fixed exterior integer node -> scalar K or callback(time_s)->scalar K |
| heat_source | finite scalar W/m³, `{region name: Q}`, or callback(points_m,time_s)->exactly (Q,) W/m³ |

A source callback receives (Q,2) metre coordinates and one scalar second value.
There is no scalar broadcasting for callback outputs. Reject bool, complex,
nonfinite values, malformed shapes and bool/noninteger/interior/out-of-range
Dirichlet IDs. Mixed Python sequences are checked for booleans before dtype
coercion. Already converted floating arrays do not reveal their construction
history. There is no coordinate, time, Celsius or material-unit inference.

Finite negative K is permitted by this constant-capacity **linear mathematical
API**, as in standalone steady heat. This is not physical temperature/material
validity certification. Signed sources/sinks are allowed. Consistent-mass
evolution need not preserve nonnegative nodes; no clamping, mass lumping or
discrete maximum principle is promised. The separate heat-to-mechanics snapshot
policy still rejects negative K; this module does not alter that transfer API.

No Robin/outward-flux/radiation input, temperature-dependent or continuously varying material, changing mesh,
adaptive time step, Crank–Nicolson, mechanics, schema/CLI/Studio, persistence or
restart API is included. Unexpected keywords are not silently ignored.

## Initial agreement and callback lifecycle

At each prescribed node, initial and sampled t0 boundary data must agree within:

```text
32*eps*max(1 K, abs(initial_i), abs(d_i))
```

No initial projection or overwrite is performed, even within the accepted
roundoff bound. The first old-state mass term uses the actual initial field.
Nonzero start time is allowed: initial data belong to the first supplied time.

Source and boundary callbacks must be pure and deterministic. Source is sampled
at t0 for validation and retained f0 diagnostics. It is then sampled once at
each requested time and BE uses the **right-endpoint** load. Each prescribed
boundary callback is also sampled once per time. No point-batch or node
evaluation-order guarantee is made. No initial rate or reaction is invented.

Geometry/connectivity, time, initial data, scalar inputs and the fixed
Dirichlet selection are copied/captured before callbacks. No concurrent caller
mutation during capture/solve is supported. Callback coordinates are copies;
later caller changes do not change returned histories or captured geometry.

The solve is eager and all-or-error. Structural input errors raise ValueError.
Preparation, sampling, solve, derived-history and final-copy failures are
chained as TransientHeatStepError, a ValueError subclass with time_index and
time_s; __cause__ preserves the original exception. Preparation is index0;
final-copy failure uses the last index/time. No successful partial result is
returned, and the accepted previous internal state is not replaced by a failed
trial. External callback side effects are not rolled back.

## Discretization and moving temperatures

```text
M_e = c*A/12 * [[2,1,1],[1,2,1],[1,1,2]]
K_ij = integral k*grad(N_i).grad(N_j)
f_i(t) = integral N_i*Q(x,t)
r_n = M*(T_n-T_n-1)/h_n + K*T_n - f_n

(M_FF/h_n+K_FF)*T_F,n =
    f_F,n + M_FF*T_F,n-1/h_n
    - K_FC*d_n - M_FC*(d_n-d_n-1)/h_n
```

Both old and new M_FC terms are required. The implementation includes the full
old M*T and subtracts the full new A_FC*d; it does not solve a sequence of
steady problems. Four-point boundary or Robin integration from steady heat is
not used here. Spatial source integration uses the existing 6x6 Duffy rule.

Each geometric component uses one **time-independent** initial offset for
subtractions/derivatives. Its stiffness image is mathematically zero and its
mass derivative is zero. The offset is never reset at each time. Sparse
factorization is recomputed for each requested dt; no dt-independent reuse or
performance claim is made. Derived floating overflow or failed residual/balance
checks raises rather than returning a successful invalid history.

## Result arrays, lifetime and memory

TransientHeatResult has the following owned read-only copied arrays. N is
nodes, M triangles, Nt requested times and D unique sorted prescribed nodes.

| Field | Shape | Meaning / units |
|---|---|---|
| time_s | (Nt,) | requested seconds |
| temperature_k | (Nt,N) | nodal K, including exact copied initial field |
| heat_flux_w_m2 | (Nt,M,2) | element q=-k*grad(P1 T), W/m², including t0 |
| source_load_w_per_m | (Nt,N) | nodal f, W/m; f0 is diagnostic only |
| reaction_w_per_m | (Nt-1,N) | original residual at fixed nodes, zero at free, W/m |
| residual_w_per_m | (Nt-1,N) | full original BE residual at all nodes, W/m |
| storage_rate_w_per_m | (Nt-1,N) | M*(T_n-T_n-1)/h_n, W/m |
| heat_content_j_per_m | (Nt,) | H=1ᵀ M T, J/m |
| quadratic_functional_jk_per_m | (Nt,) | V=.5 Tᵀ M T, J K/m |
| dirichlet_node_ids | (D,) | sorted unique fixed node indices |
| dirichlet_temperatures_k | (Nt,D) | sampled prescribed K |
| nodes_m / triangles | (N,2) / (M,3) | copied SI geometry/connectivity/order |

The two metadata fields conductivity_w_mk and
volumetric_heat_capacity_j_m3k record the supplied constants (a float, or a
`{region name: float}` copy for per-region input). No unit,
provenance, hash or source-origin authentication is claimed. Read-only arrays
and a frozen container are not cryptographic protection against hostile code.

Histories alone use O(Nt*(N+M)) memory; sparse systems/factors and temporary
copies add memory, including at final result construction. No hidden
downsampling, streaming or restart is implemented. A large request may fail
allocation; no partial successful history is returned.

## Heat accounting and quadratic functional

All nodal rates are per unit out-of-plane depth W/m, not total W. Multiply
rates and H by explicit physical thickness in m to obtain W and J. Do not
multiply temperatures or fluxes. Mechanical N/m is not a thermal rate.

```text
H_n = 1^T*M*T_n                         [J/m]
V_n = .5*T_n^T*M*T_n                   [J K/m]
storage_n = M*(T_n-T_n-1)/h_n           [W/m]
reaction_n = residual_n on fixed DOFs  [W/m]
outward_D,n = -sum(reaction_n)
(H_n-H_n-1)/h_n = sum(f_n)+sum(reaction_n)
outward_D,n = sum(f_n)-sum(storage_n)
```

Positive reaction injects heat. H is the linear constant-capacity sensible
content with a chosen zero at0K, not a universal absolute enthalpy model.
V is a quadratic functional, **not stored heat**. For homogeneous zero
Dirichlet or fully insulated unforced evolution, the BE quadratic identity
implies non-growing V. With sources or nonzero/moving boundary temperatures,
do not assert monotonic H/V or a maximum principle. Recovered cell flux is not
H(div)-conforming: its direct boundary normal integral is generally different
from a finite-mesh weak thermostat reaction and must be reported separately.

See the [validation guide](transient_heat_validation.md) for the fixed
gates, independent algebra/reference boundaries and reproduction.

## Separate headless document adapter

Rectangular `thermal.transient2d` JSON/API/CLI and saved histories are provided by a separate simcase adapter. Its [input, result and save contract](../simcase/thermal_transient2d.md) is in the simcase documentation. This engine function's arbitrary callbacks/mesh support are not the serialized document scope. Documents use uniform/affine initial fields and side-constant/requested-time samples while retaining initial agreement, no projection and finite K/no clamp. No Studio, restart, transient flux/Robin or automatic coupling is added. Engine acceptance is distinct from headless source/installed/save/CI acceptance.

## Bounded spatial-residual refinement

The initial component state offset remains fixed for the entire solve. Only
stiffness and gradient evaluation subtract each component's current representative
value. This does not redefine temperature, its history or the mass derivative.
For component constants E, K E=0 in exact arithmetic, so the original
backward-Euler equation and both old/new boundary mass terms are preserved.
A rounded assembled K need not satisfy K E=0 bit-for-bit; this is not a claim
that the rounded pencil is unchanged.

Each step with free degrees of freedom retains its original matrix and LU, evaluates six physical residuals
and performs five free-DOF corrections using that same LU. Prescribed-node
corrections are zero. The best physical-residual iterate is selected before the
original free-residual and component-balance guards, with unchanged tolerances.
This is not an analytic mean replacement, projection or new acceptance gate.
A failed final guard still raises. The bounded loop adds up to five triangular
solves and additional matrix-vector evaluations per step, without an additional
factorization; it guarantees neither convergence nor performance.

New producer tests in `test_transient_heat_tiny_domain.py` and
`test_transient_heat_general_state.py` cover tiny uniform/ramp controls and
nonuniform, moving-boundary, all-fixed and disconnected/reordered states with
independent dense consistent-mass reconstruction. Addition is not execution.
A narrow four-case diagnostic of the selected source returned successfully;
this is not full source, installed, public-headless or platform acceptance.
Original failing evidence and all fixed numerical gates remain applicable.
