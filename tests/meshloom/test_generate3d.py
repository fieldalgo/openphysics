# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""``meshloom.generate3d`` through ``galerkin.from_mesher``: V2's interop clause and V22.

Rows of docs/packages/meshine/validation3d.md:

- V2 (part): ``from_mesher`` accepts the mesh, with the facet tags as boundary names and
  the region names.
- V22: C3 with the mold split at the die's top (substrate, die, lower and upper mold),
  conductivities 1, 0.01, 0.01 and 1, T = 0 at the bottom and T = 1 at the top: P1
  reproduces the piecewise linear solution in z to 1e-10 at every node.
"""

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)
galerkin = pytest.importorskip("galerkin")

try:  # the box assembly of the refinement tests; the installed-wheel check renames it
    from test_refine import grid_plc  # noqa: E402
except ImportError:
    from test_meshloom_refine import grid_plc  # noqa: E402

LAYERS = {"substrate": 1.0, "die": 0.01, "mold_low": 0.01, "mold_high": 1.0}
SEEDS = [((5.0, 5.0, 0.5), "substrate"), ((5.0, 5.0, 1.25), "die"), ((1.0, 1.0, 1.25), "mold_low"),
         ((5.0, 5.0, 2.0), "mold_high")]


def layered_chip():
    g = [0.0, 3.0, 7.0, 10.0]
    cells = {(i, j, 0): "substrate" for i in range(3) for j in range(3)}
    cells.update({(i, j, 1): "mold_low" for i in range(3) for j in range(3)})
    cells.update({(i, j, 2): "mold_high" for i in range(3) for j in range(3)})
    cells[(1, 1, 1)] = "die"
    pts, facets = grid_plc(g, g, [0.0, 1.0, 1.5, 2.5], cells)
    tags = []
    for f in facets:
        z = pts[f[0], 2]
        tags.append("z0" if np.all(z == 0.0) else "z1" if np.all(z == 2.5) else f"facet{len(tags)}")
    return pts, facets, tags


@pytest.mark.parametrize("h", [0.8, 0.4])
def test_v22_layered_conduction_is_exact(h):
    from galerkin import from_mesher
    from galerkin.kernels import assemble_stiffness_3d, solve_dirichlet
    pts, facets, tags = layered_chip()
    m = meshloom.generate3d(pts, facets, h=h, region_points=SEEDS, facet_tags=tags)
    mesh = from_mesher(m)
    assert type(mesh).__name__ == "Mesh3D"
    assert m["region_names"] == list(LAYERS)
    k = np.array([LAYERS[n] for n in m["region_names"]])[m["regions"]]
    K = assemble_stiffness_3d(mesh, eps=k)
    T = solve_dirichlet(K, np.zeros(mesh.num_nodes),
                        {tuple(m["boundary_nodes"]["z0"]): 0.0, tuple(m["boundary_nodes"]["z1"]): 1.0})
    flux = 1.0 / (1.0 / 1.0 + 0.5 / 0.01 + 1.0 / 1.0)  # series resistances per unit area
    z = m["nodes"][:, 2]
    exact = np.where(z <= 1.0, flux * z, np.where(z <= 1.5, flux * (1.0 + (z - 1.0) / 0.01), flux * (51.0 + (z - 1.5))))
    assert np.abs(T - exact).max() <= 1e-10
