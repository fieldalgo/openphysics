# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent mathematical oracle; no production or existing refsol imports.

Stage 1 uses analytic nodal samples, never a producer result or a FEM solve.
Coordinates m; T K; k W/(m K); Q W/m^3; flux W/m^2; nodal heat W/m.
"""
import numpy as np

L, H, K, SOURCE, LEFT, RIGHT = .03, .02, 12.5, 1e5, 280., 315.
LENGTH_FACTORS = {'m': 1., 'mm': 1e-3, 'um': 1e-6}
FORMAT = 'thermal.steady2d-result-v1'
LAYOUT = 'thermal2d-p1-node-cell-v1'
UNITS = {'nodes_m': 'm', 'triangles': '1', 'temperature_k': 'K',
         'heat_flux_w_m2': 'W/m^2', 'load_w_per_m': 'W/m',
         'reaction_w_per_m': 'W/m', 'residual_w_per_m': 'W/m',
         'dirichlet_node_ids': '1', 'dirichlet_temperature_k': 'K'}

LOCATIONS = {key: ('cell' if key in ('triangles','heat_flux_w_m2') else 'prescribed_node' if key.startswith('dirichlet_') else 'node') for key in UNITS}


def rectangle(n, unit='m', origin=(.007, -.004)):
    """Direct SI conversion of translated document coordinates, no Scale helper."""
    factor = LENGTH_FACTORS[unit]
    bounds = np.array([origin[0], origin[0]+L, origin[1], origin[1]+H])/factor
    physical = bounds*factor
    x = np.linspace(physical[0], physical[1], n+1)
    y = np.linspace(physical[2], physical[3], n+1)
    xx, yy = np.meshgrid(x, y)
    nodes = np.column_stack([xx.ravel(), yy.ravel()])
    ids = np.arange((n+1)**2).reshape(n+1, n+1)
    a, b, c, d = ids[:-1, :-1], ids[:-1, 1:], ids[1:, :-1], ids[1:, 1:]
    triangles = np.stack([np.stack([a,b,d],axis=-1), np.stack([a,d,c],axis=-1)],axis=-2).reshape(-1,3)
    tags = {'left': ids[:,0], 'right': ids[:,-1], 'bottom': ids[0], 'top': ids[-1]}
    return nodes, triangles, tags


def closed_form(points, source=SOURCE, origin_x=.007):
    x = np.asarray(points)[...,0]-origin_x
    temperature = LEFT+(RIGHT-LEFT)*x/L+source*x*(L-x)/(2*K)
    gradient = np.zeros((*x.shape, 2))
    gradient[...,0] = (RIGHT-LEFT)/L+source*(L-2*x)/(2*K)
    return temperature, -K*gradient


def continuous_heat(source=SOURCE):
    """Outward left/right heat obtained from q dot n boundary integration."""
    left = K*(RIGHT-LEFT)*H/L+source*L*H/2
    right = -K*(RIGHT-LEFT)*H/L+source*L*H/2
    return np.array([left, right]), source*L*H


def prescribed_nodes(tags, temperatures):
    values, owners = {}, {}
    for tag, temperature in temperatures.items():
        if tag not in tags or len(tags[tag]) == 0:
            raise ValueError(f'unknown or empty boundary tag: {tag}')
        if isinstance(temperature, (bool, np.bool_)) or not np.isscalar(temperature) or not np.isfinite(temperature) or temperature < 0:
            raise ValueError('absolute Kelvin must be finite nonnegative real, not bool')
        for node in tags[tag]:
            i = int(node)
            if i in values and values[i] != temperature:
                raise ValueError(f'conflict node {i}: {owners[i]} and {tag}')
            values[i], owners[i] = float(temperature), tag
    ids = np.array(sorted(values), dtype=np.int64)
    return ids, np.array([values[i] for i in ids])


def geometry(nodes, triangles):
    p = nodes[triangles]
    # [1,x,y] coefficient inversion is independent of any production B/mesh helper.
    coefficients = np.linalg.inv(np.concatenate([np.ones((*p.shape[:2],1)),p],axis=-1))
    gradients = coefficients[:,1:,:].swapaxes(1,2)
    edges = p[:,1:]-p[:,:1]
    area = np.linalg.det(edges)/2
    if np.any(area <= 0):
        raise ValueError('require positive CCW triangle area')
    return area, gradients


def original_system(nodes, triangles, source=SOURCE):
    """Return original uneliminated K as additive COO entries, plus consistent f."""
    area, gradients = geometry(nodes, triangles)
    local = K*area[:,None,None]*np.einsum('tik,tjk->tij',gradients,gradients)
    rows = np.repeat(triangles,3,axis=1).ravel()
    cols = np.tile(triangles,(1,3)).ravel()
    load = np.zeros(len(nodes))
    np.add.at(load,triangles.ravel(),np.repeat(source*area/3,3))
    return rows, cols, local.ravel(), load


def action(rows, cols, entries, vector):
    out = np.zeros(len(vector))
    np.add.at(out, rows, entries*vector[cols])
    return out


def analytic_sample(n=8, unit='m', source=SOURCE):
    """Synthetic analytic nodal P1 arrays, NOT output of a thermal runner."""
    nodes, triangles, tags = rectangle(n, unit)
    temperature, _ = closed_form(nodes, source)
    area, gradients = geometry(nodes, triangles)
    flux = -K*np.einsum('ti,tij->tj',temperature[triangles]-LEFT,gradients)
    rows,cols,entries,load = original_system(nodes,triangles,source)
    # Constant-offset evaluation preserves derivative accuracy at absolute Kelvin.
    residual = action(rows,cols,entries,temperature-LEFT)-load
    ids, values = prescribed_nodes(tags,{'left':LEFT,'right':RIGHT})
    reaction = np.zeros(len(nodes));reaction[ids] = residual[ids]
    return dict(nodes_m=nodes, triangles=triangles, temperature_k=temperature,
                heat_flux_w_m2=flux, load_w_per_m=load,
                reaction_w_per_m=reaction,residual_w_per_m=residual,
                dirichlet_node_ids=ids,dirichlet_temperature_k=values)


def interpolation_errors(n, order=6):
    """Analytic interpolation convergence only; does not imply a FEM solve ran."""
    raw = analytic_sample(n)
    nodes, tri = raw['nodes_m'],raw['triangles']
    z,w = np.polynomial.legendre.leggauss(order);z=(z+1)/2;w=w/2
    r,s=np.meshgrid(z,z,indexing='ij');wr,ws=np.meshgrid(w,w,indexing='ij')
    bary=np.stack([(1-r)*(1-s),r*(1-s),s],axis=-1).reshape(-1,3)
    weights=(2*wr*ws*(1-s)).ravel()
    points=np.einsum('qa,tad->tqd',bary,nodes[tri])
    exact_t,exact_q=closed_form(points)
    th=np.einsum('qa,ta->tq',bary,raw['temperature_k'][tri])
    area,_=geometry(nodes,tri)
    dt=(th-exact_t)/(RIGHT-LEFT)
    dq=(raw['heat_flux_w_m2'][:,None]-exact_q)/(K*(RIGHT-LEFT)/L)
    return np.array([np.sqrt(np.sum(area[:,None]*weights*dt**2)/(L*H)),
                     np.sqrt(np.sum(area[:,None]*weights*np.sum(dq*dq,axis=-1))/(L*H))])


def document(n=8, unit='mm', source=SOURCE, fields=True):
    factor=LENGTH_FACTORS[unit]
    return {'openphysics':'0.2','name':'Independent translated heat fixture',
            'units':{'length':unit,'temperature':'K'},
            'geometry':{'domain':{'xmin':.007/factor,'xmax':.037/factor,
                                  'ymin':-.004/factor,'ymax':.016/factor}},
            'materials':{},'physics':{'independent_heat':{'type':'thermal.steady2d',
            'conductivity_w_mk':K,'heat_source_w_m3':source,
            'dirichlet_temperature_k':{'left':LEFT,'right':RIGHT}}},
            'mesh':{'subdivisions':[n,n]},'study':{'type':'single'},
            'results':{'save_fields':fields,'plots':False}}


def result_arrays(result):
    names={'nodes_m':'mesh_nodes_m','triangles':'mesh_triangles'}
    return {key:np.asarray(getattr(result,names.get(key,key))) for key in UNITS}


def errors_from_actual(raw,order=6):
    z,w=np.polynomial.legendre.leggauss(order);z=(z+1)/2;w=w/2
    r,s=np.meshgrid(z,z,indexing='ij');wr,ws=np.meshgrid(w,w,indexing='ij')
    bary=np.stack([(1-r)*(1-s),r*(1-s),s],axis=-1).reshape(-1,3)
    weights=(2*wr*ws*(1-s)).ravel()
    tri=raw['triangles'];points=np.einsum('qa,tad->tqd',bary,raw['nodes_m'][tri])
    exact_t,exact_q=closed_form(points)
    th=np.einsum('qa,ta->tq',bary,raw['temperature_k'][tri])
    area,_=geometry(raw['nodes_m'],tri)
    dt=(th-exact_t)/35;dq=(raw['heat_flux_w_m2'][:,None]-exact_q)/(K*35/L)
    return np.array([np.sqrt(np.sum(area[:,None]*weights*dt**2)/(L*H)),
                     np.sqrt(np.sum(area[:,None]*weights*np.sum(dq*dq,axis=-1))/(L*H))])


def validate_actual_raw(raw,source=SOURCE):
    """Independent physical assertions, never producer summary-derived answers."""
    n=len(raw['nodes_m']);m=len(raw['triangles']);d=len(raw['dirichlet_node_ids'])
    shapes=[(n,2),(m,3),(n,),(m,2),(n,),(n,),(n,),(d,),(d,)]
    for (name,value),shape in zip(raw.items(),shapes):
        assert value.dtype.kind in 'iuf' and value.shape==shape and np.all(np.isfinite(value)),name
    tri=raw['triangles'];ids=raw['dirichlet_node_ids'];p=raw['nodes_m']
    assert tri.dtype.kind in 'iu' and np.all(tri>=0) and np.all(tri<n)
    assert ids.dtype.kind in 'iu' and np.array_equal(ids,np.unique(ids)) and np.all(ids>=0) and np.all(ids<n)
    assert np.all(raw['temperature_k']>=0) and np.all(raw['dirichlet_temperature_k']>=0)
    area,grad=geometry(p,tri)
    scale=abs(source*L*H)+2*K*35*H/L
    rows,cols,entries,load=original_system(p,tri,source)
    np.testing.assert_allclose((raw['load_w_per_m']-load)/scale,0,atol=1e-10)
    residual=action(rows,cols,entries,raw['temperature_k']-LEFT)-load
    np.testing.assert_allclose((raw['residual_w_per_m']-residual)/scale,0,atol=1e-10)
    fixed=np.flatnonzero(np.isclose(p[:,0],.007,rtol=0,atol=1e-15)|np.isclose(p[:,0],.037,rtol=0,atol=1e-15))
    np.testing.assert_array_equal(ids,fixed)
    expected_values=np.where(p[ids,0]<.02,LEFT,RIGHT)
    np.testing.assert_array_equal(raw['dirichlet_temperature_k'],expected_values)
    reaction=np.zeros(n);reaction[ids]=residual[ids]
    np.testing.assert_allclose((raw['reaction_w_per_m']-reaction)/scale,0,atol=1e-10)
    free=np.setdiff1d(np.arange(n),ids)
    np.testing.assert_allclose(raw['residual_w_per_m'][free]/scale,0,atol=1e-10)
    q=-K*np.einsum('ti,tij->tj',raw['temperature_k'][tri]-LEFT,grad)
    np.testing.assert_allclose((raw['heat_flux_w_m2']-q)/(K*35/L),0,atol=1e-10)
    sides,total=continuous_heat(source)
    actual=-np.array([raw['reaction_w_per_m'][p[:,0]<.007+1e-15].sum(),raw['reaction_w_per_m'][p[:,0]>.037-1e-15].sum()])
    np.testing.assert_allclose((actual-sides)/scale,0,atol=1e-10)
    assert abs(raw['load_w_per_m'].sum()-total)/scale<=1e-10
    assert abs(raw['reaction_w_per_m'].sum()+total)/scale<=1e-10
