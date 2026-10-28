# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Closed-form element kernels for the lowest-order spaces.

Each kernel returns element matrices ``(T, i, j)`` or vectors ``(T, i)`` in the
array library of its coefficient (NumPy for Python scalars), ready for
``galerkin.core.forms.matrix`` or ``vector``. Mesh geometry is static and
computed with NumPy; only coefficients may be live, so a JAX or PyTorch
coefficient carries its derivative into the element matrices.

On NumPy the arithmetic is, operation for operation, that of the hand-written
assembly it mirrors (named in each docstring), so assembling these kernels
reproduces those matrices bit for bit.
"""
import numpy as np

from .backend import Backend, backend_of, namespace
from .tets import tet_gradients

# Local edge e of a triangle is the edge opposite node e: (e+1, e+2) mod 3.
_TRI_I = (1, 2, 0)
_TRI_J = (2, 0, 1)
# Local edges of a tetrahedron, as in galerkin.edge3d.
_TET_EDGES = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
_TET_I = np.array([e[0] for e in _TET_EDGES])
_TET_J = np.array([e[1] for e in _TET_EDGES])


def coefficient(value):
    """``(xp, value)`` with value in its own library, keeping double precision.

    A Python scalar or a NumPy array stays NumPy (float64 or complex128); a JAX or
    PyTorch array stays where it is.
    """
    if isinstance(value, (bool, int, float, complex, list, tuple)):
        value = np.asarray(value)
    return namespace(value), value


def _einsum(xp, spec, *operands):
    """``xp.einsum``; on PyTorch the operands are first brought to one dtype.

    NumPy and JAX promote mixed real and complex operands themselves; PyTorch's
    einsum refuses them (a real basis with a complex coefficient).
    """
    if backend_of(xp) is Backend.TORCH:
        dtype = operands[0].dtype
        for operand in operands[1:]:
            dtype = xp.result_type(dtype, operand.dtype)
        operands = [xp.astype(operand, dtype) for operand in operands]
    return xp.einsum(spec, *operands)


def _lift(xp, array):
    return xp.asarray(array)


def _real_coefficient(xp, coeff):
    """As ``np.asarray(coeff, dtype=float)`` in galerkin.edge3d: a complex coefficient is refused."""
    if xp.isdtype(coeff.dtype, "complex floating"):
        raise TypeError("this 3D edge kernel takes a real coefficient")
    return xp.astype(coeff, xp.float64)


# -- P1 triangles (galerkin.assembly) ------------------------------------------

def _triangle_bc(mesh):
    p = mesh.nodes[mesh.triangles]
    x, y = p[:, :, 0], p[:, :, 1]
    b = np.stack([y[:, 1] - y[:, 2], y[:, 2] - y[:, 0], y[:, 0] - y[:, 1]], axis=1)
    c = np.stack([x[:, 2] - x[:, 1], x[:, 0] - x[:, 2], x[:, 1] - x[:, 0]], axis=1)
    area = np.abs(0.5 * (b[:, 0] * c[:, 1] - b[:, 1] * c[:, 0]))
    return b, c, area


def p1_stiffness(mesh, eps=1.0):
    """``int eps grad phi_j . grad phi_i``; eps scalar, (T,) or (T, 2, 2). Mirrors assemble_stiffness."""
    xp, eps = coefficient(eps)
    b, c, area = _triangle_bc(mesh)
    if eps.ndim == 3:
        g = _lift(xp, np.stack([b, c], axis=2))
        return _einsum(xp, "tie,tef,tjf->tij", g, eps, g) / _lift(xp, 4.0 * area)[:, None, None]
    eps = xp.broadcast_to(eps, (len(area),))
    bb = _lift(xp, b[:, :, None] * b[:, None, :] + c[:, :, None] * c[:, None, :])
    return (eps / _lift(xp, 4.0 * area))[:, None, None] * bb


_P1_MASS = np.array([[2.0, 1.0, 1.0], [1.0, 2.0, 1.0], [1.0, 1.0, 2.0]]) / 12.0


def p1_mass(mesh, coeff=1.0):
    """``int c phi_i phi_j``; coeff scalar or (T,). Mirrors assemble_mass."""
    xp, coeff = coefficient(coeff)
    area = mesh.areas()
    coeff = xp.broadcast_to(coeff, (len(area),))
    return (coeff * _lift(xp, area))[:, None, None] * _lift(xp, _P1_MASS)


def p1_boundary_mass(mesh, edges, coeff=1.0):
    """``int_edge c phi_i phi_j ds`` on boundary edges (E, 2); coeff scalar or (E,). Mirrors assemble_boundary_mass."""
    xp, coeff = coefficient(coeff)
    edges = np.asarray(edges, dtype=int)
    p = mesh.nodes[edges]
    length = np.linalg.norm(p[:, 1] - p[:, 0], axis=1)
    coeff = xp.broadcast_to(coeff, (len(edges),))
    base = np.array([[2.0, 1.0], [1.0, 2.0]]) / 6.0
    return (coeff * _lift(xp, length))[:, None, None] * _lift(xp, base)


def p1_load(mesh, rho=0.0):
    """``int rho phi_i`` with the centroid rule; rho scalar, (T,) or callable(x, y).

    Mirrors assemble_load; assemble it with ``forms.vector(..., order="columns")``.
    """
    tris = mesh.triangles
    area = mesh.areas()
    if callable(rho):
        centroid = mesh.nodes[tris].mean(axis=1)
        xp, rho_e = coefficient(rho(centroid[:, 0], centroid[:, 1]))
    else:
        xp, rho_e = coefficient(rho)
        rho_e = xp.broadcast_to(_real_coefficient(xp, rho_e), (len(tris),))
    contrib = rho_e * _lift(xp, area) / 3.0
    return xp.stack([contrib, contrib, contrib], axis=1)


# -- P1 tetrahedra (galerkin.assembly3d) ---------------------------------------

def tet_stiffness(mesh, eps=1.0):
    """``int eps grad phi_n . grad phi_m``; eps scalar, (T,) or (T, 3, 3). Mirrors assemble_stiffness_3d."""
    xp, eps = coefficient(eps)
    g, vol = tet_gradients(mesh)
    if eps.ndim == 3:
        return _einsum(xp, "tmd,tde,tne->tmn", _lift(xp, g), eps, _lift(xp, g)) * _lift(xp, vol)[:, None, None]
    c = xp.broadcast_to(eps, (mesh.num_tets,))
    return _lift(xp, np.einsum("tmd,tnd->tmn", g, g)) * (c * _lift(xp, vol))[:, None, None]


def tet_mass(mesh, coeff=1.0):
    """``int c phi_m phi_n``; coeff scalar or (T,). Mirrors assemble_mass_3d."""
    xp, coeff = coefficient(coeff)
    vol = mesh.volumes()
    c = xp.broadcast_to(coeff, (mesh.num_tets,))
    return (c * _lift(xp, vol))[:, None, None] * _lift(xp, (np.ones((4, 4)) + np.eye(4)) / 20.0)


# -- Lowest-order Nédélec on triangles (galerkin.edge) -------------------------

def _triangle_gradients(mesh):
    """Barycentric gradients (T, 3, 2) and areas, as galerkin.edge computes them."""
    b, c, area = _triangle_bc(mesh)
    return np.stack([b, c], axis=2) / (2.0 * area)[:, None, None], area


def nedelec_curlcurl(space, coeff=1.0):
    """``int c curl W_e curl W_f``; coeff scalar or (T,). Mirrors assemble_curlcurl."""
    xp, coeff = coefficient(coeff)
    g, area = _triangle_gradients(space.mesh)
    coeff = xp.broadcast_to(coeff, (len(area),))
    curls = np.stack([2.0 * (g[:, i, 0] * g[:, j, 1] - g[:, i, 1] * g[:, j, 0])
                      for i, j in zip(_TRI_I, _TRI_J)], axis=1) * space.signs
    curls = _lift(xp, curls)
    return (coeff * _lift(xp, area))[:, None, None] * curls[:, :, None] * curls[:, None, :]


def _nedelec_midpoint_values(space, g):
    """W_e at the three edge midpoints, signs applied: (T, 3 edges, 3 points, 2)."""
    lam = 0.5 * (np.ones((3, 3)) - np.eye(3))
    W = np.stack([lam[None, :, i, None] * g[:, None, j, :] - lam[None, :, j, None] * g[:, None, i, :]
                  for i, j in zip(_TRI_I, _TRI_J)], axis=1)
    return W * space.signs[:, :, None, None]


def nedelec_mass(space, coeff=1.0):
    """``int c W_e . W_f`` (exact edge-midpoint rule); coeff scalar, (T,) or (T, 2, 2). Mirrors assemble_edge_mass."""
    xp, coeff = coefficient(coeff)
    g, area = _triangle_gradients(space.mesh)
    W = _nedelec_midpoint_values(space, g)
    if coeff.ndim == 3:
        return _einsum(xp, "teqd,tdk,tfqk->tef", _lift(xp, W), coeff, _lift(xp, W)) * _lift(xp, area / 3.0)[:, None, None]
    coeff = xp.broadcast_to(coeff, (len(area),))
    return _lift(xp, np.einsum("teqd,tfqd->tef", W, W)) * (coeff * _lift(xp, area) / 3.0)[:, None, None]


def nedelec_grad(space, coeff=1.0):
    """``int c W_e . grad phi_n``, element shape (T, 3 edges, 3 nodes). Mirrors assemble_edge_grad.

    Rows are ``space.tri_edges``, columns ``space.mesh.triangles``.
    """
    xp, coeff = coefficient(coeff)
    g, area = _triangle_gradients(space.mesh)
    diff = np.stack([g[:, j, :] - g[:, i, :] for i, j in zip(_TRI_I, _TRI_J)], axis=1)   # (T, 3, 2)
    if coeff.ndim == 3:
        Ge = _einsum(xp, "ted,tdf,tkf->tek", _lift(xp, diff), coeff, _lift(xp, g))
        scale = _lift(xp, area) / 3.0
    else:
        coeff = xp.broadcast_to(coeff, (len(area),))
        Ge = _lift(xp, np.einsum("ted,tkd->tek", diff, g))
        scale = coeff * _lift(xp, area) / 3.0
    return Ge * scale[:, None, None] * _lift(xp, space.signs)[:, :, None]


# -- Lowest-order Nédélec on tetrahedra (galerkin.edge3d) ----------------------

def nedelec3d_curlcurl(space, coeff=1.0):
    """``int c curl W_e . curl W_f``; coeff scalar or (T,). Mirrors assemble_curlcurl_3d."""
    xp, coeff = coefficient(coeff)
    g, vol = tet_gradients(space.mesh)
    c = xp.broadcast_to(_real_coefficient(xp, coeff), (space.mesh.num_tets,))
    curls = 2.0 * np.cross(g[:, _TET_I, :], g[:, _TET_J, :]) * space.signs[:, :, None]
    return _lift(xp, np.einsum("ted,tfd->tef", curls, curls)) * (c * _lift(xp, vol))[:, None, None]


def nedelec3d_mass(space, coeff=1.0):
    """``int c W_e . W_f`` (exact); coeff scalar or (T,). Mirrors assemble_edge_mass_3d."""
    xp, coeff = coefficient(coeff)
    g, vol = tet_gradients(space.mesh)
    c = xp.broadcast_to(_real_coefficient(xp, coeff), (space.mesh.num_tets,))
    G = np.einsum("tad,tbd->tab", g, g)
    d = np.eye(4)
    i, j = _TET_I[:, None], _TET_J[:, None]
    k, l = _TET_I[None, :], _TET_J[None, :]
    Me = ((1 + d[i, k]) * G[:, j, l] - (1 + d[i, l]) * G[:, j, k]
          - (1 + d[j, k]) * G[:, i, l] + (1 + d[j, l]) * G[:, i, k])
    return (_lift(xp, Me) * (c * _lift(xp, vol) / 20.0)[:, None, None]
            * _lift(xp, space.signs[:, :, None] * space.signs[:, None, :]))


def nedelec3d_components(space):
    """Curl-curl and mass element matrices split by Cartesian component: NumPy (3, T, 6, 6) each.

    Summed over the component they are ``nedelec3d_curlcurl`` and
    ``nedelec3d_mass`` with coefficient 1. Scaling the mesh along the axes,
    x_a -> d_a x_a, maps them exactly to sum_a d_a^2 / (d_x d_y d_z) K_a and
    (d_x d_y d_z) sum_a M_a / d_a^2 (edge functions transform covariantly).
    """
    g, vol = tet_gradients(space.mesh)
    curls = 2.0 * np.cross(g[:, _TET_I, :], g[:, _TET_J, :]) * space.signs[:, :, None]
    signs = space.signs[:, :, None] * space.signs[:, None, :]
    d = np.eye(4)
    i, j = _TET_I[:, None], _TET_J[:, None]
    k, l = _TET_I[None, :], _TET_J[None, :]
    stiffness, mass = [], []
    for a in range(3):
        stiffness.append(np.einsum("te,tf->tef", curls[:, :, a], curls[:, :, a]) * vol[:, None, None])
        G = g[:, :, None, a] * g[:, None, :, a]
        Me = ((1 + d[i, k]) * G[:, j, l] - (1 + d[i, l]) * G[:, j, k]
              - (1 + d[j, k]) * G[:, i, l] + (1 + d[j, l]) * G[:, i, k])
        mass.append(Me * (vol / 20.0)[:, None, None] * signs)
    return np.stack(stiffness), np.stack(mass)


def nedelec3d_grad(space, coeff=1.0):
    """``int c W_e . grad phi_n``, element shape (T, 6 edges, 4 nodes). Mirrors assemble_edge_grad_3d."""
    xp, coeff = coefficient(coeff)
    g, vol = tet_gradients(space.mesh)
    c = xp.broadcast_to(_real_coefficient(xp, coeff), (space.mesh.num_tets,))
    Ge = _lift(xp, np.einsum("ted,tnd->ten", g[:, _TET_J, :] - g[:, _TET_I, :], g))
    return Ge * (c * _lift(xp, vol) / 4.0)[:, None, None] * _lift(xp, space.signs)[:, :, None]


# -- Vector P1 (galerkin.elasticity) -------------------------------------------

def vector_p1_stiffness(bmat, d, area):
    """``int B^T D B`` from strain matrices (T, 3, 6), D (3, 3) or (T, 3, 3), areas (T,).

    Mirrors the stiffness half of galerkin.elasticity.stiffness_and_stress.
    """
    xp, d = coefficient(d)
    if d.ndim == 2:
        return _einsum(xp, "tji,jk,tkl,t->til", _lift(xp, bmat), d, _lift(xp, bmat), _lift(xp, area))
    return _einsum(xp, "tji,tjk,tkl,t->til", _lift(xp, bmat), d, _lift(xp, bmat), _lift(xp, area))
