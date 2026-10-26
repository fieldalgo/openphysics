# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Cartesian modal PML and constant-radius coordinates, exp(+i omega t)."""
from dataclasses import dataclass
import numpy as np
import scipy.sparse.linalg as spla
from .assembly import assemble_mass, assemble_stiffness


@dataclass(frozen=True)
class ModeCoordinates:
    """Piecewise centroid coefficients and masks; not a physical-energy model."""
    factors: np.ndarray
    physical: np.ndarray
    physical_nodes: np.ndarray
    node_h: np.ndarray
    bounds: np.ndarray
    physical_bounds: np.ndarray


def mode_coordinates(mesh, *, thickness, strength=3.0, order=2,
                     bend_radius=None, bend_axis="x", bend_origin=0.0):
    """Coordinate Jacobian diag(sx,sy,h) on the existing rectangular domain.

    thickness maps left/right/bottom/top to nonnegative lengths in mesh units.
    The physical window is the domain minus these interior strips. The material
    distribution must already extend correctly through the PML. strength is
    dimensionless: s=1-i*strength*(depth/thickness)**order. R is measured from
    bend_origin on the selected outward axis and z=R*theta is reference arc length.
    """
    sides = ("left", "right", "bottom", "top")
    if not isinstance(thickness, dict) or set(thickness)-set(sides):
        raise ValueError("PML thickness must map left/right/bottom/top to lengths")
    if any(isinstance(v, (bool, np.bool_)) or not isinstance(v, (int, float, np.number)) for v in thickness.values()):
        raise ValueError("PML thicknesses must be numeric lengths, not booleans")
    widths = np.array([thickness.get(s, 0.) for s in sides], dtype=float)
    if not np.isfinite(widths).all() or np.any(widths < 0) or not np.any(widths > 0):
        raise ValueError("PML thicknesses must be finite, nonnegative, with at least one positive")
    if isinstance(strength, bool) or not np.isfinite(strength) or strength <= 0:
        raise ValueError("PML strength must be finite and positive")
    if isinstance(order, bool) or order not in (2, 3, 4):
        raise ValueError("PML order must be 2, 3 or 4")
    bounds = np.array([mesh.nodes.min(axis=0), mesh.nodes.max(axis=0)])
    if set(mesh.boundary) != set(sides):
        raise ValueError("modal coordinates require a rectangular mesh with four named outer faces")
    for side, dim, upper in (("left",0,0),("right",0,1),("bottom",1,0),("top",1,1)):
        if not np.allclose(mesh.nodes[mesh.boundary[side],dim], bounds[upper,dim], rtol=0,
                           atol=1e-12*np.max(bounds[1]-bounds[0])):
            raise ValueError("modal coordinates require rectangular outer faces")
    inner = bounds.copy()
    inner[0] += widths[[0, 2]]
    inner[1] -= widths[[1, 3]]
    if np.any(inner[0] >= inner[1]):
        raise ValueError("PML strips leave no physical window")
    if bend_axis not in ("x", "y"):
        raise ValueError("bend_axis must be x or y")
    axis = 0 if bend_axis == "x" else 1
    if bend_radius is not None:
        if (isinstance(bend_radius, bool) or not np.isfinite(bend_radius) or bend_radius <= 0
                or not np.isfinite(bend_origin) or bend_radius+bounds[0, axis]-bend_origin <= 0):
            raise ValueError("bend radius must be positive and the entire domain must have positive radius")

    def at(points):
        stretch = np.ones(points.shape, dtype=complex)
        mapped = points.astype(complex).copy()
        for dim in (0, 1):
            for upper in (False, True):
                width = widths[2*dim+int(upper)]
                if width == 0:
                    continue
                sign = 1 if upper else -1
                start = inner[int(upper), dim]
                depth = np.clip(sign*(points[:, dim]-start), 0, width)
                stretch[:, dim] -= 1j*strength*(depth/width)**order
                mapped[:, dim] -= sign*1j*strength*width/(order+1)*(depth/width)**(order+1)
        h = np.ones(len(points), dtype=complex) if bend_radius is None else 1+(mapped[:, axis]-bend_origin)/bend_radius
        return np.column_stack([stretch, h])

    cent = mesh.nodes[mesh.triangles].mean(axis=1)
    physical = np.all((cent >= inner[0]) & (cent <= inner[1]), axis=1)
    physical_nodes = np.all((mesh.nodes >= inner[0]) & (mesh.nodes <= inner[1]), axis=1)
    if not physical.any() or not physical_nodes.any() or physical.all():
        raise ValueError("mesh must resolve both the physical window and the PML")
    return ModeCoordinates(at(cent), physical, physical_nodes, at(mesh.nodes)[:, 2], bounds, inner)


def scalar_coordinate_system(mesh, eps_r, k0, factors):
    """A u=beta^2 B u for the scalar Helmholtz approximation in these coordinates."""
    factors = np.asarray(factors)
    if factors.shape != (mesh.num_triangles, 3) or not np.isfinite(factors).all() or np.any(factors == 0):
        raise ValueError("coordinate factors must be finite nonzero (triangles, 3)")
    sx, sy, h = factors.T
    tensor = np.zeros((mesh.num_triangles, 2, 2), dtype=complex)
    tensor[:, 0, 0], tensor[:, 1, 1] = h*sy/sx, h*sx/sy
    A = k0**2*assemble_mass(mesh, np.asarray(eps_r)*h*sx*sy)-assemble_stiffness(mesh, tensor)
    B = assemble_mass(mesh, sx*sy/h)
    return A, B


def solve_scalar_coordinates(mesh, eps_r, k0, n_target, factors, *, num_modes=6, fixed_nodes=()):
    """Complex scalar candidates, without a Hermitian/generalized-mass assumption.

    Returns n_eff and nodal fields. Amplitudes are arbitrary; no candidate is
    silently classified as a physical resonance by this low-level solver.
    """
    A, B = scalar_coordinate_system(mesh, eps_r, k0, factors)
    free = np.setdiff1d(np.arange(mesh.num_nodes), fixed_nodes)
    Af, Bf = A[free][:, free].tocsc(), B[free][:, free].tocsc()
    count = min(num_modes, len(free)-2)
    if count < 1:
        raise ValueError("too few free nodes for a scalar mode search")
    shift = (k0*n_target)**2
    lu = spla.splu((Af-shift*Bf).tocsc())
    op = spla.LinearOperator(Af.shape, matvec=lambda x: lu.solve(Bf@x), dtype=lu.L.dtype)
    val, vec = spla.eigs(op, k=count, which="LM", v0=np.ones(len(free)),
                         ncv=min(len(free), max(4*count, 40)), maxiter=20000)
    neff = np.sqrt((shift+1/val).astype(complex))/k0
    indices = np.argsort(-neff.real)
    fields = np.zeros((mesh.num_nodes, count), dtype=complex)
    fields[free] = vec[:, indices]
    return neff[indices], fields
