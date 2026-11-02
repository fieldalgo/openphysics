# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Time 2D elasticity and the thermoelastic traction workflow in fresh processes; run from the repository root."""

import argparse
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _harness as harness  # noqa: E402

CASES = ("elasticity", "thermoelastic_traction", "workflow")
METRICS = ("mesh_seconds", "solver_call_seconds", "heat_seconds", "freeze_seconds",
           "mechanics_seconds", "workflow_seconds")
LENGTH, HEIGHT = 1.0, 0.25
YOUNG, POISSON, PLANE = 70e9, 0.3, "stress"
TRACTION = (1e6, 0.0)                 # Pa, on the right end
THERMAL_TRACTION = (8e6, 3e6)         # Pa, total traction on the right end
CONDUCTIVITY, COLD, HOT, REFERENCE = 50.0, 300.0, 350.0, 293.15
EXPANSION = 12e-6


def mesh_of(n):
    from galerkin import rectangle_mesh

    return rectangle_mesh(LENGTH, HEIGHT, 4 * n, n)


def clamp(mesh):
    """Both displacement components fixed on the left end."""
    return {(int(i), c): 0.0 for i in mesh.boundary["left"] for c in (0, 1)}


def thermal_ends(mesh):
    data = {int(i): COLD for i in mesh.boundary["left"]}
    data.update({int(i): HOT for i in mesh.boundary["right"]})
    return data


def residual_free(residual, dirichlet):
    """Largest residual entry on a free degree of freedom."""
    import numpy as np

    free = np.ones(residual.shape, dtype=bool)
    for node, component in dirichlet:
        free[node, component] = False
    return float(np.max(np.abs(residual[free])))


def elasticity(n):
    import numpy as np
    from galerkin.elasticity import solve_elasticity

    mesh, mesh_seconds = harness.timed(mesh_of, n)
    dirichlet = clamp(mesh)
    result, seconds = harness.timed(
        solve_elasticity, mesh, young_modulus=YOUNG, poisson_ratio=POISSON, plane=PLANE,
        dirichlet=dirichlet, traction={"right": TRACTION})
    sample = harness.peak_rss()
    right = [int(i) for i in mesh.boundary["right"]]
    sample.update(nodes=mesh.num_nodes, triangles=mesh.num_triangles, dofs=2 * mesh.num_nodes,
                  mesh_seconds=mesh_seconds, solver_call_seconds=seconds,
                  mean_end_displacement_m=float(np.mean(result.displacement[right, 0])),
                  bar_end_displacement_m=TRACTION[0] * LENGTH / YOUNG,  # uniaxial bar, for orientation only
                  max_abs_free_residual_n_per_m=residual_free(result.residual, dirichlet))
    return sample


def thermoelastic_traction(n):
    """Heat solve, frozen snapshot, then the prescribed-temperature mechanical stage, timed apart."""
    import numpy as np
    from galerkin.thermal import solve_steady_heat
    from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity

    mesh, mesh_seconds = harness.timed(mesh_of, n)
    heat, heat_seconds = harness.timed(
        solve_steady_heat, mesh, conductivity=CONDUCTIVITY, dirichlet=thermal_ends(mesh))
    snapshot, freeze_seconds = harness.timed(freeze_temperature, mesh, heat.temperature)
    dirichlet = clamp(mesh)
    result, mechanics_seconds = harness.timed(
        solve_thermoelasticity, mesh, snapshot, reference_temperature_k=REFERENCE,
        thermal_expansion_per_k=EXPANSION, young_modulus=YOUNG, poisson_ratio=POISSON,
        plane=PLANE, dirichlet=dirichlet, traction={"right": THERMAL_TRACTION})
    sample = harness.peak_rss()
    sample.update(nodes=mesh.num_nodes, triangles=mesh.num_triangles, dofs=2 * mesh.num_nodes,
                  mesh_seconds=mesh_seconds, heat_seconds=heat_seconds, freeze_seconds=freeze_seconds,
                  mechanics_seconds=mechanics_seconds,
                  temperature_max_k=float(heat.temperature.max()),
                  max_abs_displacement_m=float(np.max(np.abs(result.displacement))),
                  physical_elastic_energy_j_per_m=float(result.physical_elastic_energy),
                  max_abs_free_residual_n_per_m=residual_free(result.residual, dirichlet))
    return sample


def workflow(n):
    """The one-call steady heat -> thermoelastic workflow (zero natural traction)."""
    import numpy as np
    from galerkin.thermal_mechanical import solve_steady_thermoelasticity

    mesh, mesh_seconds = harness.timed(mesh_of, n)
    dirichlet = clamp(mesh)
    result, seconds = harness.timed(
        solve_steady_thermoelasticity, mesh, units={"length": "m", "temperature": "K"},
        conductivity=CONDUCTIVITY, thermal_dirichlet=thermal_ends(mesh), heat_source=0.0,
        young_modulus=YOUNG, poisson_ratio=POISSON, plane=PLANE,
        thermal_expansion_per_k=EXPANSION, reference_temperature_k=REFERENCE,
        mechanical_dirichlet=dirichlet)
    sample = harness.peak_rss()
    sample.update(nodes=mesh.num_nodes, triangles=mesh.num_triangles, dofs=2 * mesh.num_nodes,
                  mesh_seconds=mesh_seconds, workflow_seconds=seconds,
                  temperature_max_k=float(result.heat.temperature.max()),
                  max_abs_displacement_m=float(np.max(np.abs(result.mechanics.displacement))),
                  max_abs_free_residual_n_per_m=residual_free(result.mechanics.residual, dirichlet))
    return sample


MEASURE = dict(elasticity=elasticity, thermoelastic_traction=thermoelastic_traction, workflow=workflow)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", choices=CASES, help="repeat to select cases; default: all")
    parser.add_argument("--sizes", type=int, nargs="+", default=[8, 16, 32, 64],
                        help="n: a 4n x n cell bar, 1 m x 0.25 m")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=float, default=600)
    parser.add_argument("--output", type=Path, help="new JSON file; checkpoints after each worker")
    parser.add_argument("--worker", choices=CASES, help=argparse.SUPPRESS)
    parser.add_argument("--size", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if min([args.repeats, *args.sizes]) < 1:
        parser.error("sizes and repeats must be positive")
    if not math.isfinite(args.timeout_seconds) or args.timeout_seconds <= 0:
        parser.error("timeout-seconds must be finite and positive")
    if args.worker:
        if args.size is None:
            parser.error("worker requires --size")
        labels = dict(case=args.worker, size=args.size)
        return harness.print_worker(harness.worker(lambda: MEASURE[args.worker](args.size), labels))
    cases = args.case or list(CASES)
    if len(set(cases)) != len(cases) or len(set(args.sizes)) != len(args.sizes):
        parser.error("duplicate cases/sizes: use --repeats for repetitions")
    harness.reserve_output(parser, args.output)
    jobs = [(dict(case=case, size=size), ["--worker", case, "--size", str(size)])
            for size in args.sizes for case in cases]
    settings = dict(cases=cases, sizes=args.sizes, length_m=LENGTH, height_m=HEIGHT,
                    young_modulus_pa=YOUNG, poisson_ratio=POISSON, plane=PLANE,
                    traction_pa=TRACTION, thermal_traction_pa=THERMAL_TRACTION,
                    conductivity_w_mk=CONDUCTIVITY, cold_k=COLD, hot_k=HOT,
                    reference_temperature_k=REFERENCE, thermal_expansion_per_k=EXPANSION)
    return harness.run_parent(__file__, args.output, jobs, args.repeats, args.timeout_seconds,
                              settings, ("case", "size"), METRICS)


if __name__ == "__main__":
    raise SystemExit(main())
