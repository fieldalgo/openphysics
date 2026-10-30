# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Longitudinal magnetoquasistatic current diffusion in meshed metal volumes.

P1 Az and one longitudinal electric-field constant per conductor group solve
the diffusion equation and prescribed net-current constraints. The exterior
magnetic boundary is finite and explicit; displacement current and radiation
are absent. exp(+j omega t), SI and per-unit-length quantities throughout.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
from scipy.constants import epsilon_0, mu_0
from scipy.sparse.linalg import splu

from galerkin import assemble_load, assemble_mass, assemble_stiffness
from .network import _frequencies, _scalar, rlgc_network

__all__ = ['ConductorDiffusion', 'conductor_impedance']


def _indices(name, values, size):
    raw = np.asarray(values)
    if (raw.ndim != 1 or raw.dtype.kind not in 'iu' or not raw.size
            or any(isinstance(x,(bool,np.bool_)) for x in np.asarray(values,dtype=object).flat)):
        raise ValueError(f'{name} must be a nonempty integer index array')
    if np.any(raw < 0) or np.any(raw >= size) or np.unique(raw).size != raw.size:
        raise ValueError(f'{name} indices must be unique and inside the mesh')
    return raw.astype(int,copy=True)


def _snapshot(value, dtype=None):
    if value is None:
        return None
    result = np.array(value,dtype=dtype,copy=True)
    result.setflags(write=False)
    return result


@dataclass(frozen=True)
class ConductorDiffusion:
    """Series Z/R/total L and conservation diagnostics for unit port currents.

    Group order is signal names, then the common reference group. Each column
    excites +1 A in one signal and -1 A in the reference. Optional retained Az
    is (F,nodes,N); Jz is the element-centre value (F,triangles,N), not an exact
    peak or a piecewise-constant approximation used by the solver.
    """
    frequency: np.ndarray
    names: tuple[str,...]
    Z: np.ndarray
    L: np.ndarray
    voltage_gradient: np.ndarray
    current_integrals: np.ndarray
    skin_depth: np.ndarray
    max_edge_over_skin_depth: np.ndarray
    current_error: np.ndarray
    power_error: np.ndarray
    magnetic_energy_error: np.ndarray
    vector_potential: np.ndarray | None = None
    current_density: np.ndarray | None = None

    def __post_init__(self):
        object.__setattr__(self,'names',tuple(self.names))
        for name in self.__dataclass_fields__:
            if name != 'names':
                object.__setattr__(self,name,_snapshot(getattr(self,name)))

    @property
    def R(self):
        return self.Z.real

    def network(self, *, C, G, length, z_ref=50.0):
        """Propagate with matched-geometry dielectric C/G; L already includes metal."""
        return rlgc_network(self.frequency,R=self.R,L=self.L,C=C,G=G,
                            length=length,z_ref=z_ref,names=self.names)


def conductor_impedance(mesh, frequency, *, signals, ground, conductivity,
                        magnetic_boundary, relative_permeability=1.0, keep_fields=False):
    """Extract series impedance by solving inside and outside finite conductors.

    signals maps names to metal TRIANGLE indices; ground is another triangle
    set, whose connected or disconnected pieces share one longitudinal field.
    These are volume regions, not the node sets of a dielectric-only section.
    conductivity is common to all metals; permeability is uniform everywhere.
    magnetic_boundary explicitly fixes Az=0 on exterior NODES. Other exterior
    edges have zero natural magnetic flux. Compare outer-boundary refinements.

    At positive f, require good-conductor sigma/(omega*eps0)>=1000 and every
    metal triangle edge <= the skin depth. This necessary resolution gate is
    not an accuracy certificate; refine the mesh and the magnetic domain.
    """
    f = _frequencies(frequency)
    sigma = _scalar('conductivity',conductivity)
    mu_r = _scalar('relative_permeability',relative_permeability)
    if type(keep_fields) is not bool:
        raise ValueError('keep_fields must be boolean')
    if (not isinstance(signals,Mapping) or not signals
            or any(not isinstance(name,str) or not name.strip() or '\n' in name or '\r' in name
                   for name in signals)):
        raise ValueError('signals must map nonempty single-line names to metal triangles')
    mu = mu_0*mu_r
    if (not np.isfinite(mu) or mu < 1/np.finfo(float).max
            or f[-1] > np.finfo(float).max/(2*np.pi)):
        raise ValueError('frequency or permeability is outside the representable range')
    t, nodes = mesh.triangles, mesh.nodes
    if not np.all(np.isfinite(nodes)):
        raise ValueError('mesh nodes must be finite')
    sets = [_indices(name,values,mesh.num_triangles) for name,values in signals.items()]
    sets.append(_indices('ground',ground,mesh.num_triangles))
    labels = np.full(mesh.num_triangles,-1,dtype=int)
    used_nodes = np.zeros(mesh.num_nodes,dtype=bool)
    for group,indices in enumerate(sets):
        if np.any(labels[indices] != -1):
            raise ValueError('metal triangle groups must not overlap')
        labels[indices] = group
        conductor_nodes = np.unique(t[indices])
        if np.any(used_nodes[conductor_nodes]):
            raise ValueError('distinct metal groups must not touch at nodes or edges')
        used_nodes[conductor_nodes] = True
    fixed = _indices('magnetic_boundary',magnetic_boundary,mesh.num_nodes)
    all_edges = np.sort(t[:,[[0,1],[1,2],[2,0]]].reshape(-1,2),axis=1)
    edges,counts = np.unique(all_edges,axis=0,return_counts=True)
    if np.any(counts > 2) or not np.all(np.isin(fixed,np.unique(edges[counts == 1]))):
        raise ValueError('magnetic boundary must lie on a manifold exterior mesh boundary')
    p = nodes[t]
    a,b = p[:,1]-p[:,0],p[:,2]-p[:,0]
    areas = (a[:,0]*b[:,1]-a[:,1]*b[:,0])/2
    if np.any(areas <= 0) or not np.all(np.isfinite(areas)):
        raise ValueError('mesh must have positive finite triangle areas')
    metal = labels >= 0
    longest = max(np.max(np.linalg.norm(p[metal,i]-p[metal,j],axis=1))
                  for i,j in ((0,1),(1,2),(2,0)))
    skin = np.full(len(f),np.inf)
    positive = f > 0
    if np.any(np.log(sigma)-np.log(2*np.pi*epsilon_0)-np.log(f[positive]) < np.log(1000)):
        raise ValueError('current diffusion requires sigma/(omega*eps0) >= 1000')
    skin[positive] = np.exp(-.5*(np.log(np.pi)+np.log(f[positive])+np.log(mu)+np.log(sigma)))
    ratio = longest/skin
    if np.any(ratio > 1):
        raise ValueError('metal mesh edge exceeds skin depth; refine the metal volume mesh')

    # Q[:,g] = integral sigma*chi_g*phi, D[g,g] = sigma*metal area.
    coefficients = np.where(metal,sigma,0)
    q = np.column_stack([assemble_load(mesh,np.where(labels == group,sigma,0))
                         for group in range(len(sets))])
    d = sigma*np.array([areas[indices].sum() for indices in sets])
    free = np.setdiff1d(np.arange(mesh.num_nodes),fixed)
    if not len(free) or not np.all(np.isfinite(d)) or np.any(d <= 0):
        raise ValueError('invalid conductor conductance or no free magnetic nodes')
    k = assemble_stiffness(mesh,1/mu)[free][:,free].tocsc()
    m = assemble_mass(mesh,coefficients)[free][:,free].tocsc()
    q = q[free]
    n = len(signals)
    prescribed = np.vstack((np.eye(n),-np.ones((1,n))))
    impedances,inductances,gradients,currents = [],[],[],[]
    current_errors,power_errors,energy_errors,fields,densities = [],[],[],[],[]
    for frequency_hz in f:
        omega = 2*np.pi*frequency_hz
        if omega == 0:
            e = prescribed/d[:,None]
            az = splu(k).solve(q@e)
            z = prescribed.T@e
        else:
            with np.errstate(over='ignore',invalid='ignore'):
                operator = k+1j*omega*m
            if not np.all(np.isfinite(operator.data)):
                raise ValueError('current-diffusion operator cannot be represented')
            basis = splu(operator).solve(q.astype(complex))
            admittance = np.diag(d)-1j*omega*(q.T@basis)
            e = np.linalg.solve(admittance,prescribed)
            az = basis@e
            z = prescribed.T@e
        actual = d[:,None]*e-1j*omega*(q.T@az)
        magnetic_energy = az.conj().T@(k@az)
        # Integrate the actual local field with the consistent P1 mass form.
        # Expanding into global E/A cross terms loses digits under strong skin
        # shielding, where E-j*omega*A is much smaller than either term.
        full = np.zeros((mesh.num_nodes,n),dtype=complex)
        full[free] = az
        electric = e[labels[metal],None,:]-1j*omega*full[t[metal]]
        weights = sigma*areas[metal]/12
        sums = electric.sum(axis=1)
        joule = (np.einsum('tan,tam,t->nm',electric.conj(),electric,weights)
                 + sums.conj().T@(weights[:,None]*sums))
        inductance = magnetic_energy.real if omega == 0 else z.imag/omega
        residual_i = float(np.max(abs(actual-prescribed)))
        residual_p = float(np.max(abs(joule-(z+z.conj().T)/2))/np.max(abs(z.real)))
        residual_l = float(np.max(abs(magnetic_energy-inductance))/np.max(abs(inductance)))
        symmetry = float(np.max(abs(z-z.T))/np.max(abs(z)))
        if (not np.all(np.isfinite(z)) or not np.all(np.isfinite(inductance))
                or not np.all(np.isfinite([residual_i,residual_p,residual_l,symmetry]))
                or residual_i > 1e-10 or residual_p > 1e-9 or residual_l > 1e-9
                or symmetry > 1e-10):
            raise ValueError('current-diffusion solve failed conservation or reciprocity checks')
        impedances.append((z+z.T)/2)
        inductances.append((inductance+inductance.T)/2)
        gradients.append(e)
        currents.append(actual)
        current_errors.append(residual_i)
        power_errors.append(residual_p)
        energy_errors.append(residual_l)
        if keep_fields:
            current = np.zeros((mesh.num_triangles,n),dtype=complex)
            current[metal] = sigma*electric.mean(axis=1)
            fields.append(full)
            densities.append(current)
    return ConductorDiffusion(f,tuple(signals),np.asarray(impedances,dtype=complex),
        inductances,gradients,currents,skin,ratio,current_errors,power_errors,energy_errors,
        fields if keep_fields else None,densities if keep_fields else None)
