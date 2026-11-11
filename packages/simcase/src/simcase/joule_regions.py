# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""``joule.steady2d`` on named material regions.

A steady Joule heating document whose geometry has regions (flat ``background``/``shapes`` or a
version 1 block with features or a background material) solves region electric conduction
(:mod:`simcase.electric_regions`) and heats region steady heat (:mod:`simcase.thermal_regions`)
with its Joule heating, on one mesh: the electric conductivity of each region is its material's
``electrical_conductivity``, the thermal conductivity its ``thermal_conductivity``. The
potential and current data take the boundary names region electric conduction takes (exterior
boundaries only); the temperature, flux and convection data the names region heat takes (a
prescribed temperature may also fix an interface selection). The only heat source is the Joule
heating, so ``heat_source_density`` is refused, as are the conductivities of the rectangle form
on the physics entry. :func:`galerkin.joule_heating.solve_steady_joule_heat` checks that the
heat load equals the Joule load node by node and that the outward heat equals the Joule power.
Temperature-dependent conductivity (``joule.temperature2d``) and an axisymmetric component are
refused. A rectangle document keeps the rectangle path (:mod:`simcase.electric_joule`).

Format 0.3 (units batch C6): the mesh is the region heat hand-off's (``handoff_03``); galerkin
receives ``0.0 - inward_current_density`` and ``0.0 - inward_heat_flux`` (H1).
"""

import math
import time

import numpy as np

from . import views
from .electric_regions import (ELECTRIC_KEYS, boundary_data_03, outward_terminal_currents, positive_conductivities_03,
                               region_entry_03, region_inputs as electric_inputs, regions_block_03, summary_lines_03)
from .thermal_regions import (NAMES_03, boundary_names, build_region_mesh, component_03, covered_shapes,
                              default_boundaries_03, depth_03, exterior_sides, handoff_03, has_region_geometry,
                              mesh_controls_03, mesh_diagnostics_03, region_geometry_03, region_inputs as heat_inputs,
                              region_materials_table_03, region_mesh_settings_03, sides_03)

PHYSICS = 'joule.steady2d'
RESULT_FORMAT = 'joule.steady2d-regions-result-v2'
FIELD_LAYOUT = 'electric-joule2d-p1-node-cell-regions-v2'
HEAT_KEYS = ('prescribed_temperature', 'inward_heat_flux', 'convection')


def is_region_joule(data):
    """A steady Joule heating document that declares region geometry."""
    return has_region_geometry(data, PHYSICS)


def validate_region_joule(doc):
    """joule.steady2d on regions, format 0.3."""
    from .electric_joule import default_electric_boundaries_03, single_study_03
    name, p, path = region_entry_03(doc, 'Joule heating', ('electrical_conductivity', 'thermal_conductivity'))
    region_mesh_settings_03(doc)
    h = handoff_03(doc)
    region_geometry_03(doc, h, 'Joule heating')
    mesh_controls_03(doc, h)
    used = region_materials_table_03(doc, h, ('electrical_conductivity', 'thermal_conductivity'),
                                     'steady Joule heating', 'electric and thermal properties')
    positive_conductivities_03(doc, used, ('electrical_conductivity',))
    names = boundary_names(h)
    boundary_data_03(p, path, names)
    sides = exterior_sides(h)[1]
    sides_03(p, name, sides, names)
    default_electric_boundaries_03(doc, name, p, sides)
    default_boundaries_03(doc, name, p, sides)
    single_study_03(doc, PHYSICS)


def region_summary(doc):
    out = summary_lines_03(doc, f'{PHYSICS}, steady Joule heating, named material regions', (*ELECTRIC_KEYS, *HEAT_KEYS))
    out += ['  other exterior boundaries electrically insulating and insulated',
            f'  result: {RESULT_FORMAT}; layout: {FIELD_LAYOUT}',
            '  output: SI (node_coordinates m, electric_potential V, current_density A/m^2, joule_power_density W/m^3, '
            'temperature K, heat_flux W/m^2, nodal currents A/m and heat rates W/m of depth, triangle_regions)']
    return '\n'.join(out)


def run_region_joule(doc, verbose=True, *, mesh_limits=None):
    from galerkin.electric import solve_steady_electric
    from galerkin.joule_heating import solve_steady_joule_heat
    from .electric_joule import RegionJouleRunResult, electric_balance, heat_balance, result_arrays, summary_03
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
    electric_kwargs, fixed_by = electric_inputs(doc, mesh, region_materials)
    heat_kwargs = heat_inputs(doc, mesh, region_materials, views.region_heat_03(doc), NAMES_03)
    heat_kwargs.pop('heat_source')
    t_mesh = time.perf_counter()-t0
    calculation_json = doc.canonical_json(separators=(',', ':'))
    t0 = time.perf_counter()
    try:
        electric = solve_steady_electric(mesh, **electric_kwargs)
        coupled = solve_steady_joule_heat(mesh, electrical_result=electric, **heat_kwargs)
    except (ValueError, RuntimeError) as exc:
        raise ValueError(f'physics.{name} ({PHYSICS}): {exc}') from exc
    t_solve = time.perf_counter()-t0
    if doc.canonical_json(separators=(',', ':')) != calculation_json:
        raise ValueError('Joule calculation inputs changed during the solve')
    electric, heat = coupled.electrical, coupled.thermal
    fixed, held = electric_kwargs['dirichlet'], heat_kwargs['dirichlet']
    arrays = result_arrays(mesh, electric, fixed, regions=mesh.regions, heat=heat, heat_fixed=held)
    balance = electric_balance(electric, fixed, mesh)
    balance['outward_current_per_depth'] = outward_terminal_currents(electric, fixed_by,
                                                                     doc.si['physics'][name]['prescribed_electric_potential'])
    balance.update(heat_balance(coupled, held, mesh))
    metadata = summary_03(doc, result_format=RESULT_FORMAT, field_layout=FIELD_LAYOUT, arrays=arrays, balance=balance,
                          timings={'mesh': t_mesh, 'solve': t_solve}, mesh=mesh, depth=depth_03(doc),
                          extra=regions_block_03(doc, mesh, region_materials,
                                                 ('electrical_conductivity', 'thermal_conductivity')),
                          minimum_angle=math.radians(float(tri.min_angle())))
    covered = covered_shapes(h, mesh)
    printed = [doc.summary(),
               f'mesh: {mesh.num_nodes} nodes, {len(mesh.triangles)} triangles, regions {mesh.region_names}',
               *([f'shapes fully covered by later shapes (no triangles): {covered}'] if covered else []),
               f'joule_power_per_depth {electric.joule_power_per_length:.12g} W/m; temperature: '
               f'{float(np.min(heat.temperature)):.12g} K to {float(np.max(heat.temperature)):.12g} K']
    if verbose:
        print('\n'.join(printed))
    result = RegionJouleRunResult(doc, arrays, metadata, log_lines_03(doc, printed))
    result.region_materials = region_materials
    return result
