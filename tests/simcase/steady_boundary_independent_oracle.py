# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Independent constant-coefficient steady boundary mathematics (NumPy only)."""
import numpy as np

ALGEBRA = 1e-10
SI_GATE = 1e-9
UNITS = {"m": 1., "mm": 1e-3, "um": 1e-6}


def close(actual, expected, scale, label, tolerance=ALGEBRA):
    a, b = np.asarray(actual), np.asarray(expected)
    if a.shape != b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise AssertionError(label + ": shape/finite")
    if np.max(np.abs(a-b), initial=0.) > tolerance*max(float(scale), np.finfo(float).tiny):
        raise AssertionError(label + ": normalized error")


def slab(case):
    """Return L,H,k,Q,a,b,g,h,Ta,D without using a solver."""
    if case == "linear":
        return 1., 1., 2., 0., 300., -7., {"right": 2.}, {"right": 4.}, {"right": 290.}, {"left": 300.}
    if case == "quadratic":
        L, H, k, Q, a, g, h, ta = .03, .02, 12.5, 1e5, 300., 100., 20., 290.
        b = (Q*L-g-h*(a-ta)+h*Q*L*L/(2*k))/(k+h*L)
        return L,H,k,Q,a,b,{"right":g},{"right":h},{"right":ta},{"left":a}
    if case in ("robin", "zero_h"):
        L,H,k,Q,a,b = .03,.02,12.5,1e5,300.,-10.
        g = {"left": 30., "right": 100.}
        h = {"left": 10., "right": 20.}
        if case == "zero_h":
            h["left"], g["left"] = 0., k*b
        ta = {"left": a-(k*b-g["left"])/h["left"] if h["left"] else 290.,
              "right": a+b*L-Q*L*L/(2*k)-(Q*L-k*b-g["right"])/h["right"]}
        return L,H,k,Q,a,b,g,h,ta,{}
    raise ValueError(case)


class Elements:
    """Element actions, with no dense global solve or producer assembly."""
    def __init__(self, nodes, triangles, conductivity, source):
        self.x = np.asarray(nodes, dtype=float)
        self.t = np.asarray(triangles)
        if self.x.ndim != 2 or self.x.shape[1] != 2 or not np.isfinite(self.x).all():
            raise AssertionError("coordinates")
        if self.t.ndim != 2 or self.t.shape[1] != 3 or self.t.dtype.kind not in "iu":
            raise AssertionError("triangles")
        if np.any(self.t < 0) or np.any(self.t >= len(self.x)):
            raise AssertionError("indices")
        p = self.x[self.t]
        v, w = p[:,1]-p[:,0], p[:,2]-p[:,0]
        det = v[:,0]*w[:,1]-v[:,1]*w[:,0]
        if not np.isfinite(det).all() or np.any(det <= 0):
            raise AssertionError("CCW area")
        self.area = det/2
        self.grad = np.stack((np.stack((v[:,1]-w[:,1],w[:,0]-v[:,0]),axis=1),
                              np.stack((w[:,1],-w[:,0]),axis=1),
                              np.stack((-v[:,1],v[:,0]),axis=1)),axis=1)/det[:,None,None]
        self.k = conductivity
        self.f = np.zeros(len(self.x))
        np.add.at(self.f,self.t.ravel(),np.repeat(source*self.area/3,3))
        owners = {}
        for tri in self.t:
            for i,j in ((tri[0],tri[1]),(tri[1],tri[2]),(tri[2],tri[0])):
                edge = tuple(sorted((int(i),int(j))))
                owners[edge] = owners.get(edge,0)+1
        self.edges = np.array([e for e,n in owners.items() if n == 1],dtype=int)
        if not len(self.edges):
            raise AssertionError("exterior")
        self.sides = {}
        for side,axis,end in (("left",0,0),("right",0,1),("bottom",1,0),("top",1,1)):
            target = (self.x.min(axis=0) if end == 0 else self.x.max(axis=0))[axis]
            tol = 16*np.finfo(float).eps*max(1.,np.max(abs(self.x)),np.ptp(self.x[:,axis]))
            selected = self.edges[np.all(abs(self.x[self.edges,axis]-target)<=tol,axis=1)]
            self.sides[side] = selected

    def flux(self, temperature):
        return -self.k*np.einsum("ei,eij->ej",np.asarray(temperature)[self.t],self.grad)

    def stiffness(self, temperature):
        gradient = -self.flux(temperature)/self.k
        local = self.k*self.area[:,None]*np.einsum("eij,ej->ei",self.grad,gradient)
        out = np.zeros(len(self.x))
        np.add.at(out,self.t.ravel(),local.ravel())
        return out

    def boundary(self, temperature, g, h, ambient, variant=None):
        G,B,HT = (np.zeros(len(self.x)) for _ in range(3))
        for side in set(g)|set(h):
            for edge in self.sides[side]:
                length = np.linalg.norm(self.x[edge[1]]-self.x[edge[0]])
                outward = g.get(side,0.)*length/2*np.ones(2)
                offset = h.get(side,0.)*ambient.get(side,0.)*length/2*np.ones(2)
                matrix = h.get(side,0.)*length/6*np.array([[2.,1.],[1.,2.]])
                if variant == "lumped_H":
                    matrix = np.diag(matrix.sum(axis=1))
                if variant == "missing_H":
                    matrix *= 0
                if variant == "negative_H":
                    matrix *= -1
                if variant == "missing_B":
                    offset *= 0
                if variant == "wrong_sign_G":
                    outward *= -1
                np.add.at(G,edge,outward)
                np.add.at(B,edge,offset)
                np.add.at(HT,edge,matrix@(np.asarray(temperature)[edge]-(290. if variant == "wrong_offset" else 0.)))
        return G,B,HT

    def errors(self, temperature, L, a, b, Q, origin, degree):
        z,w = np.polynomial.legendre.leggauss(degree)
        z,w = (z+1)/2,w/2
        u,v = np.meshgrid(z,z,indexing="ij")
        weights = (w[:,None]*w[None,:]*(1-u)).ravel()
        bary = np.stack((1-u-(1-u)*v,u,(1-u)*v),axis=-1).reshape(-1,3)
        points = np.einsum("qi,eij->eqj",bary,self.x[self.t])
        x = points[:,:,0]-origin
        exact = a+b*x-Q*x*x/(2*self.k)
        approx = np.einsum("qi,ei->eq",bary,np.asarray(temperature)[self.t])
        f = self.flux(temperature)
        diff = f[:,None,:]-np.stack((Q*x-self.k*b,np.zeros_like(x)),axis=-1)
        return np.sqrt(np.array([np.sum(2*self.area[:,None]*weights*(approx-exact)**2),
                                 np.sum(2*self.area[:,None]*weights*np.sum(diff**2,axis=-1))]))
