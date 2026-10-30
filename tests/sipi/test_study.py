# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Analytical statistics, independent sampling and actual impedance composition."""

import numpy as np
import pytest
from scipy import stats

from sipi import CrossSectionDocument
from sipi.study import ImpedanceStudyDocument
from sipi.templates import coupled_microstrip


PARAMETERS = dict(width=.4e-3, substrate_height=.5e-3, eps_r=4,
                  thickness=0, air_height=1e-3, box_width=4e-3)
MESH = dict(edge_size=.1e-3, far_size=.4e-3, grade=.3)


def bounded(kind='sweep', count=3):
    s = dict(kind=kind, variables=[dict(name='width', lower=.3e-3, upper=.5e-3)])
    if kind != 'corners':
        s['count'] = count
    if kind == 'uniform':
        s['seed'] = 123
    return s


def document(sampling=None, **kwargs):
    return ImpedanceStudyDocument('microstrip', PARAMETERS,
        sampling=bounded() if sampling is None else sampling, quantity='z0', mesh=MESH, **kwargs)


def normal(count=10000):
    return dict(kind='normal', count=count, seed=771,
        variables=[dict(name='width', mean=.4e-3, std=.02e-3), dict(name='eps_r', mean=4., std=.1)],
        correlation=[[1., .6], [.6, 1.]])


@pytest.mark.parametrize('kind', ['sweep', 'corners', 'uniform', 'normal'])
def test_sampling_roundtrip_snapshot_and_shapes(kind):
    sampling = normal(100) if kind == 'normal' else bounded(kind, 100)
    doc = document(sampling)
    restored = ImpedanceStudyDocument.loads(doc.dumps())
    assert restored.dumps() == doc.dumps()
    np.testing.assert_array_equal(doc.samples(), restored.samples())
    assert not doc.samples().flags.writeable
    sampling['variables'][0]['name'] = 'wrong'
    copy_out = doc.to_dict()
    copy_out['parameters']['width'] = 99
    assert doc.dumps() == restored.dumps()
    if kind in ('sweep', 'corners'):
        np.testing.assert_array_equal(doc.samples()[[0, -1], 0], [.3e-3, .5e-3])
    elif kind == 'uniform':
        assert np.all((doc.samples()[:, 0] >= .3e-3) & (doc.samples()[:, 0] <= .5e-3))


def test_corners_have_full_cartesian_product_in_named_order():
    s = bounded('corners')
    s['variables'].append(dict(name='eps_r', lower=3.5, upper=4.5))
    np.testing.assert_array_equal(document(s).samples(),
        [[.3e-3, 3.5], [.3e-3, 4.5], [.5e-3, 3.5], [.5e-3, 4.5]])


def test_correlated_normal_against_moments_and_scipy_reference():
    spec = normal()
    samples = document(spec).samples()
    mean, std = np.array([.4e-3, 4.]), np.array([.02e-3, .1])
    z = (samples-mean)/std
    reference = stats.multivariate_normal(mean=[0, 0], cov=spec['correlation']).rvs(
        size=10000, random_state=np.random.default_rng(817))
    for values in (z, reference):
        assert np.max(abs(values.mean(axis=0))) <= 6/np.sqrt(len(values))
        assert np.max(abs(np.cov(values.T)-np.array(spec['correlation']))) <= .08
        # Independent normal CDF, fixed acceptance rather than a fitted histogram.
        for column in values.T:
            assert stats.kstest(column, 'norm').statistic < .03
    print('normalized mean', z.mean(axis=0), 'covariance', np.cov(z.T))


def test_perfect_correlation_is_supported_without_extra_noise():
    spec = normal(100)
    spec['correlation'] = [[1, -1], [-1, 1]]
    z = (document(spec).samples()-[.4e-3, 4])/[.02e-3, .1]
    np.testing.assert_allclose(z[:, 0], -z[:, 1], rtol=0, atol=1e-12)


def test_fixed_pitch_preserves_trace_centres_and_computes_gap():
    params = dict(PARAMETERS, gap=.3e-3)
    doc = ImpedanceStudyDocument('coupled_microstrip', params, sampling=bounded(),
                                 quantity='z_diff', mesh=MESH, fixed_pitch_m=.7e-3)
    for row in doc.sample_parameters():
        assert row['width']+row['gap'] == pytest.approx(.7e-3, rel=1e-12)
        section = coupled_microstrip(**row)
        assert section.traces[1].x-section.traces[0].x == pytest.approx(.7e-3, rel=1e-12)
        assert row['gap'] > 0


@pytest.mark.parametrize('coupled', [False, True])
def test_actual_impedance_and_direct_saved_document(coupled):
    params = dict(PARAMETERS, **({'gap': .3e-3} if coupled else {}))
    doc = ImpedanceStudyDocument('coupled_microstrip' if coupled else 'microstrip', params,
        sampling=bounded(count=2), quantity='z_diff' if coupled else 'z0', mesh=MESH,
        fixed_pitch_m=.7e-3 if coupled else None)
    out = ImpedanceStudyDocument.loads(doc.dumps()).analyze()
    assert out.failed == 0 and len(out.rows) == 2
    assert out.input_json == doc.dumps()
    for row in out.rows:
        assert row.complete and row.document is not None and row.error_type is None
        direct = CrossSectionDocument.loads(row.document.dumps()).analyze()
        reference = direct.even_odd()['z_diff'] if coupled else direct.z0
        assert row.impedance == pytest.approx(reference, rel=1e-10)
        with pytest.raises(TypeError):
            row.parameters['width'] = 1
    assert out.summary['minimum'] == min(r.impedance for r in out.rows)
    assert out.summary['maximum'] == max(r.impedance for r in out.rows)
    with pytest.raises(TypeError):
        out.summary['mean'] = 0


def test_invalid_normal_geometry_preserved_without_resampling():
    spec = normal(3)
    spec['variables'][0].update(mean=-.4e-3, std=1e-9)
    doc = document(spec)
    assert np.all(doc.samples()[:, 0] < 0)
    out = doc.analyze()
    assert out.failed == 3 and out.summary is None and len(out.rows) == 3
    for row, sample in zip(out.rows, doc.samples()):
        assert row.parameters['width'] == sample[0]
        assert row.document is None and row.impedance is None
        assert row.error_type == 'ValueError'


def test_solver_failure_row_retained_and_no_partial_summary(monkeypatch):
    original = CrossSectionDocument.analyze
    def fail_one(self):
        if self.section.traces[0].width > .4e-3:
            raise RuntimeError('controlled solver failure')
        return original(self)
    monkeypatch.setattr(CrossSectionDocument, 'analyze', fail_one)
    out = document(bounded(count=2)).analyze()
    assert out.failed == 1 and out.summary is None
    assert out.rows[0].complete and not out.rows[1].complete
    assert out.rows[1].error == 'controlled solver failure'
    assert out.rows[1].document is not None


def test_budget_rejects_before_solving(monkeypatch):
    def forbidden(self):
        pytest.fail('budget was not checked before FEM')
    monkeypatch.setattr(CrossSectionDocument, 'analyze', forbidden)
    with pytest.raises(ValueError, match='max_evaluations'):
        document(bounded(count=3)).analyze(max_evaluations=2)


@pytest.mark.parametrize('correlation', [[[1, 1.1], [1.1, 1]], [[1, .6], [.5, 1]],
    [[2, 0], [0, 1]], [[1]], [[True, 0], [0, 1]], [[1, float('nan')], [0, 1]]])
def test_invalid_correlation(correlation):
    spec = normal()
    spec['correlation'] = correlation
    with pytest.raises(ValueError):
        document(spec)


@pytest.mark.parametrize('edit', [
    lambda d: d.update(schema='sipi.impedance-study/2'),
    lambda d: d.update(extra=1),
    lambda d: d.update(mesh=None),
    lambda d: d.update(template='eval'),
    lambda d: d.update(quantity='z_diff'),
    lambda d: d['parameters'].update(extra=1),
    lambda d: d['parameters'].update(width=True),
    lambda d: d['sampling'].update(count=True),
    lambda d: d['sampling'].update(count=1),
    lambda d: d['sampling'].update(count=10001),
    lambda d: d['sampling'].update(seed=1),
    lambda d: d['sampling'].update(variables=[]),
    lambda d: d['sampling']['variables'][0].update(name='unknown'),
    lambda d: d['sampling']['variables'][0].update(lower=-1),
    lambda d: d['sampling']['variables'][0].update(lower=True),
    lambda d: d['sampling']['variables'][0].update(lower=.8e-3),
    lambda d: d.update(fixed_pitch_m=.7e-3),
])
def test_invalid_plan(edit):
    data = document().to_dict()
    edit(data)
    with pytest.raises((ValueError, TypeError)):
        ImpedanceStudyDocument.from_dict(data)


@pytest.mark.parametrize('pitch,variable', [(.8e-3, 'width'), (.7e-3, 'gap'), (True, 'width')])
def test_invalid_pitch_contract(pitch, variable):
    s = bounded()
    s['variables'][0]['name'] = variable
    with pytest.raises(ValueError):
        ImpedanceStudyDocument('coupled_microstrip', dict(PARAMETERS, gap=.3e-3),
            sampling=s, quantity='z_diff', fixed_pitch_m=pitch)


@pytest.mark.parametrize('text', ['{"schema":1,"schema":2}', '{"sampling":{"x":1,"x":2}}',
                                  '{"x":NaN}', '{"x":Infinity}'])
def test_invalid_json(text):
    with pytest.raises(ValueError):
        ImpedanceStudyDocument.loads(text)


@pytest.mark.parametrize('edit', [
    lambda s: s.update(seed=-1),
    lambda s: s.update(seed=True),
    lambda s: s.update(seed=2**32),
    lambda s: s['variables'][0].update(std=0),
    lambda s: s['variables'][0].update(std=-1),
    lambda s: s['variables'][1].update(name='width'),
])
def test_invalid_normal_sampling_inputs(edit):
    spec = normal()
    edit(spec)
    with pytest.raises(ValueError):
        document(spec)


def test_bounded_fixed_pitch_cannot_cross_zero_gap():
    s = bounded()
    s['variables'][0]['upper'] = .8e-3
    with pytest.raises(ValueError, match='gap'):
        ImpedanceStudyDocument('coupled_microstrip', dict(PARAMETERS, gap=.3e-3),
            sampling=s, quantity='z_diff', fixed_pitch_m=.7e-3)
