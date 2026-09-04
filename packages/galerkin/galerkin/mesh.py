"""Triangle mesh data structure and simple structured mesh generators.

The minimum a FEM mesh needs:
  - nodes:     (N, 2)  coordinates (x, y) of each node
  - triangles: (T, 3)  node indices of each triangle (counter-clockwise)
  - boundary:  {tag: node-index array}  node sets for boundary conditions
  - boundary_edges: {tag: (E, 2) node pairs}  for Robin/Neumann edge integrals

Structured meshes for rectangles and annuli are generated in-house so the
validation problems run without an external mesher (Gmsh etc.).
"""

from __future__ import annotations

import numpy as np


class Mesh:
    def __init__(self, nodes: np.ndarray, triangles: np.ndarray,
                 boundary: dict[str, np.ndarray],
                 boundary_edges: dict[str, np.ndarray] | None = None):
        self.nodes = np.asarray(nodes, dtype=float)
        self.triangles = np.asarray(triangles, dtype=int)
        self.boundary = {k: np.asarray(v, dtype=int) for k, v in boundary.items()}
        self.boundary_edges = {k: np.asarray(v, dtype=int)
                               for k, v in (boundary_edges or {}).items()}
        self._fix_orientation()

    @property
    def num_nodes(self) -> int:
        return len(self.nodes)

    @property
    def num_triangles(self) -> int:
        return len(self.triangles)

    def _fix_orientation(self):
        """Flip triangles so that every element is counter-clockwise (area > 0)."""
        p = self.nodes[self.triangles]  # (T, 3, 2)
        # signed area = 0.5 * cross(p1-p0, p2-p0)
        cross = ((p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 1] - p[:, 0, 1])
                 - (p[:, 2, 0] - p[:, 0, 0]) * (p[:, 1, 1] - p[:, 0, 1]))
        flipped = cross < 0
        self.triangles[flipped] = self.triangles[flipped][:, [0, 2, 1]]

    def areas(self) -> np.ndarray:
        p = self.nodes[self.triangles]
        return 0.5 * np.abs(
            (p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 1] - p[:, 0, 1])
            - (p[:, 2, 0] - p[:, 0, 0]) * (p[:, 1, 1] - p[:, 0, 1]))


def rectangle_mesh(width: float, height: float, nx: int, ny: int) -> Mesh:
    """Structured triangulation of [0,width] x [0,height].

    Each grid cell is split into two triangles along a diagonal.
    Boundary tags: 'left', 'right', 'bottom', 'top'.
    """
    x = np.linspace(0.0, width, nx + 1)
    y = np.linspace(0.0, height, ny + 1)
    X, Y = np.meshgrid(x, y, indexing="xy")
    nodes = np.column_stack([X.ravel(), Y.ravel()])

    def nid(i, j):  # (column i, row j) -> node id
        return j * (nx + 1) + i

    tris = []
    for j in range(ny):
        for i in range(nx):
            n00, n10 = nid(i, j), nid(i + 1, j)
            n01, n11 = nid(i, j + 1), nid(i + 1, j + 1)
            tris.append([n00, n10, n11])
            tris.append([n00, n11, n01])

    boundary = {
        "left":   np.array([nid(0, j) for j in range(ny + 1)]),
        "right":  np.array([nid(nx, j) for j in range(ny + 1)]),
        "bottom": np.array([nid(i, 0) for i in range(nx + 1)]),
        "top":    np.array([nid(i, ny) for i in range(nx + 1)]),
    }
    boundary_edges = {
        "left":   np.array([[nid(0, j), nid(0, j + 1)] for j in range(ny)]),
        "right":  np.array([[nid(nx, j), nid(nx, j + 1)] for j in range(ny)]),
        "bottom": np.array([[nid(i, 0), nid(i + 1, 0)] for i in range(nx)]),
        "top":    np.array([[nid(i, ny), nid(i + 1, ny)] for i in range(nx)]),
    }
    return Mesh(nodes, np.array(tris), boundary, boundary_edges)


def annulus_mesh(r_inner: float, r_outer: float, n_r: int, n_theta: int) -> Mesh:
    """Structured triangulation of an annulus (coaxial-cable cross-section).

    A polar grid split into triangles; periodic in the theta direction.
    Boundary tags: 'inner' (inner conductor), 'outer' (outer conductor).
    """
    r = np.linspace(r_inner, r_outer, n_r + 1)
    theta = np.linspace(0.0, 2.0 * np.pi, n_theta, endpoint=False)
    R, TH = np.meshgrid(r, theta, indexing="ij")
    nodes = np.column_stack([(R * np.cos(TH)).ravel(), (R * np.sin(TH)).ravel()])

    def nid(ir, it):
        return ir * n_theta + (it % n_theta)

    tris = []
    for ir in range(n_r):
        for it in range(n_theta):
            n00, n01 = nid(ir, it), nid(ir, it + 1)
            n10, n11 = nid(ir + 1, it), nid(ir + 1, it + 1)
            tris.append([n00, n01, n11])
            tris.append([n00, n11, n10])

    boundary = {
        "inner": np.array([nid(0, it) for it in range(n_theta)]),
        "outer": np.array([nid(n_r, it) for it in range(n_theta)]),
    }
    boundary_edges = {
        "inner": np.array([[nid(0, it), nid(0, it + 1)] for it in range(n_theta)]),
        "outer": np.array([[nid(n_r, it), nid(n_r, it + 1)] for it in range(n_theta)]),
    }
    return Mesh(nodes, np.array(tris), boundary, boundary_edges)
