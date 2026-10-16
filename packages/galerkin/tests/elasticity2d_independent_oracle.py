# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Direct polynomial oracles: no engine/refsol constitutive or assembly calls."""
import numpy as np

E, NU, AMPLITUDE = 17e6, .23, .002


def coefficients(plane):
    if plane == 'stress':
        return E/(1-NU**2), E*NU/(1-NU**2), E/(2*(1+NU))
    return E*(1-NU)/((1+NU)*(1-2*NU)), E*NU/((1+NU)*(1-2*NU)), E/(2*(1+NU))


def stress(strain, plane):
    # Explicit component formulas, never the production constitutive matrix.
    ex, ey, gamma = np.moveaxis(strain, -1, 0)
    if plane == 'stress':
        sx = E*(ex+NU*ey)/(1-NU**2)
        sy = E*(ey+NU*ex)/(1-NU**2)
    else:
        sx = E*((1-NU)*ex+NU*ey)/((1+NU)*(1-2*NU))
        sy = E*((1-NU)*ey+NU*ex)/((1+NU)*(1-2*NU))
    return np.stack((sx, sy, E*gamma/(2*(1+NU))), axis=-1)


def polynomial(points, plane):
    x, y = np.moveaxis(points, -1, 0)
    a = AMPLITUDE
    u = a*np.stack((x*x*y+x*y*y+x**3/3, x*y*y-2*x*x*y+y**3/4), axis=-1)
    strain = a*np.stack((2*x*y+y*y+x*x, 2*x*y-2*x*x+.75*y*y, (x-y)**2), axis=-1)
    c11, c12, mu = coefficients(plane)
    # -d_x sigma_xx - d_y sigma_xy; -d_x sigma_xy - d_y sigma_yy.
    fx = -a*(c11*(2*y+2*x)+c12*(2*y-4*x)+mu*(-2*x+2*y))
    fy = -a*(mu*(2*x-2*y)+c12*(2*x+2*y)+c11*(2*x+1.5*y))
    return u, strain, stress(strain, plane), np.stack((fx, fy), axis=-1)


def mixed(points, plane):
    x, y = np.moveaxis(points, -1, 0)
    k = NU if plane == 'stress' else NU/(1-NU)
    modulus = E if plane == 'stress' else E/(1-NU**2)
    a = AMPLITUDE
    u = a*np.stack((x*x+k*y*y, -2*k*x*y), axis=-1)
    strain = np.stack((2*a*x, -2*a*k*x, np.zeros_like(x)), axis=-1)
    sigma = np.stack((2*a*modulus*x, np.zeros_like(x), np.zeros_like(x)), axis=-1)
    force = np.stack((np.full_like(x, -2*a*modulus), np.zeros_like(x)), axis=-1)
    return u, strain, sigma, force


def quadrature(mesh, order):
    z, w = np.polynomial.legendre.leggauss(order)
    z, w = (z+1)/2, w/2
    r, s = np.meshgrid(z, z, indexing='ij')
    bary = np.stack((1-r, r*(1-s), r*s), axis=-1).reshape(-1, 3)
    qweights = (w[:, None]*w[None, :]*r).ravel()
    vertices = mesh.nodes[mesh.triangles]
    v, u = vertices[:, 1]-vertices[:, 0], vertices[:, 2]-vertices[:, 0]
    det = abs(v[:, 0]*u[:, 1]-v[:, 1]*u[:, 0])
    points = np.einsum('qi,tic->tqc', bary, vertices)
    return bary, points, det[:, None]*qweights[None, :]


def fe_strain(mesh, displacement):
    # Fit a local affine polynomial in Cartesian coordinates, independently of
    # the engine's B matrices, gradient convention and engineering shear map.
    vertices = mesh.nodes[mesh.triangles]
    matrix = np.concatenate((np.ones((*vertices.shape[:2], 1)), vertices), axis=-1)
    affine = np.linalg.solve(matrix, displacement[mesh.triangles])
    return np.stack((affine[:, 1, 0], affine[:, 2, 1],
                     affine[:, 2, 0]+affine[:, 1, 1]), axis=-1)


def errors(mesh, result, oracle, plane, order):
    bary, points, weight = quadrature(mesh, order)
    u, strain, _, _ = oracle(points, plane)
    uh = np.einsum('qi,tic->tqc', bary, result.displacement[mesh.triangles])
    delta_u = uh-u
    delta_s = fe_strain(mesh, result.displacement)[:, None]-strain
    strain_density = delta_s[..., 0]**2+delta_s[..., 1]**2+.5*delta_s[..., 2]**2
    energy_density = np.sum(delta_s*stress(delta_s, plane), axis=-1)
    return np.sqrt([np.sum(weight*np.sum(delta_u**2, axis=-1)),
                    np.sum(weight*strain_density), np.sum(weight*energy_density)])
