# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Inputs from the 3D geometry engine on which meshloom hung or failed (2026-11-27).

Each case runs ``generate3d`` in a child process with a time limit, since the failure
being guarded against is a hang. It must end either in a mesh that passes V1 (exact
orient3d > 0 on the doubles), the V2 contract checks and V3(b) (the nodes of each
boundary face lie in their facet's plane), or in a ``RefineError`` that names the thin
facet, without coming near the limit.

- ``seed55``: two facets that share an edge and lie one rounding apart from one plane
  met at a dihedral angle refinement read as "parallel planes", so the small-angle rule
  did not apply and points on each facet split the other's subfacets without end.
- ``seed42``, ``seed46``, ``strip``, ``gap``: a facet with two input edges 0.4 pm to
  862 pm apart. Refinement would need far more points there than the cap; it now says so
  before it starts instead of reaching the cap point by point.
- ``seed11``, ``seed171``: hung and failed with "subfacet ... is degenerate in doubles"
  on the geometry branch's build; they mesh on main since earlier changes, kept here.
"""

import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from geometry_defect_cases import CASES  # noqa: E402

# seconds: the meshes take 5-25 s on a 2026 cloud runner; the errors are immediate
LIMIT = 300
ERROR_LIMIT = 60


def check(m, case):
    """V1, the V2 contract and V3(b); returns a reason or ''."""
    from fractions import Fraction as F
    q = [[F(x) for x in p] for p in m["nodes"].tolist()]
    tets = m["tetrahedra"].tolist()

    def det(a, b, c, d):
        u, v, w = ([q[x][i] - q[a][i] for i in range(3)] for x in (b, c, d))
        return u[0] * (v[1] * w[2] - v[2] * w[1]) - u[1] * (v[0] * w[2] - v[2] * w[0]) + \
            u[2] * (v[0] * w[1] - v[1] * w[0])

    if any(det(*t) <= 0 for t in tets):
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
    # V3(b): a boundary face's nodes lie in its facet's plane, within the rounding of doubles
    pts = np.asarray(case["points"])
    diag = float(np.linalg.norm(pts.max(0) - pts.min(0)))
    for tag, faces in m["boundary_faces"].items():
        loop = case["facets"][int(tag[1:])][0]
        P = [[F(x) for x in pts[i]] for i in loop]
        n = [F(0)] * 3
        for a, b in zip(P, P[1:] + P[:1]):
            n = [n[0] + a[1] * b[2] - a[2] * b[1], n[1] + a[2] * b[0] - a[0] * b[2], n[2] + a[0] * b[1] - a[1] * b[0]]
        nn = float(sum(c * c for c in n)) ** 0.5
        for x in set(faces.ravel().tolist()):
            d = sum(ni * (qi - oi) for ni, qi, oi in zip(n, q[x], P[0]))
            if abs(float(d)) / nn > 4 * 2.0 ** -52 * diag:
                return f"V3(b) facet {tag}"
    return ""


def run_child(name):
    """Child process: one JSON line with the outcome of case `name`."""
    from meshloom import RefineError
    case = CASES[name]
    try:
        m = meshloom.generate3d(np.array(case["points"], dtype=float), case["facets"], h=case["h"],
                                region_points=case["region_points"],
                                facet_tags=[f"f{i}" for i in range(len(case["facets"]))],
                                max_points=case["max_points"])
        out = {"outcome": "mesh", "invalid": check(m, case), "regions": len(m["region_names"])}
    except RefineError as e:
        out = {"outcome": "RefineError", "msg": str(e)}
    except BaseException as e:  # anything else, panics included
        out = {"outcome": type(e).__name__, "msg": str(e)[:500]}
    print(json.dumps(out), flush=True)


def outcome(name, limit):
    here = Path(__file__).resolve()
    code = f"import sys; sys.path.insert(0, {str(here.parent)!r}); import {here.stem} as t; t.run_child({name!r})"
    try:
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8",
                              timeout=limit)
    except subprocess.TimeoutExpired:
        pytest.fail(f"hang: case {name} did not end within {limit} s")
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("name", ["seed55", "seed11", "seed171"])
def test_meshes(name):
    r = outcome(name, LIMIT)
    assert r["outcome"] == "mesh", r
    assert r["invalid"] == "", r
    assert r["regions"] == len({n for _, n in CASES[name]["region_points"]}), r


@pytest.mark.parametrize("name, facet, edges", [
    ("seed42", 24, "8-9 and 10-11"),
    ("seed46", 26, "18-19 and 20-21"),
    ("strip", 8, "8-9 and 10-11"),
    ("gap", 0, "12-14 and 8-10"),
])
def test_thin_facet_is_refused(name, facet, edges):
    r = outcome(name, ERROR_LIMIT)
    assert r["outcome"] == "RefineError", r
    assert f"facet {facet} is thin: its input edges {edges} are" in r["msg"], r
    assert "more than the cap of 600000 (max_points)" in r["msg"], r
