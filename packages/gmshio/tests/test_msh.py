# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import numpy as np
import pytest

from gmshio import MshFormatError, read_msh, to_fem2d

DATA = Path(__file__).parent / "data"


def test_read_unit_square_fixture():
    m = read_msh(DATA / "unit_square.msh")
    assert m.num_points == 30
    assert m.cell_types() == ["vertex", "line", "triangle"] or set(m.cell_types()) >= {"line", "triangle"}
    assert len(m.cells("triangle")) == 42
    assert len(m.cells("line")) == 16
    assert m.physical_names == {(1, 20): "pec", (2, 10): "domain"}
    assert m.physical_tag("pec") == 20
    assert m.physical_tag("domain", dim=2) == 10
    assert (m.physical_tags("triangle") == 10).all()
    assert (m.physical_tags("line") == 20).all()
    assert len(m.cells_in("pec", "line")) == 16
    # every node index is valid and every node used
    assert m.cells("triangle").max() == m.num_points - 1
    assert m.cells("triangle").min() == 0


def test_to_fem2d_unit_square():
    f = to_fem2d(read_msh(DATA / "unit_square.msh"))
    assert f.region_names == ["domain"]
    assert (f.regions == 0).all()
    assert (f.areas > 0).all()                       # counter-clockwise
    assert abs(f.areas.sum() - 1.0) < 1e-12          # polygonal domain: exact area
    assert f.boundary_edges["pec"].shape == (16, 2)
    # boundary nodes lie on the square's perimeter
    bn = f.nodes[f.boundary_nodes["pec"]]
    on_edge = (np.abs(bn) < 1e-12) | (np.abs(bn - 1) < 1e-12)
    assert on_edge.any(axis=1).all()
    assert len(f.boundary_nodes["pec"]) == 16


def test_rejects_other_versions(tmp_path):
    bad = tmp_path / "v2.msh"
    bad.write_text("$MeshFormat\n2.2 0 8\n$EndMeshFormat\n")
    with pytest.raises(MshFormatError):
        read_msh(bad)
    binary = tmp_path / "bin.msh"
    binary.write_text("$MeshFormat\n4.1 1 8\n$EndMeshFormat\n")
    with pytest.raises(MshFormatError):
        read_msh(binary)
    with pytest.raises(MshFormatError):
        read_msh(DATA / "unit_square.geo")


def test_unknown_physical_name():
    m = read_msh(DATA / "unit_square.msh")
    with pytest.raises(KeyError):
        m.physical_tag("nope")
