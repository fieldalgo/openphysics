# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Write the stored EMpy reference of the SOI strip and the square core (V16 of the mode TE fraction).

EMpy's vector finite-difference mode solver (EMpy.modesolvers.FD.VFDModeSolver, Fallahkhair, Li
and Murphy 2008) on rectilinear grids, in the window and at the indices of
tests/simcase/test_mode_polarization.py, held here as plain numbers: this script imports only
EMpy, NumPy and SciPy (no openphysics package), so the reference stays independent.

For each case and grid it records the two highest effective indices and their TE fractions,
f_TE = sum A |E_x|^2 / sum A (|E_x|^2 + |E_y|^2) over every cell, A the cell area (EMpy samples E
at the cell centres). That is the definition the product uses on its triangle centroids. The grid
puts a node on every window and core edge and splits each segment between them into equal cells
no larger than the step h, so the core edges lie on cell boundaries for any h. Install the pinned environment beside this file into its own virtual
environment, then run from this directory:

    python -m pip install --require-hashes --only-binary :all: -r requirements.txt
    python generate_strip_square_modes.py OUTPUT.json [--grids 0.02 0.01 0.005] [--product-commit SHA]

The output is a complete openphysics.reference-values/1 record. Nothing is written into the
repository unless OUTPUT.json is the record's path there.
"""
import argparse
import datetime
import hashlib
import json
import platform
import resource
import sys
import time
from pathlib import Path

import numpy as np
import scipy

import EMpy
from EMpy.modesolvers.FD import VFDModeSolver

SCHEMA = "openphysics.reference-values/1"
CONSUMER = "tests/simcase/test_reference_empy_modes.py"
GENERATOR = "tests/simcase/reference_values/empy/generate_strip_square_modes.py"
#: physmat Si (Salzberg-Villa) and SiO2 (Malitson) at 1550 nm, rounded to 6 decimals
INPUTS = {
    "vacuum_wavelength_um": 1.55,
    "core_index": 3.477724,
    "background_index": 1.444024,
    "window_um": {"xmin": -1.5, "xmax": 1.5, "ymin": -1.2, "ymax": 1.2},
    "boundary": "pec on all four walls",
    "cases": {
        "strip": {"x": -0.25, "y": 0.0, "w": 0.5, "h": 0.22},
        "square": {"x": -0.2, "y": 0.0, "w": 0.4, "h": 0.4},
    },
    "kept_modes": 2,
    "te_fraction": "sum A |E_x|^2 divided by sum A (|E_x|^2 + |E_y|^2) over every cell of the window, A the cell "
                   "area, E at cell centres",
    "grid": "nodes on every window and core edge; each segment in equal cells of at most the step h",
}
#: PEC walls for the transverse H of VFDModeSolver, in its order North, South, East, West: at a
#: wall normal to y (north, south) H_y is odd and H_x even ("S"); at a wall normal to x (east,
#: west) H_x is odd and H_y even ("A")
BOUNDARY = "SSAA"
#: VFDModeSolver.solve shifts by sigma = (guess k0)^2 and asks ARPACK for the eigenvalues just
#: above it ("LR" in shift-invert): guess must lie below every mode wanted. 1.5 is above the
#: background index (no box mode is returned) and below both kept modes of each core. SEARCHED
#: modes are asked for; the top two are then confirmed by a second solve whose guess sits just
#: below the second kept mode (any higher mode the first solve missed would appear there).
GUESS = 1.5
SEARCHED = 8
TOL = 1e-12


def grid(breaks, h):
    """Nodes on every break (window and core edges), each segment in equal cells of at most h."""
    breaks = sorted(set(float(b) for b in breaks))
    nodes = [breaks[0]]
    for a, b in zip(breaks[:-1], breaks[1:]):
        count = max(1, int(np.ceil((b - a) / h - 1e-9)))
        nodes.extend(np.linspace(a, b, count + 1)[1:])
    return np.array(nodes)


def permittivity(core):
    """Cell-centred staircase permittivity; the core edges lie on cell boundaries for every grid used."""
    x0, x1 = core["x"], core["x"] + core["w"]
    y0, y1 = core["y"], core["y"] + core["h"]
    inside, outside = INPUTS["core_index"] ** 2, INPUTS["background_index"] ** 2

    def eps(xc, yc):
        xs, ys = np.meshgrid(np.asarray(xc), np.asarray(yc), indexing="ij")
        return np.where((xs > x0) & (xs < x1) & (ys > y0) & (ys < y1), inside, outside)
    return eps


def eigen(core, x, y, boundary, guess, count):
    solver = VFDModeSolver(INPUTS["vacuum_wavelength_um"], x, y, permittivity(core), boundary)
    solver.solve(count, TOL, guess)
    # ARPACK also returns eigenvalues far below sigma when fewer than count lie above it (n_eff with
    # real part 0 or below the guess): those are not modes of interest and are left out
    found = [complex(m.neff) for m in solver.modes]
    modes = sorted([m for m, n in zip(solver.modes, found) if np.isfinite(n) and n.real > guess],
                   key=lambda m: -np.real(m.neff))
    neff = np.array([complex(m.neff) for m in modes])
    if len(modes) < INPUTS["kept_modes"] or np.any(neff.real >= INPUTS["core_index"]) or \
            np.any(np.abs(neff.imag) > 1e-8 * neff.real):
        raise SystemExit(f"rejected solve (guess {guess}, {count} eigenvalues): returned n_eff {found} give "
                         f"{len(modes)} modes above the guess, need {INPUTS['kept_modes']} real ones below the core "
                         "index; nothing written")
    return modes, neff


def solve(core, h, boundary=BOUNDARY, confirm=False):
    w = INPUTS["window_um"]
    x = grid([w["xmin"], core["x"], core["x"] + core["w"], w["xmax"]], h)
    y = grid([w["ymin"], core["y"], core["y"] + core["h"], w["ymax"]], h)
    area = np.outer(np.diff(x), np.diff(y))           # (cells in x, cells in y), the shape of E
    start = time.perf_counter()
    modes, every = eigen(core, x, y, boundary, GUESS, SEARCHED)
    kept = INPUTS["kept_modes"]
    modes, neff = modes[:kept], every[:kept]
    if confirm:
        _, top = eigen(core, x, y, boundary, float(neff[-1].real) - 0.02, kept + 2)
        if not np.allclose(top[:kept].real, neff.real, rtol=0, atol=1e-7):
            raise SystemExit(f"the top {kept} modes differ between guesses {GUESS} ({neff.real.tolist()}) and "
                             f"{neff[-1].real - 0.02:.4f} ({top[:kept].real.tolist()}); nothing written")
    seconds = time.perf_counter() - start
    fraction = []
    for m in modes:
        ex, ey = np.sum(area * np.abs(m.Ex) ** 2), np.sum(area * np.abs(m.Ey) ** 2)
        fraction.append(float(ex / (ex + ey)))
    return neff, np.array(fraction), seconds, every.real


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False,
                      ensure_ascii=False).encode("utf-8")


def values_digest(arrays):
    digest = hashlib.sha256()
    for name, array in sorted(arrays.items()):
        array = np.asarray(array)
        for part in (name, array.dtype.str, repr(array.shape)):
            digest.update(part.encode("utf-8") + b"\0")
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def text_digest(path):
    data = Path(path).read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def spec(name, unit, array):
    array = np.ascontiguousarray(array, dtype="<f8")
    return {"name": name, "unit": unit, "dtype": "<f8", "shape": list(array.shape), "data": array.ravel().tolist()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", type=Path, help="the record to write (JSON)")
    parser.add_argument("--grids", type=float, nargs="+", default=[0.02, 0.01, 0.005],
                        help="largest cell sizes in um, coarse to fine")
    parser.add_argument("--product-commit", default=None, help="the repository commit this generator was read from")
    args = parser.parse_args(argv)
    grids = sorted(args.grids, reverse=True)

    wall = time.perf_counter()
    arrays, timings, self_check, imaginary = {"grid_h_um": np.array(grids)}, {}, [], 0.0
    for case, core in INPUTS["cases"].items():
        neffs, fractions = [], []
        for h in grids:
            neff, fraction, seconds, every = solve(core, h, confirm=h == grids[0])
            imaginary = max(imaginary, float(np.max(np.abs(neff.imag))))
            neffs.append(neff.real)
            fractions.append(fraction)
            timings[f"{case} {h} um"] = round(seconds, 2)
            print(f"{case} h={h} um: n_eff {neff.real.tolist()}, f_TE {fraction.tolist()}, {seconds:.1f} s "
                  f"(all {len(every)} above {GUESS}: {np.round(every, 5).tolist()})", flush=True)
            if h == grids[0]:
                self_check.append(f"{case}: the top two at h = {h} um are the same with guess {GUESS} and with a "
                                  f"guess 0.02 below the second (all returned above {GUESS}: "
                                  f"{np.round(every, 5).tolist()})")
        arrays[f"neff_{case}"] = np.array(neffs)
        arrays[f"te_fraction_{case}"] = np.array(fractions)
        # the window walls: the same case with H set to zero outside the window, coarsest grid
        other, _, _, _ = solve(core, grids[0], "0000")
        self_check.append(f"{case}: n_eff with walls 0000 instead of {BOUNDARY} at h = {grids[0]} um differs by "
                          f"{np.max(np.abs(other.real - arrays[f'neff_{case}'][0])):.2e}")
    wall = time.perf_counter() - wall
    for case in INPUTS["cases"]:
        series = arrays[f"neff_{case}"][:, 0]
        monotone = bool(np.all(np.diff(series) > 0) or np.all(np.diff(series) < 0))
        self_check.append(f"{case}: mode 1 n_eff {'is' if monotone else 'is not'} monotone over h = {grids}")
    self_check.append(f"largest |Im n_eff| returned: {imaginary:.1e} (lossless problem)")

    values = [spec("grid_h_um", "um", arrays["grid_h_um"])]
    for case in INPUTS["cases"]:
        values += [spec(f"neff_{case}", "1", arrays[f"neff_{case}"]),
                   spec(f"te_fraction_{case}", "1", arrays[f"te_fraction_{case}"])]
    stored = {v["name"]: np.asarray(v["data"], dtype="<f8").reshape(v["shape"]) for v in values}
    values_sha256 = values_digest(stored)
    content_sha256 = hashlib.sha256(canonical_json({"inputs": INPUTS, "values_sha256": values_sha256})).hexdigest()
    record = {
        "schema": SCHEMA,
        "case": "strip_square_modes",
        "physics": "em.modes2d vector, lossless SOI strip and 400 x 400 nm square core: n_eff and TE fraction",
        "comparison": "different-discretization",
        "role": "code-to-code comparison of n_eff and the TE fraction; not analytical acceptance or convergence evidence",
        "references": [{
            "tool": "empy",
            "version": "2.2.3",
            "build": f"PyPI wheel electromagneticpython-2.2.3-py3-none-any.whl; EMpy.__version__ {EMpy.__version__}",
            "modified": {"value": False, "description": "unmodified PyPI wheel"},
            "license": "MIT",
            "source": "https://github.com/lbolla/EMpy",
            "install": {"kind": "pip", "command": "python -m pip install --require-hashes --only-binary :all: -r "
                        "tests/simcase/reference_values/empy/requirements.txt",
                        "lock": "tests/simcase/reference_values/empy/requirements.txt (hash-pinned)"},
            "settings": {"function": "EMpy.modesolvers.FD.VFDModeSolver(...).solve(neigs, tol, guess)",
                         "boundary": BOUNDARY, "neigs": SEARCHED, "tol": TOL, "guess": GUESS,
                         "kept": f"the two largest n_eff of {SEARCHED}, confirmed at the coarsest grid by a second "
                                 "solve with the guess 0.02 below the second",
                         "grid": "nodes on the window and core edges, each segment in equal cells of at most h"},
            "discretization": {"kind": "vector finite differences (Fallahkhair, Li, Murphy 2008)",
                               "permittivity": "cell-centred staircase", "grids_um": grids},
            "arrays": ["*"],
            "execution": "in-process",
            "independence": {"product_loaded": False, "inputs_from_product": True},
        }],
        "generator": {"path": GENERATOR, "sha256": text_digest(__file__),
                      "command": "python generate_strip_square_modes.py OUTPUT.json",
                      "product_commit": args.product_commit, "clean": True},
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "os": platform.system(),
                        "cpu": platform.processor() or platform.machine(), "dtype": "float64 and complex128",
                        "backend/device": f"cpu, SciPy {scipy.__version__} ARPACK shift-invert"},
        "cost": {"compile_s": None, "compute_s": round(sum(timings.values()), 1), "wall_time_s": round(wall, 1),
                 "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
                 "threads": None, "not_measured": ["BLAS thread count"], "per_solve_s": timings},
        "inputs": INPUTS,
        "matched": ["window and both cores", "PEC on all walls (VFDModeSolver boundary SSAA)",
                    "material indices: physmat Si and SiO2 at 1550 nm, as plain numbers",
                    "the TE fraction definition, weighted by cell area"],
        "not_matched": ["discretization: finite differences on a near-uniform rectilinear grid against edge finite elements on a "
                        "graded mesh", "interfaces: staircase cell-centred permittivity against mesh-conforming "
                        "interfaces", "samples: cell centres against triangle centroids", "eigen solver"],
        "reference_self_check": self_check,
        "failed_or_discarded": [],
        "not_run": ["macOS and Windows", "a repeated run for determinism"],
        "values": values,
        "values_sha256": values_sha256,
        "content_sha256": content_sha256,
        "consumers": [CONSUMER],
        "provenance_status": "complete",
        "not_recorded": {"cost.compile_s": "no compile step; source: generator",
                         "cost.threads": "BLAS threads were left at the default and not logged; source: generator"},
        "regeneration": [],
    }
    if args.product_commit is None:
        record["not_recorded"]["generator.product_commit"] = "not given with --product-commit; source: generator"
    args.output.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.output.name}: {wall:.0f} s, peak {record['cost']['peak_rss_mb']} MB", file=sys.stderr)


if __name__ == "__main__":
    main()
