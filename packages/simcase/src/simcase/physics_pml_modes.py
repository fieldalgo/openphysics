# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Open-boundary candidates; diagnostics never certify a physical resonance."""
import numpy as np
from galerkin import Mesh, EdgeSpace, eval_edge_field, assemble_mass, assemble_edge_mass
from galerkin.waveguide import solve_modes, assemble_mode_system
from galerkin.mode_coordinates import mode_coordinates, solve_scalar_coordinates, scalar_coordinate_system
from .fields import VectorField


class ModeSelectionError(ValueError):
    """No accepted candidates; inspect diagnostics for every searched candidate."""
    def __init__(self, message, diagnostics):
        super().__init__(message)
        self.diagnostics = diagnostics


def coordinates(mesh, pml, bend=None):
    bend = bend or {}
    return mode_coordinates(mesh, thickness=pml['thickness'], strength=pml.get('strength',3.),
                            order=pml.get('order',2), bend_radius=bend.get('radius'),
                            bend_axis=bend.get('axis','x'), bend_origin=bend.get('origin',0.))


def solve(mesh, eps, wavelength, boundary, num_modes, formulation, n_target, pml, bend):
    if n_target is None:
        raise ValueError('PML modes require explicit positive n_target')
    from .pml_contract import validate
    lo, hi = mesh.nodes.min(axis=0), mesh.nodes.max(axis=0)
    settings = dict(pml=pml, n_target=n_target, boundary=boundary)
    if bend is not None: settings["bend"] = bend
    validate(settings, dict(xmin=lo[0], xmax=hi[0], ymin=lo[1], ymax=hi[1]), "modes", ValueError)
    c=coordinates(mesh,pml,bend)
    # Scale coordinates, keeping the dimensionless Jacobian unchanged.
    scaled=Mesh(mesh.nodes/wavelength,mesh.triangles.copy(),mesh.boundary,mesh.boundary_edges)
    k0=2*np.pi
    sides=[s for s,v in boundary.items() if v=='pec']
    for side,width in pml['thickness'].items():
        if width>0 and boundary.get(side)!='pec':
            raise ValueError('PML outer faces must use PEC truncation')
    fixed=np.unique(np.concatenate([mesh.boundary[s] for s in sides])) if sides else np.zeros(0,int)
    search=max(2*num_modes,6)
    if formulation=='vector':
        space=EdgeSpace(scaled)
        ids={tuple(e):i for i,e in enumerate(space.edges)}
        edges=np.unique([ids[tuple(sorted(e))] for s in sides for e in mesh.boundary_edges[s]]).astype(int)
        free=np.setdiff1d(np.arange(space.num_edges+mesh.num_nodes),np.r_[edges,space.num_edges+fixed])
        search=min(search,len(free)-2)
        if search<1: raise ValueError('mesh has too few free degrees of freedom')
        n,space,et,ez=solve_modes(scaled,eps,k0,n_target,search,pec_nodes=fixed,pec_edges=edges,coordinate_factors=c.factors)
        a,b,_=assemble_mode_system(scaled,eps,k0,space=space,coordinate_factors=c.factors)
        x=np.concatenate([et*(k0*n[:,None]),ez],axis=1).T
        # Computational components in PML are artificial; the real-window
        # longitudinal field is physical Ez. All arrays retain complex phase.
        longitudinal=1j*ez.T/c.node_h[:,None]
        electric=np.stack([np.column_stack([eval_edge_field(space,t)/c.factors[:,:2],
                         1j*z[mesh.triangles].mean(axis=1)/c.factors[:,2]]) for t,z in zip(et,ez)],axis=1)
        me=assemble_edge_mass(space)
        mp=assemble_edge_mass(space,c.physical.astype(float))
        mn=assemble_mass(scaled)
        mnp=assemble_mass(scaled,c.physical.astype(float))
        # Positive L2 of computational transverse and interpolated physical Ez.
        # On the physical window sx=sy=1. PML contribution is only a diagnostic.
        total=np.sum(et.conj()*(me@et.T).T,axis=1).real+np.sum(longitudinal.conj()*(mn@longitudinal),axis=0).real
        physical=np.sum(et.conj()*(mp@et.T).T,axis=1).real+np.sum(longitudinal.conj()*(mnp@longitudinal),axis=0).real
        sign=1
    else:
        n,field=solve_scalar_coordinates(scaled,eps,k0,n_target,c.factors,num_modes=search,fixed_nodes=fixed)
        a,b=scalar_coordinate_system(scaled,eps,k0,c.factors)
        x=field
        free=np.setdiff1d(np.arange(mesh.num_nodes),fixed)
        mn=assemble_mass(scaled)
        mnp=assemble_mass(scaled,c.physical.astype(float))
        total=np.sum(field.conj()*(mn@field),axis=0).real
        physical=np.sum(field.conj()*(mnp@field),axis=0).real
        sign=-1
    af,bf=a[free][:,free],b[free][:,free]
    ax,bx=af@x[free],bf@x[free]
    beta2=(k0*n)**2
    residual=np.linalg.norm(ax+sign*bx*beta2,axis=0)/(np.linalg.norm(ax,axis=0)+abs(beta2)*np.linalg.norm(bx,axis=0))
    fraction=np.divide(physical,total,out=np.zeros_like(physical),where=total>0)
    threshold=pml.get('min_physical_fraction',.1)
    if not np.isfinite(threshold) or not 0<=threshold<=1:
        raise ValueError('min_physical_fraction must lie in [0,1]')
    records=[]
    acceptable=[]
    for i,value in enumerate(n):
        reasons=[]
        if not np.isfinite(value) or value.real<=0: reasons.append('not_finite_forward')
        if not np.isfinite(residual[i]) or residual[i]>1e-8: reasons.append('pencil_residual')
        if not np.isfinite(fraction[i]) or fraction[i]<threshold: reasons.append('low_physical_l2_fraction')
        if value.imag>1e-10*max(1.,abs(value.real)): reasons.append('positive_imaginary_index')
        if not reasons: acceptable.append(i)
        records.append(dict(candidate=i+1,neff_real=float(value.real),neff_imag=float(value.imag),
                            pencil_residual=float(residual[i]),physical_l2_fraction=float(fraction[i]),
                            pml_l2_fraction=float(1-fraction[i]),reasons=reasons,selected=False,
                            attenuation_status='numerically_unresolved' if abs(value.imag)<=1e-10*max(1.,abs(value.real)) else 'resolved_sign'))
    keep=np.array(sorted(acceptable,key=lambda i:abs(n[i]-n_target))[:num_modes],dtype=int)
    keep=keep[np.argsort(-n[keep].real)]
    for i in acceptable:
        records[i]['selected']=bool(i in keep)
        records[i]['reasons']=['selected_near_target' if i in keep else 'outside_requested_count']
    diagnostics=dict(schema='openphysics.pml-candidates/1',candidates=records,
                     selected_candidates=(keep+1).tolist(),min_physical_fraction=float(threshold),
                     residual_limit=1e-8,stability='not_checked',classification='heuristic_candidates',
                     physical_bounds=c.physical_bounds.tolist(),normalization_region='physical',
                     fraction_metric='positive_computational_transverse_and_interpolated_physical_longitudinal_l2')
    diagnostics.update(requested_modes=num_modes, returned_modes=len(keep))
    if not len(keep):
        raise ModeSelectionError(f'PML search accepted {len(keep)} of {num_modes} requested modes; inspect diagnostics, target and physical fraction threshold',diagnostics)
    result=dict(neff=n[keep],guided=np.zeros(len(keep),bool),open_boundary=diagnostics)
    if formulation=='vector':
        norm=np.linalg.norm(electric[c.physical][:,keep],axis=2).max(axis=0)
        if not np.isfinite(norm).all() or np.any(norm==0): raise ModeSelectionError('zero or nonfinite physical field',diagnostics)
        result['vector_field']=VectorField(space.edges.copy(),et[keep].T*wavelength/norm,
                                          longitudinal[:,keep]/norm,electric[:,keep]/norm[None,:,None],
                                          normalization="physical_max_centroid_magnitude")
    else:
        chosen=field[:,keep].copy()
        indices=np.flatnonzero(c.physical_nodes)
        pivot=indices[np.argmax(abs(chosen[indices]),axis=0)]
        chosen/=chosen[pivot,np.arange(len(keep))]
        result['fields']=chosen
    return result
