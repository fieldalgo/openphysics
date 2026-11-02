# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""refsol.thermal3d checks itself: flux and source by finite differences, the slab by series resistance."""
import ast
import pathlib

import numpy as np
import pytest

from refsol import thermal3d


def test_sine_product_flux_and_source_match_finite_differences():
    rng = np.random.default_rng(1)
    p = rng.random((20, 3)) * [1.0, 0.8, 0.6]
    kw = dict(lengths=(1.0, 0.8, 0.6), conductivity=2.0, reference_temperature=300.0, amplitude=5.0)
    f = thermal3d.sine_product(p, **kw)
    h = 1e-5

    def T(q):
        return thermal3d.sine_product(q, **kw).temperature
    grad = np.stack([(T(p + h * np.eye(3)[i]) - T(p - h * np.eye(3)[i])) / (2 * h) for i in range(3)], axis=1)
    assert np.abs(-2.0 * grad - f.heat_flux).max() < 1e-6
    lap = sum((T(p + h * np.eye(3)[i]) - 2 * T(p) + T(p - h * np.eye(3)[i])) / h ** 2 for i in range(3))
    assert np.abs(-2.0 * lap - f.heat_source).max() < 1e-2 * np.abs(f.heat_source).max()
    faces = np.array([[0, 0.3, 0.2], [1.0, 0.3, 0.2], [0.4, 0, 0.1], [0.4, 0.8, 0.1], [0.2, 0.2, 0], [0.2, 0.2, 0.6]])
    assert np.allclose(thermal3d.sine_product(faces, **kw).temperature, 300.0)


def test_layered_slab_is_the_series_resistance_formula():
    z = np.array([[0, 0, 0.0], [0, 0, 1.0], [0, 0, 1.5], [0, 0, 2.5], [0.3, 0.4, 1.25]])
    g = thermal3d.layered_slab(z, interfaces=[1.0, 1.5, 2.5], conductivities=[1.0, 0.01, 1.0],
                               bottom_temperature=0.0, top_temperature=1.0)
    flux = -1.0 / (1.0 + 50.0 + 1.0)
    assert np.allclose(g.heat_flux[:, 2], flux) and np.all(g.heat_flux[:, :2] == 0)
    assert np.allclose(g.temperature, [0.0, -flux, -flux * 51, 1.0, -flux * (1 + 25)])
    assert np.all(g.heat_source == 0)
    with pytest.raises(ValueError, match="increase"):
        thermal3d.layered_slab(z, interfaces=[1.0, 1.0], conductivities=[1, 1], bottom_temperature=0, top_temperature=1)
    with pytest.raises(ValueError, match="within the stack"):
        thermal3d.layered_slab(np.array([[0, 0, 3.0]]), interfaces=[1.0], conductivities=[1.0],
                               bottom_temperature=0, top_temperature=1)


def test_module_imports_no_engine():
    source = pathlib.Path(thermal3d.__file__).read_text(encoding="utf-8")
    imported = {n.names[0].name.split(".")[0] if isinstance(n, ast.Import) else (n.module or "").split(".")[0]
                for n in ast.walk(ast.parse(source)) if isinstance(n, (ast.Import, ast.ImportFrom))}
    assert imported <= {"dataclasses", "numpy"}
