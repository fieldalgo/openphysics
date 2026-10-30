# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent network implementation and file-reader checks; no shipped dependency."""
import importlib.metadata as metadata
import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import LineNetwork, rlgc_network


@pytest.fixture(scope='module')
def skrf():
    return require_tool('scikit-rf')


def test_distributed_circuit_and_mixed_mode(skrf):
    f = np.array([1e3, 1e6, 1e9, 10e9])
    frequency = skrf.Frequency.from_f(f, unit='Hz')
    # Identical RLGC inputs, independent algorithms. Inputs do not come from FEM.
    r = np.array([2, 3, 10, 30.])
    g = np.array([1e-6, 1e-5, .002, .02])
    clock = Stopwatch()
    with clock('openphysics'):
        ours = rlgc_network(f, R=r[:, None, None], L=[[400e-9]],
                            G=g[:, None, None], C=[[100e-12]], length=.13)
        pair = rlgc_network(f, R=[[4, .4], [.4, 4]], L=np.array([[300, 60], [60, 300]])*1e-9,
                             G=[[.004, -.001], [-.001, .004]],
                             C=np.array([[120, -30], [-30, 120]])*1e-12, length=.2)
        mixed = pair.mixed_mode()
    with clock('reference'):
        line = skrf.media.DistributedCircuit(frequency, R=r, L=400e-9, G=g, C=100e-12,
                                             z0_port=50).line(.13, unit='m')
        # Independently computed even/odd modes, with scikit-rf's physical
        # differential/common normalization (100 and 25 ohms).
        odd = skrf.media.DistributedCircuit(frequency, R=7.2, L=480e-9, G=.0025,
                                            C=75e-12, z0_port=100).line(.2, unit='m')
        even = skrf.media.DistributedCircuit(frequency, R=2.2, L=180e-9, G=.006,
                                             C=180e-12, z0_port=25).line(.2, unit='m')
        # Independent generalized mixed-mode conversion on the same single-ended S.
        converted = skrf.Network(frequency=frequency, s=pair.s.copy(), z0=50)
        converted.se2gmm(p=2)
    differences = [np.max(abs(ours.s-line.s)),
                   np.max(abs(mixed.s[:, :2, :2]-odd.s)),
                   np.max(abs(mixed.s[:, 2:, 2:]-even.s)),
                   np.max(abs(mixed.s-converted.s))]
    record = make_record(case='rlgc-line-network', physics='uniform multiconductor transmission line',
        api='sipi.rlgc_network', discretization='matrix exponential and scattering doubling',
        tool='scikit-rf', tool_discretization='DistributedCircuit and se2gmm',
        matched=['RLGC samples, frequencies, length, 50 ohm single-ended references',
                 'near+/near-/far+/far-; d_near,d_far,c_near,c_far mixed order',
                 '100 ohm differential, 25 ohm common reference'], not_matched=[],
        observables=[observable(name, '1', 'max absolute difference', value, 1e-10)
                     for name, value in zip(('single-ended S', 'differential S', 'common S',
                                             'mixed conversion'), differences)],
        analytical_acceptance='tests/sipi/test_line_network.py; no FEM/material accuracy inferred',
        stopwatch=clock)
    record['openphysics']['distribution'] = 'sipi'
    record['openphysics']['version'] = metadata.version('sipi')
    emit(record)
    assert max(differences) <= 1e-10


@pytest.mark.parametrize('ports', [2, 4])
def test_touchstone_independent_reader_detects_transposition(tmp_path, skrf, ports):
    # Deliberately nonreciprocal numbers detect an accidental transpose that
    # reciprocal line fixtures cannot reveal. This is file format evidence only.
    values = np.arange(1, 1+2*ports*ports).reshape(2, ports, ports)/100
    s = values+1j*values[::-1]
    z = np.arange(ports)*10+40
    net = LineNetwork([1e6, 2e9], s, z, tuple(f'p{i+1}' for i in range(ports)))
    path = tmp_path/f'line.s{ports}p'
    path.write_text(net.touchstone(), encoding='utf-8')
    loaded = skrf.Network(str(path))
    np.testing.assert_allclose(loaded.s, net.s, atol=1e-14)
    np.testing.assert_array_equal(loaded.f, net.frequency)
    np.testing.assert_allclose(loaded.z0, np.broadcast_to(z, (2, ports)), atol=1e-14)
