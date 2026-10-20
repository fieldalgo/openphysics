# Steady two-dimensional heat conduction

Explicit imports are `galerkin.thermal` and `refsol.thermal`. This module solves
homogeneous isotropic stationary conduction on a conforming P1 triangle mesh:

```text
-div(k grad T) = Q,       q = -k grad T
T = prescribed value on Dirichlet nodes
q.n = 0 on unselected natural edges (insulation by default)
```

It reuses `Mesh`, scalar P1 stiffness assembly, constant-load assembly, the
existing Dirichlet linear solver and element-gradient recovery. It does not
use electromagnetic edge spaces or an elasticity solver.

## API and SI units

```python
from galerkin.thermal import solve_steady_heat

result = solve_steady_heat(
    mesh,
    conductivity=12.0,
    dirichlet={0: 350.0, 1: 300.0},  # Example node IDs; select actual boundary nodes.
    heat_source=0.0,
)
```

| Input | Contract / units |
| --- | --- |
| mesh | `galerkin.mesh.Mesh`, reference coordinates `(N,2)` in m, integer triangles `(M,3)` |
| conductivity | Required finite real scalar k>0, W/(m K), or `{region name: k}` piecewise constant on `mesh.region_names` ([multimaterial](multimaterial.md)); no tensors or k varying inside a region |
| dirichlet | Mapping exterior integer node ID -> finite scalar temperature in K |
| heat_source | Finite real scalar Q, `{region name: Q}`, or callable `(Qpoints,2)` metre coordinates -> exactly `(Qpoints,)` W/m^3; default zero |

With the default insulated boundary, each connected component requires at least
one prescribed temperature; the optional Robin extension can also anchor it. No node is silently pinned,
no springs or least-squares regularization are added, and pure-Neumann heat
problems are outside this API. Dirichlet data must be on the actual topological
exterior boundary, not an interior node or a trusted boundary tag alone.
Unselected natural edges have insulation. Boundary node tags can construct the
Dirichlet mapping. Optional prescribed outward flux and Robin edge-tag inputs,
including additional result fields and modified balance equations, are documented
in the source-tree guide `docs/thermal_flux_robin.md`. That guide and its
example are not shipped in the distributions. The equations below describe
the default case without those inputs.

All temperatures are specified in K; no Celsius conversion or reference
temperature subtraction is inferred from user input. Finite negative source
values model heat sinks. This constant-coefficient linear PDE does not enforce
material-valid temperature ranges, thermodynamic nonlinearities or positivity
of its computed temperature. Supply physically meaningful SI data.

`SteadyHeatResult` contains:

| Field | Shape | Unit / location |
| --- | --- | --- |
| temperature | `(N,)` | K at mesh nodes |
| heat_flux | `(M,2)` | W/m^2, constant vector on each P1 triangle |
| load | `(N,)` | W/m of out-of-plane thickness, integrated volumetric heat source |
| reaction | `(N,)` | W/m of thickness, boundary heat input on fixed nodes; exactly zero at free nodes |
| residual | `(N,)` | W/m of thickness, K*T-load on all nodes |

The 2D weak form is **per unit out-of-plane thickness**. `load` and `reaction`
are not total watts. Multiply them by a physical thickness in metres only in an
explicit external calculation. No implicit thickness argument or scaling is used.

## Assembly, boundary signs and quality

For scalar P1 shape functions N_i,

```text
K_ij = integral k grad(N_i).grad(N_j) dA
f_i  = integral Q N_i dA
K_FF T_F = f_F - K_FD T_D
r = K*T-f
reaction_D = r_D, reaction_F = 0
sum(load + reaction) = 0
outward integrated boundary heat = -reaction
```

Positive reaction injects heat into the domain. For a hot-left/cold-right slab,
left reaction is positive and right reaction negative. For positive uniform
generation with equal cool boundary temperatures, total outward heat is
positive and equals the integral of Q. Integrated reaction is a nodal weak
boundary quantity, not a pointwise boundary flux density.

Constant Q uses the existing exact constant-source load routine. Callable Q
uses an original 6x6 Gauss-Legendre Duffy triangle rule for **Q*N_i**, instead
of giving each vertex one third of a centroid-only source. Constant and linear
source moments are exact. Smooth nonpolynomial sources are approximated;
discontinuous or highly oscillatory sources need a separate resolution and
quadrature study. A callback must return exactly one finite real value per
coordinate; a scalar, `(Qpoints,1)`, complex or nonfinite return is rejected.

For numerical stability, each component's first prescribed temperature is used
as a constant offset. The existing solver handles the temperature increment;
absolute K values are restored afterwards. Flux and residual are evaluated
before adding that offset, using its exact componentwise constant-nullspace
property. Mathematically the residual is still K*T-load. An independent sparse
matrix calculation from reported absolute temperature can differ by floating-
point cancellation at roundoff. Extreme temperature dynamic range or badly
conditioned geometry is not made accurate merely by this shift.

The solver rejects nonfinite assembled systems/solutions/fluxes. It requires
the infinity norm of the free residual to be <=1e-10 of
`max(norm(abs(K)*abs(increment)+abs(load), infinity), tiny)`. It also requires
absolute global heat imbalance <=1e-10 of
`max(sum(abs(load))+sum(abs(reaction)), tiny)`. These are algebraic/balance
checks, not discretization error estimates. P1 heat flux is elementwise constant
and not an H(div)-conforming locally conservative reconstruction; natural
insulation is enforced weakly. Global heat balance alone does not establish
local flux accuracy or mesh convergence.

## Validated geometry and errors

Finite real `(N,2)` coordinates, integer in-range triangle connectivity, used
and distinct nodes, unique triangles and positive resolved orientation/area
are required. Degenerate triangles, nonmanifold edges or vertices, point-only
hinges, overlapping triangle interiors and hanging nodes are rejected. Checks
use local relative geometry tolerances: determinant >1e-14 times squared edge
scale, and intersection/hanging-node tolerance 1e-12 of local length. Features
below floating-point geometric resolution remain outside the contract.

`Mesh` normally fixes orientation on construction, but arrays can be mutated:
the solver validates the actual data and rejects clockwise triangles present
at call time. `Mesh` also casts connectivity to integers on construction;
callers must not rely on it to validate fractional indices before truncation.
Do not mutate mesh data while a solve/callback is running. Boundary index,
shape, boolean-as-number, complex/nonfinite input, invalid material and missing
component constraints raise `ValueError`. A singular/nonfinite solve or failed
residual/heat-balance check is an error, not a silently accepted result.

## Reproduction

Run from the repository root with the existing package environment installed:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python packages/galerkin/examples/thermal_steady2d.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q -s \
  packages/galerkin/tests/test_thermal_steady2d.py \
  packages/galerkin-refsol/tests/test_thermal_reference.py
```

The example uses a 2 m by 0.7 m slab, k=12 W/(m K), left 350 K and right
300 K, with natural insulation at top/bottom and Q=0. It gives
`q=(300,0) W/m^2`, left injection `210 W/m` and right injection `-210 W/m`.
Use explicit submodule imports; no shared package export change is needed.

## Independent reference and fixed acceptance

`refsol.thermal.slab` directly evaluates
`T=TL+(TR-TL)x/L`, `q=(-k(TR-TL)/L,0)`, `Q=0`.
`refsol.thermal.sine_manufactured` directly differentiates

```text
T = T0 + A sin(pi*x/Lx) sin(pi*y/Ly)
Q = k*pi^2*(Lx^-2+Ly^-2)*(T-T0)
q_x = -k*A*(pi/Lx)*cos(pi*x/Lx)*sin(pi*y/Ly)
q_y = -k*A*(pi/Ly)*sin(pi*x/Lx)*cos(pi*y/Ly)
```

The reference imports no engine, solver or assembly. The default sine has
T0=300 K and A=1 K; prescribe T0 on all four sides. Exact Q comes from
`-k Laplacian(T)` and exact flux from direct derivatives, not a discrete
operator. Reference differential tests independently check these signs.

The original pre-implementation acceptance criteria are retained:

- Slab temperature/flux normalized error <=1e-10, with side reactions checked
  independently of the globally zero net heat rate.
- Sine on n=8,16,32,64 unit-square P1 meshes, k=2.5: temperature L2 order >=1.8
  and flux L2 order >=0.9 on **both last intervals**. Errors use independent
  8x8 interior triangle quadrature, not nodal values or centroid-only error.
- Normalized free residual and reaction-based heat imbalance <=1e-10.
- SI length factors 1e-3/1/1e3 and independent conductivity/source factors
  0.1/1/10, field similarity <=1e-9. With x'=s*x, k'=c*k and
  Q'(x')=d*Q(x'/s)/s^2, the same discrete geometry gives
  `T'=300+(d/c)(T-300)`, `q'=(d/s)q`, load'=d*load, reaction'=d*reaction.
- Independent linear-source shape-function moments, component nullspaces,
  finite/shape/material/boundary errors and invalid geometry are tested.

The initial source implementation observed final-two temperature orders
1.99349/1.99836 and flux orders 0.99725/0.99931 in its available environment.
These supplement the fixed gates; numerical residual is not a substitute for
physical convergence. Full source/installed-distribution evidence is recorded
separately for an exact candidate revision.

## Limits

No transient heat capacity, radiation input, conductivity varying inside a
region (piecewise-constant regions are in [multimaterial](multimaterial.md)),
anisotropic conductivity, 3D, thermoelastic coupling, simcase or Studio support
is included. Only existing NumPy/SciPy and original mathematical formulas are
used. No third-party solver source or new runtime dependency is introduced.
Documents and examples stay in the repository and are not shipped in the
distributions.
