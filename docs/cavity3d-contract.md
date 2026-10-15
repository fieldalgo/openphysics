# Vacuum PEC box cavity contract

## Scope and public entry point

First implementation: vacuum rectangular box, all six walls PEC, one study point.
No dielectric loading, loss, open boundaries, arbitrary CAD, sweep, or 3D Studio renderer.
No new runtime dependencies.

`galerkin.solve_cavity_box(lengths_m, subdivisions, *, num_modes=6, target_frequency_hz)`
takes three finite positive SI lengths and three positive integer subdivision counts.
The target is mandatory, finite and positive. The speed of light is 299792458 m/s.

Search is `near_target`: select physical candidate modes nearest the target in
squared wave number (equivalently squared frequency), then return them in ascending
frequency order. This is a target-near finite candidate search, not a promise of a
complete lowest spectrum or of all modes in an interval. Retain multiplicities;
never deduplicate eigenvalues. A requested count can cut a degenerate cluster,
whose basis and signs are not unique. Insufficient valid candidates, nonconvergence
or failed residual/orthogonality checks raise RuntimeError with no partial result.
Invalid arguments raise ValueError. Selection and numerical tolerances must be
documented alongside the implementation.

## Result and units

`CavityResult` carries:
- `mesh`: nodes in SI metres, tetrahedral connectivity; `space`: oriented edge space.
- `frequencies_hz[K]`, `eigenvalues_m2[K]` (squared wave numbers, m^-2).
- `edge_coefficients[E,K]`: full edge vectors including exact zero PEC edges.
- `electric_field[K,T,3]`: reconstructed vector at each tetrahedron centroid.
- `relative_residuals[K]`, `pec_edge_ids`, `requested_modes`,
  `target_frequency_hz`, `search="near_target"`.

Let M_SI be the vacuum edge mass matrix assembled on the SI mesh. Returned Q obeys
Q^T M_SI Q = I. Thus line-integral edge coefficients have units m^-1/2 and centroid
electric vectors m^-3/2 under this arbitrary mass normalization; these are not
physical V or V/m amplitudes. Coordinates are normalized internally with
L=max(lengths_m): q_SI=q_normalized/sqrt(L), k²_SI=k²_normalized/L².
Topology, edge orientation, coordinates, field location and these units must
survive JSON/NPZ serialization.

On the free-edge system the relative residual is
||S q - lambda M q||_2 / (||S q||_2 + |lambda| ||M q||_2), with limit 1e-8.
The kernel screen is 1e-8 times the analytic fundamental squared wave number
in normalized box coordinates, independent of target magnitude. Selected-mode
mass orthogonality has max absolute error <=1e-7. Tiny positive numerical kernel
eigenvalues are not physical modes.

## simcase document and result

Keep the existing JSON format key/version. Physics type is `em.cavity3d`.
Require `units.length`, a six-bound geometry.domain
(xmin/xmax/ymin/ymax/zmin/zmax), vacuum background, no shapes/custom materials,
`mesh.subdivisions=[nx,ny,nz]`, and `study.type="single"`.
The physics block declares `boundary="pec"`, `num_modes`,
`search="near_target"`, and `target_frequency_hz`.
The frequency field name explicitly fixes Hz; lengths follow units.length.
Do not inherit 2D wavelength/formulation or mesh-size defaults into 3D.

Convert domain dimensions and translation to SI before producing the result.
JSON/NPZ expose SI nodes with mesh_length_unit="m", tetrahedra/edge topology and
PEC IDs, frequencies_hz, eigenvalues_m2, full edge coefficients, centroid vector
fields, residuals, requested/returned counts, search, target and normalization.
Do not represent 3D results as 2D nodal scalar fields or neff.
The run() entry point dispatches cavity documents. Existing 2D stage APIs must
reject unsupported cavity calls explicitly. CLI example/validate/run/save works.
No cavity plot is required; explicit unsupported plotting requests fail clearly.
Studio stays 2D, hides cavity examples and rejects cavity mesh/run requests clearly.

## Independent acceptance

Compare analytic finite-frequency-cutoff enumeration and TE/TM counting.
Check physical-mode counts and multiplicity, distinct mass-orthogonal vectors,
PEC edge/tangential boundary, recomputed residuals, gradient-kernel exclusion,
mesh convergence, physical scaling and document-unit representation invariance.
Check malformed/unsupported input and insufficient-mode policy. Exercise CLI,
JSON/NPZ round trips, existing 2D regressions, full source tests and built-wheel
behavior on the integrated commit. Report passed/failed/skipped/unrun separately.
An independent reference cutoff guarantee does not imply production search completeness.

