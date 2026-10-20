# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Independent public-API acceptance using stdlib unittest and NumPy."""
import dataclasses
import json
import math
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

import galerkin.transient_heat as engine
from galerkin.mesh import Mesh
from transient_heat_independent_oracle import (
    ALGEBRA_GATE, C_SI, K_SI, Elements, constant_source, disjoint_squares,
    mode_truth, moving_affine, orders, pde_gates, sine, sine_source, small_be, square,
)


def mesh_of(x, cells):
    return Mesh(np.array(x, copy=True), np.array(cells, copy=True), boundary={})


def solve(x, cells, times, initial, bc=None, source=0.0, **options):
    return engine.solve_transient_heat(
        mesh_of(x, cells), conductivity=options.pop("conductivity", K_SI),
        volumetric_heat_capacity=options.pop("volumetric_heat_capacity", C_SI),
        time_s=times, initial_temperature_k=initial,
        dirichlet={} if bc is None else bc, heat_source=source, **options)


def affine_bc(x, fixed, start=0.0, shift=0.0):
    return {int(i): (lambda t, xx=x[i:i+1].copy():
                    float(moving_affine(xx, t-start)[0]+shift)) for i in fixed}


def require_close(got, expected, scale, label, limit=ALGEBRA_GATE):
    a, b = np.asarray(got), np.asarray(expected)
    if a.shape != b.shape or not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
        raise AssertionError(label+" shape/nonfinite")
    error = float(np.max(np.abs(a-b))) if a.size else 0.0
    if error > limit*float(scale):
        raise AssertionError(label+" normalized error="+repr(error/float(scale)))


def components(cells, count):
    parent = list(range(count))
    def root(i):
        while parent[i] != i:
            i = parent[i]
        return i
    for tri in cells:
        a = root(int(tri[0]))
        for node in tri[1:]:
            parent[root(int(node))] = a
    groups = {}
    for i in range(count):
        groups.setdefault(root(i), []).append(i)
    return list(groups.values())


def audit(result, element, source, check_load=True):
    """Truth uses only copied geometry, original polynomial tensors and fields."""
    ts, states = result.time_s, result.temperature_k
    fixed = np.asarray(result.dirichlet_node_ids)
    free = np.setdiff1d(np.arange(len(element.xy)), fixed)
    for j, (t, state) in enumerate(zip(ts, states)):
        require_close(result.heat_flux_w_m2[j], element.flux(state),
                      max(1.0, element.k*max(np.ptp(state), 1.0)), "flux")
        require_close(np.asarray(result.heat_content_j_per_m[j]),
                      np.asarray(np.sum(element.mass(state))),
                      max(1.0, element.c*np.sum(element.area)*max(np.max(np.abs(state)), 1)),
                      "H linear content")
        require_close(np.asarray(result.quadratic_functional_jk_per_m[j]),
                      np.asarray(state@element.mass(state)/2),
                      max(1.0, abs(state@element.mass(state)/2)), "V quadratic")
        if check_load:
            expected = element.load(source, t, 8)
            require_close(result.source_load_w_per_m[j], expected,
                          max(1, np.sum(np.abs(expected))), "independent source load")
    for j, dt in enumerate(np.diff(ts)):
        load = element.load(source, ts[j+1], 8) if check_load else result.source_load_w_per_m[j+1]
        d = element.diagnostics(states[j], states[j+1], load, dt, fixed)
        scale = max(1.0, np.sum(np.abs(load))+np.sum(np.abs(d["storage"]))
                    +np.sum(np.abs(d["reaction"])))
        require_close(result.storage_rate_w_per_m[j], d["storage"], scale, "storage")
        require_close(result.residual_w_per_m[j], d["residual"], scale, "original residual")
        require_close(result.reaction_w_per_m[j], d["reaction"], scale, "reaction")
        require_close(d["residual"][free], np.zeros(len(free)), scale, "free residual")
        require_close(np.asarray(d["heat_balance"]), np.asarray(0.0), scale, "heat balance")
        for ids in components(element.cells, len(element.xy)):
            require_close(np.asarray(np.sum(d["storage"][ids]-load[ids]-d["reaction"][ids])),
                          np.asarray(0.0), scale, "component heat balance")
        state = states[j+1]
        workscale = max(1.0, scale*max(np.max(np.abs(state)), 1.0),
                        abs(state@element.stiffness(state)))
        require_close(np.asarray(d["quadratic_identity"]), np.asarray(0.0),
                      workscale, "quadratic identity")
        # Stable direct V difference is independently audited too.
        delta = state-states[j]
        stable = (delta@element.mass(state+states[j])/(2*dt)
                  +delta@element.mass(delta)/(2*dt)
                  +state@element.stiffness(state)-state@(load+d["reaction"]))
        require_close(np.asarray(stable), np.asarray(0.0), workscale, "stable V identity")


def step_error(case, action, index, time, cause_type=None):
    with case.assertRaises(engine.TransientHeatStepError) as caught:
        action()
    error = caught.exception
    case.assertEqual(error.time_index, index)
    case.assertEqual(error.time_s, float(time))
    case.assertIsNotNone(error.__cause__)
    if cause_type is not None:
        case.assertIsInstance(error.__cause__, cause_type)
    return error


class TestTransientHeatIndependentCore(unittest.TestCase):
    def test_uniform_signed_disconnected_and_component_content(self):
        times = np.array([0, .03, .1, .4, 1.0])
        for separate in (False, True):
            x, cells, fixed = disjoint_squares(3) if separate else square(3)
            element = Elements(x, cells)
            initial = np.full(len(x), 300.0)
            if separate:
                initial[len(x)//2:] = 310
            for q in (8.0, -1600.0):
                with self.subTest(disconnected=separate, source=q):
                    r = solve(x, cells, times, initial, source=q)
                    exact = initial[None, :]+q*times[:, None]/C_SI
                    require_close(r.temperature_k, exact, max(1, abs(q)/C_SI), "uniform")
                    require_close(r.heat_flux_w_m2, np.zeros_like(r.heat_flux_w_m2),
                                  2.5, "uniform zero flux")
                    audit(r, element, constant_source(q))
                    self.assertEqual(r.dirichlet_temperatures_k.shape, (len(times), 0))
                    self.assertEqual(r.reaction_w_per_m.shape, (len(times)-1, len(x)))
                    if q < 0:
                        self.assertLess(float(np.min(r.temperature_k)), 0)

    def test_moving_affine_n8_irregular_time_and_nonzero_start(self):
        x, cells, fixed = square(8)
        for start in (0.0, 2.0):
            ts = start+np.array([0, .03, .1, .4, 1.0])
            initial = moving_affine(x, 0)
            r = solve(x, cells, ts, initial, affine_bc(x, fixed, start), 3*C_SI)
            expected = np.array([moving_affine(x, t-start) for t in ts])
            require_close(r.temperature_k, expected, 5.0, "moving affine")
            audit(r, Elements(x, cells), constant_source(3*C_SI))

    def test_actual_initial_mismatch_old_fixed_mass_R2(self):
        x, cells, fixed = square(3)
        e = Elements(x, cells)
        m, k = e.dense()
        initial = np.zeros(len(x))
        initial[1] = 16*np.finfo(float).eps
        ts = np.array([0.0, 1e-12])
        bc = {int(i): 0.0 for i in fixed}
        r = solve(x, cells, ts, initial, bc)
        self.assertTrue(np.array_equal(r.temperature_k[0], initial))
        self.assertEqual(r.dirichlet_temperatures_k[0, 1], 0)
        load = [np.zeros(len(x)), np.zeros(len(x))]
        expected = small_be(m, k, ts, initial, fixed, lambda t: np.zeros(len(fixed)), load)
        exact_storage = e.mass((expected[1]-initial)/ts[1])
        require_close(r.storage_rate_w_per_m[0], exact_storage, 1.0, "R2 actual old M_FC")
        self.assertGreater(float(np.max(np.abs(exact_storage))), 1e-6)
        audit(r, e, constant_source(0))
        invalid = initial.copy()
        invalid[1] = 64*np.finfo(float).eps
        step_error(self, lambda: solve(x, cells, ts, invalid, bc), 0, 0)

    def test_discrete_source_endpoint_R6_and_retained_f0(self):
        x, cells, _ = square(3)
        times = np.array([0, .03, .1, .4, 1.0])
        q = {float(times[0]): C_SI*2.0}
        q.update({float(times[j]): C_SI*(2+7*(times[j]+times[j-1]))
                  for j in range(1, len(times))})
        source = lambda p, t: np.full(len(p), q[float(t)])
        r = solve(x, cells, times, np.full(len(x), 300.0), source=source)
        exact = 300+2*times+7*times**2
        require_close(r.temperature_k, np.repeat(exact[:, None], len(x), axis=1),
                      9.0, "discrete endpoint R6")
        audit(r, Elements(x, cells), source)
        self.assertGreater(float(np.sum(r.source_load_w_per_m[0])), 0)

    def test_shift_SI_frame_and_node_cell_order(self):
        x, cells, fixed = square(3)
        times = np.array([0, .03, .1, .4, 1.0])
        initial = moving_affine(x, 0)
        original = solve(x, cells, times, initial, affine_bc(x, fixed), 3*C_SI)
        shifted = solve(x, cells, times, initial+17, affine_bc(x, fixed, shift=17), 3*C_SI)
        for field in ("heat_flux_w_m2", "storage_rate_w_per_m", "reaction_w_per_m"):
            require_close(getattr(shifted, field), getattr(original, field), 20.0, "shift "+field)
        require_close(shifted.heat_content_j_per_m-original.heat_content_j_per_m,
                      np.full(len(times), 17*C_SI), 17*C_SI, "H shift")
        xm = (x*1000)*1e-3
        si = solve(xm, cells, times, initial, affine_bc(xm, fixed), 3*C_SI)
        require_close(si.temperature_k, original.temperature_k, 5, "explicit SI", limit=1e-9)
        angle = .41
        rotation = np.array([[math.cos(angle), -math.sin(angle)],
                             [math.sin(angle), math.cos(angle)]])
        moved = x@rotation.T+np.array([3.0, -2.0])
        bc = {int(i): (lambda t, ii=int(i): float(initial[ii]+3*t)) for i in fixed}
        frame = solve(moved, cells, times, initial, bc, 3*C_SI)
        require_close(frame.temperature_k, original.temperature_k, 5.0, "frame T")
        require_close(frame.heat_flux_w_m2, original.heat_flux_w_m2@rotation.T, 12.5, "frame q")
        permutation = np.arange(len(x))[::-1]
        inverse = np.argsort(permutation)
        reordered_cells = inverse[cells[::-1]][:, [1, 2, 0]]
        rb = {int(inverse[i]): v for i, v in bc.items()}
        rr = solve(x[permutation], reordered_cells, times, initial[permutation], rb, 3*C_SI)
        require_close(rr.temperature_k[:, inverse], original.temperature_k, 5.0, "node order")
        require_close(rr.heat_flux_w_m2[:, ::-1], original.heat_flux_w_m2, 12.5, "cell order")

    def test_n8_temporal_eigenmode_fixed_gates(self):
        e, m, k, fixed, lam, phi = mode_truth(8)
        errors = []
        for count in (8, 16, 32, 64):
            ts = np.linspace(0, 1/lam, count+1)
            r = solve(e.xy, e.cells, ts, 300+phi, {int(i): 300.0 for i in fixed})
            product = np.r_[1.0, np.cumprod(1/(1+lam*np.diff(ts)))]
            expected = 300+product[:, None]*phi
            require_close(r.temperature_k, expected, 1.0, "n8 BE product")
            delta = r.temperature_k[-1]-300-math.exp(-1)*phi
            errors.append(math.sqrt(float(delta@m@delta)))
            audit(r, e, constant_source(0))
        rate = orders(errors)
        print(json.dumps(dict(gate="independent_n8_temporal", errors=errors, orders=rate.tolist())))
        self.assertTrue(np.all(rate[-2:] >= .9) and np.all(rate[-2:] <= 1.1))
        ts = np.array([0, .03, .1, .4, 1.0])/lam
        r = solve(e.xy, e.cells, ts, 300+phi, {int(i): 300.0 for i in fixed})
        product = np.r_[1.0, np.cumprod(1/(1+lam*np.diff(ts)))]
        require_close(r.temperature_k, 300+product[:, None]*phi, 1, "irregular dt mode")


class TestTransientHeatIndependentPDE(unittest.TestCase):
    def test_four_mesh_PDE_all_times_quadrature_and_time_separation(self):
        primary, quad10 = [], []
        companion = None
        for n in (8, 16, 32, 64):
            x, cells, fixed = square(n)
            e = Elements(x, cells)
            initial, _ = sine(x, 0)
            ts = np.arange(257)/256
            r = solve(x, cells, ts, initial, {int(i): 300.0 for i in fixed}, sine_source)
            row8, row10 = [], []
            for time in (.25, .5, 1.0):
                index = int(round(time*256))
                row8.append(e.errors(r.temperature_k[index], time, 8))
                row10.append(e.errors(r.temperature_k[index], time, 10))
                # Independently audit nonzero source on observation steps.
                sub = SimpleNamespace(**{name: getattr(r, name)[index-1:index+1]
                                         for name in ("time_s", "temperature_k", "heat_flux_w_m2",
                                                      "source_load_w_per_m", "heat_content_j_per_m",
                                                      "quadratic_functional_jk_per_m")})
                for name in ("storage_rate_w_per_m", "residual_w_per_m", "reaction_w_per_m"):
                    setattr(sub, name, getattr(r, name)[index-1:index])
                sub.dirichlet_node_ids = r.dirichlet_node_ids
                audit(sub, e, sine_source)
            primary.append(row8)
            quad10.append(row10)
            if n == 64:
                half = solve(x, cells, np.arange(513)/512, initial,
                             {int(i): 300.0 for i in fixed}, sine_source)
                companion = [e.errors(half.temperature_k[int(round(t*512))], t, 8)
                             for t in (.25, .5, 1.0)]
        print(json.dumps(dict(gate="independent_PDE", primary=primary,
                              quadrature10=quad10, companion=companion)))
        rate = pde_gates(primary, companion, quad10)
        print(json.dumps(dict(gate="independent_PDE_orders", orders=rate.tolist())))


class TestTransientHeatIndependentContract(unittest.TestCase):
    def test_shapes_owned_copy_initial_and_lifetime(self):
        x, cells, fixed = square(3)
        ts = np.array([0.0, .1, .3])
        initial = moving_affine(x, 0)
        mesh = mesh_of(x, cells)
        calls = {}
        boundary_calls = {}
        def boundary_value(node, t):
            key = (node, t)
            boundary_calls[key] = boundary_calls.get(key, 0)+1
            return float(initial[node]+3*t)
        conditions = {int(i): (lambda t, node=int(i): boundary_value(node, t))
                      for i in fixed}
        def source(p, t):
            calls[t] = calls.get(t, 0)+len(p)
            return np.full(len(p), 3*C_SI)
        r = engine.solve_transient_heat(mesh, conductivity=K_SI,
            volumetric_heat_capacity=C_SI, time_s=ts, initial_temperature_k=initial,
            dirichlet=conditions, heat_source=source)
        shapes = dict(time_s=(3,), temperature_k=(3, len(x)),
            heat_flux_w_m2=(3, len(cells), 2), source_load_w_per_m=(3, len(x)),
            reaction_w_per_m=(2, len(x)), residual_w_per_m=(2, len(x)),
            storage_rate_w_per_m=(2, len(x)), heat_content_j_per_m=(3,),
            quadratic_functional_jk_per_m=(3,), dirichlet_node_ids=(len(fixed),),
            dirichlet_temperatures_k=(3, len(fixed)), nodes_m=x.shape, triangles=cells.shape)
        saved = {}
        for name, shape in shapes.items():
            value = getattr(r, name)
            self.assertEqual(value.shape, shape)
            self.assertFalse(value.flags.writeable)
            self.assertTrue(np.all(np.isfinite(value)))
            saved[name] = value.copy()
            for caller in (mesh.nodes, mesh.triangles, ts, initial):
                self.assertFalse(np.shares_memory(value, caller))
            if value.size:
                with self.assertRaises(ValueError):
                    value.flat[0] = 0
        self.assertEqual(set(calls), set(ts))
        self.assertEqual(len(set(calls.values())), 1)
        self.assertEqual(boundary_calls, {(int(i), float(t)): 1 for i in fixed for t in ts})
        self.assertEqual(r.conductivity_w_mk, K_SI)
        self.assertEqual(r.volumetric_heat_capacity_j_m3k, C_SI)
        mesh.nodes[:] += 100
        mesh.triangles[:] = 0
        ts[:] += 20
        initial[:] = -700
        for name, old in saved.items():
            self.assertTrue(np.array_equal(getattr(r, name), old))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            r.time_s = np.array([4.0])

    def test_sampling_geometry_capture_and_no_partial_failure(self):
        x, cells, fixed = square(3)
        mesh = mesh_of(x, cells)
        ts = np.array([0.0, .1, .3])
        initial = np.full(len(x), 300.0)
        seen = []
        class Sentinel(RuntimeError):
            pass
        def source(p, t):
            seen.append(t)
            if t == .3:
                raise Sentinel("independent stage failure")
            return np.zeros(len(p))
        error = step_error(self, lambda: engine.solve_transient_heat(
            mesh, conductivity=K_SI, volumetric_heat_capacity=C_SI,
            time_s=ts, initial_temperature_k=initial, dirichlet={},
            heat_source=source), 2, .3, Sentinel)
        self.assertIn("index 2", str(error))
        self.assertEqual(set(seen), {0.0, .1, .3})
        self.assertTrue(np.array_equal(initial, np.full(len(x), 300.0)))
        self.assertTrue(np.array_equal(ts, np.array([0.0, .1, .3])))
        # Controlled mutation after capture is a diagnostic, not concurrency support.
        def mutate(p, t):
            if t == 0:
                mesh.nodes[:] = 900
                initial[:] = -10
                ts[:] = 99
            return np.zeros(len(p))
        r = engine.solve_transient_heat(mesh_of(x, cells), conductivity=K_SI,
            volumetric_heat_capacity=C_SI, time_s=np.array([0.0, .1, .3]),
            initial_temperature_k=np.full(len(x), 300.0), dirichlet={},
            heat_source=lambda p, t: np.zeros(len(p)))
        require_close(r.temperature_k, np.full((3, len(x)), 300.0), 1, "captured baseline")
        # Actual caller objects used by the second solve, captured before callback.
        mesh = mesh_of(x, cells)
        ts = np.array([0.0, .1, .3])
        initial = np.full(len(x), 300.0)
        r = engine.solve_transient_heat(mesh, conductivity=K_SI,
            volumetric_heat_capacity=C_SI, time_s=ts, initial_temperature_k=initial,
            dirichlet={}, heat_source=mutate)
        self.assertTrue(np.array_equal(r.nodes_m, x))
        self.assertTrue(np.array_equal(r.time_s, [0.0, .1, .3]))
        require_close(r.temperature_k, np.full((3, len(x)), 300.0), 1, "captured before callbacks")

    def test_finite_negative_K_and_initial_rate_alignment(self):
        x, cells, fixed = square(3)
        r = solve(x, cells, [0, .1], np.full(len(x), -5.0),
                  {int(i): -5.0 for i in fixed})
        require_close(r.temperature_k, np.full((2, len(x)), -5), 1, "negative mathematical K")
        self.assertEqual(r.reaction_w_per_m.shape, (1, len(x)))
        self.assertEqual(r.source_load_w_per_m.shape, (2, len(x)))

    def test_invalid_inputs_R5_and_used_node_boundary(self):
        x, cells, fixed = square(3)
        base = dict(conductivity=K_SI, volumetric_heat_capacity=C_SI,
                    time_s=[0, .1], initial_temperature_k=np.zeros(len(x)), dirichlet={})
        changes = [
            ("conductivity", True), ("conductivity", 0), ("conductivity", -1),
            ("conductivity", complex(2, 0)), ("conductivity", np.inf),
            ("volumetric_heat_capacity", False), ("volumetric_heat_capacity", 0),
            ("time_s", [0, True]), ("time_s", [0, 0]), ("time_s", [.1, 0]),
            ("time_s", [-1, 0]), ("time_s", [0, np.nan]), ("time_s", [[0, .1]]),
            ("time_s", [0]), ("initial_temperature_k", [0]*(len(x)-1)),
            ("initial_temperature_k", [True]+[0]*(len(x)-1)),
            ("initial_temperature_k", np.full(len(x), np.inf)),
            ("initial_temperature_k", np.zeros(len(x), dtype=complex)),
            ("dirichlet", {True: 0}), ("dirichlet", {1.5: 0}),
            ("dirichlet", {5: 0}), ("dirichlet", {-1: 0}), ("dirichlet", []),
            ("heat_source", True), ("heat_source", complex(1, 0)),
            ("heat_source", np.nan)]
        for key, value in changes:
            with self.subTest(key=key, value=repr(value)):
                kw = dict(base)
                kw[key] = value
                with self.assertRaises(ValueError):
                    engine.solve_transient_heat(mesh_of(x, cells), **kw)
        mesh = mesh_of(x, cells)
        mesh.nodes = np.vstack((mesh.nodes, [4.0, 4.0]))
        kw = dict(base, initial_temperature_k=np.zeros(len(x)+1))
        with self.assertRaises(ValueError):
            engine.solve_transient_heat(mesh, **kw)
        mesh = mesh_of(x, cells)
        mesh.triangles = mesh.triangles.astype(float)
        mesh.triangles[0, 0] = .5
        with self.assertRaises(ValueError):
            engine.solve_transient_heat(mesh, **base)

    def test_bad_callbacks_f0_shapes_bool_nonfinite_and_boundary(self):
        x, cells, fixed = square(3)
        initial = np.zeros(len(x))
        callbacks = [lambda p, t: 0.0, lambda p, t: np.zeros((len(p), 1)),
                     lambda p, t: np.full(len(p), True),
                     lambda p, t: np.full(len(p), np.nan),
                     lambda p, t: np.zeros(len(p), dtype=complex),
                     lambda p, t: [True]+[0]*(len(p)-1)]
        for callback in callbacks:
            with self.subTest(callback=repr(callback)):
                step_error(self, lambda: solve(x, cells, [0, .1], initial,
                                               source=callback), 0, 0)
        def late_bad(p, t):
            return np.zeros(len(p)) if t == 0 else np.full(len(p), np.inf)
        step_error(self, lambda: solve(x, cells, [0, .1], initial, source=late_bad), 1, .1)
        for value in ([0.0], True, np.nan, complex(0, 0)):
            step_error(self, lambda v=value: solve(x, cells, [0, .1], initial,
                       {0: lambda t: v}), 0, 0)
        for index in (0, 1):
            def bc(t, idx=index):
                if t == [0, .1][idx]:
                    raise RuntimeError("boundary sentinel")
                return 0.0
            step_error(self, lambda: solve(x, cells, [0, .1], initial, {0: bc}),
                       index, [0, .1][index], RuntimeError)

    def test_derived_overflow_is_rejected_not_partial_history_R5(self):
        x, cells, _ = square(3)
        for kwargs in (
            dict(time_s=[0.0, np.nextafter(0.0, 1.0)]),
            dict(conductivity=np.finfo(float).max),
            dict(initial_temperature_k=np.full(len(x), 1e200)),
            dict(heat_source=np.finfo(float).max),
        ):
            with self.subTest(kwargs=list(kwargs)):
                base = dict(conductivity=K_SI, volumetric_heat_capacity=C_SI,
                            time_s=[0, 10.0], initial_temperature_k=np.zeros(len(x)),
                            dirichlet={})
                base.update(kwargs)
                with self.assertRaises(ValueError):
                    engine.solve_transient_heat(mesh_of(x, cells), **base)


class TestTransientHeatIndependentWrongRuntime(unittest.TestCase):
    def test_actual_runtime_lumping_detected_by_n8_product(self):
        e, m, k, fixed, lam, phi = mode_truth(8)
        ts = np.linspace(0, 1/lam, 9)
        original = engine.assemble_mass
        def lump(*args, **kwargs):
            matrix = original(*args, **kwargs).tocsr(copy=True)
            row = np.asarray(matrix.sum(axis=1)).ravel()
            matrix.data[:] = 0
            matrix.setdiag(row)
            return matrix
        with patch.object(engine, "assemble_mass", lump):
            r = solve(e.xy, e.cells, ts, 300+phi, {int(i): 300.0 for i in fixed})
        product = np.r_[1.0, np.cumprod(1/(1+lam*np.diff(ts)))]
        with self.assertRaisesRegex(AssertionError, "wrong mass"):
            require_close(r.temperature_k, 300+product[:, None]*phi, 1, "wrong mass")

    def test_real_solve_wrong_endpoint_inputs_R6(self):
        x, cells, _ = square(3)
        times = np.array([0, .03, .1, .4, 1.0])
        values = np.r_[C_SI*2, C_SI*(2+7*(times[1:]+times[:-1]))]
        expected = np.repeat((300+2*times+7*times**2)[:, None], len(x), axis=1)
        for variant in ("left", "average", "frozen"):
            altered = values.copy()
            if variant == "left":
                altered[1:] = values[:-1]
            elif variant == "average":
                altered[1:] = (values[1:]+values[:-1])/2
            else:
                altered[:] = values[0]
            lookup = dict(zip(times.tolist(), altered.tolist()))
            r = solve(x, cells, times, np.full(len(x), 300.0),
                      source=lambda p, t: np.full(len(p), lookup[t]))
            with self.assertRaisesRegex(AssertionError, "wrong endpoint"):
                require_close(r.temperature_k, expected, 9.0, "wrong endpoint "+variant)

    def test_real_result_wrong_storage_sign_HV_and_projection(self):
        x, cells, fixed = square(3)
        ts = np.array([0, .03, .1, .4, 1.0])
        r = solve(x, cells, ts, moving_affine(x, 0), affine_bc(x, fixed), 3*C_SI)
        fields = {f.name: getattr(r, f.name) for f in dataclasses.fields(r)}
        mutations = [
            ("storage_rate_w_per_m", np.zeros_like(r.storage_rate_w_per_m), "storage"),
            ("residual_w_per_m", np.array([Elements(x, cells).stiffness(t)-f
             for t, f in zip(r.temperature_k[1:], r.source_load_w_per_m[1:])]), "original residual"),
            ("reaction_w_per_m", -r.reaction_w_per_m, "reaction"),
            ("heat_content_j_per_m", r.quadratic_functional_jk_per_m, "H linear"),
        ]
        for name, value, witness in mutations:
            fake = SimpleNamespace(**dict(fields, **{name: value}))
            with self.assertRaisesRegex(AssertionError, witness):
                audit(fake, Elements(x, cells), constant_source(3*C_SI))
        # R2 actor uses actual solve but silently replaces accepted initial C by d0.
        init = np.zeros(len(x))
        init[1] = 16*np.finfo(float).eps
        time = np.array([0, 1e-12])
        element = Elements(x, cells)
        mm, kk = element.dense()
        expected = small_be(mm, kk, time, init, fixed,
                            lambda t: np.zeros(len(fixed)),
                            [np.zeros(len(x)), np.zeros(len(x))])
        expected_storage = element.mass((expected[1]-init)/time[1])
        projected = init.copy()
        projected[fixed] = 0
        bad = solve(x, cells, time, projected, {int(i): 0.0 for i in fixed})
        with self.assertRaisesRegex(AssertionError, "R2 projection"):
            require_close(bad.storage_rate_w_per_m[0], expected_storage,
                          1.0, "R2 projection")
        # Omitted-old/new/both FC matrix actors are independent wrong alternatives,
        # not runtime injections; preserve this distinction in reports.
        e = Elements(x, cells)
        m, k = e.dense()
        loads = [e.load(constant_source(3*C_SI), t) for t in ts]
        for variant in ("omit_old_fc", "omit_new_fc", "omit_both_fc"):
            wrong = small_be(m, k, ts, moving_affine(x, 0), fixed,
                             lambda t: moving_affine(x[fixed], t), loads, variant)
            with self.assertRaisesRegex(AssertionError, "wrong MFC"):
                require_close(wrong, r.temperature_k, 5.0, "wrong MFC "+variant)

    def test_runtime_omitted_MFC_actors_fail_original_system(self):
        x, cells, fixed = square(3)
        e = Elements(x, cells)
        m, k = e.dense()
        times = np.array([0.0, .03])
        initial = moving_affine(x, 0)
        free = np.setdiff1d(np.arange(len(x)), fixed)
        loads = [e.load(constant_source(3*C_SI), t) for t in times]
        for variant in ("omit_old_fc", "omit_new_fc", "omit_both_fc"):
            altered = small_be(m, k, times, initial, fixed,
                              lambda t: moving_affine(x[fixed], t), loads, variant)
            class WrongSolve:
                def solve(self, rhs):
                    return altered[1, free]-initial[0]
            with patch.object(engine, "splu", lambda a: WrongSolve()):
                error = step_error(self, lambda: solve(
                    x, cells, times, initial, affine_bc(x, fixed), 3*C_SI), 1, .03)
            self.assertIn("normalized free residual", str(error.__cause__))
