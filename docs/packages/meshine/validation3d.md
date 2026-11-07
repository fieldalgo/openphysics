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
| C10 | adversarial inputs: Schönhardt prism; Chazelle polyhedron; cospherical prism with an interior vertex; near-coplanar quadrilaterals; stacked layers; a 4³ cospherical box lattice; 5° and 30° wedges; a 1:100 slab; closed surfaces, meshed as their parity domain (see "C14 protocol"), with each configuration the C14 validity rule makes valid: a vertex inside an edge, a vertex inside a facet, an edge inside a facet, a T-junction, nested shells, two shells touching at a vertex, an edge with four facets, two closed shells where a facet of one lies inside a coplanar facet of the other (a box standing on a larger box) |
| C11 | concentric-sphere capacitor: a = 0.5, b = 0.75, c = 1 |
| C12 | Delaunay point sets: uniform 10³–10⁶ points, a 50³ lattice, cospherical shells, coplanar sets |
| C13 | fuzz: dyadic box and cylinder assemblies with 1-ulp jitter; random closed piecewise-linear complexes |
| C14 | Thingi10K population, version 1: every file of the Thingi10K dataset (HuggingFace `Thingi10K/Thingi10K`, revision `2d5d3b2f3cd3711028ad75b12788c13b25559ec6`) licensed CC BY, CC0 or public domain, except 12 whose identical bytes also appear under another license, with 14 byte duplicates merged: 3,106 files, fixed by SHA-256 before the first boundary-recovery pull request. Each file is in class A, B or X, or is unclassified (see "C14 protocol") |
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
| V20 | C14 class A, boundary-recovery mode | share giving a valid mesh: mesh sanity (see "C14 protocol") and V1–V3 as written, with V3 applied to every input facet and V2's Euler clause applied when the referee records the surface as ball-like (one connected, edge- and vertex-manifold surface of Euler characteristic 2), plus: every input facet is tiled by the boundary faces mapped to it (each node within (√3/2)·ε·max\|x\| of the closed facet, x the node's coordinates; projected areas positive, non-overlapping and summing to the facet area within relative 1e-12); every boundary face is wound toward the outside recorded by the referee; the total volume equals the exact parity-domain volume within relative 1e-12. Time in reference seconds; counting as in "C14 protocol" | ≥ 98.0% within 60 s and ≥ 99.5% within 600 s | yes |
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
| V34 | C14: all 3,106 files in boundary-recovery mode, every class-X and class-B file through the public meshing API with the V36 defaults, and every V36 and V37 run; a file without canonical arrays runs only as "C14 protocol" says; other runs on C14 files (other modes or modified input) count for crashes and mesh sanity only | safety: crashes (a panic, caught or not; an untyped error; any other abnormal end that the harness does not classify as a time stop, a memory stop or a harness error); invalid outputs (a mesh that fails mesh sanity, or fails the validity rule of its row other than by a bound-only failure, see "C14 protocol"); rejections whose witness is missing or not confirmed by the witness verifier; meshes returned for a file with a stored, confirmed class-X or class-B witness; if the product ships an STL/OBJ reader, canonical arrays that differ from the C14 loader's | 0 of each | yes |
| V35 | C14 class X, boundary-recovery mode | share rejected with a typed invalid-input or not-closed error whose witness the witness verifier confirms, within 60 s × max(1, F_in/10⁶); not evaluated until the referee's exact test for 5 is stored | ≥ 99.5% | yes |
| V36 | C14 class A, through the public meshing API with the defaults recorded on this page before the first V36 run | share giving a mesh valid under V20's rule within 600 s × max(1, F_in/10⁵) | ≥ 98.5%, and ≥ the V20 share within 600 s on the same commit minus 1.0 percentage point; 0 invalid outputs; not evaluated when V20 is not evaluated on that commit | yes |
| V37 | C14 class A, each model inside an air box (see "C14 protocol"), through the public meshing API as in V36 | share giving a mesh valid under V20's rule over the whole box, with box nodes exactly on the box planes, every model facet tiled by model–air interface faces and each region volume within relative 1e-12 of its exact volume, within 600 s × max(1, F_in/10⁵) | ≥ 98.5%, and ≥ the V20 share within 600 s on the same commit minus 1.0 percentage point; 0 invalid outputs; not evaluated when V20 is not evaluated on that commit | yes |

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

### C14 protocol

**Population.** The population file (3,132 rows: 3,106 members, 14 merged duplicates, 12 excluded files; SHA-256
`8a3e66e43fe8ccc1a7459ea5848326e7204430e79a98994dc454b912406b3b49`) is kept in the project's lab records. The
member-set digest, the SHA-256 of the members' file SHA-256 values in lowercase hex, sorted, each followed by a line
feed, is `4c76cd96d50382a0502bdda6c039f5a534f7a8ac44b8e55a5436a025d126623e`. Members are never added, removed or
swapped; any other population is a new C14 version. Provisional class counts from the dataset's metadata are A 1,595,
B 44 and X 1,467. The referee's counts replace them before the first gated run, and failure budgets follow from the
same percentages.

**Symbols.** F_in is a file's canonical facet count (for V37, the model's alone; 0 for a file without canonical
arrays). E_max is the model's largest bounding-box extent, and lo and hi are its bounding-box minimum and maximum
corners. κ = t_cal / t_cal,ref (see "Timing"), and τ is a time limit of a row. The class letters A, B and X are
unrelated to the baseline B and to V7's B.

**Input arrays.** Every rule here applies to canonical arrays: binary STL float32 widened exactly to float64; ASCII STL
and OBJ decimals parsed to the correctly rounded float64; vertices merged only when their coordinates are bitwise equal
(+0.0 equals −0.0); OBJ polygons kept; unreferenced vertices dropped. If the product ships an STL/OBJ reader, V34 runs
through it and its canonical arrays must equal these. Otherwise C14 covers meshing canonical arrays only. A file that
the C14 loader cannot read under these rules has no canonical arrays (0 under "Validity rule"). It is outside every
share and runs in no mode that takes canonical arrays, boundary-recovery mode included. If the product ships an STL/OBJ
reader, V34 runs the file through that reader, which must reject it with a typed error. That error is the expected
rejection and needs no witness of its own; arrays returned for it differ from the C14 loader's. Otherwise the file is
only reported.

**Validity rule.** This is the input contract for imported closed surfaces; the product's own input check must
implement the same rule. Cells are the vertices, edges and facets of the canonical input. An elementary sub-segment
is the part of an edge between consecutive vertices that lie on it. A file is invalid if (0) the C14 loader cannot
read it, or it has no facets after loading. It is also invalid if it has:

1. a coordinate that is not finite, or that is nonzero with magnitude outside [2⁻¹²⁰, 2¹²⁰];
2. a facet that repeats a vertex;
3. an exactly collinear triangle, or a non-planar or non-simple polygon;
4. two facets with the same vertex set; or
5. two cells whose exact intersection is not a union of cells (crossings, piercings, partial collinear overlaps of
   edges, and a coplanar overlap with a part that no cell contained in both covers).

A vertex inside an edge or facet, an edge inside a facet, and T-junctions are valid. So are a facet inside a coplanar
facet and a coplanar overlap that is exactly the union of the facets contained in both. The product's input check
must read 5 in the same way: a rejection that names such a pair has a witness that the witness verifier does not
confirm. A valid file is closed unless (6) an elementary sub-segment lies on the boundary of an odd number of facets.
Several components, nested shells and non-manifold edges with an even number of facets are allowed. The domain of a
valid closed file is its parity domain: the points off the surface from which a generic ray crosses the surface an odd
number of times. Facet orientation is not used.

**Classes and witnesses.** The project's exact referee gives each file at most one class. It is lab code in exact
rational arithmetic, written from this rule alone by people who never see mesher results on C14, and frozen, with its
output hashed, before the first gated C14 run. Its exact test for 5 may be frozen and stored later, as stated below.

- X: a witness of 0–5.
- B: valid, with a witness of 6.
- A: valid and closed.

A file whose dataset metadata reports a self-intersection, a degenerate face or a duplicate face (a flagged file) is
never in class A in this version. A class-A file is expected to be meshed. A class-X or class-B file is expected to be
rejected with a typed error that names a witness: the cells involved and, for 5, an exact rational point of the
intersection that lies in no cell contained in both; for 0 on a file without facets, "no facets". A file without
canonical arrays is expected to be rejected as "Input arrays" says. The project's witness verifier checks the witness on
the canonical input. The referee's witness of 0 gives the C14 loader's reason category or "no facets", and the witness
verifier checks it by re-running the C14 loader on the file's bytes.

Until the referee's exact test for 5 is stored, the dataset's self-intersection count stands in for it, and every
flagged file is in class X. Flagged files without a stored witness are then outside every share, V34's no-mesh clause
does not apply to them, and a mesh returned for one is checked for mesh sanity only.

When the referee's exact test for 5 is first stored, every file is reclassified by it before the next run starts,
without mesher results, and failure budgets follow from the same percentages; a run uses the classes stored when it
starts. A flagged file that then has no witness of 0–6 is in no class in this version: it is outside every share, V34's
no-mesh clause does not apply to it, a mesh returned for it is checked for mesh sanity only, and it is reported.

**Mesh sanity.** Finite coordinates; every input vertex kept bit-identical; no duplicate or unreferenced nodes; exact
orient3d > 0 (V1); every face in one or two tetrahedra, with opposite orientations when in two; no duplicate
tetrahedra.

**Rounding bounds.** A bound-only failure is a mesh that passes mesh sanity and its row's validity rule, with every
boundary node within (√3/2)·ε·max|x| of its facet, except for one or more of: V3(a)'s area bound, V3(b)'s 4ε·L bound,
and the relative 1e-12 area and volume sums of V20's rule. Correct rounding can exceed these bounds (see "Limits"). Such
a mesh is a failure in its share and is listed, but it is not an invalid output under V34.

**Modes and air box.** Boundary-recovery mode is the exact input check, the constrained Delaunay tetrahedralization,
inside/outside labelling and one rounding to float64 with certification and repair, without refinement. The
public-API defaults used by V36 and V37 are recorded on this page before the first V36 run. A later change of them is
entered in the Amendments section with the old values, the new values and a reason that cites no C14 result; from then
on V36 and V37 use the new defaults and also report the old ones. The air box is [lo − m, hi + m] per axis, with
m = 2^⌈log₂(E_max/4)⌉, computed in float64 round-to-nearest. Each box face is split into two triangles through its
lexicographically smallest corner. The regions are "model" (the parity domain) and "air".

**Counting.** In V20, V36 and V37 only a valid mesh within the limit counts. Timeouts, memory stops, typed internal
errors and bound-only failures are failures. In V35 only a confirmed rejection within the limit counts. A share is the
exact fraction of successes over the row's files and is compared with its threshold without rounding: 8 failures in
1,595 files (99.498%) is below 99.5%. A kill that the harness did not send and that has no out-of-memory event is a
harness error: the file is re-run once, and if the error repeats, the file counts as a failure in its share, not as a
crash. A file leaves a share in three ways only:

- (a) before the run, checks independent of the mesher find that no source delivers bytes with the file's SHA-256, on
  three attempts spread over at least 24 hours. Such files are listed, and if more than 1% of a row's files are
  unavailable, the row is not evaluated.
- (b) while the exact test for 5 is not stored, the witness verifier confirms a witness of 5 that the mesher reported
  for a class-A or class-B file. The file moves to X, one way; it is listed and never replaced. If more than 1% of
  class A moves in this way after the referee is frozen, that run is not evaluated, and its share is published with
  and without the moves.
- (c) in the reclassification when the exact test for 5 is first stored (see "Classes and witnesses"), a class-A or
  class-B file for which that test finds a witness of 5 that the witness verifier confirms moves to X, one way. Such
  files are listed, and failure budgets follow from the same percentages.

A confirmed witness is a referee defect if it is of 0–4 on a class-A or class-B file, of 6 on a class-A file, or,
once the exact test is stored, of 5 on a class-A or class-B file. The referee is then corrected and every file is
rescored. Size, difficulty or other tools' results never remove a file. A result is one complete run of the row on one
tagged commit; re-running only the failures does not count. Every complete run is recorded. If two runs of a row on one
tagged commit disagree, the row is recorded as failed for that commit. This page sets no milestones: a run below a
threshold is recorded as failed for that commit, whatever stage the project is in. A run that is not evaluated is
recorded as such and never counts as passed.

**Timing.** One dedicated Linux x86-64 reference machine with at least 32 GiB of RAM; one thread; one process per
file; at most 16 GiB of memory per run, without swap. Time runs from the API call, with canonical arrays in memory, to
the certified mesh or typed error. Reading, merging and validation are not timed. Times are reference seconds: wall
seconds divided by κ = t_cal / t_cal,ref. Here t_cal is the time of a hash-pinned calibration benchmark (fixed-seed 3D
Delaunay), and t_cal,ref is its time on the reference machine when the benchmark was frozen, measured once as the
median of 5 runs and never re-measured. Files run in batches of 100 in ascending SHA-256 order. κ is measured at the
start and the end of each batch; a batch counts only if both values lie within [0.8, 1.25], and its times are wall
seconds divided by the smaller one. A batch that does not count stays in the record and is re-run whole. A run that
ends within [0.8 τ, 1.25 τ] of a time limit τ of its row, taken for the file where the row scales it, is run twice
more, and the median decides. Runs are stopped at 1.5 times the row's largest time limit for the file (900 s for V20),
converted to wall time with κ at the batch start. A file in no share runs with V35's limit. The harness classifies
memory stops, which are not crashes. A replacement reference machine counts only if its κ lies within [0.8, 1.25];
otherwise C14 rows are not evaluated. C14 rows are judged on this machine only and claim Linux x86-64 only. They run
outside CI, and CI never fetches Thingi10K.

**Reference tools and corrections.** No other tool decides a C14 class, membership, denominator or result, and no file
is excused because other tools fail it too. Figures published in papers may be shown beside C14 results. A defect in a
C14 tool is corrected only when a minimal synthetic case shows that the tool contradicts this page. The case contains
no mesher output and no C14 geometry; when it corrects a referee defect proven by a confirmed witness under
"Counting", it may be modelled on that witness. Every recorded run is then rescored mechanically, and both scorings are
published. Any other change to C14 is a new C14 version and needs its own amendment of this page.

## Reference comparisons

Comparisons with Gmsh, Gmsh HXT, Netgen and pytetwild are reported, never gated.
Gmsh-based comparisons on small cases may run live where the reference-tool rules
allow it; others are stored values in the
[stored reference value](../../stored-reference-values.md) format.
TetGen is not used, even as a stored reference.

## Amendments

Changes after the freeze, each with the old text, the new text and the reason.

**2026-10-30, V21 sizes for the layered extruder.** Old: "CI sizes {0.25, 0.177,
0.125}". New: for meshes from `meshine.extrude`, V21 on C2 is graded at
h ∈ {0.2, 0.1, 0.05} (the sizes this plan named for runs outside CI) with the same
thresholds, L2 slope ≥ 1.8 and H1 slope ≥ 0.9. Reason: at the original sizes the
extruder **failed** V21: L2 slope 1.777, H1 slope 0.881 (Linux, Python 3.13). The
first step, 0.25 to 0.177, is not yet in the asymptotic range: the same error code
gives 1.89 and 0.95 on galerkin's structured cube at n = 4, 8, 16, and size triples
of extruded meshes from 0.177 down give L2 1.89–1.91 and H1 0.94–0.95. At
{0.2, 0.1, 0.05} the extruder gives L2 1.932 and H1 0.966. The project owner approved
this exception; the failure at the original sizes stays recorded here. The
thresholds are unchanged, and the CDT kernel is graded at the original sizes.

**2026-11-06 (landed 2026-11-07), C14 population and V20 protocol.** Old: C14 "permissively licensed subset of
Thingi10K (CC0, CC BY, public domain); the subset is fixed by file hash before the first boundary-recovery pull
request"; V20 "C14 | share giving a valid (V1–V3) mesh". New: C14 is the fixed 3,106-file Thingi10K population, in
which every file is in class A, B or X or is unclassified. V20 counts class A in boundary-recovery mode, with mesh
sanity, V1–V3, facet coverage, inside/outside labelling and exact volume, timed in reference seconds and counted as in
"C14 protocol". Rows V34–V37, the subsection "C14 protocol", cases in C10 and a bullet in "Limits" are added. V20's
thresholds are unchanged. Reason: the old text did not fix the files, their expected outcomes, the denominator, the
run mode or the time measurement. A share over all permissively licensed files would include about 1,467 invalid
inputs, so it could not mean "valid mesh". V20's file set is now derived by the referee without mesher results; the
only exit from it that depends on a mesher result is limited to files with a confirmed witness of invalid input and
capped at 1% of class A. The population was fixed by SHA-256 on 2026-11-04, before any boundary-recovery pull request
was opened. These rules were adopted on 2026-11-06 and 2026-11-07, before any mesher result on a C14 file existed.
**The C14 freeze condition was missed:** this text was to land before the first boundary-recovery pull request, but
that pull request (segment recovery, #205) was opened and merged on 2026-11-07, before this text landed. It touches no
C14 file, and no mesher has been run on one; V20 has not been run. The project owner approved this change.

## Limits

- The baseline constants come from one Linux machine. Time ratios (V14) are always
  measured against a baseline rerun on the same machine, never against the numbers here.
- No dihedral-angle bound is promised next to small input angles (C7, C10); those
  cases are reported or exempted as stated.
- This page does not certify any code. Each acceptance record names the exact commit it grades.
- On C14, V3's frozen bounds can be stricter than correct rounding allows: V3(b)'s 4ε·L on a file whose largest absolute coordinate exceeds about 4.6 L, and V3(a)'s 1e-12 on a needle facet with a Steiner node on a long edge. Such files stay in every share, and the bounds are not loosened; a mesh that fails only such a bound is a failure in its share, not an invalid output under V34.
