# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Time the layered extruder on the package footprint of the 3D plan (V33).

C15: a 10 x 10 footprint with 36 vias of radius 0.15 on a 6 x 6 grid. Each
repetition runs in a fresh process with one BLAS thread and measures the meshine
2D footprint mesh at size 0.1 and the extrusion through a stack of layers, then
reports seconds per million tetrahedra. Gates (docs/packages/meshine/validation3d.md):
footprint median <= 30 s, extrusion <= 2 s per 1M tetrahedra. This is a benchmark:
CI does not run it.
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
THREADS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")


def worker(size: float, layer_size: float) -> dict:
    sys.path[:0] = [str(ROOT / "packages/meshine/src")]
    from meshine import Circle, Domain, box_sides, extrude, generate, rectangle

    centres = [(-3.75 + 1.5 * i, -3.75 + 1.5 * j) for i in range(6) for j in range(6)]
    d = Domain(size=size)
    for k, c in enumerate(centres):
        d.add_region("via", Circle(c, 0.15, n=16))
    d.add_region("board", rectangle(-5, -5, 5, 5), holes=[Circle(c, 0.15, n=16) for c in centres])
    t0 = time.perf_counter()
    fp = generate(d, box_sides(-5, 5, -5, 5))
    t1 = time.perf_counter()
    z = [0.0, 0.2, 1.0, 1.2, 1.6]
    mats = {"via": ["copper", "copper", "copper", "copper"], "board": ["copper", "core", "copper", "mold"]}
    m = extrude(fp, z, mats, size=layer_size)
    t2 = time.perf_counter()
    return dict(footprint_s=t1 - t0, footprint_triangles=len(fp.triangles), extrude_s=t2 - t1,
                tetrahedra=m.num_tetrahedra, nodes=m.num_nodes,
                extrude_s_per_million=(t2 - t1) / m.num_tetrahedra * 1e6)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--size", type=float, default=0.1)
    ap.add_argument("--layer-size", type=float, default=0.02)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.worker:
        print(json.dumps(worker(a.size, a.layer_size)))
        return
    env = dict(os.environ, **{k: "1" for k in THREADS})
    runs = []
    for _ in range(a.repeats):
        out = subprocess.run([sys.executable, __file__, "--worker", "--size", str(a.size),
                              "--layer-size", str(a.layer_size), "--output", os.devnull],
                             env=env, capture_output=True, text=True, encoding="utf-8", check=True)
        runs.append(json.loads(out.stdout.strip().splitlines()[-1]))
    med = {k: statistics.median(r[k] for r in runs) for k in ("footprint_s", "extrude_s", "extrude_s_per_million")}
    rev = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True,
                         encoding="utf-8").stdout.strip()
    dirty = bool(subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"], capture_output=True,
                                text=True, encoding="utf-8").stdout.strip())
    record = dict(benchmark="meshine extrude V33", created=datetime.now(timezone.utc).isoformat(),
                  revision=rev, checkout_dirty=dirty,
                  benchmark_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  python=sys.version, platform=platform.platform(), processor=platform.processor(),
                  size=a.size, layer_size=a.layer_size, runs=runs, median=med,
                  gates=dict(footprint_s_max=30.0, extrude_s_per_million_max=2.0,
                             footprint_pass=med["footprint_s"] <= 30.0,
                             extrude_pass=med["extrude_s_per_million"] <= 2.0))
    a.output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record["median"]), json.dumps(record["gates"]))


if __name__ == "__main__":
    main()
