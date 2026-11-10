# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""``electric.steady2d`` on named material regions.

A steady conduction document whose geometry has regions (flat ``background``/``shapes`` or a
version 1 block with features or a background material) uses the same geometry, mesh and
boundary names as region heat (:mod:`simcase.thermal_regions`): the conductivity of each region
is its material's ``electrical_conductivity``; ``prescribed_electric_potential`` and
``inward_current_density`` take the domain sides, the exterior tags the geometry declares
(``boundary_tags`` names, ``outer`` on a void border) and exterior boundary selections. An
interior selection (an interface between two regions) is refused for both, because
:func:`galerkin.electric.solve_steady_electric` fixes exterior nodes only. An unnamed exterior
boundary is electrically insulating (``I-DEFAULT-BOUNDARY`` on the domain sides). A rectangle
document keeps the rectangle path (:mod:`simcase.electric_joule`).

Format 0.3 (units batch C6): the mesh is made from the geometry hand-off of region heat
(``thermal_regions.handoff_03``), so the mesher receives the micrometre model it received for
format 0.2, and galerkin receives the outward current ``0.0 - inward_current_density`` (H1).
"""

import math
import time

import numpy as np

from . import views
from .schema import DocumentError
from .thermal_regions import (_refuse, boundary_names, build_region_mesh, component_03, covered_shapes, depth_03,
                              exterior_sides, handoff_03, has_region_geometry, mesh_controls_03, mesh_diagnostics_03,
                              region_geometry_03, region_materials_table_03, region_mesh_settings_03)

PHYSICS = 'electric.steady2d'
RESULT_FORMAT = 'electric.steady2d-regions-result-v2'
FIELD_LAYOUT = 'electric2d-p1-node-cell-regions-v2'
NONLINEAR_JOULE = 'joule.temperature2d'
#: the physics-entry keys of a region electric document
ELECTRIC_KEYS = ('prescribed_electric_potential', 'inward_current_density')


def is_region_electric(data):
    """A steady electric conduction document that declares region geometry."""
    return has_region_geometry(data, PHYSICS)


def region_joule_refusal(tree):
    """``(path, message)`` refusing a temperature-dependent Joule document with region geometry
    (it takes the rectangle path only; ``joule.steady2d`` on regions is
    :mod:`simcase.joule_regions`), or None. It reads the raw tree, so the reader refuses the
    form by name before it asks for the kind's keys (``PhysicsKind.refuse_03``)."""
    if not has_region_geometry(tree, NONLINEAR_JOULE):
        return None
    name = next(n for n, p in tree['physics'].items() if isinstance(p, dict) and p.get('type') == NONLINEAR_JOULE)
    path = f'physics.{name}.type'
    return path, (f'{path}: {NONLINEAR_JOULE}: region geometry (named material regions) is supported for {PHYSICS} '
                  'and joule.steady2d only; a temperature-dependent Joule document takes the rectangle form')


def refuse_region_joule(doc):
    """The same refusal on a read document."""
    refusal = region_joule_refusal(doc.data)
    if refusal is not None:
        path, message = refusal
        _refuse(message, path)


def region_entry_03(doc, label, refused):
    """``(name, SI entry, path)`` of the one physics entry of a region document; the material
    properties in ``refused`` are refused on it by name, and an axisymmetric component too."""
    doc.sole_physics()
    name, p = next(iter(doc.si['physics'].items()))
    if not isinstance(name, str) or not name.isidentifier():
        _refuse('physics: name must be an identifier', f'physics.{name}')
    path = f'physics.{name}'
    for key in refused:
        if key in p:
            _refuse(f'{path}.{key}: a region document takes {key} from materials.<m>', f'{path}.{key}')
    if component_03(doc)[1].get('dimension') == 'axisymmetric':
        _refuse(f'{p["type"]}: an axisymmetric component is not supported for {label} (galerkin.electric has no '
                'axisymmetric measure)', 'geometry.components')
    return name, p, path


def positive_conductivities_03(doc, used, keys):
    """``electrical_conductivity`` may be 0 in the registry; a conductor needs it positive."""
    materials = doc.si.get('materials') or {}
    for mname in used:
        for key in keys:
            if not materials[mname][key] > 0:
                _refuse(f'materials.{mname}.{key}: expected a positive conductivity', f'materials.{mname}.{key}',
                        'E-DOMAIN')


def boundary_data_03(p, path, names):
    """The names of the potential and current data, before meshing: sides, tags and exterior
    selections; an interface selection is refused by name; at least one potential; no current
    on a fixed boundary."""
    from .thermal_regions import SIDES
    tags, outside, inside = names
    allowed = set(SIDES) | tags | outside
    for label in ELECTRIC_KEYS:
        for key in p.get(label, {}):
            where = f'{path}.{label}.{key}'
            if key in inside:
                _refuse(f'{where}: selection {key!r} lies on an interface between two regions; electric data apply to '
                        'exterior boundaries only (galerkin.electric fixes exterior nodes only)', where)
            if key not in allowed:
                _refuse(f'{where}: no side, boundary tag or exterior selection of that name; expected one of '
                        f'{sorted(allowed)}', where, 'E-SELECTION-UNKNOWN')
    if not p.get('prescribed_electric_potential'):
        _refuse(f'{path}.prescribed_electric_potential: at least one boundary potential is required; gauge-only '
                'inputs are unsupported', f'{path}.prescribed_electric_potential')
    overlap = sorted(set(p['prescribed_electric_potential']) & set(p.get('inward_current_density', {})))
    if overlap:
        _refuse(f'{path}: a current condition overlaps a fixed potential on the same boundary ({overlap[0]})',
                f'{path}.inward_current_density.{overlap[0]}')


def validate_region_electric(doc):
    """electric.steady2d on regions, format 0.3."""
    from .electric_joule import default_electric_boundaries_03, single_study_03
    name, p, path = region_entry_03(doc, 'electric conduction', ('electrical_conductivity',))
    region_mesh_settings_03(doc)
    h = handoff_03(doc)
    region_geometry_03(doc, h, 'electric')
    mesh_controls_03(doc, h)
    used = region_materials_table_03(doc, h, ('electrical_conductivity',), 'steady electric conduction',
                                     'electric properties')
    positive_conductivities_03(doc, used, ('electrical_conductivity',))
    boundary_data_03(p, path, boundary_names(h))
    default_electric_boundaries_03(doc, name, p, exterior_sides(h)[1])
    single_study_03(doc, PHYSICS)


def summary_lines_03(doc, label, keys):
    """The summary text of a format 0.3 region electric or Joule document, up to its boundary data."""
    from .thermal import _authored
    from .thermal_regions import _plain
    h = handoff_03(doc)
    name, p = next(iter(doc.si['physics'].items()))
    where = f'physics.{name}'
    block = component_03(doc)[1]
    dom = ', '.join(f'{k} {_plain(block["domain"][k])}' for k in ('xmin', 'xmax', 'ymin', 'ymax'))
    out = [f'{doc.si["name"]} (openphysics 0.3)', f'  physics {name}: {label}',
           f'  domain {dom} ({block["length_unit"]}); element_size {_authored(doc, "mesh.element_size")}',
           f'  background: {h.background["material"]}']
    out += [f'  region {r["name"]}: {r["type"]}, {r["material"] if r["material"] is not None else "void (hole)"}'
            for r in h.regions()]
    for mname, spec in doc.si['materials'].items():
        props = ', '.join(f'{k} {_authored(doc, f"materials.{mname}.{k}")}' for k in spec if k != 'source')
        out.append(f'  material {mname}: {props}')
    for key in keys:
        table = p.get(key, {})
        if not table:
            continue
        if key == 'convection':
            shown = {tag: {k: _authored(doc, f'{where}.convection.{tag}.{k}') for k in c} for tag, c in table.items()}
        else:
            shown = {tag: _authored(doc, f'{where}.{key}.{tag}') for tag in table}
        out.append(f'  {key} {shown}')
    return out


def region_summary(doc):
    out = summary_lines_03(doc, f'{PHYSICS}, steady conduction, named material regions', ELECTRIC_KEYS)
    out += ['  other exterior boundaries electrically insulating',
            f'  result: {RESULT_FORMAT}; layout: {FIELD_LAYOUT}',
            '  output: SI (node_coordinates m, electric_potential V, electric_field V/m, current_density A/m^2, '
            'joule_power_density W/m^3, nodal currents A/m and powers W/m of depth, triangle_regions)']
    return '\n'.join(out)


def region_inputs(doc, mesh, region_materials, electric=None):
    """solve_steady_electric keyword arguments for a meshed region document (from its internal SI
    view, ``simcase.views.region_electric``), and the boundary name that fixes each fixed node."""
    name, _ = doc.sole_physics()
    path = f'physics.{name}'
    electric = views.region_electric(doc) if electric is None else electric
    conductivity = {r: float(electric.conductivity[m]) for r, m in region_materials.items()}
    for label, table, given in (('prescribed_electric_potential', mesh.boundary, electric.dirichlet),
                                ('inward_current_density', mesh.boundary_edges, electric.outward_current)):
        for tag in given:
            if tag not in table:
                raise DocumentError(f'{path}.{label}.{tag}: no mesh edge lies on {tag!r} (a side or boundary that '
                                    'borders a void feature only, or a selection without mesh edges)')

    def edge_set(edges):
        return {tuple(sorted(map(int, e))) for e in np.asarray(edges).reshape(-1, 2)}
    selected = getattr(mesh, 'selection_edges', None) or {}
    potentials = electric.dirichlet
    held = {tag: edge_set(mesh.boundary_edges[tag] if tag in mesh.boundary_edges else selected.get(tag, []))
            for tag in potentials}
    names = sorted(potentials)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if held[a] & held[b]:
                raise DocumentError(f'{path}.prescribed_electric_potential: {a!r} and {b!r} share mesh edges; give '
                                    'that boundary one entry')
    # a node two boundaries fix (where they meet) counts for the first name in name order, so the
    # attribution does not depend on the key order of the document
    fixed, fixed_by = {}, {}
    for tag in names:
        value = float(potentials[tag])
        for node in map(int, mesh.boundary[tag]):
            if node in fixed and fixed[node] != value:
                raise DocumentError(f'{path}.prescribed_electric_potential: {fixed_by[node]!r} and {tag!r} share node '
                                    f'{node} with different potentials')
            fixed[node] = value
            fixed_by.setdefault(node, tag)
    current = {tag: float(v) for tag, v in electric.outward_current.items()}
    edges = {tag: edge_set(mesh.boundary_edges[tag]) for tag in current}
    names = sorted(edges)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if edges[a] & edges[b]:
                raise DocumentError(f'{path}.inward_current_density: {a!r} and {b!r} share mesh edges; give that '
                                    'boundary one entry')
    for a, e in edges.items():
        # an edge whose two nodes are fixed, by one boundary or by two, takes no current
        both = sorted({fixed_by[u] for edge in e if edge[0] in fixed and edge[1] in fixed for u in edge})
        if both:
            raise DocumentError(f'{path}.inward_current_density.{a}: {a!r} has mesh edges whose nodes are fixed by '
                                f'{both}; a current condition does not apply on a fixed edge')
    _refuse_floating_parts(mesh, fixed, path)
    return (dict(conductivity=conductivity, dirichlet=dict(sorted(fixed.items())), outward_current=current),
            fixed_by)


def _refuse_floating_parts(mesh, fixed, path):
    """Every connected part of the conductor needs a fixed potential; a document cannot set the
    reference potential that a floating part would need."""
    t = np.asarray(mesh.triangles)
    parent = np.arange(len(mesh.nodes))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for a, b, c in t:
        for u, v in ((a, b), (b, c)):
            ru, rv = root(int(u)), root(int(v))
            if ru != rv:
                parent[ru] = rv
    anchored = {root(n) for n in fixed}
    floating = sorted({mesh.region_names[int(r)] for tri, r in zip(t, mesh.regions) if root(int(tri[0])) not in anchored})
    if floating:
        raise DocumentError(f'{path}.prescribed_electric_potential: a conductor part with regions {floating} touches '
                            'no fixed potential (it is surrounded by void); give one of its boundaries a potential')


def outward_terminal_currents(electric, fixed_by, potentials):
    """The current leaving the conductor through each fixed boundary, A per metre of depth:
    ``0.0 - (current the fixed potential injects)``; a node two boundaries fix counts for the
    first of them in name order."""
    reaction = np.asarray(electric.reaction)
    injected = {tag: float(sum(reaction[n] for n, by in fixed_by.items() if by == tag)) for tag in potentials}
    return {tag: 0.0 - value for tag, value in injected.items()}


def regions_block_03(doc, mesh, region_materials, keys):
    """``region_names`` and ``regions.<r>.{material, <property>...}`` (value objects) of a summary."""
    from .results_common import value_object
    materials = doc.si['materials']
    return {'region_names': list(mesh.region_names),
            'regions': {r: {'material': m, **{k: value_object(materials[m][k], k) for k in keys}}
                        for r, m in region_materials.items()}}


def run_region_electric(doc, verbose=True, *, mesh_limits=None):
    from galerkin.electric import solve_steady_electric
    from .electric_joule import (RegionElectricRunResult, electric_balance, result_arrays, summary_03)
    from .thermal import log_lines_03
    doc.validate()
    given, doc = doc, doc.copy()
    doc.validate()
    name, p = doc.sole_physics()
    t0 = time.perf_counter()
    h = handoff_03(doc)
    mesh, region_materials, tri = build_region_mesh(h, mesh_limits)
    # the mesher's findings reach the caller's document as coded diagnostics
    for target in (given, doc):
        mesh_diagnostics_03(target, component_03(doc)[0], h.notes)
    kwargs, fixed_by = region_inputs(doc, mesh, region_materials)
    t_mesh = time.perf_counter()-t0
    calculation_json = doc.canonical_json(separators=(',', ':'))
    t0 = time.perf_counter()
    try:
        electric = solve_steady_electric(mesh, **kwargs)
    except (ValueError, RuntimeError) as exc:
        raise ValueError(f'physics.{name} ({PHYSICS}): {exc}') from exc
    t_solve = time.perf_counter()-t0
    if doc.canonical_json(separators=(',', ':')) != calculation_json:
        raise ValueError('electric calculation inputs changed during the solve')
    fixed = kwargs['dirichlet']
    arrays = result_arrays(mesh, electric, fixed, regions=mesh.regions)
    balance = electric_balance(electric, fixed, mesh)
    balance['outward_current_per_depth'] = outward_terminal_currents(electric, fixed_by,
                                                                     doc.si['physics'][name]['prescribed_electric_potential'])
    metadata = summary_03(doc, result_format=RESULT_FORMAT, field_layout=FIELD_LAYOUT, arrays=arrays, balance=balance,
                          timings={'mesh': t_mesh, 'solve': t_solve}, mesh=mesh, depth=depth_03(doc),
                          extra=regions_block_03(doc, mesh, region_materials, ('electrical_conductivity',)),
                          minimum_angle=math.radians(float(tri.min_angle())))
    covered = covered_shapes(h, mesh)
    printed = [doc.summary(),
               f'mesh: {mesh.num_nodes} nodes, {len(mesh.triangles)} triangles, regions {mesh.region_names}',
               *([f'shapes fully covered by later shapes (no triangles): {covered}'] if covered else []),
               f'electric_potential: {float(np.min(electric.potential)):.12g} V to '
               f'{float(np.max(electric.potential)):.12g} V',
               f'joule_power_per_depth {electric.joule_power_per_length:.12g} W/m']
    if verbose:
        print('\n'.join(printed))
    result = RegionElectricRunResult(doc, arrays, metadata, log_lines_03(doc, printed))
    result.region_materials = region_materials
    return result
