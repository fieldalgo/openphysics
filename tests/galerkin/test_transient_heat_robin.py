# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Transient heat with prescribed outward flux and convection (pre-registered gates).

T1 convective slab and T2 constant-flux slab against the independent series of
refsol.transient_heat_robin: spatial order >= 1.8 over n=8/16/32 with 2000 steps
to 0.2 s, temporal order >= 0.9 over 4/8/16 steps on n=128, finest relative L2
error on the temperature-rise scale <= 2e-3. T3 long-time limit equals
solve_steady_heat on the same mesh to 1e-8. T4 per-step balance
storage = source + reaction - G - C to 1e-10 of the largest term, including a
Robin-only component with its own offset. T5 JAX/PyTorch histories equal NumPy
to 1e-12 and derivatives in h and ambient match central differences to 1e-6
(skipped when the libraries are absent). T6 every Dirichlet-only history is
unchanged: the fixture of origin/main 48720c9 is matched bit for bit on its
recorded platform and to roundoff elsewhere, and no boundary sampling runs.
Measured values are printed; thresholds are fixed and never loosened here.
"""
import platform

import numpy as np
import pytest

import galerkin.transient_heat as module
from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.thermal import solve_steady_heat
from galerkin.transient_heat import TransientHeatStepError, solve_transient_heat
from refsol.transient_heat_robin import ConvectiveSlab, FluxSlab
import transient_heat_dirichlet_cases as dirichlet_cases   # tests/galerkin is on pytest's pythonpath

L, K, C = 1.0, 2.5, 4.0
H, AMBIENT, INITIAL = 5.0, 300.0, 350.0
OUTWARD = -100.0                       # W/m^2, negative: heat enters at x = L
T_END = 0.2
CONVECTIVE = ConvectiveSlab(L, K, C, H, AMBIENT, INITIAL)
FLUX = FluxSlab(L, K, C, OUTWARD, INITIAL)


def slab(n, steps, kind):
    """A one-cell-high strip of n squares; left insulated, right convective or prescribed."""
    mesh = rectangle_mesh(L, L/n, n, 1)
    natural = ({"convection": {"right": (H, AMBIENT)}} if kind == "convective"
               else {"outward_flux": {"right": OUTWARD}})
    result = solve_transient_heat(
        mesh, conductivity=K, volumetric_heat_capacity=C, time_s=np.linspace(0.0, T_END, steps+1),
        initial_temperature_k=np.full(mesh.num_nodes, INITIAL), dirichlet={}, **natural)
    return mesh, result


def l2_error(mesh, nodal, exact, scale):
    """Relative L2 error of the P1 field against exact(x): edge-midpoint rule, exact for quadratics."""
    p, t = mesh.nodes, mesh.triangles
    q = p[t]
    area = 0.5*abs((q[:, 1, 0]-q[:, 0, 0])*(q[:, 2, 1]-q[:, 0, 1])-(q[:, 2, 0]-q[:, 0, 0])*(q[:, 1, 1]-q[:, 0, 1]))
    total = 0.0
    for a, b in ((0, 1), (1, 2), (2, 0)):
        mid = (q[:, a]+q[:, b])/2
        value = (nodal[t[:, a]]+nodal[t[:, b]])/2
        total += np.sum(area/3*(value-exact(mid[:, 0]))**2)
    return np.sqrt(total/np.sum(area))/scale


def reference(kind):
    series = CONVECTIVE if kind == "convective" else FLUX
    scale = abs(INITIAL-AMBIENT) if kind == "convective" else abs(OUTWARD)*L/K
    return (lambda x: series.temperature(x, T_END).temperature_k), scale


def orders(errors):
    return [np.log2(errors[i]/errors[i+1]) for i in range(len(errors)-1)]


@pytest.mark.parametrize("kind", ["convective", "flux"])
def test_t1_t2_spatial_convergence_with_tiny_steps(kind):
    exact, scale = reference(kind)
    errors = []
    for n in (8, 16, 32):
        mesh, result = slab(n, 2000, kind)
        errors.append(l2_error(mesh, result.temperature_k[-1], exact, scale))
    observed = orders(errors)
    print(f"\n{kind} slab spatial errors n=8/16/32 (dt=1e-4 s): {errors}, orders {observed}")
    assert min(observed) >= 1.8
    assert errors[-1] <= 2e-3


@pytest.mark.parametrize("kind", ["convective", "flux"])
def test_t1_t2_temporal_convergence_on_fine_mesh(kind):
    exact, scale = reference(kind)
    errors = []
    for steps in (4, 8, 16):
        mesh, result = slab(128, steps, kind)
        errors.append(l2_error(mesh, result.temperature_k[-1], exact, scale))
    observed = orders(errors)
    print(f"\n{kind} slab temporal errors 4/8/16 steps (n=128): {errors}, orders {observed}")
    assert min(observed) >= 0.9


def mixed_case():
    """Left Dirichlet, top prescribed inflow, right convection, uniform source."""
    mesh = rectangle_mesh(1.0, 0.5, 8, 4)
    left = {int(i): 320.0 for i in mesh.boundary["left"]}
    data = dict(conductivity=K, heat_source=30.0, outward_flux={"top": -20.0},
                convection={"right": (H, AMBIENT)})
    return mesh, left, data


def test_t3_long_time_limit_matches_steady_heat_on_the_same_operators():
    mesh, left, data = mixed_case()
    steady = solve_steady_heat(mesh, dirichlet=left, **data)
    times = np.r_[0.0, np.cumsum(np.full(8, 100.0))]
    transient = solve_transient_heat(
        mesh, volumetric_heat_capacity=C, time_s=times,
        initial_temperature_k=np.full(mesh.num_nodes, 320.0), dirichlet=left, **data)
    rise = max(np.max(abs(steady.temperature-320.0)), 1.0)
    error = np.max(abs(transient.temperature_k[-1]-steady.temperature))/rise
    rates = max(np.max(abs(steady.convective_outward)), np.max(abs(steady.reaction)),
                np.max(abs(steady.prescribed_outward_load)))
    convective = np.max(abs(transient.convective_outward_w_per_m[-1]-steady.convective_outward))/rates
    reaction = np.max(abs(transient.reaction_w_per_m[-1]-steady.reaction))/rates
    prescribed = np.max(abs(transient.prescribed_outward_load_w_per_m[-1]-steady.prescribed_outward_load))/rates
    print(f"\nlong-time limit vs steady: T {error:.3e}, C {convective:.3e}, reaction {reaction:.3e}, G {prescribed:.3e}")
    assert error <= 1e-8 and convective <= 1e-8 and reaction <= 1e-8 and prescribed <= 1e-8
    assert np.max(abs(transient.storage_rate_w_per_m[-1])) <= 1e-8*rates


def two_component_mesh():
    """Two disconnected strips with distinct initial offsets; each right edge convects."""
    a = rectangle_mesh(1.0, 0.5, 4, 2)
    b = rectangle_mesh(1.0, 0.5, 4, 2)
    shift = a.num_nodes
    nodes = np.concatenate([a.nodes, b.nodes+[3.0, 0.0]])
    triangles = np.concatenate([a.triangles, b.triangles+shift])
    edges = {"right_a": a.boundary_edges["right"], "right_b": b.boundary_edges["right"]+shift,
             "top_a": a.boundary_edges["top"], "left_b": b.boundary_edges["left"]+shift}
    return Mesh(nodes, triangles, {}, boundary_edges=edges), shift


def balance(result):
    """Largest per-step imbalance storage-(f+reaction-G-C), relative to the largest term."""
    worst = 0.0
    for i in range(len(result.time_s)-1):
        terms = [result.storage_rate_w_per_m[i].sum(), result.source_load_w_per_m[i+1].sum(),
                 result.reaction_w_per_m[i].sum(), result.prescribed_outward_load_w_per_m[i].sum(),
                 result.convective_outward_w_per_m[i].sum()]
        storage, source, reaction, prescribed, convective = terms
        worst = max(worst, abs(storage-(source+reaction-prescribed-convective))/max(map(abs, terms)))
    return worst


def line_matrices(mesh, edges, h, ambient, n):
    """Independent consistent line moments: H = h*l/6*[[2,1],[1,2]], B = h*ambient*l/2 per node."""
    robin, ambient_load = np.zeros((n, n)), np.zeros(n)
    for a, b in edges:
        length = np.linalg.norm(mesh.nodes[b]-mesh.nodes[a])
        robin[np.ix_([a, b], [a, b])] += h*length/6*np.array([[2., 1.], [1., 2.]])
        ambient_load[[a, b]] += h*ambient*length/2
    return robin, ambient_load


def test_t4_energy_balance_mixed_and_robin_only_components():
    mesh, left, data = mixed_case()
    times = np.array([0.0, 0.01, 0.03, 0.1, 0.25])
    result = solve_transient_heat(mesh, volumetric_heat_capacity=C, time_s=times,
                                  initial_temperature_k=np.full(mesh.num_nodes, 320.0),
                                  dirichlet=left, **data)
    mixed = balance(result)
    # Two Robin-only components: offsets 350 K and -20 K, with a left inflow on the second.
    mesh2, shift = two_component_mesh()
    initial = np.r_[np.full(shift, 350.0), np.full(mesh2.num_nodes-shift, -20.0)]
    result2 = solve_transient_heat(
        mesh2, conductivity=K, volumetric_heat_capacity=C, time_s=times, initial_temperature_k=initial,
        dirichlet={}, heat_source=3.0, outward_flux={"left_b": -7.0, "top_a": lambda p, normal: 2.0*p[:, 0]},
        convection={"right_a": (H, AMBIENT), "right_b": (lambda p, normal: 1.5+p[:, 1], 250.0)})
    robin_only = balance(result2)
    print(f"\nper-step balance: mixed {mixed:.3e}, two Robin-only components {robin_only:.3e}")
    assert mixed <= 1e-10 and robin_only <= 1e-10
    # Component balances separately, and C against independently assembled H T - B.
    n = mesh2.num_nodes
    nodes_a, nodes_b = np.arange(shift), np.arange(shift, n)
    robin_a, load_a = line_matrices(mesh2, mesh2.boundary_edges["right_a"], H, AMBIENT, n)
    for i in range(len(times)-1):
        t = result2.temperature_k[i+1]
        expected_a = (robin_a@t-load_a)[nodes_a]
        scale = max(np.max(abs(expected_a)), 1e-300)
        np.testing.assert_allclose(result2.convective_outward_w_per_m[i][nodes_a], expected_a,
                                   rtol=0, atol=1e-10*scale)
        for nodes in (nodes_a, nodes_b):
            terms = [a[i+(1 if a is result2.source_load_w_per_m else 0)][nodes].sum()
                     for a in (result2.storage_rate_w_per_m, result2.source_load_w_per_m,
                               result2.reaction_w_per_m, result2.prescribed_outward_load_w_per_m,
                               result2.convective_outward_w_per_m)]
            s, f, r, g, c = terms
            assert abs(s-(f+r-g-c)) <= 1e-10*max(map(abs, terms))
    assert not result2.reaction_w_per_m.any()
    assert result2.prescribed_outward_load_w_per_m.shape == result2.convective_outward_w_per_m.shape == (4, n)
    assert result2.temperature_k[-1][nodes_b].min() < 0    # finite negative K is not clamped


def test_contract_shapes_callbacks_and_refusals():
    mesh = rectangle_mesh(1.0, 0.5, 4, 2)
    base = dict(conductivity=K, volumetric_heat_capacity=C, time_s=[0.0, 0.1, 0.3],
                initial_temperature_k=np.full(mesh.num_nodes, INITIAL), dirichlet={})
    constant = solve_transient_heat(mesh, convection={"right": (H, AMBIENT)}, outward_flux={"top": 3.0}, **base)
    sampled = solve_transient_heat(
        mesh, convection={"right": (lambda p, normal: np.full(len(p), H), lambda p, normal: np.full(len(p), AMBIENT))},
        outward_flux={"top": lambda p, normal: 3.0*normal[:, 1]}, **base)
    for name in ("temperature_k", "convective_outward_w_per_m", "prescribed_outward_load_w_per_m", "residual_w_per_m"):
        np.testing.assert_allclose(getattr(sampled, name), getattr(constant, name), rtol=0,
                                   atol=1e-12*max(1.0, np.max(abs(getattr(constant, name)))))
        assert not getattr(constant, name).flags.writeable
    assert constant.convective_outward_w_per_m.shape == (2, mesh.num_nodes)
    assert constant.prescribed_outward_load_w_per_m.shape == (2, mesh.num_nodes)
    top = np.unique(mesh.boundary_edges["top"])
    assert np.all(constant.prescribed_outward_load_w_per_m[0][top] > 0)
    assert np.allclose(constant.prescribed_outward_load_w_per_m[0].sum(), 3.0*1.0)
    assert np.all(constant.convective_outward_w_per_m[:, np.unique(mesh.boundary_edges["right"])] > 0)
    # Time callbacks are refused up front, before any sampling.
    for bad in ({"right": (lambda p, normal, time_s: H, AMBIENT)}, {"right": (H, lambda p, n, t: AMBIENT)}):
        with pytest.raises(ValueError, match="time-independent"):
            solve_transient_heat(mesh, convection=bad, **base)
    with pytest.raises(ValueError, match="time-independent"):
        solve_transient_heat(mesh, outward_flux={"top": lambda points, time: 3.0}, **base)
    with pytest.raises(ValueError, match="must map"):
        solve_transient_heat(mesh, outward_flux=[("top", 3.0)], **base)
    # Steady-heat boundary validation is reused; failures are chained at index 0.
    for bad in ({"outward_flux": {"nowhere": 1.0}}, {"convection": {"right": (-1.0, AMBIENT)}},
                {"convection": {"right": H}}, {"outward_flux": {"top": lambda p, normal: 1.0}}):
        with pytest.raises(TransientHeatStepError) as caught:
            solve_transient_heat(mesh, **bad, **base)
        assert caught.value.time_index == 0 and isinstance(caught.value.__cause__, ValueError)
    # A natural edge with both ends prescribed is refused, as in steady heat.
    fixed = {int(i): INITIAL for i in mesh.boundary["right"]}
    with pytest.raises(TransientHeatStepError):
        solve_transient_heat(mesh, convection={"right": (H, AMBIENT)}, **(base | {"dirichlet": fixed}))


def test_t6_dirichlet_only_histories_unchanged(monkeypatch):
    environment, cases = dirichlet_cases.read()
    same_platform = environment == dirichlet_cases.environment()

    def forbidden(*args, **kwargs):
        raise AssertionError("boundary sampling ran without outward_flux or convection")
    monkeypatch.setattr(module, "scalar_boundary_samples", forbidden)
    monkeypatch.setattr(module, "scalar_boundary_system", forbidden)
    for name, case in dirichlet_cases.CASES.items():
        result = solve_transient_heat(**case())
        assert result.prescribed_outward_load_w_per_m is None and result.convective_outward_w_per_m is None
        now = dirichlet_cases.arrays(case)
        assert set(now) == set(cases[name])
        for field, array in now.items():
            saved = cases[name][field]
            if same_platform:
                assert array.tobytes() == saved.tobytes(), f"{name}.{field} changed bits"
            else:
                np.testing.assert_allclose(array, saved, rtol=1e-13, atol=1e-13*max(1.0, np.max(abs(saved))),
                                           err_msg=f"{name}.{field}")
    print(f"\nDirichlet-only fixture compared {'bit for bit' if same_platform else 'to roundoff'} "
          f"({platform.system()} {platform.machine()})")


# -- T5: JAX and PyTorch -----------------------------------------------------------

BACKENDS = ["jax", "torch"]
LIVE_MESH = rectangle_mesh(1.0, 0.5, 6, 3)
LIVE_TIMES = [0.0, 0.05, 0.1, 0.2]
LIVE_FIELDS = ("temperature_k", "heat_flux_w_m2", "source_load_w_per_m", "reaction_w_per_m",
               "residual_w_per_m", "storage_rate_w_per_m", "heat_content_j_per_m",
               "quadratic_functional_jk_per_m", "dirichlet_temperatures_k",
               "prescribed_outward_load_w_per_m", "convective_outward_w_per_m")


def _library(name):
    if name == "jax":
        jax = pytest.importorskip("jax")
        jax.config.update("jax_enable_x64", True)
        return jax
    return pytest.importorskip("torch")


def _numbers(a):
    return a.detach().numpy() if hasattr(a, "detach") else np.asarray(a)


def _live(name, values):
    lib = _library(name)
    if name == "jax":
        return [lib.numpy.asarray(v, dtype=lib.numpy.float64) for v in values]
    return [lib.tensor(v, dtype=lib.float64, requires_grad=True) for v in values]


def _gradient(name, objective, values):
    lib = _library(name)
    if name == "jax":
        return [float(g) for g in lib.grad(lambda v: objective(*v))(_live("jax", values))]
    leaves = _live("torch", values)
    objective(*leaves).backward()
    return [float(x.grad) for x in leaves]


def _central(objective, values, rel=1e-6):
    out = []
    for i, v in enumerate(values):
        step = rel*max(1.0, abs(v))
        up, down = list(values), list(values)
        up[i] += step
        down[i] -= step
        out.append((float(objective(*up))-float(objective(*down)))/(2*step))
    return out


def _live_run(h, ambient, g, k):
    """Right convection (h, ambient), top outward flux g, conductivity k; left ramp."""
    left = {int(i): (lambda s: 320.0+10.0*min(s/0.1, 1.0)) for i in LIVE_MESH.boundary["left"]}
    return solve_transient_heat(
        LIVE_MESH, conductivity=k, volumetric_heat_capacity=C, time_s=LIVE_TIMES,
        initial_temperature_k=np.full(LIVE_MESH.num_nodes, 320.0), dirichlet=left, heat_source=12.0,
        outward_flux={"top": g}, convection={"right": (h, ambient)})


LIVE_VALUES = (H, AMBIENT, -15.0, K)


@pytest.mark.parametrize("name", BACKENDS)
def test_t5_live_histories_match_numpy(name):
    reference = _live_run(*LIVE_VALUES)
    live = _live_run(*_live(name, LIVE_VALUES))
    for field in LIVE_FIELDS:
        expected = getattr(reference, field)
        assert type(getattr(live, field)).__module__.split(".")[0] in ("jax", "jaxlib", "torch")
        np.testing.assert_allclose(_numbers(getattr(live, field)), expected, rtol=1e-12,
                                   atol=1e-12*max(1.0, np.max(abs(expected))), err_msg=field)


@pytest.mark.parametrize("name", BACKENDS)
def test_t5_derivatives_in_h_ambient_flux_match_central_differences(name):
    def objective(*v):
        r = _live_run(*v)
        return (r.temperature_k[-1]**2).mean()+r.convective_outward_w_per_m[-1].sum()*1e-2
    got = _gradient(name, objective, LIVE_VALUES)
    want = _central(objective, LIVE_VALUES)
    print(f"\n{name} derivatives d/d(h, ambient, g, k): {got} vs central {want}")
    np.testing.assert_allclose(got, want, rtol=1e-6, atol=1e-9)
