# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The outward-form bodies and the public mode and cavity functions refuse under the public registry names.

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


#: the mode kernel's keywords (galerkin.kernels.solve_modes, mode_coordinates); none may reach a public message
OLD_MODES = re.compile(r"\b(eps_r|mu_r|k0|n_target|num_modes|coordinate_factors|thickness|strength|order|"
                       r"et|ez|n_eff)\b")


def _mode_refused(call, pattern, error=ValueError):
    with pytest.raises(error, match=pattern) as info:
        call()
    message = re.sub(r"\bpml_(thickness|strength|order)\b", "", str(info.value))
    assert not OLD_MODES.search(message), str(info.value)


def test_mode_refusals_name_the_public_quantities():
    """The public mode functions (galerkin step, L3 commit 11b) refuse under their own registry names."""
    from galerkin.waveguide import Bend, ModalPML, mode_power, solve_waveguide_modes
    mesh = rectangle_mesh(2e-6, 1e-6, 8, 4)
    good = dict(relative_permittivity=2.25, vacuum_wavelength=1.55e-6, target_effective_index=1.4, search_mode_count=2)

    def solve(**changes):
        return lambda: solve_waveguide_modes(mesh, **{**good, **changes})
    _mode_refused(solve(vacuum_angular_wavenumber=4e6), "exactly one of vacuum_wavelength")
    _mode_refused(solve(vacuum_wavelength=None), "exactly one of vacuum_wavelength")
    _mode_refused(solve(vacuum_wavelength=-1.55e-6), "vacuum_wavelength must be a finite real number > 0")
    _mode_refused(solve(relative_permittivity=np.ones(3)), "relative_permittivity must be a finite number or an array")
    _mode_refused(solve(relative_permittivity=complex(np.nan, 0)), "relative_permittivity must be finite")
    _mode_refused(solve(relative_permeability=np.inf), "relative_permeability must be finite")
    _mode_refused(solve(target_effective_index=-1.0), "target_effective_index must be a finite number")
    _mode_refused(solve(search_mode_count=0), "search_mode_count must be a positive integer")
    _mode_refused(solve(pml={"left": 1e-7}), "pml must be a galerkin.ModalPML", TypeError)
    _mode_refused(solve(bend=Bend(bend_radius=1e-5, bend_origin=0.0)), "a bend needs a ModalPML")
    _mode_refused(solve(pml=ModalPML(pml_thickness={"left": 2e-7}), bend=Bend(bend_radius=1e-7, bend_origin=5e-7)),
                  "bend_radius and bend_origin must put every node")
    _mode_refused(lambda: ModalPML(pml_thickness={"left": 0.0}), r"pml_thickness\['left'\] must be a finite real")
    _mode_refused(lambda: ModalPML(pml_thickness={"front": 1e-7}), "pml_thickness must map one or more of")
    _mode_refused(lambda: ModalPML(pml_thickness={"left": 1e-7}, pml_order=5), "pml_order must be 2, 3 or 4")
    _mode_refused(lambda: Bend(bend_radius=0.0, bend_origin=0.0), "bend_radius must be a finite real number > 0")
    _mode_refused(lambda: Bend(bend_radius=1e-5, bend_origin=0.0, bend_axis="z"), "bend_axis must be 'x' or 'y'")
    modes = solve_waveguide_modes(mesh, **good)
    _mode_refused(lambda: mode_power(modes, len(modes.effective_index)), "mode must be a mode index")
    _mode_refused(lambda: mode_power(object(), 0), "modes must be the WaveguideModes", TypeError)


#: the cavity solvers' former keywords and labels; none may reach a public message
OLD_CAVITY = re.compile(r"\b(lengths_m|subdivisions|num_modes|target_frequency_hz|wall_conductivity_s_per_m|walls|"
                        r"bounds_m|regions\[[^]]*\] relative permittivity)\b|exp\(\+j")


def _cavity_refused(call, pattern, error=ValueError):
    with pytest.raises(error, match=pattern) as info:
        call()
    assert not OLD_CAVITY.search(str(info.value)), str(info.value)


def test_cavity_refusals_name_the_public_quantities():
    """The public cavity functions (galerkin step, L3 commit 12) refuse under their registry names."""
    from galerkin.cavity import solve_cavity, solve_cavity_box
    from galerkin.material_cavity import CavityMaterialRegion, solve_material_cavity, solve_material_cavity_box
    from galerkin.mesh3d import box_mesh
    good = dict(box_size=(1.0, 0.8, 0.6), subdivision_count=(2, 2, 2), mode_count=1, target_frequency=2.2e8)
    corners = dict(lower_corner_position=(0.0, 0.0, 0.0), upper_corner_position=(1.0, 0.8, 0.3))

    def box(solve, **changes):
        return lambda: solve(**{**good, **changes})
    for solve in (solve_cavity_box, solve_material_cavity_box):
        _cavity_refused(box(solve, box_size=(1.0, -0.8, 0.6)), r"^box_size\[1\] must be a finite positive number$")
        _cavity_refused(box(solve, subdivision_count=(2, 0, 2)), r"^subdivision_count\[1\] must be a positive integer$")
        _cavity_refused(box(solve, mode_count=0), r"^mode_count must be a positive integer$")
        _cavity_refused(box(solve, target_frequency=-1.0), r"^target_frequency must be a finite positive number$")
    _cavity_refused(box(solve_material_cavity_box, electrical_conductivity=-1.0),
                    r"^electrical_conductivity must be a finite positive number$")
    _cavity_refused(box(solve_material_cavity_box, electrical_conductivity={"z1": 0.0}),
                    r"^electrical_conductivity\[z1\] must be a finite positive number$")
    _cavity_refused(lambda: CavityMaterialRegion(**corners, relative_permittivity=4 - 0.1j),
                    r"^relative_permittivity must be finite with positive real part and non-negative imaginary part "
                    r"\(passive under exp\(-i omega t\): a loss is Im >= 0\)$")
    _cavity_refused(lambda: CavityMaterialRegion(**corners, relative_permeability=-1.0),
                    r"^relative_permeability must be finite with positive real part")
    _cavity_refused(lambda: CavityMaterialRegion(lower_corner_position=(0.0, 0.0), upper_corner_position=(1, 1, 1)),
                    r"^lower_corner_position must be three coordinates \(x, y, z\) in m$")
    region = CavityMaterialRegion(lower_corner_position=(0.0, 0.0, 0.0), upper_corner_position=(1.0, 0.8, 0.25))
    _cavity_refused(box(solve_material_cavity_box, regions=[region]),
                    r"^regions\[0\] bound 0.25 on axis 2 is not a mesh grid plane .*; adjust subdivision_count$")
    mesh = box_mesh(1.0, 0.8, 0.6, 2, 2, 2)
    mesh_good = dict(mode_count=1, target_frequency=0.8e8)
    _cavity_refused(lambda: solve_cavity(mesh, **mesh_good, pec_faces=("lid",)), r"^pec_faces: unknown face tag")
    _cavity_refused(lambda: solve_material_cavity(mesh, relative_permittivity={"other": 2.0}, **mesh_good),
                    r"^relative_permittivity must name the regions of mesh.region_names exactly")
    _cavity_refused(lambda: solve_material_cavity(mesh, relative_permittivity={"domain": 2.0},
                                                  relative_permeability={"other": 2.0}, **mesh_good),
                    r"^relative_permeability: unknown region")
    _cavity_refused(lambda: solve_material_cavity(mesh, relative_permittivity={"domain": 2.0 - 0.1j}, **mesh_good),
                    r"^relative_permittivity\['domain'\] must be finite with positive real part and non-negative")
    _cavity_refused(lambda: solve_material_cavity(mesh, relative_permittivity={"domain": 2.0},
                                                  electrical_conductivity={"lid": 1e6}, **mesh_good),
                    r"^electrical_conductivity: unknown face tag")
    _cavity_refused(lambda: solve_material_cavity(mesh, relative_permittivity={"domain": 2.0},
                                                  electrical_conductivity={"z1": -1e6}, **mesh_good),
                    r"^electrical_conductivity\['z1'\] must be a finite positive number$")
