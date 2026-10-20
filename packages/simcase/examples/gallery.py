# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Render the example gallery shown in docs/gallery.md.

    python packages/simcase/examples/gallery.py OUTPUT_DIR [--quick]

OUTPUT_DIR must be new or empty. It receives:

- heated_plate.webp, heated_plate.png: transient heat in a plate, animated
- heated_plate_result/ and heated_plate_paraview/fields.pvd: the saved result
  and the same result as a ParaView time series, written only when meshio
  (``simcase[export]``) is installed
- coax.png: coaxial electrostatics and its mesh convergence
- box_cavity.png: four 3D cavity modes against analytical frequencies
- gallery.json: the numbers quoted on the gallery page

``--quick`` uses coarser meshes and fewer frames for tests. The gallery
illustrates features; the validation reports linked from docs/gallery.md hold
the acceptance gates. The checks below only guard against a broken picture.
Needs galerkin-refsol (``simcase[test]``) for the analytical cavity modes.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from galerkin import (annulus_mesh, assemble_load, assemble_stiffness,  # noqa: E402
                      l2_error, solve_dirichlet)
from simcase import Document, run  # noqa: E402
from simcase.export import export_time_series  # noqa: E402

EXAMPLES = Path(__file__).resolve().parent
DPI = 100


def _figure_image(fig):
    """RGB copy of a drawn matplotlib figure."""
    fig.canvas.draw()
    return Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[..., :3].copy())


def heated_plate(out, quick):
    doc = Document.load(EXAMPLES / "gallery_heated_plate.json")
    if quick:
        doc["mesh"]["subdivisions"] = [12, 12]
        doc["study"]["time_s"] = doc["study"]["time_s"][::8]
    result = run(doc, False)
    nodes = np.asarray(result.mesh_nodes_m) * 100.0  # cm for the axes
    triangles = np.asarray(result.mesh_triangles)
    times = np.asarray(result.time_s)
    temperature = np.asarray(result.temperature_k)
    low, high = 300.0, float(np.ceil(temperature.max()))

    fig, ax = plt.subplots(figsize=(4.8, 4.0), dpi=DPI, layout="constrained")
    mesh = ax.tripcolor(nodes[:, 0], nodes[:, 1], triangles, temperature[0],
                        shading="gouraud", cmap="inferno", vmin=low, vmax=high)
    fig.colorbar(mesh, ax=ax, label="Temperature [K]")
    ax.set_aspect("equal")
    ax.set_xlabel("x [cm]")
    ax.set_ylabel("y [cm]")
    frames = []
    for k, t in enumerate(times):
        mesh.set_array(temperature[k])
        ax.set_title(f"t = {t:5.2f} s")
        frames.append(_figure_image(fig))
    plt.close(fig)
    frames[-1].save(out / "heated_plate.png", optimize=True)
    frames[0].save(out / "heated_plate.webp", save_all=True, append_images=frames[1:],
                   duration=80, loop=0, quality=80, method=6)

    paraview = None
    try:
        import meshio  # noqa: F401
    except ImportError:
        print("meshio not installed: skipping the ParaView time series", file=sys.stderr)
    else:
        saved = result.save(out / "heated_plate_result")
        paraview = export_time_series(saved / "fields.npz", out / "heated_plate_paraview")

    return {"frames": len(times), "end_time_s": float(times[-1]),
            "max_temperature_k": float(temperature.max()),
            "max_rise_k": float(temperature.max() - 300.0),
            "paraview": None if paraview is None else paraview.relative_to(out).as_posix()}


def coax(out, quick):
    inner, outer = 1.0, 3.0

    def exact(x, y):
        return np.log(outer / np.hypot(x, y)) / np.log(outer / inner)

    levels = [4, 8, 16] if quick else [4, 8, 16, 32]
    sizes, errors = [], []
    for n_r in levels:
        mesh = annulus_mesh(inner, outer, n_r, 6 * n_r)
        stiffness = assemble_stiffness(mesh, eps=1.0)
        load = assemble_load(mesh, rho=0.0)
        potential = solve_dirichlet(stiffness, load, {
            tuple(mesh.boundary["inner"]): 1.0,
            tuple(mesh.boundary["outer"]): 0.0,
        })
        sizes.append((outer - inner) / n_r)
        errors.append(l2_error(mesh, potential, exact))
    rate = float(np.log(errors[-2] / errors[-1]) / np.log(2.0))
    # Same guard as coax_convergence.py: P1 must converge at second order.
    if rate <= 1.8:
        raise RuntimeError(f"coax convergence rate {rate:.2f} is below second order")

    fig, (left, right) = plt.subplots(1, 2, figsize=(8.4, 3.6), dpi=DPI, layout="constrained")
    shown = mesh.nodes
    field = left.tripcolor(shown[:, 0], shown[:, 1], mesh.triangles, potential,
                           shading="gouraud", cmap="viridis")
    fig.colorbar(field, ax=left, label="Potential [V]")
    left.set_aspect("equal")
    left.set_title(f"Potential, {mesh.num_nodes} nodes")
    left.set_axis_off()
    h, err = np.asarray(sizes), np.asarray(errors)
    right.loglog(h, err, "o-", label="FEM L2 error")
    right.loglog(h, err[-1] * (h / h[-1]) ** 2, "--", color="0.5", label="slope 2")
    right.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    right.set_xlabel("radial element size h")
    right.set_ylabel("L2 error vs exact")
    right.set_title(f"Convergence rate {rate:.2f}")
    right.legend()
    right.grid(True, which="both", alpha=0.3)
    fig.savefig(out / "coax.png")
    plt.close(fig)
    return {"element_sizes": sizes, "l2_errors": errors, "final_rate": rate}


def box_cavity(out, quick):
    from refsol.cavity import rectangular_cavity_modes

    doc = Document.load(EXAMPLES / "gallery_box_cavity.json")
    if quick:
        doc["mesh"]["subdivisions"] = [10, 6, 4]
    domain = doc["geometry"]["domain"]
    lengths = tuple(domain[f"{a}max"] - domain[f"{a}min"] for a in "xyz")
    target = doc["physics"]["em1"]["target_frequency_hz"]
    result = run(doc, False)
    cavity = result.cavity
    computed = np.asarray(cavity.frequencies_hz)

    # Analytical modes nearest the same target, one entry per independent mode.
    analytic = rectangular_cavity_modes(lengths, 2.0 * computed.max())
    analytic = sorted(analytic, key=lambda m: abs(m.frequency_hz - target))[:len(computed)]
    analytic = sorted(analytic, key=lambda m: m.frequency_hz)
    exact = np.array([m.frequency_hz for m in analytic])
    if len(np.unique(np.round(exact, 3))) != len(exact):
        raise RuntimeError("the gallery box must have non-degenerate modes near the target")
    relative = (computed - exact) / exact
    if np.max(np.abs(relative)) > 0.01:
        raise RuntimeError(f"cavity frequencies differ by {np.max(np.abs(relative)):.2%}")

    nodes = np.asarray(cavity.mesh.nodes)
    tets = np.asarray(cavity.mesh.tets)
    centroids = nodes[tets].mean(axis=1)
    nx, ny, nz = doc["mesh"]["subdivisions"]
    z_mid = domain["zmin"] + lengths[2] / 2
    near = np.abs(centroids[:, 2] - z_mid) < lengths[2] / nz / 2
    fields = np.asarray(cavity.electric_field)  # (modes, tetrahedra, 3)

    fig, axes = plt.subplots(2, 2, figsize=(8.4, 5.2), dpi=DPI, layout="constrained")
    for k, ax in enumerate(axes.flat):
        magnitude = np.linalg.norm(fields[k][near], axis=1)
        total, _, _ = np.histogram2d(centroids[near, 0], centroids[near, 1], bins=(nx, ny),
                                     range=[(domain["xmin"], domain["xmax"]),
                                            (domain["ymin"], domain["ymax"])],
                                     weights=magnitude)
        count, _, _ = np.histogram2d(centroids[near, 0], centroids[near, 1], bins=(nx, ny),
                                     range=[(domain["xmin"], domain["xmax"]),
                                            (domain["ymin"], domain["ymax"])])
        image = np.divide(total, count, out=np.zeros_like(total), where=count > 0)
        ax.imshow(image.T / image.max(), origin="lower", cmap="magma", vmin=0, vmax=1,
                  extent=(domain["xmin"], domain["xmax"], domain["ymin"], domain["ymax"]))
        m, n, p = analytic[k].indices
        ax.set_title(f"({m},{n},{p}): {computed[k] / 1e6:.2f} MHz "
                     f"(exact {exact[k] / 1e6:.2f}, {relative[k]:+.3%})", fontsize=9)
        ax.set_xlabel("x [m]")
        ax.set_ylabel("y [m]")
    fig.suptitle(f"|E| at z = {z_mid:g} m, normalized per mode", fontsize=10)
    fig.savefig(out / "box_cavity.png")
    plt.close(fig)
    return {"lengths_m": list(lengths), "subdivisions": [nx, ny, nz],
            "indices": [list(m.indices) for m in analytic],
            "frequencies_hz": computed.tolist(), "exact_hz": exact.tolist(),
            "relative_error": relative.tolist()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", type=Path, help="new or empty directory")
    parser.add_argument("--quick", action="store_true", help="coarse meshes for tests")
    args = parser.parse_args(argv)
    out = args.output
    if os.path.lexists(out) and (not out.is_dir() or any(out.iterdir())):
        parser.error(f"{out} exists and is not an empty directory")
    out.mkdir(parents=True, exist_ok=True)
    values = {"quick": args.quick,
              "heated_plate": heated_plate(out, args.quick),
              "coax": coax(out, args.quick),
              "box_cavity": box_cavity(out, args.quick)}
    (out / "gallery.json").write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(values, indent=2))
    return values


if __name__ == "__main__":
    main()
