# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Direct continuum and integration oracles; no production/refsol helpers."""
import numpy as np

E, NU, A = 17e6, .23, .002
NORMALS = {'left': (-1., 0.), 'right': (1., 0.),
           'bottom': (0., -1.), 'top': (0., 1.)}


def stress(e, plane):
    ex, ey, g = np.moveaxis(e, -1, 0)
    if plane == 'stress':
        sx, sy = E*(ex+NU*ey)/(1-NU**2), E*(ey+NU*ex)/(1-NU**2)
    else:
        sx = E*((1-NU)*ex+NU*ey)/((1+NU)*(1-2*NU))
        sy = E*((1-NU)*ey+NU*ex)/((1+NU)*(1-2*NU))
    return np.stack((sx, sy, E*g/(2*(1+NU))), axis=-1)


def manufactured(p, plane):
    x, y = np.moveaxis(p, -1, 0)
    u = A*np.stack((x*x*y+x*y*y+x**3/3+.4+.2*x-.3*y,
                    x*y*y-2*x*x*y+y**3/4-.25+.35*x+.1*y), axis=-1)
    e = A*np.stack((2*x*y+y*y+x*x+.2, 2*x*y-2*x*x+.75*y*y+.1,
                    (x-y)**2+.05), axis=-1)
    if plane == 'stress':
        c, d = E/(1-NU**2), E*NU/(1-NU**2)
    else:
        c, d = E*(1-NU)/((1+NU)*(1-2*NU)), E*NU/((1+NU)*(1-2*NU))
    mu = E/(2*(1+NU))
    f = -A*np.stack((c*(2*x+2*y)+d*(2*y-4*x)+mu*(-2*x+2*y),
                     mu*(2*x-2*y)+d*(2*x+2*y)+c*(2*x+1.5*y)), axis=-1)
    return u, e, stress(e, plane), f


def surface(p, normals, plane):
    s = manufactured(p, plane)[2]
    return np.stack((s[..., 0]*normals[..., 0]+s[..., 2]*normals[..., 1],
                     s[..., 2]*normals[..., 0]+s[..., 1]*normals[..., 1]), axis=-1)


def integration(mesh, order):
    z, w = np.polynomial.legendre.leggauss(order)
    z, w = (z+1)/2, w/2
    r, s = np.meshgrid(z, z, indexing='ij')
    bary = np.stack((1-r, r*(1-s), r*s), axis=-1).reshape(-1, 3)
    weights = (w[:, None]*w[None, :]*r).ravel()
    p = mesh.nodes[mesh.triangles]
    v, u = p[:, 1]-p[:, 0], p[:, 2]-p[:, 0]
    det = abs(v[:, 0]*u[:, 1]-v[:, 1]*u[:, 0])
    return bary, np.einsum('qi,tic->tqc', bary, p), det[:, None]*weights[None, :]


def strain_fit(mesh, u):
    p = mesh.nodes[mesh.triangles]
    matrix = np.concatenate((np.ones((*p.shape[:2], 1)), p), axis=-1)
    fit = np.linalg.solve(matrix, u[mesh.triangles])
    return np.stack((fit[:, 1, 0], fit[:, 2, 1], fit[:, 1, 1]+fit[:, 2, 0]), axis=-1)


def errors(mesh, result, plane, order):
    bary, p, w = integration(mesh, order)
    u, e, _, _ = manufactured(p, plane)
    du = np.einsum('qi,tic->tqc', bary, result.displacement[mesh.triangles])-u
    de = strain_fit(mesh, result.displacement)[:, None]-e
    return np.sqrt([np.sum(w*np.sum(du*du, axis=-1)),
                    np.sum(w*(de[..., 0]**2+de[..., 1]**2+.5*de[..., 2]**2)),
                    np.sum(w*np.sum(de*stress(de, plane), axis=-1))])


def consistent_load(mesh, plane):
    """Separate order-7 interior/order-10 line integrals, known square normals."""
    bary, p, weight = integration(mesh, 7)
    body = manufactured(p, plane)[3]
    local = np.einsum('qi,tq,tqc->tic', bary, weight, body)
    load = np.zeros_like(mesh.nodes)
    np.add.at(load, mesh.triangles.ravel(), local.reshape(-1, 2))
    z, w = np.polynomial.legendre.leggauss(10)
    z, w = (z+1)/2, w/2
    for tag, normal in NORMALS.items():
        for i, j in mesh.boundary_edges[tag]:
            points = (1-z[:, None])*mesh.nodes[i]+z[:, None]*mesh.nodes[j]
            force = surface(points, np.asarray(normal), plane)
            length = np.linalg.norm(mesh.nodes[j]-mesh.nodes[i])
            load[i] += length*np.sum((w*(1-z))[:, None]*force, axis=0)
            load[j] += length*np.sum((w*z)[:, None]*force, axis=0)
    return load


def right_edge_load(mesh):
    """Exact antiderivatives for t=(3+2y^6,-4+y^5), without quadrature."""
    load = np.zeros_like(mesh.nodes)
    for i, j in mesh.boundary_edges['right']:
        a, b = mesh.nodes[i, 1], mesh.nodes[j, 1]
        if a > b:
            i, j, a, b = j, i, b, a
        def weights(power):
            integral = (b**(power+1)-a**(power+1))/(power+1)
            first_moment = (b**(power+2)-a**(power+2))/(power+2)
            return np.array([b*integral-first_moment, first_moment-a*integral])/(b-a)
        load[[i, j], 0] += 3*weights(0)+2*weights(6)
        load[[i, j], 1] += -4*weights(0)+weights(5)
    return load
