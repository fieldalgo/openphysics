# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The guided / leaky notes of open-boundary modes on real solves (slice S3): gates G1 to G5 and G8
of the design draft, pre-registered there before the implementation (measured on main 2318e5f,
Linux). G6 and G7 (core mesh and wavelength) are test_studio_mode_channel_mesh.py; G9 and G10
(closed runs, the unit table) are the Node checks studio_mode_channel_page.cjs and
studio_mode_channel.cjs.

Each run is the document Studio's builder writes, solved and kept as Studio keeps it; the categories
and texts are the page's own functions (mode_channel_fixtures). Re n_eff only identifies a mode
(|dRe| <= 5e-4, as V4): the values below are the draft's, and the gates compare categories and the
strings computed from this machine's solve.

- G1: T16 (the strip over a substrate, every edge open, the default targets 2.46 and 1.95, 4 modes):
  2.4413, 1.7728 and 1.4864 are leaky into Substrate, with the exact strings of the draft's §4.2
  (mode 1 after its core note, whose own words are those of openRegionNotes).
- G2: the template, every edge open, 2 modes (2.4429, 1.7700) and near 1.600 with 4 modes (1.4923):
  guided.
- G3: the leaky slab (left and right closed), near 2.85: 2.8447 and 2.8327 are leaky into Substrate.
- G4: the strip over a substrate with only the top edge open, single searches near 2.441, 1.773 and
  1.49 (2.4408, 1.7708, 1.4850): guided.
- G5: the strip over a substrate with the bottom edge closed, near 2.441 and 1.773 (2.4411,
  1.7706): no claim (a layer), with the exact string of §4.2 for the mode near 2.441.
- G8: every mode of G1 to G5: guided => Im n_eff <= b, leaky => Im n_eff > b, with b the engine's
  gain bound of the mode's stored pml_l2_fraction.

A failure is reported, not re-registered silently; δ = 0.02 is never moved to pass G8.
"""
from __future__ import annotations

import pytest

import mode_channel_fixtures as G
from open_boundary_fixtures import ALL, TOP_BOTTOM

LEAKY = "{head} is a leaky mode: Re n_eff {x} is below the index of Substrate (3.478), which reaches the open window edge, so light can leak into Substrate. The loss shown is that leakage; it is part of this structure, not a fault of the solve."
G5_TEXT = "Mode 1: Re n_eff 2.441 is below the index of Substrate (3.478), which reaches the open left and right edges only as a layer. Whether light can leak into it depends on that layer's own modes, which Studio does not compute; Studio does not say whether this mode is guided or leaky."


def _check(out, expected, kind, regions, which):
    found = []
    for re in expected:
        c = G.mode_at(out, re, which)
        assert c["kind"] == kind, (which, re, c)
        assert [r["name"] for r in c["regions"]] == regions, (which, re, c)
        assert G.gain_bound_agrees(c), ("G8", which, re, c)
        found.append(c)
    return found


@pytest.mark.slow
def test_g1_t16_modes_are_leaky_into_the_substrate_with_the_registered_strings(tmp_path):
    record, seconds = G.studio_run(G.build("strip_substrate", 4), "strip_substrate", ALL)
    out = G.notes(record, tmp_path)
    G.show("G1 T16, every edge open, 4 modes", out, seconds)
    modes = _check(out, (2.4413, 1.7728, 1.4864), "leaky", ["Substrate"], "G1")
    assert [c["mode"] for c in modes] == [0, 1, 2]
    region = out["region"][0]
    assert region.startswith("Mode 1 is the core mode: ") and region.endswith(" % of |E|² in the window (PML excluded) is in Core, which does not touch the window edge."), region
    print(f"  mode 1 note: {out['notes'][0]}")
    assert out["notes"][0] == [region + " " + LEAKY.format(head="It", x="2.441")]
    assert out["notes"][1] == [LEAKY.format(head="Mode 2", x="1.773")]
    assert out["notes"][2] == [LEAKY.format(head="Mode 3", x="1.486")]


@pytest.mark.slow
def test_g2_the_template_modes_are_guided(tmp_path):
    record, seconds = G.studio_run(G.build("template", 2), "template", ALL)
    out = G.notes(record, tmp_path)
    G.show("G2 template, every edge open, 2 modes", out, seconds)
    _check(out, (2.4429, 1.7700), "guided", ["the silica background"], "G2")
    assert [t["text"].split(":")[0] for t in out["texts"]] == ["Mode 1 is guided", "Mode 2 is guided"]
    record, seconds = G.studio_run(G.build("template", 4, target="1.600"), "template", ALL)
    out = G.notes(record, tmp_path)
    G.show("G2 template near 1.600, 4 modes", out, seconds)
    _check(out, (1.4923,), "guided", ["the silica background"], "G2")


@pytest.mark.slow
def test_g3_the_leaky_slab_is_leaky_into_the_substrate(tmp_path):
    record, seconds = G.studio_run(G.build("slab", 2, target="2.85", edges=TOP_BOTTOM), "slab", TOP_BOTTOM)
    out = G.notes(record, tmp_path)
    G.show("G3 leaky slab, left and right closed, near 2.85", out, seconds)
    _check(out, (2.8447, 2.8327), "leaky", ["Substrate"], "G3")


@pytest.mark.slow
@pytest.mark.parametrize("target, expected", [(2.441, 2.4408), (1.773, 1.7708), (1.49, 1.4850)])
def test_g4_only_the_top_edge_open_the_modes_are_guided(tmp_path, target, expected):
    record, seconds = G.studio_run(G.single_search("strip_substrate", G.TOP_ONLY, target), "strip_substrate", G.TOP_ONLY)
    out = G.notes(record, tmp_path)
    G.show(f"G4 strip over a substrate, only the top edge open, near {target}", out, seconds)
    _check(out, (expected,), "guided", ["the silica background"], "G4")


@pytest.mark.slow
@pytest.mark.parametrize("target, expected", [(2.441, 2.4411), (1.773, 1.7706)])
def test_g5_bottom_closed_no_claim_as_a_layer(tmp_path, target, expected):
    record, seconds = G.studio_run(G.single_search("strip_substrate", G.BOTTOM_CLOSED, target), "strip_substrate", G.BOTTOM_CLOSED)
    out = G.notes(record, tmp_path)
    G.show(f"G5 strip over a substrate, bottom closed, near {target}", out, seconds)
    (c,) = _check(out, (expected,), "layer", ["Substrate"], "G5")
    assert c["sides"] == ["left", "right"]
    if target == 2.441:
        assert out["texts"][0]["text"] == G5_TEXT
        # on the page it follows the mode's core note, its opening reworded
        region = out["region"][0]
        assert region and region.startswith("Mode 1 is the core mode: "), region
        assert out["notes"][0] == [region + " " + G5_TEXT.removeprefix("Mode 1: ")]
