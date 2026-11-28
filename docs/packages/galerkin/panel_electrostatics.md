# Panel electrostatics: the public SI API

[한국어](../../locales/ko/pages/packages/galerkin/panel_electrostatics.md)

`galerkin.panel_electrostatics` is the public API of galerkin's homogeneous 2D
Laplace boundary-panel solvers. It follows the units convention of the other public
modules: the one quantity, `box_size`, is a keyword-only SI value under its
`physmat.units` registry name, and text in its place raises `TypeError`.

The module only wraps. Each function reads `box_size`, renames the conductor
selection, and calls an internal solver with the same numbers, so the result is
the internal solver's result object, bit for bit. The internal modules
(`galerkin.laplace_boundary`, `galerkin.laplace_two_ground`,
`galerkin.laplace_open_box`, `galerkin.laplace_corner_*`) are unchanged and stay
internal: they keep their names and their consistent units, and carry no promise.

```python
from galerkin.panel_electrostatics import solve_two_ground_rectangle

result = solve_two_ground_rectangle(
    [[[0.0038, 0.000975], [0.0042, 0.000975],
      [0.0042, 0.001025], [0.0038, 0.001025]]],
    box_size=(0.008, 0.002), panels_per_edge=64,
    ground_modes=128, interpolation_degree=12,
)
result.capacitance_per_permittivity   # dimensionless; times permittivity in F/m gives C' in F/m
```

## Solvers

| Public function | Walls | Internal solver (contract and validation) |
|---|---|---|
| `solve_grounded_rectangle` | grounded bottom; other walls zero normal flux | [`laplace_boundary`](laplace_boundary.md) |
| `solve_two_ground_rectangle` | grounded bottom and top; side walls zero normal flux | [`laplace_two_ground`](two-ground.md) |
| `solve_two_ground_rectangle_edges` | as above, with straight-edge currents | [`laplace_two_ground`](two-ground-edges.md) |
| `solve_two_ground_corner_rectangle_edges` | as above, corner-power densities, 1–2 active conductors | `laplace_two_ground` |
| `solve_two_ground_linear_corner_rectangle_edges` | as above, linear corner-power densities | `laplace_corner_linear_field` |
| `solve_two_ground_harmonic_corner_three_active_edges` | as above, three active conductors | [`laplace_corner_harmonic_field`](laplace_corner_harmonic_field.md) |
| `solve_two_ground_harmonic_corner_guard_edges` | as above, two active conductors and one zero-potential guard | [`laplace_corner_harmonic_guard_field`](laplace_corner_harmonic_guard_field.md) |
| `solve_two_ground_harmonic_corner_single_active_edges` | as above, one active conductor and two guards | [`laplace_corner_harmonic_single_active_field`](laplace_corner_harmonic_single_active_field.md) |
| `solve_open_rectangle` | all four walls zero normal flux; grounded conductors are the reference | [`laplace_open_box`](open-box.md) |

The admitted geometry, the discretization limits, the default counts, the
consistency gates and their thresholds, and the limitations are the internal
solver's, unchanged; the linked pages state them.

## Arguments

| Public argument | Internal argument | Meaning |
|---|---|---|
| `polygons` (positional) | `polygons` | The conductor boundaries: each an (n, 2) array of vertices in m, strictly convex, without a closing duplicate. |
| `box_size` (keyword) | `width`, `height` | The rectangle's two side lengths (width, height) in m; the rectangle is [0, width] × [0, height], as `box_size` of `galerkin.cavity` starts at the origin in 3D. For the two-ground solvers the height is the separation of the grounded planes. |
| `panels_per_edge`, `ground_modes`, `interpolation_degree` | same | Discretization counts; the defaults are the internal solver's. `solve_two_ground_rectangle` and `solve_two_ground_rectangle_edges` still check `ground_modes` (an integer in 64–4096), so existing calls and stored controls keep working, but their results do not depend on it: the grounded planes' current Gram is integrated in physical space. The corner solvers still use it as their Fourier count. |
| `ground_indices` | `grounds` | `solve_open_rectangle`: the indices into `polygons` of the conductors held at zero potential. |
| `signal_indices` | `signals` | `solve_two_ground_harmonic_corner_guard_edges`: two ordered indices of the active conductors. |
| `signal_index` | `signal` | `solve_two_ground_harmonic_corner_single_active_edges`: the index of the active conductor. |

`box_size` must hold exactly two finite positive numbers (a sequence or an array
of shape (2,)); otherwise the call raises `ValueError` naming `box_size`. Refusals
from the internal solvers name the public arguments (`box_size`, `ground_indices`,
`signal_indices`, `signal_index`).

The registry has no single-length names for a rectangle's width or height, and
`box_size` is the registry's name for the side lengths of an axis-aligned box with
one corner at the origin, so the panel API uses it rather than adding two names.
`polygons`, the counts and the conductor indices are structural names, scoped to
this module (`tests/_support/api_units_structural.json`).

## Results

The four result classes, `RectangleBoundaryResult`, `TwoGroundRectangleResult`,
`TwoGroundRectangleEdgesResult` (all edge solvers) and `OpenRectangleResult`, are
the internal modules' frozen records, re-exported unchanged and listed as result
classes of the units scan. `capacitance_per_permittivity` is the capacitance matrix
per unit depth divided by the absolute permittivity of the homogeneous medium: it is
dimensionless, and multiplying it by the permittivity in F/m gives the capacitance
per length in F/m. The field names stay as they are until the result-surface check
(P3-11).

## Validation

`tests/galerkin/test_panel_electrostatics.py` runs the six fast solvers through the
public function and the internal solver on the same inputs and requires every array
of the results to be equal byte for byte. For all nine solvers it checks that the
internal solver receives the caller's own `polygons`, width, height and counts (the
same objects), and that the defaults match. The three harmonic corner solvers take
about 27 s each at their smallest admitted size, so their numerical results are not
run twice there; their own tests, linked above, run them. The physics validation is
the internal solvers' and is not repeated.
