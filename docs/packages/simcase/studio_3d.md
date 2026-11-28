# 3D view in Studio (experimental)

**English** | [한국어](../../locales/ko/pages/packages/simcase/studio_3d.md)

[Documentation home](../../README.md)

Status: **experimental.** The 3D view shows a `3d` component of a version 1
geometry document ([contract](geometry_document.md)) on the
[geometry lab](geometry_lab.md) page at `/geometry-lab`. It is read-only and takes
what the stage 5 engine takes: boxes and the slab layers of `layers` features
(`simcase.geometry_engine3d`), and cylinders and spheres in meshloom's builder shapes
([cylinders and spheres](#cylinders-and-spheres)); it can mesh them ([Mesh](#mesh)) and solve 3D
steady heat on them on the server ([Run](#run)). The model
workspace does not show it yet. Its page, its controls and its HTTP answers may change
in any release.

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

The 3D view draws no mesh edges: it shows the exact geometry. The mesh is drawn
in its own view under **Mesh**.

## Mesh

**Mesh** makes the tetrahedral mesh of the shown `3d` component with
`simcase.build_mesh3d` (meshloom), in a child process of the server, and shows the
mesh's surface. It runs no physics and changes no file.

- **Estimate first.** Whenever the 3D view shows a component, the page asks for the
  `I-MESH-ESTIMATE` estimate (`simcase.estimate_mesh3d`, which meshes nothing) and shows
  it as, for example, "Estimate 48,000 tetrahedra · about 30 s": T = 6.3 Σ V_r / h_r³,
  rounded to two significant figures, and the expected time at 0.6 ms per tetrahedron
  (the slow end of the engine's 0.4–0.6 ms). Above `mesh.element_count_limit`, **Mesh** is
  disabled and the page shows the refusal in the estimate's words (`E-MESH-ESTIMATE`); the
  server refuses such a request before it starts any process.
- **Progress.** While the job runs, the page shows the steps Studio knows,
  "Forming geometry → Meshing (expected about N s) → Checking the mesh → Ready", and the
  elapsed time as m:ss. Once the elapsed time passes twice the estimate it adds "taking
  longer than the estimate". There is no percentage: meshloom reports none.
- **Cancel meshing** terminates the child process; the page says "Meshing cancelled;
  nothing kept." Cancel is the one name for this action ("Stop run" stays the name for
  runs). meshloom cannot be interrupted and, on some thin inputs, does not return at all
  (for example two boxes with a background strip 6e-8 of the domain diagonal wide between
  them); the child process is what makes such a job end.
- **One job at a time.** A server meshes one 3D model at a time; a second request is
  answered 429 "Studio is already meshing one 3D model; wait for it or cancel it."
- **Reuse.** The server keeps the latest mesh of each component (up to four components),
  keyed by the SHA-256 of the canonical `geometry` and `mesh` blocks (keys sorted, no
  spaces, numbers as written), for the life of the server process. **Mesh** on an
  unchanged block answers the kept mesh at once; a later Run reuses it when the key
  matches. When the document changes, the mesh view is dimmed until the next mesh.
- **The mesh view** draws the mesh's exterior and interface triangles coloured by
  region, with mesh edges, beside the 3D view's controls: the same keys, camera, hidden
  regions and section. A pick on it selects the same face, by the same face id, and the
  **Names** panel lists the same names (the mesh's `provenance_faces`). Its stats are
  nodes, tetrahedra, regions and the minimum and median shape quality q = 3 r_in/R_circ
  (1 for the regular tetrahedron), the measure meshloom's validation grades
  ([meshloom](../meshloom/overview.md)); meshloom's own `stats` carry no per-tetrahedron
  quality, so Studio computes q from the mesh.
- **The route** is the `thermal.steady3d` kind's (`simcase.build_thermal3d_mesh`): a component
  holding only one slab `layers` feature (E1) is meshed by `meshine.extrude`, everything else by
  `simcase.build_mesh3d`. On the extrude route the estimate is that route's count, exact for
  footprints up to 10,000 triangles and a lower bound above them; then the limit check can happen
  in the child, after the footprint mesh and before the extrusion, with the estimate's words
  ([estimate](geometry_engine3d.md)). The estimate answer adds `route` and `count`.

## Run

`POST /api/model3d/run` solves a `thermal.steady3d` document
([3D steady heat](thermal_steady3d.md)) on the server and answers its values, its surface map, cuts
and probes. The tetrahedra and the solution never leave the server.

- **Refused before any process**, in the reader's or the estimate's words: a document that is not
  one `thermal.steady3d` entry, a document the kind's reader refuses (with its code), and a mesh
  estimate above `mesh.element_count_limit`.
- **Two steps.** `mesh`: when the component's kept mesh has the same reuse key it is taken at once
  (`reused: true`, no process); otherwise it is the [Mesh](#mesh) job itself, in its child process
  and kept for the component afterwards as **Mesh** keeps it. `solve`: `simcase.solve_thermal3d` on
  a server thread, on the kept mesh read back with `simcase.mesh3d_from_arrays`
  ([on an existing mesh](thermal_steady3d.md#on-an-existing-mesh)), so the result is
  `simcase.run`'s, bit for bit. The status has C's fields: `step` of `steps` `mesh`, `solve`,
  `done`, the elapsed and expected times, `longer_than_estimate`, `route`.
- **One run at a time**, and none while a mesh job runs: they share the child slot (429, "Studio is
  already running one 3D heat model; wait for it or cancel it.", or the mesh job's words).
- **Cancel** in the mesh step ends the child as **Cancel meshing** does. The solve cannot be
  interrupted: Cancel in the solve step marks the run cancelled ("Run cancelled; nothing kept.")
  and its result is discarded when the solve returns.
- **A connected group of regions with no fixed temperature** is refused naming its regions, from
  galerkin's own check (connected components of the tetrahedra's edges): "Fixed temperature is
  missing on the connected group of regions 'B': each connected group of regions needs one
  (galerkin: each connected component of the mesh needs a Dirichlet node)". A fixed temperature on
  an interior face is refused by the reader ("Fixed temperature needs an outer face; …").

Answers (`/api/model3d/runs/{run}/…`; positions are float32 from the view's `origin_m`, lengths in
requests in the component's unit, as for sections):

| Route | Answer |
|---|---|
| `values` | `heat_rate_by_selection` (W per `prescribed_temperature` name: the sum of `reaction_heat_rate` over its nodes, a node fixed by two names under the first), `total_source`, `balance_residual` (outward minus source, W) and `relative_balance_residual`, `temperature_min` and `temperature_max` with node, position and region, the mesh stats, route and reuse key, and `document_sha256` (of the canonical document) |
| `surface` | the mesh answer's faces, regions, positions, triangles and face ids, and `temperature` (float32) at its nodes |
| `cut {axis, at}` | the exact P1 slice by the plane: each tetrahedron's nodes on the plane and its edge crossings, T interpolated on the crossed edge; a face in the plane taken once; triangles facing +axis |
| `probe {point}` | T of the P1 interpolant in the tetrahedron that holds the point, the region and the barycentric coordinates; outside the meshed regions a refusal |
| `export/cut.csv?axis=&at=` | `x_m,y_m,z_m,temperature_K` (float64, `repr`) after `# cut plane: z = 1.2345 mm (0.0012345 m)`, `# run: …`, `# document_sha256: …` |
| `export/surface.csv` | the surface nodes, `x_m,y_m,z_m,temperature_K,face` (the provenance names of the node's first triangle's face), with the same header lines |
| `export/run.json` | `{values, document}` |
| `record?maps=kept` | the run record `thermal-steady3d-run-v1`: `document`, `document_sha256`, `values`, `mesh`, `maps` (`kept` with `surface`, or `not kept` with its counts, as the [multiphysics runs' maps](workspace.md)) |

## Cylinders and spheres

A component with a cylinder or spheres in one of meshloom's builder shapes (one cylinder
through the whole slab, one sphere in a box or alone, concentric spheres) has no exact
complex yet. The view draws it from `simcase.display_shapes3d`
([engine](geometry_engine3d.md)): planar faces exactly, circles as inscribed n-gons
(n = min(256, max(48, ⌈2πr/ℓ⌉)), ℓ = diagonal/200), a cylinder side as their prism and a
sphere as a geodesic grid of frequency min(64, max(8, ⌈1.05 r/ℓ⌉)). Details says "Shape drawn
for display; the mesh follows it to within its size".

- **The answer** has every field of the box answer. A curved face has `axis` and `at` null; every
  face has `shape` (`plane`, `cylinder`, `sphere`) and the answer `display_note`.
- **Names** are the mesh's: `domain.x0`…`domain.z1`, a via's caps also `via.bottom` and
  `via.top`, `via.side`, a sphere's `ball.surface`; a pick on the drawing or on the mesh gives the
  same face. The mesh view gives each mesh triangle the face whose name set is the set of
  provenance names that hold it.
- **Sections** are the exact outlines: a z cut of a cylinder is its n-gon, an x or y cut two
  lines at ±√(r² − d²); a sphere cut a circle of radius √(r² − d²).
- **The check** (`/api/model3d/check`) gives each feature's coverage from the exact volumes (a
  via is full; a sphere with smaller concentric ones is covered in part by them), the regions and
  the mesh estimate (slice 3's T).
- **Card 2**, `via-slab-3d` (`/model3d-assets/model3d-via-slab-3d.json`), is E2 of stage 5: a
  copper via r = 0.3 m (k = 100 W/(m K)) through a slab [−1, 1]² × [0, 1] m (k = 1), 300 K on z0
  and 301 K on z1, the sides insulated, h = 0.1 m. Q = ΔT/L (k_v πr² + k_s (A − πr²)) =
  31.99159 W.

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
  - `mesh`: the estimate of meshing the component, `{"ok": true, "estimate": ..., "key": ...}`
    in the words of `/api/model3d/mesh/estimate` (`simcase.estimate_mesh3d`, the mesh job's
    reuse key), or the refusal that blocks meshing in the form below: E-MESH-ESTIMATE above the
    element count limit, a below-tolerance E-CONTRACT, or two values that round to one
    coordinate (E-3D-COMBINATION at `features[i]`). The shape is formed either way, so the
    answer stays `"ok": true`; on the card it adds about 7 ms to the check's 8 ms.
- A refusal while forming is `{"ok": false, "refused": <the engine's message as written>,
  "code", "path", "feature_index"}`. The index is the `features[i]` the path names,
  or null, and the builder marks that feature.
- `POST /api/model3d/selection` takes the envelope plus `"face"` (a face id) and
  `"name"`, and answers the document with `selections[name] = {"boundary":
  <name>}`, where `<name>` is the first of the face's sorted names that selects it
  alone ("Use for → New selection"). A face that no single name selects, a name
  already taken and a feature id are refused by name.

The mesh job:

- `POST /api/model3d/mesh/estimate` takes the display envelope and answers
  `{"ok": true, "estimate": {"code": "I-MESH-ESTIMATE", "message", "component",
  "tetrahedra", "limit", "seconds"}, "key"}` or `{"ok": false, "refused", "code"}`.
- `POST /api/model3d/mesh` takes the same envelope. It answers the estimate's refusal
  with 400, a running job with 429, and otherwise `{"job", "status", "reused",
  "estimate", "key"}`: `status` is `"done"` with `reused: true` when the kept mesh's key
  matches, else `"running"`.
- `GET /api/model3d/jobs/{job}` answers `status` (`running`, `done`, `error` or
  `cancelled`), `step` (`forming`, `meshing`, `checking`, `ready`), `elapsed_s`,
  `expected_s`, `longer_than_estimate`, `error` and `has_result`.
  `POST /api/model3d/jobs/{job}/cancel` terminates the child (terminate, then kill after
  1 s) and removes its directory. `GET /api/model3d/jobs/{job}/result` answers the mesh
  (409 until the job is done). Job ids are made by the server (`m3d-` and 12 hex digits);
  any other id is 404.
- The child is started with `multiprocessing`'s `spawn` context on every platform. It
  writes the mesh as NumPy arrays under fixed names into a temporary directory the
  server made (`tempfile.mkdtemp`); the server reads them back and removes the directory
  before it reports the job done, after a cancel or a failure, and when the server exits.
  No path comes from a request.
- The mesh answer has the display answer's frame, `faces` (with the mesh's triangle
  range per face), `regions`, `selections` and `tags`, and in place of the display
  triangles the mesh's surface only: `positions` (float32), `indices`, `triangle_faces`
  (the complex face id), `triangle_regions` (int32 index into `region_names`: the plus
  side's region, else the minus side's), `edge_indices` (uint32 pairs) with `edge_faces`,
  and `stats`. The tetrahedra stay on the server.

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
| W12 | first view at 1440 × 900 and 390 × 844: no console error, no CSP violation, canvas visible and not empty, no horizontal scroll at 390, faces list reachable by Tab; screenshots kept | all hold | all hold (faces list after 17 Tabs; 18 since the **Mesh** button, rerun 2026-11-27) | same |
| W13 | keyboard only: rotate, an axis view, select `via.z1` from the faces list, with no pointer event | complete | complete, 0 pointer events | same |
| W15 | SHA-256 of the display answer over 3 fresh server processes | identical | identical | `tests/simcase/test_studio_model3d.py` |
| W8 | Cancel: a mesh job estimated ≥ 60 s (the card at 0.28 µm: about 69 s), cancelled 3 s after it starts, on a real server process | the child process has exited 2 s after Cancel; no result is kept; server RSS within 50 MB of before | all hold | all hold, 3 of 3 runs (RSS +0.2 MB; no file left) | `tests/simcase/test_studio_mesh3d_job.py`, CI job `studio-mesh3d-w8` (main pushes and manual dispatch) |
| W9 | Estimate: the card at 0.5×, 0.99× and 1.5× the limit | `I-MESH-ESTIMATE` answered before meshing; the 1.5× document refused before a process starts | 3/3 | 3/3 | `tests/simcase/test_studio_mesh3d_job.py` |
| W12 (mesh view) | first mesh view of the card at 1440 × 900 and 390 × 844: no console error, no CSP violation, mesh canvas visible and not empty, no horizontal scroll at 390, faces list reachable by Tab; screenshots kept | all hold | all hold (faces list after 5 Tabs) | `tools/studio_browser/model3d_mesh_browser.mjs` |
| W6-E1 | E1 (three slab layers, the extrude route) through `POST /api/model3d/run` against `meshine.extrude` + `galerkin.solve_steady_heat_3d` called directly: SHA-256 of nodes, tetrahedra, temperature and reaction heat rate | identical | identical | `tests/simcase/test_studio_heat3d_run.py` |
| W6-card | the `layer-stack-3d` card (meshloom route, a via source) through the route against `build_mesh3d` + `solve_steady_heat_3d` called directly: the same SHA-256 | identical | identical | same |
| W7 | E1 through the route against `refsol.thermal3d.layered_slab` (exact for P1): max nodal \|T_h − T\|; relative error of the top heat rate (`heat_rate_by_selection.z1`) | ≤ 1e-10; ≤ 1e-9 | 1.4e-12 K; 2.5e-11 | same |
| W17 | the cut of E1 against an exact P1 slice computed in rational arithmetic (`fractions.Fraction`): same points, max \|T − T_exact\|; six planes (z on the 1 mm interface, z = 1.2345 mm, x = 3.3, y = 7.1, the faces x = 0 and z = 2.5 mm), extrude and meshloom routes, and `cut.csv` through the route at z = 1.2345 mm | ≤ 1e-12 K | 2.8e-14 K worst (0 on node planes) | `tests/simcase/test_studio_heat3d_slice.py`, `test_studio_heat3d_run.py` |
| W8-run | Cancel during a run's mesh step: the heat card at 11 µm (estimate about 69 s), cancelled 3 s after the run starts, on a real server process | the child has exited 2 s after Cancel; the run is cancelled and keeps nothing; no file left | all hold | `tests/simcase/test_studio_heat3d_run.py`, CI job `studio-mesh3d-w8` |
| W14 (run) | time and size of the surface map and of a z cut, server side | recorded | below | `tests/simcase/test_studio_heat3d_run.py` (the largest with `OPENPHYSICS_STUDIO_W14=1`) |
| W1 (shapes) | C1, C4, C5, C11 and card 2 drawn by `display_shapes3d`: (a) a triangle without its face id, or a face whose name set is not its exact surface's (table written from slice 3's tags); (b) a planar face's vertex off its plane (exact, pm before float32) | (a) 0; (b) 0 | 0; 0 (C1 52,020, C4 1,024, C5 19,232, C11 94,420, card 2 1,024 triangles) | `tests/simcase/test_geometry_display3d.py` |
| W2 (shapes) | display areas against the exact ones, s(x) = sin x / x: rectangles; a disc's inscribed n-gon; an annulus; a cylinder side's prism; a sphere's inscribed grid, ρ_f the drawn triangles' circumradii | rectangle ≤ 1e-6; disc deficit ≤ 1 − s(2π/n); annulus excess ≤ πr²(1 − s(2π/n)); side deficit ≤ 1 − s(π/n); sphere 0 ≤ deficit ≤ max(ρ_f/R)² | rectangles 0; C4 (n = 126) disc 4.14e-4, annulus 3.15e-5, side 1.04e-4, each at its bound; spheres 1.18e-4 to 4.56e-4 against bounds 2.24e-4 to 8.63e-4 | same |
| W18 | card 2 through `POST /api/model3d/run`: e_Q = \|Q_h − Q\|/Q (Q_h on z1); Q_h, T and reaction against `build_mesh3d` + `solve_steady_heat_3d` called directly (SHA-256) | ≤ 1e-2 (stage 5 P2's); identical | 7.51e-3 (23,427 tetrahedra); identical | `tests/simcase/test_studio_model3d_shapes.py` |
| W14 | performance at the card at about 48,000 tetrahedra and at 150,000 surface triangles: mesh answer time, mesh view frame time (median of 120 frames), tab JS heap | recorded; gate in Chromium with hardware GL: heap ≤ 300 MB, median frame ≤ 33 ms | recorded below; gate **not run** (software GL only) | same |

W14, recorded on 2026-11-27 in headless Chromium 158 on Linux (Xeon at 2.1 GHz, 4 CPUs, no GPU: the
renderer was ANGLE on SwiftShader, so the hardware-GL gate was not run and is not
claimed). The 150,000-triangle case is a mesh answer made by the script from the card's
display triangles (each split into four until the count is reached) and served to the
page in place of the server's, so that it measures the view at that size:

| Case | Mesh answer | Click to mesh drawn | Median frame (120) | JS heap + array stores |
|---|---|---|---|---|
| card, 0.375 µm: 47,047 tetrahedra, 12,411 surface triangles | 10 ms, 0.73 MB | 11.5 s (meshing included) | 53 ms | 10.1 MB |
| 150,002 surface triangles | 197 ms, 8.9 MB | 1.0 s | 392 ms | 41.1 MB |

W14 (run), recorded on 2026-11-28 on Linux (Xeon at 2.1 GHz, 4 CPUs), through the TestClient:

| Case | Run (mesh and solve) | Surface map | Cut at z = 505 µm |
|---|---|---|---|
| heat card, 40 µm: 6,774 tetrahedra | 2.1 s | 3 ms, 0.10 MB | 24 ms, 0.05 MB |
| heat card, 6.4 µm (estimate 586,395, the largest under the limit): 468,472 tetrahedra | 126 s | 13 ms, 1.77 MB | 123 ms, 0.30 MB |

The run's tests also check the refusals before any process (not the kind, the reader's refusal,
the estimate limit), the 429s, the reuse of a kept mesh without a process (also after **Mesh** of
E1), the unanchored group named by its regions, the probe against the exact slab (1e-10 K) and
outside, the values, the exports' headers and the record; `tests/simcase/test_studio_heat3d_process.py`
(platform-install, Linux, macOS and Windows) cancels a run in its mesh step without HTTP.

The job's own tests also check the 429 answer, that a cancelled job keeps nothing (no
mesh, no directory, a 409 result), that the reuse key changes with the geometry or mesh
block and not with other blocks or key order, that a job in meshloom's non-return (the
thin-strip document) is still meshing long past twice its estimate and ends within 2 s of
Cancel, that a server that exits mid-job leaves no child and no directory, and the mesh
answer (every face meshed on its own plane, faces and names as the display answer's). The
platform-install workflow runs the process-level ones (`tests/simcase/test_studio_mesh3d_process.py`, without an HTTP client) on Linux, macOS and Windows.

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
node tools/studio_browser/model3d_mesh_browser.mjs http://127.0.0.1:8765 out-dir-mesh
```

## Limits

- Boxes and slab layers, as stage 5 slice 1, and cylinders and spheres in meshloom's builder
  shapes; read-only (no feature editing in 3D).
- The mesh is meshloom's (experimental) and its quality is meshloom's. The estimate is
  the engine's T; the actual count differs (the card: 20,160 estimated, 23,652 made).
  The steps are the ones Studio knows; inside meshloom there is no progress to show.
- The kept meshes live in the server's memory and end with it; the model workspace does
  not show the mesh yet.
- A run's solve cannot be interrupted; Cancel during it discards the result when it returns. The
  solve holds the mesh, the solution and its answers in memory for the last eight runs.
- Cylinders and spheres are drawn by the display rule, not from an exact complex: the drawing is
  within the rule's subdivision of the exact shape and the mesh within its size; only meshloom's
  builder shapes are taken, and Use for → New selection does not take their faces yet.
- A component holding one `layers` feature (E1) is meshed through
  `meshine.extrude` (by Mesh and Run alike), and `evaluate3d` refuses it; the view takes its complex from
  the public `simcase.display_complex3d`, which builds for it the complex the
  meshloom route would build.
- Each request evaluates the whole component on the server; the CPU pick visits
  every shown triangle (fine for the few hundred of these documents).
- A section removes one side and draws the outline; cut regions are not capped.
- The canvases are 720 × 504 CSS px from a 1300 px wide window, otherwise the column
  width at 10:7. The browser checks ran in headless Chromium on Linux only, with software
  GL; the mesh view's frame time with hardware GL is not measured here.
