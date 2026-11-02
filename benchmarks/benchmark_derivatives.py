# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Time forward solves against gradients (adjoint on JAX/PyTorch, central differences on NumPy); run from the repository root."""

import argparse
import math
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _harness as harness  # noqa: E402

CASES = ("heat", "transient", "elasticity")
BACKENDS = ("numpy", "jax", "torch")
METRICS = ("forward_seconds", "second_forward_seconds", "gradient_seconds", "backward_seconds",
           "gradient_to_forward_ratio")
RELATIVE_STEP = 1e-6          # central differences, as the gradient tests use
WIDTH, HEIGHT = 1.0, 0.5
HOT, AMBIENT, FILM = 350.0, 300.0, 5.0
# Each problem has four parameters; central differences need eight more solves.
PARAMETERS = dict(heat=dict(k0=2.0, k1=3.0, k2=4.0, k3=5.0),
                  transient=dict(k=2.5, c=4.0, q=8.0, t0=300.0),
                  elasticity=dict(young_modulus=70e9, poisson_ratio=0.3, traction_x=1e6, traction_y=2e5))


class Library:
    """The array library of one backend: lifting constants and reading numbers."""

    def __init__(self, name):
        self.name = name
        if name == "numpy":
            import numpy as np
            self.module = np
        elif name == "jax":
            try:
                import jax
            except ImportError as exc:
                raise harness.Skipped("jax is not installed (pip install 'galerkin[jax]')") from exc
            jax.config.update("jax_enable_x64", True)
            self.jax = jax
            self.module = jax.numpy
        elif name == "torch":
            try:
                import torch
            except ImportError as exc:
                raise harness.Skipped("torch is not installed (pip install 'galerkin[torch]')") from exc
            self.torch = torch
            self.module = torch
        else:
            raise ValueError(name)
        self.version = None if name == "numpy" else (self.jax if name == "jax" else self.torch).__version__

    def constant(self, array):
        """A NumPy array as a constant of this library, for use inside callbacks."""
        import numpy as np

        if self.name == "numpy":
            return np.asarray(array, dtype=float)
        if self.name == "jax":
            return self.module.asarray(np.asarray(array, dtype=float))
        return self.torch.as_tensor(np.asarray(array, dtype=float))

    def stack(self, values):
        if self.name == "numpy":
            return self.module.array(values, dtype=float)
        return self.module.stack(list(values))

    def number(self, value):
        return float(value.detach() if hasattr(value, "detach") else value)

    def inputs(self, values):
        """The parameter vector as live scalars of this library."""
        if self.name == "numpy":
            return [float(v) for v in values]
        if self.name == "jax":
            return [self.module.asarray(v, dtype=self.module.float64) for v in values]
        return [self.torch.tensor(v, dtype=self.torch.float64, requires_grad=True) for v in values]


def heat_problem(n, library):
    from galerkin.mesh import layered_rectangle_mesh
    from galerkin.thermal import solve_steady_heat

    layers = len(PARAMETERS["heat"])
    mesh = layered_rectangle_mesh([WIDTH * (i + 1) / layers for i in range(layers)], HEIGHT, n, n)
    left = [int(i) for i in mesh.boundary["left"]]
    right = [int(i) for i in mesh.boundary["right"]]

    def objective(*k):
        result = solve_steady_heat(mesh, conductivity={f"layer{i}": v for i, v in enumerate(k)},
                                   dirichlet={i: HOT for i in left}, convection={"right": (FILM, AMBIENT)})
        return library.module.mean(result.temperature[right])
    return mesh, objective, dict(objective="mean temperature of the right edge, K",
                                 parameters="conductivity of the four layers, W/(m K)")


def transient_problem(n, library, steps):
    import numpy as np
    from galerkin import rectangle_mesh
    from galerkin.transient_heat import solve_transient_heat

    mesh = rectangle_mesh(WIDTH, HEIGHT, 2 * n, n)
    left = [int(i) for i in mesh.boundary["left"]]
    right_half = np.flatnonzero(mesh.nodes[:, 0] > WIDTH / 2)
    times = np.linspace(0.0, 1.0, steps + 1)
    ones = library.constant(np.ones(mesh.num_nodes))

    def objective(k, c, q, t0):
        # The uniform initial field equals the left Dirichlet value, so no projection is needed.
        result = solve_transient_heat(
            mesh, conductivity=k, volumetric_heat_capacity=c, time_s=times,
            initial_temperature_k=t0 * ones, dirichlet={i: t0 for i in left},
            heat_source=lambda points, time_s: q * library.constant(1.0 + points[:, 0]))  # grows with x
        return library.module.mean(result.temperature_k[-1][right_half])
    return mesh, objective, dict(objective="mean final temperature of the right half, K",
                                 parameters="k, c, the source amplitude and the initial/left temperature",
                                 steps=steps)


def elasticity_problem(n, library):
    from galerkin import rectangle_mesh
    from galerkin.elasticity import solve_elasticity

    mesh = rectangle_mesh(1.0, 0.25, 4 * n, n)
    dirichlet = {(int(i), c): 0.0 for i in mesh.boundary["left"] for c in (0, 1)}
    right = [int(i) for i in mesh.boundary["right"]]

    def objective(e, nu, tx, ty):
        result = solve_elasticity(mesh, young_modulus=e, poisson_ratio=nu, plane="stress",
                                  dirichlet=dirichlet, traction={"right": library.stack((tx, ty))})
        return library.module.mean(result.displacement[right, 0])
    return mesh, objective, dict(objective="mean x displacement of the right end, m",
                                 parameters="E, nu and the two traction components on the right end")


def central_differences(objective, values):
    out = []
    for i, v in enumerate(values):
        h = RELATIVE_STEP * max(1.0, abs(v))
        up, down = list(values), list(values)
        up[i] += h
        down[i] -= h
        out.append((float(objective(*up)) - float(objective(*down))) / (2 * h))
    return out


def measure(case, n, backend, steps):
    library = Library(backend)
    names = list(PARAMETERS[case])
    values = [PARAMETERS[case][name] for name in names]
    if case == "heat":
        mesh, objective, about = heat_problem(n, library)
    elif case == "transient":
        mesh, objective, about = transient_problem(n, library, steps)
    else:
        mesh, objective, about = elasticity_problem(n, library)
    sample = dict(about, backend=backend, library_version=library.version,
                  nodes=mesh.num_nodes, triangles=mesh.num_triangles,
                  parameter_names=names, parameter_values=values)
    live = library.inputs(values)
    value, forward = harness.timed(objective, *live)
    _, second = harness.timed(objective, *live)
    sample.update(forward_seconds=forward, second_forward_seconds=second,
                  objective_value=library.number(value))
    if backend == "numpy":
        gradient, seconds = harness.timed(central_differences, objective, values)
        sample.update(gradient_method="central differences, 2 solves per parameter",
                      gradient_solves=2 * len(values))
    elif backend == "jax":
        gradient, seconds = harness.timed(library.jax.grad(lambda v: objective(*v)), live)
        gradient = [float(g) for g in gradient]
        sample.update(gradient_method="jax.grad: forward solve plus one adjoint solve")
    else:
        leaves = library.inputs(values)
        start = time.perf_counter()
        result = objective(*leaves)
        forward_again = time.perf_counter() - start
        _, backward = harness.timed(result.backward)
        seconds = forward_again + backward
        gradient = [float(x.grad) for x in leaves]
        sample.update(gradient_method="torch autograd: forward solve plus one adjoint solve",
                      backward_seconds=backward)
    sample.update(harness.peak_rss())
    sample.update(gradient_seconds=seconds, gradient=gradient,
                  gradient_to_forward_ratio=seconds / second if second > 0 else None)
    return sample


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", choices=CASES, help="repeat to select cases; default: all")
    parser.add_argument("--backend", action="append", choices=BACKENDS,
                        help="repeat to select; default: all three, absent libraries are recorded as skipped")
    parser.add_argument("--sizes", type=int, nargs="+", default=[8, 16, 32, 64],
                        help="n: heat n x n cells per layer; transient 2n x n; elasticity 4n x n")
    parser.add_argument("--steps", type=int, default=20, help="transient time steps over 1 s")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=float, default=900)
    parser.add_argument("--output", type=Path, help="new JSON file; checkpoints after each worker")
    parser.add_argument("--worker", choices=CASES, help=argparse.SUPPRESS)
    parser.add_argument("--size", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--worker-backend", choices=BACKENDS, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if min([args.repeats, args.steps, *args.sizes]) < 1:
        parser.error("sizes, steps and repeats must be positive")
    if not math.isfinite(args.timeout_seconds) or args.timeout_seconds <= 0:
        parser.error("timeout-seconds must be finite and positive")
    if args.worker:
        if args.size is None or args.worker_backend is None:
            parser.error("worker requires --size and --worker-backend")
        labels = dict(case=args.worker, size=args.size, backend=args.worker_backend)
        return harness.print_worker(harness.worker(
            lambda: measure(args.worker, args.size, args.worker_backend, args.steps), labels,
            imports=("galerkin",)))
    cases = args.case or list(CASES)
    backends = args.backend or list(BACKENDS)
    if (len(set(cases)) != len(cases) or len(set(args.sizes)) != len(args.sizes)
            or len(set(backends)) != len(backends)):
        parser.error("duplicate cases/sizes/backends: use --repeats for repetitions")
    harness.reserve_output(parser, args.output)
    jobs = [(dict(case=case, size=size, backend=backend),
             ["--worker", case, "--size", str(size), "--worker-backend", backend, "--steps", str(args.steps)])
            for size in args.sizes for case in cases for backend in backends]
    settings = dict(cases=cases, sizes=args.sizes, backends=backends, steps=args.steps,
                    parameters=PARAMETERS, relative_step=RELATIVE_STEP,
                    width_m=WIDTH, height_m=HEIGHT, hot_k=HOT, ambient_k=AMBIENT, film_w_m2k=FILM)
    return harness.run_parent(__file__, args.output, jobs, args.repeats, args.timeout_seconds,
                              settings, ("case", "size", "backend"), METRICS)


if __name__ == "__main__":
    raise SystemExit(main())
