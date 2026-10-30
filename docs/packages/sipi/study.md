# Impedance tolerance studies

**English** | [한국어](../../locales/ko/pages/packages/sipi/study.md)

[Overview](overview.md) · [Impedance design](design.md)

`sipi.study.ImpedanceStudyDocument` samples named template parameters and evaluates
single-line or symmetric differential impedance. It supports explicit sweeps,
corners, independent uniform sampling and correlated normal sampling. Every
sample and failure remains in the result; failed rows are never resampled or
removed to produce a more favourable summary.

```python
from sipi.study import ImpedanceStudyDocument

plan = ImpedanceStudyDocument('coupled_microstrip',
    dict(width=.4e-3, gap=.3e-3, substrate_height=.5e-3, eps_r=4,
         thickness=0, air_height=1e-3, box_width=4e-3),
    sampling=dict(kind='sweep', count=3,
                  variables=[dict(name='width', lower=.35e-3, upper=.45e-3)]),
    quantity='z_diff', fixed_pitch_m=.7e-3,
    mesh=dict(edge_size=.1e-3, far_size=.4e-3, grade=.3))
restored = ImpedanceStudyDocument.loads(plan.dumps())
result = restored.analyze()
# Each row preserves width, derived gap, saved cross-section, Zdiff or its error.
```

## Saved plan and sampling contract

The strict `sipi.impedance-study/1` object has exactly `schema`, `template`,
`parameters`, `sampling`, `quantity`, `mesh`, `fixed_pitch_m`. Use `from_dict`,
`loads`, `to_dict`, `dumps` to validate, copy and save it. Unknown/missing fields,
duplicate JSON keys, NaN/Infinity, boolean numbers and invalid geometry are rejected.
The five templates are `microstrip`, `stripline`, `coupled_microstrip`,
`grounded_coplanar`, `coated_microstrip`. Parameters follow their SI contracts;
all template defaults and the nominal resolved mesh settings are saved. A saved
`None` for an automatic template dimension retains its existing template rule,
which can change the generated box size when another dimension changes. Supply
explicit air/box dimensions when those must remain fixed.

`quantity` is `z_diff` for `coupled_microstrip`, otherwise `z0`. Sampling uses
1–8 distinct template parameter names, in the listed order:

| `sampling.kind` | Required fields beyond `kind` | Variable fields |
|---|---|---|
| `sweep` | `variables`, `count` | `name`, `lower`, `upper`; exactly one variable |
| `corners` | `variables` | `name`, `lower`, `upper`; all 2^D corners |
| `uniform` | `variables`, `count`, `seed` | `name`, `lower`, `upper`; independent uniforms |
| `normal` | `variables`, `count`, `seed`, `correlation` | `name`, `mean`, `std`; std > 0 |

Bounds are finite and strictly increasing; all bounded-domain corner geometries
are validated before meshing. Count is an integer 2–10000; seed is an integer
0–2^32-1. Random sampling uses NumPy `Generator(PCG64(seed))`. Normal samples are
**unbounded**, with no clipping, rejection sampling or truncation. A mean or
sample that produces an invalid physical input remains an error during analysis.

The normal correlation matrix is D×D, finite, symmetric, unit diagonal and positive
semidefinite. Symmetry, unit-diagonal, entry-range and negative-eigenvalue roundoff
allow 1e-12 absolute tolerance; asymmetric roundoff is averaged. Accepted negative
eigenvalues in [-1e-12,0] are set to zero only for the symmetric square root.
Larger negative eigenvalues are rejected. Perfect correlation/anticorrelation is
supported. Samples are `mean + (standard_normal @ sqrt(correlation).T) * std`.
Requested correlations describe the distribution, not the exact finite sample's
empirical correlation. Record the engine and NumPy versions with results; a seed
alone is not a cross-version bitwise guarantee.

`samples()` returns a copied read-only `(count, D)` array of independent variable
values in listed order. `sample_parameters()` returns fresh full template argument
maps, including derived parameters. No FEM solve runs in either method.

## Fixed pitch

`fixed_pitch_m` is `None`, or a positive centre-to-centre pitch for
`coupled_microstrip`. Fixed pitch requires `width` among the independent variables
and forbids independent `gap` sampling. Nominal width+gap must equal pitch within
relative 1e-12. Every row derives `gap = pitch - width`, keeping both trace centres
fixed. The gap follows the bottom widths used by the existing tapered template.
Bounded corners with nonpositive gap are rejected at construction. Normal samples
that cross zero gap are retained as invalid rows. This is a deterministic geometric
constraint, not an additional statistical correlation parameter.

## Evaluation, failures and summaries

`analyze(max_evaluations=128)` checks an explicit integer budget 2–10000 before any
solve. A larger sample plan raises `ValueError`; it is never silently shortened.
Every row then builds its own geometry mesh using the saved nominal settings.
`ImpedanceStudy` holds `input_json`, `quantity`, immutable `rows`, `failed`, and
`summary`. Each `StudyRow` holds index, a read-only parameter map, saved
`CrossSectionDocument` when construction succeeded, impedance in ohms or `None`,
and `error_type`/`error`. Solver errors retain the valid input document; invalid
geometry has no document. Interrupts are not converted into successful rows.

Any failed row makes `summary=None`. Otherwise the read-only summary holds sample
minimum, maximum, mean, sample standard deviation (`ddof=1`) and 5th/95th percentiles
(NumPy linear interpolation). Sweep/corner statistics are descriptive samples,
not probability distributions. Sample extrema/quantiles are **not guaranteed
manufacturing limits**, yield predictions or continuous-domain worst cases.

There is no automatic mesh-refinement check per row. Converge mesh/domain settings
for each relevant geometry before using small impedance differences. Samples do
not add conductor loss, frequency networks, nonlinear materials or full-wave
physics to the underlying quasistatic cross-section model. Results do not contain
a new persistent-result schema; the JSON contract saves inputs. UI/CLI linkage is
separate from this Python API.

## Validation

```sh
OPENBLAS_NUM_THREADS=1 python -m pytest -q tests/sipi/test_study.py
python examples/sipi/tolerance_study.py
```

Fixed criteria: exact sweep/corner endpoints and ordering; uniform bounds; seed
and JSON reproduction; fixed pitch relative 1e-12; perfect anticorrelation
normalized absolute difference 1e-12. For 10000 correlated normal draws, each
standardized sample mean must be within 6/sqrt(N) of zero and the maximum
absolute difference between normalized sample covariance and target correlation
must be <=0.08. Independently generated `scipy.stats.multivariate_normal` draws
meet the same analytical moment criteria; both sets have normal-CDF KS statistic
<0.03 in each marginal. These statistical checks do not validate material physics.

Actual two-point single-line and differential FEM studies match direct saved-input
analysis within relative 1e-10. This is composition/reproduction evidence, not an
independent accuracy claim. Tests also cover invalid normal geometries without
resampling, retained solver failures, execution budgets, malformed JSON and
invalid covariance/shape/seed inputs. Existing cross-section analytical references
and convergence limits still apply. [Executable example](../../../examples/sipi/tolerance_study.py).
