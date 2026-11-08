# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""C13 fuzz of the pre-registered 3D plan (V19), at the boundary-recovery stage.

200 seeded cases per run: assemblies of dyadic boxes (disjoint, touching or
overlapping) and n-gon prisms ("cylinders"), some with a 1-ulp jitter on vertices. Each
case is meshed with ``mesh_plc`` in a child process; a case that makes no progress for
60 s is a hang. Every outcome must be either a mesh that passes V1 (exact orient3d > 0
on the doubles) and the V2 contract checks, or a typed error (``ValueError`` and its
subclasses, such as ``InvalidPLC``, or ``RuntimeError`` for the documented depth
limit). Panics, other exceptions and hangs fail. ``MESHLOOM_FUZZ_OFFSET`` shifts the
seeds; outside CI, ``MESHLOOM_FUZZ_CASES`` raises the count.
"""

import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)


def box_facets(lo, hi, index, points):
    def p(q):
        q = tuple(float(x) for x in q)
        if q not in index:
            index[q] = len(points)
            points.append(q)
        return index[q]

    (x0, y0, z0), (x1, y1, z1) = lo, hi
    loops = [[(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)],
             [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
             [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
             [(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)],
             [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)],
             [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)]]
    return [[[p(q) for q in lp]] for lp in loops]


def case(seed):
    """Points and facets of fuzz case `seed`."""
    rng = random.Random(seed)
    points, index, facets = [], {}, []
    for _ in range(rng.randint(1, 3)):
        if rng.random() < 0.6:
            lo = [rng.randint(0, 12) / 8 for _ in range(3)]
            hi = [x + rng.randint(1, 6) / 8 for x in lo]
            facets += box_facets(lo, hi, index, points)
        else:
            n = rng.randint(3, 12)
            cx, cy, r = rng.uniform(0, 2), rng.uniform(0, 2), rng.uniform(0.1, 1)
            z0 = rng.randint(0, 8) / 8
            z1 = z0 + rng.randint(1, 8) / 8
            ring = [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
            base = len(points)
            points += [(x, y, z0) for x, y in ring] + [(x, y, z1) for x, y in ring]
            facets.append([list(range(base + n - 1, base - 1, -1))])
            facets.append([list(range(base + n, base + 2 * n))])
            for k in range(n):
                a, b = base + k, base + (k + 1) % n
                facets.append([[a, b, b + n, a + n]])
    pts = np.array(points, dtype=float)
    if rng.random() < 0.3:  # 1-ulp jitter on a few coordinates
        for _ in range(rng.randint(1, 4)):
            i, c = rng.randrange(len(pts)), rng.randrange(3)
            pts[i, c] = np.nextafter(pts[i, c], np.inf if rng.random() < 0.5 else -np.inf)
    return pts, facets


def valid(m):
    """V1 and the V2 contract checks; returns a reason or ''."""
    from fractions import Fraction as F
    q = [[F(x) for x in p] for p in m["nodes"].tolist()]
    tets = m["tetrahedra"].tolist()
    for t in tets:
        a, b, c, d = (q[i] for i in t)
        u, v, w = ([x[i] - a[i] for i in range(3)] for x in (b, c, d))
        if u[0] * (v[1] * w[2] - v[2] * w[1]) - u[1] * (v[0] * w[2] - v[2] * w[0]) + u[2] * (v[0] * w[1] - v[1] * w[0]) <= 0:
            return "V1"
    owners = {}
    for t in tets:
        for i in range(4):
            owners.setdefault(tuple(sorted(t[:i] + t[i + 1:])), []).append(t[i])
    if any(len(o) > 2 for o in owners.values()):
        return "V2 face in three tetrahedra"
    exterior = sorted(f for f, o in owners.items() if len(o) == 1)
    tagged = sorted(tuple(sorted(f)) for fs in m["boundary_faces"].values() for f in fs.tolist())
    if exterior != tagged:
        return "V2 boundary faces"
    if sorted(np.unique(m["tetrahedra"]).tolist()) != list(range(len(q))):
        return "V2 orphans"
    if set(m["regions"].tolist()) != set(range(len(m["region_names"]))):
        return "V2 regions"
    return ""


def run_child(seeds):
    """Child process: one JSON line per case."""
    from meshloom._core import mesh_plc
    for s in seeds:
        pts, facets = case(s)
        try:
            m = mesh_plc(pts, facets)
            out = {"seed": s, "outcome": "mesh", "invalid": valid(m), "regions": len(m["region_names"])}
        except (ValueError, RuntimeError) as e:
            out = {"seed": s, "outcome": "typed", "type": type(e).__name__, "msg": str(e)[:200]}
        except BaseException as e:  # panics (pyo3 PanicException) and anything else
            out = {"seed": s, "outcome": "untyped", "type": type(e).__name__, "msg": str(e)[:200]}
        print(json.dumps(out), flush=True)


def test_c13_fuzz():
    count = int(os.environ.get("MESHLOOM_FUZZ_CASES", "200"))
    offset = int(os.environ.get("MESHLOOM_FUZZ_OFFSET", "0"))
    seeds = list(range(offset, offset + count))
    here = Path(__file__).resolve()
    code = (f"import sys; sys.path.insert(0, {str(here.parent)!r}); "
            f"import {here.stem} as f; f.run_child({seeds!r})")
    proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8")
    # a reader thread and a queue: portable (selecting on pipes does not work on Windows)
    import queue
    import threading
    lines = queue.Queue()
    threading.Thread(target=lambda: [lines.put(x) for x in proc.stdout] and None or lines.put(None),
                     daemon=True).start()
    results = []
    while len(results) < len(seeds):
        try:
            line = lines.get(timeout=60)
        except queue.Empty:
            proc.kill()
            pytest.fail(f"hang: seed {seeds[len(results)]} made no progress for 60 s")
        if line is None:
            break
        results.append(json.loads(line))
    proc.wait(timeout=60)
    assert len(results) == len(seeds), f"the child stopped after {len(results)} cases: {proc.stderr.read()[-2000:]}"
    bad = [r for r in results if r["outcome"] == "untyped" or (r["outcome"] == "mesh" and r["invalid"])]
    assert not bad, bad[:5]
    meshes = sum(r["outcome"] == "mesh" for r in results)
    assert meshes > 0 and meshes < len(results), "the fuzz covers both meshes and refusals"
