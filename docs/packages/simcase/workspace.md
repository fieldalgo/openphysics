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

The notebook retains up to six successful runs, preserving pinned references. Select a candidate to inspect
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

## Running, stopping the wait and resuming

The job panel shows the submitted dimensions/material, job ID, elapsed time and
result-loading state. **Stop waiting** stops browser polling only; the optical
server continues its computation. **Resume job** retrieves that same job with
its captured inputs, even after editing the current design or reloading the
same tab. The pending-job record uses session storage, separately from input
recovery and saved session files. Storage failures are reported. A server
instance identifier prevents resuming a job against a restarted server.

Only one job is tracked per tab. Resume or **Detach job** before starting another.
Detaching forgets this tab's job reference and does not cancel server work.
Polling stops after three minutes and can be resumed; failed requests do not
replace existing results. Late responses after stopping are ignored. The panel
reports elapsed time rather than inventing a completion percentage. No server
cancellation or durable server job persistence is implemented. Save completed
sessions before restarting the server or closing the tab.

## Inspecting field samples

In Results or Compare, click inside a field plot or enter x/y coordinates in µm
and select **Inspect point**. The crosshair and readout use physical coordinates.
Compare samples both meshes at the same location. The value is the normalized
stored centroid sample of the containing triangle, not an interpolated point
field. The readout identifies that triangle and its centroid; a point outside
the captured mesh reports no sample. At shared edges, the last drawn triangle
is chosen consistently. Degenerate cells are ignored.

Candidate/component changes update the readout with the same vector-normalized
scale used by the plot. **Clear point** removes the marker. Probe selection is
view state for the current tab and is not stored in session JSON. Field PNG
exports include the marker and its coordinates when selected. These samples do
not establish convergence or physical field amplitudes.

## Naming and preserving runs

Use **Selected run name** and **Rename run** to label a completed calculation
(up to 80 characters). Names appear in history and comparisons, persist in
session JSON and CSV, and never change captured inputs or fields. **Save selected
run** exports a standalone session containing that result and its original
inputs; this is useful before the six-run retention limit removes an older unpinned run.
The footer distinguishes a changed session from saved input-only files. Saving
inputs or a browser draft does not claim to save the result notebook. A selected
run export does not mark the full notebook saved.

Undo/redo applies to design inputs. Outside text fields, Ctrl/Cmd+Z undoes and
Ctrl/Cmd+Shift+Z or Ctrl+Y redoes. In text fields, native text editing is retained.
Run names and comparison choices are session metadata, outside input undo.

## Mesh preview and active interfaces

For an optical model, choose **Mesh → Generate mesh** to call the existing
server mesh builder without solving modes. The preview shows actual triangles,
region colouring, node/triangle counts, minimum angle and mean quality. Select
Full window or Core region; coordinates are in µm with equal x/y scale.
Changing the design leaves the prior preview visible with an earlier-input
label until explicitly regenerated. Failed generation preserves the last good
preview. Mesh previews live only in the tab and are not saved in session JSON.
The optical solve builds its own mesh using the same input contract; previewing
is not mesh reuse or a convergence certification.

An optical-only model tree shows Geometry, Materials, Optical modes, Mesh and
Study. Connections explains that no coupled interfaces are present and links
back to application choice. The heated-waveguide template retains the broader
setup tree and still cannot execute coupled physics.

### Guided optical workflow

The Geometry, Materials, Mesh, Study and Results bar follows the current inputs.
It identifies invalid drafts, unavailable execution, a pending job, and mesh or
results captured from earlier inputs. A mesh preview is optional: Run creates its
own mesh. Ready to run is an input/connection state, not numerical validation or
convergence certification. Results opens the newest retained matching input when
one exists; navigation itself never runs a solver. Earlier results remain available.

Connection details, input recovery and layout help are grouped in an expandable
panel. A connection failure opens it automatically. Numeric error descriptions
are separate from their field labels; workflow buttons retain keyboard focus as
status labels update. The workflow is shown for the optical application only.

### Check and export the submitted document

Study → Check inputs calls the public document validation endpoint without meshing
or starting a job. The report retains its input snapshot and server identity;
editing inputs or reconnecting to another server makes the report earlier evidence.
A transport failure retains the previous report alongside the new error. Validation
acceptance is not material-accuracy, mesh-convergence or solver acceptance. Run
always validates its own captured document again.

Export solver JSON downloads the actual simcase `openphysics: "0.2"` input with
lengths in micrometres. It can be read by the simcase Python/CLI APIs; it is not a
workspace project/session and does not contain computed results. The expandable
solver document shows the same payload; with an invalid editor draft it shows the
last valid inputs and export is disabled.

Workspace validate, mesh and run requests carry the connected server instance.
A restarted/different server rejects stale requests before parsing the model or
starting a job. Check connection before new work; old jobs do not migrate between
server processes. Classic callers without an instance query keep their existing API.

### Line profiles

Results and Compare include an expandable Line profile and CSV panel. Choose a
horizontal line (constant y) or vertical line (constant x), enter its fixed
coordinate in micrometres, and select Show profile. Both comparison runs use the
same line and 0–1 relative scale; each candidate retains its own max|E| denominator.
Changing candidate/component updates the profile. Line choices are tab-local view
state, not saved session settings.

Each plotted step is the stored centroid value of the triangle intersected by
that interval. There is no field interpolation, smoothing, absolute-power estimate
or mode tracking. Shared/coincident edges follow the last painted triangle; mesh
gaps remain gaps. CSV exports interval endpoints, triangle number, centroid,
normalized value, job, origin and candidate/component. Values at an interval's
isolated endpoints are not a separate point-probe claim.

Analytical unit-square tests cover exact horizontal/vertical intervals, reversed
winding, overlaps and empty regions. Actual exported comparison intervals were
independently checked against complex vector norms and triangle containment.

### Automatic notebook recovery

Once the tab has completed or imported results, valid input/selection/name changes
queue a browser IndexedDB snapshot containing the current inputs, up to six
completed runs, names, comparison and field view. Writes are debounced and serialized;
the footer reports pending, saving, committed or failed storage separately from
portable file save status. An empty new tab does not erase the prior notebook.

After reload, expand Connection, recovery and layout help → Recover last session.
The complete record is validated before the existing replacement dialog; recovered
fields are labeled `recovered`, not newly computed. Recovery starts a new input
undo history and keeps the document unsaved until you save a file/session. No
solver is started. Input-only recovery and pending-job recovery remain separate.

This is the latest single snapshot for the browser origin, shared across tabs;
another tab's later snapshot can replace it. It is not a backup archive. A quota or
transaction failure retains the previous committed record; Retry recovery storage
retries the latest requested state. Closing the tab while pending/saving can lose
recent changes. Browser cleanup/private mode or a different port can make recovery
unavailable. Use Save session / Save selected run for portable files. The 16 MiB
session and six-result limits still apply; invalid drafts, undo history, mesh,
preflight reports, probe and profile positions are not included.

### Pin reference runs

Pin selected run protects that result from automatic notebook eviction. A new
result replaces the oldest unpinned run, with at most six retained in total. If
all six are pinned, Run is disabled until one is unpinned; document checks and
mesh previews remain available. Pins are saved in sessions, browser recovery and
the CSV run table. They do not alter inputs, fields or the input Undo history.
Repeated retrieval of the same job preserves its existing name and pin. A failed
retention operation leaves the previous notebook and selected result intact.
Pinning is not a portable backup; export files before discarding browser data.

### Import runs without replacing the model

Results/Compare → Import runs from file accepts a session or selected-run file.
Review the number of new, matching and replaced unpinned runs before applying.
Current model inputs and input Undo are preserved; the imported selection opens
beside a retained result for comparison. Imported runs remain labeled `imported`.
Use Open session when you intend to replace both inputs and the notebook instead.

Matching job IDs retain their current names, pins and provenance only when their
input, settings, effective indices, field arrays and server version agree. A
conflicting payload rejects the whole import. Incoming runs and pinned references
are never silently dropped to fit the six-run limit; if they exceed capacity,
unpin a reference or export/import a selected-run file. Older unpinned current
runs may be replaced after the review. Pending jobs block run imports.
