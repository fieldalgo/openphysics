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

The page tabs at the top, **Library**, **Model**, **Connections**, **Results** and **Compare**,
are a tab list: the shown page's tab is selected and is the one Tab stop, and Left, Right, Home and
End move to another tab and open its page. The page below them is the tab panel (`role=tabpanel`)
that every tab controls, named by the selected tab. The workbench has a command ribbon, a model builder and adjacent Settings panel
on the left, a large Graphics workspace on the right, and a Study/Messages dock
below. The ribbon groups Project, Edit, Model setup, Physics and Compute. **Geometry**,
**Materials**, **Mesh** and **Study** open the same settings as the model tree.
**Physics → Installed** opens [Installed physics](#installed-physics). Compute holds
the run command of the chosen application, **Run study** in every model (optical, steady heat,
Joule heating and multiphysics; the header names the model). The optical workflow strip shows the current step
without hiding the model. The dock shows the study sequence and Messages; after a
Joule heating run, Results adds its **Solver log** there.

The **File** menu at the left of the ribbon opens and saves files, and **Edit** holds **Reset
design**; the ribbon's **Open…** and **Save** buttons are shortcuts to **File › Open…** and
**File › Save** ([File menu and file kinds](#file-menu-and-file-kinds)). Save keeps the whole
session, including completed optical runs and comparisons, or a multiphysics model with its runs,
in every model (optical, heat, Joule heating and multiphysics); **File › Export › Model file…**
keeps the inputs only, and **File › Browser copy** holds the browser draft. **Workspace tools** in the bottom status bar contains connection,
recovery and Reset layout; **Installed physics** sits next to it. Both open above the
status bar, one at a time, on every page including Library; Escape closes the open
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

## File menu and file kinds

The **File** menu, at the left of the ribbon, is a menu button: Enter, Space or Down opens it on its
first item, Up and Down move, Right opens a submenu (or the next menu), Left closes a submenu (or
opens the previous menu), Escape closes one level and returns focus, and Tab closes the menus. Its shortcuts are shown beside the items.

| Item | Shortcut | What it does |
|---|---|---|
| **Open…** | Ctrl+O (⌘O) | Opens a session file or a model file of any model. The ribbon's **Open…** is the same. |
| **Save** | Ctrl+S (⌘S) | Saves the session file. After a Save As through the browser's save dialog it writes that file again without asking. Where Studio downloads instead, it downloads again under the model's current file name (the name chosen in Save As or Save, or the file opened) without asking. With no current file it asks, as Save As does. The ribbon's **Save** is the same. |
| **Save As…** | Shift+Ctrl+S (⇧⌘S) | Saves the session file under a name you choose; it starts with the current file name. |
| **Export › Model file…** | | Downloads the model file (inputs only), named after the model, for example `optical-waveguide.json`. |
| **Export › Model with runs (session file)…** | | The same as Save As. |
| **Browser copy › Save browser draft**, **Restore browser draft** | | Keep or restore the optical inputs in this browser only. |
| **Edit › Reset design** | | Returns the model to its default design. |

What each kind of file holds:

| Kind | Holds | Named | Made by |
|---|---|---|---|
| Session file | The model's inputs with its completed runs, their names and pins and the comparison (optical, version 9); the inputs of steady heat and Joule heating; or a multiphysics model with its runs and without-heater results (version 8). | `<model>-session-YYYY-MM-DD-HHMM.json`, or the name chosen in Save As | **File › Save**, **Save As…**, **Export › Model with runs (session file)…** |
| Model file | The model's inputs only: no runs and no computed results (optical, steady heat and Joule heating inputs, version 7 or 8; or a multiphysics document). | After the model, for example `optical-waveguide.json`, `heat-conduction.json`, `joule-heating.json`, `heated-silicon-waveguide.json` | **File › Export › Model file…** |
| Browser draft | The optical inputs, in this browser only (not a file). | — | **File › Browser copy › Save browser draft** |
| Browser recovery | The newest sessions with completed runs, in this browser only (not a file). | — | Automatic ([notebook recovery](#automatic-notebook-recovery)) |

The contents of both files are the same as before the File menu for the same model and runs; only
their names and how they are saved changed. Messages calls an inputs-only file a *model file* and a
file with runs a *session file*, never a project.

**Where Save As saves.** Where the browser has a save dialog for web pages
(`showSaveFilePicker`, in a secure context: `http://127.0.0.1` and `http://localhost` qualify),
Save As opens it from your click or key press with the suggested name (the current file's, if
any) and one JSON file type, and writes the chosen file. It opens in the folder the browser last
used for Studio (the picker `id` `openphysics-project`), or in the current file's folder once a
file was chosen there (`startIn` is passed only then). Studio
keeps the file it wrote, so **Save** writes it again without a dialog until another model or file
is opened, the model is switched or the design is reset. Chromium replaces a kept file only when
the write is finished, so a Save whose write fails leaves it as it was: *Session not saved: …
could not be written (…); the file is unchanged.* A file just chosen in the dialog may already
have been created or emptied by the browser, so a failed first write says *…; the browser may
have left it empty.* Closing the dialog says *Save As cancelled; nothing was written.* (*Save
cancelled; …* when Save opened it), and Messages says *Saved to <name>* after a write. Elsewhere
(Firefox, Safari, a page that is not a secure context), or when the save dialog cannot be used (for
example a managed browser that refuses it), Studio asks for the **File name** in its own dialog:
ASCII letters, digits, spaces and `.`, `_`, `-`, `(`, `)` only (other characters are removed),
with `.json` added if missing. It notes
that your browser saves to its Downloads folder, or asks where if you set it to, and **Download**
hands the file to the browser: Messages then says *Session file <name> sent to your browser's
Downloads*. Opened by **Save**, the dialog also says that the browser may add “ (1)” when its
Downloads folder already has a file of that name. Studio cannot know that a download was kept.
Studio remembers the name as the model's **current file**, as it does the name of a file opened
with **File › Open…**: **Save** (and Ctrl+S) then downloads under it again without asking
(*Downloaded <name> again: … A download cannot replace the earlier file, so your browser may name
it <name> (1).json.*), and Save As starts with it. Opening another file or model, switching the
model or **Reset design** drops it, as it drops a file kept from the save dialog. **Export › Model file…**
always downloads.

Browser support for the save dialog (`window.showSaveFilePicker`), checked on 2026-11-23 in
[MDN browser-compat-data](https://github.com/mdn/browser-compat-data) 8.1.10 (data of 2026-11-19;
[MDN page](https://developer.mozilla.org/en-US/docs/Web/API/Window/showSaveFilePicker)) and the
[Chrome File System Access documentation](https://developer.chrome.com/docs/capabilities/web-apis/file-system-access):

| Browser | Save dialog (`showSaveFilePicker`) | Studio's Save As |
|---|---|---|
| Chrome, Edge (desktop) | Yes, since 86 | The browser's save dialog; Save writes the same file again |
| Opera (desktop) | Yes, since 72 | The browser's save dialog |
| Chrome for Android | Yes, since 132 | The browser's save dialog |
| Firefox (desktop and Android) | No | Studio's name dialog, then a download |
| Safari (macOS and iOS) | No | Studio's name dialog, then a download |

Automated or headless browsers (`navigator.webdriver`) cannot show the save dialog; Studio downloads
the file under the name you give. The API is marked experimental in the data. The real dialog of desktop Chrome is not driven by the
automated checks: they replace `showSaveFilePicker` at its boundary (see the
[development guide](../../development.md)).

## First optical study

1. Choose **Library → Optical waveguide** (the start page; its tab is **Library**). (The Heated
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
   wavelength in **Physics › Optical modes** (its settings are headed *Optical modes*) or in
   the Study's execution settings: both hold the same field, as both hold **Modes to find**
   (**Study → Edit wavelength** and the step bar's wavelength open it under Optical modes,
   focused). The Study settings also say which inputs the next run uses, *Next run uses 700 ×
   300 nm · Silicon · λ 1550 nm · core mesh 30 nm · Modes to find 2*, with *· group index on* when
   **Also compute group index** is ticked, whatever run Results shows.
   Set the core mesh size in **Mesh**.
3. Optionally generate **Mesh** and review **Study → Check inputs**. These actions
   do not calculate optical fields. Inspect or export the solver JSON if needed.
4. Select **Run study**. Results keep the inputs used by that run,
   even if you edit the model while waiting. Stop waiting pauses observation only.
   An input edit replaces the completion message, so it never describes edited inputs. The run
   banner (*Optical run complete…*, and **Stop waiting** while a run goes) is part of the view's
   title row, after the view title (*Results*, *Comparison*): it covers no heading and no control,
   and the row keeps its height, so it never moves the panels when it appears or leaves. The
   *Optical run complete…* banner leaves after 6 seconds, or at your next click, tap or key press if
   that comes first; Messages keeps the words.
   The dock heading, the status bar, the title and the step bar describe the run being viewed
   (the selected run), named by its number with its name: after a run *Run 1 · solved from
   the current inputs* (the status bar adds *press Run to solve again*); when the viewed run has
   other inputs, after an edit or with an older run selected, both geometries, *Run 1 · design A
   600 × 300 nm · current inputs 700 × 300 nm* (with the same geometry, at most two of the
   settings that differ: *· current inputs differ: Wavelength 1550 → 1310 nm*) (the status bar adds *Run 2 has them* when another run has the current
   inputs, else *press Run to compute them*), and when no input was edited the title adds
   *viewing Run 1 · design A (other inputs)* on Results and Compare, so the difference does not
   read as unsaved edits (on the Model tab the title describes the current inputs only). Under
   the Inputs row of the selected run, **Use this run's inputs** loads that run's inputs (and its
   Modes to find and group index option) as the current inputs at once, without a question,
   since the runs stay as they are. Messages lists only the settings that change, from → to
   (*Current inputs set from Run 1 · design A: Width 700 → 600 nm · Modes to find 4 → 2. The next
   run uses them; Undo takes them back.*), and the same words stay in the run panel where the
   button was until the next input edit. It is one input edit, so **Undo** takes all of it back, Modes
   to find and the group index option included, and **Redo** applies it again; before any run *Nothing is computed until you press Run* and *Optical adapter
   ready · explicit Run required*. A run's number is its place in the run list, the oldest first. A current run that this tab did not
   compute says where it came from instead: *Run 2 · read from file, not recomputed* after Open
   session, *Run 2 · recovered from this browser, not recomputed* after a recovery (the status
   bar adds *press Run to compute it here*). Run list entries name a run by its number with its
   name, *Pinned · Run 1 · design A · 600 × 300 nm · λ 1550 nm · 3:50:12 PM*, and give the time
   with seconds; the Compare pickers and headings name runs the same way. Compare opens with
   the two newest runs, the older as A and the newer as B (a run just computed is B); the run
   list shows the newest first, so on Compare the two cards end with a *Compare A* and a *Compare
   B* badge (read out as *· Compare A* and *· Compare B*). A pick whose run is gone sets both back to that pair. Exactly one run card
   reads as selected (the pointer over another card changes only its border). On Compare a click on
   a run in the run list selects it (Run name and the run commands act on it) and Compare stays
   as it is: A and B are chosen with the pickers above the plots, and **Open Run 1 · design A in
   Results** under the list shows the selected run in Results. While something holds Run (input
   errors, a computation or job in progress, an unsupported input), the heading repeats the
   status bar's words instead.
5. Type a **Run name** and press Enter: a named run is pinned, so new runs do not
   replace it. There is no separate Pin button: **Unpin this run** releases a pinned run,
   and Enter in Run name pins a named run again. Change the model and run again,
   then use **Compare** to choose A/B, matched modes, component, probe and line profile.
   The two field plots come first, headed by the side and the run (a run named *A* on side
   A is not named twice), drawn on the window Results draws for the same run, centred on the
   core, and as tall as the Results plot; when Compare opens, its pane scrolls so the middle of
   the plots is in view with the matched-modes picker still above them. The probe line
   (*No point selected.*) is under each plot, and the sentence naming the geometry, wavelength
   and core mesh of A and B follows the plots. Below them a table matches the modes of A and B by field overlap
   ([matching modes](#matching-modes-in-compare)): one row per matched mode, *1 ↔ 1* (A mode 1 ↔
   B mode 1), with both polarizations, the overlap, n_eff of A and B, Δn_eff (B − A), Δ % of A,
   A_eff, absorption loss and n_g of A and B; the line above it names each run (name, size, λ).
   n_eff has 8 decimals everywhere (results, mode list, Compare).
6. **Save** (**File › Save**, Ctrl+S), the first save button, creates a portable session file with the model,
   retained results and view settings, named from the application and the local
   date-time (for example `optical-waveguide-session-2026-11-21-1305.json`) in the
   browser's Downloads (Studio's name dialog lets you change the name), or written to the file
   you choose in the browser's save dialog where it has one
   ([where Save As saves](#file-menu-and-file-kinds)). Studio hands a download to the browser and
   cannot know that it was kept (a download can be cancelled), so Messages reports *Session file
   … sent to your browser's Downloads*; after the save dialog's write it reports *Saved to …*.
   When no run has the current inputs, the notice says so: *Current inputs (650 × 300 nm) have no
   run yet.*
   The header holds the one save indicator, and the footer repeats it word for word: the
   current file's name and its state, *design-a.json · downloaded 03:42* (or *design-a.json
   · saved 03:42* after the save dialog's write) until the next edit or run, then *design-a.json ·
   changed since downloaded* (*· changed since saved* after the save dialog's write, *· changed
   since opened* after **File › Open…**, *· changed since restored* after a restore). After a
   download the header and the footer have the title text *Your browser may have added “ (1)” to
   the file name.*, and the Save As name dialog says *Later saves download again under this name;
   your browser may add “ (1)”.* The next **Save**
   downloads under the same name without asking. **File › Export › Model file…**
   keeps the model without results; while completed runs are not in a session file, the indicator says *Not saved
   to a file · kept for recovery in this browser* (*· updating browser recovery* while it
   writes, *· browser recovery unavailable* if it cannot), or *design-a.json · changed
   since downloaded · kept for recovery in this browser* after a file save.
   After **File › Open…** the header says *Opened …* with the file name, and after a
   recovery *Recovered from this browser*. Browser recovery keeps the session file the notebook
   was last sent to or opened from, and whether the notebook still matched it, so a recovered
   session names it: *Recovered from this browser · same as file …json* when it still matched,
   *Recovered from this browser (last sent to a file: … at 13:05; changed since)* or *(opened
   from …json; changed since)* when it had changed, *· not saved to a file* when no file was
   saved or opened. A restore that still matched its file makes that file the current file:
   **Save** downloads under its name at once and **Save As** suggests it. These titles, and
   *… · downloaded …* (or *· saved …*) after a
   save, last until the model or a run changes (an input edit, a run added, renamed, pinned or
   unpinned) or another open: a tab click (**Library**, **Model**, **Connections**, **Results**,
   **Compare**), a selected run, a Compare choice or a field view is not a change. After a
   change the title says what changed: *design-a.json · changed since downloaded* for an input edit
   (*Unsaved inputs* when the model has no current file), *design-a.json · changed since downloaded ·
   kept for recovery in this browser* for a run. The header has no revision counter. A Width edit by an odd
   number of nanometres gives a half-nanometre Left x: the centre is kept exactly, Messages says
   where Left x moved (*Width set to 600 nm. Left x moved to −300 nm to keep the centre.*), and
   typed values are not snapped to the drag step (**More about width and height** under
   the size fields). Wait for *kept for recovery in this browser* before relying on local
   recovery (**Workspace tools** shows when it was last updated). After a reload or a
   Studio restart, the start page shows **Continue where you left off** with
   **Restore from this browser: Last session in this browser …** and any earlier ones
   (**Restore earlier from this browser: …**) and **Start new**. **Open session file…** has one
   fixed place, at the top of the Library above the box and the cards, whatever they offer,
   with the note that a session file is the copy that moves between computers; browser
   recovery stays in this browser. It does what **File › Open…** does. The Library page has one phrase for browser recovery,
   *Restore from this browser*; **Open session file…** is for files. A restore opens the page
   shown when the record was written (Model, Results or Compare) with the run that was
   selected; a record written before Studio kept the page, and an opened session file (which
   names no page), open Compare for two runs or more, else Results. Over a workspace with default
   inputs and no results, an open or recovery asks nothing. Otherwise **Open saved
   session?** (or **Recover saved session?**) lists the runs with their names and pins
   and the comparison that come back, what is replaced, and only the physics present.
   Before a model is chosen, the header reads *No model chosen*, the status bar
   *Choose a model to start* and the Study sequence lists no steps. A model just chosen
   reads *New model · not saved* until its first edit, then *Unsaved inputs*. The start
   page says what choosing does: it sets which physics the model solves, keeps the
   dimensions you entered and the runs you completed, and Undo takes it back between the
   optical, steady heat and Joule heating models; the heated silicon waveguide has its own Undo
   for its edits, and you leave it by choosing another model. Each model's note says what Save
   session keeps of it: the inputs and runs of the optical model, the inputs of steady heat and
   Joule heating (their results stay in the tab), and the heated silicon waveguide with its runs.
   Opening the heated model over optical runs says in one line of Messages *Optical waveguide runs
   stay in this tab · Library › Optical waveguide returns to them*; **More** after it says that the
   tab holds them until it is closed or reloaded, then what holds them after that: **Library ›
   Optical waveguide › Restore from this browser** (browser recovery, which keeps the four newest sessions) or **Open
   session** with the session file that holds them, or that nothing does. While the tab holds no optical
   runs and browser recovery holds an optical session, for example after a restart, the Optical
   waveguide card offers it first, *Restore from this browser · Optical waveguide · Run 1 ·
   design A, Run 2 · 2:25 PM*, next to **Start new**. The Heated silicon waveguide card does the
   same for the newest multiphysics session while the tab holds no multiphysics runs, *Restore
   from this browser · Heated silicon waveguide · Run 1, Run 2 · Heater 2e14 · 2:25 PM*. An
   offer whose record is the same as the session file it was saved to names the file's save
   time instead of the record's, *· same as file …json, saved 2:24 PM*; one the same as a file
   it was opened from says which time it shows, *· browser copy 2:25 PM · same as file …json*.
   The box above the cards then lists only the sessions no card offers. Every recovery entry names its
   model, its run count and its runs (*Run N*, with the run's name if it has one), for example
   *Optical waveguide · 2 runs · Run 1 · design A, Run 2*, and the session file its record was
   opened from or last sent to: *· same as file …json* when the record still matched it, *· file
   …json, changed since* when it did not, *· file …json* for a record written before Studio kept
   that. Each stored session is listed once, newest first:
   records with the same inputs (or model) and runs are one session even when their view (page,
   field view), selected run, Compare choice, the runs' origin (computed here, opened from a file
   or recovered), file link or save time differ. The newest is shown, naming the file if any of
   the merged records named one, and the session open in this tab is not offered. The start page uses
   one word, model: the **Library** tab, *Choose a starting model*, *Model library ·
   Choose a model*. A card's tag names the solver it runs, *Optical mode solver*, *Heat conduction
   solver*, *Electric current and heat solver*, and the heated silicon waveguide *Heat → optical
   modes · coupled*; nothing computes until you press **Run study**.

Use **Add runs from file (inputs unchanged)** to add results to the current notebook while keeping
the model. Use **File › Open…** to replace both model and notebook. *Result for the current
inputs* and *Current inputs differ from this run: this run 600 × 300 nm · Silicon, current 700 ×
300 nm · Silicon* (only the parts that differ: geometry, wavelength, core mesh) say which design a
result belongs to, in Results and in the selected run's settings. The line under the Results
heading names each part once: the parts that differ with both values, then the others,
*…, current 700 × 300 nm · Silicon; unchanged: λ 1550 nm · core mesh 30 nm*; the step bar's Results step
describes the run shown (*Result for these inputs* or *Current inputs differ from this run*), and
clicking it shows that run. Steady heat and Joule heating results use the same words. In optical
Results the modes table comes first, then the field plot with its sample and line profile. Between
designs, Compare pairs modes by field overlap, not by rank; the dock note on Results and Compare
reads *Each result keeps the inputs it was run with · Compare matches modes by field overlap ·
convergence not certified*.

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
boundaries. **Modes to find** (in **Optical modes** and in **Study**; a whole number from 1 to
8, 2 by default) sets how many modes a run asks for; the engine keeps the modes above
n = 1.45 (Re n_eff), ranked by Re n_eff. When fewer are guided, Results says so above the modes
table, *Found 3 of 8 modes above n = 1.45*, and the table has those rows. Each result shows the
shapes, wavelength and core mesh it used and keeps the count it asked for.

Modes to find is saved with the model: the model file, a browser draft, browser
recovery and a session's input keep it ([version 8](#study-settings-in-input-files-version-8)),
and each run of a session keeps the count it asked for. A change to it is an input edit:
**Undo** and **Redo** cover it, and the title reads *Unsaved inputs* until it is saved. Opening an
input file sets it from the file, 2 for a file of version 6 or 7 (an earlier Studio left it
unchanged). Opening a session sets it from the session's input when that is of version 8, else
from the selected run, as before; so a session saved at 2 modes while a run of 4 was selected
(its input is version 7) opens at 4, as such files did before. A new model starts at 2. With 2 modes the
solver document is byte for byte the one earlier Studios sent, so its n_eff, TE fraction and
effective area are unchanged.

**Also compute group index (3 solves)** in **Study** and in **Physics › Optical modes** (one box
shown in both, off by default; its note reads “Also solves at λ ± 1 nm and takes n_g from the
change (about 3× slower). Off: one solve, no n_g. n_g includes the dispersion of the materials
(evaluated at λ ± 1 nm).”, and ticking or clearing it says in Messages
what the next run does, *Group index on: the next run also solves at λ ± 1 nm and gives n_g (about
3× slower).* or *Group index off: the next run is one solve, without n_g.*) adds
`results.group_index = {"wavelength_step": "1 nm"}` to the run's document. Every material of
the optical model is a physmat record, and the engine evaluates each one at every wavelength it
solves (λ, and λ ± 1 nm for n_g), so n_g includes the material dispersion; **Physics › Optical
modes** says so under **Material data**: *physmat materials, evaluated at each wavelength solved*. The engine then also
solves the same mesh at λ0 − 1 nm and λ0 + 1 nm, with each material evaluated at each
wavelength, and returns n_g = n_eff − λ0 dn_eff/dλ0 by a central difference. The run takes about
three times as long ([group index of a single study](group_index.md)). With the box off, the
document is the `optical-shapes-v8` document as before, byte for byte. With it on, the only
difference is `results.group_index`, and n_eff and the fields at λ0 are the same values. The
box is saved with the model, like Modes to find, and **Undo** and **Redo** cover it. A new model
starts with it off. Opening an input file sets it from the file (off for version 6 or 7). Opening
a session sets it from the session's input when that is of version 8, else from the selected
run. **Use this run's inputs** sets it from the run: on for a run with n_g. It is part of the study a run is compared with: with the box on, a run without
n_g is not of the current inputs, and a document check made with the box off is of earlier
inputs. The adapter stays `optical-shapes-v8` and the run's `settings` are unchanged. The run
table CSV has n_g in its `group_index [1]` column.

A run with n_g keeps it in the version 9 slots `group_index` and `group_index_method`. Its
document is rebuilt from its settings, as for any run, with `results.group_index` added, whose
`wavelength_step` is the step named in `group_index_method`.

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

Choose **Library → Steady heat conduction** to edit a steady heat problem
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
restored. **Run study** builds a `thermal.steady2d` document (see **Study** for
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

Choose **Library → Joule heating** to set up steady Joule heating on named
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
reason is shown otherwise. **Run study** builds the
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

Choose **Library → Heated silicon waveguide** (“Heat → optical modes · coupled”) to open a
[multiphysics document](multiphysics_document.md): two physics on one geometry and one mesh,
joined by a coupling, solved by one **Run**. The template is a 500 × 220 nm `physmat:Si` core on
`physmat:SiO2` in a 6 × 4.5 µm window, with a 2 µm × 100 nm heater 1.1 µm above the core. **Heat 1**
holds the bottom edge at 300 K and heats the heater region; **Modes 1** finds the optical mode at
1550 nm; the coupling **Heat 1 temperature → Modes 1 temperature** gives every triangle the mean
of its three node temperatures, and the optical solve uses n = n₀ + (dn/dT)(T − T_ref) there. The
heater is a local record with a lossless placeholder index; metal loss is later work.

The workspace edits the document itself, so it keeps every key it has no form for, and
**File › Open…** opens any multiphysics document, such as the
shipped [heated slab example](../../../examples/simcase/multiphysics_heated_slab.json).

- **Model builder.** One Component (Geometry 1, Materials with one item per material in use,
  Mesh 1 shared by every physics), the physics with a badge giving their place in the solve
  order (a cycle shares one amber number), **Couplings** with one item per coupling named in
  words, and **Study** with the **Study 1** node, the derived solve order and any iteration step
  (the group is *Study*, so no two items of the tree share a name). Settings shows the
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
  *Modes 1 effective index (single numbers, not a map)*. Opened for one input (**Add coupling**
  from a suggestion in Messages), From lists only the outputs that input can take: a
  temperature input is offered temperature fields only. The transfer is Same mesh, the only one in this release. When an
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
- **Run study** solves every physics in solve order, with the same ▶ and label as the
  single-physics models. The ▶ is decoration with an empty alternative text, so screen readers
  read the label alone (“Run study”). The Study dock lists each physics or iteration
  step with its state (Waiting, Solving…, Done in 0.3 s, Iteration 7 of up to 30 with the last
  change, Did not settle, Not run), Connections shows the same states while it is open, and **Stop run**
  ends the run at the engine's next step: after the physics being solved, or inside an
  iteration step after the current iteration. A run that fails or is stopped keeps no partial
  result; Messages names the physics that failed, and the previous complete run stays. A sweep
  is checked but not run (the run reason says so). An edit after a run marks **Out of
  date (last run: Done in 0.3 s)** the rows of the steps whose inputs it changed, on the dock and
  in Connections: a step's own physics, the couplings into it, the shared geometry, materials, mesh
  and study, and every step upstream of it. Removing only the coupling into the optical modes
  leaves *Heat 1 · Done in 0.3 s* and marks *Modes 1 · Out of date (last run: Done in 1.2 s)*; the dock heading reads “Run 1 ·
  the model changed since; press Run to update” and the footer “Model edited since run 1 · press
  Run to update”. Whether a run is current is decided by content: an edit undone by hand (a
  coupling removed and added back, or Undo) makes it current again, and Messages, the dock
  heading and the footer then say the same sentence, “No need to run: Run 1 already has these
  results. Run study adds a copy with the same values”, which says first that nothing needs running
  (Messages adds “Also solve without heater” is ticked again when an Undo ticked it again). Messages
  also offers **Show Run 1**, which shows that run under Results without changing the model. A run read
  from a session file or recovered from this browser has no solve times: its rows read **From
  file** or **From this browser** (an iteration step keeps its count, *Settled in 7 iterations · from
  file*), the dock heading “Run 1 · read from file, not recomputed” (or
  “recovered from this browser, not recomputed”) and the footer adds “press Run to compute it
  here”; a run made in the tab keeps the words above. A named run is “Run N · name” in the dock
  heading and the footer, as in the optical application: “Run 1 · Heater 2e14 · solved from the
  current model”, “Run 1 · Heater 2e14 matches the model · press Run to solve again”, “Model
  edited since Run 1 · Heater 2e14 · press Run to update”.
- **Also solve without heater** (beside Run, *(about 1 s more)*) is on when a model whose optical modes
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
  core. The modes table has the optical application's columns, | Mode | n_eff | Polarization |
  Absorption loss (dB/cm) | A_eff (µm²) | ([Modes table](#modes-table); *Loss (dB/cm)* for a result with an open boundary), names its rows *Mode 1*, …, and the note under it gives the
  ranking sentence, “Modes are ranked by effective index.”, and the number of modes the model asks for, “This model asks for 2 modes: Modes 1 ›
  Modes to find” (the template asks for two, so its table shows a TE-like and a TM-like mode), a link to that setting (after an edit, “This run asked for …”). The n_eff table has “n_eff without heater” and “Δn_eff (coupled − without heater)”, signed and
  with the 8 decimals of n_eff (the template gives +0.00215086). The note under the table says
  what the baseline is: “without heater = Modes 1 alone with no temperature input: every material
  keeps n₀, its index at T_ref = 300 K”. The column is valid while the optical model solved alone
  (the run's document without couplings, loops and thermo-optic keys, compared with sorted keys)
  is the one of the shown run; otherwise it is marked “(other model)”, Δn_eff is left out, and
  **Run Modes 1 alone** refreshes it. A result names its run and does not change when the model
  is edited.
- **Runs.** Up to six runs are kept, with the optical rules and words: Results › Runs lists
  “Run N · name · time”, **Run name** (Enter pins) and **Unpin this run**; pinned runs stay, and
  when a new run arrives the oldest unpinned run is replaced. Selecting a run shows its result
  and its freshness line; it does not change the model. With six pinned runs, Run says to unpin
  one first.
- **Files.** **File › Save** writes the model with its runs, their names and pins and the
  without-heater results to one file, `<model-name>-session-YYYY-MM-DD-HHMM.json` (the model
  name lowercased, other characters as hyphens, at most 40 characters, else `multiphysics`),
  described in [Session files of multiphysics models](#session-files-of-multiphysics-models-version-8).
  When the tab also holds Optical waveguide runs, the save message says they are not in this
  file: “The 2 Optical waveguide runs of this tab are not in this file; Library › Optical
  waveguide, then File › Save, keeps them in their own file.”
  **File › Open…** opens such a file, an optical session, or a model file alone (“Opened model
  file …: it holds the model but no runs.”). **File › Export › Model file…** writes the document
  alone, as a model file named after the model. The title uses the optical
  words: “Not saved to a file · kept for recovery in this browser”, “heated-silicon-waveguide-session-….json · downloaded 10:15”, “Opened …”, “Recovered from this browser”. Before leaving a model
  whose runs no session file holds (another model card, the template again, an opened file or
  inputs), Studio asks first: “Leave this model? 3 runs are only in this tab and in browser
  recovery. Save session first to keep them in a file.”, with **Cancel**, **Save session** and
  **Leave**. Opening a multiphysics model over optical runs that are in no session file names
  them the same way and offers **Save session, then continue**; those runs stay in the tab and
  come back with the optical model. The graphics footer names the geometry's length unit
  (“Lengths in µm; …”). An
  opened file is read by the server first, so a duplicate key or text that is not JSON is
  refused by name; a saved file writes each number in its shortest form. A sweep is checked,
  and this view runs one point only.

Studio runs these documents through `/api/multiphysics/*` (validate, run, progress events,
stop, result), as an ordinary consumer of `simcase.multiphysics`; the n_eff it shows is the
engine's for the same document, exactly. CI drives this model in a real browser
(`tools/studio_browser/studio_multiphysics_browser.mjs`, and
`studio_multiphysics_session_browser.mjs` for its session files), and
`tests/simcase/test_studio_multiphysics.py` and `studio_workspace_multiphysics.cjs` check the
routes and the words. Limitations: only heat transfer (`thermal.steady2d`) and optical modes
(`em.modes2d`) are edited here; the Same mesh transfer only; no multiphysics sweep runs; the
geometry form edits rectangles and the window, other shapes stay as written in the file.

### Session files of multiphysics models (version 8)

A multiphysics model is saved as a session file of **version 8**; optical sessions are still
written as version 7, byte for byte as before, so a file shared with an earlier Studio keeps
opening there. This section is the public statement of the format.

```json
{"format": "openphysics-studio-session", "version": 8, "application": "multiphysics",
 "document": {"openphysics": "0.3/multiphysics.1", "name": "Heated silicon waveguide", "...": "..."},
 "runs": [{"job": "mp-3f2a9c1d7e4b", "number": 1, "label": "Heater 10 mW", "pinned": true,
           "completedAt": "2026-11-22T10:15:03.120Z", "serverVersion": "0.0.2",
           "document": {"...": "the document this run solved"}, "events": [{"event": "physics_started", "physics": "heat1"}],
           "maps": "kept", "result": {"result": "multiphysics-run-v1", "...": "..."}, "digest": "sha256:9c1e…"}],
 "baselines": {"modes1": {"job": "mp-77a01b2c3d4e", "completedAt": "…", "document": {"...": "Modes 1 alone"},
                          "result": {"type": "em.modes2d", "effective_index": {"unit": "1", "values": [[2.443499265702046]]}, "...": "..."},
                          "digest": "sha256:41d0…"}},
 "selected": "mp-3f2a9c1d7e4b",
 "view": {"page": "Results", "selection": "results:modes1", "index_map": "change", "baseline_option": true}}
```

- `application` is required and `"multiphysics"` is its only value in version 8. `document` is
  the model as it is now (it may differ from every run), written as File › Export › Model file writes it.
- `runs` holds up to six runs in completion order. `job` is the server's job identifier
  (`mp-` and 12 hex digits), `number` the “Run N” shown (the next run is numbered after the
  highest stored), `label` and `pinned` follow the optical rules (at most 80 characters, no
  control characters). `document` is the document the run solved; whether the model changed
  since is decided as on screen, by comparing it with the current model with sorted keys.
  `events` are the run's progress events (the Study dock rows). `result` is the reply of
  `/api/multiphysics/jobs/{job}/result` unchanged (`multiphysics-run-v1`; a one-physics `"0.3"`
  model run in this view keeps the reply of its kind, for example
  `em-modes2d-p1-node-centroid-v2`): the solve order, the per-physics results, the coupling
  records, each iteration step with its residuals, the shared mesh (`node_coordinates` in m,
  `triangles`, `regions`, `region_names`), the heat temperature per node (K), and for the
  optical modes `effective_index` and the per-triangle coupled `temperature` (K),
  `refractive_index.n`, `refractive_index.k` (null when lossless) and `index_change` (null
  when a material has no thermo-optic model). Mode fields are not in the reply and not in the
  file.
- `maps` is `"kept"` or `"not kept"`. A run whose maps are not kept has `counts`
  (`{"nodes": N, "triangles": M}`) and a `result` without `mesh` and without the per-node and
  per-triangle values; it keeps the solve order, the coupling records, the iteration steps
  with their residuals, `effective_index` and the heat range and summary. On screen it reads
  “Maps not kept in this file: n_eff, the coupling check and the iteration history are.” and
  the run list says “values only”.
- `baselines` holds at most one without-heater result per optical physics: the uncoupled
  document solved and the modes part of its reply. Its tie to a run is decided from content on
  open (the run's document without couplings, loops and thermo-optic keys, compared with sorted
  keys), not by a stored key, and a baseline that belongs to no run in the file and not to the
  model refuses the file.
- `selected` is the run shown under Results (or null); `view` is the page (`Model`,
  `Connections` or `Results`), the selected tree item, the index map (`index` or `change`)
  and the “Also solve without heater” option. Undo history, a comparison, failed or stopped
  runs and the provider list are not stored.
- **Numbers.** Every number is JSON in its shortest round-trip form, as JavaScript's
  `JSON.stringify` writes it (ECMAScript Number::toString), except negative zero, written
  `-0.0` so that it reads back as negative zero. NaN and the infinities are never written and
  are refused when read. Integers stay integers. Every stored value comes back bit for bit.
- **Digest.** Each run and each baseline carries `"digest": "sha256:<hex>"`, the SHA-256 of
  the record without its `digest`, written as JSON with the keys of every object sorted and
  the same number rules. It detects a truncated, damaged or hand-edited file. It is not an
  authentication: whoever edits a file can recompute it, so opened results read
  “Loaded from file, not recomputed. Results match the file's checksum.”, and that sentence's
  title text says *The checksum detects a damaged or hand-edited file; it does not show who
  made the file: whoever edits a file can recompute it.*
  Recovered results read “Recovered from this browser, not recomputed.” An optical session
  file carries no digest; its opened results read “Loaded from file, not recomputed. Studio
  checks that the file is well formed, not who made it.”
- **Size.** A file is at most 16 MiB, checked before it is read, and each document in it at
  most 1 MiB. Save session writes every run with its maps when the file fits (six runs of the
  template mesh are about 2.5 MB). When it does not, it writes nothing and asks, naming the
  size: “Session is 22 MB; the limit is 16 MiB. Keep the maps of the selected and pinned runs
  only? …”; **Keep maps for selected and pinned runs** writes the others as `"maps": "not
  kept"`, **Cancel** writes nothing. When even the selected and pinned runs are over the limit,
  Save session refuses and names them (“Run 3 alone is 18 MB, over the 16 MiB session limit.
  Unpin it or keep it in a smaller-mesh model.”). Maps are never dropped without saying so.

**Opening.** Results are read from the file, not recomputed: the notice reads “Opened … Its
results were read from the file, not recomputed; input undo starts here.”, runs say “from file”
(or “recovered”), and opening never starts a run. Every check runs before anything in the tab is
replaced; a failure refuses the whole file with a message that names the check, and the model,
its runs and Undo stay as they were:

- the size and the JSON (a leading byte order mark is removed), at most six runs, unique job
  identifiers and run numbers, valid names, pins, times and server versions, `selected` a stored
  run, and the view one the workspace offers;
- each run's result against its document: the physics names and types, the solve order the
  server derives for the document, the couplings with the same `from`, `to` and `transfer` (and
  for Same mesh a matching mesh and a difference of 0), and the iteration steps of `study.loops`,
  each converged, with one residual fewer than its iterations and the last at most the tolerance;
- for kept maps: `node_coordinates` N × 2 and finite, `triangles` M × 3 with integers in [0, N),
  `regions` M integers naming a region, the node temperature N finite values, each per-triangle
  map M finite values, a finite `effective_index`, the heat range exactly the minimum and maximum
  of the stored temperatures, and the coupled temperature the mean of each triangle's three node
  temperatures within a relative 1e-12;
- the digest of every run and baseline (“Run 2 changed after it was saved (its check value does
  not match).”);
- the server's check of every run and baseline document with the rules of `simcase validate`
  (“Run 2's model does not pass today's check: …”), a document Studio runs, and the current model
  read as File › Open reads a model file (its problems open into Messages). Without the server the
  file is not opened.

A version above 9 is refused by name (“This session file is version 10, newer than this Studio
reads (versions 6–9). Open it in a newer Studio.”; version 9 is an
[optical session](#optical-session-files-version-9), and a version 8 layout under version 9 is
refused by its first unknown key), as are another `application` (“This session
file holds a “…” model, which this Studio does not read.”), another result (“Run 2 was saved as
result “multiphysics-run-v2”, which this Studio does not read.”) and another document envelope
(the server reader's refusal, named in the run). Session files of versions 6 and 7 open as
before; versions 1 to 5 keep their refusal. A Studio from before version 8 refuses a version 8
file or recovery record with “Unsupported session format or run count.” and keeps its workspace,
so multiphysics sessions need this Studio or a newer one.

**Browser recovery** keeps a multiphysics model in the same store as optical sessions, with the
same limits (one latest and three earlier sessions, each at most 16 MiB, written 0.7 s after a
change, the cross-tab conflict rule). It writes once the model has a run or was edited since it
was opened, as the version 8 text Save session would write. Over 16 MiB it keeps the maps of
the selected and pinned runs only, without a dialog, and the indicator says “kept for recovery in
this browser without the maps of 2 runs · File › Save keeps them”; when even that is over the
limit it writes nothing new (“browser recovery unavailable: session over 16 MiB”) and the earlier
record stays. **Restore last session from this browser**, **Restore earlier session from this
browser · Heated silicon waveguide · 3 runs · Run 1, Run 2, Run 3 · time** (Workspace tools) and
the Heated silicon waveguide card's **Restore from this browser** run the same checks as Open
session. A restored record that was the same as the session file it was saved to, or opened
from, reads *Recovered from this browser · same as file …json*, as an optical one does. A
template just opened reads *New model · not saved* until its first edit, run or save.

The module checks are in `tests/simcase/studio_workspace_multiphysics_session.cjs` (the optical
files of versions 6 and 7 written by the Studio before version 8, in
`tests/simcase/studio_session_fixtures/`, open and are written byte for byte as before),
`tests/simcase/test_studio_multiphysics_session.py` recomputes the digests with Python's
hashlib and its own writer, and the browser check saves, opens and saves again the template, a
0.12 µm mesh and a two-run session (the second file byte-identical, every array equal to the
server's reply as Float64), six runs of a 0.08 µm mesh against the 16 MiB limit, the refusals
and browser recovery. Not in version 8: a session mixing optical and multiphysics runs, one
mesh shared between runs, adding runs from a file, and mode fields of coupled runs.

## Results and files

The notebook retains up to six successful runs, preserving pinned references. Select a mode to inspect
its field or compare two runs. Mode numbers are ranks by effective index; Compare matches modes between
two runs by field overlap.
Field colours use the vector magnitude normalized separately per mode;
they do not represent optical power or a common physical colour scale.

### Modes table

Results show one table per run, | Mode | n_eff | Polarization | Absorption loss (dB/cm) | A_eff (µm²) | n_g |, in the optical
application, and the same table without n_g in a multiphysics model's Modes 1 page. “Modes are ranked by effective index.” (the optical
application adds “Compare matches them between runs by field overlap.”)
Every value is defined on the saved centroid field `unnormalized_electric_field`, so Studio, the
engine and older session files give the same number from the same samples:

- **Polarization** is the TE fraction `f_TE = Σ A_T |E_x|² / Σ A_T (|E_x|² + |E_y|²)` over every
  triangle of the window (the column help: “TE = share of |E_x|² in |E_x|² + |E_y|², x
  horizontal”), shown as a word and the TE percentage, e.g. *TE-like · 98.2 % TE*; a TM-like cell names its TM
  share first, *TM-like · 96.9 % TM (3.1 % TE)*, and a hybrid cell names both, *hybrid · 21.7 % TE /
  78.3 % TM*. Both shares come from the one fraction: TE is f_TE × 100 rounded to one decimal, and
  TM is 100 minus that rounded TE, so the two add to exactly 100.0 as shown. Studio's words
  are **TE-like** at f_TE ≥ 0.9, **TM-like** at f_TE ≤ 0.1, otherwise **hybrid**; the engine saves
  only the number (`te_polarization_fraction`, [result format](overview.md#mode-post-processing)).
- **Degenerate pairs**: two adjacent modes of one run whose Re n_eff differ by at most 1e-3 share one
  merged cell (shown only when both have a fraction), *pair (n_eff within 1e-3) · 50 % TE together*, the mean of their two fractions;
  its tooltip says each member's polarization is not defined (any rotation within the pair is a
  solution). The field view's mode picker names a member *pair*. The threshold is 1e-3 because the
  mesh splits a symmetric pair (a square core) by 1e-4 to 6e-4 at 40 to 10 nm, below the solver's
  n_eff error at those meshes. A mesh split above 1e-3, possible on very coarse meshes, is not
  flagged, and a member's polarization is then a rotation chosen by the mesh.
- **Absorption loss (dB/cm)** comes from Im n_eff: dB/cm = 20 · log10(e) · k0 · Im(n_eff) / 100 with k0 = 2π / λ0 in
  1/m (exp(−iωt), Im n_eff > 0 is loss), the engine's `propagation_loss = (40π / ln 10) · Im n_eff
  / λ0` in dB/m divided by 100, shown to 4 significant digits (*37.49 dB/cm*). In a closed window
  the column counts material absorption (k) only, and its header, the help of every cell and the
  note below the table say so: the help reads “Absorption (material k) only; leakage and
  radiation are not computed in a closed window”, the note “Absorption loss counts material
  absorption (k) only. Leakage and radiation are not computed in a closed window.” Where every
  Im n_eff is exactly 0 each row reads *0 dB/cm*, a lossless run rather than a computed
  zero, and the note reads “Absorption loss counts material absorption (k) only: all materials
  have k = 0 at this wavelength, so it is 0 dB/cm. Leakage and radiation are not computed in a
  closed window.” A multiphysics result with an open boundary (PML) has an Im n_eff that includes
  leakage into the PML, so its column reads **Loss (dB/cm)**, with the help “Material absorption
  (k) and leakage into the PML of the open boundary” and the note “Loss includes material
  absorption (k) and leakage into the PML of the open boundary.”; every other table reads
  **Absorption loss (dB/cm)**. Compare shows the same value as *Absorption loss A (dB/cm)* and
  *Absorption loss B (dB/cm)*. There is no threshold: a nonzero Im n_eff,
  however small, is shown as it is. The engine returns a complex n_eff only for a material with
  k > 0 or a PML; a lossless problem gives a real n_eff, whose Im is exactly 0. The optical
  application's materials and the heated template are lossless, so they read 0 dB/cm; a
  multiphysics session or model file can hold a complex n_eff (a lossy material or a PML), whose
  loss is shown as a number. Loss is display only: the result and session formats are unchanged.
- **A_eff (µm²)** is the effective area `(Σ A_T |E|²)² / Σ A_T |E|⁴` over every triangle of the
  window with all three components, `|E|² = |E_x|² + |E_y|² + |E_z|²`, to 4 significant digits
  (column help: “Effective area (∫|E|²)²/∫|E|⁴ over the window, all three field components”;
  `effective_area`, [result format](overview.md#mode-post-processing)). It is the common
  mode-solver form, not the vectorial nonlinear area. A member of a degenerate pair shows its own
  value, and its tooltip says that value depends on the rotation within the pair. A scalar
  multiphysics result shows the engine's |φ|² area.
- **n_g** (optical application only) is the engine's group index to 4 decimals, from a run with
  **Also compute group index** on. The column help reads “n_g = n_eff − λ0 dn_eff/dλ0: central
  difference over λ0 ± 1 nm (3 solves), materials evaluated at each wavelength”. A cell reads
  **—** in two cases:
  - The run did not compute n_g. The help reads “Turn on Also compute group index in Study or Optical modes”,
    and the line above the modes table reads *n_g: Off · turn on in Study or Optical modes*; the
    header reads just *n_g* (Compare, when neither run computed n_g, has the same line above its
    table, so the n_g columns stay narrow).
  - The engine could not match that mode at a side wavelength (`null`, for example one member
    of a degenerate pair). In the tab that ran it, the help gives the engine's reason,
    *Not matched: vacuum_wavelength 1.549 um: …*. A session file does not keep the reasons, so
    after opening one the help reads “Not matched at λ0 ± 1 nm; the reason is not kept in
    session files”.
- The field view's mode picker reads *Mode 1 · TE-like · n_eff 2.44406001*.

Run details say where the fraction and the effective area came from: *computed by the engine from the saved field* for
a run computed in this tab, *computed by Studio from the saved field* for a run opened from a
session file (optical versions 6 and 7 store the samples, not the fraction; the files are
written exactly as before). Multiphysics runs take the engine's value; a version 8 run saved
before Studio kept it, or a scalar-formulation run, shows “—” (its tooltip says *Run again to
compute*, or that the scalar formulation has no polarization). The effective area follows the
same rule: optical runs of version 6 and 7 files show the value Studio computes from the saved
samples (Run details: *Effective area · computed by Studio from the saved field*), and a version
8 run saved before Studio kept it shows “—” with *Run again to compute*; no session version
changes and optical version 7 files are written byte for byte as before. Version 8 files now also read a
complex effective index `{re, im}`. The run-table CSV keeps its `candidate` column name.
An optical session of [version 9](#optical-session-files-version-9) keeps the engine's
`te_polarization_fraction` and `effective_area` with each run, so a run opened from it shows
*computed by the engine from the saved field*; a run whose fields that file did not keep shows
*saved in the session file; its fields were not kept*.

Save input JSON to keep the design, or save session JSON to include validated
results. Open restores these files; input-only files are limited to 64 KiB and
sessions to 16 MiB. CSV and PNG exports are available. These workspace
formats are separate from headless simcase JSON documents. After reload, explicitly choose Restore last session from this browser for the committed browser
snapshot, or Open session for a portable file. Pending writes are not a backup.

A download request does not confirm that the browser wrote a file to disk.
Check the browser download before relying on it as a portable backup. The input
and session indicators compare against the last save/open snapshot or download
request; an unchanged indicator does not certify download completion. Browser
recovery reports its own committed storage state separately.

Input files are version 7, or [version 8](#study-settings-in-input-files-version-8) when they
hold study settings. Version 7 is version 6 (the units and naming batch) plus the Joule heating
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
page shows it) and the candidate number carry no unit. `effective_index [1]` is Re n_eff. Two
columns follow `origin`, so every earlier column keeps its place: `effective_index_imag [1]`,
Im n_eff under exp(−iωt) (0 for a lossless run, whose n_eff is real), and `group_index [1]`, n_g
of a run with the group index (empty when the run has none or the mode has no value).

Optical session files are version 7, whose input is an input file of version 7 (a version 6
session is still read, its input as a version 6 input file; a multiphysics model is saved as
[version 8](#session-files-of-multiphysics-models-version-8); a session with a run that version 7
cannot hold is saved as [version 9](#optical-session-files-version-9)); version 6 was written since the units and naming batch: the workspace
builds a format 0.3 document (lengths as quantity strings such as `"1550 nm"`, materials
under their exact `physmat:` names) and each run record keeps the result's
`effective_index` (Re and Im under exp(−iωt)) and field samples with `node_coordinates` in
metres, and its input as an input file of version 6. Sessions of versions 1 to 5 hold
results under the earlier names and the document length unit; the workspace refuses them
by version with a message instead of reading them under another meaning. Enter the design
again, run it and save a new session.

The workspace checks `/api/workspace/capabilities/v8` before enabling Run. Contract
version 8 (the content of version 7 with runs of 1 to 8 modes: the settings drop the fixed
`mode_count: 2`, and `mode_count_range: [1, 8]` and `mode_count_default: 2` stand beside them;
version 7 is the content of version 6, for a workspace that saves input and session files of
version 7; version 6 is the content of version 5 for files of version 6 and the coded
`diagnostics` of a document check) and adapter
`optical-shapes-v8` (the document of `optical-shapes-v7` with the mode count asked for) declare the window in nm, at most eight
shapes and twelve polygon vertices, the shape types and the ten materials with their
`physmat:` names, the 1400–1700 nm wavelength and 20–60 nm core mesh ranges (quantity
strings), the fixed window and boundary settings, the mode count range,
`optical: true`, `coupled: false` and `simcase_version`. A workspace request (one that names
its `workspace_instance`) to `/api/validate` or `/api/run` whose `em.modes2d` physics asks
for another `mode_count` is refused with *Modes to find must be a whole number from 1 to 8
(got 9).*: 0, 9, 2.5, 2.0, `"2"` and `true` are refused; requests of the single-page Studio
are read under the document's own rules. A missing or incompatible
contract blocks execution; **Check connection** retries. Each submitted run
captures its shapes, wavelength, core mesh and the reported simcase package version and preserves them in session JSON.
The earlier capability endpoints (`/api/workspace/capabilities` and `/v2` to `/v7`) remain
available at the same paths and schema versions, `/v7` with its fixed two modes;
because every adapter now writes format 0.3 documents and reads the new result names, each
names its family's next adapter version (`optical-fixed-v2`, `optical-rectangle-v4` and `-v5`,
`optical-shapes-v6` and `-v7`), with its values as quantity strings.
This is not a complete engine dependency or Git provenance record.

### Study settings in input files (version 8)

Version 8 is version 7 with the optical study settings in `model`, after `model.joule`:
`modeCount` (Modes to find, a whole number from 1 to 8), written only when it is not 2, and
`groupIndex` (`true`), written only when **Also compute group index** is on. Inputs with
2 modes and the box off are written as version 7, byte for byte as before, so such a file still
opens in an earlier Studio, and opening a version 6 or 7 file never rewrites it. A version 8
file is read with both keys checked (a `modeCount` outside 1 to 8 or a `groupIndex` that is not
a boolean is refused); one whose values are the defaults reads as version 7 inputs. A Studio that
reads input files up to version 7 refuses a version 8 file with *Unsupported project format or
version.* A run keeps its inputs as version 7: its `settings.mode_count` and its group index hold
its study. A session with no runs takes its settings from its input alone (2 and off for a
version 7 input).

### Open boundary document (optical-shapes-v9)

`/api/workspace/capabilities/v9` is version 8 with adapter `optical-shapes-v9` and an
`open_boundary` block. The page still checks version 8 and has no control for it yet. The
adapter's document builder (`opticalDocument` with `openBoundary: {edges, thickness, target}`)
can open any edge of the window:

- a perfectly matched layer (PML) of thickness *t* = 1 µm (1000 nm, the one value offered)
  lies **outside** the 3 × 2.4 µm window on each open edge: the domain grows by *t* there and
  the outer wall stays PEC. Closed edges stay PEC walls;
- a polygon edge along an open edge continues straight through the layer, and where two open
  edges meet at a shape's corner the corner square is filled too (a substrate that fills the
  bottom of the window reaches the outer wall). A circle meets an edge only at a point and is
  written as before;
- the PML settings are fixed: `pml_strength` 3, `pml_order` 2,
  `pml_minimum_physical_fraction` 0.5 and `pml_search_mode_count` 32;
- **Search near n_eff** (`target_effective_index`) is above 1.45 and below the largest
  index of the design. By default it is (n_max + n_SiO2) / 2 to two decimals, from the
  materials' indices at 1550 nm (2.46 for a silicon core);
- the group index is not computed with an open boundary.

With every edge closed, or without `openBoundary`, the document is the `optical-shapes-v8`
document byte for byte, and its results are those of that document. A workspace request whose
`em.modes2d` physics has any other `pml` (another thickness, unequal thicknesses or another fixed
value), a target of 1.45 or below, or a domain other than the window grown by the thickness on
exactly the open edges (in nm) is refused with *The open boundary of a workspace run has a PML of 1 µm on each open edge
with strength 3, order 2, physical fraction 0.5 and a search of 32 candidates.* The PML results
are candidates under the [PML mode rules](pml_modes.md).

Limits of the open boundary, from its validation:

- **One search target.** The candidates are the eigenvalues nearest **Search near n_eff**, and the
  PML's own modes crowd the region around it. A mode far from the target can be missed even when
  fewer modes are found than asked: a strip over a silicon substrate has a third mode near the
  cladding index (n ≈ 1.486 + 0.008i, about 2800 dB/cm) that the default target 2.46 does not
  reach with 32 candidates. To find modes near the cladding index
  (Re n_eff below about 1.6), lower Search near n_eff (for example to 1.95).
- **Why 1 µm and 32.** With the mesh held fixed, a 1.5 or 2 µm layer changes the loss by at
  most 0.02 % and n_eff by about 1e-8, so it adds no accuracy; it adds PML modes near the target,
  which pushed the TM-like mode of the strip over a substrate out of a search of 16. 32 keeps
  it at every thickness tested.
- **Mesh error at the default mesh.** The default mesh overestimates the strip-over-substrate
  loss by about 3 % (TE-like +2.8 %, TM-like +1.8 %, against the value extrapolated from 0.7, 0.5
  and 0.35 × the element lengths: 28.35 and 988.7 dB/cm). The leaky slab against its analytic
  pole is an independent check of the same size: +2.96 % (TE) and −1.41 % (TM) at the default
  mesh. As first registered, the convergence check (× 1, 0.7, 0.5) failed: the TE-like loss
  changes were 0.096 then 0.301 dB/cm, so it was registered again, after that result, at 0.7, 0.5
  and 0.35 ×. The values it was planned from (28.72 and 28.55 dB/cm at 0.7 and 0.5 ×) were
  reproduced neither with the refinement distance fixed nor with it scaled.
- **The PML settings are part of the search.** Changing the PML thickness, strength or order
  changes the spectrum of the PML's own modes and can make a fixed search miss modes: with a search
  of 32 near 2.46, the TM-like mode of the strip over a substrate is missing at strength 1.5. The
  page does not let these settings change.
- As first validated, the thickness check (V4: the window meshed again for each thickness,
  search of 16) failed four times: at 1.5 µm the TE-like loss moved by +1.28 % and n_eff by 8.7e-4
  (a remeshing difference: −0.31 % and 4.3e-4 at 0.7 × the element lengths), and the TM-like mode
  was missing at 2 µm and at strength 1.5 and 6. Registered again on one mesh with the search of
  32, it failed a fifth time: the TM-like mode was missing at strength 1.5. PML independence is
  now checked with a search that reaches every reference mode, and the shipped search separately
  for completeness.
- The filter check (V8) first asked that the analytic slab mode come back within 1e-3 of its pole,
  a tolerance chosen when the test was written, not registered. It failed for 1 to 4 modes: the
  returned TE mode is 4.76e-3 from the pole at the default mesh, the discretization error the slab
  convergence check measures (it gates n_eff within 1e-3 only at 1/4 of the element lengths). After
  that result the mode is identified as the one nearest the pole and must meet the slab check's
  default-mesh gate (loss within 3.5 %; it is +2.96 %). Its first rule for known misses also
  failed for the slab: it counted the slab's lateral harmonics that a search near 1.95 finds
  (Re 2.38 to 1.90, ranked 5th and beyond), modes outside the asked count. After that result a
  known miss is a physical mode of the two searches that ranks within the asked count and is not
  returned; the only one is the strip-over-substrate mode near 1.486 when 8 modes are asked.

### Optical session files (version 9)

A session in which every run has two real modes and its fields is written as version 7, byte
for byte as before. Version 9 is written once the session holds a run that version 7 cannot
hold: a run of 1 or of 3 to 8 modes, a complex effective index, a run without its fields, or a
view of mode 3 or higher, or an input of
[version 8](#study-settings-in-input-files-version-8). Opening a version 6 or 7 file never rewrites it: its runs read two
modes, with the TE fraction and effective area Studio computes from the saved samples, and the
session is written as version 7 again. A Studio before version 9 refuses a version 9 file with
*This session file is version 9, newer than this Studio reads (versions 6–8). Open it in a
newer Studio.* Multiphysics sessions stay version 8. Browser recovery keeps the same text, so
the same rules apply.

A version 9 file is one JSON object with exactly the keys `format`
(`"openphysics-studio-session"`), `version` (9), `application` (`"optical"`), `input` (an input
file of version 7), `runs` (at most six), `selected` (a run's `job` or null), `comparison` (two
`job`s or nulls) and `view` (all required; as in version 7, with `mode` 0 to 7 and below the selected run's
mode count). Its `input` may also be an input file of version 8 (study settings): a session
whose input is of version 8 is written as version 9 even when every run fits version 7, and a
version 6 or 7 session holding one is refused (*A version 7 session holds an input file of version
6 or 7.*, and likewise for version 6). A run read from a version 6 or 7 file whose indices are not
ranked above n = 1.45 can therefore not be saved while Modes to find is not 2 or the group index
option is on: the refusal names the run and says that the setting asks for version 9. Browser
recovery keeps working: it keeps that notebook as version 7 without the setting, and says so once
in the message line and in the recovery details (*Browser recovery kept this notebook without
Modes to find 3: …*). A Studio that reads input files up to version 7 refuses such a version 9 file with *Unsupported project
format or version.* Each run has these keys, in this order; any other key is refused by name:

| Key | Type | |
| --- | --- | --- |
| `job`, `completedAt`, `label`, `pinned`, `origin`, `serverVersion`, `input` | as in version 7 | required |
| `settings` | version 7's, with `adapter: "optical-shapes-v8"` and `mode_count` 1 to 8 | required |
| `effective_index` | k numbers, or `{"re": [k], "im": [k]}`; 1 ≤ k ≤ `mode_count`, ranked by Re n_eff, every Re above 1.45 | required |
| `field` | `{node_coordinates, triangles, real, imag}` of k modes (as in version 7, only these four are read; another key inside `field` is not refused, is covered by the digest and is not written again) | optional |
| `te_polarization_fraction` | k numbers in [0, 1] or null: the engine's (for a run written without `field`, the values it showed) | optional; required without `field` |
| `effective_area` | k numbers in m² above 0 or null: the engine's (for a run written without `field`, the values it showed) | optional; required without `field` |
| `group_index`, `group_index_method` | k numbers or null (null: a mode the engine did not match); a text of 1 to 64 characters, only with `group_index`, written as `central_difference <step> <tracker>`, such as `central_difference 1 nm electric-l2-assignment-v1` | optional: present for a run with Also compute group index |
| `digest` | `"sha256:<hex>"` | required |

The digest is the SHA-256 of the run without its digest, as sorted-key JSON with the number
rules of version 8 (negative zero written `-0.0`), so it covers every other key the run has; a
changed run is refused with *Run 1 changed after it was saved (its check value does not
match).* A mode count over 8 is refused with *Run 1 asks for 9 modes; this Studio reads 1 to
8.* Studio does not write what it would refuse: a run read from a version 6 or 7 file whose indices are not ranked above n = 1.45 can stay in a version 7 session, but a save that needs version 9 is refused naming it. Numbers are written as in version 8; a file Studio wrote from runs it read (whose origin is
then `imported`) is written again byte for byte. The digest detects a damaged or hand-edited
file; it is not an authentication.

Six runs of 8 modes on the template's mesh (2275 triangles) are about 9.4 MB, about 0.2 MB per
mode, under the 16 MiB limit. A session over the limit asks first, as a multiphysics session
does: *Keep fields for selected and pinned runs* writes the other runs without `field`, with
their n_eff, TE fractions and effective areas; Cancel writes nothing; when even the selected
and pinned runs are over the limit, the save is refused, naming them. Browser recovery keeps
the fields of the selected and pinned runs only, without asking, when the full text is over
the limit. A run without fields shows its modes table, but no field view, and Compare says it
cannot match its modes by overlap.

### Matching modes in Compare

Compare matches the modes of runs A and B by their fields, so a row pairs the same mode even
when the ranks change between designs (for example a wider core whose second TE-like mode
overtakes the TM-like one). Matching is always on, and the ranks stay in every row.

- **Common grid.** The runs can have different meshes, and each keeps only its own centroid
  samples, so Studio samples both on one grid: uniform cell centres over the intersection of the
  two windows, spacing ½ · min(core mesh of A, of B), at most 400 × 400 points. A point takes the
  centroid E_t = (E_x, E_y) of the triangle that contains it; a point in no triangle of a run is
  left out of every sum.
- **Overlap.** η(a, b) = |Σ_g conj(E_A,a)·E_B,b|² / (Σ_g |E_A,a|² · Σ_g |E_B,b|²), with the
  transverse field only, like the engine's sweep tracker; η does not depend on a mode's arbitrary
  phase or scale. A degenerate pair (n_eff within 1e-3, as in the [modes table](#modes-table)) is
  matched as one unit by the mean squared cosine of the principal angles between the two 2-mode
  spans, and its Δn_eff is the difference of the pair means. A pair against a single mode scores
  at most 0.5 and is never matched.
- **Assignment.** Studio computes η for every pair of modes and keeps the one-to-one assignment
  with the largest total η (every assignment is tried; at most 8 modes per run). A match is
  accepted when η ≥ 0.8 and η exceeds the next-best value in its row and in its column by at
  least 0.1: the tracker's defaults `mode_tracking_threshold` and
  `mode_tracking_margin_threshold`.
- **Table.** One row per matched mode, headed *1 ↔ 1* (*1–2 ↔ 1–2* for a pair; its accessible
  name is the full *A mode 1 ↔ B mode 1*, its title adds the overlap and Δn_eff), with the polarization of both sides
  (word and TE percentage), the overlap to 2 decimals, n_eff of A and B, Δn_eff (B − A) and Δ % of
  A, then A_eff of A and of B in µm² (a matched degenerate pair shows *mean* of its members' values,
  with a tooltip that each member's value is defined only up to a rotation within the pair), then
  the absorption loss of A and of B (*Absorption loss A (dB/cm)*, *Absorption loss B (dB/cm)*,
  on matched and unmatched rows: the modes table's value from the saved indices, *mean* of the
  members' dB/cm for a matched pair; optical runs read *0 dB/cm*, as the optical adapter's
  materials are lossless), then *n_g A* and *n_g B* (the modes table's value, *mean* of the
  members' values for a matched pair, **—** with the modes table's help when a run has none). The
  headers are short and grouped: *Polarization*, *n_eff*, *A_eff (µm²)*, *Absorption loss (dB/cm)*
  and *n_g* each over an **A** and a **B** column, *Modes*, *Overlap*, *Δn_eff (B − A)* and *Δ % (of
  A)* over one; a line above the table names run A and run B. Each Polarization cell has two lines,
  the class and then the share (*TE-like* / *98.2 % TE*). At 1440 × 900 every column fits the table's
  box. Where the box is narrower (a phone), the first column stays in view while the others scroll
  sideways inside the box: a shadow at its right edge and the line *Scroll sideways for all 14
  columns ›* show that more columns are hidden. The page does not scroll sideways. A mode
  without a match is headed *1 ↔ —* or *— ↔ 2*, with the full *A mode 2: no match in B (best
  overlap 0.43, with B mode 2)* as its title and accessible name, and
  shows no Δn_eff; the unmatched modes of B follow. Below the table: “Matched by field overlap ≥
  0.8 on a common grid. A low overlap means the mode changed shape between designs.”
- **Field picker.** *Matched modes* lists the matched pairs (*A mode 1 ↔ B mode 1 · overlap
  0.99 · TE-like*, the polarization word once when A and B agree, else *A TE-like, B
  hybrid*; the closed picker spans the pane, so the whole pair shows; the members of a matched degenerate pair read *pair, any rotation*), and the two plots
  and the line profile show the chosen pair. With no match the picker is disabled and the plots
  show mode 1 of each run, marked *not matched*. The choice is not saved: session files are
  written exactly as before.
- **Older files.** Matching uses only the stored samples, so it works on every optical run of
  version 6 and 7 session files, and nothing is added to the files.
- **Limitations.** η is computed from piecewise-constant centroid samples, so it carries a
  discretization error of about 1.2 (h / w)² for a mode of width w on a mesh of size h (about
  1.5e-3 for a 0.4 µm wide mode on 30 and 25 nm meshes), falling as h² when the meshes are
  refined; this is far below the 0.8 and 0.1 decision gaps. A mode near cutoff can change shape
  between designs: a low overlap then says so instead of forcing a match. The multiphysics Modes
  page has no Compare and keeps ranks.

The checks are `tests/simcase/studio_mode_matching.cjs` (shifted Gaussians on two meshes against
the exact overlap, with the grid and mesh study) and `tests/simcase/test_studio_mode_matching.py`
(engine runs of silicon strips and the 400 × 400 nm square core fed into Studio's matching).

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
After reloading, **Restore recent inputs from this browser** offers a confirmed replacement; it
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

Mode/component changes update the readout with the same vector-normalized
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
Study and, once there is a run, a *Results · run N* group (N the run shown) with *Runs · N of 6*,
which opens Results, and, with two runs or more, *Compare*, which opens Compare. The 6 is the
run limit the run list's note states (*Up to six runs are kept*); both come from one constant.

The model builder of every model is an ARIA tree named *Model tree*. Its group headings
(*Component 1*, *Physics*, *Analysis*; in the multiphysics model *Couplings*, *Study* and the
results of the last run) are tree items at level 1 that open and close their group, their nodes
are tree items at level 2 (a results page included), and a node under another (a material, an
iteration step) is at level 3; no two items share a name. A node is marked selected (`aria-selected`) only
while its settings or page are shown: on Results the optical tree marks *Runs* and the
multiphysics tree marks the results page shown; on Compare the optical tree marks *Compare*
(the tree is hidden on that page) and the multiphysics tree marks none.
The tree is one tab stop, the selected node (the arrows move it while the tree has the focus). **Up** and **Down** move between the visible items,
**Home** and **End** to the first and the last, **Enter** or **Space** selects a node (the same
as a click) or opens and closes a group, **Right** opens a group or moves into it, and **Left**
closes a group or moves from a node to its parent, the item one level up. Connections explains that no coupled interfaces are present and links
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
The Results step is highlighted on Results only, not on Compare. When the viewed run has other
inputs than the current ones, the Results step says *Current inputs differ from this run* in the
plain text colour: it is information, not a problem. The Study sequence
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
same line and 0–1 relative scale; each mode retains its own max|E| denominator.
Changing mode/component updates the profile. Line choices are view state saved with the session and browser notebook recovery.

Each plotted step is the stored centroid value of the triangle intersected by
that interval. There is no field interpolation, smoothing or absolute-power estimate;
on Compare the profile shows the pair chosen in *Matched modes*. Shared/coincident edges follow the last painted triangle; mesh
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

After reload, choose the last session on its model's card (**Restore from this browser** under
Optical waveguide or Heated silicon waveguide), on the start page's **Continue where you left
off** card for the sessions no card offers, or under Workspace tools → **Restore last session
from this browser**.
The complete record is validated before the existing replacement dialog; recovered
fields are labeled `recovered`, not newly computed. Recovery starts a new input
undo history and keeps the document unsaved until you save a file/session. No
solver is started. Input-only recovery and pending-job recovery remain separate.

Starting new work without recovering does not discard the stored session. The first
automatic save after a page opens moves the stored session to the earlier sessions,
newest first, keeping at most three. That save keeps a session once, compared without its view,
its selected run, its Compare choice and its runs' origin (before this, opening a session file or
recovering re-marked every run's origin, so a new page's first save kept the stored copy of the same
runs as a second earlier session):
when the session written equals the stored one (the same file opened again) the stored record is
replaced, not moved, and an earlier copy of either (the unchanged model saved again after the tab
moved to another model and back) is dropped. The lists hide any copy left. Browser recovery also keeps the name of the session file the notebook was
opened from, for the lists; **Restore earlier session from this browser** lists each with its
model, run count, run names and time and recovers it through the same replacement dialog. Recovering
an earlier session keeps the current one as an earlier session at the next save.

The latest snapshot is a single record for the browser origin, shared across tabs.
Each write checks the previously observed revision in the same database transaction.
If another tab has saved since this tab loaded or recovered the notebook, automatic
storage stops without overwriting that record. Save session to preserve this tab,
then Restore last session from this browser to review and adopt the newer notebook. Cancelling the
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
normalization, mode, line location, job IDs, geometry, materials and origins.
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
capability contract (now `/api/workspace/capabilities/v8`, for runs of 1 to 8 modes). Installed providers are not yet offered as
workspace physics; the list only shows what is installed.

Checks: `tests/simcase/test_studio_providers.py` (the built-in provider alone, an
injected provider, unavailable providers, a failing listing, and route output with
empty, long and hostile strings read by the shipped page module) and
`tests/simcase/studio_workspace_providers.cjs` (escaping and the reply contract).
