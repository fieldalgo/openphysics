# Straight-edge currents between grounded planes

[한국어](../../locales/ko/pages/packages/galerkin/two-ground-edges.md)

`galerkin.laplace_two_ground.solve_two_ground_rectangle_edges` exposes the
individual straight-edge currents of the [two-ground solver](two-ground.md).
It performs one checked solve with the same input arguments, defaults,
admission bounds and refusal conditions as `solve_two_ground_rectangle`.
The original whole-surface API retains its result and checks.

```python
from galerkin.laplace_two_ground import solve_two_ground_rectangle_edges

result = solve_two_ground_rectangle_edges(
    [[[0.0038, 0.000975], [0.0042, 0.000975],
      [0.0042, 0.001025], [0.0038, 0.001025]]],
    width=0.008, height=0.002, panels_per_edge=64,
    ground_modes=128, interpolation_degree=12,
)
bottom_edge_gram = result.edge_current_gram[0]
```

## Output and ordering

`result.whole` is the original `TwoGroundRectangleResult`. It includes the
ordered conductor surfaces followed by the separate bottom and top grounded
planes. The additional immutable arrays describe only the polygon edges:

| Field | Shape | Meaning |
| --- | --- | --- |
| `edge_owners` | `(E,)` | Zero-based input conductor index |
| `edge_starts`, `edge_ends` | `(E, 2)` | Directed physical endpoints in metres |
| `edge_current_gram` | `(E, N, N)` | Integrated unit-current products, 1/metre |
| `edge_current_integrals` | `(E, N)` | Signed integrated unit currents |

Here `N` is the number of input conductors and `E` their total vertex count.
Each conductor's edges follow its admitted counterclockwise boundary. A
clockwise input is reversed; no separate rotation to a preferred first vertex
occurs. Consequently edge index 0 means the bottom edge only for the explicitly
ordered rectangle in the example. Consumers must use endpoints and ownership
when assigning physical face names. Changing a polygon's starting vertex
changes edge order, without changing the physical answer.

Each column is normalized to unit total current on its corresponding
conductor. An edge's current may have either sign. Its Gram is positive
semidefinite; an off-diagonal entry may be negative. Ground planes are not
split into finite edges and remain available through `whole`.

## Method and checks

For integrated panel charges converted to unit-current columns `q`, a panel of
physical length `l` contributes `outer(q, q) / l`. Summing those contributions
on one original polygon edge produces its Gram. Signed panel currents are
summed on that same edge. No finite difference of a potential gradient,
material law or artificial corner smoothing is introduced.

The sum of a conductor's edge Grams must reproduce its original whole Gram
at entrywise relative `1e-10`, with no diagonal floor. Signed sums use absolute
`1e-10`. Finite values, reciprocity and scaled positive semidefiniteness are
checked at `1e-10`. `partition_error` reports the largest entrywise relative
whole-Gram difference. An unresolved partition raises `ValueError`; the solver
does not substitute whole-surface factors for failed edges.

These are consistency checks, not a physical accuracy guarantee. Corner
currents make each edge quantity sensitive to panel resolution. Refine the
panels and finite outer dimensions for the requested quantity. For wide
outer boxes the explicit ground-mode count may also need to increase; the
original ground-refinement gate continues to reject an unresolved choice.

## Validation boundary

The edge contract tests cover physical endpoints, signed conservation,
immutable snapshots, exact preservation of the original whole result, and
scale, conductor permutation, reflection, winding and cyclic-start invariants.
They also preserve original admission and ground-refinement refusals. A
triangle checks that the API does not assume four edges; it does not qualify
arbitrary polygon accuracy.

Independent face accuracy additionally requires registered panel and mesh
refinement, an independent volume-energy shape derivative, and finite-outer
checks. Whole-surface agreement alone cannot establish each face's accuracy.
No frequency, metal, foil roughness, measured-coupon fit or consumer input
schema is part of this API. There is no new platform or release qualification.

## Registered rectangular sections

Three selected sections (offset single conductor, asymmetric pair and close
pair) retain 64/128/256-panel results, two independent P2 finite-element
meshes, and two interior harmonic extensions of each moving face. The
independent calculation uses the volume-energy shape derivative, rather than
the panel current formula. Each face entry is compared with its own independent
value at relative 2%, with no denominator floor; capacitance uses 0.05%.
The final panel and mesh changes must each be at most 1% per face entry.
An analytical parallel-plate case checks the independent construction at
1e-10. The independent solver and its numerical tool versions are recorded in
the evidence provenance; replay tests use the saved results, not a fresh FEM
solve. A separate bounded reference path uses explicit symmetric SuperLU
controls on the same P2 equations after the original refined run exhausted
its memory cap. An analytical anchor and all three original coarse results
are compared at `1e-10` before using that path. The original resource failures
remain failures; this reference-only change does not alter the product solver.

Separate 8/16/32 mm outer boxes use 256 ground modes and require both successive
face-entry changes to be at most 1%. The original offset single-conductor
32 mm case at 128 modes failed the original ground check and remains a refusal;
it was not counted as a passing outer comparison. These are finite-domain
sensitivity checks for the registered sections, not infinite-domain accuracy
or qualification of tapered, arbitrary polygon or measured material behavior.
