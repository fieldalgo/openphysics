# Transient heat on a fixed P1 mesh

[전체 한국어판](../../locales/ko/pages/packages/galerkin/transient_heat.md) · [Validation](transient_heat_validation.md)

**At a glance**

- **What it does:** `galerkin.transient_heat.solve_transient_heat` advances 2D heat conduction, c·dT/dt − div(k·grad T) = Q, on a fixed conforming P1 triangle mesh with consistent mass and backward Euler. Inputs are constant isotropic k [W/(m K)] and c [J/(m³ K)], a source Q [W/m³], explicit times [s], an initial field [K], fixed Dirichlet nodes with time-dependent temperatures and, on tagged exterior edges, a prescribed outward flux g [W/m²] or convection h·(T − T_amb) with the steady solver's input forms, each constant, spatially varying or time-dependent; other boundaries are insulated.
- **Limits:** no radiation or temperature-dependent h; time-dependent boundary data are an engine feature only (the simcase document adapter takes constants); a time-dependent h is refused with JAX or PyTorch inputs; no restart or automatic heat-to-mechanics coupling. Finite negative Kelvin is not clamped, and no discrete maximum principle is promised.
- **Validation:** the [validation contract](transient_heat_validation.md) and [independent acceptance](transient_heat_independent_validation.md) fix backward-Euler order 0.9–1.1 against the exact discrete eigenmode product, and temperature L2 order ≥ 1.8 and flux L2 order ≥ 0.9 on a manufactured sine solution; the [flux and convection gates](transient_heat_validation.md#outward-flux-and-convection-gates) compare convective and constant-flux slabs with independent series, the steady solver and the per-step heat balance, and the [time-dependent gates](transient_heat_validation.md#time-dependent-flux-and-convection-gates) compare a sinusoidal ambient temperature and a ramped flux with closed forms. For the result of a specific commit, see its CI run.

## Evidence

This page defines the API contract. Results for a specific commit are that
commit's CI exits, logs and artifacts; the fixed gates and reproduction
commands are in the [validation guide](transient_heat_validation.md).

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
    time_s, initial_temperature_k, dirichlet, heat_source=0.0,
    outward_flux=None, convection=None, checkpoint_every=None)
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
| outward_flux | `None` or `{boundary_edges tag: g}`, g in W/m² (positive removes heat); scalar, callback(points_m, outward_normals)->exactly (Q,), callback(time_s)->scalar or callback(points_m, outward_normals, time_s)->exactly (Q,) |
| convection | `None` or `{boundary_edges tag: (h, T_amb)}`, h ≥ 0 in W/(m² K), T_amb in K; each a scalar or any of the same callback forms |

A source callback receives (Q,2) metre coordinates and one scalar second value.
Flux and convection follow [steady outward flux and convection](thermal_flux_robin.md)
exactly: q·n = g + h·(T − T_amb) on the selected edges, the same 4-point edge
quadrature, the same edge validation (nonempty tagged exterior edges with one
incident triangle, no duplicate or fully Dirichlet edge, h ≥ 0) and the same
unit-length outward normals. Each of g, h and T_amb takes one of four forms,
told apart by the number of required positional parameters of a callback: a
scalar or a `callback(points_m, outward_normals)` is **static** and sampled once
before stepping, exactly as before; a `callback(time_s)` returning a scalar or a
`callback(points_m, outward_normals, time_s)` returning exactly (Q,) is
**time-dependent**. Time-dependent values are sampled at `time_s[0]` for
validation and then at the **end of every step, t_{n+1}**, the same instant at
which Dirichlet and source callbacks are evaluated (backward Euler uses the
right-endpoint data). Any other signature (no parameter, more than three,
variadic positionals, or a two-parameter callback whose parameter is named
`time_s`/`time`) is refused with ValueError before any sampling. Edge geometry
and validation run once; sampling and assembly failures at `time_s[0]` are
chained at time index 0, later ones at their step. The Robin matrix H is
assembled once unless h itself is time-dependent, in which case it is
reassembled at every step; G and B are re-evaluated at every step whenever any
value is time-dependent (an edge-local cost, small next to the per-step
factorization). A natural edge does not anchor anything that a Dirichlet node
would: a Robin-only component is well posed because M/dt + K + H_n is positive
definite.
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

No radiation, temperature-dependent h, temperature-dependent or continuously varying material, changing mesh,
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
boundary callback is also sampled once per time, and so is each time-dependent
flux or convection callback (static ones once, before stepping). No point-batch
or node evaluation-order guarantee is made. No initial rate or reaction is invented.

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
H_n,ij = integral_Gamma h(t_n)*N_i*N_j ds        (convection edges)
G_n,i  = integral_Gamma g(t_n)*N_i ds            (outward_flux edges)
B_n,i  = integral_Gamma h(t_n)*T_amb(t_n)*N_i ds
f_i(t) = integral N_i*Q(x,t)
A_n = M/h_n + K + H_n
r_n = M*(T_n-T_n-1)/h_n + K*T_n + H_n*T_n - B_n + G_n - f_n

(A_FF)*T_F,n =
    f_F,n + B_n,F - G_n,F + M_FF*T_F,n-1/h_n
    - A_FC*d_n + M_FC*d_n-1/h_n
```

Both old and new M_FC terms are required. The implementation includes the full
old M*T and subtracts the full new A_FC*d; it does not solve a sequence of
steady problems. H_n, G_n and B_n are the steady solver's 4-point edge
integrals on edge geometry computed once: for static data they are assembled
once (H, G, B), for time-dependent data G_n and B_n are re-evaluated at every
step and H_n only when h varies; without flux or convection data they are
absent and the system and loads are exactly the Dirichlet-only ones. Spatial
source integration uses the existing 6x6 Duffy rule.

Each geometric component uses one **time-independent** initial offset for
subtractions/derivatives. Its stiffness image is mathematically zero and its
mass derivative is zero. H does not annihilate the offset: as in steady heat
the solve uses the increment u = T − offset with the shifted ambient load that
integrates h·(T_amb − offset of the component), and the convective rate is
C_n = H_n·u_n − shifted B_n = H_n·T_n − B_n. The offset is never reset at each time. Sparse
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
| prescribed_outward_load_w_per_m | (Nt-1,N) or None | G_n per step, W/m; None without outward_flux/convection |
| convective_outward_w_per_m | (Nt-1,N) or None | C_n = H_n*T_n-B_n, W/m; None without outward_flux/convection |

The two boundary rates are positive outward. They are `None`, not zero arrays,
when neither `outward_flux` nor `convection` is given, so a Dirichlet-only
result keeps its fields and memory unchanged. `residual_w_per_m` and
`reaction_w_per_m` include the H, G and B terms when they exist.

The two metadata fields conductivity_w_mk and
volumetric_heat_capacity_j_m3k record the supplied constants (a float, or a
`{region name: float}` copy for per-region input). No unit,
provenance, hash or source-origin authentication is claimed. Read-only arrays
and a frozen container are not cryptographic protection against hostile code.

Histories alone use O(Nt*(N+M)) memory; sparse systems/factors and temporary
copies add memory, including at final result construction. No hidden
downsampling, streaming or restart is implemented. A large request may fail
allocation; no partial successful history is returned.

JAX or PyTorch inputs give histories in that library, not read-only, with
reverse-mode derivatives; their memory and the `checkpoint_every` option are in
[Derivatives with JAX and PyTorch](differentiation.md). With such inputs a
time-dependent g or T_amb is supported; a time-dependent h is refused with
ValueError (H would have to be reassembled inside the differentiated steps).

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
(H_n-H_n-1)/h_n = sum(f_n)+sum(reaction_n)-sum(G_n)-sum(C_n)
outward_D,n = sum(f_n)-sum(storage_n)-sum(G_n)-sum(C_n)
```

With flux or convection data, G_n and C_n are the two boundary result fields and
the identity holds on every connected component separately; without them the
G and C terms are absent. The free residual must stay within 1e-10 of the
absolute term scale (now including |H|·|u|, |shifted B| and |G|) and each
component's imbalance within 1e-10 of the sum of its absolute storage, source,
reaction, prescribed and convective rates, else the step raises.
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

Rectangular `thermal.transient2d` JSON/API/CLI and saved histories are provided by a separate simcase adapter. Its [input, result and save contract](../simcase/thermal_transient2d.md) is in the simcase documentation. This engine function's arbitrary callbacks/mesh support are not the serialized document scope. Documents use uniform/affine initial fields and side-constant/requested-time samples while retaining initial agreement, no projection and finite K/no clamp. The document adapter exposes constant outward flux and convection sides only; the engine's time-dependent boundary callbacks are not part of the document scope. No Studio, restart or automatic coupling is added. Engine acceptance is distinct from headless source/installed/save/CI acceptance.

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

Producer tests in `test_transient_heat_tiny_domain.py` and
`test_transient_heat_general_state.py` cover tiny uniform/ramp controls and
nonuniform, moving-boundary, all-fixed and disconnected/reordered states with
independent dense consistent-mass reconstruction. All fixed numerical gates
of the validation guide still apply.
