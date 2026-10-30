# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Terminated networks: independent circuits, modal references, strict inputs."""
import importlib.metadata as metadata

import numpy as np
import pytest

from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import LineNetwork, rlgc_network
from sipi.termination import terminate_network, loaded_crosstalk


def line(f=(0, 1e6, 1e9)):
    return rlgc_network(f, R=[[10]], L=[[400e-9]], G=[[0]], C=[[100e-12]], length=1)


def pair():
    return rlgc_network([1e3, 1e6, 1e9, 5e9],
                        R=[[4, .4], [.4, 4]], L=np.array([[300, 60], [60, 300]])*1e-9,
                        G=[[.004, -.001], [-.001, .004]],
                        C=np.array([[120, -30], [-30, 120]])*1e-12, length=.2)


def test_dc_voltage_divider_and_power():
    out = terminate_network(line(), source_voltages={'near:1': 1},
                            terminations={'near:1': 50, 'far:1': 100})
    np.testing.assert_allclose(out.voltage[0], [110/160, 100/160], rtol=1e-10)
    np.testing.assert_allclose(out.current[0], [1/160, -1/160], rtol=1e-10)
    np.testing.assert_allclose(out.network_power[0], 10/160**2, rtol=1e-10)
    np.testing.assert_allclose(out.source_power, out.network_power+out.termination_power,
                               rtol=1e-10, atol=1e-15)
    assert np.max(out.kvl_residual) < 1e-10
    assert np.max(out.wave_residual) < 1e-10
    assert np.all(out.network_power >= 0)


def test_complex_source_load_against_independent_abcd():
    f = np.array([1e3, 1e6, 1e9, 5e9])
    r, l, g, c, length = 7., 320e-9, .003, 115e-12, .23
    net = rlgc_network(f, R=[[r]], L=[[l]], G=[[g]], C=[[c]], length=length)
    source = np.array([1+.2j, .5-1j, 2j, -1])
    zs, zl = 35+17j, np.array([70-10j, 80+4j, 90-13j, 110+33j])
    out = terminate_network(net, source_voltages={'near:1': source},
                            terminations={'near:1': zs, 'far:1': zl})
    z, y = r+2j*np.pi*f*l, g+2j*np.pi*f*c
    gamma, zc = np.sqrt(z*y), np.sqrt(z/y)
    a = d = np.cosh(gamma*length)
    b, cc = zc*np.sinh(gamma*length), np.sinh(gamma*length)/zc
    vf = source/(a+b/zl+zs*(cc+d/zl))
    expected_v = np.column_stack(((a+b/zl)*vf, vf))
    expected_i = np.column_stack(((cc+d/zl)*vf, -vf/zl))
    np.testing.assert_allclose(out.voltage, expected_v, rtol=1e-10, atol=1e-14)
    np.testing.assert_allclose(out.current, expected_i, rtol=1e-10, atol=1e-16)
    np.testing.assert_allclose(out.source_power, out.network_power+out.termination_power,
                               rtol=1e-10, atol=1e-15)


def test_short_ideal_source_and_zero_excitation():
    net = line()
    out = terminate_network(net, source_voltages={'near:1': 1},
                            terminations={'near:1': 0, 'far:1': 0})
    np.testing.assert_allclose(out.voltage, np.tile([1, 0], (3, 1)), rtol=1e-10, atol=1e-13)
    np.testing.assert_allclose(out.current[0], [.1, -.1], rtol=1e-10)
    np.testing.assert_allclose(out.termination_power, 0, atol=0)
    zero = terminate_network(net, source_voltages={'near:1': 0})
    np.testing.assert_array_equal(zero.voltage, 0)
    np.testing.assert_array_equal(zero.current, 0)
    np.testing.assert_array_equal(zero.kvl_residual, 0)


def test_matched_crosstalk_against_even_odd_abcd():
    net = pair()
    result = loaded_crosstalk(net, aggressor='near:1', near_victim='near:2', far_victim='far:2')
    modes = []
    for sign in (1, -1):
        f = net.frequency
        z = (4+sign*.4)+2j*np.pi*f*(300+sign*60)*1e-9
        y = (.004-sign*.001)+2j*np.pi*f*(120-sign*30)*1e-12
        propagation, zc = np.sqrt(z*y), np.sqrt(z/y)
        a = np.cosh(propagation*.2)
        b, c = zc*np.sinh(propagation*.2), np.sinh(propagation*.2)/zc
        denom = 2*a+b/50+c*50
        modes.append(((b/50-c*50)/denom, 2/denom))
    np.testing.assert_allclose(result.next_ratio, (modes[0][0]-modes[1][0])/2, rtol=0, atol=1e-10)
    np.testing.assert_allclose(result.fext_ratio, (modes[0][1]-modes[1][1])/2, rtol=0, atol=1e-10)
    np.testing.assert_allclose(result.next_ratio, net.s[:, 1, 0], rtol=0, atol=1e-13)
    np.testing.assert_allclose(result.fext_ratio, net.s[:, 3, 0], rtol=0, atol=1e-13)
    assert result.response.basis == 'single-ended'


def test_nonmatched_crosstalk_changes_and_short_victim():
    net = pair()
    result = loaded_crosstalk(net, aggressor='near:1', near_victim='near:2', far_victim='far:2',
                              terminations={'near:1': 25+10j, 'near:2': 0, 'far:2': 100})
    np.testing.assert_allclose(result.next_ratio, 0, atol=1e-13)
    assert np.max(abs(result.fext_ratio-net.s[:, 3, 0])) > 1e-3
    reference = np.sqrt(50)*result.response.a[:, 0]
    np.testing.assert_allclose(result.fext_ratio, result.response.voltage[:, 3]/reference)


def test_mixed_basis_and_unequal_references():
    mixed = pair().mixed_mode()
    out = terminate_network(mixed, source_voltages={'d_near': 1})
    np.testing.assert_array_equal(out.terminations[0], [100, 100, 25, 25])
    assert out.basis == 'mixed-mode'
    s = np.full((2, 3, 3), .1+.02j)
    net = LineNetwork([1, 2], s, [25, 50, 100], ('a', 'n', 'f'))
    xt = loaded_crosstalk(net, aggressor='a', near_victim='n', far_victim='f')
    np.testing.assert_allclose(xt.next_ratio, s[:, 1, 0]*np.sqrt(2))
    np.testing.assert_allclose(xt.fext_ratio, s[:, 2, 0]*2)


@pytest.mark.parametrize('ports', [2, 4])
def test_independent_impedance_circuit(ports):
    skrf = require_tool('scikit-rf')
    # Nonreciprocal passive data exposes mistaken transpose/order; no geometry
    # accuracy is inferred from these synthetic matrices.
    rng = np.random.default_rng(771+ports)
    s = (rng.normal(size=(3, ports, ports))+1j*rng.normal(size=(3, ports, ports)))/(5*ports)
    refs = np.arange(ports)*17+35
    names = tuple(f'p{i}' for i in range(ports))
    net = LineNetwork([1e3, 1e6, 1e9], s, refs, names)
    vs = rng.normal(size=(3, ports))+1j*rng.normal(size=(3, ports))
    zt = np.arange(ports)[None, :]*11+np.array([20+3j, 30-5j, 40+17j])[:, None]
    clock = Stopwatch()
    with clock('openphysics'):
        out = terminate_network(net, source_voltages=dict(zip(names, vs.T)),
                                terminations=dict(zip(names, zt.T)))
    with clock('reference'):
        z = skrf.network.s2z(s, z0=refs, s_def='power')
        current = np.linalg.solve(z+np.array([np.diag(row) for row in zt]), vs[..., None])[..., 0]
        voltage = (z @ current[..., None])[..., 0]
    errors = [float(np.max(abs(a-b))/np.max(abs(b)))
              for a, b in ((out.voltage, voltage), (out.current, current))]
    record = make_record(case=f'terminated-{ports}-port-network', physics='loaded linear network',
        api='sipi.termination.terminate_network', discretization='power-wave feedback solve',
        tool='scikit-rf', tool_discretization='s2z and independent impedance circuit solve',
        matched=['synthetic nonreciprocal S, positive real unequal references',
                 'complex Thevenin sources and passive frequency-dependent impedances',
                 'peak phasors; current into every network port'], not_matched=[],
        observables=[observable(name, unit, 'max relative infinity-norm difference', value, 1e-10)
                     for name, unit, value in zip(('voltage', 'current'), ('1', '1'), errors)],
        analytical_acceptance='test_termination.py: DC, complex-load ABCD and coupled modal crosstalk',
        stopwatch=clock)
    record['openphysics']['distribution'] = 'sipi'
    record['openphysics']['version'] = metadata.version('sipi')
    emit(record)
    assert max(errors) <= 1e-10
    np.testing.assert_allclose(out.source_power, out.network_power+out.termination_power, rtol=1e-10)


def test_input_and_result_snapshots():
    net = line()
    values = np.array([1, 2, 3.])
    out = terminate_network(net, source_voltages={'near:1': values})
    values[:] = 9
    assert out.source_voltages[0, 0] == 1
    net.s.setflags(write=True)
    net.s[:] = 9
    assert not np.array_equal(out.network.s, net.s)
    for value in (out.a, out.b, out.voltage, out.current, out.source_voltages, out.terminations,
                  out.frequency, out.condition_number, out.kvl_residual, out.wave_residual,
                  out.network_power, out.source_power, out.termination_power):
        assert not value.flags.writeable
    result = loaded_crosstalk(pair(), aggressor='near:1', near_victim='near:2', far_victim='far:2')
    assert not result.next_ratio.flags.writeable and not result.fext_ratio.flags.writeable


@pytest.mark.parametrize('values', [{}, [], {'wrong': 1}, {0: 1}, {'near:1': True},
    {'near:1': [1, True, 2]}, {'near:1': '1'}, {'near:1': [1, 2]},
    {'near:1': [[1], [2], [3]]}, {'near:1': float('inf')}, {'near:1': complex(1, float('nan'))}])
def test_bad_sources(values):
    with pytest.raises(ValueError):
        terminate_network(line(), source_voltages=values)


@pytest.mark.parametrize('values', [[], {'wrong': 1}, {'near:1': True}, {'near:1': -1},
    {'near:1': -1+3j}, {'near:1': [10, -1, 10]}, {'near:1': '50'}, {'near:1': [1, 2]},
    {'near:1': float('inf')}, {'near:1': float('nan')}])
def test_bad_terminations(values):
    with pytest.raises(ValueError):
        terminate_network(line(), source_voltages={'near:1': 1}, terminations=values)


@pytest.mark.parametrize('s', [-np.eye(2), np.diag([-1+1e-14, 0])])
def test_singular_and_ill_conditioned(s):
    net = LineNetwork([0], s[None], 50, ('a', 'b'))
    with pytest.raises(ValueError, match='ill-conditioned'):
        terminate_network(net, source_voltages={'a': 1}, terminations={'a': 0, 'b': 0})


@pytest.mark.parametrize('ports', [('near:1', 'near:1', 'far:1'), ('bad', 'near:2', 'far:2'),
                                  (False, 'near:2', 'far:2'), ([], 'near:2', 'far:2')])
def test_invalid_crosstalk_ports(ports):
    with pytest.raises(ValueError, match='distinct'):
        loaded_crosstalk(pair(), aggressor=ports[0], near_victim=ports[1], far_victim=ports[2])


def test_vanishing_incident_voltage():
    with pytest.raises(ValueError, match='too small'):
        loaded_crosstalk(pair(), aggressor='near:1', near_victim='near:2', far_victim='far:2',
                         terminations={'near:1': 1e20})


def test_wrong_network_type():
    with pytest.raises(TypeError):
        terminate_network(None, source_voltages={'a': 1})
    with pytest.raises(TypeError):
        loaded_crosstalk(None, aggressor='a', near_victim='b', far_victim='c')


def test_active_external_network_power_is_not_clipped():
    net = LineNetwork([0, 1e6], [[[2]], [[2]]], 50, ('p',))
    out = terminate_network(net, source_voltages={'p': 1})
    np.testing.assert_allclose(out.network_power, [-.015, -.0075], rtol=1e-10)
    np.testing.assert_allclose(out.source_power, out.network_power+out.termination_power, rtol=1e-10)


def test_reactive_load_dissipates_no_average_power():
    net = rlgc_network([1e6, 1e9], R=[[0]], L=[[400e-9]], G=[[0]], C=[[100e-12]], length=.1)
    out = terminate_network(net, source_voltages={'near:1': 1},
                            terminations={'near:1': 0, 'far:1': 20j})
    np.testing.assert_allclose(out.termination_power, 0, rtol=0, atol=1e-16)
    np.testing.assert_allclose(out.network_power, 0, rtol=0, atol=1e-16)


def test_power_overflow_is_reported():
    net = LineNetwork([1e6], [[[0]]], 50, ('p',))
    out = terminate_network(net, source_voltages={'p': 1e200})
    assert np.all(np.isfinite(out.voltage))
    with pytest.raises(ValueError, match='power overflow'):
        _ = out.network_power
