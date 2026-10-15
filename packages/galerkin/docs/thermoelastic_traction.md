# Prescribed-temperature thermoelasticity with total mechanical traction

[전체 한국어판](locales/ko/pages/thermoelastic_traction.md)

This is a linear static mechanical solve on a conforming planar P1 triangle
mesh, with an explicitly frozen nodal Kelvin field and constant isotropic 3D
material. It does not run a heat solver or certify the origin of temperature.
Both `plane="stress"` and `plane="strain"` are required explicit choices.

## API and executable example

```python
from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity
snapshot = freeze_temperature(mesh, temperature_k)
result = solve_thermoelasticity(
    mesh, snapshot, reference_temperature_k=293.15,
    thermal_expansion_per_k=12e-6, young_modulus=70e9,
    poisson_ratio=.3, plane="strain", dirichlet=constraints,
    body_force=(0., 0.), traction={"right": (8e6, 3e6)})
```

`dirichlet` maps `(node_id, component)` to displacement in m; component 0/1 is
Cartesian x/y. `body_force` is a finite real constant `(2,)` N/m³ or pure
`callback(points_m)->(Q,2)` N/m³. `traction` is `None`, `{}`, or a mapping from
`mesh.boundary_edges` tags to global Cartesian finite real `(2,)` vectors in Pa,
or pure `callback(points_m, outward_normals)->(Q,2)` in Pa. Points and unit
normals have shape `(Q,2)`. No scalar pressure or normal/tangent component API
is provided. A vector `(8e6,3e6)` means x/y components, regardless of edge angle.
Callbacks must be deterministic and must not mutate mesh/snapshot/inputs.
Evaluation order and batching are not public contracts. No concurrent input
mutation is supported. Callback exceptions propagate; invalid values raise
`ValueError`. No partial successful result is returned after failure.

From a checkout root with the packages available:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python packages/galerkin/examples/thermoelastic_traction.py
python -m pytest -q packages/galerkin/tests/test_thermoelastic_traction.py packages/galerkin-refsol/tests/test_thermoelastic_traction_reference.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m pytest -q -s packages/galerkin/tests/test_thermoelastic_traction_convergence.py
```

The example sets uniform 313.15 K, Tref293.15 K, a1m square, E70GPa, nu.3,
alpha12e-6/K, target stress `[[8e6,3e6],[3e6,-2e6]]` Pa and a nonzero rigid
translation `(2e-5,-1e-5)` m. The left displacement is prescribed; the other
three edges carry TOTAL physical stress traction. It prints displacement
error, separate external/support resultants, support work, physical U and zz.
It is a prescribed-temperature mechanical example, not a heat workflow.

## Total traction, signs and units

Let a=alpha*(T-Tref), e=(exx,eyy,gamma_xy), gamma_xy=2exy, m=(1,1,0).
The original 3D law is

```text
mu = E/[2(1+nu)]
lambda = E*nu/[(1+nu)(1-2nu)]
sigma = 2*mu*(epsilon-a*I) + lambda*tr(epsilon-a*I)*I
-div(sigma) = body_force
sigma*n = traction
K*u = load_body + load_traction + load_thermal
load_external = load_body + load_traction
load_total = load_external + load_thermal
residual = K*u - load_external - load_thermal
```

Traction is **TOTAL physical sigma*n**. Do not add or subtract the thermal
q*n from an already-total traction. The positive thermal-equivalent RHS remains
`g=integral B.T*q*m`, with q=E*a/(1-nu) in PS or E*a/(1-2nu) in PE. Constant
T has zero gradient but generally nonzero g. Treating thermal effects as only
a body term proportional to grad(T) loses boundary physics.

| Quantity | Unit / location |
|---|---|
| coordinates, displacement | m / nodes |
| T, Tref; alpha | K / nodal P1; K; 1/K |
| E, stress, traction | Pa=N/m² |
| body force | N/m³ |
| body/traction/thermal load, residual, reaction | N/m per thickness / nodes `(N,2)` |
| mechanical moment per thickness | N |
| physical elastic energy, endpoint work | J/m |

Multiplying by a physical thickness h in m gives forces in N and energy in J.
Heat rate W/m is a different quantity and cannot be added to mechanical N/m.
There is no unit inference: convert geometry/displacements/materials/loads to
SI before solving. T and Tref must be finite nonnegative absolute K; cooling
is allowed, and alpha may be signed or zero. E>0 and -1<nu<.5 are required.
Near-incompressible plane-strain P1 locking remains a limitation.

## Selected-edge validation and constrained overlap

Each selected tag must exist and contain nonempty integer `(E,2)` endpoint
indices in range. Each unordered edge must be a nonzero exterior triangle edge
with exactly one owner. Reject selected duplicates within/across tags,
interior/nonedges, degenerate endpoints and malformed indices. Distinct edges
sharing a corner add once each. Unselected tags are not globally deduplicated.
Boundary node tags alone do not define line-load edges. Complete selected-edge
validation precedes traction callbacks. Meshes must be conforming,
nonoverlapping and manifold; this API does not repair arbitrary CAD geometry.

Normals point away from the unique owner triangle, independent of endpoint
ordering. Inner-hole normals point into the void; a domain-center heuristic
would be wrong. Four-point Gauss edge integration forms consistent P1 loads,
not endpoint lumping. For linear endpoint traction t0,t1 on length L:

```text
f0 = L*(2*t0+t1)/6
f1 = L*(t0+2*t1)/6
```

Loads on prescribed components are still included. Dirichlet fixes displacement
but does not erase applied traction. Reaction is residual at fixed DOFs and
zero at free DOFs, using the original uneliminated system. Corner sharing means
a per-tag support reaction is not uniquely defined. Even balanced pure-Neumann
loads require sufficient rigid constraints on every connected component.

## Results, legacy construction and snapshots

The original 18 `ThermoelasticResult` positional fields retain their order and
meaning: displacement, total_strain, thermal_strain, elastic_strain, stress,
sigma_zz, epsilon_zz, load_external, load_thermal, reaction, residual,
physical_elastic_energy, temperature_snapshot, reference_temperature_k,
thermal_expansion_per_k, young_modulus, poisson_ratio, plane. Two fields are
appended: `load_body=None`, `load_traction=None`. Normal solver results populate
both as `(N,2)` arrays. Legacy manually constructed 18-argument results have
`None` for these fields; consumers must allow that. `load_total` remains a
computed sum. `traction=None/{}` preserves earlier numerical results.

Displacement is nodal; total_strain is element constant. thermal_strain,
elastic_strain, stress, sigma_zz and epsilon_zz are centroid samples. Stress
vector order is `(sxx,syy,sxy)` and strain vector order `(exx,eyy,gamma_xy)`.
P1 T makes physical stress linear inside each cell. Reconstruct from constant
strain plus interpolated T for integrals; centroid stress is not a constant
full-cell stress. Physical energy integrates the quadratic temperature term.

PS eliminates ezz from sigma_zz=0. PE has total ezz=0 and
sigma_zz=lambda*(exx+eyy)-q. For uniform S=0 free in-plane expansion, PE strain
is (1+nu)*a in both normals, sigma_zz=-E*a and energy density .5*E*a²; PS has
strain a and zero stress/energy. Plane reduction does not discard 3D physics.

Snapshots copy immutable SI geometry, connectivity/order and nodal T.
Changing the original input array cannot change the snapshot. Identical mesh
content in another object may be used; stale scale/coordinates/node or cell
order/temperature metadata is rejected by fingerprints plus exact-array checks.
Boundary tags are **not** authenticated by snapshot hashes: current selected
edges are independently validated on each solve. Fingerprints are identifiers,
not signatures or proof of a heat-solver origin. Results and their load arrays
are mutable; no post-return integrity guarantee is made.

## Physical endpoint energy and support work

At fixed temperature, let C_T be physical energy with zero in-plane strain.
With F=load_external, g=load_thermal, r=reaction:

```text
uKu = u·(F+g+r)
U = .5*uKu - u·g + C_T
integral sigma:epsilon_inplane = u·F + u_D·r
2U = u·F + u_D·r - u·g + 2*C_T
```

Physical U uses the full 3D elastic strain. Neither .5*uKu nor .5*u·F is
physical thermoelastic energy. Support work u_D·r cannot generally be omitted
for nonzero supports. A former continuum diagnostic with zero left shear and
ux=0 had exactly zero support work despite nonzero uy; that valid cancellation
is retained as a control. Adding a fixed translation makes omitted-work
errors detectable without changing strain, stress, body, traction or gates.
These are fixed-temperature endpoint identities, not heating-path work or a
claim of complete thermodynamic energy conservation. Physical force/moment
balance uses F+r; g separately has zero resultant/moment, not another applied
physical force.

## Analytic references and fixed validation gates

`refsol.thermoelastic_traction` imports NumPy and stdlib only, never the engine
or existing reference helpers. It provides `uniform_combined`,
`polynomial_manufactured`, `parent_state` and `traction_from_stress`.
The unit-square polynomial uses c=1e-4 and the translated fields:

```text
u = c*(x^3+2*x*y^2+x*y, 2*x^2*y+y^3+x^2) + (2e-5,-1e-5) m
T-Tref = 12+9*x-4*y+6*x*y+3*y^2 K
linear control: T-Tref = 12+9*x-4*y K
```

Exact body is differentiated from the full physical stress; exact TOTAL
sigma*n acts on right/top/bottom and exact u fixes both left components.
Quadratic analytic T is sampled at nodes, so T interpolation error is part of
the mechanical consistency study, not heat FEM error. The linear control has
exact P1 T. No affine fitting or strain rescaling is used.

Both planes use fixed n8/16/32/64. Each of the **last two** intervals must have
u L2 order>=1.8; full gradient, strain tensor, full3D stress including zz and
tangent-energy norm order>=.9. Quadratic-T L2/H1 orders are >=1.8/.9.
Characteristic scales are c*L, max(c,alpha*20), E*strain, stress*L,
stress*L² and E*strain²*L², never a cancelling net load or Tref.
Norm quadrature8/10 agrees within1% of measured nonzero error; exact reference
energy quadrature12/16 differs<=1e-8 characteristic energy. Physical energy
error decreases at every refinement and is finally<=.02. Uniform fields,
independent loads/work/energy/recovery errors<=1e-10 normalized; free residual
and force/moment<=1e-9. Linear consistent-edge and rotated ring/hole/reordering
checks retain exactness gates. Actual helper mutations add/subtract thermal
boundary traction or omit/reverse g and must fail the physical patch assertion.
Reference derivative checks and invalid/callback/duplicate/stale controls are
separate from convergence. A count or continuum diagnostic alone does not
establish installed, full regression, independent acceptance or platform support.

No heat/workflow extension, pressure, traction persistence, schema/CLI/Studio,
feedback, transient, nonlinear, large strain, general 3D or locking remediation
is added. Windows and release integration require their own actual evidence.
