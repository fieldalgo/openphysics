# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Segment recovery counters of meshloom's boundary recovery (V15 of the 3D plan).

Cases of the plan (docs/packages/meshine/validation3d.md):
- C3, the chip package: substrate 10 x 10 x [0, 1], die 4 x 4 x 0.5 centred on top,
  mold 10 x 10 x [1, 2.5] around the die; three regions, the interfaces as facets.
- C1 at h = 0.1: until the curved primitives (M7) exist, a frequency-11 geodesic
  subdivision of the icosahedron on the unit sphere (edges about 0.1), every vertex
  projected to the sphere and rounded: nearly cospherical points.

Each repetition runs in a fresh process: the PLC check, then segment recovery on the
elementary segments. Reported per case: Steiner points per segment, exact-stage calls
per inserted vertex (input-point exact predicates plus mixed-point big-integer calls),
walk steps per vertex, insertions per output vertex and the time. V15: a counter may
not exceed twice the value measured in the pull request that introduces it. This is
a benchmark: CI does not run it.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
THREADS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "RAYON_NUM_THREADS")


def chip_package():
    """C3 as a PLC: box corners and the facets of three regions with their interfaces."""
    pts, index = [], {}

    def p(x, y, z):
        key = (x, y, z)
        if key not in index:
            index[key] = len(pts)
            pts.append([float(x), float(y), float(z)])
        return index[key]

    def rect(axis, c, a0, a1, b0, b1):
        # an axis-aligned rectangle at coordinate c on `axis`, spanning [a0, a1] x [b0, b1]
        # on the other two axes in cyclic order
        u, v = [(1, 2), (2, 0), (0, 1)][axis]
        corners = []
        for a, b in ((a0, b0), (a1, b0), (a1, b1), (a0, b1)):
            q = [0.0, 0.0, 0.0]
            q[axis], q[u], q[v] = c, a, b
            corners.append(p(*q))
        return corners

    facets = [
        [rect(2, 0, 0, 10, 0, 10)],                                   # substrate bottom
        [rect(2, 1, 0, 10, 0, 10), rect(2, 1, 3, 7, 3, 7)],          # substrate/mold, die hole
        [rect(2, 1, 3, 7, 3, 7)],                                     # substrate/die
        [rect(2, 1.5, 3, 7, 3, 7)],                                   # die top (die/mold)
        [rect(2, 2.5, 0, 10, 0, 10)],                                 # mold top
    ]
    # sides: on x = c the rectangle spans (y, z); on y = c it spans (z, x)
    for c in (0, 10):
        facets += [[rect(0, c, 0, 10, 0, 1)], [rect(0, c, 0, 10, 1, 2.5)],
                   [rect(1, c, 0, 1, 0, 10)], [rect(1, c, 1, 2.5, 0, 10)]]
    for c in (3, 7):
        facets += [[rect(0, c, 3, 7, 1, 1.5)], [rect(1, c, 1, 1.5, 3, 7)]]
    return pts, facets


def geodesic_sphere(freq):
    t = (1 + 5 ** 0.5) / 2
    ico = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
           (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2),
             (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5),
             (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    index, pts, tris = {}, [], []

    def pid(key, q):
        if key not in index:
            n = math.sqrt(sum(c * c for c in q))
            index[key] = len(pts)
            pts.append([c / n for c in q])
        return index[key]

    for a, b, c in faces:
        grid = {}
        for i in range(freq + 1):
            for j in range(freq + 1 - i):
                k = freq - i - j
                key = tuple(x for x in sorted(((a, i), (b, j), (c, k))) if x[1])
                q = [(i * ico[a][m] + j * ico[b][m] + k * ico[c][m]) / freq for m in range(3)]
                grid[i, j] = pid(key, q)
        for i in range(freq):
            for j in range(freq - i):
                tris.append([[grid[i, j], grid[i + 1, j], grid[i, j + 1]]])
                if i + j < freq - 1:
                    tris.append([[grid[i + 1, j], grid[i + 1, j + 1], grid[i, j + 1]]])
    return pts, tris


CASES = {"C3": chip_package, "C1-geodesic-h0.1": lambda: geodesic_sphere(11)}


def worker(case: str) -> dict:
    sys.path[:0] = [str(ROOT / "packages/meshloom/src")]
    import numpy as np
    from meshloom._core import check_plc, recover_segments

    pts, facets = CASES[case]()
    pts = np.array(pts, dtype=float)
    t0 = time.perf_counter()
    plc = check_plc(pts, np.zeros((0, 2)), facets)
    t1 = time.perf_counter()
    r = recover_segments(pts, plc["subsegments"])
    t2 = time.perf_counter()
    s = r["stats"]
    segments = len(plc["subsegments"])
    steiner = len(r["s_t"])
    inserted = s["inserted"]
    vertices = len(pts) + steiner
    exact = s["mixed_exact"] + s["input_exact"]  # big-integer and exact-expansion stage calls
    return dict(case=case, points=len(pts), facets=len(facets), segments=segments, steiner_points=steiner,
                steiner_per_segment=steiner / segments, exact_calls_per_vertex=exact / inserted,
                walk_steps_per_vertex=s["walk_steps"] / inserted, insertions_per_output_vertex=inserted / vertices,
                tetrahedra=len(r["tetrahedra"]), check_seconds=t1 - t0, recovery_seconds=t2 - t1, stats=s)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--worker", default=None, help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.worker:
        print(json.dumps(worker(a.worker)))
        return
    env = dict(os.environ, **{k: "1" for k in THREADS})
    results = {}
    for case in CASES:
        runs = []
        for _ in range(a.repeats):
            out = subprocess.run([sys.executable, __file__, "--worker", case, "--output", os.devnull],
                                 env=env, capture_output=True, text=True, encoding="utf-8", check=True)
            runs.append(json.loads(out.stdout.strip().splitlines()[-1]))
        counters = {k: runs[0][k] for k in ("points", "facets", "segments", "steiner_points", "steiner_per_segment",
                                            "exact_calls_per_vertex", "walk_steps_per_vertex",
                                            "insertions_per_output_vertex", "tetrahedra")}
        # the counters are deterministic; only the times vary
        assert all(all(r[k] == counters[k] for k in counters) for r in runs)
        results[case] = dict(counters=counters,
                             median_seconds=dict(check=statistics.median(r["check_seconds"] for r in runs),
                                                 recovery=statistics.median(r["recovery_seconds"] for r in runs)),
                             runs=runs)
    rev = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True,
                         encoding="utf-8").stdout.strip()
    dirty = bool(subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"], capture_output=True,
                                text=True, encoding="utf-8").stdout.strip())
    record = dict(benchmark="meshloom segment recovery V15 counters", created=datetime.now(timezone.utc).isoformat(),
                  revision=rev, checkout_dirty=dirty,
                  benchmark_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  python=sys.version, platform=platform.platform(), processor=platform.processor(),
                  cpu_count=os.cpu_count(), cases=results)
    a.output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    for case, r in results.items():
        print(case, json.dumps(r["counters"]), json.dumps(r["median_seconds"]))


if __name__ == "__main__":
    main()
