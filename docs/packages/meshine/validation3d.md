# Pre-registered validation plan: 3D tetrahedral meshing

**English** | [한국어](../../locales/ko/pages/packages/meshine/validation3d.md)

[Documentation home](../../README.md)

Status: **plan, frozen before implementation.** No 3D mesher in OpenPhysics passes
or fails any criterion below yet. This page fixes, before any meshing algorithm is
written, the cases, formulas and thresholds that will decide whether OpenPhysics's
own permissive 3D tetrahedral meshers are accepted:

- the layered **extruder** in `meshine` (pure Python, prisms of a 2D meshine
  footprint split into tetrahedra), and
- the general **constrained Delaunay kernel**, planned as a separate package,
  `meshloom` (compiled kernel, required dependency numpy only).

Both return the same tetrahedral mesh contract (below), so one set of criteria
grades both. Until they pass, 3D meshing in OpenPhysics stays on Gmsh through
[`gmshio`](../gmshio/overview.md).

## Rules

- The SHA-256 of this file is recorded when it lands. Algorithm work starts after that.
- **Thresholds are never loosened.** A missed gate is recorded as *failed*. The
  owner may approve an exception explicitly; the threshold text is not edited.
  An unrun test is never reported as run.
- A later change to this page may add cases or tighten a threshold. Any other
  change states the old text, the new text and the reason, in the same pull request.
- Gates compare our own measured values with fixed numbers, including the frozen
  baseline constants below. Side-by-side comparisons with other tools mesh the
  same shape differently ("different discretization"): they are reported, never gated.
- Wall-time ratios are benchmarks, not required CI. Required CI holds counts,
  exact checks and analytic errors only.
- ε = 2⁻⁵². L = bounding-box diagonal of the input.
- All quality metrics are computed by our own NumPy code from the output arrays,
  for every tool. No number printed by a tool is used.

## Output contract

The mesh is read by `galerkin.from_mesher` and has the fields of `gmshio.FemMesh3D`:

| Field | Shape | Guarantee |
|---|---|---|
| `nodes` | (N, 3) float64 | no orphans, no duplicates |
| `tetrahedra` | (T, 4) int64 | exact `orient3d > 0` on the output doubles, for every tetrahedron |
| `regions` | (T,) int64 | in `[0, len(region_names))`, never −1, every region non-empty |
| `region_names` | list of str | order of first appearance |
| `boundary_faces` | {tag: (F, 3) int64} | exterior faces only (used by one tetrahedron), wound outward, each in exactly one tag; the union is the whole topological boundary |
| `boundary_nodes` | {tag: (n,) int64} | exactly `np.unique(boundary_faces[tag])` |
| `interfaces` | {(a, b): (F, 3) int64} | a < b; each face lies between one tetrahedron of region a and one of b, wound from a to b |

`write_msh` writes Gmsh MSH 4.1 ASCII in pure Python: volume physical group `i + 1`
is `region_names[i]`, each boundary tag is a surface group, and interfaces are
written only on request (`gmshio` puts every surface group into `boundary_faces`).

## Metrics

For a tetrahedron with vertices p₀..p₃, a = p₁ − p₀, b = p₂ − p₀, c = p₃ − p₀:

```text
V         = a·(b×c) / 6                                   signed volume
A_k       = area of the face opposite p_k,  S = Σ A_k
r_in      = 3|V| / S
R         = | |a|²(b×c) + |b|²(c×a) + |c|²(a×b) | / (2|a·(b×c)|)
q         = 3 r_in / R                                    1 for the regular tetrahedron
θ_e       = arccos(−n_k·n_l)                              dihedral at edge e; n_k, n_l the outward unit normals of its two faces
ρ         = R / ℓ_min                                     radius-edge ratio (0.612 regular)
γ         = 2√6 r_in / ℓ_max                              reported only
r_e       = ℓ_e / h(midpoint of e)                        size ratio per edge
```

Reported statistics: min, p1, p5, median, mean, max; histograms of q (bins of 0.05)
and θ (bins of 5°); counts of tetrahedra with any θ below 10° and below 30°.

## Cases

| ID | Case |
|---|---|
| C1 | unit sphere, radius 1 |
| C2 | unit cube [0,1]³ |
| C3 | chip package: substrate 10×10×[0,1], die 4×4×0.5 centred on top, mold 10×10×[1,2.5] around the die; 3 regions |
| C4 | cylindrical via, r = 0.3, through the slab [−1,1]²×[0,1]; 2 regions |
| C5 | sphere r = 0.5 inside the cube [−1,1]³; 2 regions |
| C6 | Fichera corner: [−1,1]³ minus [0,1]³ |
| C7 | prism of length 1 over an isosceles triangle with legs 1 and a 15° apex |
| C8 | thin-layer stack, aspect ratio 1:50 |
| C9 | box cavity with a dielectric block |
| C10 | adversarial inputs: Schönhardt prism; Chazelle polyhedron; cospherical prism with an interior vertex; near-coplanar quadrilaterals; stacked layers; a 4³ cospherical box lattice; 5° and 30° wedges; a 1:100 slab |
| C11 | concentric-sphere capacitor: a = 0.5, b = 0.75, c = 1 |
| C12 | Delaunay point sets: uniform 10³–10⁶ points, a 50³ lattice, cospherical shells, coplanar sets |
| C13 | fuzz: dyadic box and cylinder assemblies with 1-ulp jitter; random closed piecewise-linear complexes |
| C14 | permissively licensed subset of Thingi10K (CC0, CC BY, public domain); the subset is fixed by file hash before the first boundary-recovery pull request |
| C15 | package footprint 10×10 with 36 vias, r = 0.15 |

Sizes for C1–C7: C1 h ∈ {0.2, 0.1, 0.05}; C2 {0.12, 0.06, 0.03}; C3 {0.8, 0.4, 0.2};
C3 with the die at h/2 {0.96, 0.48, 0.24}; C4 {0.2, 0.1, 0.05}; C5 and C6
{0.24, 0.12, 0.06}; C7 {0.06, 0.03, 0.015}.

## Baseline

The quality and performance baseline is **Gmsh 4.15.2 with the Netgen optimizer**
(`Mesh.Algorithm3D=1`, `Mesh.Optimize=1`, `Mesh.OptimizeNetgen=1`, `Mesh.MeshSizeMax=h`,
one thread), written B below. Gmsh default (the same without the Netgen optimizer) is D.

The frozen constants below come from one measurement campaign in October 2026:
Linux x86-64 (Intel Xeon 2.1 GHz), Python 3.13, the Gmsh 4.15.2 PyPI wheel, one
thread, 3 repetitions with identical meshes, metrics computed by our own code with the
formulas above. They are constants of this plan, not results of OpenPhysics code.
Gmsh was used unmodified as a separate-process study tool; no Gmsh, Netgen or TetGen
source was read.

**Size convention.** With `MeshSizeMax = h`, the baseline's median edge is 0.76 h to
1.32 h, depending on case and size. Our size parameter is calibrated once to match
the baseline (V8 below), so "size h" means the same in both meshes and tetrahedron
counts can be compared.

## Acceptance criteria

| ID | Case | Metric | Threshold | Gate |
|---|---|---|---|---|
| V1 | every case and size | n_bad = #{T : exact orient3d(p₀..p₃) ≤ 0} on the output float64; Python `Fraction` up to 20k tetrahedra, the kernel's exact check above, cross-checked on the small cases | 0 | yes |
| V2 | every case | each face in 1 or 2 tetrahedra; ∪ `boundary_faces` = faces used once, each in exactly one tag; `boundary_nodes` = unique face nodes; no orphan nodes; regions in range and non-empty; each interface face between one tetrahedron of each side; Euler characteristic V − E + F − T = 1 per ball-like region; `from_mesher` succeeds | all hold | yes |
| V3 | planar facets of C2–C10 | (a) \|Σ face area − facet area\| / facet area; (b) exact distance of the facet's nodes to its plane, over L; (c) each boundary face maps to exactly one input facet | (a) ≤ 1e-12; (b) ≤ 4ε, and exactly 0 on axis-aligned facets | yes |
| V4 | C2, C3, C6–C10 | \|Σ_{T∈r} V_T − V_r\| / V_r per region and in total; V_r exact from the input by the divergence theorem (`Fraction`) | ≤ 1e-12 | yes |
| V5 | C1, C4, C5, C11 at 3 sizes | δ(p) = \|‖p − c‖² − R²\| / (2R(‖c‖ + R)) computed exactly (for cylinders, the distance to the axis); max over nodes on curved surfaces | ≤ 1e-15 | yes |
| V6 | C1 | e(h) = \|ΣV_T − 4π/3\| / (4π/3); least-squares slope of log e against log h over the 3 sizes | slope ≥ 1.8 and e(0.05) ≤ 1.5e-3 | yes |
| V7 | C2, C3, C9 (all input angles ≥ 90°), guaranteed mode (B = 2), after refinement and before improvement | max ρ | ≤ 2·(1 + 1e-9) | yes |
| V8 | C1 and C2 at 3 sizes; C3 with the die at h/2; C2 graded with h(x) = min(0.2, 0.02 + 0.3‖x − (½,½,½)‖) | r_e per region | uniform and die cases: median within ±10% of the baseline median in the table below, and p95 ≤ baseline p95 + 0.10; graded: ≥ 90% of edges with r_e / 1.281 in [0.5, 1.5] (1.281 = baseline median on C1 at h = 0.1) | yes |
| V9 | C1 at 3 sizes | precondition T within [0.85, 1.25]·T_B; then min θ, min q, mean q | min θ ≥ 15.0°; min q ≥ 0.30; mean q ≥ mean q_B − 0.03 (table below) | yes |
| V10 | C2–C6 at 3 sizes | over non-exempt tetrahedra: min θ, mean q, T / T_B. Exempt: touching an input edge with dihedral angle < 60° or a facet corner < 20° (counted and reported) | min θ ≥ max(θ_D, min(15°, θ_B − 3°)); mean q ≥ mean q_B − 0.03; T within [0.75, 1.33]·T_B; pass on ≥ 14 of the 15 (case, size) pairs | yes |
| V11 | C1–C6 | tetrahedra with no boundary vertex: min and max θ | target ≥ 15° and ≤ 150° | report |
| V12 | C1–C6 | "matches Gmsh with the Netgen optimizer" is claimed only if mean q ≥ B − 0.01, min q ≥ 0.9·B, min θ ≥ B − 2°, \|T/T_B − 1\| ≤ 0.15 all hold | — | report |
| V13 | C1–C7 at 3 sizes | histograms and percentiles of q, θ and r_e for ours, Gmsh default, Gmsh with the Netgen optimizer, Gmsh HXT, Netgen and pytetwild; C7 also reports the tetrahedra within 2h of the 15° edge | — | report |
| V14 | C1–C7 | same machine, same session, one thread, median of 5 fresh processes. (i) ratio = our time from the surface to the tetrahedral mesh / Gmsh 3D + optimization time, from the same surface triangles; (ii) end-to-end time from the geometry, reported | (i) C1 at h = 0.1 and 0.05: ≤ 1.5; C2–C7: ≤ 2.0; a graded 1M-tetrahedron cube: ≤ 60 s and ≤ 1 GiB peak RSS | benchmark |
| V15 | C1 at h = 0.1, C3 | exact-arithmetic stage calls per inserted vertex; mean walk steps; insertions per output vertex; Steiner points per segment | ≤ 2× the value measured in the pull request that introduces the counter; never raised later | yes |
| V16 | orient3d, insphere and in-plane incircle for every combination of input, segment and facet points | sign agreement with exact rational arithmetic, plus a cross-language set checked with Python `Fraction` | 100% on 10⁴ random + 10⁴ adversarial cases in CI, 10⁶ + 10⁵ outside CI | yes |
| V17 | C12 | (a) every interior face locally Delaunay under symbolic perturbation, checked exactly; (b) 3 insertion orders give the same tetrahedra; throughput on 10⁶ uniform points | (a), (b) 100%; ≥ 150k points/s target, < 50k points/s stops the kernel plan | yes |
| V18 | C10 at 3 sizes | V1–V4 | 100%; Steiner counts reported | yes |
| V19 | C13 | panics, invalid outputs (V1–V3), hangs (60 s child-process limit), untyped errors | all 0; 200 cases per CI run, 10⁵ outside CI | yes |
| V20 | C14 | share giving a valid (V1–V3) mesh | ≥ 98.0% within 60 s and ≥ 99.5% within 600 s | yes |
| V21 | C2: u = sin πx sin πy sin πz, −Δu = 3π²u, u = 0 on the boundary. C1: u = x² − y² + z with Dirichlet data | P1 errors with a degree-5 rule: e_L2, e_H1 (C2 only); h_eff = (\|Ω\|/T)^{1/3}; least-squares slopes over 3 meshes | L2 slope ≥ 1.8; H1 slope ≥ 0.9 | yes |
| V22 | C3 with conductivities 1, 0.01, 1 per layer; T = 0 at the bottom, T = 1 at the top, insulated sides | max over nodes of \|T_h − T_exact\|, T_exact piecewise linear in z | ≤ 1e-10 | yes |
| V23 | C2 PEC cube cavity through `from_mesher` and the 3D edge-element eigensolver | the existing assertions of the unstructured-cavity tests in `tests/galerkin/test_cavity_modes.py`, unchanged | unchanged | yes |
| V24 | C11: inner sphere u = 1, outer u = 0, ε = 1 on (a, b), ε = 4 on (b, c) | e = \|C_h − 16π/3\| / (16π/3), C_h = uᵀKu; slope over 3 sizes | ≥ 1.6 | yes |
| V25 | C1 PEC sphere cavity | relative k² error per cluster, TM (ka = 2.7437) and TE (ka = 4.4934) | expected: monotone, order ≥ 1.5, finest < 2e-2 | report |
| V26 | C1–C9 at h = 0.1 | SHA-256 of the canonical arrays over 3 fresh processes and 2 in-process runs; Python 3.12 and 3.15 with the same wheel | identical | yes |
| V27 | C1, C3 scaled by 2⁻²⁰ and 2¹⁰ | connectivity, regions and faces; nodes against the exactly scaled nodes | identical, bitwise | yes |
| V28 | C2, C3, C5 in µm, mm, m, km and 1e6 m | region volume fractions; tetrahedron counts; V1–V5 | fractions equal to relative 1e-9; counts within relative 0.1 | yes |
| V29 | C1–C9 on every wheel platform | canonical SHA-256 per platform | identical (target) | report |
| V30 | every published wheel and the sdist | installs with `--only-binary`, passes the mesher tests on its own runner; an install without the kernel keeps the 2D mesher and the extruder working and raises a clear error for the kernel path | all pass | yes |
| V31 | C2, C3 | `write_msh` → `gmshio.read_msh` → `gmshio.to_fem3d`: region names, regions and per-tag face sets equal the original mesh | identical, no Gmsh binary needed | yes |
| V32 | the 3D meshing and interop tests that are skipped without Gmsh today (gmshio generation, galerkin interop, unstructured cavity) | the same assertions on a mesh from OpenPhysics's own mesher | unchanged | yes |
| V33 | C15 | 2D footprint mesh time at size 0.1 (median of 3); extrusion and tagging time | ≤ 30 s; ≤ 2 s per 1M tetrahedra | benchmark |

### Frozen baseline constants

V9, C1 (sphere):

| h | T_B | T window [0.85, 1.25]·T_B | mean q_B | mean q floor |
|---|---|---|---|---|
| 0.2 | 2,518 | 2,141–3,147 | 0.8408 | 0.8108 |
| 0.1 | 17,667 | 15,017–22,083 | 0.8647 | 0.8347 |
| 0.05 | 134,381 | 114,224–167,976 | 0.8763 | 0.8463 |

The baseline's own min q on C1 at h = 0.2 is 0.293, below the V9 floor of 0.30.
The floor is kept: V9 asks for more than the baseline at that size.

V10 (θ in degrees):

| Case | h | T_B | θ_B | θ_D | min θ gate | mean q_B | mean q floor | T window |
|---|---|---|---|---|---|---|---|---|
| C2 | 0.12 | 3,627 | 19.19 | 7.60 | 15.00 | 0.8206 | 0.7906 | 2,721–4,823 |
| C2 | 0.06 | 21,225 | 23.83 | 13.63 | 15.00 | 0.8574 | 0.8274 | 15,919–28,229 |
| C2 | 0.03 | 158,259 | 20.64 | 12.07 | 15.00 | 0.8729 | 0.8429 | 118,695–210,484 |
| C3 | 0.8 | 4,330 | 16.80 | 12.66 | 13.80 | 0.7637 | 0.7337 | 3,248–5,758 |
| C3 | 0.4 | 21,585 | 14.53 | 12.82 | 12.82 | 0.8082 | 0.7782 | 16,189–28,708 |
| C3 | 0.2 | 140,512 | 15.61 | 12.43 | 12.61 | 0.8476 | 0.8176 | 105,384–186,880 |
| C4 | 0.2 | 3,124 | 18.32 | 12.17 | 15.00 | 0.7942 | 0.7642 | 2,343–4,154 |
| C4 | 0.1 | 19,078 | 20.33 | 12.54 | 15.00 | 0.8430 | 0.8130 | 14,309–25,373 |
| C4 | 0.05 | 132,840 | 15.89 | 12.46 | 12.89 | 0.8669 | 0.8369 | 99,630–176,677 |
| C5 | 0.24 | 3,778 | 21.06 | 13.06 | 15.00 | 0.8068 | 0.7768 | 2,834–5,024 |
| C5 | 0.12 | 22,713 | 23.56 | 12.45 | 15.00 | 0.8485 | 0.8185 | 17,035–30,208 |
| C5 | 0.06 | 160,659 | 18.51 | 11.69 | 15.00 | 0.8685 | 0.8385 | 120,495–213,676 |
| C6 | 0.24 | 3,742 | 19.09 | 13.11 | 15.00 | 0.8094 | 0.7794 | 2,807–4,976 |
| C6 | 0.12 | 19,802 | 23.58 | 11.86 | 15.00 | 0.8503 | 0.8203 | 14,852–26,336 |
| C6 | 0.06 | 138,138 | 20.43 | 12.27 | 15.00 | 0.8703 | 0.8403 | 103,604–183,723 |

V8, baseline r_e per region:

| Case | h | Region | median | median window (±10%) | p95 | p95 limit |
|---|---|---|---|---|---|---|
| C1 | 0.2 | ball | 1.178 | 1.060–1.296 | 1.671 | 1.771 |
| C1 | 0.1 | ball | 1.281 | 1.153–1.409 | 1.710 | 1.810 |
| C1 | 0.05 | ball | 1.324 | 1.191–1.456 | 1.710 | 1.810 |
| C2 | 0.12 | cube | 1.053 | 0.947–1.158 | 1.584 | 1.684 |
| C2 | 0.06 | cube | 1.245 | 1.120–1.369 | 1.677 | 1.777 |
| C2 | 0.03 | cube | 1.296 | 1.166–1.425 | 1.682 | 1.782 |
| C3, die h/2 | 0.96 | substrate | 0.763 | 0.687–0.839 | 1.232 | 1.332 |
| C3, die h/2 | 0.96 | die | 0.919 | 0.827–1.011 | 1.380 | 1.480 |
| C3, die h/2 | 0.96 | mold | 0.764 | 0.688–0.841 | 1.239 | 1.339 |
| C3, die h/2 | 0.48 | substrate | 0.937 | 0.843–1.031 | 1.447 | 1.547 |
| C3, die h/2 | 0.48 | die | 0.983 | 0.885–1.081 | 1.546 | 1.646 |
| C3, die h/2 | 0.48 | mold | 0.937 | 0.843–1.030 | 1.460 | 1.560 |
| C3, die h/2 | 0.24 | substrate | 0.992 | 0.893–1.091 | 1.504 | 1.604 |
| C3, die h/2 | 0.24 | die | 1.165 | 1.049–1.282 | 1.666 | 1.766 |
| C3, die h/2 | 0.24 | mold | 0.992 | 0.893–1.091 | 1.523 | 1.623 |

V12 claim thresholds for C1 (h = 0.2 / 0.1 / 0.05): mean q ≥ 0.8308 / 0.8547 / 0.8663;
min q ≥ 0.2640 / 0.4439 / 0.3686; min θ ≥ 20.91° / 23.64° / 20.98°.

Derivation (rounding: windows inward to integers, other values to 4 decimals):
T window = [⌈0.85 T_B⌉, ⌊1.25 T_B⌋] for V9 and [⌈0.75 T_B⌉, ⌊1.33 T_B⌋] for V10;
V10 min θ gate = max(θ_D, min(15, θ_B − 3)); V8 window = [0.9 m_B, 1.1 m_B],
p95 limit = p95_B + 0.10.

### Revision before freezing

The design draft of V8 asked for a median r_e in [0.8, 1.2] and p98 ≤ 1.6 at
uniform h. The baseline measurement showed that Gmsh with the Netgen optimizer has a
median of 1.18–1.32 and p95 of 1.67–1.71 on C1 and C2. Matching the baseline's
tetrahedron count (V9, V10) and the draft V8 would have been contradictory, so V8 is
now stated against the baseline's own size distribution. This revision was made
before the freeze and before any implementation.

## Reference comparisons

Comparisons with Gmsh, Gmsh HXT, Netgen and pytetwild are reported, never gated.
Gmsh-based comparisons on small cases may run live where the reference-tool rules
allow it; others are stored values in the
[stored reference value](../../stored-reference-values.md) format.
TetGen is not used, even as a stored reference.

## Limits

- The baseline constants come from one Linux machine. Time ratios (V14) are always
  measured against a baseline rerun on the same machine, never against the numbers here.
- No dihedral-angle bound is promised next to small input angles (C7, C10); those
  cases are reported or exempted as stated.
- This page does not certify any code. Each acceptance record names the exact commit it grades.
