# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Analytical circular conductor over an infinite grounded line."""
import json
import math

import numpy as np
import pytest
from scipy.linalg import cho_factor, cho_solve

from galerkin.dense_residual import bounded_dense_residual
from galerkin.laplace_corner_harmonic import power_panel_harmonic_gram
from galerkin.laplace_corner_harmonic_interactions import _rule
from galerkin.laplace_corner_harmonic_assembly import assemble_harmonic_corner_half_space


@pytest.fixture(scope='module')
def circles():
    result = []
    for vertices in (8, 12, 16):
        radius, height, width = .1, .5, 4.
        angles = (np.arange(vertices)*2+1)*np.pi/vertices
        polygon = np.column_stack((width/2+radius*np.cos(angles)/np.cos(np.pi/vertices),
                                   height+radius*np.sin(angles)/np.cos(np.pi/vertices)))
        half = assemble_harmonic_corner_half_space([polygon], width=width, height=1.)
        geometry = half.geometry
        matrix = (half.matrix+half.matrix.T)/2
        potentials = np.tile([1., 0.], geometry.panel_count)[:, None]
        rhs = 2*np.pi*potentials
        factor = cho_factor(matrix)
        charge = cho_solve(factor, rhs)
        for _ in range(2):
            charge += cho_solve(factor, bounded_dense_residual(matrix, charge, rhs))
        capacitance = float((potentials.T@charge)[0, 0])
        assert np.max(abs(bounded_dense_residual(matrix, charge, rhs)))/(2*np.pi) <= 1e-10
        assert abs(float((charge.T@matrix@charge)[0, 0])/(2*np.pi)/capacitance-1) <= 1e-10
        current = (charge/capacitance).reshape(-1, 2)
        assert abs(math.fsum(current[:, 0])-1) <= 1e-10
        signal = math.fsum(current[i, a]*power_panel_harmonic_gram(length, exponent)[a, b]*current[i, b]
            for i, (length, exponent) in enumerate(zip(geometry.lengths_m, geometry.exponents))
            for a in range(2) for b in range(2))
        starts = geometry.normalized_starts*geometry.length_unit_m
        directions = geometry.normalized_directions*geometry.length_unit_m
        minimum_height = float(np.min(np.r_[starts[:, 1], (starts+directions)[:, 1]]))
        ground = {}
        for source_order in (16, 32):
            points, weights = [], []
            for i, exponent in enumerate(geometry.exponents):
                u, physical_weights, error = _rule(float(exponent), source_order)
                assert error <= 1e-12
                points.extend(starts[i]+u[:, None]*directions[i])
                weights.extend(current[i]@physical_weights)
            points, weights = np.array(points), np.array(weights)
            assert abs(math.fsum(weights)-1) <= 1e-10
            for order in (32, 64):
                nodes, laguerre_weights = np.polynomial.laguerre.laggauss(order)
                assert abs(math.fsum(laguerre_weights)-1) <= 1e-12
                k = nodes/(2*minimum_height)
                amplitudes = [np.dot(weights, np.exp(-wave*(points[:, 1]-minimum_height)
                    +1j*wave*(points[:, 0]-width/2))) for wave in k]
                ground[source_order, order] = math.fsum(laguerre_weights*abs(np.array(amplitudes))**2)/(2*np.pi*minimum_height)
        for value in ground.values():
            assert abs(value/ground[32, 64]-1) <= 1e-10
        b = math.sqrt(height**2-radius**2)
        expected = np.array([2*np.pi/np.arccosh(height/radius), height/(2*np.pi*radius*b), 1/(2*np.pi*b)])
        actual = np.array([capacitance, signal, ground[32, 64]])
        result.append(dict(vertices=vertices, physical_panels=geometry.panel_count,
            actual=actual.tolist(), expected=expected.tolist(), errors=(abs(actual-expected)/expected).tolist(),
            raw_reciprocity=half.reciprocity_error, refinement=half.quadrature_error))
    return result


@pytest.mark.parametrize('index', [0, 1, 2], ids=['capacitance', 'signal-gram', 'ground-gram'])
def test_circumscribed_polygons_approach_closed_circle(circles, index, record_property):
    errors = [row['errors'][index] for row in circles]
    assert errors[2] < errors[1] < errors[0]
    assert errors[2] <= .005
    record_property('harmonic_half_space_circle', json.dumps(circles, sort_keys=True))
