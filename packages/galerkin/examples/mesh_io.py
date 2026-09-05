"""M3b: reading meshes from Gmsh, without linking Gmsh.

Gmsh is GPL, so it is run as a separate executable and only its output file is
read here — parsing a published format creates no derivative work:

    gmsh -3 cavity.geo -o cavity.msh                  # 4.1, the current default
    gmsh -3 cavity.geo -o cavity.msh -format msh2     # 2.2, still widely used

Two gates, because a mesh reader is exactly the kind of code that fails silently:
a mis-parsed connectivity still produces a mesh, still assembles, still returns
eigenvalues, and every number is wrong.

  1. Fixtures transcribed by hand from the format documentation, one per format
     version, with deliberately non-contiguous node tags so the remapping is
     exercised. These check the parsing itself.
  2. A round trip that ends in physics: write a box mesh out, read it back, and
     recompute the cavity spectrum. Connectivity or orientation damage that a
     node-count check would miss moves those eigenvalues.

The Gmsh executable is not available in this development container, so neither
gate uses a file that Gmsh itself produced. That limitation is real and is the
first thing to close when Gmsh is at hand.
"""

import os
import tempfile

import numpy as np

from galerkin import read_msh, write_msh, box_mesh
from cavity_modes import solve_cavity, cavity_matrices, A_BOX, B_BOX, C_BOX

# One tetrahedron and its four faces. Node tags are 10, 20, 30, 40 rather than
# 1..4 so that a reader which assumes contiguous tags starting at one fails here.
FIXTURE_22 = """$MeshFormat
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
"""

# The same tetrahedron in format 4.1, where the physical group of an element is
# reached indirectly, through the entity the element belongs to.
FIXTURE_41 = """$MeshFormat
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
"""


def _write_temp(text, suffix=".msh"):
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w") as fh:
        fh.write(text)
    return path


def check_fixtures():
    print("hand-written fixtures (transcribed from the format documentation):")
    for version, text in (("2.2", FIXTURE_22), ("4.1", FIXTURE_41)):
        path = _write_temp(text)
        try:
            mesh = read_msh(path)
        finally:
            os.unlink(path)
        vol = mesh.volumes().sum()
        wall = sorted(mesh.boundary["wall"].tolist())
        print(f"  msh {version}: {mesh.num_nodes} nodes, {mesh.num_tets} tet, "
              f"volume {vol:.10f}, boundary 'wall' = {wall}")
        assert mesh.num_nodes == 4 and mesh.num_tets == 1
        assert abs(vol - 1.0 / 6.0) < 1e-14, "unit tetrahedron volume wrong"
        assert wall == [0, 1, 2, 3], "physical group did not survive the read"
        assert np.allclose(np.sort(mesh.nodes, axis=0),
                           np.sort(np.array([[0., 0, 0], [1, 0, 0], [0, 1, 0],
                                             [0, 0, 1]]), axis=0)), "coordinates wrong"


def check_round_trip(n=(5, 4, 3)):
    """Write a mesh out, read it back, and check the physics is unchanged."""
    direct = box_mesh(A_BOX, B_BOX, C_BOX, *n)
    path = _write_temp("")
    try:
        write_msh(direct, path)
        back = read_msh(path)
        size = os.path.getsize(path)
    finally:
        os.unlink(path)

    print(f"\nround trip through a {size/1024:.0f} kB .msh file:")
    print(f"  nodes {direct.num_nodes} -> {back.num_nodes}, "
          f"tets {direct.num_tets} -> {back.num_tets}, "
          f"volume {direct.volumes().sum():.12f} -> {back.volumes().sum():.12f}")
    assert back.num_nodes == direct.num_nodes and back.num_tets == direct.num_tets
    assert np.allclose(back.nodes, direct.nodes), "coordinates changed"
    assert abs(back.volumes().sum() - direct.volumes().sum()) < 1e-12

    tags = sorted(set(direct.boundary) & set(back.boundary))
    for tag in tags:
        a, b = np.sort(direct.boundary[tag]), np.sort(back.boundary[tag])
        assert np.array_equal(a, b), f"boundary tag '{tag}' did not survive"
    print(f"  boundary tags preserved: {tags}")

    # the gate that actually matters: the same spectrum out of the read-back mesh
    _, _, _, vals_direct, _ = solve_cavity(*n)
    _, _, _, S, M, _ = cavity_matrices(*n)
    import scipy.sparse.linalg as spla
    from galerkin import EdgeSpace3D, assemble_curlcurl_3d, assemble_edge_mass_3d
    space = EdgeSpace3D(back)
    Sb = assemble_curlcurl_3d(space)
    Mb = assemble_edge_mass_3d(space)
    free = np.setdiff1d(np.arange(space.num_edges), space.boundary_edge_ids())
    vb = spla.eigsh(Sb[free][:, free].tocsc(), k=8, M=Mb[free][:, free].tocsc(),
                    sigma=45.0, which="LM", v0=np.ones(len(free)),
                    ncv=min(len(free), 80), maxiter=50000,
                    return_eigenvectors=False)
    vb = np.sort(vb[vb > 1e-6 * np.abs(vb).max()])
    drift = np.abs(vb[:4] - vals_direct[:4]).max()
    print(f"  cavity spectrum from the read-back mesh: "
          + "  ".join(f"{v:.6f}" for v in vb[:4]))
    print(f"  largest drift from the directly built mesh: {drift:.2e}")
    assert drift < 1e-9, "connectivity or orientation damaged by the round trip"


def check_rejections():
    """A reader must refuse what it cannot honour, rather than guess."""
    print("\nrefusals:")
    for name, text in (
            ("binary file", "$MeshFormat\n2.2 1 8\n$EndMeshFormat\n"),
            ("second-order tetrahedra",
             FIXTURE_22.replace("5 4 2 2 1 10 20 30 40", "5 11 2 2 1 10 20 30 40")),
            ("no mesh at all", "$MeshFormat\n2.2 0 8\n$EndMeshFormat\n"
                               "$Nodes\n1\n1 0 0 0\n$EndNodes\n"
                               "$Elements\n0\n$EndElements\n")):
        path = _write_temp(text)
        try:
            read_msh(path)
        except Exception as exc:
            print(f"  {name}: refused with {type(exc).__name__} — "
                  f"{str(exc).split(':')[-1].strip()}")
        else:
            raise AssertionError(f"{name} should have been refused")
        finally:
            os.unlink(path)


def main():
    check_fixtures()
    check_round_trip()
    check_rejections()
    print("\nPASS: both .msh formats parse, tags and connectivity survive a round "
          "trip, and the cavity spectrum is unchanged to 1e-9")


if __name__ == "__main__":
    main()
