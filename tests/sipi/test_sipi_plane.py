# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""sipi.PowerPlane DC voltage drop against closed-form references.

D1 uniform strip, source and load on opposite ends: exact in P1.
D2 annulus, source on the inner circle, load on the outer edge:
   dV = I ln(b/a) / (2 pi sigma t); mesh convergence.
D3 two circular pads (radius a, centres d apart) in a large plane: the
   resistance between two equipotential discs in an infinite sheet is
   acosh(d / 2a) / (pi sigma t). The load draws uniform current instead of
   being equipotential, and the plane is finite; both effects are measured.
D4 energy: the plane's Joule loss equals the power delivered at the terminals.
"""

import numpy as np
import pytest

from sipi import (COPPER_CONDUCTIVITY, PowerPlane, Sink, Source, circle, edge,
                  rectangle_outline)

T = 35e-6
SIGMA = COPPER_CONDUCTIVITY


def test_d1_strip_is_exact():
    length, width, current = 50e-3, 5e-3, 3.0
    plane = PowerPlane(rectangle_outline(0, 0, length, width), T,
                       sources=[Source("vrm", edge((0, 0), (0, width)), 1.0)],
                       sinks=[Sink("load", edge((length, 0), (length, width)), current)])
    r = plane.solve()
    resistance = length / (SIGMA * T * width)
    assert r.resistance("load") == pytest.approx(resistance, rel=1e-9)
    assert r.drop("load") == pytest.approx(current * resistance, rel=1e-9)
    assert r.terminals["vrm"]["current"] == pytest.approx(current, rel=1e-9)
    assert r.power_loss == pytest.approx(current ** 2 * resistance, rel=1e-9)
    assert r.max_current_density == pytest.approx(current / (width * T), rel=1e-9)
    np.testing.assert_allclose(r.sheet_current, r.current_density * T, rtol=0, atol=0)


@pytest.mark.slow
def test_d2_annulus_converges():
    a, b, current = 1e-3, 10e-3, 2.0
    exact = current * np.log(b / a) / (2 * np.pi * SIGMA * T)
    errors = []
    for edge_size, far_size in ((None, None), (a / 16, b / 40), (a / 24, b / 60)):
        plane = PowerPlane(circle((0, 0), b, n=64), T,
                           sources=[Source("vrm", circle((0, 0), a), 1.0)],
                           sinks=[Sink("edge", "outline", current)])
        r = plane.solve(edge_size=edge_size, far_size=far_size)
        errors.append(abs(r.drop("edge") / exact - 1))
    assert errors[-1] <= 1e-3
    assert errors[0] > errors[1] > errors[2]


def _pads(size):
    a, d = 0.5e-3, 10e-3
    return PowerPlane(rectangle_outline(-size / 2, -size / 2, size / 2, size / 2), T,
                      sources=[Source("vrm", circle((-d / 2, 0), a), 1.0)],
                      sinks=[Sink("load", circle((d / 2, 0), a), 1.0)]).solve(), a, d


def test_d3_two_pads_match_the_infinite_sheet():
    small, a, d = _pads(100e-3)
    large, _, _ = _pads(200e-3)
    exact = np.arccosh(d / (2 * a)) / (np.pi * SIGMA * T)
    assert small.resistance("load") == pytest.approx(exact, rel=1e-2)
    assert large.resistance("load") == pytest.approx(exact, rel=1e-2)
    # Doubling the plane moves the answer by the truncation error.
    assert abs(large.resistance("load") / small.resistance("load") - 1) <= 5e-3


def test_d4_power_balance_with_several_terminals():
    plane = PowerPlane(rectangle_outline(0, 0, 40e-3, 30e-3), T,
                       holes=[rectangle_outline(15e-3, 10e-3, 25e-3, 20e-3)],
                       sources=[Source("vrm", circle((5e-3, 5e-3), 1e-3), 1.0)],
                       sinks=[Sink("cpu", circle((35e-3, 25e-3), 1e-3), 4.0),
                              Sink("mem", circle((35e-3, 5e-3), 0.6e-3), 1.5)])
    r = plane.solve()
    delivered = sum(t["mean"] * t["current"] for t in r.terminals.values())
    assert r.power_loss == pytest.approx(delivered, rel=1e-9)
    assert r.terminals["vrm"]["current"] == pytest.approx(5.5, rel=1e-9)
    # The cutout lengthens the path to the far load.
    assert r.drop("cpu") > r.drop("mem") > 0
    assert r.terminals["cpu"]["min"] <= r.terminals["cpu"]["mean"] <= r.terminals["cpu"]["max"]


@pytest.mark.parametrize("kwargs, message", [
    (dict(thickness=0.0), "thickness"),
    (dict(conductivity=-1.0), "conductivity"),
    (dict(sources=[]), "at least one Source"),
    (dict(sinks=[Sink("load", circle((5e-3, 5e-3), 1e-3), 0.0)]), "current must be > 0"),
    (dict(sinks=[Sink("vrm", circle((5e-3, 5e-3), 1e-3), 1.0)]), "unique"),
    (dict(outline=[(0, 0), (1, 0)]), "outline"),
])
def test_plane_rejects_bad_input(kwargs, message):
    args = dict(outline=rectangle_outline(0, 0, 10e-3, 10e-3), thickness=T,
                sources=[Source("vrm", circle((2e-3, 2e-3), 1e-3), 1.0)],
                sinks=[Sink("load", circle((8e-3, 8e-3), 1e-3), 1.0)])
    args.update(kwargs)
    with pytest.raises(ValueError, match=message):
        PowerPlane(args.pop("outline"), args.pop("thickness"), **args)


def test_edge_and_outline_terminal_checks():
    with pytest.raises(ValueError, match="distinct"):
        edge((0, 0), (0, 0))
    with pytest.raises(ValueError, match="only one terminal"):
        PowerPlane(rectangle_outline(0, 0, 1e-2, 1e-2), T,
                   sources=[Source("a", "outline", 1.0)], sinks=[Sink("b", "outline", 1.0)])
    plane = PowerPlane(rectangle_outline(0, 0, 10e-3, 10e-3), T,
                       sources=[Source("vrm", circle((2e-3, 2e-3), 1e-3), 1.0)],
                       sinks=[Sink("load", edge((0, 20e-3), (10e-3, 20e-3)), 1.0)])
    with pytest.raises(RuntimeError, match="received no boundary edges"):
        plane.solve()
