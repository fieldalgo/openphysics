# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Time meshloom's Delaunay kernel on uniform random points (V17 throughput, V15 counters).

Each repetition runs in a fresh process: n points uniform in the unit cube (fixed
seed), Delaunay tetrahedralization by the compiled kernel, timed from the numpy
array to the tetrahedron array. Reports points per second and the V15 counters per
inserted vertex (exact-stage predicate calls, walk steps). Gate of the 3D plan
(docs/packages/meshine/validation3d.md): >= 150k points/s is the target, < 50k
points/s on 10^6 points stops the kernel plan. This is a benchmark: CI does not run it.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
THREADS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "RAYON_NUM_THREADS")


def worker(n: int, seed: int) -> dict:
    sys.path[:0] = [str(ROOT / "packages/meshloom/src")]
    import numpy as np
    from meshloom._core import delaunay

    pts = np.random.default_rng(seed).random((n, 3))
    t0 = time.perf_counter()
    tets, _, stats = delaunay(pts)
    t1 = time.perf_counter()
    inserted = stats["inserted"]
    return dict(points=n, seconds=t1 - t0, points_per_second=n / (t1 - t0), tetrahedra=len(tets),
                exact_calls_per_vertex=(stats["orient3d_exact"] + stats["insphere_exact"]) / inserted,
                orient3d_exact_per_vertex=stats["orient3d_exact"] / inserted,
                insphere_exact_per_vertex=stats["insphere_exact"] / inserted,
                walk_steps_per_vertex=stats["walk_steps"] / inserted,
                cavity_tets_per_vertex=stats["cavity_tets"] / inserted,
                walk_fallbacks=stats["walk_fallbacks"], stats=stats)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--points", type=int, default=1_000_000)
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.worker:
        print(json.dumps(worker(a.points, a.seed)))
        return
    env = dict(os.environ, **{k: "1" for k in THREADS})
    runs = []
    for _ in range(a.repeats):
        out = subprocess.run([sys.executable, __file__, "--worker", "--points", str(a.points), "--seed", str(a.seed),
                              "--output", os.devnull],
                             env=env, capture_output=True, text=True, encoding="utf-8", check=True)
        runs.append(json.loads(out.stdout.strip().splitlines()[-1]))
    keys = ("seconds", "points_per_second", "exact_calls_per_vertex", "walk_steps_per_vertex",
            "cavity_tets_per_vertex")
    med = {k: statistics.median(r[k] for r in runs) for k in keys}
    rev = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True,
                         encoding="utf-8").stdout.strip()
    dirty = bool(subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"], capture_output=True,
                                text=True, encoding="utf-8").stdout.strip())
    record = dict(benchmark="meshloom Delaunay V17 throughput", created=datetime.now(timezone.utc).isoformat(),
                  revision=rev, checkout_dirty=dirty,
                  benchmark_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  python=sys.version, platform=platform.platform(), processor=platform.processor(),
                  cpu_count=os.cpu_count(), points=a.points, seed=a.seed, runs=runs, median=med,
                  gates=dict(target_points_per_second=150_000, stop_below_points_per_second=50_000,
                             target_met=med["points_per_second"] >= 150_000,
                             plan_continues=med["points_per_second"] >= 50_000))
    a.output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record["median"]), json.dumps(record["gates"]))


if __name__ == "__main__":
    main()
