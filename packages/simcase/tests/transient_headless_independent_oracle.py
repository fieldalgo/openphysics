"""Independent transient headless mathematics; NumPy/stdlib only."""
import numpy as np

ALGEBRA_RTOL = 1e-10
SI_RTOL = 1e-9
COORD_ATOL_M = 1e-12
UNITS = {"m": 1.0, "mm": 1e-3, "um": 1e-6}
TIMES_S = (2.0, 2.03, 2.1, 2.4, 3.0)


def rectangle(nx=8, ny=8, width_m=0.002, height_m=0.001):
    """Own CCW geometry, unrelated to producer meshing helpers."""
    nodes = np.array([(width_m*i/nx, height_m*j/ny)
                      for j in range(ny+1) for i in range(nx+1)])
    cells = []
    for j in range(ny):
        for i in range(nx):
            a = j*(nx+1)+i
            cells.extend(((a, a+1, a+nx+2), (a, a+nx+2, a+nx+1)))
    return nodes, np.asarray(cells, dtype=np.int64)


class P1:
    def __init__(self, nodes_m, triangles, capacity, conductivity):
        self.nodes = np.array(nodes_m, dtype=float, copy=True)
        self.cells = np.array(triangles, dtype=np.int64, copy=True)
        self.c, self.k = float(capacity), float(conductivity)
        p = self.nodes[self.cells]
        d = ((p[:, 1, 0]-p[:, 0, 0])*(p[:, 2, 1]-p[:, 0, 1])
             -(p[:, 2, 0]-p[:, 0, 0])*(p[:, 1, 1]-p[:, 0, 1]))
        if np.any(d <= 0) or not np.all(np.isfinite(d)):
            raise ValueError("independent oracle requires positive finite CCW area")
        self.area = d/2
        self.grad = np.stack((
            np.stack((p[:, 1, 1]-p[:, 2, 1], p[:, 2, 0]-p[:, 1, 0]), -1),
            np.stack((p[:, 2, 1]-p[:, 0, 1], p[:, 0, 0]-p[:, 2, 0]), -1),
            np.stack((p[:, 0, 1]-p[:, 1, 1], p[:, 1, 0]-p[:, 0, 0]), -1)), 1)/d[:, None, None]
        self.me = self.c*self.area[:, None, None]*(np.ones((3, 3))+np.eye(3))/12
        self.ke = self.k*self.area[:, None, None]*np.einsum("eid,ejd->eij", self.grad, self.grad)

    def scatter(self, local):
        out = np.zeros(len(self.nodes))
        np.add.at(out, self.cells.ravel(), np.asarray(local).ravel())
        return out

    def action(self, tensors, values):
        return self.scatter(np.einsum("eij,ej->ei", tensors, np.asarray(values)[self.cells]))

    def mass(self, values):
        return self.action(self.me, values)

    def stiffness(self, values):
        v = np.asarray(values)
        return self.action(self.ke, v-v[0])

    def source(self, q):
        return self.scatter(np.broadcast_to(float(q)*self.area[:, None]/3,
                                           self.cells.shape))

    def flux(self, values):
        v = np.asarray(values)
        return -self.k*np.einsum("ei,eid->ed", (v-v[0])[self.cells], self.grad)

    def histories(self, states, times_s, q, fixed):
        """Full original-system diagnostics; inward reactions, no initial rates."""
        states, times = np.asarray(states), np.asarray(times_s)
        storage = np.array([self.mass((new-old)/dt)
                            for old, new, dt in zip(states[:-1], states[1:], np.diff(times))])
        load = self.source(q)
        residual = storage+np.array([self.stiffness(v) for v in states[1:]])-load
        reaction = np.zeros_like(residual)
        reaction[:, np.asarray(fixed, dtype=int)] = residual[:, np.asarray(fixed, dtype=int)]
        heat = np.array([np.sum(self.mass(v)) for v in states])
        quadratic = np.array([v@self.mass(v)/2 for v in states])
        return dict(storage=storage, residual=residual, reaction=reaction,
                    source=np.repeat(load[None, :], len(times), axis=0),
                    heat=heat, quadratic=quadratic,
                    flux=np.array([self.flux(v) for v in states]),
                    balance=np.sum(storage-load-reaction, axis=1),
                    outward=-np.sum(reaction, axis=1))


def uniform_heating(times_s, count, initial_k=300.0, q=8.0, capacity=4.0):
    times = np.asarray(times_s, dtype=float)
    return np.repeat((initial_k+q/capacity*(times-times[0]))[:, None], count, axis=1)


def uniform_ramp(times_s, count, initial_k=290.0, rate_k_s=3.0):
    times = np.asarray(times_s, dtype=float)
    return np.repeat((initial_k+rate_k_s*(times-times[0]))[:, None], count, axis=1)


def require_close(actual, expected, scale, label, rtol=ALGEBRA_RTOL):
    a, b = np.asarray(actual), np.asarray(expected)
    if a.shape != b.shape or not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
        raise AssertionError(label+": shape/nonfinite")
    error = float(np.max(np.abs(a-b))) if a.size else 0.0
    if error > rtol*float(scale):
        raise AssertionError(label+": normalized error="+repr(error/float(scale)))
