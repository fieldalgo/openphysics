# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Report tiny-domain heat conditioning without changing acceptance gates.

This diagnostic preserves solver failures and inspects their original traceback
locals. A completed report is not a passing physical acceptance result.
"""
import argparse
import json
from pathlib import Path
import platform
import sys

import numpy as np

from galerkin import rectangle_mesh
from galerkin.assembly import assemble_mass, assemble_stiffness
from galerkin.transient_heat import solve_transient_heat


def case(name, source, ramp=False, n=8):
    mesh = rectangle_mesh(.002, .001, n, n)
    times = np.array([2., 2.03, 2.1, 2.4, 3.])
    initial = 290. if ramp else 300.
    fixed = np.unique(np.concatenate(list(mesh.boundary.values()))) if ramp else np.array([], dtype=int)
    boundary = {int(i): (lambda t: 290. + 3.*(t-2.)) for i in fixed}
    mass = assemble_mass(mesh, 4.)
    stiffness = assemble_stiffness(mesh, 2.5)
    ones = np.ones(mesh.num_nodes)
    result = {"name": name, "nodes": mesh.num_nodes, "fixed": len(fixed),
              "mass_total": float(ones @ (mass @ ones)),
              "stiffness_constant_max": float(np.max(abs(stiffness @ ones))),
              "stiffness_constant_sum": float(np.sum(stiffness @ ones))}
    free = np.setdiff1d(np.arange(mesh.num_nodes), fixed)
    a = (mass / .6 + stiffness)[free][:, free].toarray()
    if len(free):
        eigenvalues = np.linalg.eigvalsh(a)
        result["last_step_eigenvalue_extrema"] = [float(eigenvalues[0]), float(eigenvalues[-1])]
        result["last_step_condition_estimate"] = float(eigenvalues[-1]/eigenvalues[0])
    try:
        solved = solve_transient_heat(mesh, conductivity=2.5, volumetric_heat_capacity=4.,
                    time_s=times, initial_temperature_k=np.full(mesh.num_nodes, initial),
                    dirichlet=boundary, heat_source=source)
        exact = initial + (3. if ramp else source/4.) * (times-times[0])
        result.update(status="returned", temperature_max_error=float(np.max(abs(solved.temperature_k-exact[:, None]))),
                      flux_max=float(np.max(abs(solved.heat_flux_w_m2))),
                      balance_max=float(np.max(abs((solved.storage_rate_w_per_m-
                          solved.source_load_w_per_m[1:]-solved.reaction_w_per_m).sum(axis=1)))))
    except Exception as error:
        result.update(status="raised", error=repr(error), cause=repr(error.__cause__))
        chain = error
        while chain is not None:
            trace = chain.__traceback__
            while trace is not None:
                frame = trace.tb_frame
                local = frame.f_locals
                if frame.f_code.co_name == "solve_transient_heat" and "current" in local:
                    current = np.array(local["current"], copy=True)
                    result["failure_step"] = int(local["index"])
                    for key in ("balance", "balance_scale", "scale"):
                        if key in local:
                            result[key] = float(local[key])
                    result["spatial_sum"] = float(np.sum(stiffness @ current))
                    result["centered_spatial_sum"] = float(np.sum(stiffness @ (current-current[0])))
                    result["free_residual_sum"] = float(np.sum(local["residual"][free]))
                    result["increment_spread"] = float(np.ptp(current))
                    expected = initial + (3. if ramp else source/4.)*(times[local["index"]]-times[0])
                    absolute = current + np.asarray(local["offsets"])
                    result["failure_temperature_error"] = float(np.max(abs(absolute-expected)))
                    result["mass_mean_error"] = float(ones @ (mass @ (absolute-expected)) / result["mass_total"])
                trace = trace.tb_next
            chain = chain.__cause__
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = {"scope": "diagnostic only; no changed inputs, tolerances or solver controls",
              "python": sys.version, "platform": platform.platform(), "numpy": np.__version__,
              "cases": [case("insulated-heating", 8.), case("insulated-cooling", -1600.),
                        case("boundary-ramp", 12., True), case("all-fixed-ramp", 2., True, 1)]}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(report, indent=2, allow_nan=False) + "\n"
    with args.report.open("x", encoding="utf-8") as stream:
        stream.write(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    main()
