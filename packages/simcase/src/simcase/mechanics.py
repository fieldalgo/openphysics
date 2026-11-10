# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict headless adapters for the existing 2D elasticity and thermoelastic solvers.

A document whose geometry declares material regions (flat ``background``/``shapes`` or a
version 1 region component) takes the region path of mechanics_regions.py; the rest of this
module is the rectangle contract below.

One homogeneous isotropic rectangle, plane stress or plane strain, side-constant prescribed
displacement components and global Cartesian side tractions, an optional constant body force.
``mechanics.elasticity2d`` is the isothermal solve; ``mechanics.thermoelastic2d`` first solves
steady heat with side-constant boundary data on the same mesh, freezes the nodal temperature
and solves the prescribed-temperature mechanical stage with TOTAL physical side tractions. The
runners build the mesh once in metres and call ``galerkin`` with no new discretization.

Both kinds read ``"openphysics": "0.3"`` (units batch C7; phase-2 spec sections 4.6 and 4.7):
values carry their units, keys are registry names, and a format 0.2 document is refused by
name. galerkin still receives today's keywords and values (``young_modulus``,
``reference_temperature_k``, ``thermal_expansion_per_k``; the thermal stage the outward flux
``0.0 - inward_heat_flux``, hazard H1; an absent body force or heat source as today's zeros,
H8). Results save their arrays under registry names with the summary of section 5.3.3: numeric
balances under ``balance``, every coded diagnostic under ``diagnostics``.
"""
import copy
import time

import numpy as np

from .schema import DocumentError
from .steady_boundary_contract import SIDES, boundary_kwargs, natural_conditions_03, rect_geometry_03, rectangle_03
from .thermal import _OwnedOutput, _authored, model_bytes_03, log_lines_03
from . import results_common, views
from .registry import PhysicsKind, register

ELASTIC = 'mechanics.elasticity2d'
THERMOELASTIC = 'mechanics.thermoelastic2d'
TYPES = {ELASTIC, THERMOELASTIC}
FIELD_LAYOUTS = {ELASTIC: 'mechanics2d-p1-v2', THERMOELASTIC: 'thermoelastic2d-p1-v2'}
FIELD_LAYOUT = FIELD_LAYOUTS[ELASTIC]
RESULT_FORMAT = ELASTIC+'-result-v2'
MAX_TRIANGLES = 200_000
PLANES = ('stress', 'strain')
COMPONENTS = ('x', 'y')
_FORMAT_02 = ('format 0.2 mechanics documents are not read: units now travel with each value ("200 GPa", "0 mm", '
              '"1 MPa"), the geometry declares its length_unit and the keys are registry names (youngs_modulus, '
              'prescribed_displacement, traction, stress_free_temperature). Write "openphysics": "0.3" '
              '(docs/packages/simcase/mechanics2d.md)')
#: the summary's sign sentence of a gauge pressure (region documents; section 5.3.3 of the batch)
GAUGE_PRESSURE_SIGN = 'traction = \u2212gauge_pressure \u00b7 n, n the outward normal; positive pushes into the body'

_STRAIN = ['strain_xx', 'strain_yy', 'engineering_shear_strain_xy']
#: saved array -> (registry quantity, or None for a structural array; location; components)
FIELDS = {
    'node_coordinates': ('node_coordinates', 'nodes', ['x', 'y']),
    'triangles': (None, 'triangle_connectivity', None),
    'triangle_regions': (None, 'triangles', None),
    'temperature': ('temperature', 'nodes', None),
    'heat_flux': ('heat_flux', 'triangle_centroids', ['x', 'y']),
    'generated_heat_rate_per_depth': ('generated_heat_rate_per_depth', 'nodes', None),
    'reaction_heat_rate_per_depth': ('reaction_heat_rate_per_depth', 'nodes', None),
    'residual_heat_rate_per_depth': ('residual_heat_rate_per_depth', 'nodes', None),
    'outward_prescribed_heat_rate_per_depth': ('outward_prescribed_heat_rate_per_depth', 'nodes', None),
    'ambient_convective_heat_rate_per_depth': ('ambient_convective_heat_rate_per_depth', 'nodes', None),
    'outward_convective_heat_rate_per_depth': ('outward_convective_heat_rate_per_depth', 'nodes', None),
    'applied_heat_rate_per_depth': ('applied_heat_rate_per_depth', 'nodes', None),
    'thermal_prescribed_node_ids': (None, 'thermal_prescribed_nodes', None),
    'prescribed_temperature': ('prescribed_temperature', 'thermal_prescribed_nodes', None),
    'displacement': ('displacement', 'nodes', ['x', 'y']),
    'strain': ('strain', 'triangle_centroids', _STRAIN),
    'thermal_strain': ('thermal_strain', 'triangle_centroids',
                       ['thermal_strain_xx', 'thermal_strain_yy', 'engineering_shear_thermal_strain_xy']),
    'elastic_strain': ('elastic_strain', 'triangle_centroids',
                       ['elastic_strain_xx', 'elastic_strain_yy', 'engineering_shear_elastic_strain_xy']),
    'stress': ('stress', 'triangle_centroids', ['stress_xx', 'stress_yy', 'stress_xy']),
    'stress_zz': ('stress_zz', 'triangle_centroids', None),
    'strain_zz': ('strain_zz', 'triangle_centroids', None),
    'applied_force_per_depth': ('applied_force_per_depth', 'nodes', ['x', 'y']),
    'thermal_equivalent_force_per_depth': ('thermal_equivalent_force_per_depth', 'nodes', ['x', 'y']),
    'applied_body_force_per_depth': ('applied_body_force_per_depth', 'nodes', ['x', 'y']),
    'applied_traction_force_per_depth': ('applied_traction_force_per_depth', 'nodes', ['x', 'y']),
    'reaction_force_per_depth': ('reaction_force_per_depth', 'nodes', ['x', 'y']),
    'residual_force_per_depth': ('residual_force_per_depth', 'nodes', ['x', 'y']),
    'prescribed_node_ids': (None, 'prescribed_dofs', None),
    'prescribed_components': (None, 'prescribed_dofs', None),
    'prescribed_displacement': ('prescribed_displacement', 'prescribed_dofs', None),
}
#: galerkin's heat result attribute of each heat-stage array
HEAT_ARRAYS = (('temperature', 'temperature'), ('heat_flux', 'heat_flux'),
               ('generated_heat_rate_per_depth', 'load'), ('reaction_heat_rate_per_depth', 'reaction'),
               ('residual_heat_rate_per_depth', 'residual'),
               ('outward_prescribed_heat_rate_per_depth', 'prescribed_outward_load'),
               ('ambient_convective_heat_rate_per_depth', 'ambient_load'),
               ('outward_convective_heat_rate_per_depth', 'convective_outward'),
               ('applied_heat_rate_per_depth', 'system_rhs'))
#: galerkin's result attribute of each mechanical array, per kind, in the saved order
ELASTIC_ARRAYS = (('displacement', 'displacement'), ('strain', 'strain'), ('stress', 'stress'),
                  ('applied_force_per_depth', 'load'), ('reaction_force_per_depth', 'reaction'),
                  ('residual_force_per_depth', 'residual'))
THERMOELASTIC_ARRAYS = (('displacement', 'displacement'), ('strain', 'total_strain'),
                        ('thermal_strain', 'thermal_strain'), ('elastic_strain', 'elastic_strain'),
                        ('stress', 'stress'), ('stress_zz', 'sigma_zz'), ('strain_zz', 'epsilon_zz'),
                        ('applied_force_per_depth', 'load_external'),
                        ('thermal_equivalent_force_per_depth', 'load_thermal'),
                        ('applied_body_force_per_depth', 'load_body'),
                        ('applied_traction_force_per_depth', 'load_traction'),
                        ('reaction_force_per_depth', 'reaction'), ('residual_force_per_depth', 'residual'))
#: the thermal stage's physics keys; an elasticity document refuses each by name (K4)
HEAT_KEYS = ('stress_free_temperature', 'linear_expansion_coefficient', 'thermal_conductivity',
             'prescribed_temperature', 'inward_heat_flux', 'convection', 'heat_source_density')


def is_mechanics(data):
    return isinstance(data, dict) and isinstance(data.get('physics'), dict) and any(
        isinstance(p, dict) and p.get('type') in TYPES for p in data['physics'].values())


def _refuse(message, path=None, code='E-CONTRACT'):
    """A coded refusal. An E-CONTRACT message names its own path; any other code does not repeat it."""
    if code != 'E-CONTRACT' and path and message.startswith(path + ': '):
        message = message[len(path) + 2:]
    raise DocumentError(message, path=path, code=code)


# -- slots (format 0.3) ---------------------------------------------------------------------------

_OUTWARD_INPUT = ('inputs are inward_: write inward_heat_flux (positive into the body, so an outward value is '
                  'written negated, such as "-2 W/m^2")')
_NO_THERMAL_STAGE = 'a mechanics.elasticity2d document has no thermal stage; use mechanics.thermoelastic2d'


def mechanics_slots():
    """The physics slots of the two kinds (``simcase.slots``), data only."""
    out = []
    for kind in sorted(TYPES):
        p = 'physics.*{' + kind + '}'

        def q(key, quantity, forms=('QS', 'AV'), slot_kind='quantity', **extra):
            return {'pattern': f'{p}.{key}', 'kind': slot_kind, 'quantity': quantity, 'forms': list(forms), **extra}

        def obj(key, **extra):
            return {'pattern': f'{p}.{key}', 'kind': 'structural', 'forms': ['OBJECT'], **extra}

        def refused(key, message, code='E-CONTRACT'):
            return {'pattern': f'{p}.{key}', 'kind': 'refused', 'code': code, 'message': message}

        out += [{'pattern': f'{p}.type', 'kind': 'enum', 'values': [kind], 'required': True},
                {'pattern': f'{p}.plane', 'kind': 'enum', 'values': list(PLANES), 'required': True},
                # a rectangle gives the material on the physics entry; regions take it from materials.<m>
                q('youngs_modulus', 'youngs_modulus', slot_kind='material_property'),
                q('poisson_ratio', 'poisson_ratio', ('BD', 'AV'), slot_kind='material_property'),
                obj('prescribed_displacement', required=True),
                q('prescribed_displacement.*', 'prescribed_displacement', ('CO',), components=list(COMPONENTS)),
                obj('traction'), q('traction.*', 'traction', ('SL', 'TA')),
                obj('gauge_pressure'), q('gauge_pressure.*', 'gauge_pressure'),
                q('body_force_density', 'body_force_density', ('SL', 'TA'), default=None,
                  default_reason='absent: no body force (no value is assumed)'),
                refused('absolute_pressure', 'an absolute pressure is not a load; give the gauge_pressure (the '
                        'pressure above the surroundings)', 'E-ABSOLUTE-AS-LOAD'),
                refused('force', 'point loads are not supported; give a traction on a boundary'),
                refused('force_per_depth', 'point loads are not supported; give a traction on a boundary'),
                refused('gravitational_acceleration', 'gravity needs mass_density, which this release does not '
                        'read; give the weight as body_force_density (such as ["0 N/m^3", "-77000 N/m^3"])')]
        if kind == THERMOELASTIC:
            out += [q('stress_free_temperature', 'stress_free_temperature', required=True),
                    q('linear_expansion_coefficient', 'linear_expansion_coefficient', slot_kind='material_property'),
                    q('thermal_conductivity', 'thermal_conductivity', slot_kind='material_property'),
                    # a constant, or on region documents {region name: value}
                    q('heat_source_density', 'heat_source_density', ('QS', 'AV', 'OBJECT'), default=None,
                      default_reason='absent: no volumetric heat source (no value is assumed)'),
                    q('heat_source_density.*', 'heat_source_density'),
                    obj('prescribed_temperature'), q('prescribed_temperature.*', 'prescribed_temperature'),
                    obj('inward_heat_flux'), q('inward_heat_flux.*', 'inward_heat_flux'),
                    obj('convection'), obj('convection.*'),
                    q('convection.*.heat_transfer_coefficient', 'heat_transfer_coefficient', required=True),
                    q('convection.*.ambient_temperature', 'ambient_temperature', required=True),
                    refused('outward_heat_flux', _OUTWARD_INPUT, 'E-KEY-UNKNOWN'),
                    refused('mean_linear_expansion_coefficient', 'mean_linear_expansion_coefficient is not read in '
                            'this release; give linear_expansion_coefficient'),
                    refused('volumetric_expansion_coefficient', 'volumetric_expansion_coefficient is not read in '
                            'this release; give linear_expansion_coefficient')]
        else:
            out += [refused(key, _NO_THERMAL_STAGE) for key in HEAT_KEYS]
    reads = {ELASTIC: ['youngs_modulus', 'poisson_ratio'],
             THERMOELASTIC: ['youngs_modulus', 'poisson_ratio', 'linear_expansion_coefficient', 'thermal_conductivity']}
    results = {'save_fields': True, 'plots': False}
    out += [{'pattern': 'materials.*', 'kind': 'override', 'library': 'none', 'reads': reads},
            {'pattern': 'name', 'kind': 'override', 'default': 'untitled',
             'default_reason': 'structural default: the document has no name'},
            {'pattern': 'results', 'kind': 'override', 'default': results,
             'default_reason': 'structural default of mechanics documents'},
            {'pattern': 'results.save_fields', 'kind': 'override', 'default': True,
             'default_reason': 'structural default of mechanics documents'},
            {'pattern': 'results.plots', 'kind': 'override', 'default': False,
             'default_reason': 'structural default of mechanics documents (headless)'},
            {'pattern': 'study', 'kind': 'override', 'default': {'type': 'single'},
             'default_reason': 'structural default: one static solve'}]
    return tuple(out)


# -- validation (format 0.3) ----------------------------------------------------------------------

def rigid_modes_fixed(fixed):
    """Whether side-constant constraints hold all three planar rigid-body motions.

    ``fixed`` holds (side, component) keys. A rigid motion is u = (a - t*y, b + t*x).
    Fixing x on left or right (y varies along the side) or y on bottom or top
    kills the rotation t; so does fixing x on both bottom and top, or y on both
    left and right. Fixing only x on one horizontal side and y on one vertical
    side leaves a hinge about their corner, and is refused.
    """
    x_sides = {side for side, c in fixed if c == 'x'}
    y_sides = {side for side, c in fixed if c == 'y'}
    if not x_sides or not y_sides:
        return False
    return bool(x_sides & {'left', 'right'} or y_sides & {'bottom', 'top'}
                or {'bottom', 'top'} <= x_sides or {'left', 'right'} <= y_sides)


def entry_03(doc):
    """``(name, SI entry, path, kind)`` of the one physics entry."""
    doc.sole_physics()
    name, p = next(iter(doc.si['physics'].items()))
    if not isinstance(name, str) or not name.isidentifier():
        _refuse('physics: name must be an identifier', f'physics.{name}')
    return name, p, f'physics.{name}', p['type']


def vector_03(value, path, key):
    """A [x, y] vector (a traction or the body force): exactly two entries."""
    if len(value) != 2:
        _refuse(f'{path}: {key} is a global [x, y] vector of two entries' + (
            '; for a normal load on a region boundary use gauge_pressure' if key == 'traction' else ''), path,
            'E-VALUE-FORM')
    return [float(v) for v in value]


def displacement_components_03(p, path):
    """Each prescribed_displacement entry fixes x and/or y (the reader refused other components)."""
    for tag, components in p['prescribed_displacement'].items():
        if not components:
            _refuse(f'{path}.prescribed_displacement.{tag}: expected x and/or y',
                    f'{path}.prescribed_displacement.{tag}', 'E-KEY-MISSING')


def default_traction_free_03(doc, name, p, sides):
    """``I-DEFAULT-BOUNDARY`` for each exterior side that no displacement, traction or gauge
    pressure names: it is traction free."""
    from physmat.units import Diagnostic
    named = set(p['prescribed_displacement']) | set(p.get('traction', {})) | set(p.get('gauge_pressure', {}))
    for side in sides:
        if side not in named:
            where = f'physics.{name}.traction.{side}'
            doc.diagnostics.append(Diagnostic('I-DEFAULT-BOUNDARY', where, f'side {side!r} has no condition: it is '
                                              'traction free (traction ["0 Pa", "0 Pa"])'))


def single_study_03(doc, kind):
    if doc.si['study'] != {'type': 'single'}:
        _refuse(f'study: {kind} supports only {{"type": "single"}}', 'study.type')
    if doc.si['results'].get('plots'):
        _refuse(f'results.plots: {kind} is headless; plots=true is not supported', 'results.plots')


def validate_rectangle_03(doc):
    """The two kinds on a rectangle (flat, or a homogeneous version 1 component, D-1): the checks
    of today's contract on SI values."""
    name, p, path, kind = entry_03(doc)
    thermal = kind == THERMOELASTIC
    required = ['youngs_modulus', 'poisson_ratio']
    if thermal:
        required += ['linear_expansion_coefficient', 'thermal_conductivity', 'prescribed_temperature']
    homogeneous = ('youngs_modulus, poisson_ratio, linear_expansion_coefficient and thermal_conductivity are '
                   'homogeneous' if thermal else 'youngs_modulus and poisson_ratio are homogeneous')
    rectangle_03(doc, kind, tuple(required), noun='mechanics', homogeneous=homogeneous)
    nx, ny = doc.si['mesh']['subdivision_count']
    if 2*nx*ny > MAX_TRIANGLES:
        _refuse(f'mesh.subdivision_count: at most {MAX_TRIANGLES} triangles supported', 'mesh.subdivision_count',
                'E-DOMAIN')
    single_study_03(doc, kind)
    if p.get('gauge_pressure') is not None:
        _refuse(f'{path}.gauge_pressure: a rectangle takes no gauge pressure; give a traction, or use a region '
                'document (whose boundaries take gauge_pressure)', f'{path}.gauge_pressure')
    if not p['youngs_modulus'] > 0:
        _refuse('youngs_modulus: expected a positive modulus', f'{path}.youngs_modulus', 'E-DOMAIN')
    body = p.get('body_force_density')
    if body is not None:
        vector_03(body, f'{path}.body_force_density', 'body_force_density')
    displacement = p['prescribed_displacement']
    extra = sorted(set(displacement) - set(SIDES))
    if extra:
        _refuse(f'{path}.prescribed_displacement.{extra[0]}: a rectangle takes the sides {list(SIDES)}',
                f'{path}.prescribed_displacement.{extra[0]}', 'E-SELECTION-UNKNOWN')
    displacement_components_03(p, path)
    fixed = {(side, c): v for side, components in displacement.items() for c, v in components.items()}
    for a in ('left', 'right'):
        for b in ('bottom', 'top'):
            for c in COMPONENTS:
                if (a, c) in fixed and (b, c) in fixed and fixed[a, c] != fixed[b, c]:
                    _refuse(f'{path}.prescribed_displacement: conflicting {c} displacement at the {a}/{b} corner',
                            f'{path}.prescribed_displacement.{b}.{c}')
    if not rigid_modes_fixed(fixed):
        _refuse(f'{path}.prescribed_displacement: constraints leave a rigid-body motion free; fix x and y, and '
                'block rotation (x on left/right, y on bottom/top, x on both bottom and top, or y on both left and '
                'right)', f'{path}.prescribed_displacement')
    traction = p.get('traction', {})
    extra = sorted(set(traction) - set(SIDES))
    if extra:
        _refuse(f'{path}.traction.{extra[0]}: a rectangle takes the sides {list(SIDES)}',
                f'{path}.traction.{extra[0]}', 'E-SELECTION-UNKNOWN')
    for side, vector in traction.items():
        t = vector_03(vector, f'{path}.traction.{side}', 'traction')
        for i, c in enumerate(COMPONENTS):
            if (side, c) in fixed and t[i] != 0:
                _refuse(f'{path}.traction.{side}: nonzero {c} traction on a side whose {c} displacement is '
                        'prescribed', f'{path}.traction.{side}')
    default_traction_free_03(doc, name, p, SIDES)
    if not thermal:
        return
    if not p['thermal_conductivity'] > 0:
        _refuse('thermal_conductivity: expected a positive conductivity', f'{path}.thermal_conductivity', 'E-DOMAIN')
    temperatures = p['prescribed_temperature']
    extra = sorted(set(temperatures) - set(SIDES))
    if extra:
        _refuse(f'{path}.prescribed_temperature.{extra[0]}: a rectangle takes the sides {list(SIDES)}',
                f'{path}.prescribed_temperature.{extra[0]}', 'E-SELECTION-UNKNOWN')
    for a in ('left', 'right'):
        for b in ('bottom', 'top'):
            if a in temperatures and b in temperatures and temperatures[a] != temperatures[b]:
                _refuse(f'{path}.prescribed_temperature: conflicting corner temperatures on {a}/{b}',
                        f'{path}.prescribed_temperature.{b}')
    _flux, convection = natural_conditions_03(p, path, temperatures)
    if not temperatures and not any(h > 0 for h, _ in convection.values()):
        _refuse(f'{path}: requires a prescribed-temperature or positive-convection anchor; pure Neumann is '
                'unsupported', f'{path}.prescribed_temperature', 'E-KEY-MISSING')
    from .thermal_regions import default_boundaries_03
    default_boundaries_03(doc, name, p, SIDES)


def validate_mechanics(doc):
    """Format 0.3 rectangles and regions. A format 0.2 document is refused by name."""
    if doc.si is None:
        raise DocumentError(_FORMAT_02, path='openphysics', code='E-FORMAT')
    from .mechanics_regions import is_region_mechanics, validate_region_mechanics
    if is_region_mechanics(doc.data):
        validate_region_mechanics(doc)
    else:
        validate_rectangle_03(doc)


# -- summary text ---------------------------------------------------------------------------------

def boundary_text_03(doc, where, p):
    """The boundary data of a mechanics entry, as written."""
    displacement = {tag: {c: _authored(doc, f'{where}.prescribed_displacement.{tag}.{c}') for c in components}
                    for tag, components in p['prescribed_displacement'].items()}
    traction = {tag: _authored(doc, f'{where}.traction.{tag}') for tag in p.get('traction', {})}
    pressure = {tag: _authored(doc, f'{where}.gauge_pressure.{tag}') for tag in p.get('gauge_pressure', {})}
    out = f'  prescribed_displacement {displacement}'
    if traction:
        out += f'; traction {traction}'
    if pressure:
        out += f'; gauge_pressure {pressure}'
    return out + '; other boundaries traction free'


def heat_text_03(doc, where, p):
    temperatures = {tag: _authored(doc, f'{where}.prescribed_temperature.{tag}') for tag in p.get('prescribed_temperature', {})}
    flux = {tag: _authored(doc, f'{where}.inward_heat_flux.{tag}') for tag in p.get('inward_heat_flux', {})}
    convection = {tag: {k: _authored(doc, f'{where}.convection.{tag}.{k}') for k in c}
                  for tag, c in p.get('convection', {}).items()}
    source = p.get('heat_source_density')
    if isinstance(source, dict):
        source_text = str({r: _authored(doc, f'{where}.heat_source_density.{r}') for r in source})
    else:
        source_text = 'none' if source is None else _authored(doc, f'{where}.heat_source_density')
    return (f'  thermal stage: stress_free_temperature {_authored(doc, where + ".stress_free_temperature")}; '
            f'prescribed_temperature {temperatures}' + (f'; inward_heat_flux {flux}' if flux else '')
            + (f'; convection {convection}' if convection else '') + f'; heat_source_density {source_text}; '
            'other boundaries insulated')


def rectangle_summary_03(doc):
    name, p, where, kind = entry_03(doc)
    thermal = kind == THERMOELASTIC
    g = rect_geometry_03(doc)[1]
    dom = ', '.join(f'{k} {g["domain"][k]}' for k in ('xmin', 'xmax', 'ymin', 'ymax'))
    out = [f'{doc.si["name"]} (openphysics 0.3)',
           f'  physics {name}: {kind}, headless single static rectangle, plane {p["plane"]}'
           + (', steady heat then prescribed-temperature mechanics' if thermal else ''),
           f'  domain {dom} ({g["length_unit"]}); subdivision_count {doc.si["mesh"]["subdivision_count"]}']
    material = (f'  youngs_modulus {_authored(doc, where + ".youngs_modulus")}; poisson_ratio '
                f'{_authored(doc, where + ".poisson_ratio")}')
    if thermal:
        material += (f'; linear_expansion_coefficient {_authored(doc, where + ".linear_expansion_coefficient")}; '
                     f'thermal_conductivity {_authored(doc, where + ".thermal_conductivity")}')
    out.append(material)
    body = p.get('body_force_density')
    out.append(boundary_text_03(doc, where, p) + ('' if body is None else
                                                  f'; body_force_density {_authored(doc, where + ".body_force_density")}'))
    if thermal:
        out.append(heat_text_03(doc, where, p))
    out.append(f'  result: {kind}-result-v2; layout: {FIELD_LAYOUTS[kind]}')
    out.append('  output: SI (displacement m, strain 1, stress Pa; nodal forces N/m of depth'
               + ('; temperature K, heat rates W/m of depth)' if thermal else ')'))
    return '\n'.join(out)


def document_summary(doc):
    from .mechanics_regions import is_region_mechanics, region_mechanics_summary
    doc.validate()
    if is_region_mechanics(doc.data):
        return region_mechanics_summary(doc)
    return rectangle_summary_03(doc)


# -- solver inputs --------------------------------------------------------------------------------

def _fixed_dofs(mesh, displacement):
    """{(node, component): m} sorted by (node, component); corners agree by validation."""
    fixed = {}
    for side, components in displacement.items():
        for component, value in components.items():
            for node in mesh.boundary[side]:
                fixed[int(node), COMPONENTS.index(component)] = float(value)
    return dict(sorted(fixed.items()))


def _norm(a):
    return float(np.max(abs(np.asarray(a)), initial=0.))


def heat_view_03(doc):
    """The steady heat inputs (``views.HeatInputs``) of a validated thermoelastic rectangle: SI
    values in document order; ``inward_heat_flux`` as the outward flux ``0.0 - value`` (H1), an
    absent source as 0.0 (H8)."""
    name, p = next(iter(doc.si['physics'].items()))
    temperatures = {tag: float(v) for tag, v in p['prescribed_temperature'].items()}
    flux, convection = natural_conditions_03(p, f'physics.{name}', temperatures)
    source = p.get('heat_source_density')
    return views.HeatInputs(conductivity=float(p['thermal_conductivity']),
                            heat_source=0.0 if source is None else float(source),
                            dirichlet=temperatures, outward_flux=flux, convection=convection)


#: the heat inputs an elasticity rectangle checks its mesh with (no heat is solved)
_MESH_CHECK = views.HeatInputs(conductivity=1., heat_source=0.0, dirichlet={'left': 0.}, outward_flux={},
                               convection={})


def heat_inputs(doc, mesh):
    """The ``solve_steady_heat`` keyword arguments of a thermoelastic document on ``mesh``."""
    return boundary_kwargs(views.rectangle_mesh(doc, 'difference'), heat_view_03(doc), mesh)


def solver_inputs(doc, mesh):
    """The mechanical keyword arguments of a validated document on ``mesh``.

    For ``mechanics.elasticity2d`` these are the ``solve_elasticity`` arguments; a
    thermoelastic document adds ``reference_temperature_k`` and ``thermal_expansion_per_k``
    for ``solve_thermoelasticity`` (galerkin's keywords; the document's
    ``stress_free_temperature`` and ``linear_expansion_coefficient``), whose temperature
    snapshot comes from the heat solve. Prescribed DOFs are sorted by (node, component); the
    body force is a (2,) tuple, (0.0, 0.0) when the document gives none (H8); each traction
    a global Cartesian [tx, ty] list in Pa in document order (H6). ``mesh`` must be the
    document's rectangle in metres (``build_rectangle``); the shared rectangle mesh checks run
    on it first. The values come from the document's internal SI view
    (``simcase.views.rectangle_mechanics``).
    """
    doc.sole_physics()      # one physics entry, refused by name before any mesh check
    boundary_kwargs(views.rectangle_mesh(doc, 'difference'), _MESH_CHECK, mesh)
    m = views.rectangle_mechanics(doc)
    traction = {side: [float(v) for v in vector] for side, vector in m.traction.items()}
    inputs = dict(young_modulus=float(m.young_modulus), poisson_ratio=float(m.poisson_ratio),
                  plane=m.plane, dirichlet=_fixed_dofs(mesh, m.displacement),
                  body_force=tuple(float(v) for v in m.body_force),
                  traction=traction or None)
    if m.thermoelastic:
        inputs.update(reference_temperature_k=float(m.reference_temperature),
                      thermal_expansion_per_k=float(m.thermal_expansion))
    return inputs


def build_rectangle(doc):
    """The document's structured rectangle mesh in metres, nodes offset to the domain origin; the
    side lengths subtract the converted corners (views.LENGTH_FORMULAS)."""
    from galerkin import rectangle_mesh
    grid = views.rectangle_mesh(doc, 'corners')
    mesh = rectangle_mesh(*grid.lengths, *grid.subdivisions)
    mesh.nodes += grid.origin
    return mesh


# -- results --------------------------------------------------------------------------------------

def result_arrays(mesh, solved, fixed, *, thermal, regions=None, heat=None, heat_fixed=None):
    """The saved arrays, in today's order under the registry names (bytes unchanged)."""
    arrays = {'node_coordinates': np.asarray(mesh.nodes), 'triangles': np.asarray(mesh.triangles)}
    if regions is not None:
        arrays['triangle_regions'] = np.asarray(regions)
    if heat is not None:
        for key, attr in HEAT_ARRAYS:
            arrays[key] = np.asarray(getattr(heat, attr))
        arrays['thermal_prescribed_node_ids'] = np.array(list(heat_fixed), dtype=int)
        arrays['prescribed_temperature'] = np.asarray(list(heat_fixed.values()))
    for key, attr in (THERMOELASTIC_ARRAYS if thermal else ELASTIC_ARRAYS):
        arrays[key] = np.asarray(getattr(solved, attr))
    arrays['prescribed_node_ids'] = np.array([node for node, _ in fixed], dtype=int)
    arrays['prescribed_components'] = np.array([component for _, component in fixed], dtype=int)
    arrays['prescribed_displacement'] = np.asarray(list(fixed.values()))
    return arrays


def balance_03(arrays, solved, mesh, *, thermal, heat=None, heat_fixed=None):
    """The ``balance`` values of section 5.3.3 (SI, per metre of depth; a vector as a list)."""
    free = np.ones((mesh.num_nodes, 2), dtype=bool)
    free[arrays['prescribed_node_ids'], arrays['prescribed_components']] = False
    u, reaction, residual = arrays['displacement'], arrays['reaction_force_per_depth'], arrays['residual_force_per_depth']
    # the 0.2 load: the elastic load, or external plus thermal-equivalent (no + 0: -0.0 stays -0.0)
    load = (arrays['applied_force_per_depth'] + arrays['thermal_equivalent_force_per_depth'] if thermal
            else arrays['applied_force_per_depth'])
    out = {'applied_force_per_depth': [float(v) for v in arrays['applied_force_per_depth'].sum(axis=0)]}
    if thermal:
        out['thermal_equivalent_force_per_depth'] = [float(v) for v in
                                                     arrays['thermal_equivalent_force_per_depth'].sum(axis=0)]
    out['reaction_force_per_depth'] = [float(v) for v in reaction.sum(axis=0)]
    out['force_imbalance_per_depth'] = [float(v) for v in (load+reaction).sum(axis=0)]
    out['maximum_residual_force_per_depth'] = _norm(residual[free])
    energy = float(.5*np.sum(u*(load+residual)))
    if thermal:
        out['stiffness_energy_functional_per_depth'] = energy
        out['strain_energy_per_depth'] = float(solved.physical_elastic_energy)
    else:
        out['strain_energy_per_depth'] = energy
    out['maximum_displacement'] = float(np.max(np.hypot(u[:, 0], u[:, 1]), initial=0.))
    out['maximum_stress'] = _norm(arrays['stress'])
    if heat is not None:
        free_t = np.setdiff1d(np.arange(mesh.num_nodes), list(heat_fixed))
        source = float(heat.load.sum())
        outward = float(np.sum(-heat.reaction+heat.prescribed_outward_load+heat.convective_outward))
        out.update(generated_heat_rate_per_depth=source, outward_heat_rate_per_depth=outward,
                   heat_rate_imbalance_per_depth=outward-source,
                   maximum_residual_heat_rate_per_depth=_norm(heat.residual[free_t]),
                   minimum_temperature=float(heat.temperature.min()),
                   maximum_temperature=float(heat.temperature.max()))
    return out


def summary_03(doc, *, result_format, field_layout, arrays, balance, timings, mesh, depth, inputs=None,
               snapshot=None, extra=None, minimum_angle=None):
    """The section 5.3.3 summary: the common envelope, the field maps, the material and load
    echoes of a rectangle (``inputs``; region documents pass theirs in ``extra``), the temperature
    snapshot, ``balance`` (value objects; with a depth, each per-depth value is followed by its
    total)."""
    import galerkin
    import scipy
    from . import __version__
    name, p, _, kind = entry_03(doc)
    vo, ta = results_common.value_object, results_common.tagged_array
    fields = {key: {'quantity': FIELDS[key][0], 'location': FIELDS[key][1], 'shape': list(a.shape),
                    'components': FIELDS[key][2]} for key, a in arrays.items()}
    maps = results_common.field_maps(fields)
    del maps['field_time_axes']                      # a static result has no time axis
    out = {'name': doc.si['name'], 'physics_name': name, 'physics_type': kind, 'status': 'solved',
           **results_common.envelope(doc, result_format=result_format, field_layout=field_layout,
                                     timing_=results_common.timing(timings['mesh'], timings['solve'])),
           **maps, 'plane': p['plane']}
    if inputs is not None:
        out['youngs_modulus'] = vo(inputs['young_modulus'], 'youngs_modulus')
        out['poisson_ratio'] = inputs['poisson_ratio']
        if kind == THERMOELASTIC:
            out['linear_expansion_coefficient'] = vo(inputs['thermal_expansion_per_k'], 'linear_expansion_coefficient')
            out['thermal_conductivity'] = vo(p['thermal_conductivity'], 'thermal_conductivity')
    out.update(extra or {})
    if kind == THERMOELASTIC:
        out['stress_free_temperature'] = vo(p['stress_free_temperature'], 'stress_free_temperature')
    if p.get('body_force_density') is not None:
        out['body_force_density'] = ta(p['body_force_density'], 'body_force_density')
    if snapshot is not None:
        out['temperature_snapshot'] = dict(mesh_hash=snapshot.mesh_hash, temperature_hash=snapshot.temperature_hash,
                                           snapshot_hash=snapshot.snapshot_hash)
    mesh_block = {'nodes': int(mesh.num_nodes), 'triangles': int(len(mesh.triangles))}
    if minimum_angle is not None:
        mesh_block['minimum_triangle_angle'] = vo(minimum_angle, 'minimum_triangle_angle')
    values = {key: ta(value, key) if isinstance(value, list) else vo(value, key) for key, value in balance.items()}
    results_common.add_depth_totals(values, depth)
    out.update({'mesh': mesh_block, 'study': {'type': 'single'}, 'balance': values,
                'software_versions': dict(simcase=__version__, galerkin=galerkin.__version__, numpy=np.__version__,
                                          scipy=scipy.__version__)})
    results_common.dumps_summary(out)                # finite JSON only
    return out


class MechanicsRunResult:
    """Owned numeric evidence. Public field/summary access returns independent copies."""

    def __init__(self, doc, arrays, metadata, log):
        self.doc = doc.copy()
        self.doc.validate()
        self._document_json = self.doc.canonical_json(separators=(', ', ': '))
        self._arrays = {k: np.array(v, copy=True) for k, v in arrays.items()}
        for key, array in self._arrays.items():
            if array.dtype.kind not in 'iuf' or not np.isfinite(array).all():
                raise ValueError(f'{key}: expected finite real numeric array')
            array.setflags(write=False)
        results_common.dumps_summary(metadata)           # finite JSON only
        self._metadata = copy.deepcopy(metadata)
        self._log = tuple(log)

    @property
    def fields(self):
        return {k: a.copy() for k, a in self._arrays.items()}

    @property
    def result_format(self):
        return self._metadata['result_format']

    @property
    def field_layout(self):
        return self._metadata['field_layout']

    def summary(self):
        if self.doc.canonical_json(separators=(', ', ': ')) != self._document_json:
            raise ValueError('mechanics result document changed after the solve; run again')
        return copy.deepcopy(self._metadata)

    def save(self, outdir):
        summary = self.summary()
        encoded = results_common.dumps_summary(summary).encode('utf-8')
        owned = _OwnedOutput(outdir)
        try:
            owned.write('.incomplete', lambda f: f.write(b'incomplete mechanics result\n'))
            owned.write('model.json', lambda f: f.write(model_bytes_03(self.doc)))
            owned.write('log.txt', lambda f: f.write(('\n'.join(self._log)+'\n').encode('utf-8')))
            if self.doc.si['results']['save_fields']:
                arrays = dict(self._arrays, result_format=summary['result_format'],
                              field_layout=summary['field_layout'], metadata_json=results_common.metadata_json(summary))
                owned.write('fields.npz', lambda f: np.savez_compressed(f, **arrays))
            owned.write('summary.json', lambda f: f.write(encoded))
            owned.finish()
        except Exception:
            owned.cleanup()
            raise
        finally:
            owned.close()
        return owned.path


def solve_03(mesh, inputs, heat_args, thermal, label=None):
    """Solve the heat stage (thermoelastic) and the mechanical stage on ``mesh``; returns
    ``(solved, heat, snapshot)``. ``label`` prefixes a solver refusal with the physics entry
    (region documents)."""
    from galerkin.elasticity import solve_elasticity
    from galerkin.thermal import solve_steady_heat
    from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity
    heat = snapshot = None
    try:
        if thermal:
            heat = solve_steady_heat(mesh, **heat_args)
            snapshot = freeze_temperature(mesh, heat.temperature)
            solved = solve_thermoelasticity(mesh, snapshot, **inputs)
        else:
            solved = solve_elasticity(mesh, **inputs)
    except (ValueError, RuntimeError) as exc:
        if label is None:
            raise
        raise ValueError(f'{label}: {exc}') from exc
    return solved, heat, snapshot


def run_mechanics(doc, verbose=True, *, mesh_limits=None):
    from .mechanics_regions import is_region_mechanics, run_region_mechanics
    if is_region_mechanics(doc.data):
        return run_region_mechanics(doc, verbose=verbose, mesh_limits=mesh_limits)
    doc.validate()
    doc = doc.copy()
    doc.validate()
    name, p, _, kind = entry_03(doc)
    thermal = kind == THERMOELASTIC
    start = time.perf_counter()
    mesh = build_rectangle(doc)
    inputs = solver_inputs(doc, mesh)
    heat_args = heat_inputs(doc, mesh) if thermal else None
    mesh_time = time.perf_counter()-start
    start = time.perf_counter()
    solved, heat, snapshot = solve_03(mesh, inputs, heat_args, thermal)
    solve_time = time.perf_counter()-start
    fixed = inputs['dirichlet']
    arrays = result_arrays(mesh, solved, fixed, thermal=thermal, heat=heat,
                           heat_fixed=None if heat_args is None else heat_args['dirichlet'])
    balance = balance_03(arrays, solved, mesh, thermal=thermal, heat=heat,
                         heat_fixed=None if heat_args is None else heat_args['dirichlet'])
    metadata = summary_03(doc, result_format=kind+'-result-v2', field_layout=FIELD_LAYOUTS[kind], arrays=arrays,
                          balance=balance, timings={'mesh': mesh_time, 'solve': solve_time}, mesh=mesh,
                          depth=rect_geometry_03(doc)[2], inputs=inputs, snapshot=snapshot)
    printed = [doc.summary(), solved_line(mesh, balance, thermal)]
    if verbose:
        print('\n'.join(printed))
    return MechanicsRunResult(doc, arrays, metadata, log_lines_03(doc, printed))


def solved_line(mesh, balance, thermal):
    line = (f'Solved {mesh.num_nodes} nodes, {mesh.num_triangles} triangles; maximum_displacement '
            f'{balance["maximum_displacement"]:.12g} m, strain_energy_per_depth '
            f'{balance["strain_energy_per_depth"]:.12g} J/m (J per metre of depth)')
    if thermal:
        line += (f'\nTemperature {balance["minimum_temperature"]:.12g} K to {balance["maximum_temperature"]:.12g} K; '
                 f'outward_heat_rate_per_depth {balance["outward_heat_rate_per_depth"]:.12g} W/m')
    return line


def _defaults():
    from .thermal import defaults
    return defaults()


def _accepts_mesh_limits(data):
    """Region documents take mesh limits (simcase.mesh_limits); rectangle documents do not."""
    from .mechanics_regions import is_region_mechanics
    return is_region_mechanics(data)


register(PhysicsKind(
    name='mechanics', types=frozenset(TYPES), precedence=15,
    validate=validate_mechanics, run=run_mechanics, summary=document_summary,
    result_types=(MechanicsRunResult,), defaults=_defaults, fresh_output=True,
    stage_refusal='{stage} is an EM stage; use run(document) for mechanics physics',
    accepts_mesh_limits=_accepts_mesh_limits, slots=mechanics_slots()))
