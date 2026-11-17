# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit SI, isolated same-mesh steady heat then thermoelastic mechanics.

No persistence, unit conversion, source authentication, or thermodynamic coupling.
Import this submodule explicitly; existing component APIs remain unchanged.
Quantities are keyword-only registry names in SI units (the units convention of the
galerkin step); a str for a quantity raises TypeError. The manifest's keys are
registry names (schema ``galerkin-steady-thermoelasticity-v2``).
"""
from dataclasses import dataclass, field
from types import MappingProxyType
import json
import numpy as np

from .mesh import Mesh
from .core.checks import real_array, real_scalar, refuse_live
from .coupling import Field, OneWayChain, transfer
from ._thermal_mechanical_common import check_mesh_unchanged, dirichlet_supports, isolated_mesh, mesh_state
from .materials import is_per_region, region_property
from .thermal import solve_steady_heat_outward
from .thermoelasticity import freeze_temperature, solve_thermoelasticity
from ._public import ResultSurface, refuse_text

__all__ = ["WorkflowStageError", "SteadyThermoelasticResult", "solve_steady_thermoelasticity"]

#: the manifest schema; v2 (the galerkin step, L2 commit 8) writes registry names where v1 wrote
#: unit-suffixed keys (conductivity_w_mk, young_modulus_pa, ...) and drops the units= argument
SCHEMA = 'galerkin-steady-thermoelasticity-v2'
#: the canonical unit of each quantity the manifest's inputs name (node_coordinates: the mesh
#: its 'mesh' section hashes)
INPUT_UNITS = MappingProxyType({
    'node_coordinates': 'm', 'thermal_conductivity': 'W/(m K)', 'youngs_modulus': 'Pa', 'poisson_ratio': '1',
    'linear_expansion_coefficient': '1/K', 'stress_free_temperature': 'K', 'prescribed_temperature': 'K',
    'prescribed_displacement': 'm', 'heat_source_density': 'W/m^3', 'body_force_density': 'N/m^3'})


class WorkflowStageError(ValueError):
    """Failure of input, heat, transfer, mechanics, or manifest; cause retained."""
    def __init__(self, stage, message):
        self.stage = stage
        super().__init__(f"steady thermoelasticity [{stage}]: {message}")


def _stage_error(stage, exc):
    return WorkflowStageError(stage, str(exc))


def _material(mesh, value, name, **bounds):
    """Validated scalar float, or a {region name: float} dict (sorted keys)."""
    if is_per_region(value):
        region_property(mesh, value, name, **bounds)
        return {str(k): float(value[k]) for k in sorted(value)}
    return real_scalar(value, name)


def _input_record(value):
    if callable(value):
        return {'kind': 'callable', 'origin': 'caller_provided', 'fingerprinted': False}
    if isinstance(value, dict):
        return {'kind': 'per_region', 'value': dict(value)}
    return {'kind': 'constant', 'value': np.asarray(value).tolist()}


@dataclass(frozen=True)
class SteadyThermoelasticResult(ResultSurface):
    """Aggregate at return time; component arrays/owned mesh remain mutable.

    temperature_snapshot and canonical manifest JSON are immutable copies.
    There is no post-return certification of mutable component results.
    Its fields are objects (``.units`` is empty); ``heat.units`` and ``mechanics.units``
    give the units of the stage results.
    """
    UNITS = MappingProxyType({})
    BASIS = "planar"

    reference_mesh: Mesh
    heat: object
    temperature_snapshot: object
    mechanics: object
    manifest_json: str = field(repr=False)

    @property
    def manifest(self):
        """Return a fresh dictionary; editing it cannot change canonical JSON."""
        return json.loads(self.manifest_json)


#: the quantity parameters of solve_steady_thermoelasticity, refused as text (SI numbers only)
_QUANTITIES = ('thermal_conductivity', 'prescribed_temperature', 'heat_source_density', 'youngs_modulus',
               'poisson_ratio', 'linear_expansion_coefficient', 'stress_free_temperature', 'prescribed_displacement',
               'body_force_density')


def solve_steady_thermoelasticity(mesh, *, thermal_conductivity, prescribed_temperature,
                                 heat_source_density=None, youngs_modulus, poisson_ratio,
                                 plane, linear_expansion_coefficient, stress_free_temperature,
                                 prescribed_displacement, body_force_density=None, motion=None):
    """Run existing heat/freeze/mechanics APIs on one isolated SI reference mesh.

    SI only, no conversion or inference. Constant thermal_conductivity W/(m K),
    youngs_modulus Pa, poisson_ratio, signed linear_expansion_coefficient 1/K,
    nonnegative stress_free_temperature K. thermal_conductivity, youngs_modulus,
    poisson_ratio, linear_expansion_coefficient and a constant heat_source_density
    (W/m^3) may each be {region name: value} over mesh.region_names (piecewise
    constant; docs/packages/galerkin/multimaterial.md). heat_source_density=None is
    no source. Heat uses prescribed_temperature + insulation. Mechanics uses the
    component prescribed_displacement and zero total natural traction;
    body_force_density None (no body force), a constant (2,) or a callable, N/m^3.
    See the complete EN/KO guide.
    motion=galerkin.shape.MeshMotion(design_velocity=W, t=t) solves on the nodes X0 +
    t*W, solving the heat stage again on the moving mesh, and every heat and
    mechanics result carries the derivative with respect to the JAX or PyTorch
    scalar t (docs/packages/galerkin/shape_derivative.md).
    """
    for name, value in zip(_QUANTITIES, (thermal_conductivity, prescribed_temperature, heat_source_density,
                                         youngs_modulus, poisson_ratio, linear_expansion_coefficient,
                                         stress_free_temperature, prescribed_displacement, body_force_density)):
        refuse_text(name, value)
    heat_source = 0.0 if heat_source_density is None else heat_source_density
    body_force = (0., 0.) if body_force_density is None else body_force_density
    if motion is not None:
        from ._moving import solve_steady_thermoelasticity_moving
        return solve_steady_thermoelasticity_moving(
            mesh, motion, thermal_conductivity=thermal_conductivity, prescribed_temperature=prescribed_temperature,
            heat_source_density=heat_source, youngs_modulus=youngs_modulus, poisson_ratio=poisson_ratio,
            plane=plane, linear_expansion_coefficient=linear_expansion_coefficient,
            stress_free_temperature=stress_free_temperature, prescribed_displacement=prescribed_displacement,
            body_force_density=body_force)
    chain = OneWayChain(_stage_error)
    with chain.stage('input'):
        owned = isolated_mesh(mesh)
        state = mesh_state(owned)
        k = _material(owned, thermal_conductivity, 'thermal_conductivity', positive=True)
        e = _material(owned, youngs_modulus, 'youngs_modulus', positive=True)
        nu = _material(owned, poisson_ratio, 'poisson_ratio', lower=-1., upper=.5)
        alpha = _material(owned, linear_expansion_coefficient, 'linear_expansion_coefficient')
        tref = real_scalar(stress_free_temperature, 'stress_free_temperature')
        scalars = [v for v in (k, e) if not isinstance(v, dict)]
        if (any(v <= 0 for v in scalars) or (not isinstance(nu, dict) and not -1 < nu < .5)
                or tref < 0 or plane not in ('stress', 'strain')):
            raise ValueError('require thermal_conductivity > 0, youngs_modulus > 0, -1 < poisson_ratio < 0.5, '
                             "stress_free_temperature >= 0 K and plane 'stress' or 'strain'")
        heat_bc = dirichlet_supports(prescribed_temperature)
        mechanical_bc = dirichlet_supports(prescribed_displacement, vector=True)
        source = (heat_source if callable(heat_source)
                  else _material(owned, heat_source, 'heat_source_density'))
        body = body_force if callable(body_force) else real_array(body_force, 'body_force_density')
        if not callable(body) and body.shape != (2,):
            raise ValueError('constant body_force_density must have shape (2,)')
        # Capture configuration before external callbacks can mutate caller inputs.
        inputs = {'materials': {'thermal_conductivity': k, 'youngs_modulus': e,
                               'poisson_ratio': nu, 'linear_expansion_coefficient': alpha,
                               'stress_free_temperature': tref, 'plane': plane},
                  'prescribed_temperature': [[i, v] for i, v in sorted(heat_bc.items())],
                  'prescribed_displacement': [[i, c, v] for (i, c), v in sorted(mechanical_bc.items())],
                  'heat_source_density': _input_record(source), 'body_force_density': _input_record(body)}
    with chain.stage('heat'):
        heat = solve_steady_heat_outward(owned, conductivity=k, dirichlet=heat_bc, heat_source=source)
        # The mechanical stage computes with NumPy; a live heat input would lose its derivative.
        refuse_live(heat.temperature, "solve_steady_thermoelasticity heat inputs")
        check_mesh_unchanged(owned, state)
    with chain.stage('transfer'):
        raw = np.asarray(heat.temperature)
        if raw.shape != (len(owned.nodes),):
            raise ValueError(f'heat temperature must have shape ({len(owned.nodes)},), got {raw.shape}')
        if raw.dtype.kind not in 'iuf':
            raise ValueError('heat temperature must be a real numeric nodal array')
        invalid = np.flatnonzero(~np.isfinite(raw))
        if len(invalid):
            node = int(invalid[0])
            raise ValueError(f'nonfinite temperature transfer at node {node}: {raw[node]} K')
        with np.errstate(over='ignore', invalid='ignore'):
            temperature = np.array(raw, dtype=float, copy=True)
        invalid = np.flatnonzero(~np.isfinite(temperature))
        if len(invalid):
            raise ValueError(f'temperature transfer exceeds finite numeric range at node {int(invalid[0])}')
        minimum_node = int(np.argmin(temperature))
        if temperature[minimum_node] < 0:
            raise ValueError(f'temperature transfer requires nonnegative Kelvin; minimum {temperature[minimum_node]} K at node {minimum_node}')
        check_mesh_unchanged(owned, state)
        # Same-mesh identity transfer of the nodal Kelvin field; the snapshot
        # below adds its immutable fingerprinted form for mechanics.
        nodal = transfer(Field(owned, temperature, location='node', unit='K',
                               name='heat temperature'), owned)
        snapshot = freeze_temperature(owned, temperature=nodal.values)
        if not np.array_equal(snapshot.temperature, temperature):
            raise ValueError('temperature transfer did not preserve exact nodal values')
    with chain.stage('mechanics'):
        mechanics = solve_thermoelasticity(owned, snapshot, stress_free_temperature=tref,
            linear_expansion_coefficient=alpha, youngs_modulus=e, poisson_ratio=nu, plane=plane,
            prescribed_displacement=mechanical_bc, body_force_density=body)
        check_mesh_unchanged(owned, state)
    with chain.stage('manifest'):
        manifest = {'schema': SCHEMA,
            'units': {**INPUT_UNITS, **heat.units, **mechanics.units}, 'inputs': inputs,
            'mesh': {'nodes': len(owned.nodes), 'triangles': len(owned.triangles),
                     'mesh_hash': snapshot.mesh_hash,
                     'boundary': {k: v.tolist() for k, v in state[2].items()},
                     'boundary_edges': {k: v.tolist() for k, v in state[3].items()},
                     'regions': None if state[4] is None else state[4].tolist(), 'region_names': state[5]},
            'transfer': {'policy': 'same_mesh_exact_nodal_P1_copy', 'schema_version': snapshot.schema_version,
                         'temperature_hash': snapshot.temperature_hash, 'snapshot_hash': snapshot.snapshot_hash},
            'stages': {stage: 'completed' for stage in chain.completed if stage != 'input'},
            'origin': 'workflow_owned_heat_call', 'authentication': 'not_certified',
            'callback_policy': 'caller_provided_unfingerprinted',
            'post_return_integrity': 'not_certified_mutable_component_results'}
        encoded = json.dumps(manifest, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return SteadyThermoelasticResult(owned, heat, snapshot, mechanics, encoded)
