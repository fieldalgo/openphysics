# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Direct 3D continuum oracle. No production/FEM/refsol imports or API adapters.

This module is a continuum oracle, not a thermoelastic solver. Engineering input strain
is [exx,eyy,gamma_xy]. Returned tensors contain physical tensor shear components.
"""
import numpy as np

E0, NU0, ALPHA0, TREF0 = 70e9, .3, 12e-6, 293.15


def parent_moduli(young=E0, nu=NU0):
    return young/(2*(1+nu)), young*nu/((1+nu)*(1-2*nu))


def original_3d(strain, theta, plane, young=E0, nu=NU0, alpha=ALPHA0):
    """Eliminate z directly in the ORIGINAL 3D law; integrate nowhere here."""
    e = np.asarray(strain, dtype=float)
    a = np.asarray(theta, dtype=float)*alpha
    shape = np.broadcast_shapes(e.shape[:-1], a.shape)
    e, a = np.broadcast_to(e, (*shape, 3)), np.broadcast_to(a, shape)
    mu, lam = parent_moduli(young, nu)
    total = np.zeros((*shape, 3, 3))
    total[..., 0, 0], total[..., 1, 1] = e[..., 0], e[..., 1]
    total[..., 0, 1] = total[..., 1, 0] = e[..., 2]/2
    if plane == 'stress':
        # Solve 2mu*(ezz-a)+lambda*(exx+eyy+ezz-3a)=0.
        total[..., 2, 2] = ((2*mu+3*lam)*a-lam*(e[..., 0]+e[..., 1]))/(2*mu+lam)
    elif plane != 'strain':
        raise ValueError('explicit plane stress/strain required')
    thermal = a[..., None, None]*np.eye(3)
    elastic = total-thermal
    trace = np.trace(elastic, axis1=-2, axis2=-1)
    sigma = 2*mu*elastic+lam*trace[..., None, None]*np.eye(3)
    psi = mu*np.sum(elastic*elastic, axis=(-2, -1))+.5*lam*trace**2
    return dict(total=total, thermal=thermal, elastic=elastic, sigma=sigma, energy=psi)


def compatible(points, plane, theta0=10., gradient=20., alpha=ALPHA0, nu=NU0):
    x, y = np.moveaxis(np.asarray(points), -1, 0)
    a0, p = alpha*theta0, alpha*gradient
    factor = 1. if plane == 'stress' else 1+nu
    u = factor*np.stack((a0*x+.5*p*(x*x-y*y), a0*y+p*x*y), axis=-1)
    theta = theta0+gradient*x
    e = factor*np.stack((alpha*theta, alpha*theta, np.zeros_like(theta)), axis=-1)
    return u, e, theta


def nonlinear_fields(points, plane, polynomial=False, young=E0, nu=NU0, alpha=ALPHA0):
    """Analytic continuum fields and directly differentiated total-stress force.

    The preregistered sine gate is retained. A distinct polynomial is an
    additional independent oracle, not a replacement for section 8's sine gate.
    Unit square coordinates are numerical metres (L0=1m).
    """
    x, y = np.moveaxis(np.asarray(points), -1, 0)
    mu, lam3 = parent_moduli(young, nu)
    lam = young*nu/(1-nu**2) if plane == 'stress' else lam3
    beta = young*alpha/(1-nu if plane == 'stress' else 1-2*nu)
    if polynomial:
        amp = 1e-4
        theta = 8+13*x*x-7*x*y+5*y*y
        u = amp*np.stack((x*x*y+x*y*y+x**3/3, x*y*y-2*x*x*y+y**3/4), axis=-1)
        e = amp*np.stack((2*x*y+y*y+x*x, 2*x*y-2*x*x+.75*y*y, (x-y)**2), axis=-1)
        fx = -amp*((lam+2*mu)*(2*x+2*y)+lam*(2*y-4*x)+mu*(-2*x+2*y))+beta*(26*x-7*y)
        fy = -amp*(mu*(2*x-2*y)+lam*(2*x+2*y)+(lam+2*mu)*(2*x+1.5*y))+beta*(-7*x+10*y)
        grad_theta = np.stack((26*x-7*y, -7*x+10*y), axis=-1)
    else:
        pi = np.pi
        sx, sy, cx, cy = np.sin(pi*x), np.sin(pi*y), np.cos(pi*x), np.cos(pi*y)
        s, c = sx*sy, cx*cy
        a, b = 1e-4, .6e-4
        theta = 20*s
        u = np.stack((a*s, b*s), axis=-1)
        e = pi*np.stack((a*cx*sy, b*sx*cy, a*sx*cy+b*cx*sy), axis=-1)
        fx = pi*pi*((lam+3*mu)*a*s-(lam+mu)*b*c)+beta*20*pi*cx*sy
        fy = pi*pi*((lam+3*mu)*b*s-(lam+mu)*a*c)+beta*20*pi*sx*cy
        grad_theta = 20*pi*np.stack((cx*sy, sx*cy), axis=-1)
    return dict(displacement=u, strain=e, theta=theta, grad_theta=grad_theta,
                body=np.stack((fx, fy), axis=-1), state=original_3d(e, theta, plane, young, nu, alpha))


def triangle_rule(order=10):
    """Independent Duffy quadrature on [(0,0),(1,0),(0,1)], weights sum to .5."""
    r, w = np.polynomial.legendre.leggauss(order)
    r, w = (r+1)/2, w/2
    u, v = np.meshgrid(r, r, indexing='ij')
    bary = np.stack((1-u, u*(1-v), u*v), axis=-1).reshape(-1, 3)
    return bary, (w[:, None]*w[None, :]*u).ravel()


