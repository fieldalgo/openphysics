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
