# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Stage 5, slice 4a: electromagnetic cavities from a geometry document, end to end.

Each case goes geometry document -> ``simcase.build_mesh3d`` (meshloom, boxes only) ->
galerkin's public cavity solvers -> an independent analytic reference from galerkin_refsol.

Pre-registered checks (fixed before measuring; never loosened):

- P4: E4, the empty cavity: one ``3d`` component, domain [0, 1]^3 m, vacuum, no features,
  PEC on every face, through ``galerkin.solve_cavity``, against
  ``refsol.cavity.rectangular_cavity_modes``. Metric: the relative k^2 error of the first
  cluster (the three degenerate modes at k^2 = 2 pi^2), the maximum over the three.
  Thresholds: monotone decrease over h = 0.24, 0.12, 0.06 m; observed order >= 1.5; finest
  < 1e-2.
- P5: E5, the slab-loaded cavity: the same domain with a later ``box`` over z in [0, 0.5]
  (full x and y) of eps_r = 4, the rest vacuum, PEC on every face, through
  ``galerkin.solve_material_cavity``, against
  ``refsol.material_cavity.slab_loaded_cavity_modes``. Metric: the computed modes in
  ascending order matched to the first four reference roots in ascending order, the
  maximum relative k^2 error over the four. Thresholds: monotone; order >= 1.5; finest
  < 2e-2.

The observed order is the least-squares slope of log e against log h over the three
sizes; the two pairwise orders are reported, not gated. The spurious-mode count, the
computed and reference k^2, the mesh sizes and wall times are reported (as JUnit
properties and on stdout), not gated.

Tier: the convergence studies run on main pushes and manual dispatch only
(``OPENPHYSICS_GEOMETRY3D_FULL=1``, the CI job ``geometry3d-full``). Pull requests run a
smoke test at h = 0.24 m that checks only that both cases mesh and solve.
"""

import math
import os
import time

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from galerkin import solve_cavity, solve_material_cavity  # noqa: E402
from refsol.cavity import rectangular_cavity_modes  # noqa: E402
from refsol.material_cavity import slab_loaded_cavity_modes  # noqa: E402
from simcase import build_mesh3d  # noqa: E402

FULL = os.environ.get("OPENPHYSICS_GEOMETRY3D_FULL") == "1"
SIZES = (0.24, 0.12, 0.06)               # m, the document's mesh element_size
C0 = 299_792_458.0
EPS_SLAB = 4.0
SLAB_TOP = 0.5
E4_MODES = 5                              # the 2 pi^2 cluster (3) and the 3 pi^2 pair (TE/TM111)
E5_MODES = 6                              # the first four roots and the next degenerate pair
SPURIOUS_TOLERANCE = 0.1                  # reported only: a mode farther than this from every root


def cavity_document(features, element_size):
    domain = {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1, "zmin": 0, "zmax": 1}
    component = {"dimension": "3d", "length_unit": "m", "domain": domain,
                 "background": {"material": "vacuum"}, "features": features}
    return {"openphysics": "0.3", "geometry": {"version": 1, "components": {"cavity": component}},
            "mesh": {"element_size": f"{element_size} m"}}


def e4_document(h):
    return cavity_document([], h)


def e5_document(h):
    slab = {"name": "slab", "type": "box", "xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1,
            "zmin": 0, "zmax": SLAB_TOP, "material": "dielectric"}
    return cavity_document([slab], h)


def frequency(k_squared):
    return C0 * math.sqrt(k_squared) / (2 * math.pi)


def e4_reference():
    limit = frequency(4 * math.pi ** 2)
    return np.array(sorted(m.wavenumber_squared for m in
                           rectangular_cavity_modes(box_size=(1.0, 1.0, 1.0), frequency_limit=limit)))


def e5_reference():
    limit = frequency(3 * math.pi ** 2)
    modes = slab_loaded_cavity_modes(box_size=(1.0, 1.0, 1.0), thickness=SLAB_TOP, frequency_limit=limit,
                                     relative_permittivity=(EPS_SLAB, 1.0))
    return np.array(sorted(float(np.real(m.wavenumber_squared)) for m in modes))


def solve_e4(h):
    start = time.perf_counter()
    mesh = build_mesh3d(e4_document(h)).mesh
    meshed = time.perf_counter()
    assert mesh.region_names == ["background"]
    assert set(mesh.tagged_faces) == {"x0", "x1", "y0", "y1", "z0", "z1"}
    # Target below the first cluster: the nearest modes are the lowest ones.
    result = solve_cavity(mesh, pec_faces=None, mode_count=E4_MODES, target_frequency=frequency(math.pi ** 2))
    solved = time.perf_counter()
    assert set(result.pec_faces) == {"x0", "x1", "y0", "y1", "z0", "z1"}
    return mesh, np.sort(np.asarray(result.wavenumber_squared, dtype=float)), meshed - start, solved - meshed


def solve_e5(h):
    start = time.perf_counter()
    mesh = build_mesh3d(e5_document(h)).mesh
    meshed = time.perf_counter()
    assert sorted(mesh.region_names) == ["background", "slab"]
    assert set(mesh.tagged_faces) == {"x0", "x1", "y0", "y1", "z0", "z1"}
    centroid_z = mesh.nodes[mesh.tets].mean(axis=1)[:, 2]
    slab = mesh.region_names.index("slab")
    assert np.array_equal(mesh.regions == slab, centroid_z < SLAB_TOP)
    result = solve_material_cavity(mesh, relative_permittivity={"slab": EPS_SLAB, "background": 1.0},
                                   mode_count=E5_MODES, target_frequency=frequency(0.5 * math.pi ** 2))
    solved = time.perf_counter()
    assert result.lossless
    k2 = np.asarray(result.wavenumber_squared)
    assert np.all(np.abs(k2.imag) <= 1e-9 * np.abs(k2.real))
    return mesh, np.sort(k2.real), meshed - start, solved - meshed


def spurious_count(computed, reference):
    """Computed modes farther than SPURIOUS_TOLERANCE (relative) from every reference root."""
    return int(sum(np.min(np.abs(reference - k2)) / k2 > SPURIOUS_TOLERANCE for k2 in computed))


def study(solve, reference, metric_count, record_property, label):
    errors, rows = [], []
    for h in SIZES:
        mesh, computed, mesh_time, solve_time = solve(h)
        error = float(np.max(np.abs(computed[:metric_count] - reference[:metric_count]) / reference[:metric_count]))
        errors.append(error)
        rows.append({"h": h, "nodes": mesh.num_nodes, "tets": mesh.num_tets, "error": error,
                     "spurious": spurious_count(computed, reference),
                     "k2_over_pi2": [round(float(v) / math.pi ** 2, 8) for v in computed],
                     "mesh_s": round(mesh_time, 2), "solve_s": round(solve_time, 2)})
    logs = np.log(np.array(SIZES)), np.log(np.array(errors))
    order = float(np.polyfit(*logs, 1)[0])
    pairwise = [float((logs[1][i] - logs[1][i + 1]) / (logs[0][i] - logs[0][i + 1])) for i in range(2)]
    record_property(f"{label}_reference_k2_over_pi2", [round(float(v) / math.pi ** 2, 8) for v in reference[:metric_count + 2]])
    record_property(f"{label}_rows", rows)
    record_property(f"{label}_order", round(order, 4))
    record_property(f"{label}_pairwise_orders", [round(p, 4) for p in pairwise])
    print(f"{label} reference k2/pi2 {[round(float(v) / math.pi ** 2, 6) for v in reference[:metric_count + 2]]}")
    for row in rows:
        print(f"{label} {row}")
    print(f"{label} order {order:.4f} pairwise {[round(p, 4) for p in pairwise]}")
    return errors, order


@pytest.mark.skipif(not FULL, reason="main-tier study: OPENPHYSICS_GEOMETRY3D_FULL=1 (CI job geometry3d-full)")
def test_p4_empty_cavity_first_cluster_converges(record_property):
    reference = e4_reference()
    assert np.allclose(reference[:3], 2 * math.pi ** 2) and reference[2] < reference[3]
    errors, order = study(solve_e4, reference, 3, record_property, "P4")
    assert errors[0] > errors[1] > errors[2], errors
    assert order >= 1.5, (order, errors)
    assert errors[-1] < 1e-2, errors


@pytest.mark.skipif(not FULL, reason="main-tier study: OPENPHYSICS_GEOMETRY3D_FULL=1 (CI job geometry3d-full)")
def test_p5_slab_loaded_cavity_first_four_modes_converge(record_property):
    reference = e5_reference()
    assert len(reference) >= E5_MODES
    errors, order = study(solve_e5, reference, 4, record_property, "P5")
    assert errors[0] > errors[1] > errors[2], errors
    assert order >= 1.5, (order, errors)
    assert errors[-1] < 2e-2, errors


@pytest.mark.parametrize("solve", [solve_e4, solve_e5], ids=["E4", "E5"])
def test_cavity_cases_mesh_and_solve_at_the_coarsest_size(solve):
    """Pull-request smoke test at h = 0.24 m: the case meshes and solves; no numeric threshold."""
    mesh, computed, _, _ = solve(SIZES[0])
    assert mesh.num_tets > 0
    assert computed.shape == (E4_MODES if solve is solve_e4 else E5_MODES,)
    assert np.all(np.isfinite(computed)) and np.all(computed > 0)
