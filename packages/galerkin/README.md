# galerkin — the OpenPhysics finite-element engine

[Documentation](docs/overview.md)

[Suite documentation](https://github.com/fieldalgo/openphysics/blob/main/docs/README.md)

A finite-element solver engine written in pure Python (numpy + scipy.sparse),
built with an analytical-validation-first approach. It covers 2D
electromagnetics, 3D cavity eigenmodes, steady and transient 2D heat
conduction, static 2D elasticity and one-way heat-to-mechanics workflows. Its
only runtime dependencies are numpy and scipy.

## What it solves

Each standalone submodule is imported explicitly. Its contract defines units,
inputs, results and limits; its validation report records the independent
references and fixed thresholds.

| Problem | Entry point | Contract and validation | Example |
|---|---|---|---|
| 2D electrostatics and frequency-domain waves with absorbing boundaries or a cylindrical PML | `assemble_stiffness`, `solve_dirichlet`, `radial_pml_coeffs` | [Milestone validation](docs/milestone_validation.md) | `examples/coax_convergence.py`, `examples/cylinder_scattering_pml.py` |
| Waveguide cutoffs and dielectric waveguide modes: scalar P1 and full-vector mixed Nédélec/nodal | `solve_modes` | [Eigenspace reliability](docs/eigenspace_reliability.md), [milestone validation](docs/milestone_validation.md) | `examples/fiber_modes.py`, `examples/waveguide_modes.py` |
| 3D vacuum rectangular PEC cavity eigenmodes, SI frequencies and raw edge fields | `solve_cavity_box` | [Cavity API](docs/cavity_solver.md) | `examples/cavity_modes.py` |
| 3D rectangular cavity with lossy box-shaped dielectric/magnetic regions and finite-conductivity walls: complex frequencies and Q | `solve_material_cavity_box` | [Material cavity](docs/material_cavity.md) | — |
| Steady 2D heat conduction, isotropic, Dirichlet and insulated boundaries | `galerkin.thermal.solve_steady_heat` | [Contract](docs/thermal_steady2d.md), [validation](docs/thermal_independent_validation.md) | [thermal_steady2d.py](examples/thermal_steady2d.py) |
| Prescribed outward flux and Robin convection for steady heat | `galerkin.thermal.solve_steady_heat` | [Contract](docs/thermal_flux_robin.md), [validation](docs/thermal_flux_robin_independent_validation.md) | [thermal_flux_robin.py](examples/thermal_flux_robin.py) |
| Transient 2D heat: fixed P1, consistent mass, backward Euler, time-dependent Dirichlet and insulation | `galerkin.transient_heat.solve_transient_heat` | [Contract](docs/transient_heat.md), [validation](docs/transient_heat_validation.md), [independent validation](docs/transient_heat_independent_validation.md) | [transient_heat_convergence.py](examples/transient_heat_convergence.py) |
| Static 2D linear elasticity, plane stress or plane strain | `galerkin.elasticity.solve_elasticity` | [Contract](docs/elasticity2d.md), [validation](docs/elasticity2d_independent_validation.md) | [elasticity2d.py](examples/elasticity2d.py) |
| Global Cartesian boundary traction for elasticity | `galerkin.elasticity.solve_elasticity` | [Contract](docs/elasticity_traction.md), [validation](docs/elasticity_traction_independent_validation.md) | [elasticity_traction.py](examples/elasticity_traction.py) |
| Mechanics under a prescribed same-mesh nodal Kelvin field | `galerkin.thermoelasticity.solve_thermoelasticity` | [Contract](docs/prescribed_temperature_thermoelasticity.md), [validation](docs/prescribed_temperature_thermoelasticity_independent_validation.md) | [prescribed_temperature_thermoelasticity.py](examples/prescribed_temperature_thermoelasticity.py) |
| Total traction on the prescribed-temperature mechanical stage | `galerkin.thermoelasticity.solve_thermoelasticity` | [Contract](docs/thermoelastic_traction.md), [validation](docs/thermoelastic_traction_independent_validation.md) | [thermoelastic_traction.py](examples/thermoelastic_traction.py) |
| Steady heat, then mechanics on the same mesh (one-way) | `galerkin.thermal_mechanical.solve_steady_thermoelasticity` | [Contract](docs/thermal_mechanical_workflow.md), [validation](docs/thermal_mechanical_independent_validation.md) | [thermal_mechanical_workflow.py](examples/thermal_mechanical_workflow.py) |
| Quasistatic mechanics at selected stored transient-heat times (one-way) | `galerkin.transient_thermal_mechanical.solve_transient_thermoelasticity` | [Contract](docs/transient_thermal_mechanical.md) | [transient_thermal_mechanical.py](examples/transient_thermal_mechanical.py) |
| Piecewise-constant materials on named mesh regions for steady and transient heat, elasticity, thermoelasticity and both heat-to-mechanics workflows | `{region name: value}` in place of a scalar k, c, Q, E, nu or alpha | [Contract and validation](docs/multimaterial.md) | — |

Units follow each contract: SI metres, seconds and Kelvin for heat and
mechanics; heat flow per depth W/m, mechanical force per depth N/m and physical
elastic energy per depth J/m. Vector modes retain complex transverse and
longitudinal coefficients, including degenerate eigenspace directions; read the
eigenspace reliability contract before converting fields to real values.

The [simcase](https://github.com/fieldalgo/openphysics/blob/main/packages/simcase/README.md)
package wraps some of these solvers as JSON documents: 2D modes, the PEC cavity
and rectangular steady and transient heat. Python-only capabilities do not
automatically appear there.

## Limits

- Heat-to-mechanics coupling is one-way and explicit, with no feedback to heat.
  The steady workflow accepts Dirichlet/insulated heat only; it does not take
  the separate flux/Robin or traction extensions.
- Transient heat has no flux/Robin input, restart or automatic coupling.
  Finite negative Kelvin is not clamped by the linear API.
- Heat and elastic materials are isotropic and constant within each named mesh
  region ([multimaterial](docs/multimaterial.md)); there is no temperature-dependent
  or anisotropic material. Mechanics is linear and small-strain. The traction
  APIs take global Cartesian loads; there is no dedicated scalar-pressure,
  local-frame or follower-load API.
- The cavity solver handles a vacuum rectangular PEC box. Read its contract for
  near-target search limitations.
- The 3D sparse direct factorization is comfortable to about 25k edge degrees
  of freedom on four cores; larger problems need iterative solvers.

## Layout

```
src/galerkin/
  mesh.py         # Mesh data structure (boundary nodes + edges) + structured mesh generators
  assembly.py     # Stiffness K (scalar/tensor coefficients), mass M, boundary B, load vector
  solver.py       # Dirichlet reduction + scipy sparse direct solve (real/complex)
  postprocess.py  # E = -grad V, L2 error (complex-aware)
  pml.py          # Cylindrical PML coefficients (Collino-Monk complex stretching)
  edge.py         # Lowest-order Nédélec (Whitney) edge elements: numbering, signs, curl-curl, mass, edge-nodal coupling
  waveguide.py    # Mixed edge/nodal vector mode solver, A x = -beta^2 B x
  mesh3d.py       # Mesh3D + box_mesh (Kuhn subdivision, six tets per cube)
  assembly3d.py   # P1 tetrahedron stiffness (scalar/tensor) and mass, closed form
  edge3d.py       # Whitney edge elements on tetrahedra, all matrices closed form
  cavity.py       # Public vacuum PEC box solver, SI output and projected gradient kernel
  material_cavity.py # Box cavity with lossy materials and impedance walls: complex resonances and Q
  thermal.py      # Steady heat: Dirichlet, insulation, prescribed flux, Robin
  transient_heat.py               # Transient heat, backward Euler
  elasticity.py                   # Static plane stress/strain elasticity and traction
  thermoelasticity.py             # Mechanics under a prescribed temperature field
  thermal_mechanical.py           # Steady heat -> mechanics workflow
  transient_thermal_mechanical.py # Stored transient heat -> quasistatic mechanics
  gmsh.py         # Read/write Gmsh .msh (ASCII 2.2 and 4.1) — Gmsh never linked
  interop.py      # from_mesher: adapt a mesh built elsewhere (meshine, gmshio, ...)
examples/         # runnable examples and figure scripts
```

The analytical, convergence and independent-validation tests are in
`tests/galerkin/` at the repository root, outside the package.

`galerkin.from_mesher` adapts any object exposing `nodes`, `triangles` or
`tetrahedra`, `regions`, `region_names` and boundary edges or faces, and
`Mesh.by_region({"core": ..., "clad": ...})` turns region names into a
per-element material array. It is verified against meshine and gmshio; neither
is a dependency of the engine.

## Tests

The engine is graded against [galerkin-refsol](https://github.com/fieldalgo/openphysics/blob/main/packages/galerkin-refsol/README.md),
a separate package holding the closed-form and published reference solutions. It
shares this repository but stays an independent implementation: the reference
package does not import the solver it grades. `tests/galerkin/test_independence.py` enforces
that the engine never imports it, and that the engine's only dependencies stay
numpy and scipy.

```bash
# From the repository root
python -m pip install -e packages/galerkin   # engine only: numpy and scipy
# Install the full local test stack using ../../README.md, then:
python -m pytest -q tests/galerkin
python -m pytest -q tests/galerkin -m "not slow"
```

Run all commands from the repository root. An editable install puts `galerkin`
on the path, so the tests and examples run without setting `PYTHONPATH`.

The examples keep their own analytical solutions so they run without the test
extra; two tests check those independent implementations against refsol so the
pair cannot drift apart. The measurements recorded while the electromagnetic and
cavity solvers were built are in the [milestone validation](docs/milestone_validation.md)
page.

## Run

```bash
python packages/galerkin/examples/coax_convergence.py        # electrostatics convergence
python packages/galerkin/examples/waveguide_convergence.py   # Helmholtz convergence
python packages/galerkin/examples/cylinder_scattering.py     # cylinder scattering
python packages/galerkin/examples/cylinder_scattering_pml.py # ABC vs PML
python packages/galerkin/examples/waveguide_modes.py         # waveguide cutoff eigenmodes
python packages/galerkin/examples/fiber_modes.py             # step-index fibre vector modes
python packages/galerkin/examples/cavity_modes.py            # 3D PEC cavity
python packages/galerkin/examples/mesh_io.py                 # Gmsh reader
python packages/galerkin/examples/thermal_steady2d.py        # steady heat
python packages/galerkin/examples/elasticity_traction.py     # elasticity with traction
python packages/galerkin/examples/thermoelastic_traction.py  # prescribed-temperature mechanics
python packages/galerkin/examples/visualize.py               # figures
```

## License

Apache License 2.0 - see [LICENSE](LICENSE) and [NOTICE](NOTICE).

Copyright 2026 Yongha Kim (FieldAlgo)

Gmsh is a separate program under GPL-2.0-or-later. It is neither distributed
with this engine nor linked into it: `galerkin.gmsh` is an independent parser
for the published MSH ASCII formats, and Gmsh itself, when used at all, is run
as a separate executable. The GPL therefore does not extend to `galerkin` or to
code that uses it.

This project is not affiliated with, endorsed by, or supported by the Gmsh
project.
