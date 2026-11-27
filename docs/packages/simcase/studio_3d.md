# 3D view in Studio (experimental)

**English** | [한국어](../../locales/ko/pages/packages/simcase/studio_3d.md)

[Documentation home](../../README.md)

Status: **experimental.** The 3D view shows a `3d` component of a version 1
geometry document ([contract](geometry_document.md)) on the
[geometry lab](geometry_lab.md) page at `/geometry-lab`. It is read-only and takes
what the stage 5 engine takes: boxes and the slab layers of `layers` features
(`simcase.geometry_engine3d`). The model workspace does not show it yet. Its page,
its controls and its HTTP answers may change in any release.

## Use

Start Studio and open the geometry lab:

```sh
python -m simcase.studio            # then open http://127.0.0.1:8765/geometry-lab
```

Choose **Via in a layer stack (3D example)** under **Start from**, or open a
document whose shown component is `3d`. A document with a 2D component shows that
one first, as before; choose the `3d` one under **Component**. The card document
(`simcase/studio/static/model3d-via-stack.json`, in µm) is a 10 × 10 domain with
three slab layers (substrate 0–2, oxide 2–3 and top silicon 3–4, one `layers`
feature `stack`) and a copper box `via` with x and y in [4, 6] through the oxide
(z in [2, 3]).

The same view is the Model page of the workspace's 3D model, which edits a document
and makes selections from picked faces: see [3D models](workspace.md#3d-models-experimental).

| Action | Pointer | Keyboard (focus on the view) |
|---|---|---|
| Rotate | drag | arrow keys (15° per press) |
| Pan | Shift-drag or right-drag | Shift + arrow keys |
| Zoom | wheel | `+` and `−` |
| Fit the whole domain | **Fit** | `F` |
| Axis views +X, −X, +Y, −Y, +Z, −Z | buttons | `1` to `6` |
| Isometric view | **Iso** | `0` or `I` |
| Pick a face | click | the **Faces** list: Tab to an entry, Enter |

- **Names** shows the picked face: its plane, exact area, the regions on its two
  sides, its tag and every provenance name it carries, sorted (for example
  `stack.oxide.top`, `stack.top.bottom`, `via.z1`).
- **Faces** lists every face of the complex with its names; it is the keyboard way
  to every face, including the interior ones.
- **Regions** has a box per region to hide or show it. A face is drawn when a
  non-void region on one of its sides is shown.
- **Section** keeps the part with x, y or z at most the slider's value, and the
  server draws the exact outline of the cut faces in red. Picking ignores the
  removed part.
- Refusals are the engine's own words; a feature the stage 5 engine does not take
  yet is named (`E-3D-COMBINATION`, for example `cylinder 'pin' is not taken yet in
  a 3d component; boxes and slab layers are`).

Mesh edges are not drawn: the view shows the exact geometry, not the mesh.

## What it sends and answers

- `POST /api/model3d/display` takes `{"doc": <document>, "component": <name or
  null>}` (without a name, the first `3d` component). `GET /api/model3d/display`
  answers the card document. The answer is `{"ok": true, ...}` or `{"ok": false,
  "refused": <message>}`; requests are read as on the other lab routes
  ([geometry lab](geometry_lab.md#what-it-sends-and-answers)).
- The display tessellation is built on the server from the exact complex, not
  from the mesh. Every face of the complex is an axis-aligned polygon (with holes);
  it is split exactly, in pm integers, into rectangles over the grid of its own
  vertex coordinates, and each rectangle into two triangles. Every triangle lies
  on its face's plane, inside its polygon, and carries its face's id.
- Arrays are little-endian base64: `positions` (float32, metres from the domain
  centre `origin_m`, each from its exact pm value), `indices` (uint32, three per
  triangle), `triangle_faces` (uint32, the face id of each triangle), and the face
  outlines `edges` (float32 segment end points) with `edge_faces`.
- `faces` gives per face: `id`, `axis` and `at` (its plane, in the component's
  length unit), `names` (the sorted provenance), the regions on its `minus` and
  `plus` sides, `exterior`, `tag`, the exact `area`, and its triangle range.
  `regions` gives name, material, `void`, exact `volume` and faces; `selections`
  and `tags` follow the engine; `summary` is a text listing.
- `POST /api/model3d/section` takes the same envelope plus `"axis"` (`x`, `y` or
  `z`) and `"at"` (a number in the component's length unit, rounded once to pm).
  It answers the segments where the plane meets the closed faces (`segments`,
  float32, two end points each, same frame; `segment_faces`), the faces cut and
  the regions met. A plane outside the domain is refused by name.
- The answer is deterministic (W15): nothing unordered reaches it. Each face also
  lists under `alone` the names that select that face and no other.
- `POST /api/model3d/check` is the 3D builder's check (same envelope). It answers
  `{"ok": true, ...}` with:
  - `features`: per feature its `index`, `id`, `type`, its `volume` inside the
    domain and the volume its own cells keep (`owned`), both in the component's
    length unit cubed, and its `coverage`. The coverage is `full`, `partial`
    ("covered in part by N (id)"), `none` ("covered by N (id); adds no region") or `outside`
    ("outside the domain; adds no region"). N lists the later features (numbered
    from 1) whose box overlaps it and that keep volume themselves. All of this is
    computed exactly from the complex, in pm.
  - `parameters`: SI value, unit, the written value, and `used_by`, the fields of
    the component that name the parameter.
  - `regions`, `selections`, and the display answer under `display`.
- A refusal is `{"ok": false, "refused": <the engine's message as written>,
  "code", "path", "feature_index"}`. The index is the `features[i]` the path names,
  or null, and the builder marks that feature.
- `POST /api/model3d/selection` takes the envelope plus `"face"` (a face id) and
  `"name"`, and answers the document with `selections[name] = {"boundary":
  <name>}`, where `<name>` is the first of the face's sorted names that selects it
  alone ("Use for → New selection"). A face that no single name selects, a name
  already taken and a feature id are refused by name.

The page loads three.js 0.186.1 from Studio itself
([browser-served files](../../third-party.md#browser-served-files)) and the view's
own modules from `/model3d-assets/`; the page policy stays `script-src 'self'`.

### Camera

The first camera is the isometric one, and picking (W3) is checked against it:

- the frame is metres from the domain centre, and R is half the domain diagonal;
- an orthographic camera looks at the target from target + 4 R e, with
  e = (1, 1, 1)/√3 and up +z; its axes are z = e, x = normalize(up × z),
  y = z × x (three.js `lookAt`);
- **Fit** frames a sphere of radius 1.1 R: for a W × H canvas with W ≥ H, half
  height 1.1 R and half width 1.1 R W/H, otherwise half width 1.1 R and half
  height 1.1 R H/W (divided by the zoom);
- a canvas point (px, py) in CSS pixels is at ndc (2 px/W − 1, 1 − 2 py/H);
- the axis views look along ±x, ±y (up +z) and ±z (up +y).

Picking is a CPU ray cast against the display triangles (float32), nearest hit on
a shown face, on the kept side of the section.

## Checks

Pre-registered (fixed before measuring; never loosened):

| Check | What | Threshold | Measured | Where |
|---|---|---|---|---|
| W1 | every display triangle carries an exact surface's provenance, on E1, the card and 50 seeded G1 sets: (a) face id missing or name set different from the face's; (b) vertex off the face's plane or outside its polygon, or centroid not inside (exact, on pm values before float32) | (a) 0; (b) 0 | 0; 0 (52 documents, 1458 faces, 3066 triangles) | `tests/simcase/test_studio_model3d.py` |
| W2 | per face, area of its float32 triangles against the exact face area | ≤ 1e-6 relative | 9.5e-8 worst (G1 seed 0, face 7) | same |
| W3 | picking at 40 fixed points, 1440 × 900 window, isometric camera, card: face id and first name, against an independent ray cast on the exact complex written before the view (`tests/simcase/model3d_pick_oracle.py`, `studio_model3d_pick_points.json`; 26 raster points within 3 px of an edge excluded) | 40/40 | 40/40 | `tools/studio_browser/model3d_view_browser.mjs` |
| W12 | first view at 1440 × 900 and 390 × 844: no console error, no CSP violation, canvas visible and not empty, no horizontal scroll at 390, faces list reachable by Tab; screenshots kept | all hold | all hold (faces list after 17 Tabs) | same |
| W13 | keyboard only: rotate, an axis view, select `via.z1` from the faces list, with no pointer event | complete | complete, 0 pointer events | same |
| W15 | SHA-256 of the display answer over 3 fresh server processes | identical | identical | `tests/simcase/test_studio_model3d.py` |

Also tested: section outlines lie on their plane and have the exact cut length of
each face (four planes of the card, one along an edge of the via's hole);
refusals carry the engine's words; the asset route serves only its files; the pure
helpers (`tests/simcase/studio_model3d.cjs`: camera contract, controls, picking,
visibility).

The browser checks are local (Playwright with a Chromium it can launch, not in
CI); run them against a running Studio:

```sh
python -m simcase.studio --no-browser --port 8765 &
node tools/studio_browser/model3d_view_browser.mjs http://127.0.0.1:8765 out-dir
```

## Limits

- Boxes and slab layers only, as stage 5 slice 1; read-only (no feature editing in
  3D); no mesh view yet.
- A component holding one `layers` feature (E1) is meshed through
  `meshine.extrude`, and `evaluate3d` refuses it; the view takes its complex from
  the public `simcase.display_complex3d`, which builds for it the complex the
  meshloom route would build.
- Each request evaluates the whole component on the server; the CPU pick visits
  every shown triangle (fine for the few hundred of these documents).
- A section removes one side and draws the outline; cut regions are not capped.
- The canvas is 720 × 504 CSS px from a 1300 px wide window, otherwise the column
  width at 10:7. The checks ran in headless Chromium on Linux only.
