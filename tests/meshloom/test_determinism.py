# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Determinism and scale of ``meshloom.generate3d``: V26, V27 and V28.

Rows of docs/packages/meshine/validation3d.md, with the inputs fixed before measuring
(plan 5 criteria):

- V26: C1-C9 at h = 0.1. The SHA-256 of the canonical arrays (nodes, tetrahedra,
  regions, node_source, boundary faces by tag, interfaces by region pair) is the same over
  3 fresh processes and 2 runs in this process. C3 at h = 0.1 (about 1.3 million
  tetrahedra, minutes per run) runs only with ``MESHLOOM_V26_FULL=1``; its record and the
  comparison across Python versions (the same wheel on 3.12 and 3.15, through
  ``python test_determinism.py v26 CASE ...``) are kept with the plan 5 measurements.
- V27: C1 at h = 0.2, 0.1, 0.05 and C3 at h = 0.8, 0.4, with the input points, the size
  and the region points scaled by 2^-20 and 2^10 (exact): connectivity, regions, node
  sources and faces are identical, and the nodes are the unscaled nodes times the factor,
  bit for bit.
- V28: C2 at h = 0.12, 0.06, C3 at 0.8, 0.4 and C5 at 0.24, 0.12 in micrometres,
  millimetres, metres, kilometres and 1e6 m (points, size and region points times
  1e-6 ... 1e6, rounded to doubles): region volume fractions equal to the metre mesh's
  within relative 1e-9, tetrahedron counts within relative 0.1, and V1-V5 on each mesh
  (V4 with the exact volumes on C2 and C3, V5 on C5's sphere). The second size of each
  case runs with the slow studies.
"""

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

import quality_cases as Q  # noqa: E402
import test_adversarial as A  # noqa: E402
from test_builder import delta  # noqa: E402

V26_CASES = ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"]
V26_CI = [c for c in V26_CASES if c != "C3" or os.environ.get("MESHLOOM_V26_FULL") == "1"]


def digest(m):
    """SHA-256 of the canonical arrays of a generate3d mesh."""
    d = hashlib.sha256()
    for key in ("nodes", "tetrahedra", "regions", "node_source"):
        d.update(np.ascontiguousarray(m[key]).tobytes())
    for tag in sorted(m["boundary_faces"]):
        d.update(tag.encode() + b"\0" + np.ascontiguousarray(m["boundary_faces"][tag]).tobytes())
    for pair in sorted(m["interfaces"]):
        d.update(np.array(pair, dtype=np.int64).tobytes() + np.ascontiguousarray(m["interfaces"][pair]).tobytes())
    return d.hexdigest()


def v26_digests(cases):
    return [digest(Q.generate(c, 0.1)) for c in cases]


def test_v26_c1_c9_are_deterministic():
    here = Path(__file__).resolve()
    cmd = [sys.executable, str(here), "v26", *V26_CI]
    procs = [subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True, cwd=here.parent) for _ in range(3)]
    inproc = [v26_digests(V26_CI) for _ in range(2)]
    fresh = []
    for p in procs:
        out, _ = p.communicate()
        assert p.returncode == 0
        fresh.append(out.split())
    assert all(len(d) == len(V26_CI) for d in fresh + inproc)
    assert all(d == inproc[0] for d in fresh + inproc), fresh + inproc


def scaled(kw, s):
    """The case's arguments with points, size and region points times s (rounded)."""
    kw = dict(kw)
    kw["points"] = np.asarray(kw["points"], dtype=np.float64) * s
    kw["h"] = kw["h"] * s
    if "region_points" in kw:
        kw["region_points"] = [(tuple(float(x) * s for x in p), n) for p, n in kw["region_points"]]
    return kw


V27 = [("C1", 0.2), ("C1", 0.1), pytest.param("C1", 0.05, marks=pytest.mark.slow), ("C3", 0.8),
       pytest.param("C3", 0.4, marks=pytest.mark.slow)]


@pytest.mark.parametrize("case,h", V27)
def test_v27_dyadic_scaling_is_exact(case, h):
    kw = Q.case_kwargs(case, h)
    m0 = meshloom.generate3d(**kw)
    for k in (-20, 10):
        s = 2.0 ** k
        m = meshloom.generate3d(**scaled(kw, s))
        for key in ("tetrahedra", "regions", "node_source"):
            assert np.array_equal(m[key], m0[key]), (case, h, k, key)
        assert sorted(m["boundary_faces"]) == sorted(m0["boundary_faces"])
        for tag in m0["boundary_faces"]:
            assert np.array_equal(m["boundary_faces"][tag], m0["boundary_faces"][tag]), (case, h, k, tag)
        assert sorted(m["interfaces"]) == sorted(m0["interfaces"])
        for pair in m0["interfaces"]:
            assert np.array_equal(m["interfaces"][pair], m0["interfaces"][pair]), (case, h, k, pair)
        assert m["nodes"].tobytes() == (m0["nodes"] * s).tobytes(), (case, h, k)


UNITS = (1e-6, 1e-3, 1.0, 1e3, 1e6)
V28 = [("C2", 0.12), pytest.param("C2", 0.06, marks=pytest.mark.slow), ("C3", 0.8),
       pytest.param("C3", 0.4, marks=pytest.mark.slow), ("C5", 0.24),
       pytest.param("C5", 0.12, marks=pytest.mark.slow)]
EXACT_VOLUMES = {"C2": [1.0], "C3": [8.0, 100.0, 142.0]}


def region_volumes(m):
    x = m["nodes"][m["tetrahedra"]]
    v = np.einsum("ij,ij->i", x[:, 1] - x[:, 0], np.cross(x[:, 2] - x[:, 0], x[:, 3] - x[:, 0])) / 6
    return np.array([v[m["regions"] == r].sum() for r in range(len(m["region_names"]))])


def check_v1_v5(case, kw, m, u, tags):
    facets = kw["facets"]
    volumes = [w * u ** 3 for w in EXACT_VOLUMES[case]] if case in EXACT_VOLUMES else list(region_volumes(m))
    A.check(m, kw["points"], {str(i): f for i, f in enumerate(facets)}, volumes, True, euler=case != "C5")
    if case == "C5":  # V5: the nodes of the locked sphere are its input points, on the sphere
        on = sorted({v for i in kw["locked_facets"] if tags[i] == "sphere" for v in facets[i][0]})
        worst = max(delta(p, "sphere", (0.0, 0.0, 0.0), 0.5 * u) for p in kw["points"][on])
        assert worst <= 1e-15, (case, u, float(worst))


@pytest.mark.parametrize("case,h", V28)
def test_v28_units(case, h):
    base = Q.case_kwargs(case, h)
    tags = base.pop("facet_tags", None)  # boundary faces by facet index, for V3
    out = {}
    for u in UNITS:
        kw = scaled(base, u)
        m = meshloom.generate3d(**kw)
        check_v1_v5(case, kw, m, u, tags)
        vol = region_volumes(m)
        out[u] = (vol / vol.sum(), len(m["tetrahedra"]))
    frac, count = out[1.0]
    for u, (f, n) in out.items():
        assert np.all(np.abs(f - frac) <= 1e-9 * frac), (case, h, u, f, frac)
        assert abs(n - count) <= 0.1 * count, (case, h, u, n, count)


if __name__ == "__main__":  # python test_determinism.py v26 CASE ...: the digests, one per case
    if sys.argv[1:2] == ["v26"]:
        print(" ".join(v26_digests(sys.argv[2:])))
