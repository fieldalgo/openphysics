# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent transformed scalar/mixed assembly and dense non-Hermitian QZ."""
import numpy as np
import pytest
import scipy.linalg as la
from galerkin import rectangle_mesh, solve_modes
from galerkin.mode_coordinates import mode_coordinates, solve_scalar_coordinates
from crosscheck import require_tool, Stopwatch, emit, make_record, observable


@pytest.mark.parametrize('bend', [False, True])
@pytest.mark.parametrize('vector', [False, True])
def test_transformed_modes_same_discretization(bend, vector):
    sk = require_tool('scikit-fem')
    from skfem.helpers import curl, grad
    mesh = rectangle_mesh(3., 2., 10, 8)
    eps = np.full(mesh.num_triangles, 2.25-.01j)
    c = mode_coordinates(mesh, thickness=dict(left=.6,right=.6,bottom=.5,top=.5),
                         bend_radius=5. if bend else None)
    k0 = 2*np.pi/1.55
    clock = Stopwatch()
    with clock('openphysics'):
        if vector:
            ours, *_ = solve_modes(mesh, eps, k0, 1.4, num_modes=4, coordinate_factors=c.factors)
        else:
            fixed = np.unique(np.concatenate(list(mesh.boundary.values())))
            ours, _ = solve_scalar_coordinates(mesh, eps, k0, 1.4, c.factors, num_modes=4, fixed_nodes=fixed)
    refmesh = sk.MeshTri(mesh.nodes.T.copy(), mesh.triangles.T.copy(), sort_t=False)
    element = sk.ElementTriN1()*sk.ElementTriP1() if vector else sk.ElementTriP1()
    basis = sk.Basis(refmesh, element, intorder=2)
    nq = basis.default_parameters()['x'].shape[-1]
    # Independent material tensor from the coordinate Jacobian, not engine matrices.
    sx, sy, h = (np.repeat(v[:, None], nq, axis=1) for v in c.factors.T)
    er = np.repeat(eps[:, None], nq, axis=1)
    ex, ey, ez = er*sy*h/sx, er*sx*h/sy, er*sx*sy/h
    mx, my, mz = sy*h/sx, sx*h/sy, sx*sy/h
    if vector:
        @sk.BilinearForm(dtype=complex)
        def left(et, z, vt, q, w):
            return curl(et)*curl(vt)/mz-k0**2*(ex*et[0]*vt[0]+ey*et[1]*vt[1])
        @sk.BilinearForm(dtype=complex)
        def right(et, z, vt, q, w):
            dz,dq=grad(z),grad(q)
            return ((et[0]+dz[0])*(vt[0]+dq[0])/my
                    +(et[1]+dz[1])*(vt[1]+dq[1])/mx-k0**2*ez*z*q)
    else:
        @sk.BilinearForm(dtype=complex)
        def left(u,v,w):
            du,dv=grad(u),grad(v)
            return k0**2*er*h*sx*sy*u*v-h*(sy/sx*du[0]*dv[0]+sx/sy*du[1]*dv[1])
        @sk.BilinearForm(dtype=complex)
        def right(u,v,w):
            return sx*sy/h*u*v
    with clock('reference'):
        free=basis.complement_dofs(basis.get_dofs().all())
        a,b=(f.assemble(basis)[free][:,free].toarray() for f in (left,right))
        lam=la.eigvals(a,b)
        ref=np.sqrt(((-1 if vector else 1)*lam[np.isfinite(lam)]).astype(complex))/k0
    # Match all returned candidates bijectively, not only one selected pole.
    from scipy.optimize import linear_sum_assignment
    rows,cols=linear_sum_assignment(abs(ours[:,None]-ref[None,:]))
    error=float(np.max(abs(ours[rows]-ref[cols])/abs(ref[cols])))
    emit(make_record(case=f'waveguide-pml-{"vector" if vector else "scalar"}-{"bend" if bend else "straight"}',
        physics='Cartesian complex coordinate modal pencil',api='galerkin.mode_coordinates / waveguide',
        discretization='centroid coefficients, lowest-order triangles',tool='scikit-fem',
        tool_discretization='ElementTriN1 x ElementTriP1' if vector else 'ElementTriP1',
        matched=['nodes, triangles, centroid coordinate factors, epsilon, PEC boundaries, degree-2 quadrature'],
        not_matched=['ordinary shift-invert ARPACK versus dense QZ'],
        analytical_acceptance='tests/galerkin/test_pml_modes.py',stopwatch=clock,
        observables=[observable('four complex effective indices','1','max relative difference',error,1e-9)]))
