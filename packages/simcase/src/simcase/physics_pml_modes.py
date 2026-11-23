# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Open-boundary candidates; diagnostics never certify a physical resonance."""
import numpy as np
from galerkin import Mesh, EdgeSpace
from galerkin.kernels import (assemble_edge_mass, assemble_mass, assemble_mode_system, eval_edge_field,
                              mode_coordinates, scalar_coordinate_system, solve_modes, solve_scalar_coordinates)
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


def search_count(pml, num_modes):
    """The candidates searched before the filter: ``pml['search_count']`` when given, else
    max(2 num_modes, 6) (the count before the setting existed)."""
    return int(pml['search_count']) if 'search_count' in pml else max(2*num_modes,6)


#: the rule that makes a candidate of a later search a duplicate of an earlier one (pml.additional_searches)
DUPLICATE_RULE = {"effective_index_distance": 1e-9, "field_overlap": 0.99,
                  "overlap_metric": "computational_transverse_electric_l2", "degenerate_span": 0.99}


def transverse_gram(mesh, edges, et):
    """The Hermitian Gram matrix <a, b> of the candidates' transverse edge coefficients ``et`` (m, E)
    with the edge mass matrix of the whole computational ``mesh``: the transverse part of
    subspace_tracking's electric L2 product (its longitudinal part is left out)."""
    from .subspace_tracking import ElectricMetric
    field = VectorField(edges, et.T, np.zeros((mesh.num_nodes, len(et)), complex),
                        np.zeros((0, len(et), 3), complex))
    return ElectricMetric(mesh).product(field, field)


def _merge(records, acceptable, n, gram, origin, num_modes):
    """Mark the duplicates of a merged search and select the eligible ones by descending Re n_eff.

    Candidate b of a later search is a duplicate of an earlier kept candidate a (one of an earlier
    search, itself no duplicate, eligible or not) when |n_b - n_a| <= 1e-9 max(1, |n_a|) and
    eta_w(a, b) = |<a, b>| / (||a|| ||b||) >= 0.99, the inner product of the transverse edge
    coefficients with the edge mass matrix of the whole computational mesh. When several earlier
    candidates lie within the index tolerance, b is a duplicate when its projection on their span
    holds at least 0.99 of its squared norm, h^H G^-1 h = ||L^-1 h||^2 with G = L L^H (``gram`` is
    ``transverse_gram``); when their Gram matrix is not positive definite the single overlap decides.
    Returns the selected indices (descending Re n_eff)."""
    from scipy.linalg import cholesky, solve_triangular
    norms=np.sqrt(np.maximum(np.diag(gram).real,0.))
    duplicate=np.zeros(len(n),bool)
    for j in range(len(n)):
        if origin[j]==1: continue
        near=[i for i in range(j) if origin[i]<origin[j] and not duplicate[i]
              and abs(n[j]-n[i])<=DUPLICATE_RULE['effective_index_distance']*max(1.,abs(n[i]))]
        if not near or norms[j]==0: continue
        overlap=np.array([abs(gram[i,j])/(norms[i]*norms[j]) if norms[i]>0 else 0. for i in near])
        best=int(np.argmax(overlap))
        span=len(near)>1
        if span:
            try:
                projected=solve_triangular(cholesky(gram[np.ix_(near,near)],lower=True),gram[near,j],lower=True)
            except np.linalg.LinAlgError:
                span=False              # earlier candidates not independent: the single overlap decides
        if span:
            fraction=float(np.sum(abs(projected)**2)/gram[j,j].real)
            found=fraction>=DUPLICATE_RULE['degenerate_span']
            measure=float(np.sqrt(max(fraction,0.)))
        else:
            found=overlap[best]>=DUPLICATE_RULE['field_overlap']
            measure=float(overlap[best])
        if not found: continue
        duplicate[j]=True
        a=near[best]
        records[j].update(duplicate_of=a+1,duplicate_effective_index_distance=float(abs(n[j]-n[a])),
                          duplicate_field_overlap=measure)
        if span: records[j]['duplicate_span']=[i+1 for i in near]
        records[j]['reasons']=records[j]['reasons']+['duplicate_candidate']
    eligible=[i for i in acceptable if not duplicate[i]]
    keep=np.array(sorted(eligible,key=lambda i:(-n[i].real,i))[:num_modes],dtype=int)
    for i in eligible:
        records[i]['selected']=bool(i in keep)
        records[i]['reasons']=['selected_descending_real_index' if i in keep else 'outside_requested_count']
    for i,record in enumerate(records):
        records[i]=dict(candidate=record.pop('candidate'),search=int(origin[i]),**record)
    return keep


def solve(mesh, eps, wavelength, boundary, num_modes, formulation, n_target, pml, bend, motion=None):
    """With ``motion`` (a galerkin MeshMotion of the nodes in the mesh's unit; internal:
    simcase.shape_derivative), the modes are chosen from the numbers on the moved mesh exactly as
    without it, and the kept modes' ``neff`` is returned live in the library of ``motion.t``: the
    same eigensolve with the layer's factors of the moved mesh held fixed (galerkin requires the
    motion to leave every stretched element in place)."""
    if motion is not None:
        return _solve_moving(mesh, eps, wavelength, boundary, num_modes, formulation, n_target, pml, bend, motion)
    if n_target is None:
        raise ValueError('PML modes require explicit positive n_target')
    from .pml_contract import validate
    lo, hi = mesh.nodes.min(axis=0), mesh.nodes.max(axis=0)
    settings = dict(pml=pml, n_target=n_target, boundary=boundary, num_modes=num_modes, formulation=formulation)
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
    search=search_count(pml,num_modes)
    extra=pml.get('additional_searches') or []
    if formulation=='vector':
        space=EdgeSpace(scaled)
        ids={tuple(e):i for i,e in enumerate(space.edges)}
        edges=np.unique([ids[tuple(sorted(e))] for s in sides for e in mesh.boundary_edges[s]]).astype(int)
        free=np.setdiff1d(np.arange(space.num_edges+mesh.num_nodes),np.r_[edges,space.num_edges+fixed])
        search=min(search,len(free)-2)
        if search<1: raise ValueError('mesh has too few free degrees of freedom')
        n,space,et,ez=solve_modes(scaled,eps,k0,n_target,search,pec_nodes=fixed,pec_edges=edges,coordinate_factors=c.factors)
        searches=[dict(search=1,n_target=float(n_target),search_count=int(search),candidate_count=len(n))]
        origin=np.ones(len(n),int)
        for k,further in enumerate(extra,start=2):
            # the same mesh and pencil, one factorization per target; candidates numbered in order
            count=min(int(further['search_count']),len(free)-2)
            nk,_,etk,ezk=solve_modes(scaled,eps,k0,further['n_target'],count,pec_nodes=fixed,pec_edges=edges,
                                     coordinate_factors=c.factors)
            searches.append(dict(search=k,n_target=float(further['n_target']),search_count=count,candidate_count=len(nk)))
            n,et,ez=np.concatenate([n,nk]),np.concatenate([et,etk]),np.concatenate([ez,ezk])
            origin=np.concatenate([origin,np.full(len(nk),k)])
        a,b,_=assemble_mode_system(scaled,eps,k0,space=space,coordinate_factors=c.factors)
        x=np.concatenate([et*(k0*n[:,None]),ez],axis=1).T
        # Computational components in PML are artificial; the real-window
        # longitudinal field is physical Ez. All arrays retain complex phase.
        longitudinal=1j*ez.T/c.node_h[:,None]
        # A search of only static beta^2 = 0 roots returns none; selection then refuses.
        electric=np.stack([np.column_stack([eval_edge_field(space,t)/c.factors[:,:2],
                         1j*z[mesh.triangles].mean(axis=1)/c.factors[:,2]]) for t,z in zip(et,ez)],axis=1) \
            if len(n) else np.zeros((mesh.num_triangles,0,3),complex)
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
    if extra:
        keep=_merge(records,acceptable,n,transverse_gram(scaled,space.edges,et),origin,num_modes)
    else:
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
    if extra:
        diagnostics.update(searches=searches,selection='descending_real_index',duplicate_rule=dict(DUPLICATE_RULE))
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
        peak = chosen[pivot,np.arange(len(keep))]
        if not np.isfinite(peak).all() or np.any(peak == 0):
            raise ModeSelectionError('zero or nonfinite physical field', diagnostics)
        chosen /= peak
        result['fields']=chosen
    return result


def _solve_moving(mesh, eps, wavelength, boundary, num_modes, formulation, n_target, pml, bend, motion):
    from galerkin.shape import MeshMotion, motion_step

    from .physics_em_modes2d import _numbers
    if pml.get('additional_searches'):
        raise ValueError("a mesh motion is refused with pml additional_searches: one target is searched")
    if bend is not None:
        raise ValueError("a mesh motion is refused with a bend: its coordinate factor depends on every node position")
    if formulation != "vector":
        raise ValueError("a mesh motion takes the vector formulation")
    moved = motion_step(mesh, motion).moved
    numbers = solve(moved, eps, wavelength, boundary, num_modes, formulation, n_target, pml, None)
    c = coordinates(moved, pml)
    scaled = Mesh(mesh.nodes / wavelength, mesh.triangles.copy(), mesh.boundary, mesh.boundary_edges)
    sides = [s for s, v in boundary.items() if v == 'pec']
    fixed = np.unique(np.concatenate([mesh.boundary[s] for s in sides])) if sides else np.zeros(0, int)
    space = EdgeSpace(scaled)
    ids = {tuple(e): i for i, e in enumerate(space.edges)}
    edges = np.unique([ids[tuple(sorted(e))] for s in sides for e in mesh.boundary_edges[s]]).astype(int)
    free = np.setdiff1d(np.arange(space.num_edges + mesh.num_nodes), np.r_[edges, space.num_edges + fixed])
    search = min(search_count(pml, num_modes), len(free) - 2)
    scaled_motion = MeshMotion(design_velocity=np.asarray(motion.design_velocity, dtype=float) / wavelength,
                               t=motion.t)
    live, *_ = solve_modes(scaled, eps, 2 * np.pi, n_target, search, pec_nodes=fixed, pec_edges=edges,
                           coordinate_factors=c.factors, motion=scaled_motion)
    values = _numbers(live)
    picks = []
    for value in numbers['neff']:
        j = int(np.argmin(np.abs(values - value)))
        if abs(values[j] - value) > 1e-12 * max(1.0, abs(value)):
            raise ValueError("the moving-mesh PML solve did not reproduce a selected mode (a defect of simcase, "
                             "please report it)")
        picks.append(j)
    return {"neff": live[np.asarray(picks)], "guided": numbers['guided'], "open_boundary": numbers['open_boundary']}
