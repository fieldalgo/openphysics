# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Raw harmonic-density Green assembly: topology, energy and preserved P0 limit."""
import numpy as np
import pytest

from galerkin.laplace_corner_assembly import assemble_corner_half_space
from galerkin.laplace_corner_harmonic_assembly import assemble_harmonic_corner_half_space

W, H = .008, .002
SQUARE = np.array([[.0038,.0008],[.0042,.0008],[.0042,.0012],[.0038,.0012]])
TRIANGLE = SQUARE[[0, 1, 3]]
PAIR = [np.array([[.0032,.0006],[.00355,.0006],[.00350,.00065],[.0032,.00065]]),
        np.array([[.00425,.0011],[.00465,.0011],[.0047,.00116],[.00425,.00116]])]


def assemble(poly=SQUARE, scale=1.0, count=16):
    return assemble_harmonic_corner_half_space(
        [scale*poly], width=scale*W, height=scale*H, panels_per_edge=count)


def norm_difference(actual, expected):
    return np.max(abs(actual-expected))/np.max(abs(expected))


@pytest.fixture(scope="module", params=[SQUARE, TRIANGLE], ids=["square", "triangle"])
def sample(request):
    return request.param, assemble(request.param)


def test_raw_reciprocity_positive_energy_and_p0_subspace(sample, record_property):
    poly, result = sample
    assert result.matrix.shape == (2*result.geometry.panel_count,)*2
    assert max(result.quadrature_error, result.reciprocity_error) <= 1e-10
    for matrix in (result.coarse_matrix, result.matrix):
        assert np.isfinite(matrix).all()
        assert norm_difference(matrix, matrix.T) <= 1e-10
        assert np.linalg.eigvalsh((matrix+matrix.T)/2).min() > 0
    constant = assemble_corner_half_space([poly], width=W, height=H, panels_per_edge=16)
    assert norm_difference(result.matrix[::2,::2], constant.matrix) <= 1e-10
    record_property("harmonic_half_space", f"{len(poly)}:{result.geometry.panel_count}:"
                    f"{result.quadrature_error:.17g}:{result.reciprocity_error:.17g}")


@pytest.mark.parametrize("scale", [2.0**-15, 2.0**15])
def test_physical_scaling_preserves_dimensionless_green_matrix(sample, scale):
    poly, base = sample
    changed = assemble(poly, scale)
    assert norm_difference(changed.matrix, base.matrix) <= 1e-10
    np.testing.assert_allclose(changed.geometry.lengths_m,
                               scale*base.geometry.lengths_m, rtol=1e-12, atol=0)


def test_horizontal_reflection_maps_physical_density_modes(sample):
    poly, base = sample
    reflected = assemble(np.column_stack((W-poly[:,0], poly[:,1])))
    count = 10
    permutation = np.concatenate([
        ((len(poly)-2-face)%len(poly))*count+np.arange(count-1,-1,-1)
        for face in range(len(poly))])
    density = (2*permutation[:,None]+np.arange(2)).ravel()
    np.testing.assert_allclose(reflected.geometry.normalized_directions[permutation],
                               base.geometry.normalized_directions*[-1,1],rtol=1e-12,atol=0)
    assert norm_difference(reflected.matrix[np.ix_(density,density)], base.matrix) <= 1e-10


def test_clockwise_and_horizontal_translation_keep_half_space_geometry(sample):
    poly, base = sample
    assert np.array_equal(assemble(poly[::-1]).matrix, base.matrix)
    shifted = assemble(poly+[.0003, 0.0])
    assert norm_difference(shifted.matrix, base.matrix) <= 1e-10


@pytest.mark.parametrize("count", [16, 32])
def test_unequal_conductors_preserve_owner_permutation_and_positive_energy(count):
    base = assemble_harmonic_corner_half_space(PAIR, width=W, height=H, panels_per_edge=count)
    swapped = assemble_harmonic_corner_half_space(PAIR[::-1], width=W, height=H,
                                               panels_per_edge=count)
    panels = base.geometry.panel_count//2
    permutation = np.r_[np.arange(panels,2*panels),np.arange(panels)]
    density = (2*permutation[:,None]+np.arange(2)).ravel()
    assert norm_difference(swapped.matrix[np.ix_(density,density)], base.matrix) <= 1e-10
    assert np.linalg.eigvalsh((base.matrix+base.matrix.T)/2).min() > 0
    constant = assemble_corner_half_space(PAIR,width=W,height=H,panels_per_edge=count)
    assert norm_difference(base.matrix[::2,::2],constant.matrix) <= 1e-10


def test_snapshot_keeps_independent_immutable_arrays():
    polygon = SQUARE.copy()
    result = assemble(polygon)
    before = result.matrix.copy()
    polygon[:] = 0
    assert np.array_equal(result.matrix, before)
    for array in (result.matrix,result.coarse_matrix,result.geometry.normalized_anchors):
        with pytest.raises(ValueError): array.flat[0] = 0
        with pytest.raises(ValueError): array.flags.writeable = True


@pytest.mark.parametrize("fault", ["fine-nan", "coarse-inf", "shape", "zero", "coarse-zero",
                                  "refinement", "fine-skew", "coarse-skew"])
def test_raw_refusals_precede_any_symmetry_averaging(monkeypatch, fault):
    import galerkin.laplace_corner_harmonic_assembly as module
    def broken(geometry):
        n = 2*geometry.panel_count
        coarse = np.eye(n)
        fine = coarse.copy()
        if fault == "fine-nan": fine[0,0] = np.nan
        elif fault == "coarse-inf": coarse[0,0] = np.inf
        elif fault == "shape": fine = fine[:-1]
        elif fault == "zero": coarse[:] = 0; fine[:] = 0
        elif fault == "coarse-zero": coarse[:] = 0
        elif fault == "refinement": coarse[0,0] += 1e-6
        elif fault == "fine-skew": fine[0,1] = 1e-6
        else: coarse[0,1] = 1e-6
        return coarse, fine
    monkeypatch.setattr(module,"_assemble",broken)
    with pytest.raises(ValueError): assemble()


def test_physical_panel_limit_is_checked_before_dense_allocation(monkeypatch):
    import galerkin.laplace_corner_harmonic_assembly as module
    def forbidden(*args): raise AssertionError("assembly must not begin")
    monkeypatch.setattr(module,"_assemble",forbidden)
    with pytest.raises(ValueError,match="512 physical panels"):
        assemble(count=256)


@pytest.mark.parametrize("polygons,width,height,count", [
    ([],W,H,16),([SQUARE,SQUARE],W,H,16),([SQUARE],0,H,16),
    ([SQUARE],W,0,16),([SQUARE],W,H,17),([SQUARE],W,H,14),
    ([SQUARE],W,H,True),([SQUARE],W,H,514),([SQUARE-[0,.001]],W,H,16),
])
def test_existing_geometry_contract_remains_required(polygons,width,height,count):
    with pytest.raises(ValueError):
        assemble_harmonic_corner_half_space(polygons,width=width,height=height,panels_per_edge=count)


def test_unresolved_pair_error_identifies_panel_indices(monkeypatch):
    import galerkin.laplace_corner_harmonic_assembly as module
    def unresolved(*args,**kwargs): raise ValueError("reference refinement unresolved")
    monkeypatch.setattr(module,"_block",unresolved)
    with pytest.raises(ValueError,match="harmonic panel pair 0/0: reference refinement unresolved"):
        assemble()
