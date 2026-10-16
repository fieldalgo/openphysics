# Transient heat validation contract

[전체 한국어판](locales/ko/pages/transient_heat_validation.md) · [Usage](transient_heat.md)

## Execution boundary

This submission contains implementation, producer contract tests, additive
analytic references and a fixed convergence program. **All new Python
parse/import/compile, unit/numerical/source/whole/installed/platform checks are
unexecuted.** Static source review is not numerical acceptance. There are no
observed product errors, orders, successful checks or installed artifacts to
report from this stage; mathematical expected answers below are not results.
Existing steady tests and previous small design diagnostics are not credited
as transient product tests. Independent acceptance and release regression
remain necessary before integration.

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
variant has already been injected or rejected. Such designated mutation runs
and independent physical proof are pending. Existing gates remain unchanged.

## Future reproduction and packaging boundary

From a repository root with its existing dependencies available:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m pytest -q packages/galerkin/tests/test_transient_heat.py packages/galerkin-refsol/tests/test_transient_heat_reference.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python packages/galerkin/examples/transient_heat_convergence.py
python -m pytest -q
```

The convergence program asserts the fixed temporal/spatial/separation gates
before producing a successful combined JSON report; it does not print a
predetermined pass. It retains all requested history, so the n64 companion
needs substantial memory. No wall time is a dedicated-host performance baseline.

Later installed checks must build actual sdist->wheel artifacts, verify
installed package origins/source bytes and EN/KO/example inclusion, then run
outside-source contract/physical consumers. No build/install or distribution
inclusion has been verified here. No shared release helper/manifest was changed.
Windows, independent acceptance, complete regression and release integration
require their own actual evidence. No Actions or deployment result is implied.
