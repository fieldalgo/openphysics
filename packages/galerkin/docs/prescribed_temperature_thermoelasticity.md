# Prescribed-temperature thermoelasticity (2D mechanical stage)

This reusable static mechanical stage accepts an explicitly supplied nodal-P1
absolute temperature field. It does not call a heat solver, connect a heat result
automatically, certify temperature provenance, or validate a complete sequential
heat-to-mechanics workflow. Import from `galerkin.thermoelasticity` and
`refsol.thermoelasticity`; no shared package exports are required.

## API and SI contract

```python
snapshot = freeze_temperature(mesh, temperature_k)
result = solve_thermoelasticity(
    mesh, snapshot, reference_temperature_k=293.15,
    thermal_expansion_per_k=12e-6, young_modulus=70e9,
    poisson_ratio=0.3, plane="strain",
    dirichlet={(0, 0): 0., (0, 1): 0., (nx, 1): 0.})
```

The supports in this example assume `rectangle_mesh(1., 1., nx, ny)` with its
original node ordering. Run `examples/prescribed_temperature_thermoelasticity.py`
for a complete executable example. Coordinates and displacements are metres;
Young's modulus and stress are Pa; strain is dimensionless; alpha is signed 1/K.
T is a real finite nonnegative `(N,)` array in K, and Tref a real finite
nonnegative scalar K. Cooling, zero alpha and negative alpha are permitted.
Require finite E>0, -1<nu<0.5 and explicit plane=`"stress"` or `"strain"`.
There is no Celsius conversion, scalar-temperature broadcast, or unit inference.

Body force is a finite two-vector or callable accepting `(Q,2)` coordinates and
returning `(Q,2)` force densities in N/m^3. It is integrated with the same
six-point-per-axis Duffy rule as the elasticity body load. Meshes use triangles
with vector nodal displacement; DOF order is `[ux0, uy0, ux1, uy1, ...]`.
Dirichlet maps exterior `(node, component)` to displacement m; components are
0=x, 1=y. Without an applied traction mapping, remaining components have **zero total
thermoelastic natural traction**. The optional global Cartesian total-traction
mapping is described in the [traction contract](thermoelastic_traction.md).
There is no dedicated scalar-pressure/local-frame/follower API; a global Pa
callback `lambda points_m, normals: -p * normals` is valid on the fixed boundary.

Loads and reactions are line forces per out-of-plane thickness, N/m. Multiplying
by an actual thickness in m gives N. Physical elastic energy is J/m; multiplying
by thickness gives J. A moment of these forces is N (moment per thickness).
Thermal-equivalent load is a weak-form contribution, not an additional physical
external force. Report body load and support reactions separately.

## Frozen field identity

`TemperatureSnapshot` copies coordinates, connectivity, node/element order and
T into canonical little-endian float64/int64, immutable bytes-backed arrays.
It stores schema1, `length_unit="m"`, `temperature_unit="K"`, mesh, temperature
and combined reproducible fingerprints. Fingerprints use version-tagged,
length-framed FNV-1a64 checksums; they are not cryptographic signatures or source
authentication. Exact mesh arrays are also compared, so a checksum collision
cannot authorize different geometry. Matching copied meshes work; changing
coordinates, scale, ordering, connectivity, schema, units or frozen data is
rejected. Mutating the original temperature input leaves the snapshot intact;
freeze a new field to change temperatures. The API cannot detect incorrectly
labelled units or certify how a direct input was obtained. Python's deliberate
low-level object mutation is outside the immutability contract; detected
metadata/array/checksum corruption is rejected.

## Constitutive reduction and weak form

Let e=(exx,eyy,gamma_xy), gamma_xy=2epsilon_xy, m=(1,1,0),
a=alpha(T-Tref). Stress order is (sigma_xx,sigma_yy,tau_xy), so e dot sigma
is the tensor contraction. D is the usual isotropic reduced engineering-shear
matrix, with D33=mu=E/[2(1+nu)]. Its normal block is
`E/(1-nu^2) * [[1,nu],[nu,1]]` for plane stress and
`E/((1+nu)(1-2nu)) * [[1-nu,nu],[nu,1-nu]]` for plane strain.

The total in-plane stress is sigma=D e-q m, where

| Reduction | q | Out-of-plane total strain/stress |
|---|---|---|
| Plane stress | E a/(1-nu) | sigma_zz=0; epsilon_zz=((1+nu)a-nu(exx+eyy))/(1-nu) |
| Plane strain | E a/(1-2nu) | epsilon_zz=0; sigma_zz=lambda(exx+eyy)-q |

Here lambda=E nu/[(1+nu)(1-2nu)] is the original 3D Lamé constant.
Physical thermal strain is aI in 3D, not 3a per normal component.
The in-plane physical elastic strain is e-a m in both reductions.

Static equilibrium is -div(sigma)=b. With P1 vector B and unit-thickness area,
K=integral B^T D B dA is unchanged from linear elasticity and

`K u = f_body + g_thermal`, `g_thermal = +integral B^T q m dA`.

The positive sign and boundary contribution matter: replacing this term solely
by a thermal body force loses free expansion under uniform temperature.
Since B is constant and q linear per triangle, the centroid temperature
integrates g exactly. Dirichlet elimination preserves component supports and
rejects remaining rigid modes on every disconnected component.

## Result locations, reconstruction and energy

`displacement` has shape `(N,2)`. `total_strain` is constant `(M,3)`.
`thermal_strain`, `elastic_strain`, `stress` are centroid `(M,3)`;
`sigma_zz` and `epsilon_zz` are centroid `(M,)`. `load_external`,
`load_thermal`, `reaction`, `residual` are distinct `(N,2)` arrays.
`load_total` is the sum of the first two. Reaction equals `Ku-f_body-g` only on
prescribed DOFs and is zero elsewhere; residual retains all DOFs.

For barycentric coordinates l in an element, reconstruct T(l)=sum l_i T_i,
a(l)=alpha(T(l)-Tref). Then thermal strain=a(l)m, elastic strain=e-a(l)m,
sigma(l)=D e-q(l)m; use the table for sigma_zz/epsilon_zz. Thus stress is
usually linear inside an element. Centroid stresses are not the complete
piecewise-constant stress field. No stress smoothing or nodal recovery is used.

`physical_elastic_energy` integrates the original 3D elastic energy after the
chosen reduction. The element energy density is

- PS: `.5 (e-a m)^T D (e-a m)`;
- PE: `.5 (e-(1+nu)a m)^T D (e-(1+nu)a m) + .5 E a^2`.

A degree-two-exact three-point triangle rule integrates these densities for P1
T. Squaring centroid T would underintegrate them. Free uniform PE expansion has
u=(1+nu)a(x,y), zero in-plane stress, sigma_zz=-Ea and residual energy density
`.5 E a^2`; the latter is physical, not solver error. Negative energy is not
clamped. With fixed-temperature constant CT equal to the integral of
`E a^2/(1-nu)` (PS) or `1.5 E a^2/(1-2nu)` (PE), endpoint identities are

`U=.5 u^T K u-u^T g+CT`,
`u^T K u=u^T(f+g+r)`,
`integral sigma:e = u^T f+u_D^T r`,
`2U=u^T f+u_D^T r-u^T g+2CT`.

Support work is retained for nonzero prescribed displacements. These identities
are fixed-temperature mechanical identities, not heat balance or a thermal
loading-path work calculation.

## Independent validation and preregistered gates

The independent reference module uses the original 3D law, without importing
production constitutive functions, mesh helpers or solvers. Four groups are
uniform free, uniform constrained, compatible quadratic displacement under
linear T, and smooth sine MMS. For the sine case S=sin(pi x)sin(pi y),
u=(1e-4,0.6e-4)S and T=Tref+20S on the unit square. Its independent body force is
`-mu Laplacian(u)-(lambda_eff+mu) grad(div u)+beta grad T`, with
lambda_eff=E nu/(1-nu^2) PS or lambda PE, beta=E alpha/(1-nu) PS or
E alpha/(1-2nu) PE. Exact nodal T is injected; this is mechanical convergence
under an interpolated prescribed field, not heat FEM convergence.

HQ fixed the gates before implementation: original n=8,16,32, both adjacent
orders L2u>=1.8 and H1u/stress/mechanical energy norm>=0.9; independent8x8 vs
10x10 quadrature differences <1% of errors; analytic physical energy12x12 vs
16x16 agreement1e-8 energy scale; monotonically decreasing normalized energy
error with final<=0.02. Compatible-case displacement uses only a
consistent-mass rigid translation/rotation fit, never strain/scale/shear fitting.

Representative automated results (E=2GPa, nu=.27, alpha12e-6/K, unit square;
additional independent original-3D checks and example use E70GPa/nu.3):

| Group / reduction | L2u adjacent orders | H1u orders | Stress orders | Final normalized energy error |
|---|---|---|---|---|
| Sine PS | 1.978,1.994 | .993,.998 | 1.007,1.002 | .00177 |
| Sine PE | 1.975,1.993 | .995,.999 | 1.028,1.007 | .00240 |
| Compatible PS | 1.881,1.957 | 1.018,1.012 |  .980,.993 | decreases toward zero |
| Compatible PE | 1.879,1.958 | 1.017,1.012 | .982,.994 | decreases toward analytic PE residual |

The preregistered primary E70GPa/nu.3 studies also pass: sine PS L2u
1.978/1.994, H1u .993/.998, stress1.007/1.002; PE1.972/1.992,
.996/.999,1.031/1.008. Final normalized physical energy errors are .001802 PS
and .002376 PE. Compatible L2u orders are PS1.881/1.958 and PE1.875/1.958;
H1u/stress/strain orders all exceed .96. Gates were not adjusted.

Other checks cover physical3D energy/work, support work, force/moment balance,
side/corner-half-edge reactions, temperature/reference shift, alpha0 agreement
with elasticity, cooling/negative alpha, superposition, frozen/stale/tampered
snapshot, bad input/mesh and disconnected rigid modes. Executable negative
controls reject wrong thermal sign, bodyforce-only omission, threefold alpha,
incorrect PE free expansion, missing/uncoupled sigma_zz and centroid-T-squared
energy. Reference MMS body force is checked against finite-difference stress
divergence. See dedicated tests for executable criteria; no heat/full sequential
coupling acceptance results are claimed.

## Limits and release integration

Homogeneous isotropic linear small-strain, static triangular P1 displacement,
constant material/alpha and explicitly prescribed same-mesh nodal-P1 T only.
Near-incompressible plane strain can lock; nu approaching .5 is not cured by
validation. No nonlinear/large-strain/contact/dynamics/3D/thermal conduction,
dedicated scalar-pressure/local-frame/follower APIs, material-temperature dependence, cross-mesh transfer,
simcase or Studio integration is included. Boundary tags do not certify units
or provenance. Callable body forces are integrated numerically, so highly
oscillatory inputs require an independently adequate mesh/quadrature.

This document and its English example are included in the source-distribution
manifest and required byte-asset checks. Installed-wheel consumer checks are
configured to execute the verified archived example with isolated Python.
Inclusion and check configuration are not execution results; confirm actual
build, installation and validation outcomes for the exact candidate.
