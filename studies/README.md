# Studies

Diagnostic and exploratory scripts that people run to understand a result.
Required CI never runs or imports them, and a study is not an acceptance gate:
the tests in `tests/` and the checks in `tools/` are.

| Script | Record |
|---|---|
| `cavity3d_convergence_diagnosis.py` | [Rectangular PEC 111 doublet convergence diagnosis](../docs/packages/galerkin/cavity3d_convergence_diagnosis.md) |

Run a study from the repository root in the pinned environment of the
[development guide](../docs/development.md), for example
`python studies/cavity3d_convergence_diagnosis.py`.
