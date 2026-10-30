# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Layered tetrahedral meshes from ``meshine.extrude``, graded by the pre-registered
3D plan (docs/packages/meshine/validation3d.md): the mesh contract and exact
geometry (V1-V4), a P1 Poisson solution converging on an extruded cube (V21), a
layered conduction problem that P1 reproduces exactly (V22), determinism (V26),
unit independence (V28) and the MSH round trip (V31).
"""

import hashlib
import subprocess
import sys
from fractions import Fraction

import numpy as np
import pytest

from meshine import Domain, box_sides, check, extrude, generate, rectangle, write_msh

galerkin = pytest.importorskip("galerkin")


def chip(scale=1.0, size=1.0, layer_size=None):
    """C3: substrate 10x10x[0,1], die 4x4x0.5 centred on it, mold 10x10x[1,2.5] around the die."""
    s = scale
    d = Domain(size=size * s)
    d.add_region("die_zone", rectangle(-2 * s, -2 * s, 2 * s, 2 * s))
    d.add_region("rest", rectangle(-5 * s, -5 * s, 5 * s, 5 * s), holes=[rectangle(-2 * s, -2 * s, 2 * s, 2 * s)])
    fp = generate(d, box_sides(-5 * s, 5 * s, -5 * s, 5 * s))
    mats = {"die_zone": ["substrate", "die", "mold_high"], "rest": ["substrate", "mold_low", "mold_high"]}
    return extrude(fp, np.array([0.0, 1.0, 1.5, 2.5]) * s, mats, size=(layer_size or size) * s)


def unit_cube(h):
    d = Domain(size=h)
    d.add_region("cube", rectangle(0, 0, 1, 1))
    return extrude(generate(d, box_sides(0, 1, 0, 1)), [0.0, 1.0], size=h)


def digest(m):
    h = hashlib.sha256()
    for a in (m.nodes, m.tetrahedra, m.regions):
        h.update(np.ascontiguousarray(a).tobytes())
    for tag in sorted(m.boundary_faces):
        h.update(tag.encode() + np.ascontiguousarray(m.boundary_faces[tag]).tobytes())
    return h.hexdigest()


# -- V1-V4: contract and exact geometry ------------------------------------

def test_chip_stack_satisfies_the_contract_with_exact_volumes():
    m = check(chip())
    assert m.region_names == ["substrate", "die", "mold_low", "mold_high"]
    exact = {"substrate": 100.0, "die": 8.0, "mold_low": 42.0, "mold_high": 100.0}
    for name, v in exact.items():
        assert abs(m.region_volume(name) - v) / v <= 1e-12, name
    # balls have Euler characteristic 1; mold_low is a ring around the die, 0
    assert {n: m.euler_characteristic(n) for n in exact} == {"substrate": 1, "die": 1, "mold_low": 0, "mold_high": 1}
    assert set(m.boundary_faces) == {"z0", "z1", "left", "right", "bottom", "top"}
    assert sorted(m.interfaces) == [("die", "mold_high"), ("die", "mold_low"), ("die", "substrate"),
                                    ("mold_high", "mold_low"), ("mold_low", "substrate")]


def test_planar_boundaries_are_exact():
    m = chip()
    z = m.nodes[:, 2]
    assert set(np.unique(z[m.boundary_nodes["z0"]])) == {0.0}
    assert set(np.unique(z[m.boundary_nodes["z1"]])) == {2.5}
    for tag, axis, value in (("left", 0, -5.0), ("right", 0, 5.0), ("bottom", 1, -5.0), ("top", 1, 5.0)):
        assert set(np.unique(m.nodes[m.boundary_nodes[tag], axis])) == {value}
        f = m.nodes[m.boundary_faces[tag]]
        area = 0.5 * np.linalg.norm(np.cross(f[:, 1] - f[:, 0], f[:, 2] - f[:, 0]), axis=1).sum()
        assert abs(area - 10.0 * 2.5) <= 1e-12 * 25.0
    # interface planes are exact too: the die's top and the substrate's top
    for pair, level in ((("die", "mold_high"), 1.5), (("mold_low", "substrate"), 1.0)):
        assert set(np.unique(z[np.unique(m.interfaces[pair])])) == {level}


def test_layer_boundaries_are_kept_exactly_and_subdivisions_are_affine():
    m = unit_cube(0.3)
    levels = np.unique(m.nodes[:, 2])
    assert levels.tolist() == [0.0, 0.25, 0.5, 0.75, 1.0]
    m = chip(size=1.0, layer_size=0.4)
    assert {1.0, 1.5, 2.5} <= set(np.unique(m.nodes[:, 2]).tolist())


def test_void_cells_are_left_out_and_tagged():
    d = Domain(size=0.4)
    d.add_region("hole", rectangle(-1, -1, 1, 1))
    d.add_region("frame", rectangle(-3, -3, 3, 3), holes=[rectangle(-1, -1, 1, 1)])
    fp = generate(d, box_sides(-3, 3, -3, 3))
    m = check(extrude(fp, [0, 1, 2], {"hole": ["slab", None], "frame": ["slab", "wall"]}))
    assert abs(m.region_volume("slab") - 36.0) < 1e-12 * 36
    assert abs(m.region_volume("wall") - 32.0) < 1e-12 * 32
    f = m.nodes[m.boundary_faces["void"]]
    area = 0.5 * np.linalg.norm(np.cross(f[:, 1] - f[:, 0], f[:, 2] - f[:, 0]), axis=1).sum()
    assert abs(area - (4.0 + 4 * 2.0)) < 1e-12 * 12               # the pit's floor and four walls
    assert m.euler_characteristic("wall") == 0                       # a ring: one hole through it


def test_orientation_is_exact_on_every_tetrahedron():
    from meshine.mesh3d import orient3d_signs
    m = chip()
    assert (orient3d_signs(m.nodes, m.tetrahedra) == 1).all()


def test_bad_inputs_are_refused():
    d = Domain(size=0.5)
    d.add_region("a", rectangle(0, 0, 1, 1))
    fp = generate(d, box_sides(0, 1, 0, 1))
    with pytest.raises(ValueError, match="increasing"):
        extrude(fp, [0.0, 0.0, 1.0])
    with pytest.raises(ValueError, match="nothing to mesh"):
        extrude(fp, [0, 1], {"a": [None]})
    with pytest.raises(ValueError, match="no entry"):
        extrude(fp, [0, 1], {"b": ["x"]})
    with pytest.raises(ValueError, match="clash"):
        extrude(fp, [0, 1], top="top")
    with pytest.raises(ValueError, match="not both"):
        extrude(fp, [0, 1], divisions=2, size=0.1)


# -- V21: P1 Poisson on the extruded unit cube ------------------------------

def _duffy_rule(n=5):
    """Collapsed Gauss-Legendre rule on the unit tetrahedron: barycentric weights and coordinates.

    With n = 5 points per direction it is exact for polynomials of degree 9 in the
    collapsed variables, so for degree 5 or more on the tetrahedron.
    """
    x, w = np.polynomial.legendre.leggauss(n)
    x, w = 0.5 * (x + 1), 0.5 * w
    u, v, s = np.meshgrid(x, x, x, indexing="ij")
    wu, wv, ws = np.meshgrid(w, w, w, indexing="ij")
    a = u
    b = v * (1 - u)
    c = s * (1 - u) * (1 - v)
    weight = (wu * wv * ws * (1 - u) ** 2 * (1 - v)).ravel()
    lam = np.stack([1 - a - b - c, a, b, c], axis=-1).reshape(-1, 4)
    return lam, weight                                                  # sum(weight) = 1/6


def _poisson_errors(m):
    from galerkin import assemble_stiffness_3d, from_mesher, solve_dirichlet
    mesh = from_mesher(m)
    lam, wq = _duffy_rule()
    p = mesh.nodes[mesh.tets]                                           # (T, 4, 3)
    vol6 = np.abs(np.einsum("ij,ij->i", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0])))
    xq = np.einsum("qk,tkd->tqd", lam, p)                               # (T, Q, 3)
    s = np.sin(np.pi * xq)
    u = s.prod(axis=2)
    load = 3 * np.pi ** 2 * u * wq * vol6[:, None]                      # dV = vol6 * dlam
    f = np.zeros(mesh.num_nodes)
    np.add.at(f, mesh.tets, np.einsum("tq,qk->tk", load, lam))
    K = assemble_stiffness_3d(mesh)
    bnd = mesh.boundary_nodes()
    uh = solve_dirichlet(K, f, {tuple(bnd): 0.0})
    # gradients of the P1 basis per tetrahedron
    J = np.stack([p[:, 1] - p[:, 0], p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]], axis=1)
    G = np.linalg.inv(J)                                                # rows: d(lambda_1..3)/dx
    grad_lam = np.concatenate([-G.sum(axis=2, keepdims=True), G], axis=2).transpose(0, 2, 1)
    uh_q = np.einsum("qk,tk->tq", lam, uh[mesh.tets])
    guh = np.einsum("tkd,tk->td", grad_lam, uh[mesh.tets])
    c = np.cos(np.pi * xq)
    gu = np.pi * np.stack([c[..., 0] * s[..., 1] * s[..., 2], s[..., 0] * c[..., 1] * s[..., 2],
                           s[..., 0] * s[..., 1] * c[..., 2]], axis=-1)
    e2 = ((uh_q - u) ** 2 * wq * vol6[:, None]).sum()
    g2 = (((guh[:, None, :] - gu) ** 2).sum(axis=2) * wq * vol6[:, None]).sum()
    return np.sqrt(e2), np.sqrt(g2), (1.0 / len(mesh.tets)) ** (1 / 3)


@pytest.mark.slow
def test_poisson_on_the_extruded_cube_converges():
    """V21 on C2 at the sizes {0.2, 0.1, 0.05}, thresholds unchanged.

    The plan's first CI sizes {0.25, 0.177, 0.125} missed the gate on the extruder
    (L2 slope 1.777, H1 0.881; the first step is not yet asymptotic); that result is
    recorded as failed and the size change is the amendment in validation3d.md.
    """
    lam, wq = _duffy_rule()
    assert abs(wq.sum() - 1 / 6) < 1e-15
    # the rule integrates a degree-5 monomial exactly: int x^2 y^2 z dV over the unit tet = 2!2!1!/8! * 6 / 6
    assert abs((lam[:, 1] ** 2 * lam[:, 2] ** 2 * lam[:, 3] * wq).sum() - float(Fraction(2 * 2 * 1, 40320))) < 1e-17
    results = [_poisson_errors(unit_cube(h)) for h in (0.2, 0.1, 0.05)]
    e_l2, e_h1, h = map(np.array, zip(*results))
    slope_l2 = np.polyfit(np.log(h), np.log(e_l2), 1)[0]
    slope_h1 = np.polyfit(np.log(h), np.log(e_h1), 1)[0]
    assert slope_l2 >= 1.8, (slope_l2, e_l2, h)
    assert slope_h1 >= 0.9, (slope_h1, e_h1, h)


# -- V22: layered conduction, reproduced exactly by P1 ---------------------

def test_layered_conduction_matches_the_one_dimensional_solution():
    from galerkin import assemble_stiffness_3d, from_mesher, solve_dirichlet
    m = chip(size=1.25, layer_size=0.5)
    kappa = {"substrate": 1.0, "die": 0.01, "mold_low": 0.01, "mold_high": 1.0}
    mesh = from_mesher(m)
    k = np.array([kappa[n] for n in m.region_names])[m.regions]
    K = assemble_stiffness_3d(mesh, eps=k)
    T = solve_dirichlet(K, np.zeros(mesh.num_nodes),
                        {tuple(m.boundary_nodes["z0"]): 0.0, tuple(m.boundary_nodes["z1"]): 1.0})
    # series resistances 1/1 + 0.5/0.01 + 1/1 per unit area
    r = np.array([1.0, 50.0, 1.0])
    flux = 1.0 / r.sum()
    z = m.nodes[:, 2]
    exact = np.where(z <= 1.0, flux * z,
                     np.where(z <= 1.5, flux * (1.0 + (z - 1.0) / 0.01), flux * (51.0 + (z - 1.5))))
    assert np.abs(T - exact).max() <= 1e-10


# -- V26, V28: determinism and units ----------------------------------------

def test_the_same_input_gives_bitwise_the_same_mesh():
    first = digest(chip())
    assert digest(chip()) == first
    code = ("import sys; sys.path[:0] = sys.argv[1:]; import test_extrude as t; print(t.digest(t.chip()))")
    here = str(__import__("pathlib").Path(__file__).parent)
    out = subprocess.run([sys.executable, "-c", code, here, *sys.path], capture_output=True, text=True,
                         check=True, encoding="utf-8").stdout.split()[-1]
    assert out == first


@pytest.mark.parametrize("scale", [1e-6, 1e-3, 1e3, 1e6])
def test_units_do_not_change_the_mesh(scale):
    ref = chip()
    m = check(chip(scale=scale))
    assert scale != 1.0
    for name in ref.region_names:
        frac_ref = ref.region_volume(name) / ref.volumes.sum()
        frac = m.region_volume(name) / m.volumes.sum()
        assert abs(frac - frac_ref) <= 1e-9
    assert abs(m.num_tetrahedra - ref.num_tetrahedra) <= 0.1 * ref.num_tetrahedra


# -- V31: MSH round trip of an extruded mesh --------------------------------

def test_extruded_mesh_round_trips_through_gmshio(tmp_path):
    gmshio = pytest.importorskip("gmshio")
    m = chip()
    back = gmshio.to_fem3d(gmshio.read_msh(write_msh(m, tmp_path / "chip.msh")))
    assert back.region_names == m.region_names
    assert np.array_equal(back.nodes, m.nodes)
    assert sorted(zip(map(tuple, back.tetrahedra.tolist()), back.regions.tolist())) == \
        sorted(zip(map(tuple, m.tetrahedra.tolist()), m.regions.tolist()))
    for tag in m.boundary_faces:
        assert {tuple(sorted(f)) for f in back.boundary_faces[tag].tolist()} == \
            {tuple(sorted(f)) for f in m.boundary_faces[tag].tolist()}


# -- V32: Gmsh-free twin of tests/gmshio/test_generate.py::test_box_cavity_volume_and_watertight_boundary

def test_box_cavity_volume_and_watertight_boundary_without_gmsh():
    a, b, d = 1.0, 0.5, 0.75
    dom = Domain(size=0.2)
    dom.add_region("cavity", rectangle(0, 0, a, b))
    fem = extrude(generate(dom, box_sides(0, a, 0, b)), [0.0, d], size=0.2)
    assert fem.region_names == ["cavity"]
    assert (fem.volumes > 0).all()
    assert abs(fem.region_volume("cavity") - a * b * d) < 1e-9
    # faces of tets: boundary faces appear once, interior faces twice
    T = fem.tetrahedra
    f = np.vstack([T[:, [0, 1, 2]], T[:, [0, 1, 3]], T[:, [0, 2, 3]], T[:, [1, 2, 3]]])
    f.sort(axis=1)
    uniq, counts = np.unique(f, axis=0, return_counts=True)
    assert set(counts) == {1, 2}
    single = {tuple(r) for r in uniq[counts == 1]}
    tagged = {tuple(sorted(r)) for faces in fem.boundary_faces.values() for r in faces}
    assert single == tagged
    # boundary nodes really are on the box surface
    p = fem.nodes[np.unique(np.concatenate(list(fem.boundary_nodes.values())))]
    on = (np.abs(p) < 1e-9) | (np.abs(p - [a, b, d]) < 1e-9)
    assert on.any(axis=1).all()
