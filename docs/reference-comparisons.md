# Reference-tool comparisons

**English** | [한국어](locales/ko/pages/reference-comparisons.md)

Selected problems are solved twice: with galerkin and with an independent
finite-element tool. The comparison is recorded separately from each feature's
analytical acceptance references, which stay unchanged.

- **Same discretization** (same mesh, element, coefficients and boundary data):
  both tools must produce the same discrete solution. The relative difference is
  gated at `1e-9`, far above roundoff and far below any discretization error.
  This checks assembly, boundary handling and solvers, code against code.
- **Different discretization** (another element order or quadrature): the
  differences are reported, never gated.

Agreement between tools is not convergence evidence. Convergence and accuracy
claims still come from analytical references and mesh-refinement studies.

## Tools

| Tool | Version | License | How it is used |
|---|---|---|---|
| [scikit-fem](https://github.com/kinnala/scikit-fem) | `>=12,<13`; CI pins 12.0.2 | BSD-3-Clause | Imported in tests from the test-only extra `galerkin[crosscheck]` |
| [symfem](https://github.com/mscroggs/symfem) | `==2025.12.0` (sympy 1.14.0 in CI) | MIT (sympy: BSD-3-Clause AND MIT) | Same; [element definitions](#element-definitions) only |

By choice, only permissively licensed tools are installed as test extras and
run in CI (see [third-party software](third-party.md)). Tools under weak
copyleft (LGPL, such as NGSolve) or GPL are not imported or installed by this
repository; if compared at all, they run as separately installed, unmodified
programs in their own environment and process, and only their numerical results
are reported. AGPL tools are not used.

## Running

```bash
python -m pip install -e "packages/galerkin[crosscheck]"
OPENPHYSICS_CROSSCHECK_DIR=.validation/crosscheck \
  python -m pytest -q tests/galerkin/test_crosscheck_skfem.py \
    tests/galerkin/test_crosscheck_skfem_lossy_cavity.py \
    tests/galerkin/test_crosscheck_skfem_multimaterial.py \
    tests/galerkin/test_crosscheck_symfem_elements.py
```

Without the tool the tests skip locally. CI sets
`OPENPHYSICS_REQUIRE_CROSSCHECK=1`, so a missing tool fails instead, and keeps
each record in `.validation/crosscheck/` inside the Linux job's artifact. The
installed-wheel run keeps its records in `.validation/installed-crosscheck/`
inside the `installed-test-results` artifact.

## Record format

Each comparison emits one JSON record (schema `openphysics.crosscheck/1`),
printed into the JUnit output and optionally written to a file. The helper is
`tests/galerkin/crosscheck.py`.

| Field | Content |
|---|---|
| `case`, `physics` | Case identifier and the problem solved |
| `openphysics` | Distribution, installed version, API and discretization |
| `reference` | Tool, exact installed version, SPDX license, source URL, how it is used, its discretization |
| `matched` | Conditions made identical (mesh, element, coefficients, boundary data, forms) |
| `not_matched` | Known differences (element order, quadrature, eigensolver) |
| `observables` | Per quantity: name, unit, metric, value, gate (`null` = reported only), pass/fail |
| `analytical_acceptance` | Where the feature's analytical pass/fail lives; never replaced by the comparison |
| `wall_time_s` | Wall time of each tool's assembly and solve |
| `not_measured` | What the record does not cover (currently peak memory, which one shared process cannot separate per tool) |
| `environment` | Python, platform, numpy and scipy versions |
| `role` | Always `code-to-code comparison; not convergence evidence` |

## Current cases

Values from a local Linux run (Python 3.12, numpy 2.5.4, scipy 1.18.1,
scikit-fem 12.0.2). The CI records of each commit are authoritative.

| Case | galerkin | scikit-fem | Observable | Difference | Gate |
|---|---|---|---|---|---|
| `heat-p1-slab` | `thermal.solve_steady_heat`, P1 | `ElementTriP1` | nodal temperature; element heat flux | 2.1e-15; 4.0e-14 | 1e-9 |
| `elasticity-p1-plane-strain-cantilever` | `elasticity.solve_elasticity`, P1 | `ElementVector(ElementTriP1)` | nodal displacement | 4.5e-13 | 1e-9 |
| `elasticity-p1-plane-stress-cantilever` | same, plane stress | same | nodal displacement | 8.2e-14 | 1e-9 |
| `waveguide-vector-rect-core` | `waveguide.solve_modes`, Nedelec x P1 | `ElementTriN1 * ElementTriP1` | effective index, 4 guided modes | 1.5e-15 | 1e-9 |
| `cavity-pec-box` | `cavity.solve_cavity_box`, Nedelec tetrahedra | `ElementTetN0` | lowest 8 eigenvalues k^2 | 1.4e-14 | 1e-9 |
| `cavity-lossy-slab` | `material_cavity.solve_material_cavity_box`, complex eps/mu per tetrahedron | `ElementTetN0`, per-material assembly | six complex k^2; Q | 4.1e-15; 9.2e-14 | 1e-9 |
| `cavity-impedance-walls` | same, Leontovich walls z1 and x0 | `ElementTetN0` + `FacetBasis` tangential mass, `T(k)` frozen at galerkin's `k0` | three complex k^2 at the fixed point | 6.8e-13 | 1e-9 |
| `heat-p1-three-region-wall` | `thermal.solve_steady_heat`, P1, region k and Q | `ElementTriP1`, per-triangle k and Q | nodal temperature; element heat flux | 2.0e-15; 3.1e-13 | 1e-9 |
| `elasticity-p1-plane-strain-three-region-bar` | `elasticity.solve_elasticity`, P1, region E and nu | `ElementVector(ElementTriP1)`, per-triangle Lame parameters | nodal displacement; element stress | 3.7e-13; 3.2e-13 | 1e-9 |
| `elasticity-p1-plane-stress-three-region-bar` | same, plane stress | same | nodal displacement; element stress | 1.6e-12; 1.0e-12 | 1e-9 |
| `thermoelasticity-p1-plane-strain-three-region-bar` | `thermoelasticity.solve_thermoelasticity`, P1, region alpha, E, nu | same, thermal load `beta (T_h - Tref) div v` | nodal displacement; element stress | 4.0e-13; 2.0e-13 | 1e-9 |
| `thermoelasticity-p1-plane-stress-three-region-bar` | same, plane stress | same | nodal displacement; element stress | 4.4e-13; 2.7e-13 | 1e-9 |
| `transient-heat-p1-three-region-wall` | `transient_heat.solve_transient_heat`, P1, region k, c and Q | `ElementTriP1` stiffness and consistent mass, backward Euler in the test | nodal temperature at every stored time | 1.2e-15 | 1e-9 |
| `heat-p2-reference-slab` | P1 | `ElementTriP2` | vertex temperature: P1 vs P2; P1 vs exact; P2 vs exact | 3.7e-5; 3.6e-5; 1.5e-6 | reported |
| `elasticity-p2-reference-cantilever` | P1, plane stress | `ElementVector(ElementTriP2)` | tip deflection, P1 vs P2 | 1.7e-1 | reported |

The P2 rows show the expected effect of element order on coarse meshes (P1
triangles are stiff in bending); they are not accuracy claims for either tool.

## Element definitions

[symfem](https://github.com/mscroggs/symfem) builds finite elements from their
definitions and integrates in exact rational arithmetic (sympy); DefElement uses
it to verify other libraries. `test_crosscheck_symfem_elements.py` compares
galerkin's element definitions and element matrices with it on two small meshes
with rational coordinates and scrambled node ids: six triangles (obtuse, thin
and clockwise ones included) and four tetrahedra around one interior edge.
The engine never imports symfem (`test_independence.py`).

Conventions are fixed first, exactly and independently of both codes. Each
cell's vertices are passed to symfem in ascending global node id, and the
circulation of every symfem Nedelec function along every edge of the cell,
directed from the lower to the higher node id, is integrated here with sympy.
It equals the identity matrix, so symfem's degrees of freedom are galerkin's
(unit-tangent circulation, low node id to high node id) with no sign or scale
conversion. The P1 functions equal the Kronecker delta at the vertices. Both
checks are exact (gate 0). The test also asserts that galerkin's global edges
run from the lower to the higher node id and that both local orientations occur.

The global matrices are then compared entry by entry (relative gate `1e-12`;
float64 against exact rationals gives about `1e-16`). A sign flip in the
orientation rule, a wrong mass scale or a `1e-7` change in one P1 mass entry
each fail it.

| Case | Observable (galerkin API) | Difference | Gate |
|---|---|---|---|
| `elements-p1-nedelec-triangles` | edge circulations minus identity; P1 vertex values minus delta | 0; 0 | exact |
| | P1 gradients (`postprocess.element_gradient`); stiffness; mass | 1.1e-16; 9.8e-17; 1.0e-16 | 1e-12 |
| | Nedelec values at centroids (`edge.eval_edge_field`); curl-curl; mass; edge x P1 gradient coupling | 1.7e-16; 3.6e-16; 1.1e-16; 1.6e-16 | 1e-12 |
| `elements-p1-nedelec-tetrahedra` | edge circulations minus identity; P1 vertex values minus delta | 0; 0 | exact |
| | P1 gradients (`assembly3d.tet_gradients`); stiffness; mass | 2.0e-16; 1.6e-16; 7.8e-17 | 1e-12 |
| | Nedelec values at centroids (`edge3d.eval_edge_field_3d`); curl-curl; mass; edge x P1 gradient coupling | 2.3e-16; 1.0e-16; 1.2e-16; 1.5e-16 | 1e-12 |

Values from a local Linux run with symfem 2025.12.0 and sympy 1.14.0. Not
compared: the P1 load vector (galerkin uses a one-point centroid rule) and the
P1 boundary mass. The symbolic integration takes about 20 s on one core.

## Adding a case

1. Solve the same problem with the public galerkin API and the reference tool.
2. Match everything you can and list it in `matched`; list every remaining
   difference in `not_matched`.
3. Gate only same-discretization observables, with `SAME = 1e-9`; report the
   others with `gate=None`.
4. Add the tool to `galerkin[crosscheck]`, the CI pins, the license inventory and
   [third-party software](third-party.md) if it is new.
5. Update this table in English and Korean.

## Stored comparisons

Comparisons without a live tool use the [stored reference values](stored-reference-values.md) contract.
scikit-fem and symfem currently run live; NGSolve uses stored results. Add each new stored tool and its record together.
