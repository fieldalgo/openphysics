# Line-network validation

**English** | [한국어](../../locales/ko/pages/packages/sipi/network_validation.md)

[Contract](network.md)

Acceptance criteria were fixed before implementation. These checks validate
propagation of supplied RLGC, not copper/material extraction or FEM accuracy.
The existing cross-section accuracy and mesh-convergence criteria are unchanged.

| Check | Criterion |
|---|---|
| Matched lossless line, negative propagation phase, DC series R, zero length | absolute S error <=1e-10 |
| Scalar lossy/mismatched line vs independently written ABCD formula | absolute S error <=1e-10 |
| Lossless unitary S, reciprocal S, passive singular values | error/excess <=1e-10 |
| Symmetric coupled line vs independent odd/even ABCD | absolute S error <=1e-10 |
| Noncommuting asymmetric 2-conductor matrices; uncoupled 3-conductor port mapping | same identities and absolute 1e-10 |
| Matched alpha*length=4000 | finite output, absolute S <=1e-10 |
| scikit-rf DistributedCircuit single line and odd/even line, se2gmm | absolute S difference <=1e-10 |
| Touchstone 2.0 independent reader, deliberately nonreciprocal 2/4-port samples | absolute 1e-14 and exact frequencies |

`tests/sipi/test_line_network.py` covers the analytical checks, actual lossy
stripline extraction bridge, strict input validation and snapshots.
`tests/sipi/test_crosscheck_skrf_network.py` runs scikit-rf **2.2.0** lazily from
the `sipi[test]` extra. Required CI fails if it is absent; it is not imported or
bundled by SIPI. The [license inventory](../../third-party.md) records the exact
version, source license and test-only dependencies.

Local Linux observation (2026-10-30): Python 3.12.14, NumPy 2.5.4, SciPy 1.18.1,
scikit-rf 2.2.0, pandas 3.0.3. The 36 network tests passed. Maximum differences:
single-line S 1.53e-11; odd/even S 1.83e-14; mixed conversion 2.49e-16. The isolated
reference environment installed from wheels in about 2.2 s with unchanged numerical
pins and passed dependency checking; the three reference tests including imports
ran in 0.67 s with 66.3 MiB peak RSS. These are observations on one machine.
A separate pre-existing development environment is incomplete (`simcase` absent);
its dependency check is not reported as passed.

Reproduce from the repository root in the configured validation environment:

```bash
OPENPHYSICS_REQUIRE_CROSSCHECK=1 OPENBLAS_NUM_THREADS=1 \
  python -m pytest -q tests/sipi/test_line_network.py tests/sipi/test_crosscheck_skrf_network.py
```

The emitted crosscheck record distinguishes the same RLGC inputs and algorithmic
comparison from analytical acceptance. No stored reference or golden values are
regenerated. DC with zero R/G is covered analytically, avoiding a reference-tool
0/0 characteristic impedance. No high-frequency dispersion, full-wave, skin-effect,
roughness, measurement-coupon, browser or Windows application acceptance is inferred.
