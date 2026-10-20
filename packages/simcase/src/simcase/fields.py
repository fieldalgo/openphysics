# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Vector mode fields, preserving the mixed edge/nodal representation."""

from dataclasses import dataclass

import numpy as np


@dataclass
class VectorField:
    """One study point; all components share one normalization per mode.

    edges: (E, 2), oriented from the lower to the higher node index.
    transverse: (E, modes), line integrals of E_t in document length units.
    longitudinal: (N, modes), complex E_z at nodes (including its relative phase).
    electric: (T, modes, 3), complex Ex/Ey/Ez at triangle centroids.

    The maximum centroid |E| is one. Amplitudes are relative, not V/m or
    power-normalized. Centroid samples are per element: no averaging across a
    dielectric interface. Raw coefficients retain the full finite-element field.
    """

    edges: np.ndarray
    transverse: np.ndarray
    longitudinal: np.ndarray
    electric: np.ndarray

    def to_dict(self) -> dict:
        """JSON-safe display samples, with shape (modes, triangles, components)."""
        values = self.electric.transpose(1, 0, 2)
        return {"location": "triangle_centroids", "components": ["Ex", "Ey", "Ez"],
                "normalization": "max_centroid_magnitude", "amplitude_unit": "relative",
                "real": values.real.tolist(), "imag": values.imag.tolist()}
