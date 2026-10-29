# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The tetrahedral mesh contract (V1, V2 and V31 of the pre-registered 3D plan),
checked on structured Kuhn meshes whose volumes, faces and tags are known exactly,
and on meshes broken on purpose.
"""

import itertools
import random
from fractions import Fraction

import numpy as np
import pytest

from meshine import MeshCheckError, TetMesh, check, write_msh
from meshine.mesh3d import interface_faces, orient3d_signs, validate


def kuhn_box(n=(3, 3, 3), layers=None, scale=1.0):
    """Unit box split into n cells per axis, each cell into the 6 Kuhn tetrahedra.

    ``layers`` maps a region name to its z range in cells; faces on the six box
    sides are tagged x0, x1, y0, y1, z0, z1 and interfaces are derived.
    """
    nx, ny, nz = n
    layers = layers or {"box": (0, nz)}
    idx = np.arange((nx + 1) * (ny + 1) * (nz + 1)).reshape(nx + 1, ny + 1, nz + 1)
    g = np.stack(np.meshgrid(np.arange(nx + 1) / nx, np.arange(ny + 1) / ny, np.arange(nz + 1) / nz,
                             indexing="ij"), axis=-1).reshape(-1, 3)
    tets, regs = [], []
    names = list(layers)
    for i, j, k in itertools.product(range(nx), range(ny), range(nz)):
        region = next(r for r, (z0, z1) in enumerate(layers.values()) if z0 <= k < z1)
        for perm in itertools.permutations(range(3)):
            v = [0, 0, 0]
            path = [idx[i, j, k]]
            for axis in perm:
                v[axis] += 1
                path.append(idx[i + v[0], j + v[1], k + v[2]])
            tets.append(path)
            regs.append(region)
    tets = np.array(tets, dtype=np.int64)
    p = g[tets]
    vol = np.einsum("ij,ij->i", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]))
    tets[vol < 0] = tets[vol < 0][:, [0, 1, 3, 2]]
    g = g * scale                                            # orient at unit scale, where volumes do not underflow
    mesh = TetMesh(g, tets, np.array(regs, dtype=np.int64), names, {})
    faces = mesh.boundary_face_set()
    c = g[faces].mean(axis=1) / scale
    sides = {}
    for axis, letter in enumerate("xyz"):
        sides[f"{letter}0"] = faces[np.isclose(c[:, axis], 0.0)]
        sides[f"{letter}1"] = faces[np.isclose(c[:, axis], 1.0)]
    return TetMesh(g, tets, mesh.regions, names, sides, interfaces=interface_faces(mesh))


def stack():
    return kuhn_box((4, 4, 6), {"substrate": (0, 2), "die": (2, 3), "mold": (3, 6)})


def canonical(faces):
    out = set()
    for f in np.asarray(faces).tolist():
        r = f.index(min(f))
        out.add(tuple(f[r:] + f[:r]))
    return out


# -- the contract holds on exact structured meshes -------------------------

@pytest.mark.parametrize("make", [kuhn_box, stack])
def test_structured_meshes_satisfy_the_contract(make):
    m = make()
    assert validate(m) == []
    assert check(m) is m
    assert abs(m.volumes.sum() - 1.0) < 1e-12
    assert (orient3d_signs(m.nodes, m.tetrahedra) == 1).all()
    for name in m.region_names:
        assert m.euler_characteristic(name) == 1
    assert m.euler_characteristic() == 1


def test_stack_regions_and_interfaces_are_exact():
    m = stack()
    assert m.region_names == ["substrate", "die", "mold"]
    assert abs(m.region_volume("substrate") - 2 / 6) < 1e-12
    assert abs(m.region_volume("die") - 1 / 6) < 1e-12
    assert abs(m.region_volume("mold") - 3 / 6) < 1e-12
    assert sorted(m.interfaces) == [("die", "mold"), ("die", "substrate")]
    for faces in m.interfaces.values():
        assert len(faces) == 4 * 4 * 2                       # two triangles per cell face of a 4x4 plane
    for tag, faces in m.boundary_faces.items():
        assert np.array_equal(m.boundary_nodes[tag], np.unique(faces))


def test_regular_tetrahedron_metrics():
    p = np.array([[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]], dtype=float)
    m = TetMesh(p, np.array([[0, 1, 2, 3]]), np.array([0]), ["t"], {})
    if m.volumes[0] < 0:
        m.tetrahedra = np.array([[0, 1, 3, 2]])
    assert m.quality()[0] == pytest.approx(1.0, abs=1e-14)
    assert np.allclose(m.dihedral_angles(), np.degrees(np.arccos(1 / 3)), atol=1e-12)
    assert m.radius_edge()[0] == pytest.approx(np.sqrt(6) / 4, abs=1e-14)


def test_exact_orientation_agrees_with_fractions_on_near_degenerate_input():
    rng = random.Random(20261029)
    pts, tets, want = [], [], []
    for _ in range(3000):
        dyadic = rng.random() < 0.3                            # exactly coplanar when not jittered
        draw = (lambda: rng.randint(-64, 64) / 64) if dyadic else (lambda: rng.uniform(-1, 1))
        a, b, c = ([draw() for _ in range(3)] for _ in range(3))
        s, t = (rng.randint(-8, 16) / 8, rng.randint(-8, 16) / 8) if dyadic else (rng.uniform(-1, 2), rng.uniform(-1, 2))
        d = [a[i] + s * (b[i] - a[i]) + t * (c[i] - a[i]) for i in range(3)]   # on the plane up to rounding
        if rng.random() < 0.3:
            d = [x + rng.choice([-1, 1]) * 2.0 ** -50 for x in d]
        base = len(pts)
        pts += [a, b, c, d]
        tets.append([base, base + 1, base + 2, base + 3])
        q = [[Fraction(x) for x in v] for v in (a, b, c, d)]
        u = [[q[k][j] - q[0][j] for j in range(3)] for k in (1, 2, 3)]
        det = (u[0][0] * (u[1][1] * u[2][2] - u[1][2] * u[2][1])
               - u[0][1] * (u[1][0] * u[2][2] - u[1][2] * u[2][0])
               + u[0][2] * (u[1][0] * u[2][1] - u[1][1] * u[2][0]))
        want.append((det > 0) - (det < 0))
    got = orient3d_signs(np.array(pts), np.array(tets))
    assert got.tolist() == want
    assert 0 in want and 1 in want and -1 in want


def test_exactly_coplanar_and_tiny_tetrahedra():
    flat = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0.25, 0.5, 0.0]])
    assert orient3d_signs(flat, np.array([[0, 1, 2, 3]])).tolist() == [0]
    m = kuhn_box((2, 2, 2), scale=2.0 ** -1000)              # products underflow; exact path decides
    assert validate(m) == []


# -- broken meshes are refused, every problem listed ----------------------

def broken(edit):
    m = stack()
    edit(m)
    with pytest.raises(MeshCheckError) as err:
        check(m)
    return " ".join(err.value.problems)


def test_flipped_tetrahedron_is_refused():
    def flip(m):
        m.tetrahedra = m.tetrahedra.copy()
        m.tetrahedra[7] = m.tetrahedra[7][[0, 1, 3, 2]]
    assert "not positively oriented" in broken(flip)


def test_untagged_and_inward_faces_are_refused():
    def drop(m):
        m.boundary_faces["z0"] = m.boundary_faces["z0"][1:]
        m.boundary_nodes = {k: np.unique(v) for k, v in m.boundary_faces.items()}
    assert "carry no tag" in broken(drop)

    def inward(m):
        f = m.boundary_faces["x1"].copy()
        f[0] = f[0][[0, 2, 1]]
        m.boundary_faces["x1"] = f
    text = broken(inward)
    assert "carry no tag" in text and "not outward-wound" in text


def test_double_tag_orphan_and_empty_region_are_refused():
    def double(m):
        m.boundary_faces["extra"] = m.boundary_faces["y0"][:2]
        m.boundary_nodes["extra"] = np.unique(m.boundary_faces["extra"])
    assert "tagged twice" in broken(double)

    def orphan(m):
        m.nodes = np.vstack([m.nodes, [[5.0, 5.0, 5.0]]])
    assert "orphan" in broken(orphan)

    def empty(m):
        m.region_names = m.region_names + ["air"]
    assert "without tetrahedra" in broken(empty)


def test_wrong_interface_winding_and_stale_node_sets_are_refused():
    def wind(m):
        f = m.interfaces[("die", "mold")].copy()
        m.interfaces[("die", "mold")] = f[:, [0, 2, 1]]
    assert "interfaces differ" in broken(wind)

    def stale(m):
        m.boundary_nodes["z1"] = m.boundary_nodes["z1"][:-1]
    assert "boundary_nodes['z1']" in broken(stale)


# -- V31: MSH 4.1 round trip through gmshio, no Gmsh binary needed ---------

@pytest.mark.parametrize("make", [kuhn_box, stack])
def test_write_msh_round_trips_through_gmshio(make, tmp_path):
    gmshio = pytest.importorskip("gmshio")
    m = make()
    back = gmshio.to_fem3d(gmshio.read_msh(write_msh(m, tmp_path / "m.msh")))
    assert back.region_names == m.region_names
    assert np.array_equal(back.nodes, m.nodes)                # repr round-trips every float64
    # MSH groups elements by region, so compare (tetrahedron, region) pairs; vertex order is kept
    assert sorted(zip(map(tuple, back.tetrahedra.tolist()), back.regions.tolist())) == \
        sorted(zip(map(tuple, m.tetrahedra.tolist()), m.regions.tolist()))
    assert list(back.boundary_faces) == list(m.boundary_faces)
    for tag in m.boundary_faces:
        assert canonical(back.boundary_faces[tag]) == canonical(m.boundary_faces[tag])
        assert np.array_equal(back.boundary_nodes[tag], m.boundary_nodes[tag])


def test_interfaces_are_written_only_on_request(tmp_path):
    gmshio = pytest.importorskip("gmshio")
    m = stack()
    plain = gmshio.to_fem3d(gmshio.read_msh(write_msh(m, tmp_path / "a.msh")))
    assert set(plain.boundary_faces) == set(m.boundary_faces)
    full = gmshio.to_fem3d(gmshio.read_msh(write_msh(m, tmp_path / "b.msh", interfaces=True)))
    assert canonical(full.boundary_faces["die|mold"]) == canonical(m.interfaces[("die", "mold")])


def test_galerkin_reads_the_mesh():
    galerkin = pytest.importorskip("galerkin")
    m = stack()
    g = galerkin.from_mesher(m)
    assert len(g.tets if hasattr(g, "tets") else g.tetrahedra) == m.num_tetrahedra
