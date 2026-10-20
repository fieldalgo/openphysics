# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent continuum/line algebra; no production or reference imports.

This is an independent acceptance oracle, not a production solver API.
All rates are per unit out-of-plane depth.
"""
import numpy as np
from numpy.polynomial import polynomial as poly


def slab_state(x, coefficients, *, conductivity, source):
    a,b=coefficients
    x=np.asarray(x)
    return a+b*x-source*x*x/(2*conductivity), -conductivity*b+source*x


def dirichlet_flux(*, length, conductivity, source, left_temperature, right_outward):
    return np.array([left_temperature,(source*length-right_outward)/conductivity])


def dirichlet_robin(*, length, conductivity, source, left_temperature,
                     right_h, right_ambient, right_outward=0.):
    """Eliminate b directly in the right boundary equation, no discrete system."""
    b=(source*length-right_outward-right_h*(left_temperature-right_ambient
           -source*length*length/(2*conductivity)))/(conductivity+right_h*length)
    return np.array([left_temperature,b])


def robin_only(*, length, conductivity, source, h_left, h_right,
               ambient_left, ambient_right, outward_left=0., outward_right=0.):
    """Cramer's closed form including exactly one zero-h boundary.

    The determinant is positive for passive h when at least one end anchors.
    Zero determinant signals nonuniqueness, even with compatible source/flux.
    """
    k,L=conductivity,length
    determinant=k*(h_left+h_right)+h_left*h_right*L
    if determinant<=0:
        raise ValueError('passive Robin anchor is required; compatibility is not uniqueness')
    left=h_left*ambient_left-outward_left
    right=source*L-outward_right+h_right*(ambient_right+source*L*L/(2*k))
    return np.array([(left*(k+h_right*L)+k*right)/determinant,
                     (h_left*right-h_right*left)/determinant])


def monomial_integral(*factors):
    product=np.array([1.])
    for f in factors:product=poly.polymul(product,f)
    return np.sum(product/(np.arange(len(product))+1))


def exact_line_moments(length, h, ambient, outward):
    """Coefficient-based exact polynomial integrals on s in [0,1].

    h, ambient and outward are monomial coefficient arrays, not samples.
    """
    basis=([1.,-1.],[0.,1.])
    mass=length*np.array([[monomial_integral(h,a,b) for b in basis] for a in basis])
    reservoir=length*np.array([monomial_integral(a,h,ambient) for a in basis])
    removal=length*np.array([monomial_integral(a,outward) for a in basis])
    return mass,reservoir,removal


def normal_from_oriented_cell(vertices, edge):
    """Concept witness from CCW triangle traversal, independent of tag direction."""
    vertices=np.asarray(vertices);edge=set(edge)
    for a,b in ((0,1),(1,2),(2,0)):
        if {a,b}==edge:
            tangent=vertices[b]-vertices[a]
            return np.array([tangent[1],-tangent[0]])/np.linalg.norm(tangent)
    raise ValueError('edge must be incident to the triangle')


def validate_passive_samples(h, ambient):
    """Math-domain witness, not a proposed production API or complete validator."""
    for name,value in [('h',h),('ambient',ambient)]:
        a=np.asarray(value)
        if a.dtype.kind not in 'iuf' or not np.all(np.isfinite(a)):
            raise ValueError(name+' must be finite real numeric data')
    if np.any(np.asarray(h)<0):raise ValueError('passive h must be nonnegative')


def smooth_mms(points, conductivity):
    """Distinct continuum field with directly differentiated q and Q."""
    x,y=np.moveaxis(np.asarray(points),-1,0)
    pi=np.pi
    sx,cx,sy,cy=np.sin(2*pi*x),np.cos(2*pi*x),np.sin(pi*y),np.cos(pi*y)
    temperature=310+2*x-3*y+4*x*x+2*x*y+5*y*y+.7*sx*cy
    gradient=np.stack((2+8*x+2*y+1.4*pi*cx*cy,
                       -3+2*x+10*y-.7*pi*sx*sy),axis=-1)
    return dict(temperature=temperature,flux=-conductivity*gradient,
                source=conductivity*(-18+3.5*pi*pi*sx*cy),
                h=6+2*x+y,outward=.8+.3*x-.2*y)


def triangle_geometry(nodes, triangles, order=8):
    """Raw affine polynomials and independent Duffy-product integration."""
    z,w=np.polynomial.legendre.leggauss(order);z=(z+1)/2;w=w/2
    a,b=np.meshgrid(z,z,indexing='ij')
    bary=np.stack((1-a,a*(1-b),a*b),axis=-1).reshape(-1,3)
    vertices=nodes[triangles]
    determinant=np.abs(np.linalg.det(vertices[:,1:]-vertices[:,:1]))
    weights=determinant[:,None]*(w[:,None]*w[None,:]*a).ravel()
    basis=np.linalg.inv(np.concatenate((np.ones((*vertices.shape[:2],1)),vertices),axis=-1))
    gradient=basis[:,1:,:].swapaxes(1,2)
    points=np.einsum('qa,tad->tqd',bary,vertices)
    return bary,weights,points,gradient


def independent_system(mesh, conductivity, source, flux, convection, normals,
                       reference=300., order=8):
    """Assemble parent integrals independently; normals supplied by analytic geometry.

    Expected-value computation never imports the engine, refsol or their helpers.
    """
    from scipy.sparse import coo_matrix
    p,t=mesh.nodes,mesh.triangles;n=len(p)
    b,w,x,grad=triangle_geometry(p,t,order)
    stiffness=conductivity*np.einsum('tai,tbi,t->tab',grad,grad,w.sum(1))
    rows=np.repeat(t,3,axis=1).ravel();cols=np.tile(t,(1,3)).ravel()
    K=coo_matrix((stiffness.ravel(),(rows,cols)),shape=(n,n)).tocsr()
    value=source(x.reshape(-1,2)).reshape(x.shape[:2]) if callable(source) else np.full(x.shape[:2],source)
    fq=np.zeros(n);np.add.at(fq,t.ravel(),np.einsum('tq,qa,tq->ta',w,b,value).ravel())
    ambient=np.zeros(n);shifted=np.zeros(n);removal=np.zeros(n)
    hr=[];hc=[];hv=[]
    z,w=np.polynomial.legendre.leggauss(order);z=(z+1)/2;w=w/2;shape=np.stack((1-z,z),axis=-1)
    for tag in set(flux)|set(convection):
        edges=mesh.boundary_edges[tag];end=p[edges]
        points=np.einsum('qa,ead->eqd',shape,end)
        normal=normals(tag,points.reshape(-1,2)).reshape(points.shape)
        length=np.linalg.norm(end[:,1]-end[:,0],axis=-1);weight=length[:,None]*w
        def sample(value):
            return value(points.reshape(-1,2),normal.reshape(-1,2)).reshape(points.shape[:2]) if callable(value) else np.full(points.shape[:2],value)
        if tag in flux:
            local=np.einsum('eq,qa,eq->ea',weight,shape,sample(flux[tag]))
            np.add.at(removal,edges.ravel(),local.ravel())
        if tag in convection:
            h,ta=map(sample,convection[tag]);local=np.einsum('eq,qa,qb,eq->eab',weight,shape,shape,h)
            hr.extend(np.repeat(edges,2,axis=1).ravel());hc.extend(np.tile(edges,(1,2)).ravel());hv.extend(local.ravel())
            for dest,v in [(ambient,h*ta),(shifted,h*(ta-reference))]:
                local=np.einsum('eq,qa,eq->ea',weight,shape,v)
                np.add.at(dest,edges.ravel(),local.ravel())
    H=coo_matrix((hv,(hr,hc)),shape=(n,n)).tocsr()
    return K,H,fq,ambient,removal,shifted
