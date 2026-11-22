# Experimental model workspace

**English** | [한국어](../../locales/ko/pages/packages/simcase/workspace.md)

Run `openphysics` (installed with the `openphysics` distribution) or, with the
optional `simcase[studio]` dependencies, `simcase-studio --workspace` to open this
workspace directly in your browser.
For another port, use `simcase-studio --workspace --port 8770`; add `--no-browser`
to print the address without opening a browser.
You can also follow **Open experimental model workspace** from the classic home
page, or open `/workspace` on the same local server. The existing optical and heat editors
remain at `/`. No separate proxy, JavaScript build, CDN or new dependency is needed.

New to the workspace? Start with the [quick start](workspace_quickstart.md). For build reviews and first-user checks, use the [acceptance checklist](workspace_acceptance.md).

## Workspace layout and visual foundations

The workbench has a command ribbon, a model builder and adjacent Settings panel
on the left, a large Graphics workspace on the right, and a Study/Messages dock
below. The ribbon groups Project, Edit, Model setup, Physics and Compute. **Geometry**,
**Materials**, **Mesh** and **Study** open the same settings as the model tree.
**Physics → Installed** opens [Installed physics](#installed-physics). Compute holds
the run command of the chosen application: **Run optical study**, **Run heat study**
or **Run Joule heating study**. The optical workflow strip shows the current step
without hiding the model. The dock shows the study sequence and Messages; after a
Joule heating run, Results adds its **Solver log** there.

**Save session** and **Open session** keep the whole session, including completed
optical runs and comparisons; "Save session" is the one name for that save in the
ribbon, the header and Messages. **More** contains input-only files (**More › Save
inputs only**, **Open inputs file**), browser drafts and Reset design. **Workspace tools** in the bottom status bar contains connection,
recovery and Reset layout; **Installed physics** sits next to it. Both open above the
status bar, one at a time, on every page including Models; Escape closes the open
one. Below 1000 px the ribbon leaves out the Physics group, so its Compute commands stay in
view; Installed physics remains in the status bar. Heat and Joule heating
results remain in the current tab only.

Settings and Graphics scroll independently on wide screens. The default
Model builder/Settings widths are 240/320 px; saved widths are retained. Drag
either divider right to widen its panel, or focus it and use Left/Right;
Shift uses larger steps and Home/End reach the limits. At narrower widths,
the settings and tree appear above Graphics; on phones the panels stack.
Position and size inputs are paired to keep the core dimensions visible.

The local CSS uses light neutral surfaces, blue selection, system fonts and
compact square controls: 13 px base text, 13 px input labels, 18–20 px view
headings and 32 px numeric inputs. Small ribbon/status labels have separate
roles. Tokens live at the top of `workspace.css`. Focus outlines, a skip link,
textual statuses and native form controls are retained. The shell and line
icons are authored locally, with no new runtime dependency, font download or CDN.

**Connections** retains the one-way setup diagram with labeled ports and curved
wires. Selecting a node, port or physics tree item opens its settings. Heat-source
wires are rose, temperature wires amber and geometry updates use dashed purple
wires. Excluded interfaces lose their dependent wires, and wires follow the
ports when panels resize. Small screens scroll the graph horizontally.
Ports inspect settings; arbitrary wiring, field transfer and coupled execution
remain unavailable. Single-physics optical and heat studies retain their existing
solver contracts. For the Joule heating application the diagram shows its two
interfaces, Electric currents and Heat transfer, solved together by one study (the badge
names `joule.steady2d` or `joule.temperature2d`): a rose Joule heat → heat source wire,
and, when a used material has σ(T), an amber temperature → conductivity wire that
returns below the nodes. It has no interface checkboxes; the wires cannot be rewired.

## First optical study

1. Choose **Models → Optical waveguide** (the start page; its tab is **Models**). (The Heated
   silicon waveguide card opens a coupled heat and optical model instead; see [Multiphysics models](#multiphysics-models-heat--optical-modes).)
2. In **Geometry**, edit the core numerically or drag it and its edges. Add
   rectangles, circles or polygons for slabs, slots, claddings or holes, and choose
   each shape's material; the silica background stays. A rectangle's **Width** edit
   keeps its horizontal centre (Left x moves by half the change) and a **Height** edit
   keeps its bottom edge, so a core resting on y = 0 stays centred there; the window
   rule still refuses a size that would leave the window. Projects saved earlier keep
   their stored coordinates. The step bar's **4. Study** shows *Ready to run*, and *Run
   complete* once these inputs have a result; next to it the wavelength (for example
   **λ 1550 nm**) is a button that opens the wavelength field. Optionally set the
   wavelength in **Physics › Optical modes** (its settings are headed *Optical modes*;
   **Study → Edit wavelength**, **Edit in Optical modes** under the Study's execution
   settings, which show the wavelength too, and the step bar's wavelength open that one field
   focused) and the core mesh size in **Mesh**.
3. Optionally generate **Mesh** and review **Study → Check inputs**. These actions
   do not calculate optical fields. Inspect or export the solver JSON if needed.
4. Select **Run optical study**. Results keep the inputs used by that run,
   even if you edit the model while waiting. Stop waiting pauses observation only.
   An input edit replaces the completion message, so it never describes edited inputs.
   The dock heading and the status bar name the same run: after a run *Run 1 · solved from
   the current inputs* (the status bar adds *press Run to solve again*), after an edit
   *Inputs changed since run 1 · press Run to update*, and before any run *Nothing is
   computed until you press Run* and *Optical adapter ready · explicit Run required*. A run's
   number is its place in the run list, the oldest first. While something holds Run (input
   errors, a computation or job in progress, an unsupported input), the heading repeats the
   status bar's words instead.
5. Type a **Run name** and press Enter: a named run is pinned, so new runs do not
   replace it. There is no separate Pin button: **Unpin this run** releases a pinned run,
   and Enter in Run name pins a named run again. Change the model and run again,
   then use **Compare** to choose A/B, candidate, component, probe and line profile.
   The two field plots come first, headed by the side and the run (a run named *A* on side
   A is not named twice); below them a table lists, for each candidate rank, n_eff of A
   and B, Δ (B − A) and Δ % of A; its column headers name each run (name, size, λ).
   n_eff has 8 decimals everywhere (results, candidate list, Compare).
6. **Save session**, the first save button, creates a portable file with the model,
   retained results and view settings, named from the application and the local
   date-time (for example `optical-waveguide-session-2026-11-21-1305.json`) in the
   browser's downloads. Studio hands the file to the browser and cannot know that it was
   kept (a download can be cancelled), so Messages reports *Session file … sent to the
   browser's downloads (check your Downloads folder)*. The header holds the one save
   indicator, and the footer repeats it word for word: *Session file … sent to your
   browser's Downloads · time* until the next edit or run; it never says the file was saved. **More › Save inputs only** keeps the model without
   results; while completed runs are not in a session file, the indicator says *Not saved
   to a file · kept for recovery in this browser* (*· updating browser recovery* while it
   writes, *· browser recovery unavailable* if it cannot), or *Changed since session
   file … (time) · kept for recovery in this browser* after a file save.
   After **Open session** the header says *Opened …* with the file name, and after a
   recovery *Recovered from this browser*; browser recovery keeps the last session file
   name and time, so a recovered session adds *last session file … (time)* (*changed
   since session file …* if it had changed after that save, *not saved to a file* if none
   was saved). Both last until the next change or another open. The header has no revision counter. A Width edit by an odd
   number of nanometres gives a half-nanometre Left x: the centre is kept exactly, Messages says
   where Left x moved (*Width set to 600 nm. Left x moved to −300 nm to keep the centre.*), and
   typed values are not snapped to the drag step (**More about width and height** under
   the size fields). Wait for *kept for recovery in this browser* before relying on local
   recovery (**Workspace tools** shows when it was last updated). After a reload or a
   Studio restart, the start page shows **Continue where you left off** with
   **Recover (this browser only): Last session in this browser …** and any earlier ones,
   **Open session file (portable)…** and **Start new**, and says that a session file is the
   copy that moves between computers; browser recovery stays in this browser. Over a workspace with default
   inputs and no results, an open or recovery asks nothing. Otherwise **Open saved
   session?** (or **Recover saved session?**) lists the runs with their names and pins
   and the comparison that come back, what is replaced, and only the physics present.
   Before a model is chosen, the header reads *No model chosen*, the status bar
   *Choose a model to start* and the Study sequence lists no steps. A model just chosen
   reads *New model · not saved* until its first edit, then *Unsaved inputs*. The start
   page says what choosing does: it sets which physics the model solves, keeps the
   dimensions you entered and the runs you completed, and Undo takes it back. The start page uses
   one word, model: the **Models** tab, *Choose a starting model*, *Model library ·
   Choose a model*.

Use **Add runs from file (inputs unchanged)** to add results to the current notebook while keeping
the model. Use **Open session** to replace both model and notebook. *Result for these
inputs* and *Inputs changed since this result* say which design a result belongs to; candidate ranks do not
establish mode correspondence between designs.

## Working with a model

Choose a model, select a body or boundary in the model tree or drawing,
and edit its properties in the inspector. The optical application runs a real
2D mode calculation. The Heated silicon waveguide application runs steady heat and
optical modes as one coupled model ([Multiphysics models](#multiphysics-models-heat--optical-modes)). An older input
file with all four interfaces on opens the earlier conceptual preview, whose diagram,
voltage and mechanical selections run nothing.

The optical adapter accepts up to eight shapes inside the window x = ±1500 nm,
y = ±1200 nm: rectangles, circles and polygons with 3–12 vertices in a silica
background. Each shape is silicon, silicon nitride, silica, air, sapphire, lithium
niobate, indium phosphide, gallium arsenide, calcium fluoride or magnesium fluoride,
with lossless physmat data across 1400–1700 nm. Sapphire, lithium niobate and
magnesium fluoride are uniaxial crystals; the workspace uses their ordinary index
as an isotropic material, so it does not model birefringence or crystal
orientation. At least one shape of a material above the silica index (silicon,
silicon nitride, sapphire, lithium niobate, InP or GaAs) is needed to guide light. Shapes are drawn in list order and
**later shapes win where they overlap**, as in the simcase geometry contract; for a
rib, draw the slab first and the ridge after it. Rectangles and polygons are
submitted as their corner coordinates, so shapes that share an edge in nm share it
exactly in the solver document. Set the wavelength (1400–1700 nm) in
**Optical modes** and the core mesh size (20–60 nm) in **Mesh**; new models start
with one 500 × 220 nm silicon core at 1550 nm and 30 nm. The core mesh size applies
to those guiding materials; silica, air, CaF2 and MgF2 shapes use the graded
background mesh. The window is fixed at [-1.5, 1.5, -1.2, 1.2] µm, with PEC
boundaries and two candidates. Each result shows the shapes, wavelength and core
mesh it used.

Material indices are evaluated at the chosen wavelength; the lower limit stays
inside the silicon data range. A coarser core mesh is faster and gives smaller
session files, but changes n_eff: for a 500 × 220 nm silicon core at 1400 nm,
20 nm and 60 nm meshes differ by about 0.01. Compare designs at the same mesh
size, and refine the mesh to judge whether a difference is resolved. The fixed
window and PEC edges matter more at longer wavelengths and for small cores; these
settings do not certify mesh or window convergence. Large silicon or silicon nitride
areas at a fine core mesh take longer and produce large results: a silicon block
filling the window at 20 nm took about 22 s and returned 14 MB in a Linux check, so
a session with several such runs can exceed 16 MiB. Export single runs instead (**Export this run**). Use the existing editor for
other supported optical studies; this workspace does not expose all engine APIs.

Invalid numeric drafts stay visible across navigation. Resolve or discard them
before saving, opening or running. Undo/redo keeps up to 60 edits; result input
restore creates a new edit. Panel widths can be adjusted on wide screens and
are stored in this browser. Input revisions count edits in this tab only; they are
not shown in the header and are not Git commits.

The model drawing has Zoom in/out, Pan and Fit view controls. Focus the drawing
and use +/−, arrow keys or Home. Zoom is limited to 100–400%; each view retains
its camera while navigating this tab. The conceptual preview remains schematic. The optical-only view shows a
2D cross section with equal x/y scale and dimensions in nm, drawn from the same
shapes as the submitted document: every shape in draw order over the silica
window x = ±1500 nm, y = ±1200 nm. The view opens fitted to the window; **Fit view**
returns there and **Fit shapes** zooms to the current design. A faint grid marks
every 100 nm, with stronger lines every 500 nm; it is for reading positions only. Select Boundaries to inspect the four fixed PEC
edges; these are read-only optical conditions, not thermal/mechanical assignments.
This is not a CAD editor. Camera changes do not change inputs, edit history, saved
files or computed fields.

In optical Geometry, the inspector lists shapes in draw order. Add, duplicate,
delete or move a shape earlier/later; rename it and choose its material. Edit
rectangles by left x, bottom y, width and height, circles by centre and radius,
and polygons as one `x, y` vertex per line (applied when the field loses focus;
edges may not cross or touch). Values outside the window or below 10 nm stay as
invalid drafts that block saving and running; another shape cannot be selected
until they are corrected or restored.

**Align** moves the selected shape so its bounding edges meet exactly: centre it on
x = 0, rest it on y = 0, or place it left of, right of, on top of or below a
reference shape, or centre it on that shape. Touching edges are then identical in
the submitted document. An alignment that would leave the window is refused and
the shape stays. **Drag step** (1, 5, 10 or 50 nm) sets how far a drag moves and
the grid edges and vertices snap to; it is a view setting, not part of the model.

With Bodies selected, click a shape in the drawing to select it. Drag the selected
shape to move it, drag a yellow handle to move one rectangle edge, a circle
radius or a polygon vertex, and release to apply. Dragging follows the drag step (5 nm by default); with the
shape or a handle focused, arrow keys move by 10 nm (Shift: 1 nm). A preview does
not change the model until release; Escape, pointer cancellation, window resize,
focus loss and page hiding discard it. Moves are clamped to the window, and each
completed gesture is one undoable edit. The drawing transform is captured at
gesture start, so zoom and pan do not change the unit conversion.

## Steady heat plate

Choose **Models → Steady heat conduction** to edit a steady heat problem
without JSON. The plate is one homogeneous rectangle with its lower-left corner at
(0, 0), sized in mm, with constant isotropic conductivity k [W/(m·K)] and a uniform
heat source Q [W/m³]. Select a side in the drawing or open **Heat transfer** to give
each side one condition: insulated (zero flux), a fixed temperature [K], an inward
heat flux [W/m²] (positive enters the plate, as the document's `inward_heat_flux`) or
convection with h [W/(m²·K)] and an ambient temperature [K]. **Mesh** sets the structured divisions along x and y and
shows the node and triangle counts against this server's limits.

Run is enabled when the inputs determine the temperature level (a fixed temperature
or convection with h > 0 on some side), adjacent fixed sides agree at their corner,
and the mesh fits the server limits; the reason is shown otherwise. Invalid values
stay as highlighted drafts that block running and saving until corrected or
restored. **Run heat study** builds a `thermal.steady2d` document (see **Study** for
the exact JSON), validates it through the same public thermal routes as the classic
Studio page and solves it. Results show temperature (P1, interpolated in each
triangle) or heat flux |q|, qx or qy (constant per triangle) on the actual result
mesh with optional flux arrows, minimum and maximum temperature, and the value at a
clicked point. A result keeps the inputs it was computed with; after an edit it is
labelled as an earlier snapshot and **Restore run inputs** brings them back.

Heat inputs are saved in input files, drafts, browser input recovery and undo
history (project version 7, plate lengths in mm, a flux side as its inward heat flux). Heat results stay in the tab:
sessions, run history, comparison and browser notebook recovery remain optical-only.
Transient heat, region-wise or temperature-dependent materials and arbitrary
geometry are not part of this application (region-wise materials with Joule heating are
the [Joule heating application](#joule-heating-on-named-regions)); the classic page keeps the JSON
interfaces for them.

## Joule heating on named regions

Choose **Models → Joule heating** to set up steady Joule heating on named
material regions without JSON. The domain is a rectangle in mm with its lower-left
corner at (0, 0) and a background material; **Geometry** adds up to eight
rectangles, circles or polygons (later shapes win where they overlap), each a named
region of one material. **Materials** holds up to six named materials, each with a
thermal conductivity k [W/(m·K)] and an electrical conductivity that is either a
constant σ [S/m] or the linear resistivity model σ(T) = σ₀ / (1 + α (T − T₀)) with
its reference conductivity, reference temperature, coefficient α [1/K] and valid
temperature range. **Electric currents** gives each side an insulating boundary, a
fixed potential [V] or an inward current density [A/m²]; **Heat transfer** an
insulated boundary, a fixed temperature [K], an inward heat flux [W/m²] or
convection. **Mesh** sets the element size in mm. When a used material has the
model, the study is `joule.temperature2d` and **Study** sets the iteration: the
method, Picard (default) or Newton, the initial temperature and the documented
defaults (relaxation 0.5, relative tolerance 1e-10, 100 iterations, at most Studio's
500) with a temperature tolerance the form starts at 1e-9 K. Newton takes no
relaxation (the field is hidden and its value kept) and at most 17 steps, Studio's
cap: choosing it lowers the limit to 17 at most, and choosing Picard again sets the
limit back to 100. With constant materials it is `joule.steady2d`. The default model is
the two-material strip of the [region Joule checks](electric_joule.md#material-regions-temperature-dependent-joule-heating).

Run is enabled when a side fixes the potential, a side fixes the temperature or has
convection with h > 0, adjacent fixed sides agree at their corner (potential and
temperature), every given temperature lies in the valid range of every model material,
and no heat job holds Studio's one job slot (heat waits for a Joule job the same way); the
reason is shown otherwise. **Run Joule heating study** builds the
document (shown under **Study**), validates it and runs it on Studio's
[Joule routes](electric_joule.md#studio-region-documents), with their region and mesh
limits; a refusal (for example two potentials at one corner, a mesh over the node
cap, an iteration that does not converge) is shown with its text. Results show
temperature and electric potential (P1) or current density |J|, Joule power density
and heat flux |q| (per triangle, with optional arrows) on the actual mesh with
region boundaries in Graphics, the balances (supplied electric power, Joule power,
outward heat, temperature range and the current through each fixed side, per metre of
depth) in Settings, the value at a clicked point, and the **Solver log** in the study
dock: its line gives the method and count ("Picard 31 iterations", "Newton 3 steps"),
the last temperature and conductivity changes and the three power balances, and
opening it lists every Picard iteration or accepted Newton step (|ΔT|, Δσ/σ, maximum T). With constant materials it says the problem was solved once. A result keeps its inputs;
**Restore run inputs** brings them back. Joule inputs are saved in input files,
sessions, drafts, recovery and undo history (version 7; the iteration method is an
optional key, absent meaning Picard, so earlier version 7 files load unchanged, while a
Studio from before the method was added opens a Newton file as Picard without a warning);
Joule results stay in the
tab, as heat results do. A run that ends after you switch to another application waits in
the Joule application; undo keeps following a running job, and opening a file discards its
result. In the multiphysics preview the interface boxes cannot leave electric currents and
heat alone: that combination is the Joule heating application. CI runs this application in a
real browser on Linux, macOS and Windows against installed wheels
([development guide](../../development.md)): Picard and Newton runs of the default model, a
refused Newton run shown with its text, and constant materials.

## Multiphysics models: heat → optical modes

Choose **Models → Heated silicon waveguide** (“Heat → optical modes · coupled”) to open a
[multiphysics document](multiphysics_document.md): two physics on one geometry and one mesh,
joined by a coupling, solved by one **Run**. The template is a 500 × 220 nm `physmat:Si` core on
`physmat:SiO2` in a 6 × 4.5 µm window, with a 2 µm × 100 nm heater 1.1 µm above the core. **Heat 1**
holds the bottom edge at 300 K and heats the heater region; **Modes 1** finds the optical mode at
1550 nm; the coupling **Heat 1 temperature → Modes 1 temperature** gives every triangle the mean
of its three node temperatures, and the optical solve uses n = n₀ + (dn/dT)(T − T_ref) there. The
heater is a local record with a lossless placeholder index; metal loss is later work.

The workspace edits the document itself, so it keeps every key it has no form for, and
**Open model file** (Project) opens any multiphysics document, such as the shipped
[heated slab example](../../../examples/simcase/multiphysics_heated_slab.json).

- **Model builder.** One Component (Geometry 1, Materials with one item per material in use,
  Mesh 1 shared by every physics), the physics with a badge giving their place in the solve
  order (a cycle shares one amber number), **Couplings** with one item per coupling named in
  words, and **Study 1** with the derived solve order and any iteration step. Settings shows the
  plain names; the names the file uses (the physics type, “Name in file”, the format line, and
  for a coupling whether its input takes one source) are under a closed **File details**. A red count on a node is the number of problems to fix there.
- **Add physics** lists the installed providers and their kinds from their manifests, each with
  its ports (unit, where the values live, and for inputs whether they take one source or add
  their sources). Studio adds heat transfer and optical modes here; the other kinds are listed
  and greyed with the reason (the Joule heating and thermoelastic kinds solve their own coupling
  and stay start-page applications). Adding a second physics turns a one-physics model into a
  multiphysics model; **Remove physics** leaves the couplings that named it on screen as
  problems to fix, never dropping them silently.
- **Add coupling** picks an output, then one of the inputs that can take it; the others are
  greyed with the reason (the same physics, another quantity, another unit, an input that
  already has its one source). An output of single numbers is listed greyed as, for example,
  *Modes 1 effective index (single numbers, not a map)*. The transfer is Same mesh, the only one in this release. When an
  input could obviously be fed (Modes 1 temperature from Heat 1), Messages suggests the
  coupling; nothing is coupled until you add it. Until then Modes 1 carries a warning in the
  tree, on its Connections node, in its Settings and in Messages: “Temperature input has no
  source: uses n₀ at T_ref (300 K)”. Without a coupled temperature the optical solve applies no
  index change, so every material keeps n₀, its index at its reference temperature (the shared
  T_ref is named when every material has the same one). Removing a coupling leaves a message
  with **Undo** until the next edit.
- **Ports are not dragged.** The port dots show what each physics sends and takes; their tooltip
  points to **Add coupling**, which checks the pair. In the tree, heat transfer is marked ∿ and
  optical modes λ, as in the single-physics applications.
- **Connections** is drawn from the couplings: nodes in solve-order columns, input pins on the
  left and output pins on the right with their units, one wire per coupling. Each port has its
  own row with its dot on the node edge, and a wire starts and ends at the dots of the ports its
  coupling joins (Heat 1's wire leaves from “temperature”, not from “heat flux” below it). A coupling that
  fails the check is drawn red and dashed with its short cause, or listed under the diagram when
  its physics is missing. A cycle is boxed: amber until it has an iteration step, then blue. Its
  message proposes the engine's defaults, and **Accept iteration step** writes them to
  `study.loops` (Undo reverts it); its values are edited under Study 1 › Iteration step.
- **The check runs on every edit** with the rules of `simcase validate`. Each problem appears in
  Messages (with Show and a one-click fix when there is one: Remove coupling, Use same mesh,
  remove the mesh key one physics does not read, Accept iteration step, Fill from physmat), on
  its tree node, in its Settings, and on the diagram for couplings. The engine's code and text
  stay under Details. While a problem is open, Run is disabled and says why (“Fix 1 problem in
  Messages to run”). A coupled temperature needs a thermo-optic coefficient and a reference
  temperature for every optical material: `physmat:Si` and `physmat:SiO2` carry them, and for a
  local record **Fill from physmat** copies physmat's values in (noting the source) or **Use
  physmat:… instead** switches its regions to the library material.
- **Run** solves every physics in solve order, with the same ▶ as **Run optical study**. The ▶
  is decoration with an empty alternative text, so screen readers read the label alone (“Run”,
  “Run optical study”). The Study dock lists each physics or iteration
  step with its state (Waiting, Solving…, Done in 0.3 s, Iteration 7 of up to 30 with the last
  change, Did not settle, Not run), Connections shows the same states while it is open, and **Stop run**
  ends the run at the engine's next step: after the physics being solved, or inside an
  iteration step after the current iteration. A run that fails or is stopped keeps no partial
  result; Messages names the physics that failed, and the previous complete run stays. A sweep
  is checked but not run (the run reason says so). Any edit after a run marks its rows **Out of
  date (last run: Done in 0.3 s)**, on the dock and in Connections; the dock heading reads “Run 1 ·
  the model changed since; press Run to update” and the footer “Model edited since run 1 · press
  Run to update”. Whether a run is current is decided by content: an edit undone by hand (a
  coupling removed and added back, or Undo) makes it current again, and Messages, the dock
  heading and the footer then say the same sentence, “Model matches run 1 again: results are
  current”, with no request to Run.
- **Also solve without heater** (beside Run, about 1 s) is on when a model whose optical modes
  take a coupled temperature opens. After the coupled run, Studio solves the optical model alone
  with no temperature input, through the same run route, and fills the heater-off column. It is
  skipped when the kept column has the same content. While no coupling sets an optical
  temperature the option stays in place, disabled, and says “needs a temperature coupling”.
  When a coupling comes back (added again, Undo or Redo) the option returns as it was chosen,
  and Messages adds “Also solve without heater” is ticked again.
- **Results** has a page per physics and a **Coupling check**: the solve order used and, per
  coupling, what was sent (“1,726 node temperatures, 300.0–319.0 K”), what was received
  (“3,334 triangle means (mean of 3 nodes)”) and the check (“Passed · max |received − sent| =
  0 K”). Heat 1 shows the temperature map. Modes 1 shows the answer first, the n_eff table, and
  below it the maps of its coupled input: the temperature and the refractive index (or its
  change n − n₀ = (dn/dT)(T − T_ref), computed by the server from the document's values) on the
  core. The n_eff table names its rows *Candidate 1*, …, and the note under it gives the optical
  application's caveat, “Candidates are ranked by effective index and are not matched between
  designs.”, and the number of modes the model asks for, “This model asks for 1 mode: Modes 1 ›
  Modes to find”, a link to that setting (after an edit, “This run asked for …”). The n_eff table has “n_eff without heater” and “Δn_eff (coupled − without heater)”, signed and
  with the 8 decimals of n_eff (the template gives +0.00215086). The note under the table says
  what the baseline is: “without heater = Modes 1 alone with no temperature input: every material
  keeps n₀, its index at T_ref = 300 K”. The column is valid while the optical model solved alone
  (the run's document without couplings, loops and thermo-optic keys, compared with sorted keys)
  is the one of the shown run; otherwise it is marked “(other model)”, Δn_eff is left out, and
  **Run Modes 1 alone** refreshes it. A result names its run and does not change when the model
  is edited.
- **Files.** In a multiphysics model the ribbon's Project group shows **Open model file** and
  **Save model file**, which read and write the document; the session commands are hidden
  because a multiphysics run is not kept in a file (a multiphysics session file is later work).
  The title says so: “Not saved to a file · runs stay in this tab”, and after a save “… · runs
  stay in this tab, not in the file”. Before leaving a model whose run only this tab holds
  (another model card, the template again, an opened file or inputs), Studio asks first: “Leave
  Heated silicon waveguide? Run 1 and its results exist only in this tab: a model file holds the
  model, not its runs. Opening … discards run 1.”, with **Keep this model**, **Save model file,
  then continue** (while the file does not hold the model as it is) and **Discard run 1 and
  continue**. Opening a multiphysics model over optical runs that are in no session file names
  them the same way and offers **Save session, then continue**; those runs stay in the tab and
  come back with the optical model. The graphics footer names the geometry's length unit
  (“Lengths in µm; …”). An
  opened file is read by the server first, so a duplicate key or text that is not JSON is
  refused by name; a saved file writes each number in its shortest form. A sweep is checked,
  and this view runs one point only.

Studio runs these documents through `/api/multiphysics/*` (validate, run, progress events,
stop, result), as an ordinary consumer of `simcase.multiphysics`; the n_eff it shows is the
engine's for the same document, exactly. CI drives this model in a real browser
(`tools/studio_browser/studio_multiphysics_browser.mjs`), and
`tests/simcase/test_studio_multiphysics.py` and `studio_workspace_multiphysics.cjs` check the
routes and the words. Limitations: only heat transfer (`thermal.steady2d`) and optical modes
(`em.modes2d`) are edited here; the Same mesh transfer only; no multiphysics sweep runs; the
geometry form edits rectangles and the window, other shapes stay as written in the file.

## Results and files

The notebook retains up to six successful runs, preserving pinned references. Select a candidate to inspect
its field or compare two runs. Candidate indices are not a mode-tracking result.
Field colours use the vector magnitude normalized separately per candidate;
they do not represent optical power or a common physical colour scale.

Save input JSON to keep the design, or save session JSON to include validated
results. Open restores these files; input-only files are limited to 64 KiB and
sessions to 16 MiB. CSV and PNG exports are available. These workspace
formats are separate from headless simcase JSON documents. After reload, explicitly choose Recover last session for the committed browser
snapshot, or Open session for a portable file. Pending writes are not a backup.

A download request does not confirm that the browser wrote a file to disk.
Check the browser download before relying on it as a portable backup. The input
and session indicators compare against the last save/open snapshot or download
request; an unchanged indicator does not certify download completion. Browser
recovery reports its own committed storage state separately.

Input files are version 7: version 6 (the units and naming batch) plus the Joule heating
inputs (`model.joule`, lengths in mm, `units.joule_length`). A version 6 file is still read,
with the default Joule inputs; a project whose only interfaces are electric currents and
heat opens in the Joule heating application. They record the
core height, wavelength, core mesh size and shape list in nm and the heat plate in mm,
each with its unit, and a flux side of the heat plate as its inward heat flux (version 5
stored the outward flux). Input files of versions 1 to 5 are refused by version with a
message instead of being read under another meaning; enter their inputs again and save a
new file. Browser drafts and input recovery use new storage keys
(`openphysics.studio.workspace.v2`, `openphysics.studio.recovery.v2`), so a draft an earlier
Studio saved is not offered. Each result retains its captured inputs, including field
outlines, comparisons and CSV/PNG exports.

The run table CSV (`studio-runs.csv`) writes every quantity column as `name [unit]` with
its SI value: `core_width [m]` and `core_height [m]` (single-rectangle designs),
`vacuum_wavelength [m]`, `core_element_size [m]` and `effective_index [1]`; job, name, pin,
completion time, `core_material`, a `shapes` column describing every shape (in nm, as the
page shows it) and the candidate number carry no unit.

Session files are version 7, whose input is an input file of version 7 (a version 6
session is still read, its input as a version 6 input file); version 6 was written since the units and naming batch: the workspace
builds a format 0.3 document (lengths as quantity strings such as `"1550 nm"`, materials
under their exact `physmat:` names) and each run record keeps the result's
`effective_index` (Re and Im under exp(−iωt)) and field samples with `node_coordinates` in
metres, and its input as an input file of version 6. Sessions of versions 1 to 5 hold
results under the earlier names and the document length unit; the workspace refuses them
by version with a message instead of reading them under another meaning. Enter the design
again, run it and save a new session.

The workspace checks `/api/workspace/capabilities/v7` before enabling Run. Contract
version 7 (the content of version 6, for a workspace that saves input and session files of
version 7; version 6 is the content of version 5 for files of version 6 and the coded
`diagnostics` of a document check) and adapter
`optical-shapes-v7` declare the window in nm, at most eight
shapes and twelve polygon vertices, the shape types and the ten materials with their
`physmat:` names, the 1400–1700 nm wavelength and 20–60 nm core mesh ranges (quantity
strings), the fixed window, boundary and candidate settings (`mode_count`),
`optical: true`, `coupled: false` and `simcase_version`. A missing or incompatible
contract blocks execution; **Check connection** retries. Each submitted run
captures its shapes, wavelength, core mesh and the reported simcase package version and preserves them in session JSON.
The earlier capability endpoints (`/api/workspace/capabilities` and `/v2` to `/v6`) remain
available at the same paths and schema versions;
because every adapter now writes format 0.3 documents and reads the new result names, each
names its family's next adapter version (`optical-fixed-v2`, `optical-rectangle-v4` and `-v5`,
`optical-shapes-v6` and `-v7`), with its values as quantity strings.
This is not a complete engine dependency or Git provenance record.

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
assignments in the conceptual preview remain setup labels. Study summarizes the current
core dimensions and materials with links back to their editors.

## Running, stopping the wait and resuming

The job panel shows the submitted dimensions/material, job ID, elapsed time and
result-loading state. **Stop waiting** stops browser polling only; the optical
server continues its computation. **Resume job** retrieves that same job with
its captured inputs, even after editing the current design or reloading the
same tab. The pending-job record uses session storage, separately from input
recovery and saved session files. Storage failures are reported. A server
instance identifier prevents resuming a job against a restarted server.
If the job is missing, its server changed, or the solver reported failure,
**Resume job** is disabled; use **Detach job** before starting a new calculation.
Temporary connection failures still allow resuming retrieval of the same job.
Neither case changes retained results or current model inputs.

Only one job is tracked per tab. Resume or **Detach job** before starting another.
Detaching forgets this tab's job reference and does not cancel server work.
Polling stops after three minutes and can be resumed; failed requests do not
replace existing results. Late responses after stopping are ignored. The panel
reports elapsed time rather than inventing a completion percentage. No server
cancellation or durable server job persistence is implemented. Save completed
sessions before restarting the server or closing the tab.

## Inspecting field samples

In Results or Compare, click inside a field plot or enter x/y coordinates in nm
and select **Inspect point**. The crosshair and readout use physical coordinates in nm,
like the model inputs; field, mesh and profile plot axes are in nm with ticks on round
values. The session file keeps these positions as quantity strings in µm, unchanged.
Compare samples both meshes at the same location. The value is the normalized
stored centroid sample of the containing triangle, not an interpolated point
field. The readout identifies that triangle and its centroid; a point outside
the captured mesh reports no sample. At shared edges, the last drawn triangle
is chosen consistently. Degenerate cells are ignored.

Candidate/component changes update the readout with the same vector-normalized
scale used by the plot. **Clear point** removes the marker. Probe selection is
view state stored in session JSON and browser notebook recovery. Field PNG
exports include the marker and its coordinates when selected. These samples do
not establish convergence or physical field amplitudes.

## Naming and preserving runs

Type a **Run name** (up to 80 characters) and press Enter, or leave the field, to
name the selected run. Naming a run also pins it, as the hint under the field says.
Names appear in the **Runs** list and comparisons, persist in session JSON and CSV,
and never change captured inputs or fields. The Runs list labels each run by name,
size, wavelength and completion time; **Run details** in Results holds the job id,
source, simcase version and input change number. **Export this run** writes a
standalone session file containing that result and its original inputs; this is useful
before the six-run retention limit removes an older unpinned run.
The save indicator (header and footer) distinguishes a changed session from saved input-only files. Saving
inputs or a browser draft does not claim to save the result notebook. A single-run
export does not mark the full notebook saved. **Export field PNG** draws the Results
plot; on Compare it is unavailable, and the text under it says to open a run in Results.

Undo/redo applies to design inputs. Outside text fields, Ctrl/Cmd+Z undoes and
Ctrl/Cmd+Shift+Z or Ctrl+Y redoes. In text fields, native text editing is retained.
Run names and comparison choices are session metadata, outside input undo.

## Mesh preview and active interfaces

For an optical model, choose **Mesh → Generate mesh** to call the existing
server mesh builder without solving modes. The preview shows actual triangles,
region colouring, node/triangle counts, minimum angle and mean quality. Select
Full window or Core region; axes are in nm with equal x/y scale.
Changing the design leaves the prior preview visible with an earlier-input
label until explicitly regenerated. Failed generation preserves the last good
preview. Mesh previews live only in the tab and are not saved in session JSON.
The optical solve builds its own mesh using the same input contract; previewing
is not mesh reuse or a convergence certification.

An optical-only model tree shows Geometry, Materials, Optical modes, Mesh and
Study. Connections explains that no coupled interfaces are present and links
back to application choice. The conceptual preview of older input files keeps the broader
setup tree and runs nothing; the Heated silicon waveguide is a separate, runnable model.

## Guided optical workflow

The Geometry, Materials, Mesh, Study and Results bar follows the current inputs.
It identifies invalid drafts, unavailable execution, a pending job, and mesh or
results captured from earlier inputs. A mesh preview is optional: Run creates its
own mesh. Ready to run is an input/connection state, not numerical validation or
convergence certification; Run complete means a retained result has exactly the current
inputs. Results opens the newest retained matching input when
one exists; navigation itself never runs a solver. Earlier results remain available.
The Results step is highlighted on Results only, not on Compare. The Study sequence
line in the dock is plain text; the step bar and the model tree select nodes.

Connection details, input recovery and layout help are grouped in an expandable
panel. A connection failure opens it automatically. Numeric error descriptions
are separate from their field labels; workflow buttons retain keyboard focus as
status labels update. The workflow is shown for the optical application only.

## Check and export the submitted document

Study → Check inputs calls the public document validation endpoint without meshing
or starting a job. The report retains its input snapshot and server identity;
editing inputs or reconnecting to another server makes the report earlier evidence.
It lists every coded diagnostic the server returns (severity, code, path and message:
errors, warnings and notes) in place of the earlier free-text notes.
A transport failure retains the previous report alongside the new error. Validation
acceptance is not material-accuracy, mesh-convergence or solver acceptance. Run
always validates its own captured document again.

Export solver JSON downloads the actual simcase `openphysics: "0.3"` input: its
geometry in nm (`length_unit`) and its other lengths as quantity strings. It can be read by the simcase Python/CLI APIs; it is not a
workspace project/session and does not contain computed results. The expandable
solver document shows the same payload; with an invalid editor draft it shows the
last valid inputs and export is disabled.

The server reads these requests from their raw bytes: a number keeps its written digits,
and a duplicate key, `NaN`, `Infinity`, text that is not UTF-8 or a string with an escaped
unpaired surrogate is refused with its code.
Workspace validate, mesh and run requests carry the connected server instance.
A restarted/different server rejects stale requests before parsing the model or
starting a job; old jobs do not migrate between server processes. When Run meets a
restarted server, the page reconnects to the new server at once and asks you to
select Run again; inputs and retained results stay. When the server cannot be
reached at all, Run is disabled with that reason and the page checks again every
3 seconds, reconnecting by itself once Studio is started again at the same address.
**Check connection** retries at any time. Classic callers without an instance query
keep their existing API.

## Line profiles

Results and Compare include an expandable Line profile and CSV panel. Choose a
horizontal line (constant y) or vertical line (constant x), enter its fixed
coordinate in nanometres, and select Show profile. Both comparison runs use the
same line and 0–1 relative scale; each candidate retains its own max|E| denominator.
Changing candidate/component updates the profile. Line choices are view state saved with the session and browser notebook recovery.

Each plotted step is the stored centroid value of the triangle intersected by
that interval. There is no field interpolation, smoothing, absolute-power estimate
or mode tracking. Shared/coincident edges follow the last painted triangle; mesh
gaps remain gaps. The CSV (`studio-profile.csv`) exports job, origin, candidate,
component, axis, the fixed coordinate, interval endpoints, triangle number, centroid and
normalized value; every quantity column is `name [unit]` with its SI value
(`fixed_coordinate [m]`, `start [m]`, `end [m]`, `centroid_x [m]`, `centroid_y [m]`,
`relative_amplitude [1]`), while the panel takes and shows nanometres. Values at an interval's
isolated endpoints are not a separate point-probe claim.

Analytical unit-square tests cover exact horizontal/vertical intervals, reversed
winding, overlaps and empty regions. Actual exported comparison intervals were
independently checked against complex vector norms and triangle containment.

## Automatic notebook recovery

Once the tab has completed or imported results, valid input/selection/name changes
queue a browser IndexedDB snapshot containing the current inputs, up to six
completed runs, names, comparison and field view. Writes are debounced and serialized;
the save indicator reports the browser copy (*updating browser recovery*, *kept for
recovery in this browser*, *browser recovery unavailable*) while no session file holds
the runs, and the session file once one does. An empty new tab does not erase the prior notebook.

After reload, choose the last session on the start page's **Continue where you left off**
card, or expand Connection, recovery and layout help → Recover last session.
The complete record is validated before the existing replacement dialog; recovered
fields are labeled `recovered`, not newly computed. Recovery starts a new input
undo history and keeps the document unsaved until you save a file/session. No
solver is started. Input-only recovery and pending-job recovery remain separate.

Starting new work without recovering does not discard the stored session. The first
automatic save after a page opens moves the stored session to the earlier sessions,
newest first, keeping at most three; **Recover earlier session** lists each with its
run count and time and recovers it through the same replacement dialog. Recovering
an earlier session keeps the current one as an earlier session at the next save.

The latest snapshot is a single record for the browser origin, shared across tabs.
Each write checks the previously observed revision in the same database transaction.
If another tab has saved since this tab loaded or recovered the notebook, automatic
storage stops without overwriting that record. Save session to preserve this tab,
then Recover last session to review and adopt the newer notebook. Cancelling the
review or Retry recovery storage does not bypass this protection.

To keep this tab's notebook instead, choose **Use current notebook for recovery**.
Review the stored snapshot and current run count, then explicitly replace browser
recovery. This preserves current model inputs, results and Undo; it does not import
or solve anything. It can also replace an unreadable recovery record. Save session
first if you need a portable copy of either notebook. A changed workspace, active
storage write, or a newer database revision during review prevents replacement;
review again against the latest state. Quota/database failures still require a
portable file. Empty notebooks cannot replace a completed recovery snapshot.

Reload older tabs
after updating Studio: an older running version may still overwrite the shared record.
This is not a backup archive. A quota or
transaction failure retains the previous committed record; Retry recovery storage
retries the latest requested state. Closing the tab while pending/saving can lose
recent changes. Browser cleanup/private mode or a different port can make recovery
unavailable. Use Save session / Export this run for portable files. The 16 MiB
session and six-result limits still apply; invalid drafts, undo history, mesh,
and preflight reports are not included. Probe and profile positions are included.


Recovery captures input, run metadata, selection and view when an update is
queued. Later model edits or opening an empty session cannot change that queued
snapshot. Large result arrays remain read-only and are serialized after the
coalescing delay; changing inputs does not copy field arrays on every keystroke.

## Pin reference runs

Naming a run pins it: new runs do not replace it. There is no separate Pin button;
**Unpin this run** releases a pinned run, and Enter in Run name pins a named run again. A new
result replaces the oldest unpinned run, with at most six retained in total. If
all six are pinned, Run is disabled until one is unpinned; document checks and
mesh previews remain available. Pins are saved in sessions, browser recovery and
the CSV run table. They do not alter inputs, fields or the input Undo history.
Repeated retrieval of the same job preserves its existing name and pin. A failed
retention operation leaves the previous notebook and selected result intact.
Pinning is not a portable backup; export files before discarding browser data.

## Import runs without replacing the model

Results/Compare → **Add runs from file (inputs unchanged)** accepts a session file or a single-run file from **Export this run**.
Review the number of new, matching and replaced unpinned runs before applying.
Current model inputs and input Undo are preserved; the imported selection opens
beside a retained result for comparison. Imported runs remain labeled `imported`.
Use Open session when you intend to replace both inputs and the notebook instead.

Matching job IDs retain their current names, pins and provenance only when their
input, settings, effective indices, field arrays and server version agree. A
conflicting payload rejects the whole import. Incoming runs and pinned references
are never silently dropped to fit the six-run limit; if they exceed capacity,
unpin a reference or export/import a single-run file (**Export this run**). Older unpinned current
runs may be replaced after the review. Pending jobs block run imports.

Keyboard focus stays on the corresponding tree, geometry, material and run control
after a selection refresh. Input Undo/Redo shortcuts do not act behind an open
confirmation dialog. Selecting an optical PEC edge keeps its specific boundary
identity visible above the optical interface properties.

An open line-profile panel draws an amber dashed slice on each field plot when
that line intersects the visible window. The graph uses the full domain even
when the field view is zoomed to the core. Export profile PNG includes axes,
normalization, candidate, line location, job IDs, geometry, materials and origins.
Field PNG exports also annotate an active profile line. Comparison plot rows stay
aligned when run labels wrap to multiple lines.

Session view metadata also preserves the probe coordinates/visibility and
profile direction, fixed coordinate and expanded state; the coordinates are quantity
strings such as `"0.15 um"`, and a bare number is refused. These settings do not
change model revisions or run a solver. A session without these optional
fields restores a hidden probe at (0, 0.15) µm and a closed horizontal profile at
y = 0.15 µm. Invalid/out-of-domain saved view metadata rejects the whole import
before changing current inputs or results.


File, session and browser-recovery reads share one current load intent. A later
choice or cancellation invalidates an older pending read, including its errors.
If inputs, view, run history or job state change while reading, choose the source
again. The replacement dialog lists the source, old/new dimensions, core material,
result counts and Undo behavior. It checks the workspace again when confirmed;
a completed job arriving during review cannot be silently discarded by an old
replacement prompt. Add runs from file continues to preserve current model inputs.

## Installed physics

**Installed physics**, in the status bar next to Workspace tools and opened from the
ribbon with **Physics → Installed** (Escape closes it), lists the physics
providers installed with Studio ([physics providers](providers.md)): each provider's
name, version, distribution, status and physics kinds, built-in provider
(`openphysics-fem`, distribution `simcase`) first. A provider that could not be loaded
is listed as *Unavailable* with its error as `simcase.providers.providers()` reports
it, for example `ImportError: No module named 'my_physics'`; the other providers and
the built-in physics keep working. The list is read when the panel opens, from
`GET /api/providers`.

The list is data only. Every string a provider supplies is shown as text (a
string longer than 2000 characters is cut for display), and the page never loads
code (JavaScript or HTML) from a provider. The route sends the fields above and
kind names, no other manifest content and no entry-point target. The error text is
sent as `providers()` reports it, so it can name a file, such as the module an
import failed in; Studio serves only this computer by default (see the
[package overview](overview.md)). If the list itself cannot be read, the panel
says so and the server log holds the details. The panel does not change the workspace
capability contract (now `/api/workspace/capabilities/v7`, for the Joule heating inputs). Installed providers are not yet offered as
workspace physics; the list only shows what is installed.

Checks: `tests/simcase/test_studio_providers.py` (the built-in provider alone, an
injected provider, unavailable providers, a failing listing, and route output with
empty, long and hostile strings read by the shipped page module) and
`tests/simcase/studio_workspace_providers.cjs` (escaping and the reply contract).
