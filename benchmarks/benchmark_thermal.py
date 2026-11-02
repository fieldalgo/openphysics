# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Time steady and transient 2D heat conduction in fresh processes; run from the repository root."""

import argparse
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _harness as harness  # noqa: E402

CASES = ("steady", "steady_regions", "transient", "document")
METRICS = ("mesh_seconds", "stiffness_assembly_seconds", "mass_assembly_seconds",
           "load_assembly_seconds", "dirichlet_solve_seconds", "solver_call_seconds",
           "seconds_per_step", "run_seconds")
WIDTH, HEIGHT = 1.0, 0.5
CONDUCTIVITY, CAPACITY, SOURCE = 2.0, 4.0, 1e3
HOT, AMBIENT, FILM = 350.0, 300.0, 5.0


def mesh_of(n):
    from galerkin import rectangle_mesh

    return rectangle_mesh(WIDTH, HEIGHT, 2 * n, n)


def left_nodes(mesh):
    return [int(i) for i in mesh.boundary["left"]]


def free_residual(residual, fixed):
    """Largest residual entry away from the Dirichlet nodes, where it is the reaction."""
    import numpy as np

    free = np.ones(residual.shape[-1], dtype=bool)
    free[list(fixed)] = False
    return float(np.max(np.abs(residual[..., free])))


def assembly_breakdown(mesh, conductivity):
    """Public assembly functions and the Dirichlet-only linear solve on the same mesh."""
    from galerkin import assemble_load, assemble_mass, assemble_stiffness, solve_dirichlet

    stiffness, k_seconds = harness.timed(assemble_stiffness, mesh, conductivity)
    _, m_seconds = harness.timed(assemble_mass, mesh, CAPACITY)
    load, f_seconds = harness.timed(assemble_load, mesh, SOURCE)
    _, solve_seconds = harness.timed(solve_dirichlet, stiffness, load, {tuple(left_nodes(mesh)): HOT})
    return dict(stiffness_assembly_seconds=k_seconds, mass_assembly_seconds=m_seconds,
                load_assembly_seconds=f_seconds, dirichlet_solve_seconds=solve_seconds,
                stiffness_nonzeros=int(stiffness.nnz))


def steady(n, steps):
    import numpy as np
    from galerkin.thermal import solve_steady_heat

    mesh, mesh_seconds = harness.timed(mesh_of, n)
    sample = dict(nodes=mesh.num_nodes, triangles=mesh.num_triangles, mesh_seconds=mesh_seconds)
    sample.update(assembly_breakdown(mesh, CONDUCTIVITY))
    result, seconds = harness.timed(
        solve_steady_heat, mesh, conductivity=CONDUCTIVITY,
        dirichlet={i: HOT for i in left_nodes(mesh)}, heat_source=SOURCE,
        convection={"right": (FILM, AMBIENT)})
    sample.update(harness.peak_rss())
    sample.update(solver_call_seconds=seconds,
                  temperature_min_k=float(result.temperature.min()),
                  temperature_max_k=float(result.temperature.max()),
                  max_abs_free_residual_w_per_m=free_residual(result.residual, left_nodes(mesh)))
    return sample


def steady_regions(n, steps):
    """Four conductivity layers across the width, piecewise constant on the mesh."""
    import numpy as np
    from galerkin.mesh import layered_rectangle_mesh
    from galerkin.thermal import solve_steady_heat

    layers = 4
    names = [f"layer{i}" for i in range(layers)]
    conductivity = {name: CONDUCTIVITY * (1 + i) for i, name in enumerate(names)}
    mesh, mesh_seconds = harness.timed(
        layered_rectangle_mesh, [WIDTH * (i + 1) / layers for i in range(layers)], HEIGHT,
        max(1, (2 * n) // layers), n)
    sample = dict(nodes=mesh.num_nodes, triangles=mesh.num_triangles, mesh_seconds=mesh_seconds,
                  regions=layers)
    per_cell = np.array([conductivity[names[r]] for r in mesh.regions])
    sample.update(assembly_breakdown(mesh, per_cell))
    result, seconds = harness.timed(
        solve_steady_heat, mesh, conductivity=conductivity,
        dirichlet={i: HOT for i in left_nodes(mesh)}, heat_source=SOURCE,
        convection={"right": (FILM, AMBIENT)})
    sample.update(harness.peak_rss())
    sample.update(solver_call_seconds=seconds,
                  temperature_min_k=float(result.temperature.min()),
                  temperature_max_k=float(result.temperature.max()),
                  max_abs_free_residual_w_per_m=free_residual(result.residual, left_nodes(mesh)))
    return sample


def transient(n, steps):
    import numpy as np
    from galerkin.transient_heat import solve_transient_heat

    mesh, mesh_seconds = harness.timed(mesh_of, n)
    sample = dict(nodes=mesh.num_nodes, triangles=mesh.num_triangles, mesh_seconds=mesh_seconds,
                  steps=steps)
    sample.update(assembly_breakdown(mesh, CONDUCTIVITY))
    times = np.linspace(0.0, 1.0, steps + 1)
    initial = np.full(mesh.num_nodes, AMBIENT)
    initial[left_nodes(mesh)] = HOT  # the initial field must satisfy the Dirichlet data
    result, seconds = harness.timed(
        solve_transient_heat, mesh, conductivity=CONDUCTIVITY, volumetric_heat_capacity=CAPACITY,
        time_s=times, initial_temperature_k=initial,
        dirichlet={i: HOT for i in left_nodes(mesh)}, heat_source=SOURCE)
    sample.update(harness.peak_rss())
    sample.update(solver_call_seconds=seconds, seconds_per_step=seconds / steps,
                  history_bytes=int(result.temperature_k.nbytes + result.heat_flux_w_m2.nbytes),
                  final_temperature_max_k=float(result.temperature_k[-1].max()),
                  max_abs_free_residual_w_per_m=free_residual(result.residual_w_per_m, left_nodes(mesh)))
    return sample


def document(n, steps):
    """The headless simcase runner on the shipped steady boundary example, resized."""
    import copy

    from simcase import Document, examples, run

    data = copy.deepcopy(examples.THERMAL_BOUNDARY)
    data["mesh"]["subdivisions"] = [2 * n, n]
    result, seconds = harness.timed(run, Document.from_dict(data), verbose=False)
    sample = harness.peak_rss()
    temperature = result.solution.temperature
    sample.update(run_seconds=seconds, timings=dict(result.timings),
                  nodes=int(result.mesh.num_nodes), triangles=int(result.mesh.num_triangles),
                  temperature_min_k=float(temperature.min()), temperature_max_k=float(temperature.max()))
    return sample


MEASURE = dict(steady=steady, steady_regions=steady_regions, transient=transient, document=document)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", choices=CASES, help="repeat to select cases; default: all")
    parser.add_argument("--sizes", type=int, nargs="+", default=[16, 32, 64, 128],
                        help="n: a 2n x n cell rectangle, 1 m x 0.5 m")
    parser.add_argument("--steps", type=int, default=50, help="transient time steps over 1 s")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=float, default=600)
    parser.add_argument("--output", type=Path, help="new JSON file; checkpoints after each worker")
    parser.add_argument("--worker", choices=CASES, help=argparse.SUPPRESS)
    parser.add_argument("--size", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if min([args.repeats, args.steps, *args.sizes]) < 1:
        parser.error("sizes, steps and repeats must be positive")
    if not math.isfinite(args.timeout_seconds) or args.timeout_seconds <= 0:
        parser.error("timeout-seconds must be finite and positive")
    if args.worker:
        if args.size is None:
            parser.error("worker requires --size")
        labels = dict(case=args.worker, size=args.size)
        return harness.print_worker(harness.worker(
            lambda: MEASURE[args.worker](args.size, args.steps), labels))
    cases = args.case or list(CASES)
    if len(set(cases)) != len(cases) or len(set(args.sizes)) != len(args.sizes):
        parser.error("duplicate cases/sizes: use --repeats for repetitions")
    harness.reserve_output(parser, args.output)
    jobs = [(dict(case=case, size=size), ["--worker", case, "--size", str(size), "--steps", str(args.steps)])
            for size in args.sizes for case in cases]
    settings = dict(cases=cases, sizes=args.sizes, steps=args.steps, width_m=WIDTH, height_m=HEIGHT,
                    conductivity_w_mk=CONDUCTIVITY, volumetric_heat_capacity_j_m3k=CAPACITY,
                    heat_source_w_m3=SOURCE, hot_k=HOT, ambient_k=AMBIENT, film_w_m2k=FILM)
    return harness.run_parent(__file__, args.output, jobs, args.repeats, args.timeout_seconds,
                              settings, ("case", "size"), METRICS)


if __name__ == "__main__":
    raise SystemExit(main())
