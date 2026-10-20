# Independent outward-flux and Robin thermal acceptance

[한국어](locales/ko/pages/thermal_flux_robin_independent_validation.md)

**At a glance**

- **What it checks:** independent acceptance of prescribed outward flux and Robin convection in `galerkin.thermal`, on a closed-form strip and a separate manufactured solution. The oracle does not import the production assembly or the boundary reference.
- **Fixed gates:** on n=8/16/32/64, both final intervals need interior temperature L2 order ≥ 1.8 and flux L2 order ≥ 0.9; operator, load, residual, reaction and heat-balance comparisons agree to 1e-10; quadrature 8 vs 10 agree within 1% of the measured error.
- **Scope:** the standalone steady Python API only, not documents, transient heat or coupled workflows. The candidate notes below are kept as recorded; for a specific commit, see its CI run.

This report covers initial candidate `23f528dbcffb42ec4120b762fde840f70d9aeffe`.
Its `galerkin/thermal.py` blob is
`20b2f5f0f94583e50775743e1ed9dfaf1c68d97c`; boundary reference blob is
`6dccfad22c1300a0df698dea502e1643d1a0c153`. The independent oracle never imports
that reference or production assembly, normal, load, flux or balance helpers.
Only dedicated oracle/tests/report and Korean documentation additions belong to
this independent change. Production, original tests and shared configuration are
unchanged. Initial-candidate evidence is distinct from a later final candidate,
release integration, and complete coupled workflows.

Follow-up candidate `f575a7187108800545a3e33903b3a37942df9183` has solver blob
`4633e03953d8f6369bdf0e7398d2ebd85b2b4684`. Direct AST comparison after removing
docstrings found the executable solver identical to the initial candidate. Its
reference blob `8f50ada586777e2a2dbac9f4a90275d65d17ad51` retains every existing
reference definition and adds only sine_temperature/sine_flux/sine_source. This
oracle imports none of them. The final independent branch normally merges that
follow-up, preserves the initial history, and rechecks related source and wheel
consumption. No producer code is authored or corrected by this validation. Final-candidate
related source execution passes292 cases (55 independent plus237 unchanged
producer/default/historical checks); final-wheel independent execution passes55.
Runtime negative controls reject10/10 on final source and10/10 on its wheel.
These counts are distinct from the initial-candidate counts below.

## Conservation and independently reconstructed operators

Start with `q=-k*grad(T)`, `div(q)=Q`, and physical outward normal n:

```
q.n = g_out + h*(T-T_amb)
K_ij = integral(k*grad(Ni).grad(Nj))
H_ij = integral_boundary(h*Ni*Nj)
rhs = f_Q + f_amb - f_out
f_amb_i = integral_boundary(Ni*h*T_amb)
f_out_i = integral_boundary(Ni*g_out)
reaction = ((K+H)*T-rhs) on prescribed nodes; zero elsewhere.
```

Positive reaction injects heat. Global and componentwise signed conservation is
`sum(f_Q+reaction)=sum(f_out+H*T-f_amb)`. Coordinates are m, k W/(m K), Q W/m^3,
g_out W/m^2, h W/(m^2 K), T/Tamb K. Nodal and integrated rates are W/m of
out-of-plane depth, not W. Multiplication by physical depth gives watts.

The independent oracle constructs affine basis coefficients in `[1,x,y]` from
raw triangle coordinates. It forms K from their gradients, interpolates shape
functions at its own Duffy quadrature, and separately integrates body and boundary
loads. Rectangle and square-hole normals come from analytic geometry; production
normals never provide expected values. Polynomial line moments are also computed
by coefficient multiplication and `integral(s^j)=1/(j+1)`, independently of Gauss
sampling. Thus every nodal term is checked, rather than only a cancelling total.

A test observes the actual matrix/RHS passed to elimination and compares it with
independent K+H and shifted loads. This observation supplies actual values only;
no production routine supplies oracle values. Both source and installed execution
use the same independently derived expected integrals.

## Closed-form strip and distinct manufactured solution

For constant k,Q on `[0,L]` with insulated horizontal boundaries,

```
T=a+b*x-Q*x*x/(2*k)
q_x=-k*b+Q*x
F_left=k*b; F_right=Q*L-k*b.
```

The left outward normal reverses qx. For left TD/right g,
`a=TD`, `b=(Q*L-g)/k`. For right additive Robin,
`b=[Q*L-g-h*(TD-Ta-Q*L*L/(2*k))]/(k+h*L)`.

For Robin-only endpoints define

```
B0=h0*Ta0-g0
BL=Q*L-gL+hL*(TaL+Q*L*L/(2*k))
D=k*(h0+hL)+h0*hL*L
a=[B0*(k+hL*L)+k*BL]/D
b=[h0*BL-hL*B0]/D.
```

This includes one zero-h endpoint without dividing by h. If both vanish,
compatibility `g0+gL=Q*L` still leaves an arbitrary temperature constant.
Every component must have Dirichlet or positive integrated Robin support.
The approved API rejects compatible and incompatible unanchored components;
there is no implicit pin, gauge, pseudoinverse or unit-dependent h cutoff.

The separate smooth square field differs from the producer benchmark:

```
T=310+2*x-3*y+4*x*x+2*x*y+5*y*y+.7*sin(2*pi*x)*cos(pi*y)
grad_x=2+8*x+2*y+1.4*pi*cos(2*pi*x)*cos(pi*y)
grad_y=-3+2*x+10*y-.7*pi*sin(2*pi*x)*sin(pi*y)
Q=k*(-18+3.5*pi*pi*sin(2*pi*x)*cos(pi*y))
q=-k*grad(T)
h=6+2*x+y; g=.8+.3*x-.2*y
T_amb=T-(q.n-g)/h.
```

Both all-Robin and left-Dirichlet/other-Robin cases use these direct fields.
No assembled residual is fitted into the force or boundary oracle.

## Fixed gates and weak versus raw boundary heat

The preregistered sequence is n=8,16,32,64 in both directions. Both final
intervals (16→32 and32→64) must have interior temperature L2 order>=1.8 and
vector-flux L2 order>=.9. Independent interior/boundary8 versus10 quadrature
checks retain the original thresholds: norm disagreement is <1% of measured
error; operator/load/residual/reaction/heat-balance/work comparisons use1e-10,
and coordinate/SI similarity uses1e-9 with nonzero physical contrast scales.
No absolute Kelvin offset is used to conceal a temperature-difference error.

Quadratic strip boundary quantities have two different meanings. The variational
reaction and consistent integrated `G+C` can already equal the continuum endpoint
rate to roundoff, even while interior FE error is nonzero. Requiring a decreasing
nonzero error or defining an order from those roundoff values is mathematically
inappropriate. They retain an exactness check<=1e-10; no tolerance is loosened.

Separately integrate the raw P1 constitutive flux dotted with the analytic
boundary normal over incident boundary cells. This is generally not exactly
conservative and has a nonzero discretization error. It must decrease, its final
two orders must be>=.9, and the finest nonzero quadratic boundary relative error
must remain<=.02. It does not replace the weak heat-balance check. The producer's
reported early two failures/ten passes from a monotonic-roundoff test definition
are historical evidence, not new failures in this independent suite.

Observed final interior rates and finest raw endpoint relative errors:

| Field | Final two temperature orders | Final two flux orders | Finest raw boundary error |
|---|---|---|---|
| Mixed quadratic strip | 1.998906 /1.999651 | .999266 /.999779 | .000607705 |
| Robin-only quadratic strip | 1.997677 /1.999269 | .998545 /.999560 | .001527452 |
| Mixed smooth MMS | 1.989124 /1.997144 | .995127 /.998727 | Not the quadratic endpoint gate |
| All-Robin smooth MMS | 1.985921 /1.996221 | .994533 /.998544 | Not the quadratic endpoint gate |

The corresponding weak endpoint errors are at most8.14e-14 relative. These are
observed outcomes, not fitted tolerances. Tests retain the failed-interval policy
and do not choose a convenient subset of the fixed sequence.

## Offset, geometry, validation and actual negative controls

The endpoint work identity is `theta^T*(K+H)*theta=theta^T*shifted_rhs+theta_D^T*R`.
Its unit is W K/m; it is not stored thermal energy. With `T=c+theta`, shifted RHS
must contain `-H*c`, preferably as direct integration of `h*(Tamb-c)`. Joint shifts
of Dirichlet and ambient preserve physical flux/convection. A shift of2^30 K uses
exactly representable constant boundary data; flux/rate agreement retains1e-9.
Returned absolute temperatures permit their floating-point representation error
separately, rather than feeding a large Kelvin value into the physical gate.

Tests also cover negative finite mathematical Kelvin, h0 ambient invariance,
tiny positive h1e-12 without an arbitrary cutoff, per-component Robin/Dirichlet
anchors, five-argument legacy result construction, None/empty defaults,
nonuniform h*Tamb products and consistent line mass, proper rotation/translation,
node/cell/local-edge ordering, reversed tags, and outward normals into holes.
Nine SI cases use length s in{1e-3,1,1e3}, conductivity c in{.1,1,10},
`Q→c/s^2*Q`, `g,h→c/s*(g,h)`: T is invariant, q rotates/scales c/s and unit-depth
rates scale c. Callback coordinate/normal transformations follow the physical data.

Rejection checks include same-kind duplicate and reversed edges, interior/unknown/
empty/self/negative/noninteger edges, a natural edge with two fixed endpoints,
malformed scalar/column/vector callback outputs, negative/nonfinite/bool h,
nonfinite ambient even h0, complex flux, and compatible/incompatible pure Neumann.
A single fixed corner endpoint is permitted. Flux+Robin is intentionally additive.
Low-level Dirichlet/ambient Kelvin both preserve the finite-real mathematical
policy; negative K is outside physical-validity claims, with no Celsius inference.

Actual ephemeral runtime mutations corrupt outward sign, H sign, ambient load,
consistent mass (lumping), hTamb product (separate averaging), reaction sign,
conductivity scaling, callback normals, stable offset correction and Neumann
uniqueness (implicit pin). Each runs an unchanged independent assertion; no
production file is written. A failed mutated assertion is a rejected control,
not a defect in the unmodified candidate. Expected-value functions never use the
mutated or original producer helpers as truth.

## Evidence scope and reproduction

The first independent source run passed20 cases. Expanded53 cases passed;
the final dedicated suite adds actual assembled-operator and tiny-anchor checks,
for55 cases. Related execution before those last two additions passed255 cases
(53 independent plus202 unchanged original checks). Final related execution
passes257 cases (55+202); installed independent execution passes55 cases.
Actual runtime negative controls are rejected10/10 in source and10/10 in the
installed wheel, each with one expected failed assertion. No numerical failure occurred
in these recorded source runs. An initial shell command used an invalid log
redirection before pytest started; that execution failure is preserved separately.
One expanded log ended without a summary; a separate complete53-pass run supplies
the count, rather than inferring success from an incomplete log.

From the repository root with existing dependencies:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python -m pytest -c pyproject.toml -q -s \
  tests/galerkin/test_thermal_flux_robin_independent_validation.py
```

Installed consumption runs copies of the independent oracle/tests outside the
checkout with `python -I -m pytest --confcutdir=. -q`, verifying wheel import origin
and module-byte identity. Existing environment dependencies are reused, not
newly resolved or installed from an index. Source, installed, whole-regression
and exact-CI counts must be reported separately. Shared-host timings are execution
metadata rather than a performance baseline. A complete CI/release gate is
separate from this initial candidate's independent numerical evidence.

The added Korean pages translate their named English versions without changing
historical commands, SHA, equations, gates or failure/limitation claims. Their
English links are resolved relative to the page. Existing English pages,
production, original tests and shared packaging/README settings remain unchanged.

Limits: constant isotropic steady 2D conduction and the specified smooth fields
and polygonal geometry. No transient cooling dynamics, radiation, nonlinear
convection/material, arbitrary discontinuous callback accuracy, positivity
between quadrature samples, curved-hole convergence, temperature provenance,
headless workflow or thermoelastic/sequential coupling acceptance is implied.
