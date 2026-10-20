# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The end-to-end pipeline itself: mesher -> engine -> reference.

examples/galerkin/rib_waveguide_scalar.py and rib_waveguide_vector.py are wiring
checks — meshine builds the mesh, galerkin assembles and solves, refsol grades.
These tests gate the wiring, not the physics: the physics gates for this geometry
live in test_hadley.py.

What is deliberately NOT asserted here is that the two models bracket Hadley's
value. They do once each is converged (the scalar settles about +2.5e-4 above,
the vector approaches from below), but at a mesh cheap enough for a test the
scalar has not reached its own limit: measured at h = 0.08 its error runs from
+1.3e-4 at slab 0 down through zero to -2.9e-5 at slab 0.7, so it crosses the
reference for reasons that have nothing to do with the model being right.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "examples" / "galerkin"))

pytest.importorskip("meshine")

H_COARSE = 0.08


@pytest.fixture(scope="module")
def scalar():
    import rib_waveguide_scalar
    return rib_waveguide_scalar


@pytest.fixture(scope="module")
def vector():
    import rib_waveguide_vector
    return rib_waveguide_vector


def test_scalar_pipeline_runs_end_to_end(refsol, scalar):
    ref = refsol.benchmarks.rib_neff(0.3)
    tm, mesh, neff, fields, _, _ = scalar.run(0.3, H_COARSE)
    assert tm.num_triangles > 1000
    assert mesh.region_names == ["core", "box", "clad"]
    assert abs(neff[0] - ref) < 5e-4, f"{neff[0]:.6f} vs {ref}"
    assert fields.shape == (mesh.num_nodes, 2)


def test_vector_pipeline_runs_end_to_end(refsol, vector):
    ref = refsol.benchmarks.rib_neff(0.3)
    tm, mesh, neff, (space, et, ez), _, _ = vector.run(0.3, H_COARSE)
    assert mesh.region_names == ["core", "box", "clad"]
    assert abs(neff[0] - ref) < 5e-4, f"{neff[0]:.6f} vs {ref}"
    assert et.shape[1] == space.num_edges and ez.shape[1] == mesh.num_nodes


def test_the_two_pipelines_differ_only_in_the_solver(scalar, vector):
    """Same mesher, same adapter, same materials — so the meshes must be identical
    and only the eigenproblem different."""
    tm_s, mesh_s, ns, _, _, _ = scalar.run(0.3, H_COARSE)
    tm_v, mesh_v, nv, _, _, _ = vector.run(0.3, H_COARSE)
    assert tm_s.num_triangles == tm_v.num_triangles
    assert np.allclose(mesh_s.nodes, mesh_v.nodes)
    assert np.array_equal(mesh_s.regions, mesh_v.regions)
    assert abs(ns[0] - nv[0]) > 1e-5, (
        "the two solvers returned the same number — the vector one is probably "
        "not being exercised")


@pytest.mark.slow
def test_vector_error_is_uniform_across_the_slab_family(refsol, vector):
    """At a fixed mesh the vector solver's error should barely move across the
    eight slab thicknesses; a model or wiring fault would show up as one case
    drifting away from the rest.

    Measured at h = 0.08: -1.62e-4 to -1.23e-4, a spread of 3.9e-5, against a
    scalar spread of 1.6e-4 over the same family.
    """
    errors = []
    for case in refsol.benchmarks.RIB_WAVEGUIDES:
        neff = vector.run(case.slab_thickness_um, H_COARSE)[2]
        assert len(neff), f"slab {case.slab_thickness_um}: no guided mode"
        errors.append(neff[0] - case.neff_quasi_te)
    errors = np.array(errors)
    assert (errors < 0).all(), (
        f"the vector solver should sit below the reference at this resolution: "
        f"{errors}")
    assert errors.max() - errors.min() < 8e-5, (
        f"error spread {errors.max()-errors.min():.2e} across the family: "
        f"{errors}")
