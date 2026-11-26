# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Shared helpers of the guided / leaky gate of open-boundary modes (slice S3, G1 to G8:
test_studio_mode_channel_gate.py and test_studio_mode_channel_mesh.py).

A document Studio's optical-shapes-v9 builder writes (open_boundary_fixtures.build) is solved, and
the result kept as the page keeps a run: the modes above n = 1.45 (Re and Im apart, as
validateRun gives them), the engine's candidate record, the field on every triangle. The page's own modules then give each mode's category
(workspace-mode-channel.mjs modeChannel) and the note texts of the modes table: the region notes
(workspace-modes.mjs openRegionNotes) with the channel text placed after them, or alone
(placeChannelNotes), as workspace-app.mjs does. Nothing is computed outside the page's functions.
"""
from __future__ import annotations

import copy
import json
import subprocess
import time

import numpy as np

import open_boundary_fixtures as F
from open_boundary_fixtures import STATIC, node
from simcase import Document, run

STRIP = {"name": "Core", "type": "rect", "material": "Silicon", "x": -250, "y": 0, "w": 500, "h": 220}
FILM = {"name": "Film", "type": "rect", "material": "Silicon", "x": -1500, "y": 0, "w": 3000, "h": 220}
SUBSTRATE = {"name": "Substrate", "type": "rect", "material": "Silicon", "x": -1500, "y": -1200, "w": 3000, "h": 700}
SHAPES = {"template": [STRIP], "slab": [FILM, SUBSTRATE], "strip_substrate": [STRIP, SUBSTRATE]}
TOP_ONLY = {"left": "closed", "right": "closed", "bottom": "closed", "top": "open"}
BOTTOM_CLOSED = {"left": "open", "right": "open", "bottom": "closed", "top": "open"}
#: the identification of a mode by Re n_eff (as V4)
SAME_MODE = 5e-4

_NOTES = r"""
import {readFileSync} from 'node:fs';
const M = await import(process.argv[1]), C = await import(process.argv[2]);
const run = JSON.parse(readFileSync(process.argv[3], 'utf8'));
// the modes table's notes, as workspace-app.mjs builds them
const regions = M.openRegionNotes(run);
const edge = new Map([...M.edgeNotes(run), ...regions.filter(n => n.kind === 'edge')].map(n => [n.mode, n.text]));
const core = new Map([...M.coreNotes(run), ...regions.filter(n => n.kind === 'core')].map(n => [n.mode, n.text]));
const before = {edge: new Map(edge), core: new Map(core)};
const alone = C.placeChannelNotes(run, edge, core);
const channel = C.modeChannel(run);
process.stdout.write(JSON.stringify({
  channel: channel.map(c => ({mode: c.mode, kind: c.kind, regions: c.regions, sides: c.sides, x: c.x, im: c.im, bound: c.bound, resolved: c.resolved})),
  texts: C.channelNotes(run),
  region: run.effective_index.map((_, m) => before.edge.get(m) ?? before.core.get(m) ?? null),
  notes: run.effective_index.map((_, m) => [edge.get(m), core.get(m), alone.get(m)?.text].filter(Boolean)),
}));
"""


def build(kind, modes, edges=F.ALL, target="-", core_mesh=30, wavelength=1550, single=False):
    """The builder's document (open_boundary_fixtures.build) at a core mesh and wavelength."""
    script = F._BUILD.replace("wavelength: 1550, coreMesh: 30", f"wavelength: {wavelength}, coreMesh: {core_mesh}")
    assert script != F._BUILD or (core_mesh, wavelength) == (30, 1550)
    return json.loads(F.build(kind, modes, target=target, edges=edges, script=script, single=single))


def single_search(kind, edges, target, modes=1):
    """One search of 32 candidates near ``target`` (the draft's c6 / c7 documents)."""
    d = build(kind, modes, edges=edges)
    em = d["physics"]["em1"]
    em["pml"].pop("pml_additional_searches", None)
    em["target_effective_index"] = target
    assert em["pml"]["pml_search_mode_count"] == 32
    return d


def studio_run(d, kind, edges, core_mesh=30, wavelength=1550):
    """Solve ``d`` and keep it as Studio keeps an open run; returns (run, seconds)."""
    doc = copy.deepcopy(d)
    doc["results"] = {"plots": False}
    start = time.perf_counter()
    result = run(Document.from_dict(doc), False)
    seconds = time.perf_counter() - start
    n = np.asarray(result.effective_index[0])
    keep = [i for i, value in enumerate(n.real) if value > 1.45]
    e = np.asarray(result.vector_fields[0].electric).transpose(1, 0, 2)[keep]
    open_edges = [side for side in ("left", "right", "bottom", "top") if edges[side] == "open"]
    em = d["physics"]["em1"]
    settings = {"adapter": "optical-shapes-v9", "domain": {"xmin": "-1.5 um", "xmax": "1.5 um", "ymin": "-1.2 um", "ymax": "1.2 um"},
                "boundary": "PML", "mode_count": em["mode_count"], "solver_version": "not reported",
                "vacuum_wavelength": f"{wavelength} nm", "core_element_size": f"{core_mesh} nm",
                "pml": {"thickness": "1000 nm", "open_edges": open_edges, "target": f"{em['target_effective_index']:.3f}"}}
    record = {"job": "0000000a", "completedAt": "2026-11-25T00:00:00.000Z", "settings": settings,
              "input": {"model": {"shapes": SHAPES[kind], "wavelength": wavelength}}, "origin": "local", "serverVersion": "0.0.0",
              # the page's form of a run (workspace-notebook.mjs validateRun): Re and Im apart
              "effective_index": n.real[keep].tolist(), "effective_index_im": n.imag[keep].tolist(),
              "open_boundary": result.open_boundary[0],
              "field": {"node_coordinates": np.asarray(result.node_coordinates).tolist(), "triangles": np.asarray(result.triangles).tolist(),
                        "real": e.real.tolist(), "imag": e.imag.tolist()}}
    return record, seconds


def notes(record, tmp_path):
    """The page's categories and note texts of a run (see the module docstring)."""
    path = tmp_path / f"run-{time.perf_counter_ns()}.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    done = subprocess.run([node(), "--input-type=module", "-e", _NOTES, (STATIC / "workspace-modes.mjs").as_uri(),
                           (STATIC / "workspace-mode-channel.mjs").as_uri(), str(path)], capture_output=True, text=True, encoding="utf-8")
    path.unlink()
    assert done.returncode == 0, done.stdout + done.stderr
    return json.loads(done.stdout)


def mode_at(out, re, which):
    """The one mode of ``out`` within SAME_MODE of ``re``."""
    found = [c for c in out["channel"] if abs(c["x"] - re) <= SAME_MODE]
    assert len(found) == 1, (which, re, [c["x"] for c in out["channel"]])
    return found[0]


def show(title, out, seconds):
    """One line per mode for the log."""
    lines = [f"\n{title} ({seconds:.0f} s)"]
    for c in out["channel"]:
        lines.append(f"  mode {c['mode'] + 1}: {c['x']:.8f}{c['im']:+.3e}i b={c['bound']:.2e} {c['kind']}"
                     f" {[r['name'] for r in c['regions']]} {'resolved' if c['resolved'] else 'not resolved'}")
    print("\n".join(lines))


def gain_bound_agrees(c):
    """G8: guided => Im n_eff <= b; leaky => Im n_eff > b (no claim: not gated)."""
    if c["kind"] == "guided":
        return not c["resolved"]
    if c["kind"] == "leaky":
        return c["resolved"]
    return True
