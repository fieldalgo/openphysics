# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Stage 5, slice 4b: steady heat on cylinders and spheres in meshloom's builder shapes (E2, E3; P2, P3),
and ``thermal.steady3d``'s "builder" route.

The physics is computed on the direct path, ``simcase.build_mesh3d`` + ``galerkin.solve_steady_heat_3d``,
which is the gated one; the kind must give the same heat rate and nodal temperatures on the same
documents (slice 6's row), to 1e-12 relative.

Pre-registered (the design's cases and thresholds, coordinator decision 2026-11-27):
- E2 (C4 as a document, in m): slab [-1,1]^2 x [0,1] with k_s = 1 W/(m K), via r = 0.3 with
  k_v = 100 W/(m K); T = 300 K on z0 and 301 K on z1, sides insulated. Q = dT/L (k_v pi r^2 +
  k_s (A - pi r^2)) = 31.99 W with A = 4. P2: e_Q = |Q_h - Q| / Q (Q_h the reaction on z1) and its
  least-squares slope against s = 2 pi r / m (m from I-SURFACE-SAMPLED), at h {0.2, 0.1, 0.05}:
  e_Q(0.05) <= 1e-2 and slope >= 1.5 (main).
- E3 (C11 as a document): hole r = 0.5, k = 1 on (0.5, 0.75), k = 4 on (0.75, 1); T = 301 K on the
  inner surface and 300 K on the outer. Q = 16 pi / 3 W. P3: slope of e_Q against h >= 1.6 and
  e_Q(0.05) <= 5e-3 at h {0.2, 0.1, 0.05} (main); P3(a): Q_h equals V24's C_h = u^T K u on the same
  mesh, computed independently as sum_T k_T |grad u_T|^2 V_T with u = T - 300 K, within 1e-9
  relative (PR at h 0.2 and 0.1, main at all three).
- The kind against the direct path: Q_h and nodal T to 1e-12 relative, at each size the tier runs.
- A fixed temperature on an interior part (C4's via.side, C11's sb.surface) is refused with
  "Fixed temperature needs an outer face; <name> is inside" (E-CONTRACT).
PR runs h {0.2, 0.1}: P3(a), the refusals and the kind's equality are gated; P2 and P3 values are
reported only. The main-only tests are defined only with OPENPHYSICS_GEOMETRY3D_FULL=1 (no skip; the
geometry3d-full job checks in its JUnit report that they ran).
"""

import copy
import math
import os
import re

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from simcase import Document, DocumentError, build_mesh3d, run  # noqa: E402

FULL = os.environ.get("OPENPHYSICS_GEOMETRY3D_FULL") == "1"
PR_SIZES = (0.2, 0.1)
MAIN_SIZES = (0.2, 0.1, 0.05)
R, KS, KV, AREA = 0.3, 1.0, 100.0, 4.0
Q_E2 = KV * math.pi * R * R + KS * (AREA - math.pi * R * R)
Q_E3 = 16 * math.pi / 3


def _document(component, materials, prescribed, h):
    return {"openphysics": "0.3", "name": "builder heat",
            "geometry": {"version": 1, "components": {"c": component}},
            "materials": materials,
            "physics": {"heat": {"type": "thermal.steady3d", "prescribed_temperature": prescribed}},
            "mesh": {"element_size": f"{h} m"}}


def e2(h, prescribed=None):
    comp = {"dimension": "3d", "length_unit": "m",
            "domain": {"xmin": -1, "xmax": 1, "ymin": -1, "ymax": 1, "zmin": 0, "zmax": 1},
            "background": {"material": "slab"},
            "features": [{"name": "via", "type": "cylinder", "cx": 0, "cy": 0, "r": R, "zmin": 0, "zmax": 1,
                          "material": "copper"}]}
    mats = {"slab": {"thermal_conductivity": f"{KS} W/(m K)"}, "copper": {"thermal_conductivity": f"{KV} W/(m K)"}}
    return _document(comp, mats, prescribed or {"z0": "300 K", "z1": "301 K"}, h)


def e3(h, prescribed=None):
    comp = {"dimension": "3d", "length_unit": "m",
            "domain": {"xmin": -1.2, "xmax": 1.2, "ymin": -1.2, "ymax": 1.2, "zmin": -1.2, "zmax": 1.2},
            "background": {"material": None},
            "features": [{"name": "sc", "type": "sphere", "cx": 0, "cy": 0, "cz": 0, "r": 1, "material": "outer"},
                         {"name": "sb", "type": "sphere", "cx": 0, "cy": 0, "cz": 0, "r": 0.75, "material": "inner"},
                         {"name": "sa", "type": "sphere", "cx": 0, "cy": 0, "cz": 0, "r": 0.5, "material": None}]}
    mats = {"inner": {"thermal_conductivity": "1 W/(m K)"}, "outer": {"thermal_conductivity": "4 W/(m K)"}}
    return _document(comp, mats, prescribed or {"sa.surface": "301 K", "sc.surface": "300 K"}, h)


# ----------------------------------------------------------------------------- the direct path

def _nodes(result, name):
    faces = result.mesh.tagged_faces.get(name)
    if faces is None:
        faces = result.provenance_faces[name]
    return np.unique(np.asarray(faces))


def direct(document, kappa, fixed, measured):
    """build_mesh3d + galerkin.solve_steady_heat_3d: (result, solution, Q_h on ``measured``)."""
    from galerkin.thermal3d import solve_steady_heat_3d
    built = build_mesh3d(document)
    prescribed = {}
    for name, value in fixed.items():
        for n in _nodes(built, name).tolist():
            prescribed[n] = value
    solution = solve_steady_heat_3d(built.mesh, thermal_conductivity=kappa,
                                    prescribed_temperature=dict(sorted(prescribed.items())))
    q = float(np.asarray(solution.reaction_heat_rate)[_nodes(built, measured)].sum())
    return built, solution, q


def e2_direct(h):
    return direct(e2(h), {"background": KS, "via": KV}, {"z0": 300.0, "z1": 301.0}, "z1")


def e3_direct(h):
    return direct(e3(h), {"sb": 1.0, "sc": 4.0}, {"sa.surface": 301.0, "sc.surface": 300.0}, "sa.surface")


def ring_points(built) -> int:
    (info,) = [d for d in built.diagnostics if d.code == "I-SURFACE-SAMPLED"]
    return int(re.search(r"m = (\d+) points per ring", info.message).group(1))


def energy(built, solution, kappa) -> float:
    """V24's C_h = u^T K u with u = T - 300 K, as sum_T k_T |grad u_T|^2 V_T (independent of the assembly)."""
    mesh = built.mesh
    u = np.asarray(solution.temperature) - 300.0
    p = mesh.nodes[mesh.tets]
    e = p[:, 1:] - p[:, :1]                                      # (T, 3, 3) edge vectors
    du = u[mesh.tets[:, 1:]] - u[mesh.tets[:, :1]]               # (T, 3)
    grad = np.linalg.solve(e, du[..., None])[..., 0]             # e @ g = du
    vol = np.abs(np.linalg.det(e)) / 6
    k = np.array([kappa[mesh.region_names[r]] for r in mesh.regions])
    return float(np.sum(k * np.einsum("ti,ti->t", grad, grad) * vol))


def _slope(x, y):
    return float(np.polyfit(np.log(x), np.log(y), 1)[0])


# ----------------------------------------------------------------------------- PR tier

@pytest.mark.parametrize("h", PR_SIZES)
def test_p3a_heat_rate_equals_the_energy_on_the_same_mesh(h):
    built, solution, q = e3_direct(h)
    c_h = energy(built, solution, {"sb": 1.0, "sc": 4.0})
    print(f"E3 h={h}: Q_h {q:.10g} W, C_h {c_h:.10g}, e_Q {abs(q - Q_E3) / Q_E3:.3e}")
    assert abs(q - c_h) <= 1e-9 * abs(c_h)


@pytest.mark.parametrize("h", PR_SIZES)
def test_p2_values_are_reported(h):
    built, _, q = e2_direct(h)
    m = ring_points(built)
    print(f"E2 h={h}: m {m}, s {2 * math.pi * R / m:.4g}, Q_h {q:.10g} W, Q {Q_E2:.10g} W, "
          f"e_Q {abs(q - Q_E2) / Q_E2:.3e}")
    assert q > 0


def _kind_matches_direct(document, direct_result, measured):
    built, solution, q = direct_result
    result = run(Document.from_dict(copy.deepcopy(document)), verbose=False)
    assert result.route == "builder"
    assert result.mesh.nodes.tobytes() == built.mesh.nodes.tobytes()
    t_kind, t_direct = np.asarray(result.temperature), np.asarray(solution.temperature)
    assert np.max(np.abs(t_kind - t_direct)) <= 1e-12 * np.max(np.abs(t_direct))
    q_kind = result.heat_rates_by_boundary()[measured]
    assert abs(q_kind - q) <= 1e-12 * abs(q)
    summary = result.summary()
    assert summary["mesh_route"] == "builder"
    assert any(d["code"] == "I-SURFACE-SAMPLED" for d in summary["diagnostics"])


@pytest.mark.parametrize("h", PR_SIZES)
def test_the_kind_equals_the_direct_path_e2(h):
    _kind_matches_direct(e2(h), e2_direct(h), "z1")


@pytest.mark.parametrize("h", PR_SIZES)
def test_the_kind_equals_the_direct_path_e3(h):
    _kind_matches_direct(e3(h), e3_direct(h), "sa.surface")


@pytest.mark.parametrize("make, name", [(e2, "via.side"), (e3, "sb.surface")])
def test_a_fixed_temperature_on_an_interior_part_is_refused(make, name):
    base = make(0.2)
    prescribed = dict(base["physics"]["heat"]["prescribed_temperature"])
    prescribed[name] = "300 K"
    with pytest.raises(DocumentError) as err:
        Document.from_dict(make(0.2, prescribed))
    (d,) = [x for x in err.value.diagnostics if x.severity == "error"]
    assert d.code == "E-CONTRACT"
    assert d.path == f"physics.heat.prescribed_temperature.{name}"
    assert d.message == f"Fixed temperature needs an outer face; {name} is inside"


def test_an_unknown_boundary_name_is_refused():
    with pytest.raises(DocumentError) as err:
        Document.from_dict(e2(0.2, {"z0": "300 K", "nowhere": "301 K"}))
    assert any(d.code == "E-SELECTION-UNKNOWN" and d.path == "physics.heat.prescribed_temperature.nowhere"
               for d in err.value.diagnostics)


def test_default_tags_left_unnamed_are_reported_insulated():
    doc = Document.from_dict(e2(0.2))
    named = sorted(d.path.rsplit(".", 1)[1] for d in doc.diagnostics if d.code == "I-DEFAULT-BOUNDARY")
    assert named == ["x0", "x1", "y0", "y1"]


# ----------------------------------------------------------------------------- main tier

if FULL:
    def test_p2_via_heat_rate_converges():
        s, e = [], []
        for h in MAIN_SIZES:
            built, _, q = e2_direct(h)
            s.append(2 * math.pi * R / ring_points(built))
            e.append(abs(q - Q_E2) / Q_E2)
        print("P2", s, e, _slope(s, e))
        assert e[-1] <= 1e-2
        assert _slope(s, e) >= 1.5

    def test_p3_shell_heat_rate_converges_and_equals_the_energy():
        e = []
        for h in MAIN_SIZES:
            built, solution, q = e3_direct(h)
            c_h = energy(built, solution, {"sb": 1.0, "sc": 4.0})
            assert abs(q - c_h) <= 1e-9 * abs(c_h), h
            e.append(abs(q - Q_E3) / Q_E3)
        print("P3", e, _slope(MAIN_SIZES, e))
        assert e[-1] <= 5e-3
        assert _slope(MAIN_SIZES, e) >= 1.6

    def test_the_kind_equals_the_direct_path_at_the_finest_size():
        _kind_matches_direct(e2(0.05), e2_direct(0.05), "z1")
        _kind_matches_direct(e3(0.05), e3_direct(0.05), "sa.surface")
