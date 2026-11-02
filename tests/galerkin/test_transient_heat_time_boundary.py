# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Time-dependent outward flux and convection in solve_transient_heat (pre-registered gates).

U1 periodic ambient temperature T_a(t) = T_m + A sin(wt) on the convective face of
an insulated slab, compared over one period after t >= 6 L^2/alpha (here the
twelfth period, from 11 L^2/alpha) with the closed-form periodic steady state of
refsol.transient_heat_robin.PeriodicAmbientSlab: the complex amplitude (amplitude
and phase) at x = 0 and x = L is read from a one-period DFT of the history. Spatial
order >= 1.8 over n=8/16/32 with 256 steps per period against the backward-Euler
time-discrete amplitude (which isolates the spatial error); temporal order >= 0.9
over 16/32/64 steps per period on n=128 against the analytic amplitude; the finest
run (n=32, 512 steps per period) within 3e-3 of A against the analytic amplitude.
U2 ramped outward flux g(t) = g0 t/tau against the Duhamel series
RampedFluxSlab: spatial order >= 1.8 (n=8/16/32, 4000 steps to 0.2 s), temporal
order >= 0.9 (n=128, 4/8/16 steps), finest relative L2 error <= 2e-3 of the exact
surface rise |T(L, 0.2 s) - T0|. U3 callbacks returning constants give results bit-
identical to constant values, and H is assembled once unless h varies. U4 per-step
balance storage = f + reaction - G_n - C_n <= 1e-10 of the largest term with every
boundary value varying in time, and C_n, G_n equal the independently assembled line
moments of h, T_a and g sampled at the END of each step. U5 JAX/PyTorch histories
equal NumPy for time-dependent g and T_a (skipped without the libraries), and a
time-dependent h is refused there. U6 refusal of other callback signatures and of
wrong shapes, NaN and negative h at any step, with the step index in the message.
Measured values are printed; thresholds are fixed and never loosened here.
"""
import dataclasses

import numpy as np
import pytest

import galerkin.transient_heat as module
from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.transient_heat import TransientHeatStepError, solve_transient_heat
from refsol.transient_heat_robin import PeriodicAmbientSlab, RampedFluxSlab

L, K, C, H = 1.0, 2.5, 4.0, 5.0
DIFFUSION_TIME = L**2*C/K                     # L^2/alpha = 1.6 s
# U1: one period per diffusion time; twelve periods, the last one compared.
TM, A = 300.0, 20.0
PERIOD = DIFFUSION_TIME
OMEGA = 2*np.pi/PERIOD
PERIODS = 12
PERIODIC = PeriodicAmbientSlab(L, K, C, H, TM, A, OMEGA)
# U2: g(t) = g0 t/tau (inflow growing to -100 W/m^2 at 0.2 s).
G0, TAU, T0, T_END = -100.0, 0.2, 300.0, 0.2
RAMP = RampedFluxSlab(L, K, C, G0/TAU, T0)
RISE = abs(RAMP.temperature(np.array([L]), T_END).temperature_k[0]-T0)


def ambient(t):
    return TM+A*np.sin(OMEGA*t)


def strip(n):
    """A one-cell-high strip of n squares: left (x=0) insulated, right (x=L) natural."""
    return rectangle_mesh(L, L/n, n, 1)


def periodic_run(n, per_period):
    mesh = strip(n)
    times = np.linspace(0.0, PERIODS*PERIOD, PERIODS*per_period+1)
    result = solve_transient_heat(
        mesh, conductivity=K, volumetric_heat_capacity=C, time_s=times,
        initial_temperature_k=np.full(mesh.num_nodes, TM), dirichlet={},
        convection={"right": (H, ambient)})
    return mesh, result


def fitted_amplitudes(mesh, result, per_period):
    """{x: complex amplitude} at x=0 and x=L from a one-period DFT of the last period.

    T - T_m = Re(Theta) sin(wt) + Im(Theta) cos(wt); equispaced samples over a
    full period recover both coefficients exactly for a pure harmonic.
    """
    last = slice(len(result.time_s)-per_period, len(result.time_s))
    t = result.time_s[last]
    out = {}
    for x in (0.0, L):
        nodes = np.flatnonzero(abs(mesh.nodes[:, 0]-x) < 1e-12)
        signal = result.temperature_k[last][:, nodes].mean(axis=1)-TM
        out[x] = (2/per_period)*(np.sum(signal*np.sin(OMEGA*t))+1j*np.sum(signal*np.cos(OMEGA*t)))
    return out


def amplitude_error(mesh, result, per_period, time_step=None):
    """max over x=0, L of |Theta_fem - Theta_ref| / A; Theta_ref analytic or time-discrete."""
    fitted = fitted_amplitudes(mesh, result, per_period)
    return max(abs(fitted[x]-PERIODIC.complex_amplitude(np.array([x]), time_step)[0])/A
               for x in fitted)


def orders(errors):
    return [np.log2(errors[i]/errors[i+1]) for i in range(len(errors)-1)]


def test_u1_spatial_order_against_the_time_discrete_amplitude():
    per_period = 256
    errors, analytic = [], []
    for n in (8, 16, 32):
        mesh, result = periodic_run(n, per_period)
        errors.append(amplitude_error(mesh, result, per_period, PERIOD/per_period))
        analytic.append(amplitude_error(mesh, result, per_period))
    observed = orders(errors)
    print(f"\nU1 spatial errors n=8/16/32 (256 steps/period) vs BE discrete amplitude: {errors}, "
          f"orders {observed}; vs analytic amplitude {analytic}")
    assert min(observed) >= 1.8


def test_u1_temporal_order_on_fine_mesh():
    errors = []
    for per_period in (16, 32, 64):
        mesh, result = periodic_run(128, per_period)
        errors.append(amplitude_error(mesh, result, per_period))
    observed = orders(errors)
    print(f"\nU1 temporal errors 16/32/64 steps/period (n=128) vs analytic amplitude: {errors}, orders {observed}")
    assert min(observed) >= 0.9


def test_u1_finest_amplitude_and_phase():
    per_period = 512
    mesh, result = periodic_run(32, per_period)
    fitted = fitted_amplitudes(mesh, result, per_period)
    worst = 0.0
    for x, theta in fitted.items():
        exact = PERIODIC.complex_amplitude(np.array([x]))[0]
        amplitude = abs(abs(theta)-abs(exact))/A
        phase = abs(np.angle(theta/exact))
        print(f"\nU1 finest (n=32, 512 steps/period) x={x}: |Theta| {abs(theta):.6f} vs {abs(exact):.6f} "
              f"(relative {amplitude:.3e}), phase {np.angle(theta):.6f} vs {np.angle(exact):.6f} rad "
              f"(difference {phase:.3e})")
        worst = max(worst, abs(theta-exact)/A)
    print(f"U1 finest complex amplitude error / A: {worst:.3e}")
    assert worst <= 3e-3
    # The compared period starts after 11 diffusion times; the transient has decayed.
    assert result.time_s[-1-per_period] >= 6*DIFFUSION_TIME


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


def ramp_run(n, steps):
    mesh = strip(n)
    result = solve_transient_heat(
        mesh, conductivity=K, volumetric_heat_capacity=C, time_s=np.linspace(0.0, T_END, steps+1),
        initial_temperature_k=np.full(mesh.num_nodes, T0), dirichlet={},
        outward_flux={"right": lambda t: G0*t/TAU})
    return l2_error(mesh, result.temperature_k[-1],
                    lambda x: RAMP.temperature(x, T_END).temperature_k, RISE)


def test_u2_ramped_flux_spatial_convergence_with_tiny_steps():
    errors = [ramp_run(n, 4000) for n in (8, 16, 32)]
    observed = orders(errors)
    print(f"\nU2 ramp spatial errors n=8/16/32 (dt=5e-5 s, rise scale {RISE:.4f} K): {errors}, orders {observed}")
    assert min(observed) >= 1.8
    assert errors[-1] <= 2e-3


def test_u2_ramped_flux_temporal_convergence_on_fine_mesh():
    errors = [ramp_run(128, steps) for steps in (4, 8, 16)]
    observed = orders(errors)
    print(f"\nU2 ramp temporal errors 4/8/16 steps (n=128): {errors}, orders {observed}")
    assert min(observed) >= 0.9


# -- U3: constant-data callbacks are bit-identical, H assembled once -----------------

def mixed_case():
    """Left Dirichlet ramp, top prescribed inflow, right convection, uniform source."""
    mesh = rectangle_mesh(1.0, 0.5, 8, 4)
    left = {int(i): (lambda s: 320.0+10.0*min(s/0.1, 1.0)) for i in mesh.boundary["left"]}
    return mesh, dict(conductivity=K, volumetric_heat_capacity=C, heat_source=30.0,
                      time_s=np.array([0.0, 0.01, 0.03, 0.1, 0.25]),
                      initial_temperature_k=np.full(mesh.num_nodes, 320.0), dirichlet=left)


def arrays(result):
    return {f.name: getattr(result, f.name) for f in dataclasses.fields(result)
            if isinstance(getattr(result, f.name), np.ndarray)}


def assert_bits_equal(a, b):
    first, second = arrays(a), arrays(b)
    assert set(first) == set(second)
    for name in first:
        assert first[name].shape == second[name].shape
        assert first[name].tobytes() == second[name].tobytes(), f"{name} changed bits"


def count_calls(monkeypatch, name):
    original, calls = getattr(module, name), []

    def spy(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(module, name, spy)
    return calls


def test_u3_constant_callbacks_are_bit_identical_to_constants(monkeypatch):
    mesh, base = mixed_case()
    g, ambient_k = -20.0, 300.0
    constant = solve_transient_heat(mesh, outward_flux={"top": g}, convection={"right": (H, ambient_k)}, **base)
    systems, conversions = count_calls(monkeypatch, "scalar_boundary_system"), count_calls(monkeypatch, "_scipy")
    timed_scalars = solve_transient_heat(
        mesh, outward_flux={"top": lambda t: g},
        convection={"right": (lambda t: H, lambda t: ambient_k)}, **base)
    assert_bits_equal(timed_scalars, constant)
    nt = len(base["time_s"])
    assert len(systems) == nt and len(conversions) == nt      # h varies in form: H per step
    systems.clear(), conversions.clear()
    timed_fields = solve_transient_heat(
        mesh, outward_flux={"top": lambda p, n, t: np.full(len(p), g)},
        convection={"right": (H, lambda p, n, t: np.full(len(p), ambient_k))}, **base)
    assert_bits_equal(timed_fields, constant)
    assert len(systems) == nt and len(conversions) == 1       # static h: H assembled once
    systems.clear(), conversions.clear()
    static = solve_transient_heat(
        mesh, outward_flux={"top": lambda p, n: np.full(len(p), g)},
        convection={"right": (lambda p, n: np.full(len(p), H), ambient_k)}, **base)
    assert_bits_equal(static, constant)
    assert len(systems) == 1 and len(conversions) == 1        # static data: sampled once
    print("\nU3: callback(t) and callback(points, normals, t) constants bit-identical to constants; "
          f"boundary systems assembled {nt} (timed) / 1 (static) times")


# -- U4: energy balance and end-of-step sampling ----------------------------------

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


def balance(result, nodes=None):
    """Largest per-step imbalance storage-(f+reaction-G-C) on ``nodes``, relative to the largest term."""
    nodes = slice(None) if nodes is None else nodes
    worst = 0.0
    for i in range(len(result.time_s)-1):
        terms = [result.storage_rate_w_per_m[i][nodes].sum(), result.source_load_w_per_m[i+1][nodes].sum(),
                 result.reaction_w_per_m[i][nodes].sum(), result.prescribed_outward_load_w_per_m[i][nodes].sum(),
                 result.convective_outward_w_per_m[i][nodes].sum()]
        storage, source, reaction, prescribed, convective = terms
        worst = max(worst, abs(storage-(source+reaction-prescribed-convective))/max(map(abs, terms)))
    return worst


def line_moments(mesh, edges, h, ambient_k, g, n):
    """Independent consistent line moments: H = h*l/6*[[2,1],[1,2]], B = h*T_a*l/2, G = g*l/2 per node."""
    robin, ambient_load, flux_load = np.zeros((n, n)), np.zeros(n), np.zeros(n)
    for a, b in edges:
        length = np.linalg.norm(mesh.nodes[b]-mesh.nodes[a])
        robin[np.ix_([a, b], [a, b])] += h*length/6*np.array([[2., 1.], [1., 2.]])
        ambient_load[[a, b]] += h*ambient_k*length/2
        flux_load[[a, b]] += g*length/2
    return robin, ambient_load, flux_load


def test_u4_energy_balance_and_end_of_step_sampling_with_time_varying_data():
    mesh, base = mixed_case()
    result = solve_transient_heat(
        mesh, outward_flux={"top": lambda t: -20.0*(1.0+2.0*t), "bottom": lambda p, n, t: 3.0*t*p[:, 0]},
        convection={"right": (lambda t: H*(1.0+t), lambda p, n, t: 300.0+40.0*np.sin(5.0*t)+p[:, 1])}, **base)
    mixed = balance(result)
    mesh2, shift = two_component_mesh()
    n = mesh2.num_nodes
    times = np.array([0.0, 0.01, 0.03, 0.1, 0.25])
    initial = np.r_[np.full(shift, 350.0), np.full(n-shift, -20.0)]
    h_of = lambda t: H*(1.0+3.0*t)
    ambient_of = lambda t: 300.0-80.0*t
    g_of = lambda t: -7.0*(1.0-t)
    result2 = solve_transient_heat(
        mesh2, conductivity=K, volumetric_heat_capacity=C, time_s=times, initial_temperature_k=initial,
        dirichlet={}, heat_source=3.0, outward_flux={"left_b": g_of, "top_a": lambda p, normal, t: 2.0*p[:, 0]*t},
        convection={"right_a": (h_of, ambient_of), "right_b": (lambda p, normal, t: 1.5+p[:, 1]+t, 250.0)})
    nodes_a, nodes_b = np.arange(shift), np.arange(shift, n)
    robin_only = max(balance(result2, nodes_a), balance(result2, nodes_b))
    print(f"\nU4 per-step balance with time-varying g, h, T_a: mixed {mixed:.3e}, two Robin-only components {robin_only:.3e}")
    assert mixed <= 1e-10 and robin_only <= 1e-10
    # C_n and G_n use h, T_a and g sampled at the END of the step, t_{n+1}.
    for i in range(len(times)-1):
        now = times[i+1]
        robin, ambient_load, _ = line_moments(mesh2, mesh2.boundary_edges["right_a"], h_of(now), ambient_of(now), 0.0, n)
        _, _, flux_load = line_moments(mesh2, mesh2.boundary_edges["left_b"], 0.0, 0.0, g_of(now), n)
        expected_c = (robin@result2.temperature_k[i+1]-ambient_load)[nodes_a]
        np.testing.assert_allclose(result2.convective_outward_w_per_m[i][nodes_a], expected_c, rtol=0,
                                   atol=1e-10*max(np.max(abs(expected_c)), 1e-300))
        left_b = np.unique(mesh2.boundary_edges["left_b"])
        np.testing.assert_allclose(result2.prescribed_outward_load_w_per_m[i][left_b], flux_load[left_b],
                                   rtol=1e-12, atol=0)
    assert result2.prescribed_outward_load_w_per_m.shape == result2.convective_outward_w_per_m.shape == (4, n)
    assert not result2.reaction_w_per_m.any()
    # Sampling instant, directly: G of step n integrates g(t_{n+1}); the t0 value is not used.
    mesh3 = rectangle_mesh(1.0, 0.5, 4, 2)
    probe = solve_transient_heat(
        mesh3, conductivity=K, volumetric_heat_capacity=C, time_s=[0.0, 0.1, 0.3, 0.35],
        initial_temperature_k=np.full(mesh3.num_nodes, 300.0), dirichlet={}, outward_flux={"top": lambda t: t})
    np.testing.assert_allclose(probe.prescribed_outward_load_w_per_m.sum(axis=1), [0.1, 0.3, 0.35], rtol=1e-12)


# -- U6: refusals -----------------------------------------------------------------

def test_u6_signature_shape_nan_and_negative_h_refusals():
    mesh = rectangle_mesh(1.0, 0.5, 4, 2)
    base = dict(conductivity=K, volumetric_heat_capacity=C, time_s=[0.0, 0.1, 0.3, 0.6],
                initial_temperature_k=np.full(mesh.num_nodes, 350.0), dirichlet={})
    # Signatures: refused before any sampling, as plain ValueError.
    for bad in (lambda: 1.0, lambda a, b, c, d: 1.0, lambda *args: 1.0, lambda p, time: 1.0,
                lambda p, time_s: 1.0, lambda p, n, t, *more: np.ones(len(p))):
        with pytest.raises(ValueError, match="forms") as caught:
            solve_transient_heat(mesh, outward_flux={"top": bad}, **base)
        assert not isinstance(caught.value, TransientHeatStepError)
    with pytest.raises(ValueError, match="convection\\['right'\\]"):
        solve_transient_heat(mesh, convection={"right": (H, lambda: 300.0)}, **base)
    # Shapes and values at time index 0 (validation sampling).
    for bad, match in (({"top": lambda t: np.ones(2)}, "finite real scalar"),
                       ({"top": lambda t: True}, "boolean"),
                       ({"top": lambda p, n, t: np.ones(3)}, "exactly shape"),
                       ({"top": lambda p, n, t: 1.0}, "exactly shape")):
        with pytest.raises(TransientHeatStepError) as caught:
            solve_transient_heat(mesh, outward_flux=bad, **base)
        assert caught.value.time_index == 0
        assert match in str(caught.value.__cause__)
    # NaN, infinity and negative h at a later step: the step index is in the message.
    cases = (dict(outward_flux={"top": lambda t: np.nan if t > 0.2 else 1.0}),
             dict(outward_flux={"top": lambda p, n, t: np.where(t > 0.5, np.inf, 1.0)*np.ones(len(p))}),
             dict(convection={"right": (lambda t: H if t < 0.3 else -1.0, 300.0)}),
             dict(convection={"right": (H, lambda t: 300.0 if t < 0.6 else np.nan)}))
    for case, index in zip(cases, (2, 3, 2, 3)):
        with pytest.raises(TransientHeatStepError, match=f"time index {index}") as caught:
            solve_transient_heat(mesh, **case, **base)
        assert caught.value.time_index == index and caught.value.time_s == base["time_s"][index]
        assert isinstance(caught.value.__cause__, ValueError)
    # Result shapes are unchanged by time dependence.
    result = solve_transient_heat(mesh, outward_flux={"top": lambda t: 1.0+t},
                                  convection={"right": (lambda t: H+t, lambda t: 300.0-t)}, **base)
    assert result.prescribed_outward_load_w_per_m.shape == result.convective_outward_w_per_m.shape == (3, mesh.num_nodes)
    assert result.temperature_k.shape == (4, mesh.num_nodes)
    assert not result.prescribed_outward_load_w_per_m.flags.writeable


# -- U5: JAX and PyTorch ----------------------------------------------------------

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


def _live_run(h, amplitude, g_rate):
    """Static h; ambient T_m + amplitude*sin(5t) and top flux g_rate*t vary in time; left ramp."""
    left = {int(i): (lambda s: 320.0+10.0*min(s/0.1, 1.0)) for i in LIVE_MESH.boundary["left"]}
    sin = np.sin
    return solve_transient_heat(
        LIVE_MESH, conductivity=K, volumetric_heat_capacity=C, time_s=LIVE_TIMES,
        initial_temperature_k=np.full(LIVE_MESH.num_nodes, 320.0), dirichlet=left, heat_source=12.0,
        outward_flux={"top": lambda t: g_rate*t},
        convection={"right": (h, lambda t: 300.0+amplitude*sin(5.0*t))})


LIVE_VALUES = (H, 30.0, -150.0)


@pytest.mark.parametrize("name", BACKENDS)
def test_u5_live_histories_match_numpy_with_time_dependent_g_and_ambient(name):
    reference = _live_run(*LIVE_VALUES)
    live = _live_run(*_live(name, LIVE_VALUES))
    for field in LIVE_FIELDS:
        expected = getattr(reference, field)
        assert type(getattr(live, field)).__module__.split(".")[0] in ("jax", "jaxlib", "torch")
        np.testing.assert_allclose(_numbers(getattr(live, field)), expected, rtol=1e-12,
                                   atol=1e-12*max(1.0, np.max(abs(expected))), err_msg=field)


@pytest.mark.parametrize("name", BACKENDS)
def test_u5_derivatives_in_h_amplitude_and_flux_rate_match_central_differences(name):
    def objective(*v):
        r = _live_run(*v)
        return (r.temperature_k[-1]**2).mean()+r.convective_outward_w_per_m[-1].sum()*1e-2
    got = _gradient(name, objective, LIVE_VALUES)
    want = _central(objective, LIVE_VALUES)
    print(f"\n{name} derivatives d/d(h, amplitude, g_rate): {got} vs central {want}")
    np.testing.assert_allclose(got, want, rtol=1e-6, atol=1e-9)


@pytest.mark.parametrize("name", BACKENDS)
def test_u5_time_dependent_h_is_refused_with_live_inputs(name):
    (h,) = _live(name, [H])
    with pytest.raises(ValueError, match="not supported with JAX or PyTorch"):
        solve_transient_heat(
            LIVE_MESH, conductivity=K, volumetric_heat_capacity=C, time_s=LIVE_TIMES,
            initial_temperature_k=np.full(LIVE_MESH.num_nodes, 320.0), dirichlet={},
            convection={"right": (lambda t: h*(1.0+t), 300.0)})
