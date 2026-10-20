# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Triangle mesh data structure and simple structured mesh generators.

The minimum a FEM mesh needs:
  - nodes:     (N, 2)  coordinates (x, y) of each node
  - triangles: (T, 3)  node indices of each triangle (counter-clockwise)
  - boundary:  {tag: node-index array}  node sets for boundary conditions
  - boundary_edges: {tag: (E, 2) node pairs}  for Robin/Neumann edge integrals
  - regions:         (T,) material-region index per triangle, and
  - region_names:    the name of each region, so a material table can be written
                     by name rather than by position. External meshers hand back
                     exactly this pair; galerkin.from_mesher adapts them.

Structured meshes for rectangles, annuli and layered disks are generated
in-house so the validation problems run without an external mesher (Gmsh etc.).
"""

from __future__ import annotations

import numpy as np


class Mesh:
    def __init__(self, nodes: np.ndarray, triangles: np.ndarray,
                 boundary: dict[str, np.ndarray],
                 boundary_edges: dict[str, np.ndarray] | None = None,
                 regions: np.ndarray | None = None,
                 region_names: list[str] | None = None):
        self.nodes = np.asarray(nodes, dtype=float)
        self.triangles = np.asarray(triangles, dtype=int)
        self.boundary = {k: np.asarray(v, dtype=int) for k, v in boundary.items()}
        self.boundary_edges = {k: np.asarray(v, dtype=int)
                               for k, v in (boundary_edges or {}).items()}
        self.regions = (None if regions is None
                        else np.asarray(regions, dtype=int))
        self.region_names = list(region_names) if region_names is not None else None
        self._fix_orientation()   # reorders vertices only, so regions stays aligned

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

    def by_region(self, values) -> np.ndarray:
        """Per-triangle coefficient array from one value per material region.

        values: a {region name: value} mapping, or a sequence indexed by region id.
        """
        if self.regions is None:
            raise ValueError("this mesh carries no region information")
        if isinstance(values, dict):
            if self.region_names is None:
                raise ValueError("this mesh has no region names to look up")
            missing = set(self.region_names) - set(values)
            if missing:
                raise KeyError(f"no value given for region(s) {sorted(missing)}")
            values = [values[name] for name in self.region_names]
        return np.asarray(values)[self.regions]

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


def disk_mesh(r_layers, n_r, n_theta: int, region_names=None) -> Mesh:
    """Structured triangulation of a disk built from concentric material layers.

    r_layers: increasing outer radii of the layers, e.g. (a, R) for a fibre core
              of radius a inside a cladding reaching out to R. Every layer
              boundary lands exactly on element edges, so a piecewise-constant
              material coefficient carries no geometric error of its own; the
              only geometry error left is the inscribed polygon approximating
              the circle, which is O(h^2) and so does not spoil second order.
    n_r:      radial divisions, one int for every layer or a per-layer sequence
    n_theta:  azimuthal divisions. The mesh then has an exact C_n rotational
              symmetry; n_theta >= 5 keeps that discrete symmetry from splitting
              the m = +-1 and m = +-2 degenerate mode pairs, a split that would
              otherwise be mistaken for physical birefringence.

    The centre of a polar grid is a coordinate singularity, meshed here as a
    single node with a fan of n_theta triangles. Those triangles are slender but
    their largest angle stays near 90 degrees, and interpolation accuracy is
    governed by the maximum angle, not the minimum one.

    Boundary tag: 'outer'. Regions are the layers, named 'layer0', 'layer1', ...
    unless region_names is given.
    """
    r_layers = np.atleast_1d(np.asarray(r_layers, dtype=float))
    n_r = np.broadcast_to(np.atleast_1d(np.asarray(n_r, dtype=int)),
                          r_layers.shape)
    if np.any(np.diff(np.concatenate([[0.0], r_layers])) <= 0):
        raise ValueError("r_layers must be strictly increasing and positive")
    if n_theta < 3:
        raise ValueError("n_theta must be at least 3")

    # Ring radii, plus the layer index of each radial band between two rings
    radii, band_layer, r_prev = [0.0], [], 0.0
    for layer, (r_out, m) in enumerate(zip(r_layers, n_r)):
        radii.extend(np.linspace(r_prev, r_out, m + 1)[1:])
        band_layer.extend([layer] * m)
        r_prev = r_out
    radii = np.asarray(radii)
    band_layer = np.asarray(band_layer)
    n_rings = len(radii) - 1

    theta = np.linspace(0.0, 2.0 * np.pi, n_theta, endpoint=False)
    ring_xy = radii[1:, None] * np.stack([np.cos(theta), np.sin(theta)])[:, None, :]
    nodes = np.concatenate([[[0.0, 0.0]],
                            np.stack(ring_xy, axis=-1).reshape(-1, 2)])

    it = np.arange(n_theta)
    itp = (it + 1) % n_theta

    def nid(ring, idx):            # ring 1..n_rings, node 0 is the centre
        return 1 + (ring - 1) * n_theta + idx

    fan = np.stack([np.zeros(n_theta, dtype=int), nid(1, it), nid(1, itp)], axis=1)

    k = np.arange(1, n_rings)[:, None]        # inner ring of each band
    n00, n01 = nid(k, it[None, :]), nid(k, itp[None, :])
    n10, n11 = nid(k + 1, it[None, :]), nid(k + 1, itp[None, :])
    bands = np.stack([np.stack([n00, n01, n11], axis=-1),
                      np.stack([n00, n11, n10], axis=-1)], axis=2)  # (K, n_theta, 2, 3)

    triangles = np.concatenate([fan, bands.reshape(-1, 3)])
    regions = np.concatenate([np.full(n_theta, band_layer[0]),
                              np.repeat(band_layer[1:], 2 * n_theta)])

    outer = nid(n_rings, it)
    boundary = {"outer": outer}
    boundary_edges = {"outer": np.stack([outer, nid(n_rings, itp)], axis=1)}
    names = (list(region_names) if region_names is not None
             else [f"layer{i}" for i in range(len(r_layers))])
    return Mesh(nodes, triangles, boundary, boundary_edges, regions, names)


def _layer_coordinates(start, ends, n, label):
    ends = np.atleast_1d(np.asarray(ends, dtype=float))
    n = np.broadcast_to(np.atleast_1d(np.asarray(n, dtype=int)), ends.shape)
    if ends.ndim != 1 or not len(ends) or not np.all(np.isfinite(ends)):
        raise ValueError(f"{label} must be a nonempty finite 1D sequence")
    if np.any(np.diff(np.concatenate([[start], ends])) <= 0):
        raise ValueError(f"{label} must be strictly increasing beyond {start}")
    if np.any(n < 1):
        raise ValueError("every layer needs at least one division")
    coords, band, prev = [start], [], start
    for layer, (end, m) in enumerate(zip(ends, n)):
        coords.extend(np.linspace(prev, end, m + 1)[1:])
        band.extend([layer] * m)
        prev = end
    coords = np.asarray(coords)
    coords[np.cumsum(np.r_[0, n])] = np.r_[start, ends]   # interfaces land exactly
    return coords, np.asarray(band), len(ends)


def _names(region_names, count):
    names = (list(region_names) if region_names is not None
             else [f"layer{i}" for i in range(count)])
    if len(names) != count:
        raise ValueError("region_names needs one name per layer")
    return names


def layered_rectangle_mesh(x_interfaces, height: float, nx, ny: int,
                           region_names=None) -> Mesh:
    """Structured triangulation of [0, x_interfaces[-1]] x [0, height] in x-layers.

    x_interfaces: increasing right-hand x of each layer (m); layer i spans
    x_interfaces[i-1]..x_interfaces[i] with x_interfaces[-1] = total width.
    nx: divisions per layer (one int or one per layer). Every material
    interface is a mesh line, so a piecewise-constant coefficient is exact on
    the mesh. Boundary tags as rectangle_mesh ('left', 'right', 'bottom',
    'top'). Regions are the layers, named 'layer0', ... unless region_names.
    """
    x, band, count = _layer_coordinates(0.0, x_interfaces, nx, "x_interfaces")
    if ny < 1 or not np.isfinite(height) or height <= 0:
        raise ValueError("height must be positive and ny >= 1")
    base = rectangle_mesh(1.0, height, len(x) - 1, ny)
    nodes = base.nodes.copy()
    column = np.rint(nodes[:, 0] * (len(x) - 1)).astype(int)
    nodes[:, 0] = x[column]
    tri_column = np.min(column[base.triangles], axis=1)
    return Mesh(nodes, base.triangles, base.boundary, base.boundary_edges,
                band[tri_column], _names(region_names, count))


def layered_annulus_mesh(r_inner: float, r_interfaces, n_r, n_theta: int,
                         region_names=None) -> Mesh:
    """Structured annulus r_inner..r_interfaces[-1] built from concentric layers.

    Layer i spans r_interfaces[i-1]..r_interfaces[i] (r_interfaces[-1] is the
    outer radius). Every layer interface is a ring of mesh nodes, so the
    piecewise-constant material carries no geometric error beyond the inscribed
    polygon (O(h^2)). Boundary tags 'inner' and 'outer' (nodes and edges).
    Regions are the layers, named 'layer0', ... unless region_names is given.
    """
    if not np.isfinite(r_inner) or r_inner <= 0:
        raise ValueError("r_inner must be positive")
    if n_theta < 3:
        raise ValueError("n_theta must be at least 3")
    radii, band, count = _layer_coordinates(float(r_inner), r_interfaces, n_r,
                                            "r_interfaces")
    n_rings = len(radii)
    theta = np.linspace(0.0, 2.0 * np.pi, n_theta, endpoint=False)
    R, TH = np.meshgrid(radii, theta, indexing="ij")
    nodes = np.column_stack([(R * np.cos(TH)).ravel(), (R * np.sin(TH)).ravel()])
    it = np.arange(n_theta)
    itp = (it + 1) % n_theta
    k = np.arange(n_rings - 1)[:, None]
    n00, n01 = k * n_theta + it, k * n_theta + itp
    n10, n11 = n00 + n_theta, n01 + n_theta
    tris = np.stack([np.stack([n00, n01, n11], -1), np.stack([n00, n11, n10], -1)],
                    axis=2).reshape(-1, 3)
    regions = np.repeat(band, 2 * n_theta)
    inner, outer = it, (n_rings - 1) * n_theta + it
    boundary = {"inner": inner, "outer": outer}
    boundary_edges = {"inner": np.stack([inner, itp], axis=1),
                      "outer": np.stack([outer, (n_rings - 1) * n_theta + itp], axis=1)}
    return Mesh(nodes, tris, boundary, boundary_edges, regions,
                _names(region_names, count))
