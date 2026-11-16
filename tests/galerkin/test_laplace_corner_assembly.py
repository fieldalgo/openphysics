# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Half-space Green invariants and independent normalized-density entries."""
import numpy as np
import pytest
from galerkin.laplace_corner_assembly import assemble_corner_half_space

W,H=.008,.002
SQUARE=np.array([[.0038,.0008],[.0042,.0008],[.0042,.0012],[.0038,.0012]])
TRIANGLE=np.array([[.0038,.0008],[.0042,.0008],[.0038,.0012]])


def assemble(poly=SQUARE,scale=1.,count=16):
    return assemble_corner_half_space([scale*poly],width=scale*W,height=scale*H,
        panels_per_edge=count)


@pytest.fixture(scope='module',params=[SQUARE,TRIANGLE],ids=['square','triangle'])
def sample(request):return request.param,assemble(request.param)


def test_raw_reciprocity_and_positive_green_energy(sample,record_property):
    poly,result=sample
    assert result.quadrature_error<=1e-10 and result.reciprocity_error<=1e-10
    for matrix in (result.coarse_matrix,result.matrix):
        assert np.isfinite(matrix).all() and np.min(matrix)>0
        assert np.max(abs(matrix-matrix.T))/np.max(abs(matrix))<=1e-10
        assert np.linalg.eigvalsh((matrix+matrix.T)/2).min()>0
    record_property('half_space_energy',f'{len(poly)}:{result.geometry.panel_count}:{result.quadrature_error:.17g}:{result.reciprocity_error:.17g}')


@pytest.mark.parametrize('scale',[1e-6,2.,1e6])
def test_dimensionless_green_matrix_is_invariant_under_physical_scaling(sample,scale):
    poly,base=sample;changed=assemble(poly,scale)
    np.testing.assert_allclose(changed.matrix,base.matrix,rtol=1e-10,atol=0)
    np.testing.assert_allclose(changed.geometry.lengths_m,scale*base.geometry.lengths_m,rtol=1e-12,atol=0)


def test_horizontal_reflection_preserves_corresponding_densities(sample):
    poly,base=sample;reflected=assemble(np.column_stack((W-poly[:,0],poly[:,1])))
    n=10;permutation=np.concatenate([((len(poly)-2-face)%len(poly))*n+np.arange(n-1,-1,-1) for face in range(len(poly))])
    np.testing.assert_allclose(reflected.matrix[np.ix_(permutation,permutation)],base.matrix,rtol=1e-10,atol=0)


def test_horizontal_translation_and_clockwise_input(sample):
    poly,base=sample;translated=assemble(poly+[.0003,0.])
    np.testing.assert_allclose(translated.matrix,base.matrix,rtol=1e-10,atol=0)
    assert np.array_equal(assemble(poly[::-1]).matrix,base.matrix)


def test_snapshot_is_immutable_and_independent_of_inputs():
    poly=SQUARE.copy();result=assemble(poly);before=result.matrix.copy();poly[:]=0
    assert np.array_equal(result.matrix,before)
    for value in (result.matrix,result.coarse_matrix,result.geometry.normalized_anchors):
        with pytest.raises(ValueError):value.flat[0]=0
        with pytest.raises(ValueError):value.flags.writeable=True


@pytest.mark.parametrize('fault',['fine-nan','coarse-inf','zero','refinement','raw-skew'])
def test_unresolved_raw_matrix_is_refused_before_symmetry_averaging(monkeypatch,fault):
    import galerkin.laplace_corner_assembly as module
    def broken(a,b,p,g):
        x=np.ones((len(a),len(a)));y=x.copy()
        if fault=='fine-nan':y[0,0]=np.nan
        elif fault=='coarse-inf':x[0,0]=np.inf
        elif fault=='zero':x[:]=0;y[:]=0
        elif fault=='refinement':x[0,0]+=1e-6
        else:x[0,1]+=1e-6;y[0,1]+=1e-6
        return x,y
    monkeypatch.setattr(module,'_half',broken)
    with pytest.raises(ValueError):assemble()


# Independent direct 2D density-removing integration at 60/80 decimal digits.
# mpmath 1.3.0 BSD-3-Clause is an unshipped reference tool.
# Generator SHA256: ce97127f6016e4ebd5d3a94461ae1055e8115e010b9d9158390579dac103ade6
@pytest.mark.parametrize('indices,expected', [([0, 39], '5.3720234092909177675422931238680439746394298544003664268485003457982302078497565'), ([0, 10], '1.4334171764867480186047916923507125534768976165912285595966812567364343769453542'), ([5, 15], '1.8584937392471497804191256475597489728466178468453027835414978097739924524080731')])
def test_independent_high_precision_half_space_entries(indices,expected):
    result=assemble();i,j=indices
    assert abs(result.matrix[i,j]-float(expected))<=1e-12*max(1,abs(float(expected)))


@pytest.mark.parametrize('reflect',[False,True])
def test_short_far_panels_keep_local_distance_precision(reflect):
    from galerkin.laplace_corner_assembly import _constant_half
    g={k:np.array(v) for k,v in {'anchor': [[0.46875, 0.08124999999999999], [0.46875, 0.08124999999999999]], 'local': [[2.8280723736314326e-07, -5.656144747262877e-07], [-1.4997120552853865e-07, 0.0]], 'direction': [[4.2326296825876764e-08, -8.465259365175371e-08], [-6.483773501168677e-08, 0.0]]}.items()}
    g.update(starts=np.array([1,3]),ends=np.array([2,4]))
    if reflect:
        g['anchor'][:,0]=1-g['anchor'][:,0]
        g['local'][:,0]*=-1;g['direction'][:,0]*=-1
    a=g['anchor']+g['local']
    reference=float('12.249251728225946324120722408012234275468376748233147426323856556862492461822424')
    for order in (6,8):
        value=_constant_half(a,g,order)[0,1]
        assert abs(value-reference)<=1e-12*abs(reference)


def test_compensated_displacements_against_independent_fsum():
    import math
    from galerkin.laplace_corner_assembly import _relative_displacements
    rng=np.random.default_rng(20261116)
    anchor=rng.uniform(.25,.75,(64,2));local=rng.uniform(-1e-6,1e-6,(64,2))
    anchor[:3]=.5;local[:3]=np.array([[0,0],[2.**-60,2.**-100],[2.**-61,2.**-101]])
    result=_relative_displacements(dict(anchor=anchor,local=local),slice(None))
    expected=np.array([[[math.fsum((anchor[j,k],-anchor[i,k],local[j,k],-local[i,k])) for k in range(2)] for j in range(64)] for i in range(64)])
    magnitude=abs(anchor[None])+abs(anchor[:,None])+abs(local[None])+abs(local[:,None])
    assert np.all(abs(result-expected)<=4*np.finfo(float).eps**2*magnitude+np.spacing(abs(expected)))
    assert np.array_equal(result[:3,:3],expected[:3,:3])
