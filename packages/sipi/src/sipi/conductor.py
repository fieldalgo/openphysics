# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""High-frequency conductor loss from quasi-TEM surface-current distributions.

The exterior field is the perfect-conductor vacuum field. Finite conductivity
is a first-order surface-impedance perturbation, not an interior eddy-current
solve. DC, thin strips and insufficiently small skin depth are rejected by the
cross-section adapter. exp(+j omega t), SI units throughout.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.constants import epsilon_0, mu_0

from galerkin import assemble_stiffness, solve_dirichlet
from .network import _frequencies, _scalar, rlgc_network
from .quasistatic import _node_set
from .roughness import CausalHuray

__all__ = ['SurfaceCurrentFactors', 'ConductorLoss', 'surface_current_factors',
           'surface_impedance', 'surface_conductor_loss']


def _metal_samples(frequency, conductivity, relative_permeability, roughness_rms,
                   roughness=None):
    f = _frequencies(frequency)
    if f[0] <= 0:
        raise ValueError('surface impedance needs strictly positive frequency; DC is unsupported')
    sigma = _scalar('conductivity', conductivity)
    mu_r = _scalar('relative_permeability', relative_permeability)
    rms = _scalar('roughness_rms', roughness_rms, zero=True)
    if roughness is not None:
        if not isinstance(roughness, CausalHuray):
            raise TypeError('roughness must be a CausalHuray model or None')
        if rms != 0:
            raise ValueError('choose either roughness_rms or a causal roughness model')
    log_f = np.log(f)
    if np.any(np.log(sigma)-np.log(2*np.pi*epsilon_0)-log_f < np.log(1000)):
        raise ValueError('surface approximation requires sigma/(omega*eps0) >= 1000')
    log_mu = np.log(mu_0)+np.log(mu_r)
    delta = np.exp(-.5*(np.log(np.pi)+log_f+log_mu+np.log(sigma)))
    resistance = np.exp(.5*(np.log(np.pi)+log_f+log_mu-np.log(sigma)))
    if (not np.all(np.isfinite(delta)) or np.any(delta <= 0)
            or not np.all(np.isfinite(resistance)) or np.any(resistance <= 0)):
        raise ValueError('surface impedance cannot be represented for these inputs')
    scale = np.maximum(rms, delta)
    correction = 1+2/np.pi*np.arctan2(1.4*(rms/scale)**2, (delta/scale)**2)
    # Hammerstad is an empirical resistance correction. Do not invent a
    # roughness reactance or imply broadband causality for this correction.
    impedance = resistance*correction + 1j*resistance
    if roughness is not None:
        # Re((1+j)*H) and Im((1+j)*H) are different corrections.
        correction, reactance = roughness._impedance_factors(delta)
        with np.errstate(over='ignore', invalid='ignore'):
            impedance = resistance*correction + 1j*(resistance*reactance)
    if not np.all(np.isfinite(impedance)):
        raise ValueError('surface impedance cannot be represented for these inputs')
    return f, delta, correction, impedance


def surface_impedance(frequency, *, conductivity, relative_permeability=1.0,
                      roughness_rms=0.0, roughness=None):
    """Ohm/square samples for a uniform good-conductor half-space.

    Smooth Zs=(1+j)*sqrt(pi*f*mu/sigma). Optional Hammerstad RMS roughness
    multiplies only its resistance by 1+(2/pi)*atan(1.4*(Rq/delta)^2).
    The correction is empirical, without an added causal reactance model.
    Alternatively roughness=CausalHuray(...) changes both resistance and
    reactance; it cannot be combined with nonzero roughness_rms.
    Geometry/skin-depth validity is checked by surface_conductor_loss, not here.
    """
    return _metal_samples(frequency, conductivity, relative_permeability, roughness_rms,
                          roughness)[3]


def _readonly(value, dtype=float):
    result = np.array(value, dtype=dtype, copy=True)
    if not np.all(np.isfinite(result)):
        raise ValueError('nonfinite surface-current result')
    result.setflags(write=False)
    return result


@dataclass(frozen=True)
class SurfaceCurrentFactors:
    """Surface integrals of Ki*Kj (1/m) for unit longitudinal signal currents.

    parts is (N+1,N,N): each signal boundary in names order, then all reference
    boundaries together. current_integrals is (N+1,N); its target is [I;-ones].
    Flux disagreement estimates boundary-gradient error, not resistance error.
    """
    names: tuple[str, ...]
    parts: np.ndarray
    current_integrals: np.ndarray
    C0: np.ndarray

    def __post_init__(self):
        names = tuple(self.names)
        if not names or len(set(names)) != len(names):
            raise ValueError('surface-current factors need unique signal names')
        object.__setattr__(self, 'names', names)
        n = len(names)
        for key, shape in (('parts', (n+1,n,n)), ('current_integrals', (n+1,n)), ('C0',(n,n))):
            value = _readonly(getattr(self,key))
            if value.shape != shape:
                raise ValueError(f'{key} has incorrect shape')
            object.__setattr__(self,key,value)

    @property
    def total(self):
        return np.sum(self.parts, axis=0)

    @property
    def L_external(self):
        return mu_0*epsilon_0*np.linalg.inv(self.C0)

    @property
    def current_error(self):
        n = len(self.names)
        return float(np.max(abs(self.current_integrals-np.vstack((np.eye(n),-np.ones((1,n)))))))


def surface_current_factors(mesh, signals, ground):
    """Integrate PEC surface currents from a vacuum electrostatic basis.

    mesh is a dielectric-only P1 mesh. Every conductor node must lie on its
    own boundary edges; internal zero-thickness strips are rejected. Open
    boundaries are insulated in the electric dual problem. Uniform isotropic
    nonmagnetic exterior is assumed. Geometry and box errors require refinement.
    """
    if not signals:
        raise ValueError('at least one signal is required')
    n, count = mesh.num_nodes, len(signals)
    sets = [_node_set(name,nodes,n) for name,nodes in signals.items()]
    sets.append(_node_set('reference',ground,n))
    labels = np.full(n,-1,dtype=int)
    for label, nodes in enumerate(sets):
        if np.any(labels[nodes] >= 0):
            raise ValueError('conductor node sets overlap')
        labels[nodes] = label

    t = mesh.triangles
    all_edges = t[:,[[0,1],[1,2],[2,0]]].reshape(-1,2)
    _, first, multiplicity = np.unique(np.sort(all_edges,axis=1),axis=0,
                                      return_index=True,return_counts=True)
    if np.any(multiplicity > 2):
        raise ValueError('surface-current mesh must be manifold')
    exterior = first[multiplicity == 1]
    edges, owners = all_edges[exterior], exterior//3
    group = labels[edges[:,0]]
    is_metal = (group >= 0) & (group == labels[edges[:,1]])
    edges, owners, group = edges[is_metal], owners[is_metal], group[is_metal]
    for label, nodes in enumerate(sets):
        if not np.array_equal(np.unique(edges[group == label]),nodes):
            raise ValueError('every conductor must bound dielectric elements; zero-thickness internal strips are unsupported')

    k = assemble_stiffness(mesh, 1.0)
    v = []
    for excited in range(count):
        bc = {tuple(nodes):float(label == excited) for label,nodes in enumerate(sets)}
        v.append(solve_dirichlet(k,np.zeros(n),bc))
    v = np.stack(v,axis=1)
    c0 = epsilon_0*(v.T@(k@v))
    c0 = (c0+c0.T)/2
    inverse = np.linalg.inv(c0)

    p = mesh.nodes[t]
    determinant = ((p[:,1,0]-p[:,0,0])*(p[:,2,1]-p[:,0,1])
                   -(p[:,2,0]-p[:,0,0])*(p[:,1,1]-p[:,0,1]))
    if np.any(determinant <= 0):
        raise ValueError('surface-current mesh has nonpositive element area')
    gradients = np.stack((np.stack((p[:,1,1]-p[:,2,1],p[:,2,0]-p[:,1,0]),axis=1),
                          np.stack((p[:,2,1]-p[:,0,1],p[:,0,0]-p[:,2,0]),axis=1),
                          np.stack((p[:,0,1]-p[:,1,1],p[:,1,0]-p[:,0,0]),axis=1)),axis=1)
    gradients /= determinant[:,None,None]
    grad_v = np.einsum('tad,tan->tdn',gradients,v[t])
    tangent = mesh.nodes[edges[:,1]]-mesh.nodes[edges[:,0]]
    lengths = np.linalg.norm(tangent,axis=1)
    normal = np.column_stack((tangent[:,1],-tangent[:,0]))/lengths[:,None]
    derivative = np.einsum('ed,edn->en',normal,grad_v[owners])
    # Magnetic/electric duality: K_i = eps0 * d_n(V_basis) * inv(C0)[:,i].
    currents = epsilon_0*derivative@inverse
    parts, integrated = [], []
    for label in range(count+1):
        selected = group == label
        weights, values = lengths[selected], currents[selected]
        parts.append(values.T@(weights[:,None]*values))
        integrated.append(np.sum(weights[:,None]*values,axis=0))
    return SurfaceCurrentFactors(tuple(signals),parts,integrated,c0)


@dataclass(frozen=True)
class ConductorLoss:
    """Sampled R/internal L; roughness_factor is Re(Zrough)/Re(Zsmooth)."""
    frequency: np.ndarray
    R: np.ndarray
    L_internal: np.ndarray
    skin_depth: np.ndarray
    roughness_factor: np.ndarray
    factors: SurfaceCurrentFactors

    def __post_init__(self):
        f = _frequencies(self.frequency)
        n = len(self.factors.names)
        for key, shape in (('frequency',f.shape), ('skin_depth',f.shape),
                           ('roughness_factor',f.shape), ('R',(len(f),n,n)),
                           ('L_internal',(len(f),n,n))):
            value = _readonly(getattr(self,key))
            if value.shape != shape:
                raise ValueError(f'{key} has incorrect shape')
            object.__setattr__(self,key,value)

    def network(self, *, C, G, length, z_ref=50.0):
        """Combine matched-geometry dielectric C/G with this R and total L."""
        return rlgc_network(self.frequency,R=self.R,L=self.factors.L_external+self.L_internal,
                            C=C,G=G,length=length,z_ref=z_ref,names=self.factors.names)


def surface_conductor_loss(section, frequency, *, conductivity, ground_thickness,
                           relative_permeability=1.0, roughness_rms=0.0,
                           roughness=None, **mesh_options):
    """High-frequency loss for one common metal on all signal/reference surfaces.

    Require delta <= every trace's minimum thickness/face-width and reference
    thickness divided by five. The reference planes are represented by the
    section boundary; ground_thickness supplies their physical minimum thickness.
    That skin-depth gate is necessary, not a complete curvature/error bound.
    Integrated unit-current disagreement above 5% raises instead of returning
    an under-resolved surface-current result. R convergence is a separate check.
    """
    samples = _surface_samples(section, frequency, conductivity, ground_thickness,
                               relative_permeability, roughness_rms, roughness)
    return _surface_from_mesh(section.mesh(**mesh_options), *samples)


def _surface_samples(section, frequency, conductivity, ground_thickness,
                     relative_permeability, roughness_rms, roughness=None):
    """Validate all metal/geometry limits before meshing."""
    f, delta, correction, zs = _metal_samples(frequency,conductivity,relative_permeability,
                                            roughness_rms,roughness)
    ground_thickness = _scalar('ground_thickness',ground_thickness)
    minimum = min([ground_thickness,section.width] +
                  [min(t.thickness,t.width,t.top_width or t.width) for t in section.traces])
    if minimum <= 0 or np.max(delta) > minimum/5:
        raise ValueError('surface loss requires finite conductors and skin depth <= minimum conductor dimension / 5')
    return f, delta, correction, zs


def _surface_from_mesh(meshed, f, delta, correction, zs):
    """Internal composition on the same mesh as the dielectric solve."""
    factors = surface_current_factors(meshed.mesh,meshed.signals,meshed.ground)
    if factors.current_error > .05:
        raise ValueError(f'surface-current flux error {factors.current_error:.3%} exceeds 5%; refine the mesh')
    resistance = zs.real[:,None,None]*factors.total
    internal = (zs.imag/f/(2*np.pi))[:,None,None]*factors.total
    return ConductorLoss(f,resistance,internal,delta,correction,factors)
