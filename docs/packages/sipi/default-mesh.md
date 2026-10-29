# Finite-thickness default mesh validation

**English** | [한국어](../../locales/ko/pages/packages/sipi/default-mesh.md)

[Cross-section API and limits](overview.md)

The default corner target is the minimum of layer thicknesses, trace widths and
inter-trace gaps divided by 100, capped at each positive conductor thickness
divided by 10. The old rule included conductor thickness in the /100 minimum.
The interior of a solid conductor is excluded from the electrostatic mesh;
refining to thickness /100 everywhere near the trace was unnecessarily costly
for the cases below. This change does not alter the solver or explicit options.

## Reproduction and criteria

Run from the repository root with the development environment installed:

```sh
OPENBLAS_NUM_THREADS=1 python -m pytest -q tests/sipi
```

`test_default_mesh.py` compares default and refined solutions for 0, 5, 35 and
105 µm copper in a microstrip (h = 1 mm, w = 1 mm, εr = 4.3, box width 40 mm,
air height 20 mm). Refinement halves edge_size, far_size and grade together.
Z0 and εeff must differ by at most 0.5 %. A homogeneous coupled stripline with
35 µm copper also checks C/C0/L and even/odd/differential/common impedances at
0.5 %. Its width/gap/plane spacing are 0.4/0.1/1 mm, εr = 4 and box width 6 mm.
The 35 µm microstrip must use less than half the old default's node count.
The pre-existing analytical V1–V5 tests retain their original tolerances.
Mesh agreement is a sensitivity check, not proof of exact accuracy.

Measured on 2026-10-30 KST, Linux, Python 3.12.14, NumPy 2.5.4, SciPy 1.18.1:
all 36 SIPI tests passed. These are source tests; installed-package and other
platform results must be checked separately in CI.

## Representative cost

For the 35 µm microstrip above, with one OpenBLAS thread:

| Setting | Nodes | Z0 (Ω) | εeff | Mesh time (s) |
|---|---:|---:|---:|---:|
| Old default, edge 0.35 µm | 38,266 | 70.303901 | 3.064522 | 7.12 |
| New default, edge 3.5 µm | 12,034 | 70.275092 | 3.065323 | 2.56 |
| New default with all three settings halved | 28,716 | 70.353904 | 3.065071 | 5.05 |

Node count fell by 68.6 %. New-default/refined Z0 differs by 0.112 % and εeff
by 0.0083 %. Times are single-host observations, not a performance guarantee.
The thinner 5 µm case is still expensive: the thickness cap is deliberately
retained to resolve its side faces. This does not establish browser performance.

## Independent comparison

A private research reproduction compared the new default against historical
scikit-rf 2.2.0 (BSD-3-Clause) Hammerstad–Jensen `MLine` outputs generated on
2026-10-26. The reference tool was **not rerun** for this change. Settings:
`disp='none'`, `diel='frequencyinvariant'`, `rho=0`, `rough=0`; compare the
quasi-static `zl_eff` and `ep_reff`, with the finite-thickness correction enabled.
The new default was run for w/h = 0.25, 0.5, 1, 2, 4; εr = 4.3 and 9.8;
h = 1 mm; t = 35 µm; box width 40h and air height 20h.

Differences across those ten cases: Z0 −0.194 to +0.123 %, εeff +0.233 to
+0.652 %. These are report-only comparisons of different discretizations and
thickness approximations. The analytical acceptance tests are independent of
these values. No Polar solver was run; no equivalence to a commercial solver
is claimed.

For new geometries, check mesh refinement and box truncation independently.
The rule is not an adaptive error estimator and does not cover every clearance,
material contrast or fabrication geometry.
