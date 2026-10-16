"""Independent transient heat truth. NumPy/stdlib only; not executed at registration."""
import math
import numpy as np

K_SI = 2.5
C_SI = 4.0
GAMMA = 0.7
TEMPORAL_STEPS = (8, 16, 32, 64)
PDE_N = (8, 16, 32, 64)
OBSERVATION_TIMES = (0.25, 0.5, 1.0)
ALGEBRA_GATE = 1e-10
SI_GATE = 1e-9


def square(n, length=1.0, origin=(0.0, 0.0)):
    """Deterministic CCW diagonal mesh; no mesher/production geometry calls."""
    xy = np.array([(length*i/n+origin[0], length*j/n+origin[1])
                   for j in range(n+1) for i in range(n+1)], dtype=float)
    cells = []
    for j in range(n):
        for i in range(n):
            a = j*(n+1)+i
            cells.extend(((a, a+1, a+n+2), (a, a+n+2, a+n+1)))
    boundary = np.array([j*(n+1)+i for j in range(n+1) for i in range(n+1)
                         if i in (0, n) or j in (0, n)], dtype=int)
    return xy, np.array(cells, dtype=int), boundary


def disjoint_squares(n):
    x, e, b = square(n)
    y, f, d = square(n, origin=(2.0, 0.0))
    return np.vstack((x, y)), np.vstack((e, f+len(x))), np.r_[b, d+len(x)]


class Elements:
    """Original local M/K and scatter action, avoiding dense n64 global storage."""

    def __init__(self, xy, cells, conductivity=K_SI, capacity=C_SI):
        self.xy = np.array(xy, dtype=float, copy=True)
        self.cells = np.array(cells, dtype=int, copy=True)
        self.k, self.c = float(conductivity), float(capacity)
        p = self.xy[self.cells]
        det = ((p[:, 1, 0]-p[:, 0, 0])*(p[:, 2, 1]-p[:, 0, 1])
               -(p[:, 2, 0]-p[:, 0, 0])*(p[:, 1, 1]-p[:, 0, 1]))
        if np.any(det <= 0) or not np.all(np.isfinite(det)):
            raise ValueError("oracle requires finite positive CCW cell area")
        self.area = det/2
        self.grad = np.stack((np.stack((p[:, 1, 1]-p[:, 2, 1],
                                       p[:, 2, 0]-p[:, 1, 0]), axis=-1),
                              np.stack((p[:, 2, 1]-p[:, 0, 1],
                                        p[:, 0, 0]-p[:, 2, 0]), axis=-1),
                              np.stack((p[:, 0, 1]-p[:, 1, 1],
                                        p[:, 1, 0]-p[:, 0, 0]), axis=-1)), axis=1)/det[:, None, None]
        self.me = self.c*self.area[:, None, None]*(np.ones((3, 3))+np.eye(3))/12
        self.ke = self.k*self.area[:, None, None]*np.einsum("eid,ejd->eij", self.grad, self.grad)

    def action(self, local, temperature):
        result = np.zeros(len(self.xy))
        values = np.einsum("eij,ej->ei", local, np.asarray(temperature)[self.cells])
        np.add.at(result, self.cells.reshape(-1), values.reshape(-1))
        return result

    def mass(self, temperature):
        return self.action(self.me, temperature)

    def stiffness(self, temperature):
        # Fixed common offset suppresses cancellation without changing K*1=0.
        t = np.asarray(temperature)
        return self.action(self.ke, t-t[0])

    def dense(self):
        """Only small-mesh algebra/temporal truth; never n64 PDE factorization."""
        n = len(self.xy)
        m, k = np.zeros((n, n)), np.zeros((n, n))
        for ids, me, ke in zip(self.cells, self.me, self.ke):
            m[np.ix_(ids, ids)] += me
            k[np.ix_(ids, ids)] += ke
        return m, k

    def flux(self, temperature):
        t = np.asarray(temperature)
        return -self.k*np.einsum("ei,eid->ed", (t-t[0])[self.cells], self.grad)

    def quadrature(self, order=8):
        """Tensor Gauss on Duffy square: lambda=(1-r,r*(1-s),r*s)."""
        z, w = np.polynomial.legendre.leggauss(order)
        z, w = (z+1)/2, w/2
        r, s = np.meshgrid(z, z, indexing="ij")
        wr, ws = np.meshgrid(w, w, indexing="ij")
        r, s = r.ravel(), s.ravel()
        bary = np.stack((1-r, r*(1-s), r*s), axis=-1)
        weight = (wr*ws).ravel()*r
        points = np.einsum("qi,eid->eqd", bary, self.xy[self.cells])
        return bary, points, 2*self.area[:, None]*weight[None, :]

    def load(self, source, time, order=8):
        bary, points, weights = self.quadrature(order)
        value = np.asarray(source(points.reshape(-1, 2), float(time)), dtype=float)
        if value.shape != (points.shape[0]*points.shape[1],) or not np.all(np.isfinite(value)):
            raise ValueError("oracle source shape/nonfinite")
        local = np.einsum("eq,qi->ei", value.reshape(weights.shape)*weights, bary)
        result = np.zeros(len(self.xy))
        np.add.at(result, self.cells.ravel(), local.ravel())
        return result

    def diagnostics(self, old, new, load, dt, fixed):
        storage = self.mass((new-old)/dt)
        residual = storage+self.stiffness(new)-load
        reaction = np.zeros_like(residual)
        reaction[np.asarray(fixed, dtype=int)] = residual[np.asarray(fixed, dtype=int)]
        h0, h1 = np.sum(self.mass(old)), np.sum(self.mass(new))
        v0, v1 = old@self.mass(old)/2, new@self.mass(new)/2
        delta = new-old
        quadratic = ((v1-v0)/dt+delta@self.mass(delta)/(2*dt)
                     +(new-new[0])@self.stiffness(new)-new@(load+reaction))
        heat_balance = (h1-h0)/dt-np.sum(load+reaction)
        return dict(storage=storage, residual=residual, reaction=reaction,
                    heat_content=h1, quadratic_functional=v1,
                    outward_dirichlet=-np.sum(reaction),
                    heat_balance=heat_balance, quadratic_identity=quadratic)

    def errors(self, temperature, time, order=8):
        bary, points, weights = self.quadrature(order)
        value = np.einsum("qi,ei->eq", bary, (temperature-300)[self.cells])
        exact, q = sine(points, time)
        et = math.sqrt(float(np.sum(weights*(value-(exact-300))**2)))
        dq = self.flux(temperature)[:, None, :]-q
        eq = math.sqrt(float(np.sum(weights*np.sum(dq*dq, axis=-1))))
        return et, eq


def constant_source(value):
    return lambda points, time: np.full(len(points), value, dtype=float)


def sine(points, time):
    x, y = points[..., 0], points[..., 1]
    s = np.sin(math.pi*x)*np.sin(math.pi*y)
    amp = 1+GAMMA*time
    temperature = 300+amp*s
    gradient = math.pi*np.stack((np.cos(math.pi*x)*np.sin(math.pi*y),
                                np.sin(math.pi*x)*np.cos(math.pi*y)), axis=-1)
    return temperature, -K_SI*amp*gradient


def sine_source(points, time):
    s = np.sin(math.pi*points[:, 0])*np.sin(math.pi*points[:, 1])
    return (C_SI*GAMMA+2*K_SI*math.pi**2*(1+GAMMA*time))*s


def moving_affine(points, time):
    return 290+5*points[:, 0]+3*time


def small_be(m, k, times, initial, fixed, boundary, loads, variant="correct"):
    """Independent dense BE reference/wrong actors; no product API or helper."""
    fixed = np.asarray(fixed, dtype=int)
    free = np.setdiff1d(np.arange(len(initial)), fixed)
    mm = np.diag(m.sum(axis=1)) if variant == "lump_mass" else m.copy()
    result = [np.array(initial, dtype=float, copy=True)]
    baseline = float(initial[0])
    cache = None
    for j, dt in enumerate(np.diff(times), start=1):
        old = result[-1]-baseline
        dn = np.asarray(boundary(float(times[j])), dtype=float)-baseline
        dp = old[fixed]
        f = loads[j].copy()
        if variant == "left_source":
            f = loads[j-1]
        if variant == "frozen_source":
            f = loads[0]
        if variant == "average_source":
            f = (loads[j]+loads[j-1])/2
        a = mm/dt+k
        rhs = f[free]+mm[np.ix_(free, free)]@old[free]/dt-k[np.ix_(free, fixed)]@dn
        fc = mm[np.ix_(free, fixed)]
        if variant != "omit_old_fc" and variant != "omit_both_fc":
            rhs += fc@dp/dt
        if variant != "omit_new_fc" and variant != "omit_both_fc":
            rhs -= fc@dn/dt
        block = a[np.ix_(free, free)]
        if cache is None or variant != "stale_dt":
            cache = np.linalg.inv(block)
        new = np.zeros(len(initial))
        new[fixed] = dn
        new[free] = cache@rhs
        new += baseline
        if variant == "clamp":
            new = np.maximum(new, 0)
        result.append(new)
    return np.array(result)


def mode_truth(n=8):
    xy, cells, fixed = square(n)
    element = Elements(xy, cells)
    m, k = element.dense()
    free = np.setdiff1d(np.arange(len(xy)), fixed)
    mf, kf = m[np.ix_(free, free)], k[np.ix_(free, free)]
    chol = np.linalg.cholesky(mf)
    a = np.linalg.solve(chol, kf)
    a = np.linalg.solve(chol, a.T).T
    values, vectors = np.linalg.eigh((a+a.T)/2)
    i = np.flatnonzero(values > 100*np.finfo(float).eps*np.max(np.abs(values)))[0]
    phi = np.zeros(len(xy))
    phi[free] = np.linalg.solve(chol.T, vectors[:, i])
    phi /= np.max(np.abs(phi))
    phi *= 1 if phi[np.argmax(np.abs(phi))] > 0 else -1
    return element, m, k, fixed, float(values[i]), phi


def orders(errors):
    errors = np.asarray(errors, dtype=float)
    if np.any(errors <= 0) or not np.all(np.isfinite(errors)):
        raise AssertionError("orders need finite nonzero measured error")
    return np.log2(errors[:-1]/errors[1:])


def pde_gates(primary, companion, quadrature10):
    """Inputs (n,time,(T L2,flux L2)); no gate selected from observations."""
    a, b, q = np.asarray(primary), np.asarray(companion), np.asarray(quadrature10)
    if a.shape != (4, 3, 2) or b.shape != (3, 2) or q.shape != a.shape:
        raise AssertionError("registered arrays are 4 meshes x 3 times x 2 norms")
    if np.any(a <= 0) or not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)) or not np.all(np.isfinite(q)):
        raise AssertionError("nonfinite or zero measured error")
    p = np.log2(a[:-1]/a[1:])
    if np.any(p[-2:, :, 0] < 1.8) or np.any(p[-2:, :, 1] < 0.9):
        raise AssertionError("fixed spatial orders failed")
    if np.any(np.abs(b-a[-1])/a[-1] > 0.05):
        raise AssertionError("fixed time/spatial error separation failed")
    if np.any(np.abs(q-a)/a > 0.01):
        raise AssertionError("fixed interior quadrature disagreement")
    return p
