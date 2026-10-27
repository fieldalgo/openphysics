# galerkin — the OpenPhysics finite-element engine

**English** | [한국어](../../locales/ko/pages/packages/galerkin/overview.md)

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
| 2D electrostatics and frequency-domain waves with absorbing boundaries or a cylindrical PML | `assemble_stiffness`, `solve_dirichlet`, `radial_pml_coeffs` | [Milestone validation](milestone_validation.md) | `examples/galerkin/coax_convergence.py`, `examples/galerkin/cylinder_scattering_pml.py` |
| Waveguide cutoffs and dielectric waveguide modes: scalar P1 and full-vector mixed Nédélec/nodal | `solve_modes` | [Eigenspace reliability](eigenspace_reliability.md), [milestone validation](milestone_validation.md) | `examples/galerkin/fiber_modes.py`, `examples/galerkin/waveguide_modes.py` |
| 3D vacuum rectangular PEC cavity eigenmodes, SI frequencies and raw edge fields | `solve_cavity_box` | [Cavity API](cavity_solver.md) | `examples/galerkin/cavity_modes.py` |
| 3D rectangular cavity with lossy box-shaped dielectric/magnetic regions and finite-conductivity walls: complex frequencies and Q | `solve_material_cavity_box` | [Material cavity](material_cavity.md) | — |
| Steady 2D heat conduction, isotropic, Dirichlet and insulated boundaries | `galerkin.thermal.solve_steady_heat` | [Contract](thermal_steady2d.md), [validation](thermal_independent_validation.md) | [thermal_steady2d.py](../../../examples/galerkin/thermal_steady2d.py) |
| Same-mesh steady electric to heat (one-way) | `galerkin.joule_heating.solve_steady_joule_heat` | [API, units and validation](joule_heating.md) | [joule_heating.py](../../../examples/galerkin/joule_heating.py) |
| Prescribed outward flux and Robin convection for steady heat | `galerkin.thermal.solve_steady_heat` | [Contract](thermal_flux_robin.md), [validation](thermal_flux_robin_independent_validation.md) | [thermal_flux_robin.py](../../../examples/galerkin/thermal_flux_robin.py) |
| Derivatives with respect to materials, sources and boundary values on JAX or PyTorch: steady and transient heat, steady electric conduction, elasticity, thermoelasticity, and waveguide eigenvalues and fields | `solve_steady_heat`, `solve_steady_electric`, `solve_transient_heat`, `solve_elasticity`, `solve_thermoelasticity`, `solve_modes` with JAX or PyTorch inputs | [Contract and validation](differentiation.md) | — |
| Transient 2D heat: fixed P1, consistent mass, backward Euler, time-dependent Dirichlet and insulation | `galerkin.transient_heat.solve_transient_heat` | [Contract](transient_heat.md), [validation](transient_heat_validation.md), [independent validation](transient_heat_independent_validation.md) | [transient_heat_convergence.py](../../../examples/galerkin/transient_heat_convergence.py) |
| Static 2D linear elasticity, plane stress or plane strain | `galerkin.elasticity.solve_elasticity` | [Contract](elasticity2d.md), [validation](elasticity2d_independent_validation.md) | [elasticity2d.py](../../../examples/galerkin/elasticity2d.py) |
| Global Cartesian boundary traction for elasticity | `galerkin.elasticity.solve_elasticity` | [Contract](elasticity_traction.md), [validation](elasticity_traction_independent_validation.md) | [elasticity_traction.py](../../../examples/galerkin/elasticity_traction.py) |
| Mechanics under a prescribed same-mesh nodal Kelvin field | `galerkin.thermoelasticity.solve_thermoelasticity` | [Contract](prescribed_temperature_thermoelasticity.md), [validation](prescribed_temperature_thermoelasticity_independent_validation.md) | [prescribed_temperature_thermoelasticity.py](../../../examples/galerkin/prescribed_temperature_thermoelasticity.py) |
| Total traction on the prescribed-temperature mechanical stage | `galerkin.thermoelasticity.solve_thermoelasticity` | [Contract](thermoelastic_traction.md), [validation](thermoelastic_traction_independent_validation.md) | [thermoelastic_traction.py](../../../examples/galerkin/thermoelastic_traction.py) |
| Steady heat, then mechanics on the same mesh (one-way) | `galerkin.thermal_mechanical.solve_steady_thermoelasticity` | [Contract](thermal_mechanical_workflow.md), [validation](thermal_mechanical_independent_validation.md) | [thermal_mechanical_workflow.py](../../../examples/galerkin/thermal_mechanical_workflow.py) |
| Quasistatic mechanics at selected stored transient-heat times (one-way) | `galerkin.transient_thermal_mechanical.solve_transient_thermoelasticity` | [Contract](transient_thermal_mechanical.md) | [transient_thermal_mechanical.py](../../../examples/galerkin/transient_thermal_mechanical.py) |
| Piecewise-constant materials on named mesh regions for steady and transient heat, elasticity, thermoelasticity and both heat-to-mechanics workflows | `{region name: value}` in place of a scalar k, c, Q, E, nu or alpha | [Contract and validation](multimaterial.md) | — |
| Public-reference benchmarks: Timoshenko (1925) bimetal strip and NAFEMS T4 | existing heat and mechanical stages; references `refsol.bimetal`, `refsol.thermal_convection` | [Validation](public_benchmarks.md) | [public_benchmarks.py](../../../examples/galerkin/public_benchmarks.py) |

Units follow each contract: SI metres, seconds and Kelvin for heat and
mechanics; heat flow per depth W/m, mechanical force per depth N/m and physical
elastic energy per depth J/m. Vector modes retain complex transverse and
longitudinal coefficients, including degenerate eigenspace directions; read the
eigenspace reliability contract before converting fields to real values.

The [simcase](https://github.com/fieldalgo/openphysics/blob/main/packages/simcase/README.md)
package wraps some of these solvers as JSON documents: 2D modes, the box cavity
(vacuum PEC or lossy materials and walls) and steady and transient heat
(rectangular or with material regions). Python-only capabilities do not
automatically appear there.

## Limits

- Heat-to-mechanics coupling is one-way and explicit, with no feedback to heat.
  The steady workflow accepts Dirichlet/insulated heat only; it does not take
  the separate flux/Robin or traction extensions.
- Transient heat has no flux/Robin input, restart or automatic coupling.
  Finite negative Kelvin is not clamped by the linear API.
- Heat and elastic materials are isotropic and constant within each named mesh
  region ([multimaterial](multimaterial.md)); these thermal and elastic coefficients do not vary with temperature.
  The separate [Joule workflow](temperature_joule_heating.md)
  supports bounded temperature-dependent isotropic electrical conductivity. Mechanics is linear and small-strain. The traction
  APIs take global Cartesian loads; there is no dedicated scalar-pressure,
  local-frame or follower-load API.
- `solve_cavity_box` handles a vacuum rectangular PEC box;
  `solve_material_cavity_box` adds box-shaped lossy regions and
  finite-conductivity walls. Read their contracts for near-target search
  limitations.
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
```

The analytical, convergence and independent-validation tests, the examples
and the documentation are outside the package, at the repository root:
`tests/galerkin/`, `examples/galerkin/` and `docs/packages/galerkin/`.

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
# Install the full local test stack using the repository README.md, then:
python -m pytest -q tests/galerkin
python -m pytest -q tests/galerkin -m "not slow"
```

Run all commands from the repository root. An editable install puts `galerkin`
on the path, so the tests and examples run without setting `PYTHONPATH`.

The examples keep their own analytical solutions so they run without the test
extra; two tests check those independent implementations against refsol so the
pair cannot drift apart. The measurements recorded while the electromagnetic and
cavity solvers were built are in the [milestone validation](milestone_validation.md)
page.

## Run

```bash
python examples/galerkin/coax_convergence.py        # electrostatics convergence
python examples/galerkin/waveguide_convergence.py   # Helmholtz convergence
python examples/galerkin/cylinder_scattering.py     # cylinder scattering
python examples/galerkin/cylinder_scattering_pml.py # ABC vs PML
python examples/galerkin/waveguide_modes.py         # waveguide cutoff eigenmodes
python examples/galerkin/fiber_modes.py             # step-index fibre vector modes
python examples/galerkin/cavity_modes.py            # 3D PEC cavity
python examples/galerkin/mesh_io.py                 # Gmsh reader
python examples/galerkin/thermal_steady2d.py        # steady heat
python examples/galerkin/elasticity_traction.py     # elasticity with traction
python examples/galerkin/thermoelastic_traction.py  # prescribed-temperature mechanics
python examples/galerkin/visualize.py               # figures
```

## License

Apache License 2.0 - see [LICENSE](../../../packages/galerkin/LICENSE) and [NOTICE](../../../packages/galerkin/NOTICE).

Copyright 2026 Yongha Kim (FieldAlgo)

Gmsh is a separate program under GPL-2.0-or-later. It is neither distributed
with this engine nor linked into it: `galerkin.gmsh` is an independent parser
for the published MSH ASCII formats, and Gmsh itself, when used at all, is run
as a separate executable. The GPL therefore does not extend to `galerkin` or to
code that uses it.

This project is not affiliated with, endorsed by, or supported by the Gmsh
project.

[Steady electric conduction: Python API, Joule heat and Neumann gauges](electric_steady2d.md).
