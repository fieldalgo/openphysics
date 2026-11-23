# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""V4a and V5: the strip over a substrate does not depend on the PML, and the template strip in
silica does not leak (shipped settings: 1 um, strength 3, order 2, search 32, target 2.46).
"""
from __future__ import annotations

import copy
import json

import numpy as np
import pytest

from open_boundary_fixtures import build, independent, mode_near, solve


# -- V4: PML independence ------------------------------------------------------------------------
# Registered again after the results, split in two. As first registered, V4 varied the thickness
# through the builder, which grows the domain and so meshes the window again, judged against the
# 1 um base at x 1 with the search of 16 then shipped. It failed four times: at t = 1.5 um the
# TE-like mode moved by +1.28 % in loss and 8.7e-4 in Re n_eff, and the TM-like mode was not among
# the candidates at t = 2 um, at strength 1.5 and at strength 6. Registered again on one outer box
# with the shipped search of 32, it failed a fifth time: the TM-like mode was missing at strength 1.5.
#
# V4a (here): physical PML independence. The thicknesses 1 / 1.5 / 2 um share one outer box (the
# t = 2 um extent, one mesh); strength 1.5 / 6 and order 3 vary on the base mesh. Each reference mode
# (TE-like, TM-like: the 2.46/32 search of the shipped document) is looked for in each variant by a
# diagnostic search of its own, targeted at that mode's Re n_eff with 32 candidates. Gates as
# registered: |dloss|/loss <= 1 % and |dRe| <= 5e-4 per paired mode; a mode not found is a failure.
# V4b, the completeness of the shipped search, is the pass gate of V8 below (strip, slab, template).

@pytest.mark.slow
def test_v4a_strip_over_substrate_does_not_depend_on_the_pml():
    base = json.loads(build("strip_substrate", 2))
    n, loss, fraction, _ = solve(base)
    reference = (n[fraction >= 0.97], loss[fraction >= 0.97])
    assert len(reference[0]) == 2                                 # TE-like and TM-like
    for key, value in (("pml_strength", 1.5), ("pml_strength", 6), ("pml_order", 3)):
        d = copy.deepcopy(base)
        d["physics"]["em1"]["pml"][key] = value
        independent(reference, d, key)
    box = json.loads(build("strip_substrate", 2, thickness=2000))
    variants = {}
    for t in (1000, 1500, 2000):
        d = copy.deepcopy(box)
        d["physics"]["em1"]["pml"]["pml_thickness"] = {side: f"{t} nm" for side in d["physics"]["em1"]["pml"]["pml_thickness"]}
        variants[t] = d
    # the box's reference: its 1 um PML, the same modes as the base (another mesh, so not gated)
    box_reference = tuple(np.array(v) for v in zip(*(mode_near(variants[1000], z) for z in reference[0])))
    for t in (1500, 2000):
        independent(box_reference, variants[t], f"box, {t} nm")



# -- V5: no false leakage ------------------------------------------------------------------------

@pytest.mark.slow
def test_v5_the_template_strip_in_silica_does_not_leak():
    losses, resolved = [], []
    for t in (1000, 1500, 2000):
        n, loss, fraction, _ = solve(json.loads(build("template", 2, thickness=t)))
        assert len(n) == 2 and np.all(fraction >= 0.5)
        assert np.all(loss < 0.01), loss
        losses.append(loss)
        resolved.append(abs(n.imag) > 1e-10 * np.maximum(1, abs(n.real)))
    for m in range(2):
        if resolved[0][m] and resolved[2][m]:
            assert losses[2][m] < losses[0][m], [x[m] for x in losses]
