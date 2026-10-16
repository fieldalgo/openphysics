# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Repeat vector workloads in fresh processes; run from the repository root."""

import argparse
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
CASES = ("te", "tm", "two_modes", "single", "fiber", "hadley", "te_fine")


def document_data(case):
    from simcase import examples

    source = {"single": examples.VECTOR_SLAB, "fiber": examples.VECTOR_FIBER,
              "hadley": examples.HADLEY_RIB}.get(case, examples.VECTOR_SLAB_SWEEP)
    data = copy.deepcopy(source)
    if case == "tm":
        data["physics"]["em1"]["boundary"].update(left="pmc", right="pmc")
    elif case == "two_modes":
        data["physics"]["em1"]["num_modes"] = 2
        data["study"]["values"] = [1.20, 1.25, 1.30]
    elif case == "hadley":
        data["physics"]["em1"].update(formulation="vector", n_cladding=3.4)
    elif case == "te_fine":
        data["geometry"]["shapes"][0]["mesh_size"] *= 0.5
        data["mesh"]["size"] *= 0.5
        for key in ("near", "far"):
            data["mesh"]["grading"][key] *= 0.5
    return data


def measure(case, snapshot=None):
    import numpy as np
    from galerkin import EdgeSpace, Mesh
    from simcase import Document, run

    # Editable installs pointing at another checkout would invalidate comparison.
    for name in ("galerkin", "simcase", "meshine", "physmat"):
        module = importlib.import_module(name)
        if not Path(module.__file__).resolve().is_relative_to(ROOT / "packages"):
            raise RuntimeError(f"{name} must be installed from this checkout")
    data = document_data(case)
    doc = Document.from_dict(data)
    start = time.perf_counter()
    result = run(doc, verbose=False)
    seconds = time.perf_counter() - start
    try:
        import resource
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        rss_mib = rss / (1024**2 if sys.platform == "darwin" else 1024)
    except ImportError:  # Windows has no standard-library process peak RSS API.
        rss_mib = None
    mesh = Mesh(result.mesh_nodes, result.mesh_triangles, {})
    # Measure the complete topology constructor separately, outside run timing.
    topology = []
    for _ in range(21):
        start = time.perf_counter()
        space = EdgeSpace(mesh)
        topology.append(time.perf_counter() - start)
    if snapshot:
        np.savez_compressed(snapshot, neff=result.neff, edges=space.edges,
                            transverse=np.stack([f.transverse for f in result.vector_fields]),
                            longitudinal=np.stack([f.longitudinal for f in result.vector_fields]),
                            electric=np.stack([f.electric for f in result.vector_fields]))
    return dict(case=case, document=data,
                document_sha256=hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest(),
                seconds=seconds, timings=result.timings, peak_rss_mib=rss_mib,
                topology_seconds_median=statistics.median(topology),
                nodes=mesh.num_nodes, triangles=mesh.num_triangles, edges=space.num_edges,
                neff=result.neff.tolist(),
                group_index=None if result.mode_tracking is None else result.group_index().tolist(),
                mode_tracking=result.mode_tracking)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", choices=CASES, help="repeat to select cases; default: all")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, help="new JSON result file; default: stdout")
    parser.add_argument("--snapshots", type=Path, help="new directory for first-run field arrays")
    parser.add_argument("--worker", choices=CASES, help=argparse.SUPPRESS)
    parser.add_argument("--snapshot", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    if args.worker:
        print(json.dumps(measure(args.worker, args.snapshot), allow_nan=False))
        return
    if args.output and args.output.exists():
        parser.error("--output must not exist")
    if args.snapshots:
        args.snapshots.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
               BLIS_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1")
    runs = []
    for case in args.case or CASES:
        for repetition in range(args.repeats):
            command = [sys.executable, str(Path(__file__).resolve()), "--worker", case]
            if args.snapshots and repetition == 0:
                command += ["--snapshot", str((args.snapshots / f"{case}.npz").resolve())]
            completed = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
            if completed.returncode:
                raise RuntimeError(f"{case} failed:\n{completed.stderr}")
            sample = json.loads(completed.stdout)
            sample["repetition"] = repetition + 1
            runs.append(sample)
            print(f"{case} {repetition + 1}/{args.repeats}: {sample['seconds']:.3f} s", file=sys.stderr)
    git = lambda *args: subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()
    from importlib.metadata import version
    report = dict(schema_version=1, revision=git("rev-parse", "HEAD"),
                  checkout_dirty=bool(git("status", "--porcelain")),
                  python=sys.version, platform=platform.platform(),
                  versions={name: version(name) for name in ("numpy", "scipy", "shapely")},
                  pins_sha256=hashlib.sha256((ROOT / "ci/requirements-py312-linux.txt").read_bytes()).hexdigest(),
                  thread_environment={k: env[k] for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS",
                                                        "MKL_NUM_THREADS", "BLIS_NUM_THREADS",
                                                        "VECLIB_MAXIMUM_THREADS")},
                  runs=runs)
    output = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
