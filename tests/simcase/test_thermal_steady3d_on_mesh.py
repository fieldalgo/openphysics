# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""``thermal.steady3d`` on an existing mesh: ``build_thermal3d_mesh``, ``mesh3d_to_arrays`` /
``mesh3d_from_arrays`` and ``solve_thermal3d`` (decision 2026-11-27-openphysics-studio-3d-run-route).

Checks (fixed before implementation):

- ``solve_thermal3d(doc, build_thermal3d_mesh(doc))`` against ``simcase.run(doc)``, bitwise: SHA-256
  of the nodes, tetrahedra, temperature and reaction heat rate, and the summary's values equal, on
  all three routes (E1 through meshine.extrude, E1 with a box via through meshloom, E2 through
  meshloom's builder).
- The array round trip is bitwise: every array of ``mesh3d_to_arrays`` equal after
  ``mesh3d_from_arrays`` and a second ``mesh3d_to_arrays``, through an ``.npz`` file read with
  ``allow_pickle=False``; and solving on the round-tripped mesh gives the same SHA-256.
- The route is the kind's: a lone slab ``layers`` component gives the extrude mesh, also from a
  document with no physics block; a mesh of the other route is refused by name.
"""

import copy
import hashlib
import io

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

import simcase  # noqa: E402
from simcase import (Document, DocumentError, build_thermal3d_mesh, mesh3d_from_arrays, mesh3d_to_arrays,  # noqa: E402
                     run, solve_thermal3d)

import test_thermal_steady3d as k3  # noqa: E402
import test_thermal_steady3d_builders as kb  # noqa: E402

CASES = {"E1-extrude": lambda: k3.e1(0.8), "E1-via-meshloom": lambda: k3.e1(0.8, via=True),
         "E2-builder": lambda: kb.e2(0.2)}
ROUTES = {"E1-extrude": "extrude", "E1-via-meshloom": "meshloom", "E2-builder": "builder"}


def _sha(result):
    h = hashlib.sha256()
    for a in (np.asarray(result.mesh.nodes, dtype=float), np.asarray(result.mesh.tets, dtype=np.int64),
              np.asarray(result.temperature, dtype=float), np.asarray(result.reaction_heat_rate, dtype=float)):
        h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


def _values(result):
    s = result.summary()
    return {k: v for k, v in s.items() if k != "timing"}


def _npz(arrays):
    buf = io.BytesIO()
    np.savez(buf, **arrays)
    buf.seek(0)
    with np.load(buf, allow_pickle=False) as f:
        return {k: f[k] for k in f.files}


def test_the_names_are_public():
    assert {"build_thermal3d_mesh", "solve_thermal3d", "mesh3d_to_arrays", "mesh3d_from_arrays"} <= \
        set(simcase.__all__)


@pytest.mark.parametrize("case", list(CASES))
def test_solving_on_the_kind_s_mesh_equals_run_bit_for_bit(case):
    data = CASES[case]()
    expected = run(Document.from_dict(copy.deepcopy(data)), verbose=False)
    mesh = build_thermal3d_mesh(copy.deepcopy(data))
    got = solve_thermal3d(Document.from_dict(copy.deepcopy(data)), mesh, verbose=False)
    assert got.route == expected.route == ROUTES[case]
    assert _sha(got) == _sha(expected)
    assert _values(got) == _values(expected)
    assert [d.code for d in got.doc.diagnostics] == [d.code for d in expected.doc.diagnostics]


@pytest.mark.parametrize("case", list(CASES))
def test_the_array_round_trip_is_bitwise(case):
    data = CASES[case]()
    mesh = build_thermal3d_mesh(copy.deepcopy(data))
    arrays = mesh3d_to_arrays(mesh)
    assert all(isinstance(v, np.ndarray) and v.dtype != object for v in arrays.values())
    back = mesh3d_from_arrays(_npz(arrays), copy.deepcopy(data))
    again = mesh3d_to_arrays(back)
    assert sorted(again) == sorted(arrays)
    for k in arrays:
        assert again[k].dtype == arrays[k].dtype and again[k].shape == arrays[k].shape, k
        assert again[k].tobytes() == arrays[k].tobytes(), k
    direct = solve_thermal3d(Document.from_dict(copy.deepcopy(data)), mesh, verbose=False)
    through = solve_thermal3d(Document.from_dict(copy.deepcopy(data)), back, verbose=False)
    assert _sha(through) == _sha(direct)
    assert _values(through) == _values(direct)


def test_a_lone_slab_meshes_on_the_extrude_route_without_physics():
    data = k3.e1(0.8)
    geometry_only = {k: v for k, v in data.items() if k in ("openphysics", "geometry", "mesh")}
    a, b = build_thermal3d_mesh(geometry_only), build_thermal3d_mesh(data)
    assert mesh3d_to_arrays(a).keys() == mesh3d_to_arrays(b).keys()
    for k, v in mesh3d_to_arrays(a).items():
        assert v.tobytes() == mesh3d_to_arrays(b)[k].tobytes(), k
    with pytest.raises(simcase.GeometryError):
        simcase.build_mesh3d(geometry_only)          # build_mesh3d still refuses it, as before


def test_a_mesh_of_the_other_route_is_refused():
    slab, via = k3.e1(0.8), k3.e1(0.8, via=True)
    with pytest.raises(DocumentError) as err:
        solve_thermal3d(Document.from_dict(slab), build_thermal3d_mesh(via), verbose=False)
    assert "extrude" in str(err.value)
    with pytest.raises(DocumentError) as err:
        solve_thermal3d(Document.from_dict(via), build_thermal3d_mesh(slab), verbose=False)
    assert "meshloom" in str(err.value)
