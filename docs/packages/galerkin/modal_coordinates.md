# Modal complex coordinates

[한국어](../../locales/ko/pages/packages/galerkin/modal_coordinates.md)

The public route is `galerkin.ModalPML(*, pml_thickness={side: m}, pml_strength=3.0,
pml_order=2)` and `galerkin.Bend(*, bend_radius, bend_origin, bend_axis="x")`, passed as `pml=` and
`bend=` to `solve_waveguide_modes` (SI, exp(−iωt)): each given side's thickness is > 0 in metres (a side
without a layer is left out), the bend has no default origin and needs a layer, and the solver builds
the coordinate factors below on the metre mesh. In exp(−iωt) the stretch reads
`s = 1 + i pml_strength (depth/pml_thickness)**pml_order`; the factors keep the kernels' convention and
never reach the caller.

The low-level modal coordinate API (`galerkin.kernels.mode_coordinates`) uses `exp(+i omega t-i beta z)`.
`galerkin.mode_coordinates.mode_coordinates(mesh, thickness={"left": 1.0,
"right": 1.0}, strength=3.0, order=2)` returns centroid Jacobians
`(sx, sy, h)`, physical-region masks and bounds on the existing rectangular
mesh. Thicknesses use mesh length units. The domain includes the PML strips;
materials must extend through them. The polynomial stretch is
`s = 1 - i strength (depth/thickness)**order`, with order 2, 3 or 4.
The mesh must resolve both the physical window and the PML.

For a constant-radius bend, supply `bend_radius`, `bend_axis="x"` or `"y"`,
and `bend_origin`. The selected axis points outward, radius is positive at
that origin, and propagation distance is reference arc length `z=R theta`.
The entire domain must have positive radius. The metric is
`h=1+(q_tilde-bend_origin)/bend_radius`, including the integrated complex
coordinate inside PML. This is a constant-curvature model.

Pass `coordinates.factors` as `coordinate_factors` to
`galerkin.kernels.solve_modes` or `assemble_mode_system`. The vector formulation uses
the transformed permittivity **and permeability**, not an absorbing epsilon
alone. Returned edge/nodal coefficients are computational covariant fields;
outside PML the physical longitudinal field is `1j*ez/h`.
`solve_scalar_coordinates` returns complex indices and nodal fields for the
scalar Helmholtz approximation. It is exact for the invariant-axis TE slab
polarization, including a cylindrical bend, but is an approximation for a
fully two-dimensional high-contrast guide.

Both solvers use ordinary shift-invert for a complex, non-Hermitian pencil.
Amplitudes are arbitrary and candidates are not certified physical poles.
PML produces artificial modes; changing mesh, physical window, thickness and
strength independently is necessary. A single solve does not verify stability.
Passive forward poles have negative imaginary effective index. Total
attenuation includes absorption and radiation; it does not separate them.

`mode_coordinates`, `scalar_coordinate_system` and `solve_scalar_coordinates`
compute with NumPy and refuse JAX and PyTorch values with a `TypeError`;
derivatives with respect to the coordinates are not provided
([derivatives](differentiation.md)).

Current validation: independent outgoing TE/TM slab roots with material-aligned
mesh convergence and PML/window variation (`test_pml_modes.py`), and separate
scikit-fem assembly plus dense QZ for straight/bent scalar/vector pencils
(`test_crosscheck_skfem_pml_modes.py`). Same-discretization relative gate is
1e-9; agreement between assemblies does not establish physical convergence.
See the [document, Studio and tracking contract](../simcase/pml_modes.md).
