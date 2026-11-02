# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Tagged boundary faces and region checks of Mesh3D (docs/packages/galerkin/mesh3d_format.md).

The refusals are the M5 gates of the 3D opening: regions < 0, an untagged
exterior face, a doubly tagged face and an inward-wound face each raise with a
message naming the problem.
"""
import numpy as np
import pytest

from galerkin import Mesh3D, box_mesh, from_mesher
from galerkin.mesh3d import OUTWARD_FACES, MeshCheckError, tag_faces_by_node_sets
from galerkin._cavity_common import cavity_mesh


def test_box_mesh_tags_outward_faces_that_pass_the_check():
    mesh = box_mesh(1.0, 0.8, 0.6, 3, 2, 4).check()
    assert set(mesh.tagged_faces) == {"x0", "x1", "y0", "y1", "z0", "z1"}
    assert {k: len(v) for k, v in mesh.tagged_faces.items()} == {
        "x0": 2 * 2 * 4, "x1": 2 * 2 * 4, "y0": 2 * 3 * 4, "y1": 2 * 3 * 4,
        "z0": 2 * 3 * 2, "z1": 2 * 3 * 2}
    for tag, axis, value in (("x0", 0, 0.0), ("x1", 0, 1.0), ("y1", 1, 0.8), ("z0", 2, 0.0)):
        faces = mesh.tagged_faces[tag]
        assert np.allclose(mesh.nodes[faces][:, :, axis], value)
        p = mesh.nodes[faces]
        normal = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
        outward = np.zeros(3)
        outward[axis] = -1.0 if value == 0.0 else 1.0
        assert (normal @ outward > 0).all(), tag
        assert np.array_equal(mesh.boundary[tag], np.unique(faces))
    # node sets and faces are the same boundary
    assert np.array_equal(np.unique(np.concatenate(list(mesh.tagged_faces.values()))),
                          mesh.boundary_nodes())


def test_alternating_cavity_mesh_retags_the_moved_diagonals():
    mesh = cavity_mesh((1.0, 0.7, 0.5), (3, 3, 2)).check()
    assert sum(len(v) for v in mesh.tagged_faces.values()) == len(mesh.boundary_faces())


def test_regions_below_zero_are_refused_with_the_count():
    base = box_mesh(1.0, 1.0, 1.0, 1, 1, 1)
    regions = np.zeros(base.num_tets, dtype=int)
    regions[:2] = -1
    with pytest.raises(ValueError, match="2 tetrahedra carry a negative region id"):
        Mesh3D(base.nodes, base.tets, base.boundary, regions=regions, region_names=["domain"])
    with pytest.raises(ValueError, match="2 of 6 cells carry region id -1"):
        from_mesher({"nodes": base.nodes, "tetrahedra": base.tets, "regions": regions,
                     "region_names": ["domain"], "boundary_faces": base.tagged_faces})
    with pytest.raises(ValueError, match=r"\[0, 1\)"):
        Mesh3D(base.nodes, base.tets, base.boundary, regions=regions + 2, region_names=["domain"])


def test_by_region_refuses_negative_ids_instead_of_picking_the_last_region():
    base = box_mesh(1.0, 1.0, 1.0, 1, 1, 1)
    mesh = Mesh3D(base.nodes, base.tets, base.boundary, regions=np.zeros(6, dtype=int))
    mesh.regions[0] = -1       # bypass the constructor, as an in-place edit would
    with pytest.raises(ValueError, match="negative"):
        mesh.by_region([1.0, 2.0])
    mesh.regions[0] = 0
    assert mesh.by_region([7.0]).tolist() == [7.0] * 6


def _tagged(mesh, faces):
    return Mesh3D(mesh.nodes, mesh.tets, regions=mesh.regions, region_names=mesh.region_names,
                  tagged_faces=faces)


def test_untagged_doubly_tagged_and_inward_faces_are_refused():
    mesh = box_mesh(1.0, 1.0, 1.0, 2, 2, 2)
    faces = dict(mesh.tagged_faces)

    missing = dict(faces)
    missing["z1"] = missing["z1"][1:]
    with pytest.raises(MeshCheckError, match="1 exterior faces carry no tag"):
        _tagged(mesh, missing).check()

    doubled = dict(faces)
    doubled["lid"] = faces["z1"][:2]
    with pytest.raises(MeshCheckError, match="2 exterior faces are tagged more than once"):
        _tagged(mesh, doubled).check()

    inward = dict(faces)
    inward["x0"] = inward["x0"][:, [0, 2, 1]]
    with pytest.raises(MeshCheckError, match="8 tagged faces are wound inward"):
        _tagged(mesh, inward).check()

    interior = dict(faces)
    uniq, count = mesh.faces()
    interior["x0"] = np.concatenate([interior["x0"], uniq[count == 2][:1]])
    with pytest.raises(MeshCheckError, match="1 tagged faces are not exterior faces"):
        _tagged(mesh, interior).check()

    # several problems are reported together, in the order found
    problems = _tagged(mesh, {**missing, "x0": inward["x0"]}).validate()
    assert len(problems) == 2 and "no tag" in problems[0] and "inward" in problems[1]


def test_node_sets_disagreeing_with_faces_are_refused():
    mesh = box_mesh(1.0, 1.0, 1.0, 2, 2, 2)
    bad = dict(mesh.boundary)
    bad["x0"] = bad["x0"][1:]
    with pytest.raises(MeshCheckError, match=r"boundary\['x0'\] is not the node set"):
        Mesh3D(mesh.nodes, mesh.tets, bad, tagged_faces=mesh.tagged_faces).check()
    with pytest.raises(MeshCheckError, match="different tags"):
        Mesh3D(mesh.nodes, mesh.tets, {**mesh.boundary, "extra": np.array([0])},
               tagged_faces=mesh.tagged_faces).check()


def test_from_mesher_keeps_faces_regions_and_interfaces_and_checks_them():
    meshine = pytest.importorskip("meshine")
    d = meshine.Domain(size=0.3)
    d.add_region("cavity", meshine.rectangle(0, 0, 1.0, 0.8))
    tet = meshine.extrude(meshine.generate(d, meshine.box_sides(0, 1.0, 0, 0.8)),
                          [0.0, 0.3, 0.6], {"cavity": ["slab", "air"]}, size=0.3)
    mesh = from_mesher(tet)
    assert set(mesh.tagged_faces) == {"z0", "z1", "left", "right", "bottom", "top"}
    assert mesh.region_names == ["slab", "air"]
    assert list(mesh.interfaces) == [("air", "slab")]
    for tag, arr in tet.boundary_faces.items():
        assert np.array_equal(mesh.tagged_faces[tag], arr)
        assert np.array_equal(mesh.boundary[tag], np.unique(arr))
    assert mesh.validate() == []
    assert from_mesher(mesh) is mesh

    broken = {"nodes": tet.nodes, "tetrahedra": tet.tetrahedra, "regions": tet.regions,
              "region_names": tet.region_names,
              "boundary_faces": {k: (v[:, [0, 2, 1]] if k == "z0" else v)
                                 for k, v in tet.boundary_faces.items()}}
    with pytest.raises(MeshCheckError, match="wound inward"):
        from_mesher(broken)


def test_outward_faces_match_the_positively_oriented_tetrahedra():
    mesh = box_mesh(1.0, 1.0, 1.0, 2, 1, 1)
    p = mesh.nodes[mesh.tets]
    for i in range(4):
        f = p[:, OUTWARD_FACES[i]]
        normal = np.cross(f[:, 1] - f[:, 0], f[:, 2] - f[:, 0])
        assert (np.einsum("td,td->t", normal, p[:, i] - f[:, 0]) < 0).all()
    retagged = tag_faces_by_node_sets(mesh, mesh.boundary)
    assert all(np.array_equal(retagged[k], mesh.tagged_faces[k]) for k in retagged)
    with pytest.raises(ValueError, match="lie in no node set"):
        tag_faces_by_node_sets(mesh, {k: v for k, v in mesh.boundary.items() if k != "z1"})


def test_read_msh_keeps_regions_and_tagged_faces(tmp_path):
    meshine = pytest.importorskip("meshine")
    from galerkin import read_msh
    d = meshine.Domain(size=0.4)
    d.add_region("cavity", meshine.rectangle(0, 0, 1.0, 1.0))
    tet = meshine.extrude(meshine.generate(d, meshine.box_sides(0, 1.0, 0, 1.0)),
                          [0.0, 0.5, 1.0], {"cavity": ["a", "b"]})
    path = meshine.write_msh(tet, tmp_path / "two.msh")
    mesh = read_msh(path)
    assert mesh.region_names == ["a", "b"]
    assert np.array_equal(np.sort(mesh.tets, axis=1)[np.lexsort(np.sort(mesh.tets, axis=1).T[::-1])],
                          np.sort(tet.tetrahedra, axis=1)[np.lexsort(np.sort(tet.tetrahedra, axis=1).T[::-1])])
    assert set(mesh.tagged_faces) == set(tet.boundary_faces)
    assert mesh.validate() == []
