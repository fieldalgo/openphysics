# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Research-only Fourier charges on separated circles above a grounded plane."""
import math
import numpy as np
from scipy.linalg import cho_factor,cho_solve


def angular(order,count,offset=0.):
    theta=2*np.pi*(np.arange(count)+offset)/count
    basis=np.column_stack([np.ones(count),*[f(n*theta)*np.sqrt(2) for n in range(1,order+1) for f in (np.cos,np.sin)]])
    return theta,basis


def solve(centers,radii,*,order=16,quadrature=256):
    centers=np.asarray(centers,dtype=float);radii=np.asarray(radii,dtype=float)
    n=len(radii);size=1+2*order
    assert centers.shape==(n,2) and np.isfinite(centers).all() and np.all(radii>0) and np.all(centers[:,1]>radii)
    assert quadrature>4*order
    for i in range(n):
        for j in range(i):assert np.linalg.norm(centers[i]-centers[j])>radii[i]+radii[j]
    theta,beta=angular(order,quadrature)
    points=centers[:,0,None]+1j*centers[:,1,None]+radii[:,None]*np.exp(1j*theta)
    matrix=np.empty((n*size,n*size))
    for i in range(n):
        for j in range(n):
            image=np.log(abs(points[i,:,None]-points[j,None,:].conj()))
            block=beta.T@image@beta/quadrature**2
            if i==j:block+=np.diag([-math.log(radii[i]),*[1/(2*k) for k in range(1,order+1) for _ in range(2)]])
            else:block-=beta.T@np.log(abs(points[i,:,None]-points[j,None,:]))@beta/quadrature**2
            matrix[i*size:(i+1)*size,j*size:(j+1)*size]=block
    reciprocity=float(np.max(abs(matrix-matrix.T))/np.max(abs(matrix)))
    assert reciprocity<=1e-12
    matrix=(matrix+matrix.T)/2
    rhs=np.zeros((n*size,n));rhs[::size]=2*np.pi*np.eye(n)
    charges=cho_solve(cho_factor(matrix),rhs)
    residual=float(np.max(abs(matrix@charges-rhs))/(2*np.pi));assert residual<=1e-12
    cap=charges[::size];current=(charges@np.linalg.inv(cap)).reshape(n,size,n)
    grams=np.array([a.T@a/(2*np.pi*r) for a,r in zip(current,radii)])
    ground=ground_gram(centers,radii,current)
    # Independent target nodes; analytical self potential, direct source rule.
    theta_check,beta_check=angular(order,2*quadrature+1,.3125)
    boundary=centers[:,0,None]+1j*centers[:,1,None]+radii[:,None]*np.exp(1j*theta_check)
    charge=charges.reshape(n,size,n);errors=[]
    for i in range(n):
        potential=np.zeros((len(theta_check),n))
        for j in range(n):
            values=np.log(abs(boundary[i,:,None]-points[j,None,:].conj()))@beta/quadrature
            if i==j:values+=beta_check*np.array([-math.log(radii[i]),*[1/(2*k) for k in range(1,order+1) for _ in range(2)]])[None,:]
            else:values-=np.log(abs(boundary[i,:,None]-points[j,None,:]))@beta/quadrature
            potential+=values@charge[j]
        errors.append(float(np.max(abs(potential/(2*np.pi)-np.eye(n)[i]))))
    numerical=dict(raw_reciprocity=reciprocity,residual=residual,current=float(np.max(abs(current[:,0]-np.eye(n)))),pointwise=max(errors))
    return dict(capacitance=cap,whole=grams,ground=ground,current_coefficients=current,numerical=numerical)


def ground_gram(centers,radii,current,precision=None):
    # Integral_0^inf k^p exp[-k(y_s+y_t+i(x_s-x_t))] dk = p!/lambda^(p+1).
    n,size,bases=current.shape;order=(size-1)//2
    if precision is not None:
        import mpmath as mp
        mp.mp.dps=precision
        convert=mp.mpf;imag=mp.j;root=mp.sqrt(2);factorial=mp.factorial;real=mp.re;total=mp.fsum;pi=mp.pi
    else:
        convert=float;imag=1j;root=math.sqrt(2);factorial=math.factorial;real=lambda x:x.real;total=math.fsum;pi=math.pi
    coefficients=[]
    for s in range(n):
        a=convert(float(radii[s]));rows=[[convert(float(v)) for v in current[s,0]]]
        for k in range(1,order+1):rows.append([(convert(float(x))-imag*convert(float(y)))*(-imag*a)**k/(root*factorial(k)) for x,y in zip(current[s,2*k-1],current[s,2*k])])
        coefficients.append(rows)
    terms=[[[] for j in range(bases)] for i in range(bases)]
    for s in range(n):
        for t in range(n):
            lam=convert(float(centers[s,1]))+convert(float(centers[t,1]))+imag*(convert(float(centers[s,0]))-convert(float(centers[t,0])))
            integrals=[factorial(k)/lam**(k+1) for k in range(2*order+1)]
            for k in range(order+1):
                for l in range(order+1):
                    for i in range(bases):
                        for j in range(bases):terms[i][j].append(real(coefficients[s][k][i]*coefficients[t][l][j].conjugate()*integrals[k+l]))
    return [[total(terms[i][j])/pi for j in range(bases)] for i in range(bases)] if precision is not None else np.array([[total(terms[i][j])/pi for j in range(bases)] for i in range(bases)])
