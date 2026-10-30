# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Telegrapher identities, port conventions and failure boundaries."""
import numpy as np
import pytest
from sipi import LineNetwork, rlgc_network, quasistatic_network, stripline

F = np.array([0, 1e3, 1e6, 1e9, 10e9])


def scalar(f=F, **changes):
    kw = dict(R=[[0]], L=[[250e-9]], G=[[0]], C=[[100e-12]], length=.037, z_ref=50)
    kw.update(changes)
    return rlgc_network(f, **kw)


def analytic(f, r, l, g, c, length, ref=50):
    # Independent scalar ABCD solution, suitable for moderate electrical length.
    z, y = r+2j*np.pi*f*l, g+2j*np.pi*f*c
    gamma = np.sqrt(z*y)
    zc = np.sqrt(z/y)
    a, b, cc = np.cosh(gamma*length), zc*np.sinh(gamma*length), np.sinh(gamma*length)/zc
    den = 2*a+b/ref+cc*ref
    reflection = (b/ref-cc*ref)/den
    transmission = 2/den
    out = np.zeros((len(f), 2, 2), complex)
    out[:, 0, 0] = out[:, 1, 1] = reflection
    out[:, 0, 1] = out[:, 1, 0] = transmission
    return out


def test_matched_phase_dc_and_zero_length():
    net = scalar()
    np.testing.assert_allclose(net.s[:, 0, 0], 0, atol=1e-10)
    np.testing.assert_allclose(net.s[:, 1, 0], np.exp(-2j*np.pi*F*.037*5e-9), atol=1e-10)
    zero = scalar(length=0, R=[[20]], G=[[.02]])
    np.testing.assert_allclose(zero.s, np.broadcast_to([[0, 1], [1, 0]], zero.s.shape), atol=1e-10)
    # DC series resistor with zero shunt G: Zseries=R*length.
    dc = scalar([0], R=[[20]], length=2)
    np.testing.assert_allclose(dc.s[0], [[40/140, 100/140], [100/140, 40/140]], atol=1e-10)


@pytest.mark.parametrize('r,g,length', [(0, 0, .2), (4, .004, .7), (200, .02, 1)])
def test_scalar_against_independent_abcd(r, g, length):
    f = F[1:]
    net = scalar(f, R=[[r]], G=[[g]], L=[[400e-9]], length=length)
    np.testing.assert_allclose(net.s, analytic(f, r, 400e-9, g, 100e-12, length), atol=1e-10, rtol=0)
    np.testing.assert_allclose(net.s, net.s.swapaxes(1, 2), atol=1e-10)
    assert np.max(np.linalg.svd(net.s, compute_uv=False)) <= 1+1e-10
    if r == g == 0:
        np.testing.assert_allclose(net.s.conj().swapaxes(1, 2)@net.s,
                                   np.broadcast_to(np.eye(2), net.s.shape), atol=1e-10)


def test_extreme_attenuation_does_not_overflow():
    # R/L = G/C, Zc=50, alpha=sqrt(RG)=40/m, alpha*l=4000.
    net = scalar(R=[[2000]], G=[[.8]], length=100)
    assert np.all(np.isfinite(net.s))
    np.testing.assert_allclose(net.s, 0, atol=1e-10)


def test_coupled_pair_modes_and_near_far_port_order():
    f = F[1:]
    l = np.array([[300, 60], [60, 300]])*1e-9
    c = np.array([[120, -30], [-30, 120]])*1e-12
    r = np.array([[4, .4], [.4, 4]])
    g = np.array([[.004, -.001], [-.001, .004]])
    line = rlgc_network(f, R=r, L=l, G=g, C=c, length=.2, names=('p', 'n'))
    assert line.port_names == ('near:p', 'near:n', 'far:p', 'far:n')
    mm = line.mixed_mode()
    # Odd differential and even common ABCD each use their original 50-ohm modal waves.
    odd = analytic(f, 3.6, 240e-9, .005, 150e-12, .2)
    even = analytic(f, 4.4, 360e-9, .003, 90e-12, .2)
    np.testing.assert_allclose(mm.s[:, :2, :2], odd, atol=1e-10, rtol=0)
    np.testing.assert_allclose(mm.s[:, 2:, 2:], even, atol=1e-10, rtol=0)
    np.testing.assert_allclose(mm.s[:, :2, 2:], 0, atol=1e-10)
    np.testing.assert_array_equal(mm.z_ref, [100, 100, 25, 25])
    u = np.array([[1, -1, 0, 0], [0, 0, 1, -1], [1, 1, 0, 0], [0, 0, 1, 1]])/np.sqrt(2)
    np.testing.assert_allclose(u.T@mm.s@u, line.s, atol=1e-10)
    with pytest.raises(ValueError, match='single-ended'):
        mm.touchstone()


def test_asymmetric_noncommuting_matrices_are_reciprocal_and_passive():
    c = np.array([[110, -30], [-30, 150]])*1e-12
    l = np.array([[300, 40], [40, 250]])*1e-9
    assert not np.allclose(l@c, c@l, rtol=1e-12, atol=1e-25)
    for r, g in [(np.zeros((2, 2)), np.zeros((2, 2))),
                 (np.array([[4, 1], [1, 8]]), np.array([[.004, -.001], [-.001, .002]]))]:
        net = rlgc_network(F, R=r, L=l, G=g, C=c, length=.7)
        np.testing.assert_allclose(net.s, net.s.swapaxes(1, 2), atol=1e-10)
        assert np.max(np.linalg.svd(net.s, compute_uv=False)) <= 1+1e-10
        if not np.any(r):
            np.testing.assert_allclose(net.s.conj().swapaxes(1, 2)@net.s,
                                       np.broadcast_to(np.eye(4), net.s.shape), atol=1e-10)


def test_quasistatic_bridge_preserves_dielectric_loss():
    p = stripline(width=.5e-3, plane_spacing=1e-3, eps_r=4, tan_delta=.02).analyze(
        edge_size=5e-6, far_size=.5e-3, grade=.2)
    net = quasistatic_network(p, F, length=.02, R=[[0]])
    expected = scalar(F[1:], L=p.L, C=p.C, G=np.array([p.G(f) for f in F[1:]]), length=.02)
    np.testing.assert_allclose(net.s[1:], expected.s, atol=1e-10)
    assert abs(net.s[-1, 1, 0]) < abs(net.s[1, 1, 0])
    # Conductor R must be an explicit modelling decision, never an implicit zero.
    with pytest.raises(TypeError):
        quasistatic_network(p, F, length=.02)


@pytest.mark.parametrize('kw', [dict(length=-1), dict(length=True), dict(z_ref=0),
    dict(z_ref=1j), dict(R=[[-1]]), dict(G=[[-1]]), dict(L=[[0]]), dict(C=[[-1]]),
    dict(R=[[True]]), dict(R=[[float('nan')]]), dict(R=[[1j]]), dict(R=[[1, 2], [0, 1]]),
    dict(C=[1]), dict(R=[[[1]], [[2]]]), dict(names=['bad\nname'])])
def test_invalid_controls_and_physical_matrices(kw):
    with pytest.raises(ValueError):
        scalar(**kw)


@pytest.mark.parametrize('f', [[], [1, 1], [2, 1], [-1], [True], [float('inf')], [[1]]])
def test_invalid_frequencies(f):
    with pytest.raises(ValueError):
        scalar(f)


def test_psd_validation_is_not_an_entrywise_sign_rule():
    # Positive diagonal entries do not establish passivity.
    with pytest.raises(ValueError, match='semidefinite'):
        rlgc_network(F, R=[[1, 2], [2, 1]], L=np.eye(2)*1e-7,
                     G=np.zeros((2, 2)), C=np.eye(2)*1e-10, length=.1)


def test_snapshot_and_touchstone_order():
    s = np.array([[[.1+.2j, .3+.4j], [.5+.6j, .7+.8j]]])
    net = LineNetwork([1e9], s, 50, ('in', 'out'))
    s[0, 0, 0] = 99
    with pytest.raises(ValueError):
        net.s[0, 0, 0] = 99
    data = net.touchstone().split('[Network Data]\n')[1].splitlines()[0]
    np.testing.assert_allclose([float(x) for x in data.split()], [1e9,.1,.2,.5,.6,.3,.4,.7,.8])
    with pytest.raises(ValueError):
        net.mixed_mode()


def test_three_conductors_and_mixed_boolean_rejection():
    n = 3
    net = rlgc_network(F, R=np.zeros((n, n)), L=np.diag([250, 360, 490])*1e-9,
                       G=np.zeros((n, n)), C=np.diag([100, 100, 100])*1e-12, length=.03)
    for i, inductance in enumerate([250e-9, 360e-9, 490e-9]):
        expected = scalar(F, L=[[inductance]], length=.03)
        np.testing.assert_allclose(net.s[:, [i, n+i]][:, :, [i, n+i]], expected.s, atol=1e-10)
    with pytest.raises(ValueError, match='booleans'):
        scalar([True, 2])
    with pytest.raises(ValueError, match='booleans'):
        rlgc_network(F, R=[[True, 0], [0, 1]], L=np.eye(2), G=np.zeros((2, 2)),
                     C=np.eye(2), length=1)
