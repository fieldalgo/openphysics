# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Time steady electric conduction, Joule heating and the temperature-dependent Joule solve; run from the repository root."""

import argparse
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _harness as harness  # noqa: E402

CASES = ("conduction", "joule", "thermistor_picard", "thermistor_newton")
METRICS = ("mesh_seconds", "stiffness_assembly_seconds", "dirichlet_solve_seconds",
           "electric_seconds", "heat_seconds", "solver_call_seconds", "seconds_per_iteration")
WIDTH, HEIGHT = 0.02, 0.01                      # m, the Joule tutorial's strip
SIGMA, VOLTAGE, THERMAL_CONDUCTIVITY, WALL = 3.0, 2.0, 5.0, 300.0
THERMISTOR_WIDTH, THERMISTOR_HEIGHT = 1.0, 0.25  # m, the temperature-dependent tutorial
CURRENT_DENSITY, THERMISTOR_K, THERMISTOR_T = 1.0, 1.0, 300.0
ALPHA, RANGE = 0.5, (300.0, 400.0)               # rho(T) = 1 + alpha (T - 300) ohm m


def ends(mesh, left, right):
    data = {int(i): left for i in mesh.boundary["left"]}
    data.update({int(i): right for i in mesh.boundary["right"]})
    return data


def free_residual(residual, fixed):
    """Largest residual entry away from the Dirichlet nodes, where it is the reaction."""
    import numpy as np

    free = np.ones(residual.shape[-1], dtype=bool)
    free[list(fixed)] = False
    return float(np.max(np.abs(residual[..., free])))


def conduction(n, relaxation):
    import numpy as np
    from galerkin import assemble_stiffness, rectangle_mesh, solve_dirichlet
    from galerkin.electric import solve_steady_electric

    mesh, mesh_seconds = harness.timed(rectangle_mesh, WIDTH, HEIGHT, 2 * n, n)
    stiffness, k_seconds = harness.timed(assemble_stiffness, mesh, SIGMA)
    _, solve_seconds = harness.timed(
        solve_dirichlet, stiffness, np.zeros(mesh.num_nodes),
        {tuple(int(i) for i in mesh.boundary["left"]): 0.0,
         tuple(int(i) for i in mesh.boundary["right"]): VOLTAGE})
    result, seconds = harness.timed(
        solve_steady_electric, mesh, conductivity=SIGMA, dirichlet=ends(mesh, 0.0, VOLTAGE))
    sample = harness.peak_rss()
    sample.update(nodes=mesh.num_nodes, triangles=mesh.num_triangles, mesh_seconds=mesh_seconds,
                  stiffness_assembly_seconds=k_seconds, stiffness_nonzeros=int(stiffness.nnz),
                  dirichlet_solve_seconds=solve_seconds, solver_call_seconds=seconds,
                  joule_power_w_per_m=float(result.joule_power_per_length),
                  exact_joule_power_w_per_m=SIGMA * VOLTAGE**2 / WIDTH * HEIGHT,
                  max_abs_free_residual_a_per_m=free_residual(result.residual, ends(mesh, 0.0, VOLTAGE)))
    return sample


def joule(n, relaxation):
    """Explicit DC solve, then the same-mesh steady heat transfer, timed apart."""
    import numpy as np
    from galerkin import rectangle_mesh
    from galerkin.electric import solve_steady_electric
    from galerkin.joule_heating import solve_steady_joule_heat

    mesh, mesh_seconds = harness.timed(rectangle_mesh, WIDTH, HEIGHT, 2 * n, n)
    voltage = ends(mesh, 0.0, VOLTAGE)
    electrical, electric_seconds = harness.timed(
        solve_steady_electric, mesh, conductivity=SIGMA, dirichlet=voltage)
    result, heat_seconds = harness.timed(
        solve_steady_joule_heat, mesh, electrical_result=electrical,
        conductivity=THERMAL_CONDUCTIVITY, dirichlet={i: WALL for i in voltage})
    sample = harness.peak_rss()
    sample.update(nodes=mesh.num_nodes, triangles=mesh.num_triangles, mesh_seconds=mesh_seconds,
                  electric_seconds=electric_seconds, heat_seconds=heat_seconds,
                  source_power_w_per_m=float(result.source_power_per_length),
                  outward_heat_w_per_m=float(result.outward_heat_per_length),
                  temperature_max_k=float(result.thermal.temperature.max()),
                  max_abs_free_heat_residual_w_per_m=free_residual(result.thermal.residual, voltage))
    return sample


def thermistor(n, relaxation, method):
    """The current-driven thermistor of the temperature-dependent Joule tutorial."""
    import numpy as np
    from galerkin import rectangle_mesh
    from galerkin.temperature_joule_heating import ConductivityModel, solve_temperature_joule_heat

    mesh, mesh_seconds = harness.timed(rectangle_mesh, THERMISTOR_WIDTH, THERMISTOR_HEIGHT, 4 * n, n)
    model = ConductivityModel(lambda t: 1 / (1 + ALPHA * (t - 300.0)), RANGE,
                              derivative=lambda t: -ALPHA / (1 + ALPHA * (t - 300.0))**2)
    left = {int(i): 0.0 for i in mesh.boundary["left"]}
    result, seconds = harness.timed(
        solve_temperature_joule_heat, mesh, method=method, electrical_conductivity=model,
        thermal_conductivity=THERMISTOR_K, electric_dirichlet=left,
        outward_current={"right": CURRENT_DENSITY},
        thermal_dirichlet=ends(mesh, THERMISTOR_T, THERMISTOR_T),
        initial_temperature=THERMISTOR_T, relaxation=relaxation)
    sample = harness.peak_rss()
    last = result.history[-1]
    sample.update(nodes=mesh.num_nodes, triangles=mesh.num_triangles, mesh_seconds=mesh_seconds,
                  method=method, relaxation=relaxation, solver_call_seconds=seconds,
                  iterations=len(result.history), seconds_per_iteration=seconds / len(result.history),
                  temperature_max_k=float(result.coupled.thermal.temperature.max()),
                  joule_power_w_per_m=float(result.coupled.source_power_per_length),
                  final_temperature_defect_k=float(last.temperature_defect),
                  final_nonlinear_heat_residual=float(last.nonlinear_heat_residual))
    return sample


MEASURE = dict(conduction=conduction, joule=joule,
               thermistor_picard=lambda n, relaxation: thermistor(n, relaxation, "picard"),
               thermistor_newton=lambda n, relaxation: thermistor(n, relaxation, "newton"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", choices=CASES, help="repeat to select cases; default: all")
    parser.add_argument("--sizes", type=int, nargs="+", default=[8, 16, 32, 64],
                        help="n: 2n x n cells on the 20 mm x 10 mm strip, 4n x n on the 1 m x 0.25 m thermistor")
    parser.add_argument("--relaxation", type=float, default=1.0,
                        help="Picard relaxation of the thermistor (the tutorial's value); Newton ignores it")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=float, default=600)
    parser.add_argument("--output", type=Path, help="new JSON file; checkpoints after each worker")
    parser.add_argument("--worker", choices=CASES, help=argparse.SUPPRESS)
    parser.add_argument("--size", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if min([args.repeats, *args.sizes]) < 1:
        parser.error("sizes and repeats must be positive")
    if not 0 < args.relaxation <= 1:
        parser.error("relaxation must be in (0, 1]")
    if not math.isfinite(args.timeout_seconds) or args.timeout_seconds <= 0:
        parser.error("timeout-seconds must be finite and positive")
    if args.worker:
        if args.size is None:
            parser.error("worker requires --size")
        labels = dict(case=args.worker, size=args.size)
        return harness.print_worker(harness.worker(
            lambda: MEASURE[args.worker](args.size, args.relaxation), labels))
    cases = args.case or list(CASES)
    if len(set(cases)) != len(cases) or len(set(args.sizes)) != len(args.sizes):
        parser.error("duplicate cases/sizes: use --repeats for repetitions")
    harness.reserve_output(parser, args.output)
    jobs = [(dict(case=case, size=size),
             ["--worker", case, "--size", str(size), "--relaxation", str(args.relaxation)])
            for size in args.sizes for case in cases]
    settings = dict(cases=cases, sizes=args.sizes, strip_m=(WIDTH, HEIGHT), conductivity_s_m=SIGMA,
                    voltage_v=VOLTAGE, thermal_conductivity_w_mk=THERMAL_CONDUCTIVITY, wall_k=WALL,
                    thermistor_m=(THERMISTOR_WIDTH, THERMISTOR_HEIGHT), current_density_a_m2=CURRENT_DENSITY,
                    thermistor_conductivity_w_mk=THERMISTOR_K, thermistor_ends_k=THERMISTOR_T,
                    resistivity_slope_per_k=ALPHA, temperature_range_k=RANGE, relaxation=args.relaxation)
    return harness.run_parent(__file__, args.output, jobs, args.repeats, args.timeout_seconds,
                              settings, ("case", "size"), METRICS)


if __name__ == "__main__":
    raise SystemExit(main())
