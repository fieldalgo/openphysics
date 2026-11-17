# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""``joule.temperature2d`` on named material regions.

A temperature-dependent Joule heating document whose geometry has regions (flat
``background``/``shapes`` or a version 1 block with features or a background material) takes
the geometry, mesh and boundary names of region steady Joule heating
(:mod:`simcase.joule_regions`): potentials and currents on the exterior names region electric
conduction takes, temperatures, fluxes and convection on the names region heat takes. Each
material gives ``thermal_conductivity`` (a constant) and ``electrical_conductivity``, either a
constant (``"2 S/m"``) or the ``linear_resistivity`` model of the rectangle form (same keys,
same checks); ``initial_temperature`` and ``iteration`` are those of the rectangle form.

galerkin's :func:`~galerkin.temperature_joule_heating.solve_temperature_joule_heat` receives a
region table {region name: ConductivityModel}: a model material its law on its
``valid.temperature`` range, a constant material a model of constant value on
``electric_joule.CONSTANT_MODEL_RANGE`` (0 K to the largest double; galerkin refuses an
infinite range, and every finite temperature from 0 K up lies in this one, so it never binds).
The initial, prescribed and ambient temperatures must lie inside every model material's
``valid.temperature`` (their intersection; an empty intersection is refused). Conductivities on
the physics entry, ``heat_source_density``, an axisymmetric component and a void background
are refused by name. Picard iteration only, as on a rectangle; a failed iteration raises
``JouleConvergenceError`` with its history, unchanged.

Format 0.3: the mesh is the region heat hand-off's (``handoff_03``); galerkin's solves compute
with ``0.0 - inward_current_density`` and ``0.0 - inward_heat_flux`` (H1; galerkin takes the inward
values and negates them, ``views.galerkin_electric_arguments``).
"""

import math
import time

import numpy as np

from . import views
from .electric_regions import (ELECTRIC_KEYS, boundary_data_03, outward_terminal_currents, region_entry_03,
                               region_inputs as electric_inputs, summary_lines_03)
from .thermal_regions import (_refuse, NAMES_03, boundary_names, build_region_mesh, component_03, covered_shapes,
                              default_boundaries_03, depth_03, exterior_sides, handoff_03, has_region_geometry,
                              mesh_controls_03, mesh_diagnostics_03, region_geometry_03, region_inputs as heat_inputs,
                              region_materials_table_03, region_mesh_settings_03, sides_03)

PHYSICS = 'joule.temperature2d'
RESULT_FORMAT = 'joule.temperature2d-regions-result-v2'
FIELD_LAYOUT = 'electric-joule2d-temperature-p1-node-cell-regions-v2'
HEAT_KEYS = ('prescribed_temperature', 'inward_heat_flux', 'convection')
_MODEL_KEYS = ('reference_conductivity', 'reference_temperature', 'resistivity_temperature_coefficient')


def is_region_joule_temperature(data):
    """A temperature-dependent Joule heating document that declares region geometry."""
    return has_region_geometry(data, PHYSICS)


def valid_range_03(doc, used):
    """``(lo, hi, owner)``: the intersection of the ``valid.temperature`` ranges of the model
    materials among ``used`` (K), and the words that name it; None when no material is a
    model. Disjoint ranges are refused at the first material whose range empties it."""
    materials = doc.si['materials']
    models = [m for m in used if isinstance(materials[m]['electrical_conductivity'], dict)]
    if not models:
        return None
    lo, hi = -math.inf, math.inf
    for m in models:
        a, b = materials[m]['electrical_conductivity']['valid']['temperature']
        lo, hi = max(lo, a), min(hi, b)
        if lo > hi:
            where = f'materials.{m}.electrical_conductivity.valid.temperature'
            _refuse(f'{where}: [{a!r}, {b!r}] K does not overlap the valid.temperature of the materials before it '
                    f'({models[:models.index(m)]}); every temperature of the solve must lie in each model\'s range',
                    where)
    owner = (f"the conductivity model's (materials.{models[0]})" if len(models) == 1 else
             f'the intersection of the conductivity models\' ({", ".join(f"materials.{m}" for m in models)})')
    return lo, hi, owner


def validate_region_joule_temperature(doc):
    """joule.temperature2d on regions, format 0.3."""
    from .electric_joule import (_model_checks, default_electric_boundaries_03, iteration_checks_03, single_study_03,
                                 temperatures_in_range_03)
    name, p, path = region_entry_03(doc, 'temperature-dependent Joule heating',
                                    ('electrical_conductivity', 'thermal_conductivity'))
    region_mesh_settings_03(doc)
    h = handoff_03(doc)
    region_geometry_03(doc, h, 'Joule heating')
    mesh_controls_03(doc, h)
    used = region_materials_table_03(doc, h, ('electrical_conductivity', 'thermal_conductivity'),
                                     'temperature-dependent Joule heating', 'electric and thermal properties')
    materials = doc.si['materials']
    for m in used:
        value = materials[m]['electrical_conductivity']
        if isinstance(value, dict):
            _model_checks(value, f'materials.{m}')
        elif not value > 0:
            _refuse(f'materials.{m}.electrical_conductivity: expected a positive conductivity',
                    f'materials.{m}.electrical_conductivity', 'E-DOMAIN')
    names = boundary_names(h)
    boundary_data_03(p, path, names)
    sides = exterior_sides(h)[1]
    sides_03(p, name, sides, names)
    default_electric_boundaries_03(doc, name, p, sides)
    default_boundaries_03(doc, name, p, sides)
    valid = valid_range_03(doc, used)
    if valid is not None:
        temperatures_in_range_03(p, path, *valid)
    iteration_checks_03(p, path)
    single_study_03(doc, PHYSICS)


def _material_line(doc, mname, spec):
    from .thermal import _authored
    where = f'materials.{mname}'
    out = []
    for k, value in spec.items():
        if k == 'source':
            continue
        if isinstance(value, dict):
            m = f'{where}.{k}'
            lo, hi = doc.authored(f'{m}.valid.temperature')
            out.append(f'{k} {value["model"]} ('
                       + ', '.join(f'{key} {_authored(doc, f"{m}.{key}")}' for key in _MODEL_KEYS)
                       + f', valid.temperature [{lo}, {hi}])')
        else:
            out.append(f'{k} {_authored(doc, f"{where}.{k}")}')
    return f'  material {mname}: ' + ', '.join(out)


def region_summary(doc):
    from .thermal import _authored
    out = summary_lines_03(doc, f'{PHYSICS}, temperature-dependent Joule heating, named material regions',
                           (*ELECTRIC_KEYS, *HEAT_KEYS), _material_line)
    name = next(iter(doc.si['physics']))
    it = f'physics.{name}.iteration'
    out += [f'  initial_temperature {_authored(doc, f"physics.{name}.initial_temperature")}; Picard iteration: '
            + ', '.join(f'{k} {_authored(doc, f"{it}.{k}")}' for k in doc.data['physics'][name]['iteration'])
            + ' (other options at their defaults)',
            '  other exterior boundaries electrically insulating and insulated',
            f'  result: {RESULT_FORMAT}; layout: {FIELD_LAYOUT}',
            '  output: SI (node_coordinates m, electric_potential V, current_density A/m^2, joule_power_density W/m^3, '
            'temperature K, evaluation_temperature K, heat_flux W/m^2, nodal currents A/m and heat rates W/m of '
            'depth, triangle_regions)']
    return '\n'.join(out)


def regions_block_03(doc, mesh, region_materials):
    """``region_names`` and ``regions.<r>.{material, electrical_conductivity, thermal_conductivity}``:
    a constant as a value object, a model as ``{model, reference_conductivity,
    reference_temperature, resistivity_temperature_coefficient, valid: {temperature: [lo, hi]}}``
    of value objects."""
    from .results_common import value_object as vo
    materials = doc.si['materials']

    def conductivity(value):
        if not isinstance(value, dict):
            return vo(value, 'electrical_conductivity')
        return {'model': value['model'], **{k: vo(value[k], k) for k in _MODEL_KEYS},
                'valid': {'temperature': [vo(t, 'temperature') for t in value['valid']['temperature']]}}
    return {'region_names': list(mesh.region_names),
            'regions': {r: {'material': m, 'electrical_conductivity': conductivity(materials[m]['electrical_conductivity']),
                            'thermal_conductivity': vo(materials[m]['thermal_conductivity'], 'thermal_conductivity')}
                        for r, m in region_materials.items()}}


def solver_inputs(doc, mesh, region_materials):
    """``(keyword arguments of solve_temperature_joule_heat, the boundary that fixes each fixed
    potential node)`` for a meshed, validated region document: the conductivity table is
    {region name: ConductivityModel of its material}."""
    electric = views.region_joule_temperature(doc)
    electric_kwargs, fixed_by = electric_inputs(doc, mesh, region_materials, electric)
    heat_kwargs = heat_inputs(doc, mesh, region_materials, views.region_heat_03(doc), NAMES_03)
    # galerkin's keywords and inward values (views.galerkin_*_arguments): the same doubles (H1)
    electric_kw = views.galerkin_electric_arguments(electric_kwargs)
    heat_kw = views.galerkin_heat_arguments(heat_kwargs)
    kwargs = dict(electrical_conductivity={r: electric.conductivity_model[m] for r, m in region_materials.items()},
                  thermal_conductivity=heat_kw['thermal_conductivity'],
                  prescribed_electric_potential=electric_kw['prescribed_electric_potential'],
                  prescribed_temperature=heat_kw['prescribed_temperature'],
                  initial_temperature=electric.initial_temperature,
                  inward_current_density=electric_kw['inward_current_density'],
                  inward_heat_flux=heat_kw['inward_heat_flux'],
                  convection=heat_kw['convection'], method='picard', **electric.iteration)
    return kwargs, fixed_by


def run_region_joule_temperature(doc, verbose=True, *, mesh_limits=None):
    from galerkin.temperature_joule_heating import JouleConvergenceError, solve_temperature_joule_heat
    from .electric_joule import (RegionJouleTemperatureRunResult, electric_balance, heat_balance, result_arrays,
                                 summary_03)
    from .thermal import log_lines_03
    doc.validate()
    given, doc = doc, doc.copy()
    doc.validate()
    name, p = doc.sole_physics()
    t0 = time.perf_counter()
    h = handoff_03(doc)
    mesh, region_materials, tri = build_region_mesh(h, mesh_limits)
    for target in (given, doc):
        mesh_diagnostics_03(target, component_03(doc)[0], h.notes)
    kwargs, fixed_by = solver_inputs(doc, mesh, region_materials)
    t_mesh = time.perf_counter()-t0
    calculation_json = doc.canonical_json(separators=(',', ':'))
    t0 = time.perf_counter()
    try:
        nonlinear = solve_temperature_joule_heat(mesh, **kwargs)
    except JouleConvergenceError:
        raise                                   # its history is the evidence (simcase.cli prints it)
    except ValueError as exc:
        raise ValueError(f'physics.{name} ({PHYSICS}): {exc}') from exc
    t_solve = time.perf_counter()-t0
    if doc.canonical_json(separators=(',', ':')) != calculation_json:
        raise ValueError('Joule calculation inputs changed during the solve')
    coupled = nonlinear.coupled
    electric, heat = coupled.electrical, coupled.thermal
    fixed, held = kwargs['prescribed_electric_potential'], kwargs['prescribed_temperature']
    arrays = result_arrays(mesh, electric, fixed, regions=mesh.regions, heat=heat, heat_fixed=held,
                           evaluated=nonlinear.evaluation_temperature)
    balance = electric_balance(electric, fixed, mesh)
    balance['outward_current_per_depth'] = outward_terminal_currents(electric, fixed_by,
                                                                     doc.si['physics'][name]['prescribed_electric_potential'])
    balance.update(heat_balance(coupled, held, mesh))
    metadata = summary_03(doc, result_format=RESULT_FORMAT, field_layout=FIELD_LAYOUT, arrays=arrays, balance=balance,
                          timings={'mesh': t_mesh, 'solve': t_solve}, mesh=mesh, depth=depth_03(doc),
                          extra=regions_block_03(doc, mesh, region_materials), history=nonlinear.history,
                          minimum_angle=math.radians(float(tri.min_angle())))
    covered = covered_shapes(h, mesh)
    printed = [doc.summary(),
               f'mesh: {mesh.num_nodes} nodes, {len(mesh.triangles)} triangles, regions {mesh.region_names}',
               *([f'shapes fully covered by later shapes (no triangles): {covered}'] if covered else []),
               f'converged in {len(nonlinear.history)} Picard iterations; joule_power_per_depth '
               f'{electric.joule_power_per_depth:.12g} W/m; temperature: {float(np.min(heat.temperature)):.12g} K to '
               f'{float(np.max(heat.temperature)):.12g} K']
    if verbose:
        print('\n'.join(printed))
    result = RegionJouleTemperatureRunResult(doc, arrays, metadata, log_lines_03(doc, printed))
    result.region_materials = region_materials
    return result
