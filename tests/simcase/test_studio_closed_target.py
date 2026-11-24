# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Search near n_eff for closed-window runs (adapter optical-shapes-v10, capabilities v10, slice C1):
the capabilities, the server's checks of a closed target (K11) and the engine on the documents
Studio's builder writes with one (K2 to K8, K13). The builder itself (K1: byte for byte without a
target) is tests/simcase/studio_closed_target.cjs.

Pre-registered before the code (references measured on main 13f07f4, Linux):

- K2: the strip over a substrate (Core 500 x 220 nm at (-250, 0), Substrate 3000 x 700 nm at
  (-1500, -1200), 1550 nm), closed @2.46: 1 mode 2.43931663 +- 1e-8 with the engine's core
  confinement >= 0.9 and TE >= 0.97; 2 modes 2.48623178 and 2.43931663 +- 1e-8.
- K3: closed @2.46 against the open default through Studio's matching: the core modes paired with
  overlap >= 0.95 and |delta n_eff| <= 3e-3 (measured 0.9879 and -1.95e-3).
- K4: a 220 nm silicon film over the full width, closed @2.85, element scales 1, 2/3, 1/2, 1/3,
  against the 1D TE transfer matrix with PEC at +-1200 nm, 2.84948947 (_film_reference): the error
  is negative and shrinks at each refinement, |error| <= 5e-3 at scale 1 (measured -4.80e-3,
  -2.46e-3, -1.99e-3, -1.02e-3).
- K5: the film over the substrate @2.85 against 2.84916936: the film-like mode (confinement in the
  film >= 0.9) is among 2 modes, and its error is within 5e-4 of K4's at each scale (measured
  -4.44e-4, -1.95e-4, -0.99e-4, -1.71e-4).
- K6: the template @2.46, 2 modes: the default closed run's two n_eff within 1e-12.
- K7: the coordinator's registered variants (each edited in the document only; core 500 x 220 at
  (-250, 0), the substrate spanning the window) @2.46, 4 modes: the core mode (confinement > 0.5)
  is returned in 8 of 8 (measured ranks 3, 3, 3, 4, 4, 3, 3, 4).
- K8: n_g of the strip over a substrate closed @2.46, 1 mode: finite and within 2e-3 of the open
  run's Re n_g 4.19152 (measured 4.19234).
- K13 (engine part): the template @2.46, 4 modes returns 1.39191472 as mode 4, below the cladding;
  Studio leaves it out (slice C2, studio_closed_target_page.cjs).
- K12 (slice C2, on engine fields): Studio's notes of the strip over a substrate closed @2.46 with 2
  modes name mode 1 as mostly in Substrate (the edge note) and mode 2 as the core mode (its |E|² share
  in Core > 0.5; measured 0.644).

"Scale" multiplies every element length of the document (open_boundary_fixtures.scaled).
"""
from __future__ import annotations

import copy
import json
import subprocess

import numpy as np
import pytest

from open_boundary_fixtures import ALL, CLOSED, STATIC, build, node, scaled
from simcase import Document, run

# the builder's document with Search near n_eff in a closed window (state.searchTarget)
_BUILD = r"""
const O = await import(process.argv[1]);
const [kind, modes, target] = process.argv.slice(2);
const strip = {name: 'Core', type: 'rect', material: 'Silicon', x: -250, y: 0, w: 500, h: 220};
const film = {name: 'Film', type: 'rect', material: 'Silicon', x: -1500, y: 0, w: 3000, h: 220};
const substrate = {name: 'Substrate', type: 'rect', material: 'Silicon', x: -1500, y: -1200, w: 3000, h: 700};
const shapes = {template: [strip], film: [film], slab: [film, substrate], strip_substrate: [strip, substrate]}[kind];
const state = {electric: false, heat: false, structure: false, optics: true, wavelength: 1550, coreMesh: 30,
  modeCount: Number(modes), shapes, searchTarget: Number(target)};
process.stdout.write(JSON.stringify(O.opticalDocument(state, {materials: {Core: 'Silicon', Oxide: 'Silica', Heater: ''}})));
"""


def targeted(kind, modes, target):
    """The document Studio's optical-shapes-v10 builder writes (exact text) with a closed target."""
    done = subprocess.run([node(), "--input-type=module", "-e", _BUILD, (STATIC / "workspace-optical.mjs").as_uri(),
                           kind, str(modes), str(target)], capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stdout + done.stderr
    return done.stdout


def solve(d):
    d = copy.deepcopy(d)
    d["results"] = {"plots": False, **({"group_index": d["results"]["group_index"]} if "group_index" in d.get("results", {}) else {})}
    return run(Document.from_dict(d), False)


def confinement(result, region=0):
    """The engine's confinement factor (energy fraction) of each mode in the region of shape s1."""
    assert result.region_names[region] == f"s{region + 1}"
    return [float(c[region]) for c in result.postprocessing["confinement_factor"][0]]


# -- contract ------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from simcase.studio import app
    return TestClient(app)


def test_capabilities_v10_add_the_closed_target_to_v9(client):
    v9 = client.get("/api/workspace/capabilities/v9").json()
    v10 = client.get("/api/workspace/capabilities/v10").json()
    assert (v10.pop("schema_version"), v10.pop("adapter")) == (10, "optical-shapes-v10")
    assert v10.pop("closed_target") == {"default": "(n_max + n_SiO2) / 2 at 1550 nm, two decimals",
                                        "bounds": "above 1.45 and below n_max"}
    assert (v9.pop("schema_version"), v9.pop("adapter")) == (9, "optical-shapes-v9")
    assert v10 == v9


def _params(client, capabilities=True):
    instance = client.get("/api/workspace/capabilities/v10").json()["server_instance"]
    return {"workspace_instance": instance, **({"workspace_capabilities": "10"} if capabilities else {})}


def _strip(target=2.46):
    doc = json.loads(targeted("strip_substrate", 2, target))
    assert doc["physics"]["em1"]["target_effective_index"] == target
    return doc


@pytest.mark.parametrize("change, reason", [
    ({"target_effective_index": 1.45}, "must lie above 1.45 and below 3.4777 (the design's largest index) (got 1.45)"),
    ({"target_effective_index": 1.2}, "(got 1.2)"),
    ({"target_effective_index": 3.4777}, "(got 3.4777)"),
    ({"target_effective_index": 4}, "(got 4)"),
    ({"target_effective_index": "2.46"}, 'Search near n_eff must be a number (got "2.46").'),
    ({"target_effective_index": True}, "Search near n_eff must be a number (got true)."),
    ({"target_effective_index": None}, "Search near n_eff must be a number (got null)."),
    ({"pml": {"pml_additional_searches": [{"target_effective_index": 1.95, "pml_search_mode_count": 16}]}},
     "A closed-window search has one target; pml_additional_searches belongs to an open boundary."),
    ({"pml_additional_searches": [{"target_effective_index": 1.95, "pml_search_mode_count": 16}]},
     "A closed-window search has one target; pml_additional_searches belongs to an open boundary."),
])
def test_k11_the_server_refuses_another_closed_target(client, change, reason):
    doc = _strip()
    doc["physics"]["em1"].update(change)
    for route in ("/api/validate", "/api/run"):
        response = client.post(route, params=_params(client), json={"doc": doc})
        assert response.status_code == 400 and reason in response.json()["detail"], response.text


@pytest.mark.parametrize("capabilities", [None, "9", "11"])
def test_k11_a_closed_target_needs_capabilities_v10(client, capabilities):
    params = _params(client, capabilities=False)
    if capabilities is not None:
        params["workspace_capabilities"] = capabilities
    for route in ("/api/validate", "/api/run"):
        response = client.post(route, params=params, json={"doc": _strip()})
        assert response.status_code == 400, response.text
        assert response.json()["detail"] == "Search near n_eff in a closed window needs workspace capabilities v10; reload the page."


def test_k11_the_same_document_without_a_target_and_the_v10_document_are_taken(client):
    plain = json.loads(build("strip_substrate", 2, edges=CLOSED))
    for params in (_params(client, capabilities=False), _params(client)):
        response = client.post("/api/validate", params=params, json={"doc": plain})
        assert response.status_code == 200 and response.json()["ok"], response.text
    response = client.post("/api/validate", params=_params(client), json={"doc": _strip()})
    assert response.status_code == 200 and response.json()["ok"], response.text
    # silicon nitride: n_max 1.9963, so 1.99 is taken and 2.0 refused
    doc = _strip()
    for shape in doc["geometry"]["shapes"]:
        shape["material"] = "physmat:Si3N4"
    for target, ok in ((1.99, True), (1.9963, False), (2.0, False)):
        doc["physics"]["em1"]["target_effective_index"] = target
        response = client.post("/api/validate", params=_params(client), json={"doc": doc})
        assert (response.status_code == 200) == ok, response.text


def test_requests_without_a_workspace_instance_are_not_limited(client):
    # the single-page Studio: the reader alone decides
    response = client.post("/api/validate", json={"doc": _strip(3.0)})
    assert response.status_code == 200 and response.json()["ok"], response.text


# -- engine on the builder's documents ------------------------------------------------------------

def test_k2_k6_k13_strip_over_substrate_and_template():
    one = solve(json.loads(targeted("strip_substrate", 1, 2.46)))
    n = one.effective_index[0]
    print(f"\nK2 1 mode: {n}, confinement {confinement(one)}, TE {one.postprocessing['te_polarization_fraction'][0]}")
    assert abs(n[0] - 2.43931663) <= 1e-8 and abs(n[0].imag) == 0
    assert confinement(one)[0] >= 0.9 and one.postprocessing["te_polarization_fraction"][0][0] >= 0.97
    two = solve(json.loads(targeted("strip_substrate", 2, 2.46))).effective_index[0].real
    print(f"K2 2 modes: {two}")
    assert np.max(np.abs(two - [2.48623178, 2.43931663])) <= 1e-8
    a = solve(json.loads(targeted("template", 2, 2.46))).effective_index[0]
    b = solve(json.loads(build("template", 2, edges=CLOSED))).effective_index[0]
    print(f"K6 template @2.46 {a}, default {b}, max |diff| {np.max(np.abs(a - b)):.2e}")
    assert np.max(np.abs(a - b)) <= 1e-12
    four = solve(json.loads(targeted("template", 4, 2.46))).effective_index[0].real
    print(f"K13 template @2.46, 4 modes: {four}")
    assert len(four) == 4 and abs(four[3] - 1.39191472) <= 1e-8 and np.all(four[:3] > 1.45)


def test_k3_closed_targeted_against_the_open_default(tmp_path):
    from test_open_boundary_mode_identity import bounds, studio, studio_side
    closed = solve(json.loads(targeted("strip_substrate", 1, 2.46)))
    opened = solve(json.loads(build("strip_substrate", 2, edges=ALL)))
    m = studio({"kind": "match", "pairs": [[studio_side(closed), studio_side(opened, bounds(opened))]]}, tmp_path)[0]
    pair = [p for p in m["pairs"] if p["accepted"]]
    delta = closed.effective_index[0][0].real - opened.effective_index[0][pair[0]["b"][0]].real if pair else None
    print(f"\nK3 pairs {m['pairs']}, delta n_eff {delta}")
    assert m["disabled"] is None and len(pair) == 1 and pair[0]["a"] == [0] and pair[0]["eta"] >= 0.95
    assert abs(delta) <= 3e-3


def _film_reference(layers):
    """The TE mode of a stack of layers (thickness m, index) between PEC walls nearest 2.85: E = 0 at
    the bottom wall, shot to the top wall, its root by bisection (1D transfer matrix)."""
    from scipy.optimize import brentq
    k0 = 2 * np.pi / 1.55e-6

    def top(n):
        e, de = 0.0, 1.0
        for t, ni in layers:
            q2 = k0 ** 2 * (ni ** 2 - n ** 2)
            if q2 > 0:
                q = np.sqrt(q2)
                e, de = e * np.cos(q * t) + de * np.sin(q * t) / q, -e * q * np.sin(q * t) + de * np.cos(q * t)
            else:
                g = np.sqrt(-q2)
                e, de = e * np.cosh(g * t) + de * np.sinh(g * t) / g, e * g * np.sinh(g * t) + de * np.cosh(g * t)
        return e
    grid = np.linspace(2.84, 2.855, 3001)
    values = [top(n) for n in grid]
    roots = [brentq(top, grid[i], grid[i + 1], xtol=1e-15) for i in range(len(grid) - 1) if np.sign(values[i]) != np.sign(values[i + 1])]
    assert len(roots) == 1, roots
    return roots[0]


def test_the_film_references():
    from open_boundary_fixtures import silicon_and_silica
    si, sio2 = (n.real for n in silicon_and_silica())
    film = _film_reference([(1.2e-6, sio2), (0.22e-6, si), (0.98e-6, sio2)])
    over = _film_reference([(0.7e-6, si), (0.5e-6, sio2), (0.22e-6, si), (0.98e-6, sio2)])
    print(f"\nfilm {film:.8f}, film over substrate {over:.8f}")
    assert abs(film - 2.84948947) <= 5e-9 and abs(over - 2.84916936) <= 5e-9


SCALES = (1, 2 / 3, 1 / 2, 1 / 3)


@pytest.mark.slow
def test_k4_k5_the_film_converges_to_its_1d_reference():
    from open_boundary_fixtures import silicon_and_silica
    si, sio2 = (n.real for n in silicon_and_silica())
    film_ref = _film_reference([(1.2e-6, sio2), (0.22e-6, si), (0.98e-6, sio2)])
    over_ref = _film_reference([(0.7e-6, si), (0.5e-6, sio2), (0.22e-6, si), (0.98e-6, sio2)])
    film_text, slab_text = targeted("film", 1, 2.85), targeted("slab", 2, 2.85)
    errors, gaps = [], []
    for f in SCALES:
        film = solve(scaled(film_text, f))
        errors.append(film.effective_index[0][0].real - film_ref)
        slab = solve(scaled(slab_text, f))
        share = confinement(slab)
        like = [i for i, c in enumerate(share) if c >= 0.9]
        assert len(like) == 1, (f, share)
        gaps.append(slab.effective_index[0][like[0]].real - over_ref - errors[-1])
        print(f"scale {f:.3f}: K4 error {errors[-1]:+.3e}; K5 film-like mode {like[0] + 1} (confinement "
              f"{share[like[0]]:.3f}), error minus K4's {gaps[-1]:+.2e}")
    assert all(e < 0 for e in errors) and all(abs(b) < abs(a) for a, b in zip(errors, errors[1:]))
    assert abs(errors[0]) <= 5e-3
    assert all(abs(g) <= 5e-4 for g in gaps)


# K7: (name, half window width nm, window bottom nm, substrate top nm); the core is Studio's
K7_VARIANTS = [("Studio window", 1500, -1200, -500), ("window 4000 nm wide", 2000, -1200, -500),
               ("window 5000 nm wide", 2500, -1200, -500), ("window 6000 nm wide", 3000, -1200, -500),
               ("substrate 500 nm thicker", 1500, -1700, -500), ("substrate 1000 nm thicker", 1500, -2200, -500),
               ("BOX 800 nm", 1500, -1200, -800), ("BOX 300 nm", 1500, -1200, -300)]


@pytest.mark.slow
def test_k7_the_core_mode_is_among_4_modes_near_2_46_in_every_registered_variant():
    base = json.loads(targeted("strip_substrate", 4, 2.46))
    found = []
    for name, half, bottom, top in K7_VARIANTS:
        d = copy.deepcopy(base)
        d["geometry"]["domain"].update(xmin=-half, xmax=half, ymin=bottom)
        d["geometry"]["shapes"][1]["points"] = [[-half, bottom], [half, bottom], [half, top], [-half, top]]
        r = solve(d)
        core = [i + 1 for i, c in enumerate(confinement(r)) if c > 0.5]
        print(f"K7 {name}: {np.round(r.effective_index[0].real, 8)}, core mode rank {core}")
        found.append(len(core) == 1)
    assert sum(found) == 8, found


@pytest.mark.slow
def test_k8_the_group_index_of_a_closed_targeted_run():
    d = json.loads(targeted("strip_substrate", 1, 2.46))
    d["results"]["group_index"] = {"wavelength_step": "1 nm"}
    closed = solve(d).group_index()[0][0]
    o = json.loads(build("strip_substrate", 2, edges=ALL))
    o["results"]["group_index"] = {"wavelength_step": "1 nm"}
    opened = solve(o)
    core = int(np.argmax(opened.effective_index[0].real))
    print(f"\nK8 n_g closed {closed}, open {opened.group_index()[0]}")
    assert np.isfinite(closed) and abs(closed.real - opened.group_index()[0][core].real) <= 2e-3


_NOTES = r"""
import fs from 'node:fs';
const M = await import(process.argv[1]);
const N = await import(process.argv[2]);
const run = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const checked = N.validateRun(run);
process.stdout.write(JSON.stringify({edge: M.edgeNotes(checked), core: M.coreNotes(checked), placement: M.corePlacement(checked)}));
"""


def test_k12_the_core_mode_note_on_engine_fields(tmp_path):
    result = solve(json.loads(targeted("strip_substrate", 2, 2.46)))
    e = result.vector_fields[0].electric.transpose(1, 0, 2)
    setup = {"materials": {"Core": "Silicon", "Oxide": "Silica", "Heater": ""}, "temperature": 293.15, "cooling": "", "fixed": "", "terminal": ""}
    shapes = [{"name": "Core", "type": "rect", "material": "Silicon", "x": -250, "y": 0, "w": 500, "h": 220},
              {"name": "Substrate", "type": "rect", "material": "Silicon", "x": -1500, "y": -1200, "w": 3000, "h": 700}]
    script = ("const P = await import(process.argv[1]); process.stdout.write(JSON.stringify(P.snapshot({width: 500, voltage: 1, "
              "electric: false, heat: false, structure: false, optics: true, wavelength: 1550, coreMesh: 30, shapes: JSON.parse(process.argv[2])}, "
              "JSON.parse(process.argv[3]))));")
    done = subprocess.run([node(), "--input-type=module", "-e", script, (STATIC / "workspace-project.mjs").as_uri(), json.dumps(shapes), json.dumps(setup)],
                          capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stderr
    settings = {"adapter": "optical-shapes-v10", "domain": {"xmin": "-1.5 um", "xmax": "1.5 um", "ymin": "-1.2 um", "ymax": "1.2 um"},
                "boundary": "PEC", "mode_count": 2, "search_target": 2.46, "solver_version": "not reported",
                "vacuum_wavelength": "1550 nm", "core_element_size": "30 nm"}
    run = {"job": "0000000a", "completedAt": "2026-11-24T01:00:00.000Z", "settings": settings, "input": json.loads(done.stdout),
           "effective_index": result.effective_index[0].real.tolist(), "origin": "local", "serverVersion": "0.0.0",
           "field": {"node_coordinates": result.node_coordinates.tolist(), "triangles": result.triangles.tolist(),
                     "real": e.real.tolist(), "imag": e.imag.tolist()}}
    path = tmp_path / "run.json"
    path.write_text(json.dumps(run), encoding="utf-8")
    done = subprocess.run([node(), "--input-type=module", "-e", _NOTES, (STATIC / "workspace-modes.mjs").as_uri(),
                           (STATIC / "workspace-notebook.mjs").as_uri(), str(path)], capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stdout + done.stderr
    notes = json.loads(done.stdout)
    print(f"\nK12 edge {notes['edge']}, core {notes['core']}, placement {notes['placement']}")
    assert [n["mode"] for n in notes["edge"]] == [0] and notes["edge"][0]["text"].startswith("Mode 1 is mostly in Substrate (")
    assert [n["mode"] for n in notes["core"]] == [1]
    assert notes["core"][0]["text"] == "Mode 2 is the core mode: 64 % of |E|² is in Core, which does not touch the window edge."
