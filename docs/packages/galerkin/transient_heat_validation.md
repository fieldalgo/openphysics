# Transient heat validation contract

[전체 한국어판](../../locales/ko/pages/packages/galerkin/transient_heat_validation.md) · [Usage](transient_heat.md)

**At a glance**

- **What it checks:** the producer-side gates for `solve_transient_heat`: exact controls, a temporal gate on the smallest Dirichlet eigenmode, and spatial gates on a manufactured sine solution.
- **Fixed gates:** the last two temporal orders are 0.9–1.1 (n=8 mesh, 8/16/32/64 steps); temperature L2 order ≥ 1.8 and flux L2 order ≥ 0.9 on n=8/16/32/64 at 0.25, 0.5 and 1 s; an n=64 companion with half the time step changes each error by ≤ 5%; quadrature orders 8 and 10 agree within 1%. With outward flux or convection: slab spatial order ≥ 1.8 and temporal order ≥ 0.9 with finest relative error ≤ 2e-3, long-time agreement with `solve_steady_heat` ≤ 1e-8, per-step heat balance ≤ 1e-10, Dirichlet-only histories unchanged ([details](#outward-flux-and-convection-gates)).
- **Scope:** the eigenmode gate measures time error only, not PDE refinement. For the result of a specific commit, see its CI run.

## Evidence

This page defines the gates and how to reproduce them. Results for a specific
commit are that commit's CI exits, logs and artifacts; the commands below
reproduce the checks and are not themselves a pass result.

## Truth boundaries and algebra

The producer imports existing geometry, assembly and derivative helpers
read-only, without calling the anchored steady solver. New
refsol.transient_heat imports only NumPy and stdlib dataclasses, not the engine
or other reference helpers. Its small dense p1_matrices derives local gradients,
consistent mass and stiffness separately. It only checks local mesh validity,
not full intersections; callers must supply a valid mesh. Dense spectral
helpers target small reference meshes, not large production solves.

Reference families are uniform_insulated, moving_affine, sine_manufactured,
parent-independent small P1 matrices, smallest_dirichlet_mode and
backward_euler_amplitude. The reference field object contains temperature_k,
heat_flux_w_m2, heat_source_w_m3 and temperature_gradient_k_m. The semidiscrete
mode is deliberately distinct from a continuous PDE eigenfunction. Separate
independent acceptance must not adopt producer/refsol values as its truth.

All following criteria are fixed before producer execution. Never change
meshes, time grids, signs, scales, tolerances or excluded cases in response to a
failure. Preserve the failing candidate and evidence. A legitimate documented
implementation correction is tested against the same gates, not labelled an
original pass. No skip/xfail is an acceptance substitute.

## Exact controls

| Control | Required observation |
|---|---|
| Insulated uniform T=T0+(Q0/c)*(t-t0) | exact for arbitrary positive finite dt, signed Q; no artificial anchor, q=0, reaction=0 |
| Disconnected insulated components | separate initial constants/source balances; no steady nullspace rejection |
| Moving affine T=290+5*x+3*(t-t0), Q=3*c | exact P1 field/BE derivative, q=(-5*k,0); both M_FC terms and boundary storage |
| Discrete-time T=300+t+t² | source at right time c*(1+t_n+t_n-1), not continuous derivative c*(1+2*t_n); f0 sampled but unused in evolution |
| Same constant shift of initial/BC/T | flux/storage/reaction invariant; H shifts linearly, V does not |
| Explicit mm or other length conversion to identical metres | physical answer invariant; no automatic unit inference |
| Initial data within/outside 32eps | preserve accepted initial field exactly; reject out-of-bound data without projection |
| Callback/linear solve/history failure | original chained cause, time index/value, no successful partial result |

Registered algebra scales use Tscale=max(1K, amplitude/change), rate scale
including sum(abs(f))+sum(abs(r))+sum(abs(M*dT/dt)), heat scale c*area*Tscale,
flux k*Tscale/L and mass c*area. Never use cancelling net loads or absolute Tref
as the normalization. Exact uniform/affine fields, independent M/f/storage/
reaction, original free residual, component/global balance, H/V and BE-product
checks require normalized error<=1e-10. Explicit SI conversion requires<=1e-9.

For an unforced homogeneous perturbation, check the full quadratic identity:

```text
(V_n-V_n-1)/h_n
+ .5*(T_n-T_n-1)^T*M*(T_n-T_n-1)/h_n
+ T_n^T*K*T_n
= T_n·(f_n+r_n)
```

Every term has W K/m units. This is not a stored-heat equation. Under zero
Dirichlet or insulated homogeneous unforced conditions V cannot grow; do not
extend that statement to moving/nonzero boundary data or forcing. H balance
must use storage and outward=-sum reaction. Independently reconstructed cell
normal flux is not required to equal weak finite-mesh thermostat rate.

## Frozen temporal gate

Unit-square mesh has exactly n8 subdivisions per side. Independently assemble
M/K and select the smallest positive Dirichlet generalized mode with all
exterior fixed to300K. Normalize max(abs(phi))=1; amplitude is1K, t0=0 and
tau=1/lambda. At steps8/16/32/64 to tau:

```text
T_F,exact(t) = 300 + exp(-lambda*t)*phi
T_F,BE(t_n) = 300 + product_j(1+lambda*h_j)^(-1)*phi
```

Compare the implementation to the discrete product at algebra<=1e-10 and the
endpoint against exp for temporal error only. The last two temporal orders
must each be .9 through1.1. This removes continuum spatial error; it is not a
PDE refinement result. An insulated zero-mode control is separate, never
tau=1/0. An irregular-dt product is an additional reuse/endpoint control.

## Frozen PDE spatial and separation gates

On the unit1m square, k=2.5W/(m K), c=4J/(m³ K), amplitude1K:

```text
T = 300 + (1+.7*t)*sin(pi*x)*sin(pi*y)
Q = [c*.7 + 2*k*pi^2*(1+.7*t)]*sin(pi*x)*sin(pi*y)
q = -k*(1+.7*t)*grad(sin(pi*x)*sin(pi*y))
```

Initial data are exact nodal T; exterior is300K. Use n8/16/32/64 and the same
dt1/256s to1s. Observe .25,.5,1s. For both last mesh intervals at each observed
time, T L2 order>=1.8 and flux L2>=.9. Norm quadrature8/10 must agree within1%
of the measured nonzero error. A finest n64 companion with dt1/512 must change
each measured temperature/flux error by<=5% of the primary error. If separation
fails, record failure; do not replace the time sequence with a tuned one.
Affine continuum time dependence does not eliminate all semidiscrete temporal
transients from spatial consistency. Initial, temporal and spatial errors
must remain distinguishable.

## Designated wrong variants and lifecycle refusal

| Wrong implementation | Discriminator |
|---|---|
| Lump mass | exact triangle offdiagonals/generalized mode; no positivity substitution |
| Omit old/new/both M_FC terms | moving-affine interior values and full residual |
| Left/averaged source or f0 reused | nonconstant discrete-time source control |
| Residual=K*T-f only | storage-aware weak nodal reaction and balance |
| Steady balance or wrong outward sign | insulated heating/moving-BC content balance |
| V labelled as J/m heat | H linearity/shift, V quadratic identity/units |
| Factorization reused with wrong dt | unequal-step mode product |
| Artificial anchors or clamping | insulated/disconnected and signed negative-K cases |
| Initial projection or fabricated t0 rate | exact initial preservation, Nt-1 rate shapes |
| Missing failure context/partial success | t0/late BC/source/solve/final-copy fault cases |

Producer contract files cover the basic contracts, originals-system audit and
small reference checks. They are not a claim that every independent wrong
variant has already been injected or rejected. The independent acceptance suite
contains those runtime discriminators and physical gates; inspect its exact run
for their outcomes. Existing gates remain unchanged.

## Reproduction and packaging boundary

From a repository root with its existing dependencies available:

```python
import os
from pathlib import Path
import subprocess
import sys

root = Path.cwd()  # Run this script from the repository root.
env = os.environ.copy()
for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
             "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"):
    env[name] = "1"
subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/galerkin/test_transient_heat.py",
                "tests/refsol/test_transient_heat_reference.py"], cwd=root, env=env, check=True)
subprocess.run([sys.executable, "examples/galerkin/transient_heat_convergence.py"], cwd=root, env=env, check=True)
subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=root, env=env, check=True)
```

The convergence program asserts the fixed temporal/spatial/separation gates
before producing a successful combined JSON report; it does not print a
predetermined pass. It retains all requested history, so the n64 companion
needs substantial memory. No wall time is a dedicated-host performance baseline.

The distribution helper builds real sdist→wheel artifacts and checks that their package code is byte-identical to the checkout and that they carry no documents, tests or examples; pages, the example and tests are not shipped. It verifies installed origins/source bytes, copies the checkout's tracked independent consumer files and example outside the checkout, and runs the independent `--suite all` consumer and full English convergence example with `python -I` against the installed wheels. The original tests run with the whole `tests/` folder against installed wheels in `tools/run_installed_tests.py`. An implemented gate is distinct from a successful build/install run. Establish packaging, installed and numerical success from the exact current CI exits, logs and artifacts. The narrow Windows save gate is not full transient-physics acceptance; release success is separate.

## Outward flux and convection gates

`tests/galerkin/test_transient_heat_robin.py` and
`tests/refsol/test_transient_heat_robin_reference.py` fix these gates for the
`outward_flux`/`convection` keywords. The references are the independent series
of `refsol.transient_heat_robin` (NumPy and SciPy `brentq` only, no engine
import): a slab 0<x<L, insulated at x=0, uniform initial T0, with either
convection h·(T−T_a) at x=L (eigenvalues β_n tan β_n = hL/k, one bracketed root
per interval (nπ, nπ+π/2)) or a constant outward flux g at x=L; both sum their
series until a stated tail bound falls below 1e-13 of the temperature scale
(|T0−T_a| or |g|L/k). The reference tests check the heat equation and both
face conditions by finite differences, the exact slab mean T0−g·t/(cL), the
long-time limits and the truncation bound; they do not import the solver.

| Gate | Fixed definition | Threshold |
|---|---|---|
| T1 convective slab, spatial | L=1 m, k=2.5, c=4, h=5, T_a=300, T0=350; strips of n=8/16/32 squares, 2000 steps to 0.2 s; relative L2 error of T on the 50 K rise | both orders ≥ 1.8; finest ≤ 2e-3 |
| T1 convective slab, temporal | n=128, 4/8/16 steps to 0.2 s | both orders ≥ 0.9 |
| T2 constant-flux slab, spatial | same slab, g=−100 W/m² at x=L (inflow), scale |g|L/k=40 K | both orders ≥ 1.8; finest ≤ 2e-3 |
| T2 constant-flux slab, temporal | n=128, 4/8/16 steps | both orders ≥ 0.9 |
| T3 long-time limit | 8×4 rectangle, left 320 K Dirichlet, top g=−20, right (h=5, 300 K), Q=30; 8 steps of 100 s from 320 K vs `solve_steady_heat` with the same data on the same mesh | T, C, reaction and G within 1e-8 of their scales; final storage ≤ 1e-8 |
| T4 heat balance | the T3 problem and two disconnected Robin-only strips with offsets 350 K and −20 K, callback h and g; storage = f + reaction − G − C per step and per component; C against independently assembled h·ℓ/6·[[2,1],[1,2]] and h·T_a·ℓ/2 | ≤ 1e-10 of the largest term |
| T5 JAX/PyTorch | histories equal NumPy; d/d(h, T_a, g, k) of a final-temperature functional vs central differences | 1e-12; relative 1e-6 (skips without the libraries) |
| T6 Dirichlet-only | the frozen text fixture `tests/galerkin/data/transient_heat_dirichlet_48720c9.json` (origin/main solver, two cases) and no boundary sampling call | bit-identical on the recorded platform, 1e-13 elsewhere |

Measured on 2026-11-02 in the development environment (Linux x86_64, NumPy
2.5.4, SciPy 1.18.1; not a CI result): T1 spatial errors 1.34e-3, 3.29e-4,
7.24e-5 (orders 2.03, 2.19), temporal 1.08e-2, 5.65e-3, 2.89e-3 (orders 0.94,
0.97); T2 spatial 1.15e-3, 2.86e-4, 6.69e-5 (orders 2.01, 2.10), temporal
7.26e-3, 3.80e-3, 1.94e-3 (orders 0.94, 0.97); T3 temperature 6.2e-15,
convective 2.4e-16, reaction 1.2e-16, G 0; T4 mixed 8.1e-17, two Robin-only
components 3.5e-16; T6 bit-identical; T5 skipped (JAX and PyTorch not
installed there). The thresholds above were fixed before these runs and are
not retuned from them.

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
