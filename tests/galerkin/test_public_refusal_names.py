# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The outward-form bodies refuse under the public registry names (galerkin step, L2 commit 8b).

The public heat, electric and Joule solvers negate their inward boundary data once and call
internal outward-form bodies. A bad value is refused by the body, so its message must name the
quantity the caller passed (thermal_conductivity, prescribed_temperature, inward_heat_flux,
iteration_limit, ...), never the body's keyword. No message prints a flux or current value, so
none can show an outward value under an inward name. A few representative refusals per solver.
"""
import re

import numpy as np
import pytest

from galerkin.electric import solve_steady_electric
from galerkin.joule_heating import solve_steady_joule_heat
from galerkin.mesh import rectangle_mesh
from galerkin.temperature_joule_heating import solve_temperature_joule_heat
from galerkin.thermal import solve_steady_heat
from galerkin.transient_heat import solve_transient_heat

#: the bodies' keywords and labels before the galerkin step; none may reach a public message
OLD = re.compile(r"\b(conductivity|dirichlet|Dirichlet|heat_source|outward_flux|outward flux|outward_current|"
                 r"reference_potential|relaxation|temperature_atol|max_iterations|Neumann|thermal_dirichlet|"
                 r"electric_dirichlet|joule_load|_per_length)\b")


def _refused(call, pattern, error=ValueError):
    with pytest.raises(error, match=pattern) as info:
        call()
    message = str(info.value)
    assert not OLD.search(re.sub(r"\b(thermal|electrical)_conductivity\b|\bheat_source_density\b", "", message)), message
    return message


@pytest.fixture
def mesh():
    return rectangle_mesh(1.0, 0.5, 4, 2)


def _left(mesh, value):
    return {int(i): value for i in mesh.boundary["left"]}


def test_steady_heat_refusals_name_the_public_quantities(mesh):
    held = _left(mesh, 300.0)
    _refused(lambda: solve_steady_heat(mesh, thermal_conductivity=-1.0, prescribed_temperature=held),
             r"^thermal_conductivity must be a finite scalar > 0$")
    _refused(lambda: solve_steady_heat(mesh, thermal_conductivity=1.0, prescribed_temperature=[(0, 300.0)]),
             r"^prescribed_temperature must map node indices to temperatures in K$")
    _refused(lambda: solve_steady_heat(mesh, thermal_conductivity=1.0, prescribed_temperature={10**6: 300.0}),
             r"^prescribed_temperature node 1000000 is outside the mesh's")
    _refused(lambda: solve_steady_heat(mesh, thermal_conductivity=1.0, prescribed_temperature=held,
                                       inward_heat_flux={"nowhere": 1.0}),
             r"^inward_heat_flux: unknown boundary edge tag 'nowhere'$")
    _refused(lambda: solve_steady_heat(mesh, thermal_conductivity=1.0, prescribed_temperature=held,
                                       inward_heat_flux={"right": lambda p, n: np.ones((len(p), 2))}),
             r"^inward_heat_flux\['right'\] callback must return exactly shape \(Q,\)$")
    _refused(lambda: solve_steady_heat(mesh, thermal_conductivity=1.0, prescribed_temperature=held,
                                       convection={"right": (-1.0, 300.0)}),
             r"^convection\['right'\] heat_transfer_coefficient must be nonnegative$")
    _refused(lambda: solve_steady_heat(mesh, thermal_conductivity=1.0, prescribed_temperature=held,
                                       heat_source_density=lambda p: np.ones((len(p), 2))),
             r"^heat_source_density callback must return exactly shape \(Q,\)$")
    _refused(lambda: solve_steady_heat(mesh, thermal_conductivity=1.0, prescribed_temperature={},
                                       inward_heat_flux={"right": 1.0}),
             r"^each connected component requires prescribed_temperature or a positive convection "
             r"heat_transfer_coefficient; missing \[0\]$")


def test_transient_heat_refusals_name_the_public_quantities(mesh):
    common = dict(thermal_conductivity=1.0, volumetric_heat_capacity=1.0, time=[0.0, 1.0],
                  initial_temperature=np.full(mesh.num_nodes, 300.0))
    _refused(lambda: solve_transient_heat(mesh, **common, prescribed_temperature=[(0, 300.0)]),
             r"^prescribed_temperature must map integer nodes to Kelvin values$")
    _refused(lambda: solve_transient_heat(mesh, **{**common, "thermal_conductivity": -1.0}, prescribed_temperature={}),
             r"^thermal_conductivity must be a finite positive real scalar$")
    _refused(lambda: solve_transient_heat(mesh, **common, prescribed_temperature={},
                                          inward_heat_flux={"right": lambda a, b, c, d: 1.0}),
             r"^inward_heat_flux\['right'\] callback must take exactly one of the forms")


def test_electric_refusals_name_the_public_quantities(mesh):
    _refused(lambda: solve_steady_electric(mesh, electrical_conductivity=1.0, prescribed_electric_potential={},
                                           inward_current_density={"right": 1.0}, reference_electric_potential={0: 0.0}),
             r"^incompatible inward_current_density on component 0: a component without a "
             r"prescribed_electric_potential needs zero net current$")
    _refused(lambda: solve_steady_electric(mesh, electrical_conductivity=1.0, prescribed_electric_potential={}),
             r"^exactly one reference_electric_potential node is required per component without a "
             r"prescribed_electric_potential$")
    _refused(lambda: solve_steady_electric(mesh, electrical_conductivity=1.0,
                                           prescribed_electric_potential=_left(mesh, 0.0),
                                           reference_electric_potential={0: 0.0}),
             r"^reference_electric_potential is unnecessary on a component with a prescribed_electric_potential$")
    interior = int(np.setdiff1d(np.arange(mesh.num_nodes), np.concatenate(list(mesh.boundary.values())))[0])
    _refused(lambda: solve_steady_electric(mesh, electrical_conductivity=1.0,
                                           prescribed_electric_potential={interior: 0.0}),
             r"^prescribed_electric_potential node must lie on the exterior mesh boundary$")


def test_joule_refusals_name_the_public_quantities(mesh):
    electrical = solve_steady_electric(mesh, electrical_conductivity=1.0,
                                       prescribed_electric_potential={**_left(mesh, 0.0),
                                                                      **{int(i): 1.0 for i in mesh.boundary["right"]}})
    _refused(lambda: solve_steady_joule_heat(mesh, electrical_result=electrical, thermal_conductivity=-1.0,
                                             prescribed_temperature=_left(mesh, 300.0)),
             r"^thermal_conductivity must be a finite scalar > 0$")
    left = _left(mesh, 0.0)
    held = {**_left(mesh, 300.0), **{int(i): 300.0 for i in mesh.boundary["right"]}}
    common = dict(electrical_conductivity=1.0, thermal_conductivity=1.0, prescribed_electric_potential=left,
                  prescribed_temperature=held, initial_temperature=300.0, temperature_tolerance=1e-8)
    _refused(lambda: solve_temperature_joule_heat(mesh, **common, relaxation_factor=2.0),
             r"^relaxation_factor must be in \(0,1\]; temperature_tolerance and relative_tolerance must be positive$")
    _refused(lambda: solve_temperature_joule_heat(mesh, **common, iteration_limit=0),
             r"^iteration_limit must be a positive integer$")
