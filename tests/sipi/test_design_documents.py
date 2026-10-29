# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Input reproducibility, design failure boundaries and independent stripline target."""

import numpy as np
import pytest
from scipy.optimize import brentq

from sipi import (CrossSection, CrossSectionDocument, Layer, Trace, GoalSeekError,
                  microstrip, stripline, coupled_microstrip, grounded_coplanar,
                  seek_impedance)


@pytest.mark.parametrize('factory,kwargs,explicit', [
    (microstrip, dict(width=0.5e-3, substrate_height=1e-3, eps_r=4),
     CrossSection([Layer('substrate', 1e-3, 4), Layer('air', 10e-3)],
                  [Trace('signal', 0, .5e-3, 1e-3)], 20e-3)),
    (stripline, dict(width=0.5e-3, plane_spacing=1e-3, eps_r=4),
     CrossSection([Layer('dielectric', 1e-3, 4)],
                  [Trace('signal', 0, .5e-3, .5e-3)], 12e-3, top='ground')),
    (coupled_microstrip, dict(width=.5e-3, gap=.2e-3, substrate_height=1e-3, eps_r=4),
     CrossSection([Layer('substrate', 1e-3, 4), Layer('air', 10e-3)],
                  [Trace('positive', -.35e-3, .5e-3, 1e-3),
                   Trace('negative', .35e-3, .5e-3, 1e-3)], 20e-3)),
    (grounded_coplanar, dict(width=.5e-3, gap=.2e-3, ground_width=1e-3,
                            substrate_height=1e-3, eps_r=4),
     CrossSection([Layer('substrate', 1e-3, 4), Layer('air', 10e-3)],
                  [Trace('signal', 0, .5e-3, 1e-3),
                   Trace('ground_left', -.95e-3, 1e-3, 1e-3, ground=True),
                   Trace('ground_right', .95e-3, 1e-3, 1e-3, ground=True)], 20e-3)),
])
def test_templates_match_explicit_geometry_and_document_roundtrip(factory, kwargs, explicit):
    options = dict(edge_size=5e-6, far_size=.5e-3, grade=.2)
    doc = CrossSectionDocument(factory(**kwargs), mesh=options)
    direct = CrossSectionDocument(explicit, mesh=options)
    # Floats that have distinct arithmetic spellings need numeric comparison.
    a, b = doc.section, direct.section
    assert a.layers == b.layers
    np.testing.assert_allclose([[t.x, t.width, t.y] for t in a.traces],
                               [[t.x, t.width, t.y] for t in b.traces], rtol=1e-15)
    restored = CrossSectionDocument.loads(doc.dumps())
    assert restored.to_dict() == doc.to_dict()
    first, second = doc.analyze(), restored.analyze()
    assert first.names == second.names
    for name in ('C', 'C0', 'L', 'C_loss'):
        # Identical validated inputs through the same deterministic engine.
        np.testing.assert_array_equal(getattr(first, name), getattr(second, name))
    manual = direct.analyze()
    np.testing.assert_allclose(first.C, manual.C, rtol=1e-12)


def sample():
    return CrossSectionDocument(microstrip(width=.5e-3, substrate_height=1e-3, eps_r=4))


@pytest.mark.parametrize('path,value', [
    (('schema',), 'sipi.cross-section/2'), (('length_unit',), 'mm'),
    (('extra',), 1), (('layers',), []), (('traces',), []),
    (('layers', 0, 'thickness'), True), (('layers', 0, 'eps_r'), float('inf')),
    (('traces', 0, 'ground'), 0), (('traces', 0, 'width'), '0.001'),
    (('traces', 0, 'name'), {}), (('traces', 0, 'y'), 0),
    (('box', 'top'), []), (('box', 'width'), float('nan')),
    (('mesh', 'grade'), -1), (('mesh', 'grade'), True),
    (('mesh', 'min_angle'), 34), (('mesh', 'far_size'), 1e-12),
    (('mesh', 'unknown'), 1), (('mesh', 'edge_size'), None),
])
def test_document_rejects_ambiguous_or_unsupported_input(path, value):
    data = sample().to_dict()
    cursor = data
    for item in path[:-1]:
        cursor = cursor[item]
    cursor[path[-1]] = value
    with pytest.raises(ValueError):
        CrossSectionDocument.from_dict(data)


@pytest.mark.parametrize('text', ['{"schema":1,"schema":2}', '{"x":NaN}', '{"x":Infinity}'])
def test_json_duplicates_and_nonfinite_are_not_silently_decoded(text):
    with pytest.raises(ValueError):
        CrossSectionDocument.loads(text)


def test_document_snapshots_inputs_and_accessors():
    original = sample()
    raw = original.to_dict()
    doc = CrossSectionDocument.from_dict(raw)
    raw['traces'][0]['width'] = 2e-3
    output = doc.to_dict()
    output['layers'][0]['eps_r'] = 10
    doc.section.width = 1
    doc.mesh_options['grade'] = 1
    assert doc.dumps() == original.dumps()


@pytest.mark.parametrize('options', [dict(width=True), dict(width=float('inf')),
                                    dict(thickness=-1), dict(eps_r=True), dict(air_height=0)])
def test_templates_reject_invalid_parameters(options):
    kwargs = dict(width=.5e-3, substrate_height=1e-3, eps_r=4)
    kwargs.update(options)
    with pytest.raises(ValueError):
        microstrip(**kwargs)


@pytest.mark.parametrize('options', [dict(grade=float('nan')), dict(far_size=float('inf')),
                                    dict(edge_size=True), dict(min_angle=0), dict(grade=-1)])
def test_mesh_settings_rejects_invalid_values_before_generation(options):
    with pytest.raises(ValueError):
        sample().section.mesh_settings(**options)


def test_stripline_goal_matches_independent_cohn_width():
    from test_sipi_references import stripline_z0
    b, er, target = 1e-3, 4.0, 50.0
    expected = brentq(lambda w: stripline_z0(w, b, er)-target, .3e-3, .8e-3,
                      xtol=1e-14)
    result = seek_impedance(lambda w: stripline(width=w, plane_spacing=b, eps_r=er),
                            (.3e-3, .8e-3), target,
                            mesh=dict(edge_size=.5e-6, far_size=.125e-3, grade=.075),
                            tolerance=.1, max_evaluations=20)
    assert result.parameter == pytest.approx(expected, rel=1e-2)
    assert abs(result.residual) <= .1
    assert abs(result.refined_residual) <= .1
    assert result.document.analyze().z0 == result.impedance
    assert result.history[-1].stage == 'refinement'
    assert len(result.history) <= 20


def fake_line(z):
    class Line:
        z0 = z
        def even_odd(self):
            return {'z_diff': 2*z}
    return Line()


def test_search_bracket_budget_endpoint_and_refinement_failure(monkeypatch):
    # Isolate algorithm failure boundaries; the preceding test uses the real FEM.
    monkeypatch.setattr(CrossSection, 'analyze', lambda self, **kw: fake_line(1/self.traces[0].width))
    factory = lambda w: stripline(width=w, plane_spacing=10, eps_r=4)
    with pytest.raises(GoalSeekError, match='not bracketed') as err:
        seek_impedance(factory, (1, 2), 5)
    assert len(err.value.history) == 2
    with pytest.raises(GoalSeekError, match='evaluation limit') as err:
        seek_impedance(factory, (1, 2), .7, tolerance=1e-8, max_evaluations=3)
    assert len(err.value.history) == 2
    result = seek_impedance(factory, (1, 2), 1, tolerance=1e-8, max_evaluations=3)
    assert result.parameter == 1
    assert len(result.history) == 3
    assert seek_impedance(factory, (1, 2), 2, quantity='z_diff').quantity == 'z_diff'
    def inconsistent(self, **kw):
        return fake_line(2 if kw.get('grade') == .075 else 1/self.traces[0].width)
    monkeypatch.setattr(CrossSection, 'analyze', inconsistent)
    with pytest.raises(GoalSeekError, match='refined mesh misses') as err:
        seek_impedance(factory, (1, 2), 1, tolerance=.01)
    assert err.value.history[-1].stage == 'refinement'


@pytest.mark.parametrize('kwargs', [dict(bounds=(2, 1)), dict(bounds=(0, 1)),
                                   dict(bounds=(1, float('inf'))), dict(bounds=(1, 2, 3)),
                                   dict(target=True), dict(tolerance=0),
                                   dict(quantity='even'), dict(max_evaluations=True)])
def test_search_rejects_invalid_controls(kwargs):
    params = dict(bounds=(1, 2), target=1)
    params.update(kwargs)
    with pytest.raises(ValueError):
        seek_impedance(lambda w: sample().section, **params)
