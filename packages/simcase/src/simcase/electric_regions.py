# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""``electric.steady2d`` on named material regions.

A steady conduction document whose geometry has regions (a version 1 block with features
or a background material, or 0.2 ``shapes``) uses the same geometry, mesh and boundary
names as region heat (:mod:`simcase.thermal_regions`): the conductivity of each region is
its material's ``electrical_conductivity_s_m``; ``dirichlet_potential_v`` and
``outward_current_a_m2`` take the domain sides, the exterior tags the geometry declares
(``boundary_tags`` names, ``outer`` on a void border) and exterior boundary selections.
An interior selection (an interface between two regions) is refused for both, because
:func:`galerkin.electric.solve_steady_electric` fixes exterior nodes only. An unnamed
exterior boundary is insulated. A rectangle document keeps the existing path
(:mod:`simcase.electric_joule`) unchanged.
"""

import copy
import json
import time

import numpy as np

from .schema import DocumentError
from .steady_boundary_contract import _number, _object
from .thermal_regions import (SIDES, _named_sides, boundary_names, build_region_mesh, covered_shapes,
                              has_region_geometry, is_axisymmetric, region_geometry, region_materials_table,
                              region_mesh_settings)

PHYSICS = 'electric.steady2d'
RESULT_FORMAT = 'electric.steady2d-regions-result-v1'
FIELD_LAYOUT = 'electric2d-p1-node-cell-regions-v1'
JOULE_TYPES = ('joule.steady2d', 'joule.temperature2d')


def is_region_electric(data):
    """A steady electric conduction document that declares region geometry."""
    return has_region_geometry(data, PHYSICS)


def refuse_region_joule(data):
    """Joule documents take the rectangle path only; region geometry is refused by name."""
    for kind in JOULE_TYPES:
        if has_region_geometry(data, kind):
            raise DocumentError(f'{kind}: region geometry (named material regions) is supported for '
                                f'{PHYSICS} only; a Joule document takes the rectangle form')


def validate_region_electric(doc):
    d = doc.data
    _object(d, {'openphysics', 'name', 'units', 'geometry', 'materials', 'physics', 'mesh', 'study', 'results'},
            'document')
    if not isinstance(d['name'], str):
        raise DocumentError('name: expected a string')
    physics = d['physics']
    if not isinstance(physics, dict) or len(physics) != 1:
        raise DocumentError('physics: exactly one electric entry required')
    name, p = next(iter(physics.items()))
    if not isinstance(name, str) or not name.isidentifier() or not isinstance(p, dict):
        raise DocumentError('physics: expected identifier and settings object')
    path = f'physics.{name}'
    if 'conductivity_s_m' in p:
        raise DocumentError(f'{path}.conductivity_s_m: a region document takes electrical conductivity from '
                            'materials (electrical_conductivity_s_m)')
    _object(p, {'type', 'dirichlet_potential_v', 'outward_current_a_m2'}, path)
    _object(d.get('units'), {'length', 'temperature'}, 'units')
    if 'length' not in doc.scale.declared:
        raise DocumentError(f'{PHYSICS} requires explicit units.length')
    if 'temperature' in d['units'] and d['units']['temperature'] != 'K':
        raise DocumentError('units.temperature: expected K')
    if is_axisymmetric(doc):
        raise DocumentError(f'{PHYSICS}: an axisymmetric component is not supported for electric conduction '
                            '(galerkin.electric has no axisymmetric measure)')
    region_geometry(doc, 'electric')
    region_materials_table(doc, ('electrical_conductivity_s_m',), 'steady electric conduction')
    _boundary_data(p, path, boundary_names(doc))
    region_mesh_settings(doc)
    if d['study'] != {'type': 'single'}:
        raise DocumentError(f'{PHYSICS} supports only study {{"type":"single"}}')
    _object(d['results'], {'save_fields', 'plots'}, 'results')
    if not isinstance(d['results'].get('save_fields'), bool) or not isinstance(d['results'].get('plots'), bool):
        raise DocumentError('results.save_fields and results.plots must be booleans')
    if d['results']['plots']:
        raise DocumentError(f'results.plots: {PHYSICS} is headless; plots=true is not supported')
    doc.notes = []


def _boundary_data(p, path, names):
    """Names and values of the potential and current data, before meshing."""
    tags, outside, inside = names
    allowed = set(SIDES) | tags | outside
    for label in ('dirichlet_potential_v', 'outward_current_a_m2'):
        table = p.get(label, {})
        if isinstance(table, dict):
            for key in table:
                if key in inside:
                    raise DocumentError(f'{path}.{label}.{key}: selection {key!r} lies on an interface between two '
                                        'regions; electric data apply to exterior boundaries only (galerkin.electric '
                                        'fixes exterior nodes only)')
        _named_sides(table, allowed, f'{path}.{label}')
        for key, value in table.items():
            _number(value, f'{path}.{label}.{key}')
    bc = p.get('dirichlet_potential_v', {})
    if not bc:
        raise DocumentError(f'{path}.dirichlet_potential_v: at least one boundary potential is required; '
                            'gauge-only inputs are unsupported')
    for a in ('left', 'right'):
        for b in ('bottom', 'top'):
            if a in bc and b in bc and bc[a] != bc[b]:
                raise DocumentError(f'{path}.dirichlet_potential_v: conflicting potentials at the {a}/{b} corner')
    if set(bc) & set(p.get('outward_current_a_m2', {})):
        raise DocumentError(f'{path}: a current condition overlaps a fixed potential on the same boundary')


def region_summary(doc):
    name, p = doc.sole_physics()
    lines = [f'{doc["name"]} (openphysics 0.2)',
             f'  physics {name}: {PHYSICS}, steady conduction, named material regions',
             f'  domain {doc.domain} {doc.length_unit}; mesh size {doc["mesh"]["size"]} {doc.length_unit}',
             f'  background: {doc.background["material"]}']
    for s in doc.regions():
        lines.append(f'  shape {s["name"]}: {s["type"]}, {s["material"] if s["material"] is not None else "void (hole)"}')
    for mname, spec in doc['materials'].items():
        if 'electrical_conductivity_s_m' in spec:
            lines.append(f'  material {mname}: sigma={spec["electrical_conductivity_s_m"]} S/m')
    lines += [f'  potential {p.get("dirichlet_potential_v", {})} V; current {p.get("outward_current_a_m2", {})} A/m^2; '
              'other exterior insulated',
              '  output: coordinates m, potential V, field V/m, current density A/m^2, Joule W/m^3, '
              'nodal current A/m and power W/m of depth, triangle regions']
    return '\n'.join(lines)


def region_inputs(doc, mesh, region_materials):
    """solve_steady_electric keyword arguments for a meshed region document, and the boundary
    name that fixes each Dirichlet node."""
    name, p = doc.sole_physics()
    path = f'physics.{name}'
    materials = doc['materials']
    conductivity = {r: float(materials[m]['electrical_conductivity_s_m']) for r, m in region_materials.items()}
    for label, table in (('dirichlet_potential_v', mesh.boundary), ('outward_current_a_m2', mesh.boundary_edges)):
        for tag in p.get(label, {}):
            if tag not in table:
                raise DocumentError(f'{path}.{label}.{tag}: no mesh edge lies on {tag!r} (a side or boundary that '
                                    'borders a void feature only, or a selection without mesh edges)')
    fixed, fixed_by = {}, {}
    for tag, value in p['dirichlet_potential_v'].items():
        for node in map(int, mesh.boundary[tag]):
            if node in fixed and fixed[node] != float(value):
                raise DocumentError(f'{path}.dirichlet_potential_v: {fixed_by[node]!r} and {tag!r} share node {node} '
                                    'with different potentials')
            fixed[node] = float(value)
            fixed_by.setdefault(node, tag)
    current = {tag: float(v) for tag, v in p.get('outward_current_a_m2', {}).items()}
    edges = {tag: {tuple(sorted(map(int, e))) for e in np.asarray(mesh.boundary_edges[tag]).reshape(-1, 2)}
             for tag in current}
    names = sorted(edges)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if edges[a] & edges[b]:
                raise DocumentError(f'{path}.outward_current_a_m2: {a!r} and {b!r} share mesh edges; give that '
                                    'boundary one entry')
    selected = getattr(mesh, 'selection_edges', None) or {}
    for b in p['dirichlet_potential_v']:
        held = mesh.boundary_edges.get(b, selected.get(b))
        if held is None:
            continue
        held = {tuple(sorted(map(int, e))) for e in np.asarray(held).reshape(-1, 2)}
        for a, e in edges.items():
            if a != b and e & held:
                raise DocumentError(f'{path}.outward_current_a_m2.{a}: {a!r} shares mesh edges with the fixed '
                                    f'potential {b!r}; a current condition does not apply on a fixed edge')
    return (dict(conductivity=conductivity, dirichlet=dict(sorted(fixed.items())), outward_current=current),
            fixed_by)


def run_region_electric(doc, verbose=True, *, mesh_limits=None):
    from galerkin.electric import solve_steady_electric
    import galerkin
    import scipy
    from . import __version__
    from .electric_joule import RegionElectricRunResult
    doc.validate()
    given, doc = doc, doc.copy()
    doc.validate()
    name, p = doc.sole_physics()
    t0 = time.perf_counter()
    mesh, region_materials, tri = build_region_mesh(doc, mesh_limits)
    given.notes.extend(n for n in doc.notes if n.startswith(('geometry.', 'mesh.controls:')) and n not in given.notes)
    kwargs, fixed_by = region_inputs(doc, mesh, region_materials)
    t_mesh = time.perf_counter()-t0
    calculation_json = json.dumps(doc.data, sort_keys=True, separators=(',', ':'), allow_nan=False)
    t0 = time.perf_counter()
    try:
        electric = solve_steady_electric(mesh, **kwargs)
    except (ValueError, RuntimeError) as exc:
        raise ValueError(f'physics.{name} ({PHYSICS}): {exc}') from exc
    t_solve = time.perf_counter()-t0
    if json.dumps(doc.data, sort_keys=True, separators=(',', ':'), allow_nan=False) != calculation_json:
        raise ValueError('electric calculation inputs changed during the solve')
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
    fixed = kwargs['dirichlet']
    add('electric_dirichlet_node_ids', np.array(list(fixed), dtype=int), '1', 'electric_dirichlet_nodes')
    add('dirichlet_potential_v', list(fixed.values()), 'V', 'electric_dirichlet_nodes')
    free = np.setdiff1d(np.arange(mesh.num_nodes), list(fixed))
    reaction = np.asarray(electric.reaction)
    # current leaving through each fixed boundary, A/m of depth; a node that two boundaries fix
    # (a corner) counts for the first boundary listed in the document
    terminal = {tag: float(sum(reaction[n] for n, by in fixed_by.items() if by == tag))
                for tag in p['dirichlet_potential_v']}
    diagnostics = dict(
        current_balance_a_per_m=float(np.sum(reaction-np.asarray(electric.prescribed_outward_load))),
        electric_free_residual_a_per_m=float(np.max(abs(np.asarray(electric.residual)[free]), initial=0.)),
        supplied_power_w_per_m=electric.supplied_power_per_length,
        joule_power_w_per_m=electric.joule_power_per_length,
        electric_power_defect_w_per_m=electric.supplied_power_per_length-electric.joule_power_per_length,
        terminal_reaction_current_a_per_m=terminal,
        mesh_min_angle_deg=float(tri.min_angle()))
    metadata = dict(name=doc['name'], physics_name=name, physics_type=PHYSICS, status='converged',
        result_format=RESULT_FORMAT, field_layout=FIELD_LAYOUT, mesh_length_unit='m',
        input_units=copy.deepcopy(doc['units']), field_units=field_units, field_locations=locations,
        field_shapes={k: list(v.shape) for k, v in arrays.items()}, region_names=list(mesh.region_names),
        region_materials=dict(region_materials), region_conductivity_s_m=kwargs['conductivity'],
        diagnostics=diagnostics, iterations=[], timings_s=dict(mesh=t_mesh, solve=t_solve),
        software_versions=dict(simcase=__version__, galerkin=galerkin.__version__, numpy=np.__version__,
                               scipy=scipy.__version__))
    covered = covered_shapes(doc, mesh)
    log = [region_summary(doc),
           f'mesh: {mesh.num_nodes} nodes, {len(mesh.triangles)} triangles, regions {mesh.region_names}',
           *([f'shapes fully covered by later shapes (no triangles): {covered}'] if covered else []),
           f'potential V: {float(np.min(electric.potential)):.12g} to {float(np.max(electric.potential)):.12g}',
           f'Joule power {electric.joule_power_per_length:.12g} W/m of depth']
    if verbose:
        print('\n'.join(log))
    result = RegionElectricRunResult(doc, arrays, metadata, log)
    result.region_materials = region_materials
    return result

