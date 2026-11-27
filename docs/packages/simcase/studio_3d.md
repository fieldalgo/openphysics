# 3D view in Studio (experimental)

**English** | [한국어](../../locales/ko/pages/packages/simcase/studio_3d.md)

[Documentation home](../../README.md)

Status: **experimental.** This page describes the server side of the coming
read-only 3D view of a `3d` component of a version 1 geometry document
([contract](geometry_document.md)): display triangles and section outlines. It
takes what the stage 5 engine takes: boxes and the slab layers of `layers`
features (`simcase.geometry_engine3d`). The view itself, on the
[geometry lab](geometry_lab.md) page, comes with the next change. These HTTP
answers may change in any release.

The card document (`simcase/studio/static/model3d-via-stack.json`, in µm,
served at `/model3d-assets/model3d-via-stack.json`) is a 10 × 10 domain with
three slab layers (substrate 0–2, oxide 2–3 and top silicon 3–4, one `layers`
feature `stack`) and a copper box `via` with x and y in [4, 6] through the oxide
(z in [2, 3]).

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
- The answer is deterministic (W15): nothing unordered reaches it.

### Camera

The view's first camera will be the isometric one, and picking (W3) is checked
against it:

- the frame is metres from the domain centre, and R is half the domain diagonal;
- an orthographic camera looks at the target from target + 4 R e, with
  e = (1, 1, 1)/√3 and up +z; its axes are z = e, x = normalize(up × z),
  y = z × x (three.js `lookAt`);
- **Fit** frames a sphere of radius 1.1 R: for a W × H canvas with W ≥ H, half
  height 1.1 R and half width 1.1 R W/H, otherwise half width 1.1 R and half
  height 1.1 R H/W (divided by the zoom);
- a canvas point (px, py) in CSS pixels is at ndc (2 px/W − 1, 1 − 2 py/H);
- the axis views look along ±x, ±y (up +z) and ±z (up +y).

## Checks

Pre-registered (fixed before measuring; never loosened):

| Check | What | Threshold | Measured | Where |
|---|---|---|---|---|
| W1 | every display triangle carries an exact surface's provenance, on E1, the card and 50 seeded G1 sets: (a) face id missing or name set different from the face's; (b) vertex off the face's plane or outside its polygon, or centroid not inside (exact, on pm values before float32) | (a) 0; (b) 0 | 0; 0 (52 documents, 1458 faces, 3066 triangles) | `tests/simcase/test_studio_model3d.py` |
| W2 | per face, area of its float32 triangles against the exact face area | ≤ 1e-6 relative | 9.5e-8 worst (G1 seed 0, face 7) | same |
| W3 (expected values) | the expected picks at 40 fixed points, 1440 × 900 window (canvas 720 × 504), isometric camera, card: face id and first name by an independent ray cast on the exact complex, written before the view (`tests/simcase/model3d_pick_oracle.py`, `studio_model3d_pick_points.json`; 26 raster points within 3 px of an edge excluded). The browser check comes with the view | — | 24 face hits, 16 background points | `tests/simcase/test_studio_model3d.py` (stored file equals a fresh run) |
| W15 | SHA-256 of the display answer over 3 fresh server processes | identical | identical | `tests/simcase/test_studio_model3d.py` |

Also tested: section outlines lie on their plane and have the exact cut length of
each face (four planes of the card, one along an edge of the via's hole);
refusals carry the engine's words; the asset route serves only its files.

## Limits

- A component holding one `layers` feature (E1) is meshed through
  `meshine.extrude`, and `evaluate3d` refuses it; the view takes its complex from
  the public `simcase.display_complex3d`, which builds for it the complex the
  meshloom route would build.
- Each request evaluates the whole component on the server.
- A section answers outlines only; cut regions are not capped.
