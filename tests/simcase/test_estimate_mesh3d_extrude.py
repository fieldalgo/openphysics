# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""``simcase.estimate_mesh3d`` on the extrude route (a lone slab ``layers`` component).

Checks (fixed before implementation; coordinator decision on option C, 2026-11-28):

- E1 at 0.8 and 0.4 mm: the estimate is exact (the footprint meshed) and equals the tetrahedra of
  the mesh ``build_thermal3d_mesh`` makes; the answer and the ``I-MESH-ESTIMATE`` text name the
  extrude route and mark the time rough.
- A large lone slab whose lower bound A / (0.468 h^2) is over the limit is refused before any mesh,
  with ``E-MESH-ESTIMATE`` and the words "at least N tetrahedra on the extrude route".
- A lone slab whose lower bound is under the limit and whose exact count is over it: the estimate
  answers the lower bound, worded as one; ``build_thermal3d_mesh`` refuses after the footprint mesh
  and before extruding, with ``E-MESH-ESTIMATE`` and the same words for the exact count.
- The lower bound is never above the exact count (E1 at 0.8, 0.4, 0.2 mm).
- The meshloom and builder routes' parity with ``build_mesh3d`` is in test_estimate_mesh3d.py, unchanged.
"""
import copy
import math
import time

import pytest

meshloom = pytest.importorskip("meshloom")

import simcase  # noqa: E402
from simcase import build_thermal3d_mesh, estimate_mesh3d  # noqa: E402

import test_thermal_steady3d as k3  # noqa: E402


@pytest.mark.parametrize("h_mm", [0.8, 0.4])
def test_e1_s_estimate_is_the_extrude_mesh_s_count(h_mm):
    data = k3.e1(h_mm)
    t0 = time.perf_counter()
    found = estimate_mesh3d(copy.deepcopy(data))
    took = time.perf_counter() - t0
    made = len(build_thermal3d_mesh(copy.deepcopy(data)).tets)
    print(f"E1 {h_mm} mm: estimate {found.tetrahedra} ({found.count}), made {made}, {took * 1000:.1f} ms")
    assert (found.route, found.count) == ("extrude", "exact")
    assert found.tetrahedra == made
    (info,) = found.diagnostics
    assert info.code == "I-MESH-ESTIMATE"
    assert info.message.startswith(f"{made} tetrahedra on the extrude route (3 x ")
    assert "rough" in info.message
    assert found.seconds == made * 6e-4 and found.limit == 600000


@pytest.mark.parametrize("h_mm", [0.8, 0.4, 0.2])
def test_the_lower_bound_is_never_above_the_count(h_mm):
    from simcase import thermal3d
    from simcase.geometry_document import _pick, parse
    data = k3.e1(h_mm)
    comp = _pick(parse(data), None)
    h = h_mm / 1000
    lower = math.ceil(100e-6 / (thermal3d.FOOTPRINT_TRIANGLE_AREA * h * h) * (1 - 1e-12))
    exact = thermal3d.extrude_count(parse(data), comp, h)
    assert exact["exact"] and lower <= exact["footprint_triangles"], (lower, exact)


def test_a_lower_bound_over_the_limit_is_refused_before_any_mesh():
    data = k3.e1(0.01)
    t0 = time.perf_counter()
    with pytest.raises(simcase.GeometryError) as err:
        estimate_mesh3d(data)
    assert time.perf_counter() - t0 < 0.2
    assert err.value.code == "E-MESH-ESTIMATE" and err.value.path == "mesh.element_count_limit"
    assert str(err.value).startswith("component 'pkg': at least ")
    assert str(err.value).endswith(" tetrahedra on the extrude route (3 x footprint triangles x sub-layers); "
                                   "the limit is 600000 (mesh.element_count_limit)")


def test_an_exact_count_over_the_limit_is_refused_before_extruding():
    data = k3.e1(0.14)                       # lower bound 10,910 footprint triangles: the lower-bound branch
    data["mesh"]["element_count_limit"] = 700000
    found = estimate_mesh3d(copy.deepcopy(data))
    assert (found.route, found.count, found.tetrahedra) == ("extrude", "lower bound", 654600)
    assert found.diagnostics[0].message.startswith(
        "at least 654600 tetrahedra (extrude route; the exact count is known after the footprint mesh)")
    with pytest.raises(simcase.GeometryError) as err:
        build_thermal3d_mesh(copy.deepcopy(data))
    assert err.value.code == "E-MESH-ESTIMATE"
    assert str(err.value) == ("component 'pkg': 983040 tetrahedra on the extrude route (3 x footprint triangles x "
                              "sub-layers); the limit is 700000 (mesh.element_count_limit)")
