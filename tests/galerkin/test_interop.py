# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""One adapter, several meshers.

`meshine` (pure numpy/scipy, planar) and `gmshio` (drives the Gmsh executable as
a separate process, planar and volumetric) hand back the same five things:
nodes, cells, regions, region_names, and boundary edges or faces. galerkin reads
those attributes and imports neither package — the engine's dependency test
would fail if it did.
"""

import numpy as np
import pytest

from galerkin import from_mesher

meshine = pytest.importorskip("meshine")
gmshio = pytest.importorskip("gmshio")


def _has_gmsh():
    return gmshio.find_gmsh() is not None


needs_gmsh = pytest.mark.skipif(not _has_gmsh(),
                                reason="the gmsh executable is not installed")


def test_planar_mesh_from_meshine():
    from meshine import shapes, generate
    domain, namer = shapes.rib_waveguide(slab_thickness=0.3, size_core=0.4,
                                         size_far=2.0)
    source = generate(domain, namer, min_angle=28)
    mesh = from_mesher(source)

    assert mesh.nodes.shape == (source.nodes.shape[0], 2)
    assert np.array_equal(np.sort(mesh.triangles, axis=1),
                          np.sort(np.asarray(source.triangles), axis=1))
    assert mesh.region_names == list(source.region_names)
    assert np.array_equal(mesh.regions, np.asarray(source.regions))
    assert set(mesh.boundary) == set(source.boundary_edges)
    assert (mesh.areas() > 0).all()

    eps = mesh.by_region({"core": 3.44 ** 2, "box": 3.40 ** 2, "clad": 1.0})
    assert len(eps) == mesh.num_triangles
    assert set(np.round(np.unique(eps), 6)) == {
        round(3.44 ** 2, 6), round(3.40 ** 2, 6), 1.0}


@needs_gmsh
def test_planar_mesh_from_gmshio():
    from gmshio import geo, generate, to_fem2d
    fem = to_fem2d(generate(geo.rib_waveguide(slab_thickness=0.3, lc_core=0.5),
                            dim=2))
    mesh = from_mesher(fem)
    assert mesh.nodes.shape[1] == 2 and mesh.num_triangles == len(fem.triangles)
    assert mesh.region_names == list(fem.region_names)
    assert set(mesh.boundary) == set(fem.boundary_edges)
    assert (mesh.areas() > 0).all()


@needs_gmsh
def test_volume_mesh_from_gmshio():
    from gmshio import geo, generate, to_fem3d
    fem = to_fem3d(generate(geo.box_cavity(1.0, 0.8, 0.6, lc=0.25), dim=3))
    mesh = from_mesher(fem)
    assert mesh.nodes.shape[1] == 3
    assert mesh.num_tets == len(fem.tetrahedra)
    assert abs(mesh.volumes().sum() - 1.0 * 0.8 * 0.6) < 1e-9
    assert (mesh.volumes() > 0).all(), "the adapter must leave orientations valid"
    assert set(mesh.boundary) == set(fem.boundary_faces)

    # boundary faces really are the surface: every one belongs to a single tet
    _, count = mesh.faces()
    assert len(mesh.boundary_faces()) == int((count == 1).sum())


def test_volume_mesh_from_meshine():
    """Gmsh-free twin of the gmshio volume test: a box extruded by meshine."""
    from meshine import Domain, box_sides, extrude, generate, rectangle
    d = Domain(size=0.25)
    d.add_region("cavity", rectangle(0, 0, 1.0, 0.8))
    fem = extrude(generate(d, box_sides(0, 1.0, 0, 0.8)), [0.0, 0.6], size=0.25)
    mesh = from_mesher(fem)
    assert mesh.nodes.shape[1] == 3
    assert mesh.num_tets == len(fem.tetrahedra)
    assert abs(mesh.volumes().sum() - 1.0 * 0.8 * 0.6) < 1e-9
    assert (mesh.volumes() > 0).all(), "the adapter must leave orientations valid"
    assert set(mesh.boundary) == set(fem.boundary_faces)

    # boundary faces really are the surface: every one belongs to a single tet
    _, count = mesh.faces()
    assert len(mesh.boundary_faces()) == int((count == 1).sum())


def test_adapter_accepts_a_plain_dict_of_arrays():
    """Nothing about the adapter should depend on a particular class."""
    nodes = np.array([[0., 0], [1, 0], [0, 1], [1, 1]])
    mesh = from_mesher({
        "nodes": nodes,
        "triangles": np.array([[0, 1, 3], [0, 3, 2]]),
        "regions": np.array([0, 1]),
        "region_names": ["a", "b"],
        "boundary_edges": {"edge": np.array([[0, 1]])},
    })
    assert mesh.num_triangles == 2
    assert list(mesh.by_region({"a": 7.0, "b": 9.0})) == [7.0, 9.0]
    assert list(mesh.boundary["edge"]) == [0, 1]


def test_adapter_refuses_what_it_cannot_read():
    with pytest.raises(TypeError):
        from_mesher({"nodes": np.zeros((3, 2))})            # no cells
    with pytest.raises(ValueError):
        from_mesher({"nodes": np.zeros((4, 2)),
                     "triangles": np.array([[0, 1, 2]]),
                     "regions": np.array([0, 1])})           # length mismatch
    with pytest.raises(ValueError):
        from_mesher({"nodes": np.zeros((4, 2)),
                     "triangles": np.array([[0, 1, 2]]),
                     "regions": np.array([3]),
                     "region_names": ["only-one"]})          # index out of range
