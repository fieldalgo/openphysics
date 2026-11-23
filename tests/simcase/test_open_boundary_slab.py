# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""V1/V2: a leaky slab in the app's window (220 nm Si film, 500 nm silica gap, Si substrate
through the bottom PML) against ``refsol.lossy_slab.substrate_leaky_mode`` at physmat indices, TE
with PEC side walls and TM with PMC side walls (edited in the built document), every element
length x 1, 1/2, 1/4 (registered before the results).
"""
from __future__ import annotations


import pytest

from open_boundary_fixtures import TOP_BOTTOM, build, db_per_cm, scaled, slab_reference, solve


# -- V1/V2: leaky slab in the app's window -------------------------------------------------------

@pytest.mark.slow
@pytest.mark.parametrize("pol,target", [("TE", 2.85), ("TM", 2.06)])
def test_v1_v2_leaky_slab_converges_to_the_analytic_pole(pol, target):
    expected = slab_reference(pol)
    text = build("slab", 1, target=target, edges=TOP_BOTTOM)
    loss_errors, re_errors = [], []
    for factor in (1, 0.5, 0.25):
        d = scaled(text, factor)
        if pol == "TM":
            d["physics"]["em1"]["boundary"].update(left="pmc", right="pmc")
        n, loss, _, _ = solve(d)
        loss_errors.append(abs(loss[0] / db_per_cm(expected) - 1))
        re_errors.append(abs(n[0].real - expected.real))
    print(f"V1/V2 {pol}: loss errors {loss_errors}, Re errors {re_errors}")
    assert loss_errors[0] > loss_errors[1] > loss_errors[2], loss_errors
    assert loss_errors[0] <= 0.035 and loss_errors[2] <= 0.005, loss_errors
    assert re_errors[2] <= 1e-3, re_errors
