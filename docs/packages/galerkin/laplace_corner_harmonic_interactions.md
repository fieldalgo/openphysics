# Static wedge harmonic interaction blocks

**English** | [한국어](../../locales/ko/pages/packages/galerkin/laplace_corner_harmonic_interactions.md)

`galerkin.laplace_corner_harmonic_interactions` integrates interactions of the
[static wedge density modes](laplace_corner_harmonic.md):
`rho_a(s)=a/h*(s/h)^(a-1)`, `phi0=rho_p` and
`phi1=sqrt(3)*(rho_(2p)-rho_p)`, with masses `[1,0]` and `0.5<p<=1`.
These are static Laplace modes, not temporal harmonics. At `p=1`, the second
mode is the ordinary zero-mean linear density.

Every vector is a planar displacement in metres. With an offset argument,
the first segment runs from zero to `first`; the second runs from `offset`
to `offset+second`. Returned 2×2 matrices follow mode `0,1` on each segment.
Entries integrate `log(distance / 1 metre)` and are dimensionless. A common
length scale adds its logarithm only to entry `00`.

| Explicit API | Admitted geometry | Quadrature |
|---|---|---|
| `power_panel_harmonic_far_log` | Length ratio ≤64; offset length ≥4×sum of lengths | Requested `n=4..64`, compare `n/2n`; default32 |
| `power_panel_harmonic_shared_vertex_log` | Nonoverlapping rays from the same origin; length ratio ≤64 | Analytic Duffy radial integral; angular `n/2n`, default64 |
| `power_panel_harmonic_separated_log` | Length ratio ≤64; segment separation ≥half the longer length | Requested `n/2n`, default32 |
| `power_panel_harmonic_constant_log_partitioned` | Harmonic target; uniform linear source; length ratio ≤1e6; disjoint or common-endpoint segments | Fixed64/128 double-ended cubic rules on at most128 graded subintervals |

All functions return `HarmonicPanelLogResult` with immutable fine/coarse
`mean_log_distance` arrays, the requested order, subinterval count and physical
mass error. Exponents and vector shapes/types must be valid finite real inputs.
Mixed interactions use exact binary-input topology checks; they refuse crossings
and overlaps. Geometric and numerical refusals do not trigger another method.

The two positive measures for `rho_p` and `rho_(2p)` retain their analytic
normalization. Their computed sums are checked against mass `[1,0]`; weights
are not rescaled. Centered logarithms remove constants analytically from
zero-mass entries. The real log-modulus identity preserves small real increments.
Only the `00` entry receives the physical length logarithm. Shared-origin
blocks integrate the radial variable analytically. Partitioned mixed blocks
use the exact uniform-source integrals and physical target density factors.

Coarse/fine entries must differ by at most `1e-12*max(1,abs(fine))`, and physical
mass error must be at most `1e-12`. These are primitive numerical checks, not
bounds on field, discretization or physical accuracy. A valid geometry can
exceed a finite numerical budget and be refused.

## Evidence and limits

Seventy-one stored mpmath1.3.0 comparisons cover18far,30shared-origin,
5separated and18mixed cases. Reference entries use strict nonzero relative
`1e-12` comparisons. Separate mathematical methods are disclosed: far Taylor
moments, Duffy adaptive angular integrals, uncentered high-precision tensor
quadrature, and adaptively integrated mixed-source identities. Some mathematical
identities or quadrature measure families are shared; these are structure
comparisons, not independent complete field solvers. Stored provenance names
the version, BSD-3-Clause license, inputs, generator and compare-only replay.

Closed uniform shared-ray integrals, coordinate symmetries, physical scaling,
raw reciprocity, immutable storage and explicit admission/refinement failures
are also checked. Earlier research input-admission and complex-log evaluation
failures remain recorded; their criteria were not relaxed.

Self integrals and interactions alone do not qualify an assembled matrix,
fixed internal guard, field convergence, physical measurement or another
execution platform. Existing solver APIs, defaults and reference records remain
separate.

A separate [half-space assembler](laplace_corner_harmonic_assembly.md) retains raw matrix refinement and reciprocity before any charge solve.
