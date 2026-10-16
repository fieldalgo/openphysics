# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fixed registered transient convergence demonstration.

This program asserts the gates before reporting results. Full histories can
use substantial RAM; see the validation guide for reproduction requirements.
"""
import json
import numpy as np
from galerkin.mesh import rectangle_mesh
from galerkin.transient_heat import solve_transient_heat
from refsol.transient_heat import (p1_matrices, smallest_dirichlet_mode,
                                   backward_euler_amplitude, sine_manufactured)


def exterior(mesh):
    return np.unique(np.concatenate(list(mesh.boundary.values())))


def temporal_gate():
    mesh=rectangle_mesh(1.,1.,8,8)
    m,k=p1_matrices(mesh.nodes,mesh.triangles,
        conductivity=2.5,volumetric_heat_capacity=4.)
    fixed=exterior(mesh)
    lam,phi=smallest_dirichlet_mode(m,k,fixed)
    tau=1/lam;errors=[]
    for steps in (8,16,32,64):
        times=np.linspace(0.,tau,steps+1)
        result=solve_transient_heat(mesh,conductivity=2.5,volumetric_heat_capacity=4.,
            time_s=times,initial_temperature_k=300.+phi,
            dirichlet={int(i):300. for i in fixed})
        product=backward_euler_amplitude(lam,times)
        increment=result.temperature_k-300.
        np.testing.assert_allclose(increment,product[:,None]*phi,rtol=0,atol=1e-10)
        difference=increment[-1]-np.exp(-1)*phi
        errors.append(float(np.sqrt(difference@m@difference/(phi@m@phi))))
    orders=np.log2(np.array(errors[:-1])/errors[1:])
    assert np.all(orders[-2:]>=.9) and np.all(orders[-2:]<=1.1)
    return dict(mesh_subdivisions=8,amplitude_k=1.,baseline_k=300.,
        eigenvalue_per_s=lam,tau_s=tau,steps=[8,16,32,64],errors_k=errors,orders=orders.tolist())


def pde_errors(mesh,result,index,order):
    z,w=np.polynomial.legendre.leggauss(order);z=(z+1)/2;w=w/2
    x,y=np.meshgrid(z,z,indexing='ij')
    bary=np.stack([(1-x)*(1-y),x,(1-x)*y],axis=-1).reshape(-1,3)
    weights=(2*w[:,None]*w[None,:]*(1-x)).ravel()
    sums=np.zeros(2)
    for start in range(0,mesh.num_triangles,128):
        tri=mesh.triangles[start:start+128];p=mesh.nodes[tri]
        a=p[:,1]-p[:,0];b=p[:,2]-p[:,0]
        area=(a[:,0]*b[:,1]-a[:,1]*b[:,0])/2
        points=np.einsum('qa,tad->tqd',bary,p)
        shape=points.shape[:2]
        exact=sine_manufactured(points.reshape(-1,2),float(result.time_s[index]))
        recovered=np.einsum('qa,ta->tq',bary,result.temperature_k[index,tri])
        dt=recovered-exact.temperature_k.reshape(shape)
        dq=result.heat_flux_w_m2[index,start:start+len(tri),None,:]-exact.heat_flux_w_m2.reshape((*shape,2))
        sums[0]+=np.sum(area[:,None]*weights*dt**2)
        sums[1]+=np.sum(area[:,None]*weights*np.sum(dq**2,axis=-1))
    return np.sqrt(sums)


def pde_run(n,steps):
    mesh=rectangle_mesh(1.,1.,n,n)
    times=np.linspace(0.,1.,steps+1)
    result=solve_transient_heat(mesh,conductivity=2.5,volumetric_heat_capacity=4.,
        time_s=times,initial_temperature_k=sine_manufactured(mesh.nodes,0.).temperature_k,
        dirichlet={int(i):300. for i in exterior(mesh)},
        heat_source=lambda p,t:sine_manufactured(p,t).heat_source_w_m3)
    errors=[]
    for observed in (.25,.5,1.):
        index=int(round(observed*steps));assert result.time_s[index]==observed
        e8=pde_errors(mesh,result,index,8);e10=pde_errors(mesh,result,index,10)
        np.testing.assert_allclose(e8,e10,rtol=.01,atol=0)
        errors.append(e8)
    return np.array(errors)


def spatial_gate():
    history=np.array([pde_run(n,256) for n in (8,16,32,64)])
    orders=np.log2(history[:-1]/history[1:])
    assert np.all(orders[-2:,:,0]>=1.8)
    assert np.all(orders[-2:,:,1]>=.9)
    companion=pde_run(64,512)
    separation=abs(companion-history[-1])/history[-1]
    assert np.all(separation<=.05)
    return dict(subdivisions=[8,16,32,64],primary_dt_s=1/256,
        companion_dt_s=1/512,observed_time_s=[.25,.5,1.],
        errors=history.tolist(),orders=orders.tolist(),
        finest_companion_errors=companion.tolist(),separation_fraction=separation.tolist())


def main():
    print(json.dumps({'temporal':temporal_gate(),'spatial':spatial_gate()},indent=2))


if __name__=="__main__":
    main()
