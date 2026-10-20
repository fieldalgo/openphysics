# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Direct independent continuum oracle: NumPy only, no PDE/producer imports."""
import numpy as np

E,NU,ALPHA,TREF=70e9,.3,12e-6,293.15
C0=1e-4
TRANSLATION=np.array([2e-5,-1e-5])
LEVELS=(8,16,32,64)
TARGET=np.array([[8e6,3e6],[3e6,-2e6]])


def parent(strain,a,plane,young=E,nu=NU):
    """Full 3D strain/stress/energy, solving the original z equation for PS."""
    strain=np.asarray(strain);a=np.asarray(a)
    shape=np.broadcast_shapes(strain.shape[:-1],a.shape)
    dtype=np.result_type(strain,a,float)
    total=np.zeros((*shape,3,3),dtype=dtype)
    total[...,0,0]=strain[...,0];total[...,1,1]=strain[...,1]
    total[...,0,1]=total[...,1,0]=strain[...,2]/2
    mu=young/(2*(1+nu));lam=young*nu/((1+nu)*(1-2*nu))
    if plane=='stress':
        # The uneliminated equation is (2mu+lambda)ezz + lambda(exx+eyy)
        # - (2mu+3lambda)a = 0; no reduced production D is consulted.
        total[...,2,2]=((2*mu+3*lam)*a-lam*(total[...,0,0]+total[...,1,1]))/(2*mu+lam)
    elif plane!='strain':raise ValueError('plane must be explicit stress or strain')
    elastic=total-a[...,None,None]*np.eye(3)
    trace=np.trace(elastic,axis1=-2,axis2=-1)
    stress=2*mu*elastic+lam*trace[...,None,None]*np.eye(3)
    energy=mu*np.einsum('...ij,...ij->...',elastic,elastic)+lam*trace**2/2
    return dict(total=total,elastic=elastic,stress=stress,energy=energy)


def patch(points,plane,theta=20.,alpha=ALPHA,target=TARGET,length=1.,translation=TRANSLATION):
    """Invert the FULL 3D compliance for imposed in-plane S, then check parent."""
    p=np.asarray(points);s=np.zeros((3,3));s[:2,:2]=target;a=alpha*theta
    # PE is ezz=(szz-nu(sxx+syy))/E+a=0, solved before compliance.
    if plane=='strain':s[2,2]=NU*np.trace(target)-E*a
    elif plane!='stress':raise ValueError('plane')
    eps=(1+NU)*s/E-NU*np.trace(s)*np.eye(3)/E+a*np.eye(3)
    gu=np.array([[eps[0,0],2*eps[0,1]],[0.,eps[1,1]]])
    u=p@gu.T+np.asarray(translation)*length
    eng=np.array([eps[0,0],eps[1,1],2*eps[0,1]])
    state=parent(np.broadcast_to(eng,(*p.shape[:-1],3)),np.full(p.shape[:-1],a),plane)
    return dict(u=u,gradient=np.broadcast_to(gu,(*p.shape[:-1],2,2)),
                strain=np.broadcast_to(eng,(*p.shape[:-1],3)),theta=np.full(p.shape[:-1],theta),
                body=np.zeros_like(p),state=state)


def polynomial(points,plane,linear_temperature=False,length=1.,translation=TRANSLATION,alpha=ALPHA):
    """Cubic displacement/quadratic temperature and differentiated parent stress."""
    p=np.asarray(points);x,y=p[...,0]/length,p[...,1]/length
    u=C0*length*np.stack((x**3+2*x*y*y+x*y,2*x*x*y+y**3+x*x),axis=-1)+np.asarray(translation)*length
    gu=C0*np.stack((3*x*x+2*y*y+y,4*x*y+x,4*x*y+2*x,2*x*x+3*y*y),axis=-1).reshape((*x.shape,2,2))
    eng=np.stack((gu[...,0,0],gu[...,1,1],gu[...,0,1]+gu[...,1,0]),axis=-1)
    theta=12+9*x-4*y
    tx=np.full_like(x,9.);ty=np.full_like(y,-4.)
    if not linear_temperature:theta=theta+6*x*y+3*y*y;tx=tx+6*y;ty=ty+6*x+6*y
    # Cartesian derivatives of engineering strain come directly from the Hessian.
    dx=C0/length*np.stack((6*x,4*x,8*y+3),axis=-1)
    dy=C0/length*np.stack((4*y+1,6*y,8*x),axis=-1)
    sx=parent(dx,alpha*tx/length,plane)['stress']
    sy=parent(dy,alpha*ty/length,plane)['stress']
    body=-np.stack((sx[...,0,0]+sy[...,0,1],sx[...,1,0]+sy[...,1,1]),axis=-1)
    return dict(u=u,gradient=gu,strain=eng,theta=theta,body=body,state=parent(eng,alpha*theta,plane))


def triangle_rule(vertices,order=8):
    """Independent Cartesian barycentric/Duffy integration; no mesh PDE solve."""
    v=np.asarray(vertices);z,w=np.polynomial.legendre.leggauss(order);z=(z+1)/2;w=w/2
    s,t=np.meshgrid(z,z,indexing='ij')
    bary=np.stack((1-s,s*(1-t),s*t),axis=-1).reshape(-1,3)
    points=np.einsum('qa,cad->cqd',bary,v)
    weights=np.abs(np.linalg.det(v[:,1:]-v[:,:1]))[:,None]*(w[:,None]*w[None,:]*s).ravel()
    vandermonde=np.concatenate((np.ones((*v.shape[:2],1)),v),axis=-1)
    grad=np.swapaxes(np.linalg.inv(vandermonde)[:,1:,:],1,2)
    return bary,weights,points,grad


def square_geometry():
    return np.array([[0.,0.],[1.,0.],[1.,1.],[0.,1.]]),np.array([[0,1,2],[0,2,3]])


def ring_geometry():
    p=np.array([[-1.,-1.],[1.,-1.],[1.,1.],[-1.,1.],[-.4,-.4],[.4,-.4],[.4,.4],[-.4,.4]])
    cells=[]
    for i in range(4):
        j=(i+1)%4;cells.extend(((i,j,4+j),(i,4+j,4+i)))
    return p,np.asarray(cells)


def exterior_segments(points,cells):
    """Return (endpoint0,endpoint1,opposite) for incidence-one edges."""
    incidence={}
    for cell in cells:
        for a,b,c in ((0,1,2),(1,2,0),(2,0,1)):
            pair=tuple(sorted((int(cell[a]),int(cell[b]))))
            incidence.setdefault(pair,[]).append(int(cell[c]))
    if any(len(owners)>2 for owners in incidence.values()):raise ValueError('nonmanifold')
    return [(a,b,owners[0]) for (a,b),owners in incidence.items() if len(owners)==1]


def segment_rule(p0,p1,opposite,order=4):
    """Material-side test, independent of endpoint or cell orientation."""
    d=p1-p0;length=np.linalg.norm(d)
    if not np.isfinite(length) or length<=0:raise ValueError('zero or invalid segment')
    n=np.array([-d[1],d[0]])/length
    if np.dot(n,opposite-(p0+p1)/2)>0:n=-n
    s,w=np.polynomial.legendre.leggauss(order);s=(s+1)/2;w=w*length/2
    basis=np.column_stack((1-s,s));p=basis@np.stack((p0,p1))
    return basis,w,p,np.broadcast_to(n,p.shape)


def nodal_edge_force(p0,p1,opposite,traction,order=4):
    basis,w,p,n=segment_rule(p0,p1,opposite,order)
    t=traction(p,n)
    return np.einsum('qa,q,qi->ai',basis,w,t)


def continuum_ledger(points,cells,field,plane,alpha=ALPHA,order=8):
    """Continuum virtual work, NOT K times an interpolated cubic nodal vector."""
    bary,w,p,grad=triangle_rule(points[cells],order);f=field(p);state=f['state']
    cold=parent(f['strain'],np.zeros(w.shape),plane)
    thermal=parent(np.zeros((*w.shape,3)),alpha*f['theta'],plane)
    gu=f['gradient'];u=f['u'];sigma=state['stress'][...,:2,:2]
    volume_force=np.sum(w[...,None]*f['body'],axis=(0,1))
    volume_moment=np.sum(w*(p[...,0]*f['body'][...,1]-p[...,1]*f['body'][...,0]))
    work_body=np.sum(w*np.sum(u*f['body'],axis=-1))
    elastic_work=np.sum(w*np.einsum('...ij,...ij->...',gu,cold['stress'][...,:2,:2]))
    thermal_work=-np.sum(w*np.einsum('...ij,...ij->...',gu,thermal['stress'][...,:2,:2]))
    physical_internal=np.sum(w*np.einsum('...ij,...ij->...',gu,sigma))
    nodal_g=np.zeros_like(points);g_local=-np.einsum('tq,tqij,taj->tai',w,thermal['stress'][...,:2,:2],grad)
    np.add.at(nodal_g,cells.ravel(),g_local.reshape(-1,2))
    external_force=np.zeros(2);reaction_force=np.zeros(2);external_moment=0.;reaction_moment=0.
    traction_work=0.;support_work=0.;traction_nodes=np.zeros_like(points);support_nodes=np.zeros_like(points)
    for a,b,c in exterior_segments(points,cells):
        basis,ww,pp,nn=segment_rule(points[a],points[b],points[c])
        ff=field(pp);traction=np.einsum('qij,qj->qi',ff['state']['stress'][...,:2,:2],nn)
        force=np.sum(ww[:,None]*traction,axis=0);moment=np.sum(ww*(pp[:,0]*traction[:,1]-pp[:,1]*traction[:,0]));work=np.sum(ww*np.sum(ff['u']*traction,axis=1))
        node_force=np.einsum('qa,q,qi->ai',basis,ww,traction)
        if np.allclose(points[[a,b],0],0.,rtol=0,atol=1e-14):
            reaction_force+=force;reaction_moment+=moment;support_work+=work;support_nodes[[a,b]]+=node_force
        else:
            external_force+=force;external_moment+=moment;traction_work+=work;traction_nodes[[a,b]]+=node_force
    return dict(U=float(np.sum(w*state['energy'])),CT=float(np.sum(w*thermal['energy'])),
                elastic_work=float(elastic_work),thermal_work=float(thermal_work),physical_internal=float(physical_internal),
                body_work=float(work_body),traction_work=float(traction_work),support_work=float(support_work),
                force=volume_force+external_force+reaction_force,moment=float(volume_moment+external_moment+reaction_moment),
                g=nodal_g,traction_nodes=traction_nodes,support_nodes=support_nodes)


def rigid_ranks(points,labels,supports):
    """Three analytic rigid basis columns per disconnected material component."""
    ranks=[]
    for label in np.unique(labels):
        ids=np.flatnonzero(labels==label);center=points[ids].mean(0);rows=[]
        for node,component in supports:
            if labels[node]!=label:continue
            x,y=points[node]-center
            rows.append([1.,0.,-y] if component==0 else [0.,1.,x])
        ranks.append(0 if not rows else int(np.linalg.matrix_rank(rows,tol=1e-12)))
    return ranks
