# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Mechanics documents on named material regions (geometry order 1-c).

Pre-registered checks R1 to R7 (HQ work record, 2026-11-08; R0, the rectangle documents
hash-identical before and after, is a measurement recorded there): a region document run
equals the direct galerkin calls (R1); two layers in series (R2) and in parallel (R3) against
closed-form stiffness; Lame's thick cylinder through ``boundary_tags`` and a gauge pressure
(R4); thermoelastic bilayers against closed forms (R5); refusals by name (R6); mesh limits
(R7). Thresholds are gates: never loosen them.

The documents are format 0.3 (units batch C7): every value carries its unit and each geometry
component its length_unit; galerkin receives the same SI values as before.
"""
import copy
import json
import math

import numpy as np
import pytest

from simcase import Document, DocumentError, MeshLimitError, examples, run
from simcase.cli import main
from simcase.mechanics_regions import is_region_mechanics
from simcase.thermal_regions import build_region_mesh_03

STEEL = {'youngs_modulus': 200e9, 'poisson_ratio': 0.0, 'linear_expansion_coefficient': 12e-6,
         'thermal_conductivity': 45.0}
ALU = {'youngs_modulus': 70e9, 'poisson_ratio': 0.0, 'linear_expansion_coefficient': 23e-6,
       'thermal_conductivity': 237.0}


def q(value, unit):
    """A quantity string with the exact double: ``repr`` digits and a unit."""
    return f'{float(value)!r} {unit}'


def disp(sides):
    """{boundary: {component: metres}} -> a prescribed_displacement object."""
    return {tag: {c: q(v, 'm') for c, v in components.items()} for tag, components in sides.items()}


def trac(sides):
    """{boundary: [tx, ty] in Pa} -> a traction object."""
    return {tag: [q(v, 'Pa') for v in vector] for tag, vector in sides.items()}


def temps(sides):
    return {tag: q(v, 'K') for tag, v in sides.items()}


def material(spec, nu):
    return {'youngs_modulus': q(spec['youngs_modulus'], 'Pa'), 'poisson_ratio': nu,
            'linear_expansion_coefficient': q(spec['linear_expansion_coefficient'], '1/K'),
            'thermal_conductivity': q(spec['thermal_conductivity'], 'W/(m K)')}


def layered(kind='mechanics.elasticity2d', *, split='x', v1=True, plane='stress', size=5.0, nu=0.0,
            units='mm', **physics):
    """A 100 x 20 bar of steel with an aluminium layer: x >= 60 (split x) or y >= 10 (split y)."""
    layer = (dict(x=60.0, y=0.0, w=40.0, h=20.0) if split == 'x' else dict(x=0.0, y=10.0, w=100.0, h=10.0))
    feature = dict(name='alu', type='rect', material='aluminium', **layer)
    domain = dict(xmin=0.0, xmax=100.0, ymin=0.0, ymax=20.0)
    if v1:
        geometry = {'version': 1, 'components': {'main': dict(dimension='2d', length_unit=units, depth=None,
                    domain=domain, background={'material': 'steel'}, features=[feature], finalize='later_wins')}}
    else:
        geometry = {'length_unit': units, 'depth': None, 'domain': domain, 'background': {'material': 'steel'},
                    'shapes': [feature]}
    p = dict(type=kind, plane=plane, **physics)
    if kind == 'mechanics.thermoelastic2d':
        p.setdefault('stress_free_temperature', '300.0 K')
    return dict(openphysics='0.3', name='layers', geometry=geometry,
                materials={'steel': material(STEEL, nu), 'aluminium': material(ALU, nu)},
                mesh={'element_size': q(size, units)}, physics={'bar': p})


A, B, P, E_PIPE, NU_PIPE = 3.0, 9.0, 1e6, 200e9, 0.3


def pipe(size, **physics):
    """A quarter of a thick pipe (radii 3 and 9 mm) with ``inner`` and ``rim`` boundary tags."""
    comp = dict(dimension='2d', length_unit='mm', depth=None, domain=dict(xmin=0.0, xmax=B, ymin=0.0, ymax=B),
                background={'material': 'steel'},
                features=[dict(name='cut', type='rect', x=0.0, y=0.0, w=B, h=B, material=None),
                          dict(name='disc', type='circle', cx=0.0, cy=0.0, r=B, material='steel'),
                          dict(name='hole', type='circle', cx=0.0, cy=0.0, r=A, material=None)],
                finalize='later_wins',
                boundary_tags=[{'tag': 'inner', 'select': {'boundary': {'of': 'hole'}}},
                               {'tag': 'rim', 'select': {'boundary': {'between': ['disc', 'cut']}}}],
                selections={'bore': {'boundary': {'of': 'hole'}}})
    p = dict(type='mechanics.elasticity2d', plane='strain',
             prescribed_displacement=disp({'left': {'x': 0.0}, 'bottom': {'y': 0.0}}), gauge_pressure={'inner': q(P, 'Pa')})
    p.update(physics)
    return dict(openphysics='0.3', name='pipe', geometry={'version': 1, 'components': {'main': comp}},
                materials={'steel': {'youngs_modulus': q(E_PIPE, 'Pa'), 'poisson_ratio': NU_PIPE}},
                mesh={'element_size': q(size, 'mm')}, physics={'pipe': p})


def lame_radial(r):
    """Plane strain Lame displacement of a pipe under inner pressure P (outer surface free)."""
    a, b = A * 1e-3, B * 1e-3
    return (1 + NU_PIPE) / E_PIPE * a * a * P / (b * b - a * a) * ((1 - 2 * NU_PIPE) * r + b * b / r)


def solve(raw):
    return run(Document.from_dict(raw), verbose=False)


# -- R1: the document run is the direct galerkin calls ---------------------------------------


def _direct_inputs(doc, mesh, region_materials, name):
    """Hand-built solver arguments from the document's SI values (independent of
    mechanics_regions.region_mechanics_inputs)."""
    m, p = doc.si['materials'], doc.si['physics'][name]
    fixed = {}
    for tag, components in p['prescribed_displacement'].items():
        for c, value in components.items():
            for node in mesh.boundary[tag]:
                fixed[int(node), 'xy'.index(c)] = float(value)
    loads = {tag: [float(v) for v in t] for tag, t in p.get('traction', {}).items()}
    for tag, value in p.get('gauge_pressure', {}).items():
        loads[tag] = (lambda points, normals, value=float(value): -value * normals)
    return dict(young_modulus={r: m[n]['youngs_modulus'] for r, n in region_materials.items()},
                poisson_ratio={r: m[n]['poisson_ratio'] for r, n in region_materials.items()},
                plane=p['plane'], dirichlet=dict(sorted(fixed.items())),
                body_force=tuple(p.get('body_force_density', (0.0, 0.0))), traction=dict(sorted(loads.items())))


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_r1_elastic_region_run_equals_direct_solve(plane):
    from galerkin.elasticity import solve_elasticity
    raw = pipe(0.75, plane=plane, body_force_density=['100000.0 N/m^3', '-200000.0 N/m^3'],
               traction=trac({'rim': [3e5, -1e5]}))
    doc = Document.from_dict(raw)
    doc.validate()
    result = run(doc, verbose=False)
    mesh, region_materials, _ = build_region_mesh_03(Document.from_dict(raw))
    direct = solve_elasticity(mesh, **_direct_inputs(doc, mesh, region_materials, 'pipe'))
    f = result.fields
    assert f['node_coordinates'].tobytes() == mesh.nodes.tobytes()
    assert f['triangle_regions'].tobytes() == np.asarray(mesh.regions, dtype=np.int64).tobytes()
    for key, attr in (('displacement', 'displacement'), ('strain', 'strain'), ('stress', 'stress'),
                      ('applied_force_per_depth', 'load'), ('reaction_force_per_depth', 'reaction'),
                      ('residual_force_per_depth', 'residual')):
        assert f[key].tobytes() == np.asarray(getattr(direct, attr)).tobytes(), key


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_r1_thermoelastic_region_run_equals_direct_solves(plane):
    from galerkin.thermal import solve_steady_heat
    from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity
    raw = layered('mechanics.thermoelastic2d', split='y', size=4.0, nu=0.25, plane=plane,
                  prescribed_displacement=disp({'left': {'x': 0.0, 'y': 0.0}}), traction=trac({'right': [1e6, 0.0]}),
                  body_force_density=['0.0 N/m^3', '-10000.0 N/m^3'], heat_source_density={'alu': '2000000.0 W/m^3'},
                  prescribed_temperature=temps({'left': 300.0}),
                  convection={'top': {'heat_transfer_coefficient': '25.0 W/(m^2 K)', 'ambient_temperature': '290.0 K'}},
                  inward_heat_flux={'bottom': '500.0 W/m^2'})
    doc = Document.from_dict(raw)
    doc.validate()
    result = run(doc, verbose=False)
    mesh, region_materials, _ = build_region_mesh_03(Document.from_dict(raw))
    m = doc.si['materials']
    heat = solve_steady_heat(
        mesh, conductivity={r: m[n]['thermal_conductivity'] for r, n in region_materials.items()},
        dirichlet={int(i): 300.0 for i in sorted(map(int, mesh.boundary['left']))},
        heat_source={r: (2e6 if r == 'alu' else 0.0) for r in mesh.region_names},
        outward_flux={'bottom': -500.0}, convection={'top': (25.0, 290.0)})
    snapshot = freeze_temperature(mesh, heat.temperature)
    args = _direct_inputs(doc, mesh, region_materials, 'bar')
    direct = solve_thermoelasticity(
        mesh, snapshot, reference_temperature_k=300.0,
        thermal_expansion_per_k={r: m[n]['linear_expansion_coefficient'] for r, n in region_materials.items()}, **args)
    f = result.fields
    assert f['temperature'].tobytes() == heat.temperature.tobytes()
    assert result.summary()['temperature_snapshot']['snapshot_hash'] == snapshot.snapshot_hash
    for key, attr in (('displacement', 'displacement'), ('strain', 'total_strain'),
                      ('stress', 'stress'), ('stress_zz', 'sigma_zz'), ('reaction_force_per_depth', 'reaction'),
                      ('thermal_equivalent_force_per_depth', 'load_thermal'), ('residual_force_per_depth', 'residual')):
        assert f[key].tobytes() == np.asarray(getattr(direct, attr)).tobytes(), key


# -- R2, R3: two layers in series and in parallel ----------------------------------------------


@pytest.mark.parametrize('v1', [True, False])
@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_r2_two_layers_in_series_stretch_by_the_sum_of_compliances(plane, v1):
    s = 1e6
    result = solve(layered(plane=plane, v1=v1, prescribed_displacement=disp({'left': {'x': 0.0}, 'bottom': {'y': 0.0}}),
                           traction=trac({'right': [s, 0.0]})))
    f = result.fields
    end = np.isclose(f['node_coordinates'][:, 0], 0.1)
    exact = s * (0.06 / STEEL['youngs_modulus'] + 0.04 / ALU['youngs_modulus'])
    assert np.max(np.abs(f['displacement'][end, 0] - exact)) <= 1e-10 * exact
    assert np.max(np.abs(f['stress'][:, 0] - s)) <= 1e-10 * s
    assert sorted(result.summary()['region_names']) == ['alu', 'background']


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_r3_two_layers_in_parallel_carry_the_sum_of_stiffnesses(plane):
    nu, d = 0.3, 1e-6
    result = solve(layered(split='y', plane=plane, nu=nu,
                           prescribed_displacement=disp({'left': {'x': 0.0}, 'right': {'x': d}, 'bottom': {'y': 0.0}})))
    f = result.fields
    right = np.isclose(f['node_coordinates'][:, 0], 0.1)
    force = f['reaction_force_per_depth'][right, 0].sum()
    factor = 1.0 if plane == 'stress' else 1.0 / (1 - nu * nu)
    exact = factor * (STEEL['youngs_modulus'] + ALU['youngs_modulus']) * 0.01 * d / 0.1
    assert abs(force - exact) <= 1e-10 * exact


# -- R4: Lame's thick cylinder through boundary_tags and a gauge pressure ----------------------


def _lame_error(size, **physics):
    result = solve(pipe(size, **physics))
    n, u = result.fields['node_coordinates'], result.fields['displacement']
    r = np.hypot(n[:, 0], n[:, 1])
    radial = (u * n).sum(axis=1) / r
    return float(np.max(np.abs(radial - lame_radial(r))) / lame_radial(A * 1e-3)), result


def test_r4_lame_thick_cylinder_converges_at_second_order():
    """The sizes 0.5, 0.25 and 0.125 mm were fixed after a first measurement that the work record
    keeps: at 1 mm (a 16-sided bore, about two elements across the wall) the order to 0.5 mm is
    0.97, before the asymptotic range."""
    errors = [_lame_error(h)[0] for h in (0.5, 0.25, 0.125)]
    assert errors[1] <= 1e-2                                         # the reference mesh (0.25 mm)
    orders = [math.log2(errors[i] / errors[i + 1]) for i in range(2)]
    assert min(orders) >= 1.8, (errors, orders)


def test_r4_a_boundary_selection_and_its_tag_carry_the_same_pressure():
    by_tag = _lame_error(0.5)[1]
    by_selection = _lame_error(0.5, gauge_pressure={'bore': q(P, 'Pa')})[1]
    np.testing.assert_array_equal(by_tag.fields['displacement'], by_selection.fields['displacement'])
    summary = by_selection.summary()
    assert summary['gauge_pressure'] == {'bore': {'value': P, 'unit': 'Pa'}}
    assert summary['result_format'] == 'mechanics.elasticity2d-regions-result-v2'
    assert summary['field_layout'] == 'mechanics2d-p1-regions-v2'


# -- R5: thermoelastic bilayers ---------------------------------------------------------------


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_r5_free_expansion_of_a_confined_bilayer(plane):
    t, tref = 350.0, 300.0
    result = solve(layered('mechanics.thermoelastic2d', plane=plane, stress_free_temperature=q(tref, 'K'),
                           prescribed_temperature=temps({side: t for side in ('left', 'right', 'bottom', 'top')}),
                           prescribed_displacement=disp({'left': {'x': 0.0}, 'bottom': {'y': 0.0}, 'top': {'y': 0.0}})))
    f, summary = result.fields, result.summary()
    dt = t - tref
    end = np.isclose(f['node_coordinates'][:, 0], 0.1)
    exact = dt * (STEEL['linear_expansion_coefficient'] * 0.06 + ALU['linear_expansion_coefficient'] * 0.04)
    assert np.max(np.abs(f['displacement'][end, 0] - exact)) <= 1e-10 * exact
    names = summary['region_names']
    for i, spec in ((names.index('background'), STEEL), (names.index('alu'), ALU)):
        want = -spec['youngs_modulus'] * spec['linear_expansion_coefficient'] * dt
        got = f['stress'][f['triangle_regions'] == i, 1]
        assert np.max(np.abs(got - want)) <= 1e-10 * abs(want)
    assert summary['result_format'] == 'mechanics.thermoelastic2d-regions-result-v2'
    assert summary['field_layout'] == 'thermoelastic2d-p1-regions-v2'


def test_r5b_series_conduction_and_expansion_of_a_bilayer():
    t1, t2, tref = 400.0, 300.0, 300.0
    result = solve(layered('mechanics.thermoelastic2d', size=2.5, stress_free_temperature=q(tref, 'K'),
                           prescribed_temperature=temps({'left': t1, 'right': t2}),
                           prescribed_displacement=disp({'left': {'x': 0.0}, 'bottom': {'y': 0.0}, 'top': {'y': 0.0}})))
    f = result.fields
    k1, k2, l1, l2 = STEEL['thermal_conductivity'], ALU['thermal_conductivity'], 0.06, 0.04
    q_rate = (t1 - t2) / (l1 / k1 + l2 / k2)
    ti = t1 - q_rate * l1 / k1
    seam = np.isclose(f['node_coordinates'][:, 0], 0.06)
    assert seam.sum() >= 3
    assert np.max(np.abs(f['temperature'][seam] - ti)) <= 1e-9 * ti
    exact = (STEEL['linear_expansion_coefficient'] * l1 * ((t1 + ti) / 2 - tref)
             + ALU['linear_expansion_coefficient'] * l2 * ((ti + t2) / 2 - tref))
    end = np.isclose(f['node_coordinates'][:, 0], 0.1)
    assert abs(f['displacement'][end, 0].mean() - exact) <= 2e-3 * exact


def test_not_preregistered_bimetal_example_bends_as_timoshenko_predicts():
    """Not pre-registered: the shipped bimetal strip's tip deflection against Timoshenko's
    bimetal curvature (beam theory, equal layer thicknesses), within 2 percent."""
    raw = examples.EXAMPLES['thermoelastic_regions']
    result = solve(raw)
    f = result.fields
    materials = Document.from_dict(copy.deepcopy(raw)).si['materials']
    steel, alu = materials['steel'], materials['aluminium']
    m, n, h, length = 1.0, steel['youngs_modulus'] / alu['youngs_modulus'], 2e-3, 50e-3
    dt = 343.15 - 293.15
    kappa = (6 * (alu['linear_expansion_coefficient'] - steel['linear_expansion_coefficient']) * dt * (1 + m) ** 2
             / (h * (3 * (1 + m) ** 2 + (1 + m * n) * (m * m + 1 / (m * n)))))
    tip = np.isclose(f['node_coordinates'][:, 0], length)
    deflection = -f['displacement'][tip, 1].mean()        # aluminium on top expands more: bends down
    assert abs(deflection - kappa * length ** 2 / 2) <= 2e-2 * kappa * length ** 2 / 2


# -- R6: refusals by name ---------------------------------------------------------------------


def _seam(raw):
    comp = raw['geometry']['components']['main']
    comp['selections'] = {'seam': {'boundary': {'between': ['alu', 'background']}},
                          'end': {'boundary': {'of': 'alu'}}}
    return raw


def _refuse(raw, message, code=None, path=None):
    with pytest.raises(DocumentError, match=message) as caught:
        Document.from_dict(raw).validate()
    if code is not None:
        assert [(d.code, d.path) for d in caught.value.diagnostics if d.severity == 'error'] == [(code, path)]


SUPPORT = disp({'left': {'x': 0.0}, 'bottom': {'y': 0.0}})
BAR = 'physics.bar.'


@pytest.mark.parametrize('physics, message, code, path', [
    ({'prescribed_displacement': {**SUPPORT, 'seam': {'x': '0.0 m'}}},
     "prescribed_displacement.seam: selection 'seam' lies on an interface", 'E-CONTRACT',
     BAR + 'prescribed_displacement.seam'),
    ({'prescribed_displacement': SUPPORT, 'traction': trac({'seam': [1.0, 0.0]})},
     "traction.seam: selection 'seam' lies on an interface", 'E-CONTRACT', BAR + 'traction.seam'),
    ({'prescribed_displacement': SUPPORT, 'gauge_pressure': {'seam': '1.0 Pa'}},
     "gauge_pressure.seam: selection 'seam' lies on an interface", 'E-CONTRACT', BAR + 'gauge_pressure.seam'),
    ({'prescribed_displacement': {**SUPPORT, 'nowhere': {'x': '0.0 m'}}},
     'no side, boundary tag or exterior selection of that name', 'E-SELECTION-UNKNOWN',
     BAR + 'prescribed_displacement.nowhere'),
    ({'prescribed_displacement': disp({'left': {'x': 0.0}})}, 'rigid-body motion free', 'E-CONTRACT',
     BAR + 'prescribed_displacement'),
    ({'prescribed_displacement': {'left': {'z': '0.0 m'}, 'bottom': {'y': '0.0 m'}}},
     'a component object takes x, y', 'E-KEY-UNKNOWN', BAR + 'prescribed_displacement.left.z'),
    ({'prescribed_displacement': SUPPORT, 'traction': trac({'left': [1.0, 0.0]})},
     'nonzero x traction on a boundary whose x', 'E-CONTRACT', BAR + 'traction.left'),
    ({'prescribed_displacement': SUPPORT, 'gauge_pressure': {'right': '1.0 Pa'}, 'traction': trac({'right': [1.0, 0.0]})},
     "'right' also has a traction", 'E-CONTRACT', BAR + 'gauge_pressure.right'),
    ({'prescribed_displacement': SUPPORT, 'youngs_modulus': '1 GPa'},
     'youngs_modulus: a region document takes youngs_modulus from materials', 'E-CONTRACT', BAR + 'youngs_modulus'),
    ({'prescribed_displacement': SUPPORT, 'poisson_ratio': 0.3}, 'takes poisson_ratio from materials', 'E-CONTRACT',
     BAR + 'poisson_ratio'),
    ({'prescribed_displacement': SUPPORT, 'plane': 'shell'}, 'is not one of "stress", "strain"', 'E-VALUE-FORM',
     BAR + 'plane'),
    ({'prescribed_displacement': SUPPORT, 'body_force_density': ['1.0 N/m^3']},
     'body_force_density is a global \\[x, y\\] vector of two entries', 'E-VALUE-FORM', BAR + 'body_force_density'),
])
def test_r6_elastic_refusals_name_the_entry(physics, message, code, path):
    _refuse(_seam(layered(**physics)), message, code, path)


def test_r6_material_and_geometry_refusals():
    raw = layered(prescribed_displacement=SUPPORT)
    del raw['materials']['aluminium']['youngs_modulus']
    _refuse(raw, 'required by mechanics.elasticity2d', 'E-PROPERTY-MISSING', 'materials.aluminium.youngs_modulus')
    raw = layered(prescribed_displacement=SUPPORT)
    raw['materials']['steel']['poisson_ratio'] = 0.5
    _refuse(raw, 'poisson_ratio must be > -1 and < 0.5', 'E-DOMAIN', 'materials.steel.poisson_ratio')
    raw = layered(prescribed_displacement=SUPPORT)
    raw['materials']['steel']['youngs_modulus'] = '0 Pa'
    _refuse(raw, 'youngs_modulus must be > 0 Pa', 'E-DOMAIN', 'materials.steel.youngs_modulus')
    raw = layered(prescribed_displacement=SUPPORT)
    raw['materials'] = {'steel': raw['materials']['steel']}
    _refuse(raw, 'material "aluminium" has no record in materials', 'E-MATERIAL-UNKNOWN',
            'geometry.components.main.features[0].material')
    raw = layered(prescribed_displacement=SUPPORT)
    raw['geometry']['components']['main']['background'] = {'material': None}
    _refuse(raw, 'region mechanics takes no void background')
    raw = layered(prescribed_displacement=SUPPORT)
    raw['geometry']['components']['main']['features'].append(
        dict(name='far', type='rect', x=200.0, y=0.0, w=5.0, h=5.0, material='steel'))
    _refuse(raw, 'A mechanics region document refuses a feature')
    raw = layered(prescribed_displacement=SUPPORT, v1=False)
    raw['geometry']['shapes'].append(dict(name='far', type='rect', x=200.0, y=0.0, w=5.0, h=5.0, material='steel'))
    _refuse(raw, 'A mechanics region document refuses a shape')
    raw = layered(prescribed_displacement=SUPPORT)
    component = raw['geometry']['components']['main']
    component['dimension'] = 'axisymmetric'
    del component['depth']                                 # an axisymmetric component has none
    _refuse(raw, 'mechanics.elasticity2d takes 2d components only', 'E-CONTRACT', 'geometry.components')
    raw = layered(prescribed_displacement=SUPPORT)
    raw['mesh'] = {'subdivision_count': [10, 2]}
    _refuse(raw, 'subdivision_count belongs to rectangle documents', 'E-KEY-UNKNOWN', 'mesh.subdivision_count')
    # one name for both conductivities' thermal half: the 0.2 spellings are unknown keys
    raw = layered(prescribed_displacement=SUPPORT)
    raw['materials']['steel']['thermal_conductivity_w_mk'] = 45.0
    _refuse(raw, 'Did you mean thermal_conductivity', 'E-KEY-UNKNOWN', 'materials.steel.thermal_conductivity_w_mk')
    raw = layered(prescribed_displacement=SUPPORT)
    raw['materials']['steel']['youngs_modulus_pa'] = 1e9
    _refuse(raw, 'Did you mean youngs_modulus', 'E-KEY-UNKNOWN', 'materials.steel.youngs_modulus_pa')
    raw = layered(prescribed_displacement=SUPPORT)
    raw['units'] = {'length': 'mm'}
    _refuse(raw, 'units travel with each value', 'E-KEY-UNKNOWN', 'units')
    raw = layered(prescribed_displacement=SUPPORT)
    del raw['geometry']['components']['main']['length_unit']
    _refuse(raw, 'needs length_unit', 'E-KEY-MISSING', 'geometry.components.main.length_unit')
    raw = layered(prescribed_displacement=SUPPORT, v1=False)
    del raw['geometry']['length_unit']
    _refuse(raw, 'needs length_unit', 'E-KEY-MISSING', 'geometry.length_unit')


@pytest.mark.parametrize('change, message, code, path', [
    ({'prescribed_temperature': {}}, 'pure Neumann is unsupported', 'E-KEY-MISSING', BAR + 'prescribed_temperature'),
    ({'linear_expansion_coefficient': '10 ppm/K'}, 'takes linear_expansion_coefficient from materials', 'E-CONTRACT',
     BAR + 'linear_expansion_coefficient'),
    ({'thermal_conductivity': '1 W/(m K)'}, 'takes thermal_conductivity from materials', 'E-CONTRACT',
     BAR + 'thermal_conductivity'),
    ({'stress_free_temperature': '-1 K'}, 'stress_free_temperature must be > 0 K', 'E-DOMAIN',
     BAR + 'stress_free_temperature'),
    ({'heat_source_density': {'nowhere': '1 W/m^3'}}, 'no shape or background of that name', 'E-SELECTION-UNKNOWN',
     BAR + 'heat_source_density.nowhere'),
    ({'inward_heat_flux': {'seam': '-1 W/m^2'}}, "selection 'seam' lies on an interface between two regions; flux",
     'E-CONTRACT', BAR + 'inward_heat_flux.seam'),
])
def test_r6_thermoelastic_refusals_name_the_entry(change, message, code, path):
    raw = _seam(layered('mechanics.thermoelastic2d', prescribed_displacement=SUPPORT,
                        prescribed_temperature=temps({'left': 300.0})))
    raw['physics']['bar'].update(change)
    _refuse(raw, message, code, path)
    raw = layered('mechanics.thermoelastic2d', prescribed_displacement=SUPPORT, prescribed_temperature=temps({'left': 300.0}))
    del raw['materials']['steel']['thermal_conductivity']
    _refuse(raw, 'required by mechanics.thermoelastic2d', 'E-PROPERTY-MISSING', 'materials.steel.thermal_conductivity')


def test_r6_mesh_time_refusals_name_the_entry():
    # a void splits the bar; only the left part is held
    raw = layered(prescribed_displacement=disp({'left': {'x': 0.0, 'y': 0.0}}))
    raw['geometry']['components']['main']['features'] = [
        dict(name='gap', type='rect', x=40.0, y=0.0, w=10.0, h=20.0, material=None),
        dict(name='right_part', type='rect', x=50.0, y=0.0, w=50.0, h=20.0, material='aluminium')]
    with pytest.raises(DocumentError, match="rigid-body motion free in the part of the body made of regions "
                                            "\\['right_part'\\]"):
        solve(raw)
    # two names fix a shared corner node differently
    with pytest.raises(DocumentError, match="'left' and 'bottom' share node .* with different x displacements"):
        solve(layered(prescribed_displacement=disp({'left': {'x': 0.0}, 'bottom': {'x': 1e-6, 'y': 0.0}})))
    # a selection and the side tag carry the same edges, both loaded
    raw = layered(prescribed_displacement=SUPPORT, traction=trac({'right': [1.0, 0.0], 'end_right': [1.0, 0.0]}))
    raw['geometry']['components']['main']['selections'] = {
        'end_right': {'boundary': {'between': ['alu', 'exterior']}}}
    with pytest.raises(DocumentError, match="share mesh edges and both carry a traction"):
        solve(raw)


def test_r6_loads_on_prescribed_components_are_decided_per_edge():
    # the top is held in x and pressed normally (in y): well posed, accepted
    held = layered(prescribed_displacement={**SUPPORT, 'top': {'x': '0.0 m'}}, gauge_pressure={'top': '1000000.0 Pa'})
    assert solve(held).summary()['gauge_pressure'] == {'top': {'value': 1e6, 'unit': 'Pa'}}
    # a gauge pressure on the left side, whose x displacement is prescribed, loads that component
    with pytest.raises(DocumentError, match="gauge_pressure.left loads the x component of an edge whose x "
                                            "displacement 'left' prescribes"):
        solve(layered(prescribed_displacement=SUPPORT, gauge_pressure={'left': '1000000.0 Pa'}))
    # a traction under another name on edges a selection fixes
    raw = layered(prescribed_displacement={**SUPPORT, 'end_right': {'x': '0.0 m'}}, traction=trac({'right': [1.0, 0.0]}))
    raw['geometry']['components']['main']['selections'] = {
        'end_right': {'boundary': {'between': ['alu', 'exterior']}}}
    with pytest.raises(DocumentError, match="traction.right loads the x component of an edge whose x "
                                            "displacement 'end_right' prescribes"):
        solve(raw)


def test_r6_a_side_that_borders_a_void_only_has_no_mesh_edge():
    raw = layered(prescribed_displacement={**SUPPORT, 'right': {'x': '0.0 m'}})
    raw['geometry']['components']['main']['features'] = [
        dict(name='gap', type='rect', x=90.0, y=0.0, w=10.0, h=20.0, material=None)]
    with pytest.raises(DocumentError, match="prescribed_displacement.right: no mesh edge lies on 'right'"):
        solve(raw)


def test_r6_cli_exits_1_without_output_for_a_mesh_time_refusal(tmp_path):
    model = tmp_path / 'model.json'
    model.write_text(json.dumps(layered(prescribed_displacement=SUPPORT, gauge_pressure={'left': '1000000.0 Pa'})),
                     encoding='utf-8')
    out = tmp_path / 'out'
    assert main(['run', str(model), '-o', str(out)]) == 1
    assert not out.exists()


def test_r6_cli_refuses_with_exit_2_and_no_output(tmp_path):
    raw = _seam(layered(prescribed_displacement={**SUPPORT, 'seam': {'x': '0.0 m'}}))
    model = tmp_path / 'model.json'
    model.write_text(json.dumps(raw), encoding='utf-8')
    out = tmp_path / 'out'
    assert main(['run', str(model), '-o', str(out)]) == 2
    assert not out.exists()


# -- R7: mesh limits ---------------------------------------------------------------------------


def test_r7_mesh_limits_reach_region_mechanics_only():
    raw = layered(prescribed_displacement=SUPPORT, traction=trac({'right': [1.0, 0.0]}))
    with pytest.raises(MeshLimitError):
        run(Document.from_dict(raw), verbose=False, max_nodes=20)
    assert run(Document.from_dict(raw), verbose=False, max_nodes=10 ** 6).summary()['status'] == 'solved'
    with pytest.raises(ValueError, match='mesh limits apply only to'):
        run(Document.from_dict(examples.EXAMPLES['elastic_plate']), verbose=False, max_nodes=10 ** 6)


# -- dispatch, rectangle documents and the shipped examples ------------------------------------


def test_rectangle_documents_keep_the_rectangle_path():
    for name in ('elastic_plate', 'thermoelastic_bar'):
        data = examples.EXAMPLES[name]
        assert not is_region_mechanics(data)
        summary = run(Document.from_dict(data), verbose=False).summary()
        assert summary['result_format'] == data['physics'][next(iter(data['physics']))]['type'] + '-result-v2'
        assert 'triangle_regions' not in summary['field_shapes'] and 'regions' not in summary


@pytest.mark.parametrize('name', ['elastic_regions', 'thermoelastic_regions'])
def test_region_examples_run_and_save(name, tmp_path):
    data = copy.deepcopy(examples.EXAMPLES[name])
    assert is_region_mechanics(data)
    result = run(Document.from_dict(data), verbose=False)
    path = result.save(tmp_path / 'out')
    summary = json.loads((path / 'summary.json').read_text(encoding='utf-8'))
    with np.load(path / 'fields.npz', allow_pickle=False) as z:
        assert set(summary['field_shapes']) <= set(z.files)
        assert z['triangle_regions'].shape == (summary['mesh']['triangles'],)
    balance = summary['balance']
    assert max(abs(v) for v in balance['force_imbalance_per_depth']['values']) <= 1e-6 * max(
        1.0, *map(abs, balance['reaction_force_per_depth']['values']))


# -- length units: only the shape numbers follow length_unit; every other value carries its unit --

SCALE = {'m': '0.001', 'mm': '1', 'um': '1000', 'nm': '1000000'}
LENGTH_KEYS = ('xmin', 'xmax', 'ymin', 'ymax', 'x', 'y', 'w', 'h', 'cx', 'cy', 'r')


def _scaled(value, factor):
    from fractions import Fraction
    return float(Fraction(repr(float(value))) * Fraction(factor))


def _in_unit(raw, unit):
    """The millimetre document ``raw`` with its shape numbers written in ``unit``: each the
    nearest double of the exact product, so every one lands on the same picometre count. The
    element size and the loads are quantities and keep their own units."""
    out = copy.deepcopy(raw)
    k = SCALE[unit]
    comp = out['geometry']['components']['main']
    comp['domain'] = {key: _scaled(v, k) for key, v in comp['domain'].items()}
    for f in comp['features']:
        for key in LENGTH_KEYS:
            if key in f:
                f[key] = _scaled(f[key], k)
    comp['length_unit'] = unit
    return out


#: the smallest triangle angle is measured on the triangulation of the micrometre hand-off in the
#: document's own numbers, so it is the one summary value that moves by rounding across length
#: units (as for region heat, electric and Joule): compared within 1e-13 relative, a stated
#: deviation from P2-5's identical summaries, not a pass of it. Every array is bitwise equal.
ANGLE_BOUND = 1e-13


@pytest.mark.parametrize('name, physics', [
    ('elastic_regions', {'prescribed_displacement': disp({'left': {'x': 1e-7}, 'bottom': {'y': 0.0}}),
                         'body_force_density': ['100000.0 N/m^3', '-2000000.0 N/m^3']}),
    ('thermoelastic_regions', {'prescribed_displacement': disp({'left': {'x': 1e-7, 'y': 0.0}}),
                               'body_force_density': ['0.0 N/m^3', '-100000.0 N/m^3'],
                               'gauge_pressure': {'right': '2000000.0 Pa'}}),
])
def test_region_results_do_not_depend_on_the_length_unit(name, physics):
    """Not pre-registered (the units review of 2026-11-08 measured it; added as a regression)."""
    raw = copy.deepcopy(examples.EXAMPLES[name])
    raw['physics'][next(iter(raw['physics']))].update(physics)
    ref = solve(raw)
    angle = ref.summary()['mesh']['minimum_triangle_angle']['value']
    for unit in ('m', 'um', 'nm'):
        other = solve(_in_unit(raw, unit))
        for key, array in ref.fields.items():
            np.testing.assert_array_equal(other.fields[key], array, err_msg=f'{unit}: {key}')
        assert abs(other.summary()['mesh']['minimum_triangle_angle']['value'] - angle) <= ANGLE_BOUND * angle, unit
    # a wrong unit is caught before meshing: millimetre numbers declared as metres make the
    # 0.5 mm (or 0.25 mm) element size cover a domain a thousand times larger
    wrong = copy.deepcopy(raw)
    wrong['geometry']['components']['main']['length_unit'] = 'm'
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(wrong)
    assert [(d.code, d.path) for d in caught.value.diagnostics if d.severity == 'error'] == [
        ('E-MESH-ESTIMATE', 'geometry.components.main')]
