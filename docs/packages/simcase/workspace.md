# Experimental model workspace

**English** | [한국어](../../locales/ko/pages/packages/simcase/workspace.md)

Start `simcase-studio` with the optional `simcase[studio]` dependencies installed,
then follow **Open experimental model workspace** from the home page, or open
`/workspace` on the same local server. The existing optical and heat editors
remain at `/`. No separate proxy, JavaScript build, CDN or new dependency is needed.

## Working with a model

Choose an application, select a body or boundary in the model tree or drawing,
and edit its properties in the inspector. The optical application runs a real
2D mode calculation. The heated-waveguide application is a setup preview: its
coupling diagram, voltage and mechanical selections do not run coupled physics.

The optical adapter accepts a Si or SiN rectangular core in silica, with width
300–900 nm and height 100–500 nm. Wavelength is fixed at 1550 nm, core mesh at 30 nm,
the window at [-1.5, 1.5, -1.2, 1.2] µm, PEC boundaries and two candidates.
These fixed settings are visible with the result. Use the existing editor for
other supported optical studies; this workspace does not expose all engine APIs.

Invalid numeric drafts stay visible across navigation. Resolve or discard them
before saving, opening or running. Undo/redo keeps up to 60 edits; result input
restore creates a new edit. Panel widths can be adjusted on wide screens and
are stored in this browser. Revisions identify local editing order, not Git commits.

The model drawing has Zoom in/out, Pan and Fit view controls. Focus the drawing
and use +/−, arrow keys or Home. Zoom is limited to 100–400%; each view retains
its camera while navigating this tab. Heated-waveguide views remain schematic. The optical-only view shows a
2D cross section with equal x/y scale and dimensions in nm. Its core rectangle
and domain come from the same geometry contract as the submitted document: core
y = 0 to the chosen height, centered in x; window x = ±1500 nm and y = ±1200 nm. Only the
core and silica background appear, without a heater or perspective projection.
Select Boundaries to inspect the four fixed PEC edges; these are read-only
optical conditions, not thermal/mechanical assignments. This is not a CAD editor. Camera changes do not change inputs, edit
history, saved files or computed fields.

In optical Geometry / Bodies, drag either highlighted core edge to resize symmetrically. A dashed preview does not change the model until release; Escape or pointer cancellation discards it. One completed drag creates one undoable edit. Width is bounded to 300–900 nm and drag updates snap to 1 nm. Focus a handle and use arrow keys (10 nm, Shift: 1 nm) or Home/End. Invalid numeric drafts block resizing.

Resizing uses the drawing transform captured at gesture start, so zoom and pan do not change the unit conversion. The release position is applied even if no final move event arrives. Window resize, focus loss and page hiding cancel the preview; invalid inputs are checked again before committing.

Height is edited numerically in the Geometry inspector or by dragging the top
edge (100–500 nm, 1 nm snapping). The bottom remains at y = 0. Use Up/Down
(10 nm, Shift: 1 nm) or Home/End on the top handle. Height supports undo/redo
and the same preview, cancellation and invalid-input rules as width.
The drawing, width handles and submitted mesh use the same height.

## Results and files

The notebook retains the last six successful runs. Select a candidate to inspect
its field or compare two runs. Candidate indices are not a mode-tracking result.
Field colours use the vector magnitude normalized separately per candidate;
they do not represent optical power or a common physical colour scale.

Save input JSON to keep the design, or save session JSON to include validated
results. Open restores these files; input-only files are limited to 64 KiB and
sessions to 16 MiB. CSV and PNG exports are available. These version-2 workspace
formats are separate from headless simcase JSON documents. Reloading does not
automatically restore a notebook: save a session first.

Version-1 inputs and sessions remain readable: their fixed core height becomes
220 nm. New files record height and its nm unit explicitly; older editors reject
version 2 instead of silently ignoring height. Each result retains its captured
height, including field outlines, comparisons and CSV/PNG exports.

The workspace checks `/api/workspace/capabilities/v2` before enabling Run. Contract
version 2 and adapter `optical-rectangle-v2` declare the 100–500 nm height range
and the fixed settings above,
`optical: true`, `coupled: false` and `simcase_version`. A missing or incompatible
contract blocks execution; **Check connection** retries. Each submitted run
captures its core height and the reported simcase package version and preserves it in session JSON.
The original capability endpoint remains available for fixed-height clients.
This is not a complete engine dependency or Git provenance record. Older
version-1 sessions without this field remain readable with unknown provenance.

## Scope and validation

This is an experimental editor, not a CAD system or a general multiphysics
solver. Optical absorption → heat → deformation and geometry feedback are not
connected here. Geometry drawings and coupling cards do not establish physical
validation. No solver or numerical acceptance threshold is changed by this UI.
Keep the server local, as described in the [package overview](overview.md).

Relevant checks from the repository root:

```bash
node --test tests/simcase/*.cjs
python -m pytest -q tests/simcase/test_studio_workspace.py tests/simcase/test_studio.py
```

The workspace tests cover version/settings negotiation, input drafts, edit
history, notebook/session validation, field data and HTTP assets. Distribution
checks also run workspace JavaScript tests against copied installed assets.
These checks do not replace the required full CI or independent physics validation.

## Input recovery and material review

Valid input edits are saved automatically to a separate browser recovery record.
After reloading, **Recover recent inputs** offers a confirmed replacement; it
never runs a calculation. This is one latest record per browser origin, shared
by its tabs. Invalid drafts, completed fields and undo history are not recovered.
Recovery does not mark a file as saved. Storage failures are shown with a file
save alternative; keep session files for durable results and comparisons.

The optical Materials inspector offers silicon/silicon nitride for the core and
silica for the background. Unsupported imported assignments remain visible and
block execution until corrected. These choices reach the optical solver;
heated-waveguide assignments remain setup labels. Study summarizes the current
core dimensions and materials with links back to their editors.
