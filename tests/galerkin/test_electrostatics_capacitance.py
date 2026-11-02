# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""galerkin.electrostatics against refsol.electrostatics: pre-registered gates E1-E6.

E1 energy route eps0 V_i^T K V_j vs charge route (reaction sums): <= 1e-10 relative.
E2 coaxial capacitance on annulus meshes: observed order >= 1.8, finest <= 1e-3.
E3 two-layer parallel plate: exact in P1, <= 1e-12.
E4 real eps: C symmetric positive definite; complex eps (tan d 0.02): the loss
   matrix -Im C is positive definite (Im C_ii < 0), Re C within 1e-12 of the
   lossless C.
E5 homogeneous eps scaling dC/d eps_r = C / eps_r on JAX and PyTorch (1e-10),
   skipped when the library is absent.
E6 charge balance: sum of conductor charges (ground included) = -(total free
   charge) to 1e-10 relative; with rho = 0 the sum <= 1e-12 of the largest charge.
Error paths: touching conductors, unknown nodes, missing or unnecessary gauges,
invalid permittivities.
"""
import numpy as np
import pytest
from scipy.constants import epsilon_0

from galerkin import (ElementPermittivity, annulus_mesh, assemble_stiffness, capacitance_matrix,
                      rectangle_mesh, solve_electrostatics)
from galerkin.mesh import layered_rectangle_mesh
from conftest import rate

A, B = 1.0, 3.0
EPS = 2.2
H1, EPS1, H2, EPS2, WIDTH = 0.3e-3, 2.0, 0.7e-3, 5.0, 2.0e-3


def _coax(n_r):
    return annulus_mesh(A, B, n_r, 6 * n_r)


def _plate_mesh(nx=(3, 7), ny=4):
    return layered_rectangle_mesh([H1, H1 + H2], WIDTH, list(nx), ny)


def _three_conductor_mesh():
    """A rectangle with two interior zero-thickness traces above a grounded bottom."""
    mesh = rectangle_mesh(4.0, 2.0, 16, 8)
    x, y = mesh.nodes[:, 0], mesh.nodes[:, 1]
    row = np.isclose(y, 1.0)
    left = np.flatnonzero(row & (x >= 0.75 - 1e-12) & (x <= 1.5 + 1e-12))
    right = np.flatnonzero(row & (x >= 2.5 - 1e-12) & (x <= 3.25 + 1e-12))
    return mesh, {"left": left, "right": right}, mesh.boundary["bottom"]


# -- E1 ------------------------------------------------------------------------

def test_e1_energy_and_charge_routes_agree():
    mesh, conductors, ground = _three_conductor_mesh()
    names = list(conductors)
    mesh_eps = 3.0
    K = assemble_stiffness(mesh, epsilon_0 * mesh_eps)
    potentials, charges = [], []
    for excited in names:
        r = solve_electrostatics(mesh, permittivity=mesh_eps, ground=ground,
                                 conductors={k: (v, 1.0 if k == excited else 0.0)
                                             for k, v in conductors.items()})
        potentials.append(r.potential)
        charges.append([r.charge[k] for k in names])
    V = np.stack(potentials, axis=1)
    energy = V.T @ (K @ V)
    charge = np.array(charges).T
    diff = np.max(np.abs(energy - charge)) / np.max(np.abs(charge))
    print(f"E1 route difference {diff:.3e}")
    assert diff <= 1e-10
    C = capacitance_matrix(mesh, permittivity=mesh_eps, conductors=conductors, ground=ground)
    assert np.max(np.abs(C - 0.5 * (charge + charge.T))) <= 1e-14 * np.max(np.abs(C))


# -- E2 ------------------------------------------------------------------------

def test_e2_coax_capacitance_converges_at_second_order(refsol):
    exact = refsol.electrostatics.coax_capacitance(A, B, EPS)
    errors = []
    for n_r in (4, 8, 16, 32):
        mesh = _coax(n_r)
        C = capacitance_matrix(mesh, permittivity=EPS, conductors={"inner": mesh.boundary["inner"]},
                               ground=mesh.boundary["outer"])
        errors.append(abs(C[0, 0] / exact - 1.0))
    orders = rate(errors)
    print(f"E2 coax C relative errors {errors}, orders {orders}")
    assert np.all(orders[-2:] >= 1.8)
    assert errors[-1] <= 1e-3


def test_e2_coax_potential_and_field_follow_the_closed_form(refsol):
    mesh = _coax(32)
    r = solve_electrostatics(mesh, permittivity=EPS, ground=mesh.boundary["outer"],
                             conductors={"inner": (mesh.boundary["inner"], 1.0)})
    radius = np.hypot(*mesh.nodes.T)
    assert np.max(np.abs(r.potential - refsol.metallic.coax_potential(radius, A, B))) < 2e-3
    centroid = mesh.nodes[mesh.triangles].mean(axis=1)
    rc = np.hypot(*centroid.T)
    magnitude = np.linalg.norm(r.electric_field, axis=1)
    rel = np.abs(magnitude / refsol.metallic.coax_field_magnitude(rc, A, B) - 1.0)
    assert rel.mean() < 0.01
    np.testing.assert_allclose(r.displacement, epsilon_0 * EPS * r.electric_field, rtol=0, atol=0)
    assert r.energy_per_length == pytest.approx(0.5 * r.charge["inner"], rel=1e-12)


# -- E3 ------------------------------------------------------------------------

def test_e3_two_layer_parallel_plate_is_exact_in_p1(refsol):
    mesh = _plate_mesh()
    exact = refsol.electrostatics.two_layer_plate_capacitance(H1, EPS1, H2, EPS2, WIDTH)
    C = capacitance_matrix(mesh, permittivity={"layer0": EPS1, "layer1": EPS2},
                           conductors={"plate": mesh.boundary["left"]}, ground=mesh.boundary["right"])
    error = abs(C[0, 0] / exact - 1.0)
    print(f"E3 two-layer plate relative error {error:.3e}")
    assert error <= 1e-12
    # The same table as a mesh-bound element permittivity.
    names = mesh.region_names
    table = np.array([EPS1 if names[k] == "layer0" else EPS2 for k in mesh.regions])
    C2 = capacitance_matrix(mesh, permittivity=ElementPermittivity(mesh, table),
                            conductors={"plate": mesh.boundary["left"]}, ground=mesh.boundary["right"])
    assert C2[0, 0] == C[0, 0]


def test_e3_two_layer_plate_with_different_loss_tangents_is_exact(refsol):
    mesh = _plate_mesh()
    e1, e2 = EPS1 * (1 - 0.01j), EPS2 * (1 - 0.002j)
    exact = refsol.electrostatics.two_layer_plate_capacitance(H1, e1, H2, e2, WIDTH)
    C = capacitance_matrix(mesh, permittivity={"layer0": e1, "layer1": e2},
                           conductors={"plate": mesh.boundary["left"]}, ground=mesh.boundary["right"])
    assert abs(C[0, 0] / exact - 1.0) <= 1e-12
    assert C[0, 0].imag < 0


# -- E4 ------------------------------------------------------------------------

def test_e4_real_matrix_is_symmetric_positive_definite_and_complex_is_passive():
    mesh, conductors, ground = _three_conductor_mesh()
    C = capacitance_matrix(mesh, permittivity=EPS, conductors=conductors, ground=ground)
    assert C.shape == (2, 2) and C.dtype == float
    assert np.array_equal(C, C.T)
    assert np.all(np.linalg.eigvalsh(C) > 0)
    assert C[0, 1] < 0 < C[0, 0]
    tan = 0.02
    Cc = capacitance_matrix(mesh, permittivity=EPS * (1 - 1j * tan), conductors=conductors, ground=ground)
    assert Cc.dtype == complex and np.array_equal(Cc, Cc.T)
    # Passivity of the loss matrix: -Im C is positive semidefinite with a positive
    # diagonal; off-diagonal Im C is positive because the mutual C is negative.
    assert np.all(np.diag(Cc.imag) < 0)
    assert np.all(np.linalg.eigvalsh(-Cc.imag) > 0)
    assert Cc[0, 1].imag > 0
    real_gap = np.max(np.abs(Cc.real - C)) / np.max(np.abs(C))
    imag_gap = np.max(np.abs(Cc.imag + tan * C)) / np.max(np.abs(C))
    print(f"E4 Re C gap {real_gap:.3e}, Im C + tan d C gap {imag_gap:.3e}")
    assert real_gap <= 1e-12
    assert imag_gap <= 1e-12


# -- E5 ------------------------------------------------------------------------

def _coax_capacitance_live(name, eps):
    mesh = _coax(8)
    return capacitance_matrix(mesh, permittivity=eps, conductors={"inner": mesh.boundary["inner"]},
                              ground=mesh.boundary["outer"])[0, 0]


def _coax_capacitance(eps):
    return float(_coax_capacitance_live("numpy", eps))


def test_e5_jax_derivative_of_homogeneous_eps_is_c_over_eps():
    jax = pytest.importorskip("jax")
    jax.config.update("jax_enable_x64", True)
    jnp = jax.numpy
    value, grad = jax.value_and_grad(lambda e: _coax_capacitance_live("jax", e))(jnp.asarray(EPS))
    assert float(value) == pytest.approx(_coax_capacitance(EPS), rel=1e-13)
    assert float(grad) == pytest.approx(float(value) / EPS, rel=1e-10)
    table = {"layer0": jnp.asarray(EPS1), "layer1": jnp.asarray(EPS2)}
    mesh = _plate_mesh()

    def plate(e1):
        return capacitance_matrix(mesh, permittivity={"layer0": e1, "layer1": table["layer1"]},
                                  conductors={"plate": mesh.boundary["left"]},
                                  ground=mesh.boundary["right"])[0, 0]
    exact = epsilon_0 * WIDTH / (H1 / EPS1 + H2 / EPS2)
    d_exact = exact ** 2 / (epsilon_0 * WIDTH) * H1 / EPS1 ** 2
    assert float(jax.grad(plate)(table["layer0"])) == pytest.approx(d_exact, rel=1e-10)
    with pytest.raises(TypeError, match="complex permittivity"):
        _coax_capacitance_live("jax", jnp.asarray(EPS * (1 - 0.02j)))


def test_e5_torch_derivative_of_homogeneous_eps_is_c_over_eps():
    torch = pytest.importorskip("torch")
    eps = torch.tensor(EPS, dtype=torch.float64, requires_grad=True)
    value = _coax_capacitance_live("torch", eps)
    value.backward()
    assert float(value) == pytest.approx(_coax_capacitance(EPS), rel=1e-13)
    assert float(eps.grad) == pytest.approx(float(value) / EPS, rel=1e-10)
    with pytest.raises(TypeError, match="complex permittivity"):
        _coax_capacitance_live("torch", torch.tensor(EPS * (1 - 0.02j), dtype=torch.complex128))


# -- E6 ------------------------------------------------------------------------

def test_e6_charges_balance_the_free_charge():
    mesh = _coax(16)
    rho = 1e-6
    r = solve_electrostatics(mesh, permittivity=EPS, ground=mesh.boundary["outer"],
                             conductors={"inner": (mesh.boundary["inner"], 0.0)}, charge_density=rho)
    total = rho * mesh.areas().sum()
    assert r.total_free_charge == pytest.approx(total, rel=1e-13)
    assert r.load.sum() == pytest.approx(total, rel=1e-13)
    balance = abs(sum(r.charge.values()) + r.total_free_charge) / abs(r.total_free_charge)
    print(f"E6 charge balance with rho {balance:.3e}")
    assert balance <= 1e-10
    assert r.charge["inner"] < 0 and r.charge["ground"] < 0
    assert abs(np.sum(r.reaction) - sum(r.charge.values())) <= 1e-12 * abs(r.total_free_charge)
    # Reaction sits on conductor nodes only; the free residual is at solver precision.
    interior = np.setdiff1d(np.arange(mesh.num_nodes),
                            np.concatenate([mesh.boundary["inner"], mesh.boundary["outer"]]))
    assert np.all(r.reaction[interior] == 0)
    assert np.max(np.abs(r.residual[interior])) <= 1e-12 * abs(r.total_free_charge)


def test_e6_without_free_charge_the_conductor_charges_cancel():
    mesh, conductors, ground = _three_conductor_mesh()
    r = solve_electrostatics(mesh, permittivity=EPS, ground=ground,
                             conductors={"left": (conductors["left"], 1.0),
                                         "right": (conductors["right"], -0.5)})
    largest = max(abs(q) for q in r.charge.values())
    cancel = abs(sum(r.charge.values())) / largest
    print(f"E6 charge sum without rho {cancel:.3e} of the largest charge")
    assert cancel <= 1e-12
    assert r.total_free_charge == 0.0
    assert r.energy_per_length == pytest.approx(0.5 * (r.charge["left"] - 0.5 * r.charge["right"]), rel=1e-12)
    assert r.energy_per_length > 0


def test_e6_neumann_component_needs_a_gauge_and_balanced_charge():
    mesh = layered_rectangle_mesh([0.5, 1.0], 1.0, [4, 4], 4)
    rho = {"layer0": 2e-6, "layer1": -2e-6}
    with pytest.raises(ValueError, match="exactly one reference_potential"):
        solve_electrostatics(mesh, permittivity=1.0, conductors={}, charge_density=rho)
    r = solve_electrostatics(mesh, permittivity=1.0, conductors={}, charge_density=rho,
                             reference_potential={0: 3.0})
    assert r.potential[0] == 3.0
    assert r.total_free_charge == pytest.approx(0.0, abs=1e-12 * 2e-6)
    assert np.all(r.reaction == 0) and r.charge == {} and r.conductors == {}
    with pytest.raises(ValueError, match="incompatible net free charge"):
        solve_electrostatics(mesh, permittivity=1.0, conductors={}, charge_density=1e-6,
                             reference_potential={0: 0.0})
    with pytest.raises(ValueError, match="unnecessary"):
        solve_electrostatics(mesh, permittivity=1.0, conductors={0: 1.0}, charge_density=0.0,
                             reference_potential={5: 0.0})


# -- inputs and results ---------------------------------------------------------

def test_dirichlet_node_mapping_matches_the_node_set_form():
    mesh = _coax(8)
    sets = solve_electrostatics(mesh, permittivity=EPS, ground=mesh.boundary["outer"],
                                conductors={"inner": (mesh.boundary["inner"], 2.0)})
    mapping = {int(i): 2.0 for i in mesh.boundary["inner"]}
    nodes = solve_electrostatics(mesh, permittivity=EPS, ground=mesh.boundary["outer"], conductors=mapping)
    np.testing.assert_array_equal(nodes.potential, sets.potential)
    assert set(nodes.charge) == set(mapping) | {"ground"}
    assert sum(nodes.charge[i] for i in mapping) == pytest.approx(sets.charge["inner"], rel=1e-14)
    assert nodes.charge["ground"] == sets.charge["ground"]


def test_charge_density_callback_and_table_agree_with_the_scalar():
    mesh = layered_rectangle_mesh([0.5, 1.0], 1.0, [4, 4], 4)
    bc = {"top": (mesh.boundary["top"], 0.0)}
    scalar = solve_electrostatics(mesh, permittivity=4.0, conductors=bc, ground=mesh.boundary["bottom"],
                                  charge_density=3e-6)
    table = solve_electrostatics(mesh, permittivity=4.0, conductors=bc, ground=mesh.boundary["bottom"],
                                 charge_density={"layer0": 3e-6, "layer1": 3e-6})
    callback = solve_electrostatics(mesh, permittivity=4.0, conductors=bc, ground=mesh.boundary["bottom"],
                                    charge_density=lambda x, y: 3e-6 + 0.0 * x)
    np.testing.assert_array_equal(table.potential, scalar.potential)
    np.testing.assert_array_equal(callback.potential, scalar.potential)
    # Plates at y = 0 and y = 1 with uniform rho: V = rho y (1 - y) / (2 eps) is quadratic, so the
    # total charge is exact while the potential carries an O(h^2) discretisation error.
    assert sum(scalar.charge.values()) == pytest.approx(-3e-6, rel=1e-12)
    mid = np.isclose(mesh.nodes[:, 1], 0.5)
    assert np.allclose(scalar.potential[mid], 3e-6 / (8 * 4.0 * epsilon_0), rtol=5e-2)


def test_results_are_read_only_snapshots_in_mesh_order():
    mesh = _coax(4)
    r = solve_electrostatics(mesh, permittivity=EPS, ground=mesh.boundary["outer"],
                             conductors={"inner": (mesh.boundary["inner"], 1.0)})
    for a in (r.potential, r.electric_field, r.displacement, r.relative_permittivity, r.load,
              r.reaction, r.residual, r.mesh.nodes, r.conductors["inner"]):
        assert not a.flags.writeable
    assert r.mesh.nodes is not mesh.nodes
    np.testing.assert_array_equal(r.mesh.triangles, mesh.triangles)
    np.testing.assert_array_equal(r.conductors["ground"], np.sort(mesh.boundary["outer"]))
    assert r.relative_permittivity.shape == (mesh.num_triangles,)
    assert np.all(r.relative_permittivity == EPS)
    assert r.electric_field.shape == r.displacement.shape == (mesh.num_triangles, 2)
    assert isinstance(r.energy_per_length, float) and isinstance(r.charge["inner"], float)


@pytest.mark.parametrize("eps, match", [
    (0.0, "Re > 0"), (-1.0, "Re > 0"), (np.inf, "finite"), (True, "boolean"),
    (2.0 + 0.1j, "Im <= 0"), (-1.0 - 0.1j, "Re > 0"), ([1.0, 2.0], "scalar"),
])
def test_invalid_permittivities_are_rejected(eps, match):
    mesh = _coax(4)
    with pytest.raises(ValueError, match=match):
        solve_electrostatics(mesh, permittivity=eps, ground=mesh.boundary["outer"],
                             conductors={"inner": (mesh.boundary["inner"], 1.0)})


def test_region_tables_and_element_permittivity_are_checked():
    mesh = _plate_mesh()
    bc = {"plate": (mesh.boundary["left"], 1.0)}
    with pytest.raises(ValueError, match="region_names exactly"):
        solve_electrostatics(mesh, permittivity={"layer0": 2.0}, conductors=bc, ground=mesh.boundary["right"])
    with pytest.raises(ValueError, match="strictly positive"):
        ElementPermittivity(mesh, np.zeros(mesh.num_triangles))
    other = _plate_mesh(nx=(2, 7))
    with pytest.raises(ValueError, match="do not match"):
        solve_electrostatics(mesh, permittivity=ElementPermittivity(other, np.ones(other.num_triangles)),
                             conductors=bc, ground=mesh.boundary["right"])
    with pytest.raises(ValueError, match="ground"):
        solve_electrostatics(mesh, permittivity=2.0, conductors={"ground": (mesh.boundary["left"], 1.0)},
                             ground=mesh.boundary["right"])


def test_conductor_errors():
    mesh = _coax(4)
    inner, outer = mesh.boundary["inner"], mesh.boundary["outer"]
    with pytest.raises(ValueError, match="must not touch"):
        solve_electrostatics(mesh, permittivity=1.0, conductors={"a": (inner, 1.0), "b": (inner[:2], 0.0)})
    with pytest.raises(ValueError, match="must not touch"):
        capacitance_matrix(mesh, permittivity=1.0, conductors={"a": inner}, ground=np.r_[outer, inner[0]])
    with pytest.raises(ValueError, match="outside the mesh"):
        solve_electrostatics(mesh, permittivity=1.0, conductors={"a": ([mesh.num_nodes], 1.0)}, ground=outer)
    with pytest.raises(ValueError, match="outside the mesh"):
        solve_electrostatics(mesh, permittivity=1.0, conductors={"a": (inner, 1.0)}, ground=[-1])
    with pytest.raises(ValueError, match="no mesh nodes"):
        capacitance_matrix(mesh, permittivity=1.0, conductors={"a": inner}, ground=[])
    with pytest.raises(ValueError, match="integer node indices"):
        solve_electrostatics(mesh, permittivity=1.0, conductors={"a": ([0.5], 1.0)}, ground=outer)
    with pytest.raises(ValueError, match="pair"):
        solve_electrostatics(mesh, permittivity=1.0, conductors={"a": inner}, ground=outer)
    with pytest.raises(ValueError, match="all names"):
        solve_electrostatics(mesh, permittivity=1.0, conductors={"a": (inner, 1.0), 3: 0.0}, ground=outer)
    with pytest.raises(ValueError, match="scalar volts"):
        solve_electrostatics(mesh, permittivity=1.0, conductors={"a": (inner, [1.0, 2.0])}, ground=outer)
    with pytest.raises(ValueError, match="within the mesh"):
        solve_electrostatics(mesh, permittivity=1.0, conductors={}, reference_potential={-1: 0.0})
    with pytest.raises(ValueError, match="exactly one reference_potential"):
        solve_electrostatics(mesh, permittivity=1.0, conductors={})
    with pytest.raises(ValueError, match="at least one conductor"):
        capacitance_matrix(mesh, permittivity=1.0, conductors={}, ground=outer)
    with pytest.raises(ValueError, match="needs ground"):
        capacitance_matrix(mesh, permittivity=1.0, conductors={"a": inner}, ground=None)
    with pytest.raises(ValueError, match="rename"):
        capacitance_matrix(mesh, permittivity=1.0, conductors={"ground": inner}, ground=outer)


def test_capacitance_route_check_raises_when_the_routes_disagree(monkeypatch):
    import galerkin.electrostatics as module
    mesh = _coax(4)
    monkeypatch.setattr(module, "_ROUTE_TOLERANCE", 0.0)
    with pytest.raises(ValueError, match="energy and charge routes disagree"):
        capacitance_matrix(mesh, permittivity=1.0, conductors={"a": mesh.boundary["inner"]},
                           ground=mesh.boundary["outer"])
