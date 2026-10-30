# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Static integration measures for scalar P1 problems on 2D meshes.

Cartesian coordinates use unit thickness. Axisymmetric coordinates are (r,z)
in metres and integrate the full revolution, with volume/surface weight 2*pi*r.
The symmetry axis is not a physical boundary: finite P1 trial functions and
the weighted weak form supply its natural regularity, without dividing by r.
Geometry is static; coefficients remain in their array library.
"""
import numpy as np

from .backend import to_numpy


class ScalarMeasure:
    def __init__(self, mesh, coordinate_system="cartesian"):
        if coordinate_system not in ("cartesian", "axisymmetric"):
            raise ValueError("coordinate_system must be 'cartesian' or 'axisymmetric'")
        self.coordinate_system = coordinate_system
        self.axisymmetric = coordinate_system == "axisymmetric"
        self.nodes = mesh.nodes
        self.triangles = mesh.triangles
        if self.axisymmetric and np.any(self.nodes[:, 0] < 0):
            raise ValueError("axisymmetric radius r must be nonnegative")

    @property
    def nodal_rate_unit(self):
        return "W" if self.axisymmetric else "W/m"

    def density(self, points):
        """Static measure multiplier at points (...,2)."""
        return 2*np.pi*points[..., 0] if self.axisymmetric else np.ones(points.shape[:-1])

    def cell_factor(self):
        """Exact cell-average multiplier for a linear radius."""
        return self.density(self.nodes[self.triangles].mean(axis=1))

    def check_axis_dirichlet(self, prescribed):
        if not self.axisymmetric or not prescribed:
            return
        t = self.triangles
        edges = np.sort(np.concatenate((t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]])), axis=1)
        edges, counts = np.unique(edges, axis=0, return_counts=True)
        exterior = edges[counts == 1]
        physical = exterior[np.any(self.nodes[exterior, 0] > 0, axis=1)]
        fixed = np.asarray(list(prescribed), dtype=int)
        if np.any((self.nodes[fixed, 0] == 0) & ~np.isin(fixed, physical)):
            raise ValueError("Dirichlet data on the symmetry axis alone are not permitted")

    def boundary_samples(self, samples):
        """Weight prevalidated scalar boundary samples; reject nonregular axis data."""
        if not self.axisymmetric:
            return samples
        result = []
        for kind, edges, shape, weights, values in samples:  # boundary groups, not elements
            radius = self.nodes[edges, 0]
            on_axis = np.all(radius == 0, axis=1)
            # Flux or h on a zero-area axis must not silently disappear or anchor a solve.
            if np.any(to_numpy(values[0])[on_axis] != 0):
                raise ValueError("nonzero flux or convection on the symmetry axis is not permitted")
            factor = 2*np.pi*np.einsum("qa,ea->eq", shape, radius)
            result.append((kind, edges, shape, weights*factor, values))
        return result
