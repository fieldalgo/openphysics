# Independent prescribed-temperature mechanical-stage acceptance

**At a glance**

- **What it checks:** independent acceptance of `galerkin.thermoelasticity.solve_thermoelasticity` against an original three-dimensional continuum oracle, for an explicitly prescribed nodal-P1 Kelvin field in plane stress and plane strain.
- **Fixed gates:** on n=8/16/32, both rates need displacement L2 ≥ 1.8 and displacement-gradient H1, full 3D stress L2 (including zz) and energy-norm orders ≥ 0.9; exact fields and energy/work identities agree to 1e-10, residuals to 1e-9.
- **Scope:** the mechanical stage only. It does not validate a heat solver, temperature transfer, provenance, transient work or a full coupling workflow. For the result of a specific commit, see its CI run.

This acceptance uses an independent continuum oracle and preregistered gates.
It covers the mechanical response to an explicitly prescribed nodal-P1 Kelvin
field. It does not validate a heat solver, temperature transfer, provenance,
transient work, or a complete sequential coupling workflow.

## Evidence

This page defines the gates and how to reproduce them. Results for a specific
commit are that commit's CI exits, logs and artifacts; the commands below
reproduce the checks and are not themselves a pass result.

## Original three-dimensional oracle

The independent oracle imports NumPy only, and never calls production or refsol
constitutive, thermal-load, quadrature, or field helpers. With engineering
in-plane strain `(exx, eyy, gamma_xy)`, it constructs the symmetric physical
3D strain tensor, including `exy=gamma_xy/2`. For `a=alpha*(T-Tref)`,

```
mu = E/(2*(1+nu))
lambda = E*nu/((1+nu)*(1-2*nu))
e_elastic = e_total - a*I
sigma = 2*mu*e_elastic + lambda*trace(e_elastic)*I
psi = mu*(e_elastic:e_elastic) + lambda*trace(e_elastic)**2/2
```

Plane strain sets total `ezz=0`. Plane stress solves the parent equation
`sigma_zz=0` for total `ezz`; it does not set `ezz=0` or discard thermal z strain.
The oracle computes physical energy by the full 3D contraction. In plane strain,
free in-plane expansion is `(1+nu)*a*(x,y)`, with `sigma_zz=-E*a` and residual
energy density `E*a*a/2`. In plane stress free expansion is `a*(x,y)` with zero
physical energy. For fully constrained uniform heating, plane stress normal
in-plane stress is `-E*a/(1-nu)`; plane strain all three normal stresses are
`-E*a/(1-2*nu)`. Side and corner reactions are independently integrated from
`sigma*n`, including half-edge corner contributions.

For every nonuniform solve, independent barycentric gradients recover constant
FE total strain from displacement. A separate tensor-product Duffy quadrature
interpolates the snapshot P1 temperature internally. The parent law then gives
internal stress, including z, and physical energy at each quadrature point.
Centroid samples are compared only to corresponding centroid output fields.
Initial stress at zero displacement gives the independently assembled positive
thermal-equivalent load `g=-integral(grad(N)*sigma_initial)`. Independently
integrated body force and internal nodal forces also check the complete residual
and reaction, rather than merely global equilibrium or solution counts.

With external body load `f` and support reaction `r`, the fixed-temperature
endpoint identities are

```
uKu = u*(f+g+r)
U = uKu/2 - u*g + C_T
integral(sigma:e_total) = u*f + u_D*r
2U = u*f + u_D*r - u*g + 2*C_T
```

Here `C_T` is the parent-law energy at zero in-plane displacement, integrated
with the P1 temperature. It is not heating-path work. Nonzero prescribed
support displacement makes omission of support work observable. A centroid
`T**2` approximation cannot reproduce the degree-two physical energy.

## Fixed convergence and exact-field gates

The pre-API mathematical plan and diagnostics were committed before inspecting
the candidate. The sequence remains `n=8,16,32` on the unit square, with
`E=70e9 Pa`, `nu=.3`, `alpha=12e-6 /K`, `Tref=293.15 K`. Both adjacent rates
must satisfy displacement L2 at least 1.8, full displacement-gradient H1,
full 3D stress L2 (including zz), and tangent energy norm at least .9.
Nonlinear temperature interpolation requires L2 at least 1.8 and H1 at least .9;
this measures prescribed-field interpolation, not heat FEM convergence.

Three distinct fields are used in both planes:

- Compatible linear temperature `theta=10+20*x`. Define
  `v=(a0*x+p*(x*x-y*y)/2, a0*y+p*x*y)`, `a0=10*alpha`, `p=20*alpha`.
  Displacement is `v` in PS and `(1+nu)*v` in PE. Minimal three scalar supports
  and zero total natural traction are used. Only additive mass-weighted rigid
  motion is removed from errors; strain, shear, scaling, and affine fits are
  forbidden. Exact P1 temperature and its gradient must agree within `1e-10`.
- Registered sine field: `theta=20*sin(pi*x)*sin(pi*y)`,
  `u=(1e-4,.6e-4)*sin(pi*x)*sin(pi*y)`, both components fixed on the exterior.
- Additional independent polynomial field:
  `theta=8+13*x*x-7*x*y+5*y*y`,
  `ux=1e-4*(x*x*y+x*y*y+x**3/3)`,
  `uy=1e-4*(x*y*y-2*x*x*y+y**3/4)`, with exact nonzero exterior displacement.

For the nonlinear fields, direct differentiation of the parent total stress
produces body force: `b=-mu*Laplacian(u)-(lambda_eff+mu)*grad(div(u))`
`+ beta*grad(T)`, with `lambda_eff=E*nu/(1-nu**2)` for PS and parent lambda
for PE; `beta=E*alpha/(1-nu)` for PS and `E*alpha/(1-2*nu)` for PE.
The oracle includes explicit differentiated component formulas.

Norm quadrature orders 8 and 10 must differ by less than 1% of each measured
error. Reference physical energy orders 12 and 16 must agree within `1e-8` of
a nonzero characteristic energy scale. Physical energy error decreases at each
refinement and its final normalized value must be at most .02. Force/moment and
free residual use `1e-9`; exact fields and energy/work identities use `1e-10`,
normalized by nonzero characteristic strain/stress/force/energy scales. Gates
were not changed after observing results. Uniform PS zero energy is normalized
by a characteristic scale rather than divided by zero.

## Acceptance evidence and controls

The independent suite has 37 cases. It includes heating/cooling, signed and
zero alpha, nonzero mechanical baseline, T/Tref shifts, separated components,
missing rigid-mode supports, rotation/translation, node/cell/local-node/edge
order, copied snapshots, write-flag rejection, stale mesh, malformed shape,
nonfinite/negative absolute temperature, units/metadata and mutable-array
replacement. A forced checksum collision still must reject different actual
mesh arrays. Reproducible FNV-1a64 is a checksum, not a cryptographic signature
or authenticated temperature provenance; correctly marked manual data is not
identified as having come from a heat solver.

Measured values at the finest mesh (n=32): normalized physical-energy errors
(PS/PE) are .00018018 / .00035537 for linear temperature, .00180161 / .00237582
for sine, and .00048015 / .00090519 for polynomial. Measured minimum
displacement rates are 1.8753 for linear temperature, 1.9725 for sine and
1.9992 for polynomial.

Ephemeral runtime mutations are rejected by the real source and installed
checks: wrong PE in-plane-alpha shortcut, factor-three thermal coefficient,
thermal RHS sign, thermal-load omission, omitted zz stress, centroid-only
physical energy, omitted support reaction/work, and bypassed mesh binding.
Each mutated run fails an existing independent assertion; no production file
is edited and no relaxed gate is used to manufacture a rejection.

Run from the repository root:

```
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m pytest -q \
  tests/galerkin/test_thermoelasticity_independent_validation.py
```

Installed consumption copies the independent oracle and tests outside the
checkout, installs the local wheel without dependencies or an index, and runs
`python -I -m pytest --confcutdir=. -q`. Existing environment dependencies are
reused in a dedicated venv; this is not a clean-room dependency installation.
Shared-host timings are execution metadata, not performance baselines.

The suite records an explicit strain norm and compares all nonlinear
interpolation norms between quadrature orders. The exact-temperature assertion
checks only temperature and its gradient.
