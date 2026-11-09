# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""``joule.steady2d`` on named material regions.

A steady Joule heating document whose geometry has regions (a version 1 block with
features or a background material, or 0.2 ``shapes``) solves region electric conduction
(:mod:`simcase.electric_regions`) and heats region steady heat
(:mod:`simcase.thermal_regions`) with its Joule heating, on one mesh: the electric
conductivity of each region is its material's ``electrical_conductivity_s_m``, the thermal
conductivity its ``conductivity_w_mk``. The potential and current data take the boundary
names region electric conduction takes (exterior boundaries only); the temperature, flux and
convection data the names region heat takes (a Dirichlet temperature may also fix an
interface selection). The only heat source is the Joule heating, so ``heat_source_w_m3`` is
refused, as are the scalar conductivities of the rectangle form.
:func:`galerkin.joule_heating.solve_steady_joule_heat` checks that the heat load equals the
Joule load node by node and that the outward heat equals the Joule power. Temperature-
dependent conductivity (``joule.temperature2d``) and an axisymmetric component are refused.
A rectangle document keeps the existing path (:mod:`simcase.electric_joule`) unchanged.
"""

import copy
import json
import time

import numpy as np

from .schema import DocumentError
from .steady_boundary_contract import _object
from .electric_regions import _boundary_data, _neutral, region_inputs as electric_inputs
from .thermal_regions import (_sides, boundary_names, build_region_mesh, covered_shapes, exterior_sides,
                              has_region_geometry, is_axisymmetric, region_geometry, region_inputs as heat_inputs,
                              region_materials_table, region_mesh_settings)

PHYSICS = 'joule.steady2d'
RESULT_FORMAT = 'joule.steady2d-regions-result-v1'
FIELD_LAYOUT = 'electric-joule2d-p1-node-cell-regions-v1'
ELECTRIC_KEYS = ('dirichlet_potential_v', 'outward_current_a_m2')
HEAT_KEYS = ('dirichlet_temperature_k', 'outward_flux_w_m2', 'convection')


def is_region_joule(data):
    """A steady Joule heating document that declares region geometry."""
    return has_region_geometry(data, PHYSICS)


def validate_region_joule(doc):
    d = doc.data
    _object(d, {'openphysics', 'name', 'units', 'geometry', 'materials', 'physics', 'mesh', 'study', 'results'},
            'document')
    if not isinstance(d['name'], str):
        raise DocumentError('name: expected a string')
    physics = d['physics']
    if not isinstance(physics, dict) or len(physics) != 1:
        raise DocumentError('physics: exactly one Joule entry required')
    name, p = next(iter(physics.items()))
    if not isinstance(name, str) or not name.isidentifier() or not isinstance(p, dict):
        raise DocumentError('physics: expected identifier and settings object')
    path = f'physics.{name}'
    for key, where in (('conductivity_s_m', 'electrical_conductivity_s_m'),
                       ('thermal_conductivity_w_mk', 'conductivity_w_mk')):
        if key in p:
            raise DocumentError(f'{path}.{key}: a region document takes conductivity from materials ({where})')
    if 'heat_source_w_m3' in p:
        raise DocumentError(f'{path}.heat_source_w_m3: a Joule document is heated by its current only; '
                            'an additional heat source is not supported')
    _object(p, {'type', *ELECTRIC_KEYS, *HEAT_KEYS}, path)
    _object(d.get('units'), {'length', 'temperature'}, 'units')
    if 'length' not in doc.scale.declared or d['units'].get('temperature') != 'K':
        raise DocumentError(f'{PHYSICS} requires explicit units.length and units.temperature="K"')
    if is_axisymmetric(doc):
        raise DocumentError(f'{PHYSICS}: an axisymmetric component is not supported for Joule heating '
                            '(galerkin.electric has no axisymmetric measure)')
    region_geometry(doc, 'Joule heating')
    _neutral(region_materials_table, doc, ('electrical_conductivity_s_m', 'conductivity_w_mk'), 'steady Joule heating')
    names = boundary_names(doc)
    _neutral(_boundary_data, p, path, names)
    _sides(p, name, exterior_sides(doc)[1], names)
    _neutral(region_mesh_settings, doc)
    if d['study'] != {'type': 'single'}:
        raise DocumentError(f'{PHYSICS} supports only study {{"type":"single"}}')
    _object(d['results'], {'save_fields', 'plots'}, 'results')
    if not isinstance(d['results'].get('save_fields'), bool) or not isinstance(d['results'].get('plots'), bool):
        raise DocumentError('results.save_fields and results.plots must be booleans')
    if d['results']['plots']:
        raise DocumentError(f'results.plots: {PHYSICS} is headless; plots=true is not supported')
    doc.notes = []


def region_summary(doc):
    name, p = doc.sole_physics()
    lines = [f'{doc["name"]} (openphysics 0.2)',
             f'  physics {name}: {PHYSICS}, steady Joule heating, named material regions',
             f'  domain {doc.domain} {doc.length_unit}; mesh size {doc["mesh"]["size"]} {doc.length_unit}',
             f'  background: {doc.background["material"]}']
    for s in doc.regions():
        lines.append(f'  shape {s["name"]}: {s["type"]}, {s["material"] if s["material"] is not None else "void (hole)"}')
    for mname, spec in doc['materials'].items():
        if 'electrical_conductivity_s_m' in spec or 'conductivity_w_mk' in spec:
            lines.append(f'  material {mname}: sigma={spec.get("electrical_conductivity_s_m")} S/m, '
                         f'k={spec.get("conductivity_w_mk")} W/(m K)')
    lines += [f'  potential {p.get("dirichlet_potential_v", {})} V; current {p.get("outward_current_a_m2", {})} A/m^2',
              f'  temperature {p.get("dirichlet_temperature_k", {})} K; flux {p.get("outward_flux_w_m2", {})} W/m^2; '
              f'convection {p.get("convection", {})}; other exterior insulated',
              '  output: coordinates m, potential V, field V/m, current density A/m^2, Joule W/m^3, temperature K, '
              'heat flux W/m^2, nodal current A/m and heat W/m of depth, triangle regions']
    return '\n'.join(lines)


def run_region_joule(doc, verbose=True, *, mesh_limits=None):
    from galerkin.electric import solve_steady_electric
    from galerkin.joule_heating import solve_steady_joule_heat
    import galerkin
    import scipy
    from . import __version__
    from .electric_joule import RegionJouleRunResult
    doc.validate()
    given, doc = doc, doc.copy()
    doc.validate()
    name, p = doc.sole_physics()
    t0 = time.perf_counter()
    mesh, region_materials, tri = build_region_mesh(doc, mesh_limits)
    given.notes.extend(n for n in doc.notes if n.startswith(('geometry.', 'mesh.controls:')) and n not in given.notes)
    electric_kwargs, fixed_by = electric_inputs(doc, mesh, region_materials)
    heat_kwargs = heat_inputs(doc, mesh, region_materials)
    heat_kwargs.pop('heat_source')
    t_mesh = time.perf_counter()-t0
    calculation_json = json.dumps(doc.data, sort_keys=True, separators=(',', ':'), allow_nan=False)
    t0 = time.perf_counter()
    try:
        electric = solve_steady_electric(mesh, **electric_kwargs)
        coupled = solve_steady_joule_heat(mesh, electrical_result=electric, **heat_kwargs)
    except (ValueError, RuntimeError) as exc:
        raise ValueError(f'physics.{name} ({PHYSICS}): {exc}') from exc
    t_solve = time.perf_counter()-t0
    if json.dumps(doc.data, sort_keys=True, separators=(',', ':'), allow_nan=False) != calculation_json:
        raise ValueError('Joule calculation inputs changed during the solve')
    electric, heat = coupled.electrical, coupled.thermal
    arrays, field_units, locations = {}, {}, {}

    def add(key, value, unit, location):
        arrays[key] = np.asarray(value)
        field_units[key], locations[key] = unit, location
    add('nodes_m', mesh.nodes, 'm', 'nodes')
    add('triangles', mesh.triangles, '1', 'triangle_connectivity')
    add('triangle_regions', mesh.regions, '1', 'triangles')
    for key, attr, unit, location in (
        ('potential_v', 'potential', 'V', 'nodes'),
        ('electric_field_v_m', 'electric_field', 'V/m', 'triangle_centroids'),
        ('current_density_a_m2', 'current_density', 'A/m^2', 'triangle_centroids'),
        ('conductivity_s_m', 'conductivity', 'S/m', 'triangle_centroids'),
        ('joule_heating_w_m3', 'joule_heating', 'W/m^3', 'triangle_centroids'),
        ('joule_load_w_per_m', 'joule_load', 'W/m', 'nodes'),
        ('electric_reaction_a_per_m', 'reaction', 'A/m', 'nodes'),
        ('prescribed_outward_current_a_per_m', 'prescribed_outward_load', 'A/m', 'nodes'),
        ('electric_residual_a_per_m', 'residual', 'A/m', 'nodes')):
        add(key, getattr(electric, attr), unit, location)
    fixed = electric_kwargs['dirichlet']
    add('electric_dirichlet_node_ids', np.array(list(fixed), dtype=int), '1', 'electric_dirichlet_nodes')
    add('dirichlet_potential_v', list(fixed.values()), 'V', 'electric_dirichlet_nodes')
    for key, attr, unit, location in (
        ('temperature_k', 'temperature', 'K', 'nodes'), ('heat_flux_w_m2', 'heat_flux', 'W/m^2', 'triangle_centroids'),
        *((key+'_w_per_m', attr, 'W/m', 'nodes') for key, attr in (
            ('thermal_load', 'load'), ('thermal_reaction', 'reaction'), ('thermal_residual', 'residual'),
            ('prescribed_outward_heat', 'prescribed_outward_load'), ('ambient_load', 'ambient_load'),
            ('convective_outward_heat', 'convective_outward'), ('thermal_system_rhs', 'system_rhs')))):
        add(key, getattr(heat, attr), unit, location)
    held = heat_kwargs['dirichlet']
    add('thermal_dirichlet_node_ids', np.array(list(held), dtype=int), '1', 'thermal_dirichlet_nodes')
    add('dirichlet_temperature_k', list(held.values()), 'K', 'thermal_dirichlet_nodes')
    free_e = np.setdiff1d(np.arange(mesh.num_nodes), list(fixed))
    free_t = np.setdiff1d(np.arange(mesh.num_nodes), list(held))
    reaction = np.asarray(electric.reaction)
    # current injected into the conductor through each fixed boundary (positive in), A/m of
    # depth; a node two boundaries fix counts for the first of them in name order
    terminal = {tag: float(sum(reaction[n] for n, by in fixed_by.items() if by == tag))
                for tag in p['dirichlet_potential_v']}
    diagnostics = dict(
        current_balance_a_per_m=float(np.sum(reaction-np.asarray(electric.prescribed_outward_load))),
        electric_free_residual_a_per_m=float(np.max(abs(np.asarray(electric.residual)[free_e]), initial=0.)),
        supplied_power_w_per_m=electric.supplied_power_per_length,
        joule_power_w_per_m=electric.joule_power_per_length,
        electric_power_defect_w_per_m=electric.supplied_power_per_length-electric.joule_power_per_length,
        terminal_reaction_current_a_per_m=terminal,
        outward_heat_w_per_m=coupled.outward_heat_per_length,
        heat_power_defect_w_per_m=coupled.outward_heat_per_length-coupled.source_power_per_length,
        thermal_free_residual_w_per_m=float(np.max(abs(np.asarray(heat.residual)[free_t]), initial=0.)),
        temperature_min_k=float(np.min(heat.temperature)), temperature_max_k=float(np.max(heat.temperature)),
        mesh_min_angle_deg=float(tri.min_angle()))
    materials = doc['materials']
    metadata = dict(name=doc['name'], physics_name=name, physics_type=PHYSICS, status='converged',
        result_format=RESULT_FORMAT, field_layout=FIELD_LAYOUT, mesh_length_unit='m',
        input_units=copy.deepcopy(doc['units']), field_units=field_units, field_locations=locations,
        field_shapes={k: list(v.shape) for k, v in arrays.items()}, region_names=list(mesh.region_names),
        region_materials=dict(region_materials), region_conductivity_s_m=electric_kwargs['conductivity'],
        region_thermal_conductivity_w_mk={r: float(materials[m]['conductivity_w_mk'])
                                          for r, m in region_materials.items()},
        diagnostics=diagnostics, iterations=[], timings_s=dict(mesh=t_mesh, solve=t_solve),
        software_versions=dict(simcase=__version__, galerkin=galerkin.__version__, numpy=np.__version__,
                               scipy=scipy.__version__))
    covered = covered_shapes(doc, mesh)
    log = [region_summary(doc),
           f'mesh: {mesh.num_nodes} nodes, {len(mesh.triangles)} triangles, regions {mesh.region_names}',
           *([f'shapes fully covered by later shapes (no triangles): {covered}'] if covered else []),
           f'Joule power {electric.joule_power_per_length:.12g} W/m of depth; '
           f'temperature K: {float(np.min(heat.temperature)):.12g} to {float(np.max(heat.temperature)):.12g}']
    if verbose:
        print('\n'.join(log))
    result = RegionJouleRunResult(doc, arrays, metadata, log)
    result.region_materials = region_materials
    return result
