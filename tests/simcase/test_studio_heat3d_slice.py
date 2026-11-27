# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The Studio 3D heat answers' pure helpers (``simcase.studio.heat3d_slice``): the cut plane and the probe.

Pre-registered checks (fixed before implementation; never loosened):

- W17 (PR): the cut of E1's P1 temperature by an axis plane against an exact P1 slice computed
  here with rational arithmetic (``fractions.Fraction`` on the float node coordinates and
  temperatures): every point of the helper's slice matches one of the exact slice's points, the
  two have the same points, and max |T_cut - T_exact| <= 1e-12 K. Planes: z on the 1 mm layer
  interface (a mesh face plane), z = 1.2345 mm (off every node), x = 3.3 mm, y = 7.1 mm and the
  domain's own faces x = 0 and z = 2.5 mm; on E1 through meshine.extrude and E1 with a box via
  through meshloom.

Also tested, without numeric thresholds: the slice's triangles cover the cross-section (their area
equals the domain's 10 x 10 mm to 1e-12 relative) with no triangle twice; the probe answers the P1
interpolant (on E1, against refsol's exact layered slab, which P1 reproduces, |error| <= 1e-10 K),
its tetrahedron and barycentric coordinates, and None outside the meshed regions.
"""
from fractions import Fraction

import numpy as np
import pytest

pytest.importorskip("fastapi", reason="the studio extra is not installed")
meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from simcase import Document, run  # noqa: E402
from simcase.studio import heat3d_slice  # noqa: E402

import test_thermal_steady3d as k3  # noqa: E402

AXES = "xyz"
PLANES_MM = [("z", Fraction(1)), ("z", Fraction("1.2345")), ("x", Fraction("3.3")), ("y", Fraction("7.1")),
             ("x", Fraction(0)), ("z", Fraction("2.5"))]


@pytest.fixture(scope="module", params=[False, True], ids=["E1-extrude", "E1-via-meshloom"])
def solved(request):
    result = run(Document.from_dict(k3.e1(0.8, via=request.param)), verbose=False)
    return (np.asarray(result.mesh.nodes, dtype=float), np.asarray(result.mesh.tets, dtype=np.int64),
            np.asarray(result.temperature, dtype=float))


def exact_slice(nodes, tets, T, axis, c):
    """The exact P1 slice: ``{point (Fractions): T (Fraction)}`` of every tetrahedron the plane cuts,
    its edge crossings and the nodes on the plane, in rational arithmetic."""
    a = AXES.index(axis)
    out = {}
    for tet in tets.tolist():
        x = [Fraction(float(nodes[n, a])) - c for n in tet]
        if not (min(x) <= 0 <= max(x)) or all(v == 0 for v in x) or (sum(v == 0 for v in x) < 3 and
                                                                     (min(x) == 0 or max(x) == 0)):
            continue                                    # misses, or touches at a node or an edge only
        for i in range(4):
            if x[i] == 0:
                out[tuple(Fraction(float(v)) for v in nodes[tet[i]])] = Fraction(float(T[tet[i]]))
            for j in range(i + 1, 4):
                if x[i] * x[j] < 0:
                    t = x[i] / (x[i] - x[j])
                    pi = [Fraction(float(v)) for v in nodes[tet[i]]]
                    pj = [Fraction(float(v)) for v in nodes[tet[j]]]
                    p = tuple(pi[k] + t * (pj[k] - pi[k]) for k in range(3))
                    ti, tj = Fraction(float(T[tet[i]])), Fraction(float(T[tet[j]]))
                    out[p] = ti + t * (tj - ti)
    return out


@pytest.mark.parametrize("axis, at_mm", PLANES_MM, ids=[f"{a}={v}mm" for a, v in PLANES_MM])
def test_w17_the_cut_is_the_exact_p1_slice(solved, axis, at_mm):
    nodes, tets, T = solved
    c = Fraction(float(at_mm / 1000))                  # the plane the helper is given: the float at, exactly
    exact = exact_slice(nodes, tets, T, axis, c)
    cut = heat3d_slice.cut(nodes, tets, T, axis, float(c))
    assert len(cut.points) == len(exact), (len(cut.points), len(exact))
    keys = list(exact)
    ref = np.array([[float(v) for v in p] for p in keys])
    worst, seen = 0.0, set()
    for p, value in zip(cut.points, cut.values):
        d = np.abs(ref - p).max(axis=1)
        i = int(np.argmin(d))
        assert d[i] <= 1e-15, (p, ref[i])
        seen.add(i)
        worst = max(worst, abs(float(Fraction(float(value)) - exact[keys[i]])))
    assert len(seen) == len(keys)
    print(f"W17 {axis}={at_mm} mm: {len(keys)} points, max |T_cut - T_exact| = {worst:.3e} K")
    assert worst <= 1e-12


@pytest.mark.parametrize("axis, at_mm", PLANES_MM, ids=[f"{a}={v}mm" for a, v in PLANES_MM])
def test_the_cut_covers_the_cross_section_once(solved, axis, at_mm):
    nodes, tets, T = solved
    cut = heat3d_slice.cut(nodes, tets, T, axis, float(at_mm / 1000))
    p = cut.points[cut.triangles]
    area = 0.5 * np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)
    expected = (10e-3 * 2.5e-3) if axis in "xy" else 10e-3 * 10e-3
    assert abs(area.sum() - expected) <= 1e-12 * expected
    assert area.min() > 0
    assert len({tuple(sorted(t)) for t in cut.triangles.tolist()}) == len(cut.triangles)
    a = AXES.index(axis)
    assert np.all(cut.points[:, a] == float(at_mm / 1000))
    normal = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])[:, a]
    assert np.all(normal > 0)                           # every triangle faces +axis


def test_the_probe_answers_the_p1_interpolant():
    from refsol.thermal3d import layered_slab
    result = run(Document.from_dict(k3.e1(0.8)), verbose=False)
    nodes, tets, T = (np.asarray(result.mesh.nodes, dtype=float), np.asarray(result.mesh.tets, dtype=np.int64),
                      np.asarray(result.temperature, dtype=float))
    rng = np.random.default_rng(7)
    points = rng.uniform([0, 0, 0], [10e-3, 10e-3, 2.5e-3], size=(40, 3))
    points = np.vstack([points, nodes[[0, 5]], [[5e-3, 5e-3, 1e-3]], [[0.0, 0.0, 0.0]]])
    exact = layered_slab(points, position=[z * 1e-3 for z in k3.LEVELS_MM],
                         thermal_conductivity=list(k3.K.values()), prescribed_temperature=(300.0, 301.0))
    for p, expected in zip(points, exact.temperature):
        found = heat3d_slice.probe(nodes, tets, T, p)
        assert found is not None, p
        assert abs(found.value - expected) <= 1e-10, (p, found.value, expected)
        assert found.barycentric.min() >= -1e-12 and abs(found.barycentric.sum() - 1) <= 1e-12
        corners = nodes[tets[found.tetrahedron]]
        assert np.allclose(found.barycentric @ corners, p, rtol=0, atol=1e-15)
    for outside in ([11e-3, 5e-3, 1e-3], [5e-3, 5e-3, -1e-6], [5e-3, 5e-3, 2.6e-3]):
        assert heat3d_slice.probe(nodes, tets, T, np.array(outside)) is None


def test_a_probe_in_a_void_is_none():
    data = k3.e1(0.8, via=True)
    data["geometry"]["components"]["pkg"]["features"][1]["material"] = None      # the via is a hole
    result = run(Document.from_dict(data), verbose=False)
    nodes, tets, T = (np.asarray(result.mesh.nodes, dtype=float), np.asarray(result.mesh.tets, dtype=np.int64),
                      np.asarray(result.temperature, dtype=float))
    assert heat3d_slice.probe(nodes, tets, T, np.array([5e-3, 5e-3, 1.25e-3])) is None
    assert heat3d_slice.probe(nodes, tets, T, np.array([3e-3, 5e-3, 1.25e-3])) is not None
