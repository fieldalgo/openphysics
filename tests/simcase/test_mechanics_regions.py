# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Mechanics documents on named material regions (geometry order 1-c).

Pre-registered checks R1 to R7 (HQ work record, 2026-11-08; R0, the rectangle documents
hash-identical before and after, is a measurement recorded there): a region document run
equals the direct galerkin calls (R1); two layers in series (R2) and in parallel (R3) against
closed-form stiffness; Lame's thick cylinder through ``boundary_tags`` and a pressure (R4);
thermoelastic bilayers against closed forms (R5); refusals by name (R6); mesh limits (R7).
Thresholds are gates: never loosen them.
"""
import copy
import json
import math

import numpy as np
import pytest

from simcase import Document, DocumentError, MeshLimitError, examples, run
from simcase.cli import main
from simcase.mechanics_regions import is_region_mechanics
from simcase.thermal_regions import build_region_mesh

STEEL = {'young_modulus_pa': 200e9, 'poisson_ratio': 0.0, 'thermal_expansion_per_k': 12e-6,
         'conductivity_w_mk': 45.0}
ALU = {'young_modulus_pa': 70e9, 'poisson_ratio': 0.0, 'thermal_expansion_per_k': 23e-6,
       'conductivity_w_mk': 237.0}


def layered(kind='mechanics.elasticity2d', *, split='x', v1=True, plane='stress', size=5.0, nu=0.0,
            units='mm', **physics):
    """A 100 x 20 bar of steel with an aluminium layer: x >= 60 (split x) or y >= 10 (split y)."""
    layer = (dict(x=60.0, y=0.0, w=40.0, h=20.0) if split == 'x' else dict(x=0.0, y=10.0, w=100.0, h=10.0))
    feature = dict(name='alu', type='rect', material='aluminium', **layer)
    domain = dict(xmin=0.0, xmax=100.0, ymin=0.0, ymax=20.0)
    if v1:
        geometry = {'version': 1, 'components': {'main': dict(dimension='2d', domain=domain,
                    background={'material': 'steel'}, features=[feature], finalize='later_wins')}}
    else:
        geometry = {'domain': domain, 'background': {'material': 'steel'}, 'shapes': [feature]}
    thermal = kind == 'mechanics.thermoelastic2d'
    p = dict(type=kind, plane=plane, **physics)
    if thermal:
        p.setdefault('reference_temperature_k', 300.0)
    return dict(openphysics='0.2', name='layers', units={'length': units, **({'temperature': 'K'} if thermal else {})},
                geometry=geometry,
                materials={'steel': dict(STEEL, poisson_ratio=nu), 'aluminium': dict(ALU, poisson_ratio=nu)},
                mesh={'size': size}, physics={'bar': p})


A, B, P, E_PIPE, NU_PIPE = 3.0, 9.0, 1e6, 200e9, 0.3


def pipe(size, **physics):
    """A quarter of a thick pipe (radii 3 and 9 mm) with ``inner`` and ``rim`` boundary tags."""
    comp = dict(dimension='2d', domain=dict(xmin=0.0, xmax=B, ymin=0.0, ymax=B), background={'material': 'steel'},
                features=[dict(name='cut', type='rect', x=0.0, y=0.0, w=B, h=B, material=None),
                          dict(name='disc', type='circle', cx=0.0, cy=0.0, r=B, material='steel'),
                          dict(name='hole', type='circle', cx=0.0, cy=0.0, r=A, material=None)],
                finalize='later_wins',
                boundary_tags=[{'tag': 'inner', 'select': {'boundary': {'of': 'hole'}}},
                               {'tag': 'rim', 'select': {'boundary': {'between': ['disc', 'cut']}}}],
                selections={'bore': {'boundary': {'of': 'hole'}}})
    p = dict(type='mechanics.elasticity2d', plane='strain', displacement_m={'left': {'x': 0.0}, 'bottom': {'y': 0.0}},
             pressure_pa={'inner': P})
    p.update(physics)
    return dict(openphysics='0.2', name='pipe', units={'length': 'mm'},
                geometry={'version': 1, 'components': {'main': comp}},
                materials={'steel': {'young_modulus_pa': E_PIPE, 'poisson_ratio': NU_PIPE}},
                mesh={'size': size}, physics={'pipe': p})


def lame_radial(r):
    """Plane strain Lame displacement of a pipe under inner pressure P (outer surface free)."""
    a, b = A * 1e-3, B * 1e-3
    return (1 + NU_PIPE) / E_PIPE * a * a * P / (b * b - a * a) * ((1 - 2 * NU_PIPE) * r + b * b / r)


def solve(raw):
    return run(Document.from_dict(raw), verbose=False)


# -- R1: the document run is the direct galerkin calls ---------------------------------------


def _direct_inputs(doc, mesh, region_materials, p):
    """Hand-built solver arguments (independent of mechanics_regions.region_mechanics_inputs)."""
    m = doc['materials']
    fixed = {}
    for tag, components in p['displacement_m'].items():
        for c, value in components.items():
            for node in mesh.boundary[tag]:
                fixed[int(node), 'xy'.index(c)] = float(value)
    loads = {tag: [float(v) for v in t] for tag, t in p.get('traction_pa', {}).items()}
    for tag, value in p.get('pressure_pa', {}).items():
        loads[tag] = (lambda points, normals, value=float(value): -value * normals)
    return dict(young_modulus={r: m[name]['young_modulus_pa'] for r, name in region_materials.items()},
                poisson_ratio={r: m[name]['poisson_ratio'] for r, name in region_materials.items()},
                plane=p['plane'], dirichlet=dict(sorted(fixed.items())),
                body_force=tuple(p.get('body_force_n_m3', (0.0, 0.0))), traction=dict(sorted(loads.items())))


def _validated_copy(doc):
    copied = doc.copy()
    copied.validate()                  # sets the length scale, as the runner's copy does
    return copied


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_r1_elastic_region_run_equals_direct_solve(plane):
    from galerkin.elasticity import solve_elasticity
    raw = pipe(0.75, plane=plane, body_force_n_m3=[1e5, -2e5], traction_pa={'rim': [3e5, -1e5]})
    doc = Document.from_dict(raw)
    doc.validate()
    result = run(doc, verbose=False)
    mesh, region_materials, _ = build_region_mesh(_validated_copy(doc))
    direct = solve_elasticity(mesh, **_direct_inputs(doc, mesh, region_materials, raw['physics']['pipe']))
    f = result.fields
    assert f['nodes_m'].tobytes() == mesh.nodes.tobytes()
    assert f['triangle_regions'].tobytes() == np.asarray(mesh.regions, dtype=np.int64).tobytes()
    for key, attr in (('displacement_m', 'displacement'), ('strain', 'strain'), ('stress_pa', 'stress'),
                      ('load_n_per_m', 'load'), ('reaction_n_per_m', 'reaction'), ('residual_n_per_m', 'residual')):
        assert f[key].tobytes() == np.asarray(getattr(direct, attr)).tobytes(), key


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_r1_thermoelastic_region_run_equals_direct_solves(plane):
    from galerkin.thermal import solve_steady_heat
    from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity
    raw = layered('mechanics.thermoelastic2d', split='y', size=4.0, nu=0.25, plane=plane,
                  displacement_m={'left': {'x': 0.0, 'y': 0.0}}, traction_pa={'right': [1e6, 0.0]},
                  body_force_n_m3=[0.0, -1e4], heat_source_w_m3={'alu': 2e6},
                  dirichlet_temperature_k={'left': 300.0},
                  convection={'top': {'h_w_m2k': 25.0, 'ambient_temperature_k': 290.0}},
                  outward_flux_w_m2={'bottom': -500.0})
    doc = Document.from_dict(raw)
    doc.validate()
    result = run(doc, verbose=False)
    mesh, region_materials, _ = build_region_mesh(_validated_copy(doc))
    m, p = doc['materials'], raw['physics']['bar']
    heat = solve_steady_heat(
        mesh, conductivity={r: m[n]['conductivity_w_mk'] for r, n in region_materials.items()},
        dirichlet={int(i): 300.0 for i in sorted(map(int, mesh.boundary['left']))},
        heat_source={r: (2e6 if r == 'alu' else 0.0) for r in mesh.region_names},
        outward_flux={'bottom': -500.0}, convection={'top': (25.0, 290.0)})
    snapshot = freeze_temperature(mesh, heat.temperature)
    args = _direct_inputs(doc, mesh, region_materials, p)
    direct = solve_thermoelasticity(
        mesh, snapshot, reference_temperature_k=300.0,
        thermal_expansion_per_k={r: m[n]['thermal_expansion_per_k'] for r, n in region_materials.items()}, **args)
    f = result.fields
    assert f['temperature_k'].tobytes() == heat.temperature.tobytes()
    assert result.summary()['temperature_snapshot']['snapshot_hash'] == snapshot.snapshot_hash
    for key, attr in (('displacement_m', 'displacement'), ('total_strain', 'total_strain'),
                      ('stress_pa', 'stress'), ('sigma_zz_pa', 'sigma_zz'), ('reaction_n_per_m', 'reaction'),
                      ('load_thermal_n_per_m', 'load_thermal'), ('residual_n_per_m', 'residual')):
        assert f[key].tobytes() == np.asarray(getattr(direct, attr)).tobytes(), key


# -- R2, R3: two layers in series and in parallel ----------------------------------------------


@pytest.mark.parametrize('v1', [True, False])
@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_r2_two_layers_in_series_stretch_by_the_sum_of_compliances(plane, v1):
    s = 1e6
    result = solve(layered(plane=plane, v1=v1, displacement_m={'left': {'x': 0.0}, 'bottom': {'y': 0.0}},
                           traction_pa={'right': [s, 0.0]}))
    f = result.fields
    end = np.isclose(f['nodes_m'][:, 0], 0.1)
    exact = s * (0.06 / STEEL['young_modulus_pa'] + 0.04 / ALU['young_modulus_pa'])
    assert np.max(np.abs(f['displacement_m'][end, 0] - exact)) <= 1e-10 * exact
    assert np.max(np.abs(f['stress_pa'][:, 0] - s)) <= 1e-10 * s
    assert sorted(result.summary()['region_names']) == ['alu', 'background']


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_r3_two_layers_in_parallel_carry_the_sum_of_stiffnesses(plane):
    nu, d = 0.3, 1e-6
    result = solve(layered(split='y', plane=plane, nu=nu,
                           displacement_m={'left': {'x': 0.0}, 'right': {'x': d}, 'bottom': {'y': 0.0}}))
    f = result.fields
    right = np.isclose(f['nodes_m'][:, 0], 0.1)
    force = f['reaction_n_per_m'][right, 0].sum()
    factor = 1.0 if plane == 'stress' else 1.0 / (1 - nu * nu)
    exact = factor * (STEEL['young_modulus_pa'] + ALU['young_modulus_pa']) * 0.01 * d / 0.1
    assert abs(force - exact) <= 1e-10 * exact


# -- R4: Lame's thick cylinder through boundary_tags and a pressure ----------------------------


def _lame_error(size, **physics):
    result = solve(pipe(size, **physics))
    n, u = result.fields['nodes_m'], result.fields['displacement_m']
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
    by_selection = _lame_error(0.5, pressure_pa={'bore': P})[1]
    np.testing.assert_array_equal(by_tag.fields['displacement_m'], by_selection.fields['displacement_m'])
    summary = by_selection.summary()
    assert summary['pressure_pa'] == {'bore': P}
    assert summary['result_format'] == 'mechanics.elasticity2d-regions-result-v1'
    assert summary['field_layout'] == 'mechanics2d-p1-regions-v1'


# -- R5: thermoelastic bilayers ---------------------------------------------------------------


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_r5_free_expansion_of_a_confined_bilayer(plane):
    t, tref = 350.0, 300.0
    result = solve(layered('mechanics.thermoelastic2d', plane=plane, reference_temperature_k=tref,
                           dirichlet_temperature_k={side: t for side in ('left', 'right', 'bottom', 'top')},
                           displacement_m={'left': {'x': 0.0}, 'bottom': {'y': 0.0}, 'top': {'y': 0.0}}))
    f, summary = result.fields, result.summary()
    dt = t - tref
    end = np.isclose(f['nodes_m'][:, 0], 0.1)
    exact = dt * (STEEL['thermal_expansion_per_k'] * 0.06 + ALU['thermal_expansion_per_k'] * 0.04)
    assert np.max(np.abs(f['displacement_m'][end, 0] - exact)) <= 1e-10 * exact
    names = summary['region_names']
    for i, spec in ((names.index('background'), STEEL), (names.index('alu'), ALU)):
        want = -spec['young_modulus_pa'] * spec['thermal_expansion_per_k'] * dt
        got = f['stress_pa'][f['triangle_regions'] == i, 1]
        assert np.max(np.abs(got - want)) <= 1e-10 * abs(want)
    assert summary['result_format'] == 'mechanics.thermoelastic2d-regions-result-v1'
    assert summary['field_layout'] == 'thermoelastic2d-p1-regions-v1'


def test_r5b_series_conduction_and_expansion_of_a_bilayer():
    t1, t2, tref = 400.0, 300.0, 300.0
    result = solve(layered('mechanics.thermoelastic2d', size=2.5, reference_temperature_k=tref,
                           dirichlet_temperature_k={'left': t1, 'right': t2},
                           displacement_m={'left': {'x': 0.0}, 'bottom': {'y': 0.0}, 'top': {'y': 0.0}}))
    f = result.fields
    k1, k2, l1, l2 = STEEL['conductivity_w_mk'], ALU['conductivity_w_mk'], 0.06, 0.04
    q = (t1 - t2) / (l1 / k1 + l2 / k2)
    ti = t1 - q * l1 / k1
    seam = np.isclose(f['nodes_m'][:, 0], 0.06)
    assert seam.sum() >= 3
    assert np.max(np.abs(f['temperature_k'][seam] - ti)) <= 1e-9 * ti
    exact = (STEEL['thermal_expansion_per_k'] * l1 * ((t1 + ti) / 2 - tref)
             + ALU['thermal_expansion_per_k'] * l2 * ((ti + t2) / 2 - tref))
    end = np.isclose(f['nodes_m'][:, 0], 0.1)
    assert abs(f['displacement_m'][end, 0].mean() - exact) <= 2e-3 * exact


def test_not_preregistered_bimetal_example_bends_as_timoshenko_predicts():
    """Not pre-registered: the shipped bimetal strip's tip deflection against Timoshenko's
    bimetal curvature (beam theory, equal layer thicknesses), within 2 percent."""
    raw = examples.EXAMPLES['thermoelastic_regions']
    result = solve(raw)
    f = result.fields
    steel, alu = raw['materials']['steel'], raw['materials']['aluminium']
    m, n, h, length = 1.0, steel['young_modulus_pa'] / alu['young_modulus_pa'], 2e-3, 50e-3
    dt = 343.15 - 293.15
    kappa = (6 * (alu['thermal_expansion_per_k'] - steel['thermal_expansion_per_k']) * dt * (1 + m) ** 2
             / (h * (3 * (1 + m) ** 2 + (1 + m * n) * (m * m + 1 / (m * n)))))
    tip = np.isclose(f['nodes_m'][:, 0], length)
    deflection = -f['displacement_m'][tip, 1].mean()        # aluminium on top expands more: bends down
    assert abs(deflection - kappa * length ** 2 / 2) <= 2e-2 * kappa * length ** 2 / 2


# -- R6: refusals by name ---------------------------------------------------------------------


def _seam(raw):
    comp = raw['geometry']['components']['main']
    comp['selections'] = {'seam': {'boundary': {'between': ['alu', 'background']}},
                          'end': {'boundary': {'of': 'alu'}}}
    return raw


def _refuse(raw, message):
    with pytest.raises(DocumentError, match=message):
        Document.from_dict(raw).validate()


SUPPORT = {'left': {'x': 0.0}, 'bottom': {'y': 0.0}}


@pytest.mark.parametrize('physics, message', [
    ({'displacement_m': {**SUPPORT, 'seam': {'x': 0.0}}}, "displacement_m.seam: selection 'seam' lies on an interface"),
    ({'displacement_m': SUPPORT, 'traction_pa': {'seam': [1.0, 0.0]}}, "traction_pa.seam: selection 'seam' lies on an "
                                                                        'interface'),
    ({'displacement_m': SUPPORT, 'pressure_pa': {'seam': 1.0}}, "pressure_pa.seam: selection 'seam' lies on an "
                                                                 'interface'),
    ({'displacement_m': {**SUPPORT, 'nowhere': {'x': 0.0}}}, "unsupported mechanics keys \\['nowhere'\\]"),
    ({'displacement_m': {'left': {'x': 0.0}}}, 'rigid-body motion free'),
    ({'displacement_m': {'left': {'z': 0.0}, 'bottom': {'y': 0.0}}}, "displacement_m.left: unsupported mechanics keys"),
    ({'displacement_m': SUPPORT, 'traction_pa': {'left': [1.0, 0.0]}}, 'nonzero x traction on a boundary whose x'),
    ({'displacement_m': SUPPORT, 'pressure_pa': {'right': 1.0}, 'traction_pa': {'right': [1.0, 0.0]}},
     "'right' also has a traction"),
    ({'displacement_m': SUPPORT, 'young_modulus_pa': 1e9}, 'young_modulus_pa: a region document takes '
                                                           'young_modulus_pa from materials'),
    ({'displacement_m': SUPPORT, 'poisson_ratio': 0.3}, 'takes poisson_ratio from materials'),
    ({'displacement_m': SUPPORT, 'plane': 'shell'}, 'plane: expected "stress" or "strain"'),
    ({'displacement_m': SUPPORT, 'body_force_n_m3': [1.0]}, 'body_force_n_m3: expected \\[x, y\\]'),
])
def test_r6_elastic_refusals_name_the_entry(physics, message):
    _refuse(_seam(layered(**physics)), message)


def test_r6_material_and_geometry_refusals():
    raw = layered(displacement_m=SUPPORT)
    del raw['materials']['aluminium']['young_modulus_pa']
    _refuse(raw, 'materials.aluminium.young_modulus_pa: required by mechanics.elasticity2d')
    raw = layered(displacement_m=SUPPORT)
    raw['materials']['steel']['poisson_ratio'] = 0.5
    _refuse(raw, 'materials.steel.poisson_ratio: expected -1 < nu < 0.5')
    raw = layered(displacement_m=SUPPORT)
    raw['materials']['steel']['young_modulus_pa'] = 0.0
    _refuse(raw, 'materials.steel.young_modulus_pa: expected a finite positive number')
    raw = layered(displacement_m=SUPPORT)
    raw['materials'] = {'steel': raw['materials']['steel']}
    _refuse(raw, "material 'aluminium' is not defined in materials \\(thermal, electrical and mechanical properties")
    raw = layered(displacement_m=SUPPORT)
    raw['geometry']['components']['main']['background'] = {'material': None}
    _refuse(raw, 'region mechanics takes no void background')
    raw = layered(displacement_m=SUPPORT)
    raw['geometry']['components']['main']['features'].append(
        dict(name='far', type='rect', x=200.0, y=0.0, w=5.0, h=5.0, material='steel'))
    _refuse(raw, 'A mechanics region document refuses a feature')
    raw = layered(displacement_m=SUPPORT, v1=False)
    raw['geometry']['shapes'].append(dict(name='far', type='rect', x=200.0, y=0.0, w=5.0, h=5.0, material='steel'))
    _refuse(raw, 'A mechanics region document refuses a shape')
    raw = layered(displacement_m=SUPPORT)
    raw['geometry']['components']['main']['dimension'] = 'axisymmetric'
    _refuse(raw, 'mechanics.elasticity2d takes 2d components only')
    raw = layered(displacement_m=SUPPORT)
    raw['mesh'] = {'subdivisions': [10, 2]}
    _refuse(raw, "mesh: unsupported mechanics keys \\['subdivisions'\\]")
    raw = layered(displacement_m=SUPPORT)
    raw['materials']['steel']['thermal_conductivity_w_mk'] = 45.0
    _refuse(raw, 'materials.steel.thermal_conductivity_w_mk: the materials table names thermal conductivity '
                 'conductivity_w_mk')
    raw = layered(displacement_m=SUPPORT)
    raw['materials']['steel']['youngs_modulus_pa'] = 1e9
    _refuse(raw, "materials.steel: unsupported mechanics keys \\['youngs_modulus_pa'\\]")
    raw = layered(displacement_m=SUPPORT, v1=False)
    del raw['units']
    _refuse(raw, 'units: expected an object')
    raw = layered(displacement_m=SUPPORT)
    raw['units'] = {'length': 'mm', 'temperature': 'K'}
    _refuse(raw, "units: unsupported mechanics keys \\['temperature'\\]")


@pytest.mark.parametrize('change, message', [
    ({'dirichlet_temperature_k': {}}, 'pure Neumann unsupported'),
    ({'thermal_expansion_per_k': 1e-5}, 'takes thermal_expansion_per_k from materials'),
    ({'thermal_conductivity_w_mk': 1.0}, 'thermal_conductivity_w_mk: a region document takes conductivity_w_mk'),
    ({'reference_temperature_k': -1.0}, 'reference_temperature_k: expected a finite nonnegative number'),
    ({'heat_source_w_m3': {'nowhere': 1.0}}, 'heat_source_w_m3.nowhere: no shape or background'),
    ({'outward_flux_w_m2': {'seam': 1.0}}, "selection 'seam' lies on an interface between two regions; flux"),
])
def test_r6_thermoelastic_refusals_name_the_entry(change, message):
    raw = _seam(layered('mechanics.thermoelastic2d', displacement_m=SUPPORT, dirichlet_temperature_k={'left': 300.0}))
    raw['physics']['bar'].update(change)
    _refuse(raw, message)
    raw = layered('mechanics.thermoelastic2d', displacement_m=SUPPORT, dirichlet_temperature_k={'left': 300.0})
    del raw['materials']['steel']['conductivity_w_mk']
    _refuse(raw, 'materials.steel.conductivity_w_mk: required by mechanics.thermoelastic2d')


def test_r6_mesh_time_refusals_name_the_entry():
    # a void splits the bar; only the left part is held
    raw = layered(displacement_m={'left': {'x': 0.0, 'y': 0.0}})
    raw['geometry']['components']['main']['features'] = [
        dict(name='gap', type='rect', x=40.0, y=0.0, w=10.0, h=20.0, material=None),
        dict(name='right_part', type='rect', x=50.0, y=0.0, w=50.0, h=20.0, material='aluminium')]
    with pytest.raises(DocumentError, match="rigid-body motion free in the part of the body made of regions "
                                            "\\['right_part'\\]"):
        solve(raw)
    # two names fix a shared corner node differently
    with pytest.raises(DocumentError, match="'left' and 'bottom' share node .* with different x displacements"):
        solve(layered(displacement_m={'left': {'x': 0.0}, 'bottom': {'x': 1e-6, 'y': 0.0}}))
    # a selection and the side tag carry the same edges, both loaded
    raw = layered(displacement_m=SUPPORT, traction_pa={'right': [1.0, 0.0], 'end_right': [1.0, 0.0]})
    raw['geometry']['components']['main']['selections'] = {
        'end_right': {'boundary': {'between': ['alu', 'exterior']}}}
    with pytest.raises(DocumentError, match="share mesh edges and both carry a traction"):
        solve(raw)


def test_r6_loads_on_prescribed_components_are_decided_per_edge():
    # the top is held in x and pressed normally (in y): well posed, accepted
    held = layered(displacement_m={**SUPPORT, 'top': {'x': 0.0}}, pressure_pa={'top': 1e6})
    assert solve(held).summary()['pressure_pa'] == {'top': 1e6}
    # a pressure on the left side, whose x displacement is prescribed, loads that component
    with pytest.raises(DocumentError, match="pressure_pa.left loads the x component of an edge whose x "
                                            "displacement 'left' prescribes"):
        solve(layered(displacement_m=SUPPORT, pressure_pa={'left': 1e6}))
    # a traction under another name on edges a selection fixes
    raw = layered(displacement_m={**SUPPORT, 'end_right': {'x': 0.0}}, traction_pa={'right': [1.0, 0.0]})
    raw['geometry']['components']['main']['selections'] = {
        'end_right': {'boundary': {'between': ['alu', 'exterior']}}}
    with pytest.raises(DocumentError, match="traction_pa.right loads the x component of an edge whose x "
                                            "displacement 'end_right' prescribes"):
        solve(raw)


def test_r6_a_side_that_borders_a_void_only_has_no_mesh_edge():
    raw = layered(displacement_m={**SUPPORT, 'right': {'x': 0.0}})
    raw['geometry']['components']['main']['features'] = [
        dict(name='gap', type='rect', x=90.0, y=0.0, w=10.0, h=20.0, material=None)]
    with pytest.raises(DocumentError, match="displacement_m.right: no mesh edge lies on 'right'"):
        solve(raw)


def test_r6_cli_exits_1_without_output_for_a_mesh_time_refusal(tmp_path):
    model = tmp_path / 'model.json'
    model.write_text(json.dumps(layered(displacement_m=SUPPORT, pressure_pa={'left': 1e6})), encoding='utf-8')
    out = tmp_path / 'out'
    assert main(['run', str(model), '-o', str(out)]) == 1
    assert not out.exists()


def test_r6_cli_refuses_with_exit_2_and_no_output(tmp_path):
    raw = _seam(layered(displacement_m={**SUPPORT, 'seam': {'x': 0.0}}))
    model = tmp_path / 'model.json'
    model.write_text(json.dumps(raw), encoding='utf-8')
    out = tmp_path / 'out'
    assert main(['run', str(model), '-o', str(out)]) == 2
    assert not out.exists()


# -- R7: mesh limits ---------------------------------------------------------------------------


def test_r7_mesh_limits_reach_region_mechanics_only():
    raw = layered(displacement_m=SUPPORT, traction_pa={'right': [1.0, 0.0]})
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
        assert summary['result_format'] == data['physics'][next(iter(data['physics']))]['type'] + '-result-v1'
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
    assert max(abs(v) for v in summary['diagnostics']['force_balance_n_per_m']) <= 1e-6 * max(
        1.0, *map(abs, summary['diagnostics']['support_reaction_n_per_m']))


# -- length units: only lengths follow units.length; SI-suffixed values are never converted ------

SCALE = {'m': 1e-3, 'mm': 1.0, 'um': 1e3, 'nm': 1e6}
LENGTH_KEYS = ('xmin', 'xmax', 'ymin', 'ymax', 'x', 'y', 'w', 'h', 'cx', 'cy', 'r')


def _in_unit(raw, unit):
    """The millimetre document ``raw`` with every length written in ``unit``; SI values untouched.

    The lengths are scaled by a float product: exact enough here because a version 1 block reads
    them onto the 1 pm grid. A 0.2 document is not covered (its micrometre copy is checked by
    the region heat length tests)."""
    out = copy.deepcopy(raw)
    k = SCALE[unit]
    comp = out['geometry']['components']['main']
    comp['domain'] = {key: v * k for key, v in comp['domain'].items()}
    for f in comp['features']:
        for key in LENGTH_KEYS:
            if key in f:
                f[key] = f[key] * k
    out['mesh']['size'] = out['mesh']['size'] * k
    out['units']['length'] = unit
    return out


@pytest.mark.parametrize('name, physics', [
    ('elastic_regions', {'displacement_m': {'left': {'x': 1e-7}, 'bottom': {'y': 0.0}},
                         'body_force_n_m3': [1e5, -2e6]}),
    ('thermoelastic_regions', {'displacement_m': {'left': {'x': 1e-7, 'y': 0.0}}, 'body_force_n_m3': [0.0, -1e5],
                               'pressure_pa': {'right': 2e6}}),
])
def test_region_results_do_not_depend_on_the_length_unit(name, physics):
    """Not pre-registered (the units review of 2026-11-08 measured it; added as a regression)."""
    raw = copy.deepcopy(examples.EXAMPLES[name])
    raw['physics'][next(iter(raw['physics']))].update(physics)
    ref = solve(raw)
    for unit in ('m', 'um', 'nm'):
        other = solve(_in_unit(raw, unit))
        for key, array in ref.fields.items():
            np.testing.assert_array_equal(other.fields[key], array, err_msg=f'{unit}: {key}')
        assert abs(other.summary()['mesh']['achieved_min_angle_deg'] - ref.summary()['mesh']['achieved_min_angle_deg']) \
            <= 1e-12 * ref.summary()['mesh']['achieved_min_angle_deg']
    # the comparison sees a wrong unit: millimetre numbers declared as metres
    wrong = copy.deepcopy(raw)
    wrong['units']['length'] = 'm'
    assert not np.array_equal(solve(wrong).fields['displacement_m'], ref.fields['displacement_m'])
