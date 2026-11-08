# Geometry lab in Studio (experimental)

**English** | [한국어](../../locales/ko/pages/packages/simcase/geometry_lab.md)

[Documentation home](../../README.md)

Status: **experimental.** The geometry lab is a separate Studio page at
`/geometry-lab`. It works directly on a document with a version 1 geometry
block ([contract](geometry_document.md)) through the
[exact 2D engine](geometry_engine.md). It is the first step of letting Studio
read version 1 documents; the [model workspace](workspace.md) at `/workspace`
and the classic page at `/` are unchanged and do not link to it. Its page and
its HTTP answer may change in any release.

## Use

Start Studio as usual and open the page:

```sh
python -m simcase.studio            # then open http://127.0.0.1:8765/geometry-lab
```

- **Start from** one of the shipped examples
  (`examples/simcase/geometry_v1_soi_strip.json`,
  `geometry_v1_imprint_rib.json`, built into the page), a new one-rectangle
  document, or **Open file** with any JSON document.
- **Parameters** are listed with their evaluated value. A parameter written as
  a plain number with a `range` gets a slider, whose step is a power of ten
  (at least 200 steps over the range) so that saved values stay short decimals;
  every parameter has a text field that takes a number or an expression
  (`2 * t + 0.1`). A number a double cannot hold (`1e999`, `1e-400`) is refused
  in the page and the field returns to the value the document holds.
- Every edit sends the whole document to the server, which parses it and
  evaluates one component. The drawing shows the cells filled by region (void
  cells unfilled) and every curve; arcs and circles are sampled for drawing
  only. Click a region, a named selection or a boundary tag to highlight its
  cells or curves; the highlight follows each new answer by name. **Engine listing** is the text `python -m simcase geometry`
  prints for the same document.
- A document the engine refuses keeps the last accepted drawing, dimmed, and
  shows the engine's message unchanged; it names the feature, selection or
  parameter (for example `feature 'bow': its boundary crosses itself …` or
  `component 'xs': selection 'gold' selects nothing`).
- **Component** chooses among several components; without a choice the first
  `2d` or `axisymmetric` one is shown. A `3d` component is refused by name.
- **Save JSON** downloads the document as edited (two-space JSON). Nothing is
  stored on the server.

The lab runs no physics. Run a saved document with `python -m simcase run` or
the routes of each physics page.

## What it sends and answers

`POST /api/geometry-lab/evaluate` takes `{"doc": <document>, "component":
<name or null>}`. It reads only the `units` and `geometry` blocks, as
`python -m simcase geometry` does, so a document without physics is accepted.
The answer is `{"ok": true, ...}` with the component's cells, curves (points in
the document's length unit), regions with areas, selections with their entry
indices, boundary tags, parameters (written and evaluated), roundings and the
engine listing, or `{"ok": false, "refused": <message>}`. It is a view for this
page, not a persisted format, and it is not part of the document contract.

The page loads only its own files from `/geometry-lab-assets/`: no inline
script or style and no other origin; the page response carries a
`Content-Security-Policy` with `script-src 'self'`. Studio reaches the engine
through the public names `simcase.parse_geometry`, `simcase.evaluate_geometry`
and `simcase.GeometryError`.

## Checks

Registered before the page was written:

| Check | Where |
|---|---|
| GL-1 the engine listing equals `python -m simcase geometry` for both examples; regions, selections, curve provenance and tags equal the engine's | `tests/simcase/test_studio_geometry_lab.py` |
| GL-2 after a parameter edit (three values in the range, and an expression) cell areas, vertices, curves and selections equal a fresh engine run, compared with `==` | same |
| GL-3 refusals carry the engine's message: a self-crossing path, an arc end off its circle, a `3d` component, an empty selection, a parameter cycle, a 0.2 block (the CLI's words) | same |
| GL-4 the saved text parses back to the edited document and the same model | same, and the browser check |
| GL-5 real browser: both starters, slider and text edits, a refusal and a save, with no console error and no policy violation | `tools/studio_browser/geometry_lab_browser.mjs` (local; needs Playwright, not in CI) |
| GL-6 the page's pure helpers | `tests/simcase/studio_geometry_lab.cjs` |
| Drawing data against the document itself: sampled arc and circle points lie on their circles and run counter-clockwise, drawn loops enclose the engine's areas within 2e-3, lengths and areas in nm, µm and mm | `tests/simcase/test_studio_geometry_lab.py` |
| GL-7 `/` and `/workspace` do not load or link the lab; the lab's module imports only public names | `tests/simcase/test_studio_geometry_lab.py` |

## Limits

- 2D and axisymmetric components only (the engine's scope); no editing of
  features or selections yet, only parameters.
- Each edit re-evaluates the whole component on the server; the engine's
  measured times are in the [engine's validation](geometry_engine.md#validation).
- Not linked from the pilot pages, and not covered by the installed-wheel
  browser check.
- Written for the local Studio server. A refusal returns only the reader's or
  engine's message, which is built from the submitted document; any other
  error is a generic 500 without exception text (tested). Serving Studio to
  other people would also need limits on request size and evaluation time,
  which this page does not set.
