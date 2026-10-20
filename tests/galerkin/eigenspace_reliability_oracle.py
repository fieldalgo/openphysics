# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Independent circular-fiber +/-l electric fields from Bessel roots.

Time convention exp(+i omega t), axial convention exp(-i beta z).
Ez=f(r) exp(i l phi), Hz=h f(r) exp(i l phi); mu=c=1.
Et=(-i beta grad Ez + i k0 zhat cross grad Hz)/(k0^2 n^2-beta^2).
Continuity of Ephi determines h; refsol supplies only the scalar root.
"""

import numpy as np
from scipy.special import jv, jvp, kv, kvp


def fiber_electric(points, mode, wavelength=1.5, radius=4., n1=1.45, n2=1.44):
    k0 = 2*np.pi/wavelength
    beta = k0*mode.neff
    uc, ws = mode.u/radius, mode.w/radius
    qc, qs = uc**2, -ws**2
    dc = uc*jvp(mode.l, mode.u)/jv(mode.l, mode.u)
    ds = ws*kvp(mode.l, mode.w)/kv(mode.l, mode.w)
    x, y = points[..., 0], points[..., 1]
    r = np.hypot(x, y)
    phi = np.arctan2(y, x)
    inside = r <= radius
    # No quadrature point is at r=0; interface tests also avoid the axis.
    f = np.where(inside, jv(mode.l, uc*r)/jv(mode.l, mode.u),
                 kv(mode.l, ws*r)/kv(mode.l, mode.w))
    df = np.where(inside, uc*jvp(mode.l, uc*r)/jv(mode.l, mode.u),
                  ws*kvp(mode.l, ws*r)/kv(mode.l, mode.w))
    q2 = np.where(inside, qc, qs)
    columns = []
    for l in (mode.l, -mode.l):
        h = 1j*beta*l/radius*(1/qc-1/qs)/(k0*(dc/qc-ds/qs))
        er = (-1j*beta*df+k0*l*h*f/r)/q2
        ep = (beta*l*f/r+1j*k0*h*df)/q2
        phase = np.exp(1j*l*phi)
        columns.append(np.stack((er*np.cos(phi)-ep*np.sin(phi),
                                 er*np.sin(phi)+ep*np.cos(phi), f), axis=-1)*phase[..., None])
    return np.stack(columns, axis=-1)


def sampled_spans(mesh, space, et, ez, mode, order=5):
    """Region-resolved triangle quadrature; evaluate FE polynomials directly.

    The polygon's interface differs from the analytic circle. Evaluate the
    analytic field at its actual radius, retaining this geometric error.
    """
    u, w = np.polynomial.legendre.leggauss(order)
    u, w = (u+1)/2, w/2
    uu, vv = np.meshgrid(u, u, indexing='ij')
    bary = np.stack((1-uu, uu*(1-vv), uu*vv), axis=-1).reshape(-1, 3)
    weights = (w[:, None]*w[None, :]*uu).ravel()
    vertices = mesh.nodes[mesh.triangles]
    points = np.einsum('qi,tic->tqc', bary, vertices)
    jac = np.stack((vertices[:, 1]-vertices[:, 0], vertices[:, 2]-vertices[:, 0]), axis=-1)
    det = np.linalg.det(jac)
    # Gradients derived from the coordinate affine map, not engine assembly.
    grads = np.einsum('ic,tcd->tid', np.array([[-1., -1.], [1., 0.], [0., 1.]]), np.linalg.inv(jac))
    field = np.zeros((len(vertices), len(bary), 3, len(et)), dtype=complex)
    for e, (i, j) in enumerate(((1, 2), (2, 0), (0, 1))):
        basis = bary[None, :, i, None]*grads[:, None, j]-bary[None, :, j, None]*grads[:, None, i]
        coef = et[:, space.tri_edges[:, e]].T*space.signs[:, e, None]
        field[:, :, :2] += basis[..., None]*coef[:, None, None, :]
    field[:, :, 2] = 1j*np.einsum('qi,mti->tqm', bary, ez[:, mesh.triangles])
    analytic = fiber_electric(points, mode)
    weight = np.sqrt(det[:, None]*weights[None, :])[:, :, None, None]
    return (field*weight).reshape(-1, len(et)), (analytic*weight).reshape(-1, 2)


def span_error(left, right):
    q, _ = np.linalg.qr(left)
    p, _ = np.linalg.qr(right)
    sigma = np.linalg.svd(p.conj().T@q, compute_uv=False)
    return np.sqrt(max(0., 1-min(sigma)**2))
