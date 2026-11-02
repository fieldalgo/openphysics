# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""M3b: the Gmsh reader. A mis-parsed mesh still assembles and still returns
eigenvalues, so the gate that matters is that the physics is unchanged."""

import os
import tempfile

import numpy as np
import pytest
import scipy.sparse.linalg as spla

from galerkin import (read_msh, write_msh, box_mesh, EdgeSpace3D,
                      assemble_curlcurl_3d, assemble_edge_mass_3d)
from galerkin.gmsh import GmshFormatError
from galerkin.mesh import Mesh, layered_rectangle_mesh

# One tetrahedron and its four faces, transcribed by hand from the format
# documentation. Node tags are 10..40 rather than 1..4, so a reader that assumes
# contiguous tags starting at one fails here instead of somewhere subtler.
FIXTURES = {
    "2.2": """$MeshFormat
2.2 0 8
$EndMeshFormat
$PhysicalNames
2
2 1 "wall"
3 2 "volume"
$EndPhysicalNames
$Nodes
4
10 0 0 0
20 1 0 0
30 0 1 0
40 0 0 1
$EndNodes
$Elements
5
1 2 2 1 1 10 20 30
2 2 2 1 1 10 20 40
3 2 2 1 1 10 30 40
4 2 2 1 1 20 30 40
5 4 2 2 1 10 20 30 40
$EndElements
""",
    "4.1": """$MeshFormat
4.1 0 8
$EndMeshFormat
$PhysicalNames
2
2 1 "wall"
3 2 "volume"
$EndPhysicalNames
$Entities
0 0 1 1
1 0 0 0 1 1 1 1 1 0
1 0 0 0 1 1 1 1 2 1 1
$EndEntities
$Nodes
1 4 10 40
3 1 0 4
10
20
30
40
0 0 0
1 0 0
0 1 0
0 0 1
$EndNodes
$Elements
2 5 1 5
2 1 2 4
1 10 20 30
2 10 20 40
3 10 30 40
4 20 30 40
3 1 4 1
5 10 20 30 40
$EndElements
""",
}


def _temp(text):
    fd, path = tempfile.mkstemp(suffix=".msh")
    with os.fdopen(fd, "w") as fh:
        fh.write(text)
    return path


@pytest.mark.parametrize("version", sorted(FIXTURES))
def test_fixture_parses(version):
    path = _temp(FIXTURES[version])
    try:
        mesh = read_msh(path)
    finally:
        os.unlink(path)
    assert mesh.num_nodes == 4 and mesh.num_tets == 1
    assert abs(mesh.volumes().sum() - 1.0 / 6.0) < 1e-14
    assert sorted(mesh.boundary["wall"].tolist()) == [0, 1, 2, 3]


@pytest.mark.parametrize("text,reason", [
    ("$MeshFormat\n2.2 1 8\n$EndMeshFormat\n", "binary"),
    (FIXTURES["2.2"].replace("5 4 2 2 1 10 20 30 40", "5 11 2 2 1 10 20 30 40"),
     "second-order elements"),
])
def test_unsupported_input_is_refused_not_guessed(text, reason):
    path = _temp(text)
    try:
        with pytest.raises(GmshFormatError):
            read_msh(path)
    finally:
        os.unlink(path)


def test_round_trip_preserves_the_physics():
    direct = box_mesh(1.0, 0.8, 0.6, 5, 4, 3)
    path = _temp("")
    try:
        write_msh(direct, path)
        back = read_msh(path)
    finally:
        os.unlink(path)

    assert back.num_nodes == direct.num_nodes and back.num_tets == direct.num_tets
    assert np.allclose(back.nodes, direct.nodes)
    for tag in direct.boundary:
        assert np.array_equal(np.sort(direct.boundary[tag]),
                              np.sort(back.boundary[tag])), f"tag '{tag}' lost"

    def spectrum(mesh):
        space = EdgeSpace3D(mesh)
        S = assemble_curlcurl_3d(space)
        M = assemble_edge_mass_3d(space)
        free = np.setdiff1d(np.arange(space.num_edges), space.boundary_edge_ids())
        v = spla.eigsh(S[free][:, free].tocsc(), k=8, M=M[free][:, free].tocsc(),
                       sigma=45.0, which="LM", v0=np.ones(len(free)),
                       ncv=min(len(free), 80), maxiter=50000,
                       return_eigenvectors=False)
        return np.sort(v[v > 1e-6 * np.abs(v).max()])

    drift = np.abs(spectrum(back)[:4] - spectrum(direct)[:4]).max()
    assert drift < 1e-9, f"connectivity or orientation damaged: drift {drift:.2e}"


# A planar mesh in format 2.2: the unit square cut into two triangles, one in
# the physical surface "a" and one in no physical surface at all, the bottom
# edge in the physical curve "wall", and a fifth node (tag 50) that no triangle
# uses. A reader that keeps the dangling node, or that gives the untagged
# triangle a region of its own, disagrees with gmshio on the same bytes.
PLANAR_22 = """$MeshFormat
2.2 0 8
$EndMeshFormat
$PhysicalNames
2
1 7 "wall"
2 3 "a"
$EndPhysicalNames
$Nodes
5
10 0 0 0
20 1 0 0
30 1 1 0
40 0 1 0
50 5 5 0
$EndNodes
$Elements
3
1 1 2 7 1 10 20
2 2 2 3 1 10 20 30
3 2 2 0 1 10 40 30
$EndElements
"""


def _edge_set(edges):
    return {tuple(sorted(e)) for e in np.asarray(edges).tolist()}


def _assert_same_planar_mesh(ours, theirs):
    """The full contract a planar Mesh carries, array for array: nodes, triangles
    up to orientation (both readers leave them counter-clockwise), regions and
    their names, and the named boundary edges and nodes."""
    assert np.array_equal(ours.nodes, theirs.nodes), "node coordinates or order differ"
    assert np.array_equal(np.sort(ours.triangles, axis=1),
                          np.sort(theirs.triangles, axis=1)), "connectivity differs"
    assert (ours.areas() > 0).all() and (theirs.areas() > 0).all()
    assert ours.region_names == theirs.region_names
    assert np.array_equal(ours.regions, theirs.regions), "regions differ"
    assert set(ours.boundary_edges) == set(theirs.boundary_edges)
    for name in theirs.boundary_edges:
        assert _edge_set(ours.boundary_edges[name]) == _edge_set(theirs.boundary_edges[name]), \
            f"boundary edges of '{name}' differ"
    assert set(ours.boundary) == set(theirs.boundary)
    for name in theirs.boundary:
        assert np.array_equal(np.sort(ours.boundary[name]), np.sort(theirs.boundary[name])), \
            f"boundary nodes of '{name}' differ"


def test_planar_fixture_keeps_regions_and_drops_unused_nodes():
    path = _temp(PLANAR_22)
    try:
        mesh = read_msh(path)
    finally:
        os.unlink(path)
    assert mesh.num_nodes == 4 and mesh.num_triangles == 2, "the unused node must go"
    assert np.allclose(mesh.nodes, [[0, 0], [1, 0], [1, 1], [0, 1]])
    assert abs(mesh.areas().sum() - 1.0) < 1e-15
    assert mesh.region_names == ["a"]
    assert mesh.regions.tolist() == [0, -1], "untagged triangle must be region -1"
    assert _edge_set(mesh.boundary_edges["wall"]) == {(0, 1)}
    assert mesh.boundary["wall"].tolist() == [0, 1]
    assert mesh.by_region({"a": 2.0})[0] == 2.0


def test_planar_round_trip_keeps_regions_and_boundary_edges():
    direct = layered_rectangle_mesh([0.4, 1.0], 0.5, [2, 3], 2,
                                    region_names=["core", "clad"])
    path = _temp("")
    try:
        write_msh(direct, path)
        back = read_msh(path)
    finally:
        os.unlink(path)
    _assert_same_planar_mesh(back, direct)
    assert np.array_equal(back.triangles, direct.triangles)


def test_planar_round_trip_keeps_a_triangle_outside_every_region():
    base = layered_rectangle_mesh([0.5, 1.0], 1.0, 1, 1, region_names=["a", "b"])
    regions = base.regions.copy()
    regions[0] = -1
    direct = Mesh(base.nodes, base.triangles, base.boundary, base.boundary_edges,
                  regions, base.region_names)
    path = _temp("")
    try:
        write_msh(direct, path)
        back = read_msh(path)
    finally:
        os.unlink(path)
    _assert_same_planar_mesh(back, direct)


def test_planar_mesh_without_physical_surfaces_has_no_regions():
    text = PLANAR_22.replace('2 2 2 3 1 10 20 30', '2 2 2 0 1 10 20 30')
    path = _temp(text)
    try:
        mesh = read_msh(path)
    finally:
        os.unlink(path)
    assert mesh.regions is None and mesh.region_names is None
    assert set(mesh.boundary_edges) == {"wall"}


# --------------------------------------------------------------------------
# Until the Gmsh executable was available, this reader was gated only on
# hand-written fixtures and a round trip through galerkin's own writer. Those
# check the format as documented; they cannot check the format as Gmsh actually
# writes it. These do.
# --------------------------------------------------------------------------
gmshio = pytest.importorskip("gmshio")


def _gmsh_or_skip():
    exe = gmshio.find_gmsh()
    if exe is None:
        pytest.skip("the gmsh executable is not installed")
    return exe


@pytest.mark.parametrize("fmt,version", [("msh2", "2.2"), ("msh4", "4.1")])
def test_reads_a_file_gmsh_actually_wrote(fmt, version):
    import subprocess
    from gmshio import geo

    exe = _gmsh_or_skip()
    with tempfile.TemporaryDirectory() as d:
        geo_path = os.path.join(d, "cavity.geo")
        msh_path = os.path.join(d, "cavity.msh")
        with open(geo_path, "w") as fh:
            fh.write(geo.box_cavity(1.0, 0.8, 0.6, lc=0.3))
        proc = subprocess.run([exe, "-3", geo_path, "-o", msh_path,
                               "-format", fmt, "-v", "1"],
                              capture_output=True, text=True, timeout=300)
        assert proc.returncode == 0, proc.stdout + proc.stderr

        with open(msh_path) as fh:
            header = fh.readline(), fh.readline()
        assert header[1].split()[0].startswith(version), (
            f"asked gmsh for {version}, it wrote {header[1].strip()}")

        mesh = read_msh(msh_path)

    assert mesh.num_tets > 0 and mesh.num_nodes > 0
    assert abs(mesh.volumes().sum() - 1.0 * 0.8 * 0.6) < 1e-9, (
        "volume wrong — nodes or connectivity mis-parsed")
    assert (mesh.volumes() > 0).all()
    assert "pec" in mesh.boundary, (
        f"physical group lost; got {sorted(mesh.boundary)}")
    # the tagged surface must be the whole boundary of the box
    assert set(np.unique(mesh.boundary_faces()).tolist()) == \
        set(mesh.boundary["pec"].tolist())


def test_our_reader_agrees_with_gmshio_on_the_same_file():
    """Two independent parsers of the same bytes: galerkin's dependency-free
    reader and gmshio's. They must produce the same mesh."""
    import subprocess
    from gmshio import geo, read_msh as gmshio_read, to_fem3d
    from galerkin import from_mesher

    exe = _gmsh_or_skip()
    with tempfile.TemporaryDirectory() as d:
        geo_path = os.path.join(d, "cavity.geo")
        msh_path = os.path.join(d, "cavity.msh")
        with open(geo_path, "w") as fh:
            fh.write(geo.box_cavity(1.0, 0.8, 0.6, lc=0.35))
        subprocess.run([exe, "-3", geo_path, "-o", msh_path, "-v", "1"],
                       capture_output=True, text=True, timeout=300, check=True)
        ours = read_msh(msh_path)
        theirs = from_mesher(to_fem3d(gmshio_read(msh_path)))

    assert ours.num_nodes == theirs.num_nodes
    assert ours.num_tets == theirs.num_tets
    assert np.allclose(np.sort(ours.nodes, axis=0), np.sort(theirs.nodes, axis=0))
    assert abs(ours.volumes().sum() - theirs.volumes().sum()) < 1e-12
    assert np.array_equal(
        np.unique(np.sort(ours.tets, axis=1), axis=0),
        np.unique(np.sort(theirs.tets, axis=1), axis=0)), \
        "the two readers disagree on connectivity"


def _two_region_rectangle_geo():
    """[0,2]x[0,1] tiled by the regions 'a' (left half) and 'b' (right half),
    boundary curves named left/right/bottom/top."""
    from gmshio import geo
    g = geo.Geo()
    g.default_lc = 0.3
    g.add_region("a", [(0, 0), (1, 0), (1, 1), (0, 1)])
    g.add_region("b", [(1, 0), (2, 0), (2, 1), (1, 1)])
    return g.render(geo.box_sides(0.0, 2.0, 0.0, 1.0))


@pytest.mark.parametrize("fmt", ["msh41", "msh2"])
def test_planar_reader_agrees_with_gmshio_on_a_file_gmsh_wrote(fmt):
    """Same bytes, two independent parsers, one contract: galerkin's reader must
    return exactly what from_mesher(gmshio.to_fem2d(gmshio.read_msh(...)))
    returns — nodes, triangles, regions, region names and named boundaries.
    gmshio reads only 4.1, so the 2.2 file is the same mesh re-saved by Gmsh
    in the old format and is compared against the 4.1 result."""
    import subprocess
    from gmshio import generate, read_msh as gmshio_read, to_fem2d
    from galerkin import from_mesher

    exe = _gmsh_or_skip()
    with tempfile.TemporaryDirectory() as d:
        msh41 = os.path.join(d, "two.msh")
        generate(_two_region_rectangle_geo(), dim=2, out=msh41, verbosity=0)
        theirs = from_mesher(to_fem2d(gmshio_read(msh41)))
        if fmt == "msh41":
            ours = read_msh(msh41)
        else:
            msh2 = os.path.join(d, "two_v2.msh")
            subprocess.run([exe, msh41, "-o", msh2, "-format", "msh2", "-save", "-v", "1"],
                           capture_output=True, text=True, timeout=300, check=True)
            with open(msh2) as fh:
                fh.readline()
                assert fh.readline().split()[0].startswith("2.2")
            ours = read_msh(msh2)

    assert ours.num_triangles > 2
    assert ours.region_names == ["a", "b"]
    assert set(ours.boundary_edges) == {"left", "right", "bottom", "top"}
    assert abs(ours.areas()[ours.regions == 0].sum() - 1.0) < 1e-12
    assert abs(ours.areas()[ours.regions == 1].sum() - 1.0) < 1e-12
    _assert_same_planar_mesh(ours, theirs)
    assert np.array_equal(ours.triangles, theirs.triangles)
