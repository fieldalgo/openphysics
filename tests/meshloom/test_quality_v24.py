# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The C11 capacitor on ``meshloom.generate3d`` meshes: V24 (and V5 on its spheres).

Rows of docs/packages/meshine/validation3d.md, with the constants of its "Frozen
baseline constants" section (Gmsh 4.15.2 with the Netgen optimizer):

- V24 on C11 (spheres a = 0.5, b = 0.75, c = 1; the sizes {0.1, 0.05, 0.025} of the
  amendment of 2026-11-21): u = 1 on the inner sphere, 0 on the outer, eps = 1 on
  (a, b) and 4 on (b, c). The error e = |C_h - 16 pi/3| / (16 pi/3), with C_h = u^T K u,
  has a least-squares slope of at least 1.6 against h. The free system is solved by
  conjugate gradients (Jacobi preconditioner) to a relative residual of 1e-12 (fixed
  before h = 0.025 was first run): eight orders below the error expected at h = 0.025
  (about 5e-4), so the solver cannot bend the slope. The same meshes check V5 on C11's
  three spheres at the plan's sizes.

The finest sizes run with the slow studies. Rows the mesher does not meet yet are not
here; they are listed on the meshloom page under its limits. The cases and measures are
in quality_cases.py.
"""

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from meshloom import builder  # noqa: E402

V24_RTOL = 1e-12  # conjugate gradients, relative residual; fixed before the h = 0.025 run


@pytest.mark.slow
def test_v24_capacitor_converges():
    import scipy.sparse.linalg as spla
    from fractions import Fraction
    from galerkin import from_mesher
    from galerkin.kernels import assemble_stiffness_3d
    hs, errors = [0.1, 0.05, 0.025], []
    for h in hs:
        kw = builder.nested_spheres(h)
        m = meshloom.generate3d(h=h, **kw)
        for i, r in enumerate((0.5, 0.75, 1.0)):  # V5 on the plan's sizes: the input points are the nodes
            ids = sorted({v for f in kw["locked_facets"] if kw["facet_tags"][f] == f"sphere{i}" for v in kw["facets"][f][0]})
            worst = max(abs(sum(Fraction(float(x)) ** 2 for x in kw["points"][v]) - Fraction(r) ** 2) / (2 * Fraction(r) ** 2)
                        for v in ids)
            assert worst <= Fraction(1, 10 ** 15), (h, i, float(worst))
        mesh = from_mesher(m)
        eps = np.array([{"inner": 1.0, "outer": 4.0}[n] for n in m["region_names"]])[m["regions"]]
        K = assemble_stiffness_3d(mesh, eps=eps).tocsr()
        u = np.zeros(mesh.num_nodes)
        inner, outer = m["boundary_nodes"]["sphere0"], m["boundary_nodes"]["sphere2"]
        u[inner] = 1.0
        fixed = np.union1d(inner, outer)
        free = np.setdiff1d(np.arange(mesh.num_nodes), fixed)
        A = K[free][:, free]
        b = -(K[free][:, fixed] @ u[fixed])
        jacobi = spla.LinearOperator(A.shape, matvec=lambda x, d=A.diagonal(): x / d)
        x, info = spla.cg(A, b, rtol=V24_RTOL, atol=0.0, M=jacobi, maxiter=100_000)
        assert info == 0 and np.linalg.norm(A @ x - b) <= 10 * V24_RTOL * np.linalg.norm(b), (h, info)
        u[free] = x
        errors.append(abs(u @ (K @ u) - 16 * np.pi / 3) / (16 * np.pi / 3))
    slope = np.polyfit(np.log(hs), np.log(errors), 1)[0]
    assert slope >= 1.6, (slope, errors)
