# Steady 2D outward heat flux and convection

Import `galerkin.thermal.solve_steady_heat` explicitly. The homogeneous,
isotropic constant-conductivity P1 triangular model solves
`-div(k grad T)=Q` in SI coordinates with unit out-of-plane depth.
The independent references are in `refsol.thermal_boundary`.

## API and units

```python
result = solve_steady_heat(
    mesh, conductivity=2.5, dirichlet=prescribed_node_temperatures,
    heat_source=5.0,
    outward_flux={"right": 0.7},
    convection={"right": (10.0, 300.0)},
)
```

The two new optional keywords default to `None`. Existing arguments and the
five original result fields retain their meaning. Every unselected natural
edge remains insulated. The above right boundary is intentionally additive:

`q.n = g_out + h*(T-T_amb)`, with `q=-k grad T`.

| Input | Contract |
| --- | --- |
| outward_flux | Mapping exterior edge tag to g_out in W/m²; positive removes heat |
| convection | Mapping tag to pair (h, T_amb), h in W/(m² K), ambient K |
| Boundary scalar | Finite real scalar, not bool/complex; h>=0 |
| Boundary callback | `(points_m, outward_normals)->values`, both arguments `(Q,2)`, result exactly `(Q,)`; finite real values, no scalar/column/vector broadcasting |

All three boundary quantities may be callbacks. The outward normals have unit
length and are computed from the actual incident triangle, independently of tag
orientation; on a hole they point into the hole. Callback batches are quadrature
points, not nodes; callbacks must not mutate the mesh and should be deterministic.
Negative g models prescribed injection. Negative convection when T<T_amb is
ambient heating. h=0 is allowed but does not anchor absolute temperature;
provided ambient values are still validated. h<0 or any nonfinite data rejects.

Dirichlet and ambient retain the low-level finite-real mathematical Kelvin
policy: no conversion or clamping, including no ambient-only positivity rule.
Negative absolute K is outside physical validity claims. Separate document or
thermoelastic interfaces may enforce stricter physical ranges.

## Boundary validation and uniqueness

Only nonempty selected `mesh.boundary_edges` tags are accepted. Each selected
integer node pair must be an actual edge with exactly one incident triangle.
Unknown/empty tags, malformed shapes/types/indices, zero-length, orphan,
interior and nonmanifold edges reject. Canonical node-pair identity catches
reversed duplicates, both within and across tags of the same condition kind.
One flux and one convection condition may share an edge and are additive.
A declared natural-condition edge with **both** endpoints Dirichlet rejects,
even for zero-valued data. A single fixed endpoint at a mixed corner is valid;
its shape-function load is not discarded or renormalized.

Each connected component requires Dirichlet data or positive discrete integrated
Robin support. h=0 is not an anchor. Pure Neumann compatibility (source equals
prescribed outward rate) does not remove the constant nullspace: compatible and
incompatible unanchored components both reject. There is no hidden pin, gauge,
pseudoinverse or unit-dependent h cutoff. A sampled positive h is discrete
evidence, not a guarantee about unsampled callback behavior. Very small h can
be ill-conditioned. A nodal Dirichlet anchor fixes the discrete system; an
isolated point constraint alone is not a continuum positive-measure claim.

`Mesh` casts connectivity on construction. The solver validates actual arrays
at call time, not the provenance of already-truncated indices. Geometry retains
the conforming/nonoverlap requirements in [the original guide](thermal_steady2d.md).

## Weak signs, results and heat balance

For P1 scalar shape functions,

```text
K_ij = integral_Omega k grad(N_i).grad(N_j) dA
H_ij = integral_Gamma h N_i N_j ds
fQ_i = integral_Omega Q N_i dA
G_i  = integral_Gamma g_out N_i ds
B_i  = integral_Gamma h T_amb N_i ds
A = K+H; system_rhs = fQ+B-G
r = A*T-system_rhs
reaction = r at fixed nodes, zero at free nodes
C = H*T-B
sum(fQ+reaction) = sum(G+C)   (also separately on every component)
```

| Result field | Shape | Meaning/unit |
| --- | --- | --- |
| temperature | `(N,)` | Nodal T, K |
| heat_flux | `(M,2)` | Elementwise -k grad T, W/m² |
| load | `(N,)` | Original volumetric fQ, W/m |
| reaction | `(N,)` | Fixed-node heat injection, W/m |
| residual | `(N,)` | All rows of r, W/m |
| prescribed_outward_load | `(N,)` | G, W/m |
| ambient_load | `(N,)` | B, W/m |
| convective_outward | `(N,)` | C, W/m |
| system_rhs | `(N,)` | fQ+B-G, W/m |

The thermostat's outward rate is **minus reaction**. Total outward rate is
G+C-reaction. Nodal integrated quantities are W/m of depth, not W; explicitly
multiply by a physical depth in metres outside this API to obtain W. `load`
never silently becomes a combined boundary/system load. Direct five-positional-
argument `SteadyHeatResult` construction remains possible: the four appended
fields default to `None`; actual solve results populate all nine arrays.

Four-point line Gauss integrates the consistent boundary matrix and the product
h*T_amb. For constant h on length ell, `H=h*ell/6*[[2,1],[1,2]]`.
The matrix is not lumped, and ambient load is not product-of-means quadrature.
Highly oscillatory/discontinuous callbacks require a separate quadrature and
resolution study. Volumetric callbacks retain the original 6x6 Duffy rule.

For stability use T=offset+increment per component. K annihilates the constant
but H does not: the shifted ambient load integrates **h*(T_amb-offset)**.
Convection/residual/flux are evaluated before restoring the large absolute
Kelvin offset. Joint shifts of Dirichlet and ambient preserve flux, but shifting
T at fixed ambient is not a null mode. Absolute reported RHS/ambient fields
may have larger cancellation than the internally shifted solve.

The infinity-norm free residual must be <=1e-10 of
`max(norm(abs(A)@abs(increment)+abs(shifted_rhs), inf), tiny)`.
Each component's heat imbalance must be <=1e-10 of the sum of absolute
volumetric/reaction/prescribed/convective rates (or tiny). Nonfinite assembly,
solution or quality failure raises `ValueError`. These checks do not estimate
FEM discretization error. Element gradients are not an H(div) flux recovery;
raw pointwise boundary gradients need not equal the weak Robin trace exactly.

The stationary functional is
`0.5 integral k|grad T|² + 0.5 integral h(T-T_amb)² - integral QT + integral g_out T`.
Its unit is W K/m; it is not stored thermal energy. Work identities use admissible
test functions vanishing on prescribed nodes.

## Independent validation and reproduction

From the repository root, with existing dependencies and packages installed:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python packages/galerkin/examples/thermal_flux_robin.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -c pyproject.toml -q -s \
 packages/galerkin/tests/test_thermal_boundary.py \
 packages/galerkin/tests/test_thermal_boundary_convergence.py \
 packages/galerkin-refsol/tests/test_thermal_boundary_reference.py
```

The example compares a constant-Q slab directly to an independent polynomial:
`T=a+b*x-Q*x²/(2*k)`, outward endpoints k*b and Q*L-k*b. References cover
left Dirichlet/right flux or Robin and both ends Robin (including one h=0).
They import no FEM engine, assembly or solver. Direct differentiation and
endpoint equations check source and boundary signs independently.

Frozen gates retain all original Dirichlet tests and add:

- Linear patch temperature/flux, side rates and normalized residual/balance
  <=1e-10; positive-temperature cooling and ambient heating.
- Constant-Q slabs (flux/mixed/Robin-only) and sine MMS (all-Robin/mixed),
  n8/16/32/64: last two temperature L2 orders >=1.8 and flux orders >=0.9.
  Independent interior 8/10-point Duffy and boundary 8/10-point norm integrals
  differ by <1% of measured error. For nonzero quadratic boundary flux traces,
  convergence and finest relative error <=2%; integrated convection can already
  be exact to roundoff and is checked independently at 1e-10 instead of assigning
  a convergence order to numerical noise.
- Sine MMS differentiates T=300+sin(pi*x)sin(pi*y) directly. Side-normal oracle
  is explicit rectangle geometry. Ambient is T-(q.n-g)/h; no production normal
  helper constructs the expected values.
- SI length s=1e-3/1/1e3 and coefficient c=.1/1/10: k'=c*k,
  Q'=c*Q/s², g'=c*g/s, h'=c*h/s. T unchanged, flux c/s, unit-depth rates c;
  normalized agreement <=1e-9. Joint Kelvin offset 1e8 and h0 invariance.
- Independent consistent affine line moments and actual runtime mutations:
  wrong prescribed sign, negative H, omitted ambient/offset correction,
  lumped mass, separated product averaging and reversed normal must fail.
- Invalid values/shapes/topology/overlaps, holes, disconnected components and
  pure Neumann compatibility versus uniqueness. No gate reduction is intended.

No transient, radiation, variable/anisotropic k, temperature-dependent h,
3D, new coupling workflow, simcase/Studio or export integration is added here.
Existing NumPy/SciPy only; no new runtime dependency or third-party solver source.
Shared document/example packaging assets remain the release owner's responsibility.
