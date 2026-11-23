# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Shared helpers of the open-boundary validation (tests/simcase/test_open_boundary_*.py): the
documents Studio's optical-shapes-v9 builder writes, mesh scaling, the solve, the slab reference.

Mesh scaling multiplies every element length of the built document (mesh.element_size, the
grading's near and far, each shape's element_size); refinement_distance is a distance and stays.
"""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

import physmat
import refsol.lossy_slab
from simcase import Document, run

HERE = Path(__file__).resolve().parent
STATIC = HERE.parents[1] / "packages" / "simcase" / "src" / "simcase" / "studio" / "static"
FIXTURES = HERE / "studio_session_fixtures"
WAVELENGTH = 1.55e-6
DB = 10 * np.log10(np.e)

_BUILD = r"""
const O = await import(process.argv[1]);
const [kind, modes, t, target, edges] = process.argv.slice(2);
const strip = {name: 'Core', type: 'rect', material: 'Silicon', x: -250, y: 0, w: 500, h: 220};
const film = {name: 'Film', type: 'rect', material: 'Silicon', x: -1500, y: 0, w: 3000, h: 220};
const substrate = {name: 'Substrate', type: 'rect', material: 'Silicon', x: -1500, y: -1200, w: 3000, h: 700};
const shapes = {template: [strip], slab: [film, substrate], strip_substrate: [strip, substrate]}[kind];
const openBoundary = {edges: JSON.parse(edges), thickness: Number(t)};
if (target !== '-') openBoundary.target = Number(target);
const state = {electric: false, heat: false, structure: false, optics: true, wavelength: 1550, coreMesh: 30,
  modeCount: Number(modes), shapes};
const setup = {materials: {Core: 'Silicon', Oxide: 'Silica', Heater: ''}};
let doc;
if (Number(t) === 1000) doc = O.opticalDocument({...state, openBoundary}, setup);
else {
  // another thickness: the builder's own extrusion of its closed document (the page offers 1 um only)
  const B = await import(new URL('workspace-open-boundary.mjs', process.argv[1]).href);
  const checked = B.checkOpenBoundary({...openBoundary, thickness: 1000}, shapes);
  doc = B.applyOpenBoundary(O.opticalDocument(state, setup), {...checked, thickness: Number(t)});
}
process.stdout.write(JSON.stringify(doc));
"""
ALL = {"left": "open", "right": "open", "bottom": "open", "top": "open"}
TOP_BOTTOM = {"left": "closed", "right": "closed", "bottom": "open", "top": "open"}
CLOSED = {"left": "closed", "right": "closed", "bottom": "closed", "top": "closed"}


def node():
    found = shutil.which("node")
    if found is None:
        pytest.skip("node is not installed; the studio_open_boundary.cjs suite checks the page modules")
    return found


def build(kind, modes, thickness=1000, target="-", edges=ALL, script=_BUILD):
    """The document Studio's optical-shapes-v9 builder writes (exact text and parsed)."""
    done = subprocess.run([node(), "--input-type=module", "-e", script, (STATIC / "workspace-optical.mjs").as_uri(),
                           kind, str(modes), str(thickness), str(target), json.dumps(edges)],
                          capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stdout + done.stderr
    return done.stdout


def scaled(text, factor):
    d = json.loads(text)
    nm = lambda v: f"{float(v.split()[0]) * factor:g} nm"       # noqa: E731
    d["mesh"]["element_size"] = nm(d["mesh"]["element_size"])
    for key in ("near", "far"):
        d["mesh"]["grading"][key] = nm(d["mesh"]["grading"][key])
    for shape in d["geometry"]["shapes"]:
        if "element_size" in shape:
            shape["element_size"] = nm(shape["element_size"])
    return d


def solve(d):
    d = copy.deepcopy(d)
    d["results"] = {"plots": False}
    r = run(Document.from_dict(d), False)
    point = r.open_boundary[0]
    chosen = {c["candidate"]: c for c in point["candidates"]}
    fraction = [chosen[i]["physical_l2_fraction"] for i in point["selected_candidates"]]
    return r.effective_index[0], r.propagation_loss()[0] / 100, np.asarray(fraction), point["candidates"]


def silicon_and_silica():
    return tuple(complex(physmat.material(name).refractive_index(vacuum_wavelength=WAVELENGTH))
                 for name in ("Si", "SiO2"))


def slab_reference(pol):
    si, sio2 = silicon_and_silica()
    return refsol.lossy_slab.substrate_leaky_mode(refractive_index=(sio2, si, sio2, si), thickness=(0.22e-6, 0.5e-6),
                                                  vacuum_wavelength=WAVELENGTH, pol=pol)


def db_per_cm(n):
    return 4 * np.pi * n.imag / WAVELENGTH * DB / 100


def richardson(h, values):
    """L0 of L = L0 + C h**p through three points (p by bisection on the ratio of differences)."""
    (h1, h2, h3), (l1, l2, l3) = h, values
    ratio = (l1 - l2) / (l2 - l3)
    lo, hi = 1e-3, 20.
    f = lambda p: (h1 ** p - h2 ** p) / (h2 ** p - h3 ** p) - ratio      # noqa: E731
    assert f(lo) * f(hi) < 0, "the three values are not monotone in h"
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(lo) * f(mid) > 0 else (lo, mid)
    p = (lo + hi) / 2
    c = (l2 - l3) / (h2 ** p - h3 ** p)
    return l3 - c * h3 ** p


def physical_modes(candidates):
    return [complex(c["effective_index"]["re"], c["effective_index"]["im"]) for c in candidates
            if c["physical_l2_fraction"] >= 0.97 and c["effective_index"]["re"] > 1.45 and c["relative_residual"] <= 1e-8
            and "negative_imaginary_index" not in c["reasons"]]


def reference_modes(text, target):
    wide = json.loads(text)
    wide["physics"]["em1"]["pml"]["pml_search_mode_count"] = 32
    wide["physics"]["em1"]["target_effective_index"] = target
    return physical_modes(solve(wide)[3])


def mode_near(d, z):
    """The variant's mode nearest the reference mode z, by a search targeted at Re z (32 candidates)."""
    d = copy.deepcopy(d)
    d["physics"]["em1"]["target_effective_index"] = round(float(z.real), 6)
    d["physics"]["em1"]["pml"]["pml_search_mode_count"] = 32
    n, loss, fraction, _ = solve(d)
    physical = fraction >= 0.97
    assert physical.any(), ("no physical mode near", z, n, fraction)
    i = np.flatnonzero(physical)[np.argmin(abs(n[physical] - z))]
    return n[i], loss[i]


def independent(reference, d, where):
    for z, l in zip(*reference):
        n, loss = mode_near(d, z)
        assert abs(n.real - z.real) <= 5e-4, (where, n, z)
        assert abs(loss / l - 1) <= 0.01, (where, loss, l)
