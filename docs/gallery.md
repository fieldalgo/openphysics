# Example gallery

**English** | [한국어](locales/ko/pages/gallery.md)

Three small examples, each drawn by one script from inputs in this repository.
They show what the features produce. They are not acceptance evidence: each
item links to the validation report that holds the fixed gates.

Regenerate every picture from the repository root, after the
[installation](overview.md) with the test extra (`galerkin-refsol`) and, for the
ParaView output, the export extra (`meshio`):

```bash
python packages/simcase/examples/gallery.py gallery-out
```

The output directory must be new or empty. The script also writes
`gallery.json` with the numbers quoted below; `--quick` uses coarse meshes and
is what the test suite runs. The pictures here were produced on Linux with
Python 3.12, NumPy 2.5, SciPy 1.18, Matplotlib 3.11 and Pillow 12.3.

## Transient heat in a plate

![Temperature of an internally heated plate over 60 s](gallery/heated_plate.webp)

A 10 cm square plate with uniform internal heating of 2 MW/m³. The left and
bottom edges are held at 300 K and the other two edges are insulated; the plate
starts at 300 K. The conductivity 237 W/(m K) and volumetric heat capacity
2.42 MJ/(m³ K) are typical handbook values for aluminium, used as approximate
example inputs. The 32 × 32 mesh is solved at 81 stored times up to 60 s; the
far corner reaches 323.3 K (+23.3 K) and is still rising slowly.

- Input: [`gallery_heated_plate.json`](../packages/simcase/examples/gallery_heated_plate.json)
  (`thermal.transient2d`). A [still of the last frame](gallery/heated_plate.png)
  is also kept.
- With `meshio` installed the script also writes
  `heated_plate_paraview/fields.pvd`, the same result as a ParaView time series
  (see [Viewing in ParaView](../packages/simcase/docs/overview.md#viewing-in-paraview)).
- Validation: [transient heat validation](../packages/galerkin/docs/transient_heat_validation.md).
  This particular case was not checked for mesh or time-step convergence.

## Coaxial electrostatics and mesh convergence

![Potential between coaxial conductors and the L2 error under refinement](gallery/coax.png)

The potential between an inner conductor (radius 1, 1 V) and an outer conductor
(radius 3, 0 V) has the exact solution V = ln(3/r)/ln 3. The script solves it with
P1 elements on four meshes and plots the L2 error against the radial element
size. The error falls from 2.4 × 10⁻² to 4.1 × 10⁻⁴ and the last rate is 1.99,
matching the expected second order.

- Inputs: Python API (`annulus_mesh`, `assemble_stiffness`, `solve_dirichlet`,
  `l2_error`), as in [`coax_convergence.py`](../packages/galerkin/examples/coax_convergence.py).
- Validation: milestone M1 in [solver validation](../packages/galerkin/docs/milestone_validation.md).

## Modes of a 3D box cavity

![Electric field magnitude of four cavity modes on the mid-plane](gallery/box_cavity.png)

A vacuum box of 1 × 0.6 × 0.4 m with perfectly conducting walls, meshed with
30 × 18 × 12 subdivisions, and the four modes nearest 300 MHz. The panels show
|E| averaged over the tetrahedra crossing the mid-plane z = 0.2 m, normalized per
mode. The box sides differ, so these four modes are not degenerate. Their
frequencies are compared with the analytical box modes from `galerkin-refsol`:

| Mode (m, n, p) | Computed [MHz] | Analytical [MHz] | Relative difference |
|---|---|---|---|
| (1, 1, 0) | 291.27 | 291.35 | −0.027% |
| (2, 1, 0) | 390.13 | 390.24 | −0.030% |
| (1, 0, 1) | 403.26 | 403.61 | −0.086% |
| (0, 1, 1) | 450.13 | 450.38 | −0.056% |

- Input: [`gallery_box_cavity.json`](../packages/simcase/examples/gallery_box_cavity.json)
  (`em.cavity3d`, `near_target` search; see its
  [search semantics](../packages/simcase/docs/cavity3d.md#search-and-failure-semantics)).
- Validation: [cavity API, units and convergence](../packages/galerkin/docs/cavity_solver.md).

## Limits

- The script guards against a broken picture: the heated plate must warm up, the
  coax rate must exceed 1.8 and the cavity frequencies must agree within 1%.
  These are not the validation thresholds.
- Region-material results are not in the gallery: the ParaView export does not
  yet accept region layouts.
- Picture files are listed in the [asset inventory](assets.md).
