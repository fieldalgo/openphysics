# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded interleaved static wedge-harmonic Green matrices above one grounded line.

Internal module, consistent units: not part of galerkin's public API (the ``__all__``
of its public modules).
"""
from dataclasses import dataclass
import math

import numpy as np

from .laplace_corner_harmonic import power_panel_harmonic_self_log
from .laplace_corner_harmonic_interactions import (
    power_panel_harmonic_far_log as far,
    power_panel_harmonic_shared_vertex_log as vertex,
    power_panel_harmonic_separated_log as separated,
    power_panel_harmonic_constant_log_partitioned as mixed,
)
from .laplace_corner_assembly import offsets as _offsets
from .laplace_corner_geometry import (
    CornerPanelGeometry,
    immutable as _immutable,
    prepare_two_ground_corner_panels)


def _block(g,i,j,p,q,image=False):
 a=g['direction'][i];b=g['direction'][j].copy();o=_offsets(g,i,j,image)[0]
 if image:b*=np.array([1.,-1.])
 if not image and i==j:
  value=power_panel_harmonic_self_log(math.hypot(*a),p);return value,value
 la,lb,lo=[math.hypot(*x) for x in (a,b,o)]
 if lo>=4*(la+lb) and min(la,lb)/max(la,lb)>=1/64:
  result=far(a,b,o,p,q,quadrature_order=32)
 elif q==1:
  signs=np.ones(2)
  if not image and g['ends'][j] in (g['starts'][i],g['ends'][i]):
   b=-b;o=np.zeros(2) if g['ends'][j]==g['starts'][i] else a.copy();signs[1]=-1
  result=mixed(a,b,o,p)
  return result.coarse_mean_log_distance*signs[None],result.mean_log_distance*signs[None]
 elif p==1:
  coarse,fine=_block(g,j,i,q,p,image);return coarse.T,fine.T
 elif not image and g['starts'][i]==g['starts'][j]:result=vertex(a,b,p,q,quadrature_order=64)
 else:result=separated(a,b,o,p,q,quadrature_order=32)
 return result.coarse_mean_log_distance,result.mean_log_distance

def _assemble(geometry):
    count = geometry.panel_count
    local = dict(
        anchor=geometry.normalized_anchors,
        local=geometry.normalized_local_starts,
        direction=geometry.normalized_directions,
        starts=geometry.endpoint_ids[:, 0],
        ends=geometry.endpoint_ids[:, 1],
    )
    coarse = np.empty((2 * count, 2 * count))
    fine = np.empty_like(coarse)
    for i in range(count):
        for j in range(count):
            try:
                args = (local, i, j, geometry.exponents[i], geometry.exponents[j])
                real0, real1 = _block(*args)
                image0, image1 = _block(*args, image=True)
            except ValueError as exc:
                raise ValueError(f"harmonic panel pair {i}/{j}: {exc}") from exc
            rows, columns = slice(2 * i, 2 * i + 2), slice(2 * j, 2 * j + 2)
            coarse[rows, columns] = image0 - real0
            fine[rows, columns] = image1 - real1
    return coarse, fine


@dataclass(frozen=True)
class HarmonicCornerHalfSpaceMatrix:
    """Dimensionless raw Green blocks with two modes per physical panel.

    The modes are rho_p and sqrt(3)*(rho_2p-rho_p), where
    rho_a=a/h*u**(a-1) on the physical panel. These are static spatial modes.
    Density index 2*i is the unit-mass power mode; 2*i+1 is the zero-mass
    harmonic mode on geometry panel i. There is no symmetry averaging, charge
    solve, upper-plane or side-wall correction. The rectangle admits and
    normalizes geometry only; the Green function contains the y=0 ground.
    """

    geometry: CornerPanelGeometry
    coarse_matrix: np.ndarray
    matrix: np.ndarray
    quadrature_error: float
    reciprocity_error: float

    def __post_init__(self):
        for name in ("coarse_matrix", "matrix"):
            object.__setattr__(self, name, _immutable(getattr(self, name)))


def assemble_harmonic_corner_half_space(polygons, *, width, height, panels_per_edge=16):
    """Assemble bounded, two-mode static wedge-panel half-space Green matrices.

    Reuse convex, disjoint, strictly interior geometry admission in metres,
    even 16..512 subdivisions, and the existing merge of the first four
    cubic intervals at each edge end. Admit at most 512 physical panels
    (1024 density modes). Upper-plane and side-wall fields are absent.

    Exact self, bounded far, shared-origin, separated and explicitly partitioned mixed
    unit-source blocks keep
    physical basis masses and refinement evidence. Reversing a unit-power
    source endpoint flips its harmonic mode; a nonunit singularity is never
    reversed. Refuse unresolved pairs, normalized refinement or raw
    reciprocity above 1e-10, before any caller's symmetry averaging.
    Assembly checks alone do not establish field, panel-convergence or
    other-platform accuracy. Existing assemblers and solvers are unchanged.
    """
    geometry = prepare_two_ground_corner_panels(
        polygons, width=width, height=height, panels_per_edge=panels_per_edge
    )
    if geometry.panel_count > 512:
        raise ValueError("harmonic half-space assembly exceeds 512 physical panels")
    coarse, fine = _assemble(geometry)
    expected = (2 * geometry.panel_count,) * 2
    if (coarse.shape != expected or fine.shape != expected
            or not np.isfinite(coarse).all() or not np.isfinite(fine).all()):
        raise ValueError("harmonic half-space matrices must have finite two-mode shape")
    magnitude = float(np.max(abs(fine)))
    if not magnitude > 0:
        raise ValueError("harmonic half-space matrix scale must be positive")
    error = float(np.max(abs(fine - coarse)) / magnitude)
    reciprocity = max(
        float(np.max(abs(matrix - matrix.T)) / np.max(abs(matrix)))
        if np.max(abs(matrix)) > 0 else float("inf")
        for matrix in (coarse, fine)
    )
    if max(error, reciprocity) > 1e-10:
        raise ValueError("harmonic half-space quadrature or raw reciprocity failed")
    return HarmonicCornerHalfSpaceMatrix(geometry, coarse, fine, error, reciprocity)


__all__ = ["HarmonicCornerHalfSpaceMatrix", "assemble_harmonic_corner_half_space"]


# Public names of helpers shared with other galerkin panel modules (tests/galerkin/test_layers.py).
assemble = _assemble
