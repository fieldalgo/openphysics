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
| **Open…** | Ctrl+O (⌘O) | Opens a project file, a session file or a model file of any model. The ribbon's **Open…** (whose accessible name is its visible *Open…* since round 17; it was *Open*) and the Library's **Open file…** are the same. |
| **Save** | Ctrl+S (⌘S) | Saves the [project file](#project-files): every model of the tab with its runs. After a Save As through the browser's save dialog it writes that file again without asking. Where Studio downloads instead, it downloads under the project file's name (the name chosen in Save As or Save, or the project file opened); a file this tab already downloaded asks first, **Download again**, **Save As…** or **Cancel** (round 25). With no project file it asks, as Save As does. The ribbon's **Save** is the same. |
| **Save As…** | Shift+Ctrl+S (⇧⌘S) | Saves the project file under a name you choose; it starts with the project file's name, else the project name's (`untitled-project.json` for an untitled project). |
| **Export › Model file…** | | Downloads the model file of the model shown (inputs only), named after the model, for example `optical-waveguide.json`. |
| **Export › Model with runs (session file)…** | | Saves the model shown with its runs to a session file, which older Studios open; it always asks for the name. |
| **Browser copy › Save browser draft**, **Restore browser draft** | | Keep or restore the optical inputs in this browser only. |
| **Edit › Reset design** | | Returns the model to its default design. |

What each kind of file holds:

| Kind | Holds | Named | Made by |
|---|---|---|---|
| Project file | Every model of the tab, each as its session file, in one file (version 1, [Project files](#project-files)). | The name chosen in Save As, `untitled-project.json` suggested for an untitled project | **File › Save**, **Save As…** |
| Session file | One model's inputs with its completed runs, their names and pins and the comparison (optical, version 9, or 10 with an [open boundary](#open-boundary-in-the-optical-workspace)); the inputs of steady heat and Joule heating; or a multiphysics model with its runs and without-heater results (version 8). | `<model>-session-YYYY-MM-DD-HHMM.json`, or the name chosen | **File › Export › Model with runs (session file)…**, **Results › Export this run** |
| Model file | The model's inputs only: no runs and no computed results (optical, steady heat and Joule heating inputs, version 7 or 8, or 9 with an open boundary; or a multiphysics document). | After the model, for example `optical-waveguide.json`, `heat-conduction.json`, `joule-heating.json`, `heated-silicon-waveguide.json` | **File › Export › Model file…** |
| Browser draft | The optical inputs, in this browser only (not a file). | — | **File › Browser copy › Save browser draft** |
| Browser recovery | The newest sessions with completed runs, in this browser only (not a file). | — | Automatic ([notebook recovery](#automatic-notebook-recovery)) |

Session files and model files are byte for byte what Studio wrote before project files for the same
model and runs. Messages calls an inputs-only file a *model file*, one model with its runs a
*session file* and the file of the whole tab a *project file*; "project" on screen means only that
file.

**Where Save As saves.** Where the browser has a save dialog for web pages
(`showSaveFilePicker`, in a secure context: `http://127.0.0.1` and `http://localhost` qualify),
Save As opens it from your click or key press with the suggested name (the current file's, if
any) and one JSON file type, and writes the chosen file. It opens in the folder the browser last
used for Studio (the picker `id` `openphysics-project`), or in the current file's folder once a
file was chosen there (`startIn` is passed only then). Studio
keeps the file it wrote, so **Save** writes it again without a dialog until a file replaces the
project. Chromium replaces a kept file only when
the write is finished, so a Save whose write fails leaves it as it was: *Project not saved: …
could not be written (…); the file is unchanged.* A file just chosen in the dialog may already
have been created or emptied by the browser, so a failed first write says *…; the browser may
have left it empty.* Closing the dialog says *Save As cancelled; nothing was written.* (*Save
cancelled; …* when Save opened it), and Messages says *Saved to <name>* after a write. Elsewhere
(Firefox, Safari, a page that is not a secure context), or when the save dialog cannot be used (for
example a managed browser that refuses it), Studio asks for the **File name** in its own dialog:
ASCII letters, digits, spaces and `.`, `_`, `-`, `(`, `)` only (other characters are removed),
with `.json` added if missing. It notes
that your browser saves to its Downloads folder, or asks where if you set it to, and (opened by
Save As) *This browser cannot write to the file, so later saves download again under this name
and may add “ (1)”.* Chrome and Edge, where their save dialog works, write to the same file
instead and never show this dialog. A browser without the save dialog cannot overwrite a file: it keeps each save as a new
download. **Download**
hands the file to the browser: Messages then says *Session file <name> sent to your browser's
Downloads*. Opened by **Save**, the dialog also says that the browser may add “ (1)” when its
Downloads folder already has a file of that name. Studio cannot know that a download was kept.
Studio remembers the name as the project's file, as it does the name of a project file opened
with **File › Open…**: **Save** (and Ctrl+S) then downloads under it, and Save As starts with it.
A file opened or restored is downloaded by its first Save without a question. Once this tab has
downloaded the file, Save asks first (round 25, A2), since a download cannot replace it: *Download
design-a-ng.json again? This browser cannot replace the earlier file and may name the new one
design-a-ng (1).json.* with **Download again** (*Downloaded <name> again: … A download cannot
replace the earlier file, so your browser may add a number such as “ (1)” to its name.*; round 18:
it named *<name> (1).json* even when a (1) copy already existed), **Save As…** (the name dialog,
prefilled with the name) and **Cancel** (*Save cancelled; nothing was written.*). After **Download
again** the header says when, and under which name the browser may have kept it, until the next Save
As or Open (round 26, C3): *design-a-ng · design-a-ng.json · downloaded again 11:45 AM (your browser
may have named it design-a-ng (1).json)*, or *… · changed since downloaded again 11:45 AM (…) · …*
after a change. Since round 29 (L3) the number counts the Download again of that name in this tab:
the second says *(your browser may have named it design-a-ng (2).json)*, and so on; Save As or Open
starts the count again. The question before each Download again names the same number (*… may
name the new one design-a-ng (2).json.*). The first Save of a
project with no file keeps the name dialog, and the browser's save dialog (Chrome, Edge) is
unchanged. On every project save the name dialog also says what the file
will hold, each model with its runs: *The file will hold Optical waveguide (2 runs) and Heated
silicon waveguide (1 run).* (round 18; a heat or Joule heating model reads *(no runs)*). When the project's models changed since that file
was written or opened (a model added, such as the heated model after the optical one was saved),
**Save** opens the Save As name dialog instead, prefilled with that name and saying why: *This
project now holds Optical waveguide and Heated silicon waveguide; study.json holds Optical
waveguide. Save under this name or another.* (round 17). A file kept from the save picker is
written as before. A file that replaces the project drops it, as it
drops a file kept from the save dialog; switching models and **Reset design** keep it, since the
project is the same. **Export › Model with runs (session file)…** keeps the same rules for each
model's own session file name (the session file opened, or the name chosen there), and always asks.
**Export › Model file…** always downloads.

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

## Project files

A **project file** holds every model of a Studio tab, so one file brings back the optical waveguide
and the heated silicon waveguide with their runs. **File › Save** and **Save As…** write it, and
**File › Open…** reads it. A project holds the workspace model (the optical, steady heat or Joule
heating inputs, with the optical runs) once one of its cards was chosen or a workspace file opened,
and the multiphysics model once one was opened.

**The project in the tab.** The title bar names the project and its file in the words of the
indicator:

- *Heater study · heater-study.json · saved 13:15* after the browser's save dialog wrote it;
- *Heater study · heater-study.json · downloaded 13:15* after a download, with *Your browser may
  have added “ (1)” to the file name.* as its title text;
- *Heater study · heater-study.json · opened* after File › Open;
- *Heater study · heater-study.json · changed since saved 13:15 · kept for recovery in this browser*
  once a model changed;
- *Untitled project · not saved to a file · kept for recovery in this browser* before the first save.
- *Untitled project · changed since run-a.json, not saved · kept for recovery in this browser* once a
  project made by File › Open of a session or model file (`run-a.json`) has changed (round 24, B2, the
  coordinator's follow-up: it read *not saved to a file* beside the status bar's *Changed since session
  file run-a.json*). Just opened, it still reads *not saved to a file*; a nameless recovered record of a
  copy reads the same once changed. Only a project that never had any file keeps *not saved to a file*
  after a change.

"Changed" counts the inputs, study settings, runs, names, pins and comparisons of every model and
the project name; a page, the view or the selected run is not a change. The footer keeps the
indicator of the model shown, as before. The Library is headed by the same line, in its title row, and
the **Project name** field with **Rename** sits at the right of its **Open file…** row (one row, so
the cards and their restore offers stay in the first screen): 1 to 80 characters, no control characters, trimmed; an empty name is
refused by name and the field shows the name kept. A rename is written on the next File › Save. An
untitled project takes the chosen file's name without `.json` when it is first saved (`design-a-ng.json`
names it *design-a-ng*). A name that came from a file name follows the file: Save As to
`design-b.json` names the project *design-b*, and the header and the Open notice use that name. A
name set with **Rename** stays when Save As uses another file name. Opening a project file whose
name is its file name without `.json` counts as a name from a file; any other name as a name set
with Rename. The file format (`name`) is unchanged.

**Switching models.** Choosing another card keeps every model in the tab: the card of a model in the
project but not shown reads *In this project · N runs*, and choosing it shows that model as it was
left, with its runs and its own Undo. Nothing is asked. The leave question guards only a file that
replaces the project: *Replace Heater study? Optical waveguide (2 runs) and Heated silicon waveguide
(1 run) have runs in no file. Save project first to keep them.*, with **Cancel**, **Save project,
then open** and **Open without saving**.

**Save.** Each model's session is written by its own writer, so it is the session file Studio writes
for that model. The 16 MiB question of a session file is asked for each model and names it (for
example *Heated silicon waveguide: Session is 22 MB; the limit is 16 MiB. Keep the maps…*). The whole
file is at most 64 MiB; a save over it is refused and names the models to export, for example *The
project is 71 MB, over the 64 MiB limit. Export Heated silicon waveguide (22 MB) to its own file, or
remove runs.* (Two models of at most 16 MiB each cannot reach it today.) One notice names every model:
*Saved Heater study to heater-study.json: Optical waveguide (2 runs, the comparison) and Heated
silicon waveguide (1 run, the without-heater result).*, or *Project file heater-study.json sent to
your browser's Downloads: …*, then any runs left without fields or maps. Only **Export › Model with
runs (session file)…** says that the other model's runs are not in its file.

**Open.** File › Open reads a project file only after every check has passed, before anything in the
tab changes; one failure refuses the whole file with *Project not opened: <reason> The current project
is unchanged.*, and the workspace, its runs and Undo stay as they were. The checks, in order:

1. the size, at most 64 MiB, before the text is parsed; valid JSON, a leading byte order mark removed;
2. the envelope: `format`, `version` (a newer one is refused by name: *This project file is version 2,
   newer than this Studio reads (version 1). Open it in a newer Studio.*), no unknown key, the types,
   1 to 8 models with unique ids, at most one workspace model, and `active` naming one of them;
3. for each model, its kind against its session's version, then the session's text rebuilt from the
   file and its size and SHA-256 compared with the entry's (*Heated silicon waveguide changed after it
   was saved (its check value does not match).*), then the session read as a session file is, every
   message after the model's title;
4. the server's check of each multiphysics model, as Open session does; without the server nothing opens.

Results read from a project are marked as from a file (*Loaded from file, not recomputed. Results match
the file's checksum.*), and opening never starts a run. A session file or a model file opened with File ›
Open opens as before and becomes an untitled project holding that one model; Save then asks for a name
and never writes a project file over the session file's name. A restore from this browser of one
model's record (a button of the Library's **Continue where you left off**, or Workspace tools)
replaces that one model inside the project. When
the restored record was the same as the project file it was saved to (its line reads *same as
…json, saved …*), the project names that file and its name again: the header reads *untitled-project ·
untitled-project.json · saved 2:24 PM* and File › Save writes or suggests that file. With another
model of the tab beside it, the header reads *changed since*. Since round 19 a record changed since
the project file it was saved to brings back the name and file too: *y3-saved · y3-saved.json ·
changed since saved 06:15 AM · kept for recovery in this browser*. Since [session version 12](#optical-session-files-version-12) a record also keeps the
project's name (`project`), so a record of a file that was opened, not saved, brings the name back
with no project file: *both-models · recovered from this browser · changed since both-models.json,
not saved · kept for recovery in this browser* (round 23, E5; *· as opened from both-models.json ·*
while the record still matched it, *· not saved to a file ·* for a record of no file), and File › Save suggests `both-models.json` and asks. An older record holds the file's name
but not the project's, so no name is guessed: the header names the source, *Untitled project ·
recovered from a copy of both-models.json · not saved to a file · kept for recovery in this
browser*, as the status bar does (*Recovered from this browser (opened from both-models.json;
changed since)*). A File › Save of the project relinks
the browser recovery record of every model it wrote, shown or not, so each card names the newest
project file.

**The file.** One compact JSON object, its keys in this order:

```json
{"format":"openphysics-studio-project","version":1,"name":"Heater study","savedAt":"2026-11-23T13:15:00.000Z","studio":"0.0.2","active":"m2","models":[
 {"id":"m1","kind":"workspace","title":"Optical waveguide","card":"optical","bytes":7422,"digest":"sha256:…","session":{…}},
 {"id":"m2","kind":"multiphysics","title":"Heated silicon waveguide","card":"heated-waveguide","bytes":396949,"digest":"sha256:…","session":{…}}]}
```

(shown on several lines here; the file has none). `name` is the project's name (1 to 80 characters,
not the file name). `savedAt` and `studio` are for display only. `active` is the id of the model shown
on open. Each model has an `id` (`m` and 1 to 3 digits, kept across saves), a `kind` (`workspace`:
an optical session of version 6, 7, 9 or 10 (an open boundary), the versions the session reader reads; `multiphysics`: a
session of version 8, one per tab in this Studio, up to 7 in a version 1 file), a `title` and a
`card` (`optical`, `heat`, `joule`, `heated-waveguide` or `null`) for display, and its `session`,
unchanged: written alone by its writer it is byte for byte the session file Studio writes (version 7
through `JSON.stringify`, versions 8 and 9 with negative zero kept as `-0.0`). `bytes` and `digest`
are the UTF-8 length and `sha256:` of that text. They detect a damaged or edited file; they do not
authenticate it, as the per-run digests inside versions 8 and 9 do not. Each model is at most 16 MiB,
so every model still exports as a session file older Studios open. Not in version 1: comparisons
across models, heat and Joule heating results (their inputs are in the workspace model), undo
history, the provider list, failed or stopped runs. Browser recovery keeps its records per model, as
before; it does not restore a whole project.

**Older Studios.** A project file needs this Studio or a newer one. An older Studio refuses it with its
own message (*Session open failed: Unsupported session format or run count. …*) and keeps its
workspace. **File › Export › Model with runs (session file)…** writes a file older Studios open.

**Checks.** `tests/simcase/studio_project_file.cjs` checks the format: a save, open and save again
byte-identical with −0.0, a subnormal, 1e308 and integers above 2^31 (V-P1); each entry's size and
SHA-256 equal to node:crypto's, and to Python's hashlib in `tests/simcase/test_studio_project_file.py`
(V-P2); each reading check refused by its message (V-P3); and the 16 and 64 MiB limits at ±1 byte,
the 64 MiB one before parsing (V-P6). `tools/studio_browser/studio_project_browser.mjs` runs the
browser steps at 1440 × 900 and 390 × 844 by role and accessible name: the two models run, the project
named *Heater study* and saved under its suggested name `heater-study.json`, the server restarted and a new browser profile, File › Open, and both models read
back the same values with no run started (V-P7, V-P13); Save again under the remembered name (V-P11);
the save dialog stubbed at `window.showSaveFilePicker` (V-P10); three damaged files refused with the
tab unchanged (V-P3). With `--old-python`, it also opens the file in an older Studio (V-P9).

## First optical study

1. Choose **Library → Optical waveguide** (the start page; its tab is **Library**). (The Heated
   silicon waveguide card opens a coupled heat and optical model instead; see [Multiphysics models](#multiphysics-models-heat--optical-modes).)
2. In **Geometry**, edit the core numerically or drag it and its edges. Add
   rectangles, circles or polygons for slabs, slots, claddings or holes, and choose
   each shape's material; the silica background stays. A rectangle's **Width** edit
   keeps its horizontal centre (Left x moves by half the change) and a **Height** edit
   keeps its bottom edge, so a core resting on y = 0 stays centred there. Where the centred
   shape would leave the window but the shape with its left edge kept fits, the Width keeps
   the left edge and Messages says so: *Width set to 3000 nm. Left x kept at −1500 nm:
   centred, the shape would leave the window.* (a 3000 nm substrate typed as Left x −1500,
   Bottom y −1200, Width 3000, Height 700 is a 3000 × 700 nm rectangle at (−1500, −1200)). A
   Width is computed from the shape as it was when the field took focus, so the digits typed on
   the way do not move it. The window rule still refuses a size that fits neither way; a
   refused value stays in its field and is tried again when another value of the same shape
   changes. Projects saved earlier keep
   their stored coordinates. The step bar's **4. Study** shows *Ready to run*, and *Run
   complete* once these inputs have a result; next to it the wavelength (for example
   **λ 1550 nm**) is a button, named *Wavelength 1550 nm, edit*, that opens the wavelength field. Optionally set the
   wavelength in **Physics › Optical modes** (its settings are headed *Optical modes*) or in
   the Study's execution settings: both hold the same field, as both hold **Modes to find**
   (**Study → Edit wavelength** and the step bar's wavelength open it under Optical modes,
   focused). The Study settings also say which inputs the next run uses, *Next run uses 700 ×
   300 nm · Silicon · λ 1550 nm · core mesh 30 nm · Modes to find 2*, with *· group index on* when
   **Also compute group index** is ticked, whatever run Results shows. Beside **Run study** the
   ribbon says what the next run does and, when this tab has one, how long the last comparable run
   took (round 18; round 17 named the slow options only): *Open boundary · 2 modes · 2 searches ·
   group index on (3 solves) · last such run 3:40*. It names the boundary (*Closed window* or *Open
   boundary*), **Modes to find** (*4 modes*, *1 mode*; since round 28, G2, as the job line names it,
   so a count the slab shortcut set to 4 is seen before the next run), an open boundary's searches (*1 search* or *2 searches*), the options that add solves with the
   solve count after the last of them (*group index on*, an open boundary's *PML check on*: one more
   solve per mode at most; both *group index on · PML check on (5 solves)*), then *last such run
   m:ss* when the tab has a comparable run with a time. Since round 20 the line has no timing part
   without one (*Closed window · 2 modes*): round 19's *no timed run in this tab yet* (before it, *no earlier
   run*) raised the question what a timed run is and read wrong beside runs computed in the tab with
   another boundary or group-index state. A comparable run has the same boundary kind and group-index state; its
   time is the wall time from the job's start to its result in this tab, kept with the run in this
   tab only: opened and recovered runs have none, and no file holds it. Since round 23 (E3), with
   the group index on, the time part is an estimate from the newest run of this tab with the same
   boundary kind, whatever its group-index state: its time when it computed the group index too,
   three times its time when it did not (the group index adds two solves), *Open boundary · 2 modes ·
   2 searches · group index on (3 solves) · about 3 min* (*about 20 s* under a minute and a half). With
   no such run there is no estimate (the round-20 rule). Round 24 (B5) checked the case of P04, whose
   only comparable open run had been opened from a file: a session file of version 15 or earlier and a
   browser-recovery record of one store each run's completion time but not its wall time, so such a
   run has none; the estimate skips it and uses an older run of this tab with a wall time, and with
   none shows no estimate. Since [session version 16](#optical-session-files-version-16) an
   open-boundary run keeps its time in files, project files and browser recovery: a run opened,
   added or restored from such a file has a time and counts like a run of this tab (a run that
   was resumed keeps the server's compute time only, which the line then uses). A closed run's wall
   time is still kept in this tab only. A **Turn off group index** button sits beside
   the line while the option is on; it is the option's own edit (Undo takes it back, Messages says
   what the check box says), and the line then reads as for the option off. The group index stays an
   input: no run turns it off. Testers of round 23 kept it on from one run to the next and waited
   3:20 to 4:00 for open runs with *Computing job … 2:00* alone in view; on 2026-11-24 the T18 open
   run took 68 s without and 199 s with it. The heated model has no group index and its line is
   unchanged. The line sits in a box of
   fixed size, so the ribbon does not move when it changes (round 23: except while the slab warning
   below needs more room). Choosing **Open boundary** while the
   group index is on adds a warning to Messages: *Group index is on: open-boundary runs with it take
   about three times as long.* The options keep their state between tasks. Since round 31 (K2), when
   the group index was carried over (on before the last run completed in this tab, and not turned
   off since), **Run study** for an open boundary asks first, in a dialog *Group index is still on*:
   *This open-boundary run with group index takes about 3 min (3 solves).* (the line's estimate; *…
   about three times as long (3 solves).* without one) with **Run with group index** (the run as set),
   **Turn off group index and run** (the check box's own change, then the same run as unticking it and
   pressing Run study: the same document, values and record) and **Cancel** (Escape too; nothing is
   run or changed). Focus starts on the first button. It does not ask when the group index was turned
   on after the last completed run, for a closed window (where only the slab question below can ask),
   or for the multiphysics model; both questions never apply to one run. Round 31's testers ticked
   the group index for one task and two of five then ran open-boundary runs of about 4 minutes with
   it on that the task did not ask for.
   Set the core mesh size in **Mesh**.
3. Optionally generate **Mesh** and review **Study → Check inputs**. These actions
   do not calculate optical fields. Inspect or export the solver JSON if needed.
4. Select **Run study**. Results keep the inputs used by that run,
   even if you edit the model while waiting. Stop waiting pauses observation only.
   An input edit replaces the completion message, so it never describes edited inputs. The run
   banner (*Optical run complete…*, and **Stop waiting** while a run goes) is part of the view's
   title row, after the view title (*Results*, *Comparison*): it covers no heading and no control,
   and the row keeps its height, so it never moves the panels when it appears or leaves. The
   *Optical run complete…* banner leaves 6 seconds after it is shown (the result page drawn), or at your next click, tap or key press if
   that comes first; Messages keeps the words.
   The dock heading, the status bar, the title and the step bar describe the run being viewed
   (the selected run), named by its number with its name: after a run *Run 1 · solved from
   the current inputs* (the status bar adds *press Run to solve again*); when the viewed run has
   other inputs, after an edit or with an older run selected, both geometries, *Run 1 · design A
   600 × 300 nm · current inputs 700 × 300 nm*; several shapes are named by name and size as in the run list, *Run 6 · Core 500 × 220 + Substrate 3000 × 700 nm* (round 17; it read *2 shapes*) (with the same geometry, at most two of the
   settings that differ: *· current inputs differ: Wavelength 1550 → 1310 nm*) (the status bar names the source of the current inputs when another run has them,
   *current inputs from Run 2 · Design B* (round 18; it read *Run 2 has them*), else *press Run to compute them*), and when no input was edited the title adds
   *viewing Run 1 · design A (other inputs)* on Results and Compare, so the difference does not
   read as unsaved edits (on the Model tab the title describes the current inputs only). When an
   edit, Undo or Redo leaves the current inputs and study settings equal to a run's (geometry,
   materials, wavelength, mesh, Modes to find, group index, boundary and search targets), Messages
   adds the heated model's sentence after the edit's own message, *No need to run: Run 5 already has
   these results. Run study adds a copy with the same values.*, with **Show Run 5**, which shows
   that run under Results and changes no input (round 18). Since round 20 the edit's message then
   keeps its own sentence and drops its request to run (*Modes to find set to 3. No need to run: Run
   6 already has these results. …*); an edit no run matches keeps *… Run explicitly to compute new
   results.* Run study still runs if pressed. Under
   the Inputs row of the selected run, **Use this run's inputs** loads that run's inputs (and its
   Modes to find and group index option) as the current inputs at once, without a question,
   since the runs stay as they are. Messages lists only the settings that change, from → to
   (*Current inputs set from Run 1 · design A: Width 700 → 600 nm · Modes to find 4 → 2. The next
   run uses them; Undo takes them back.*), and the same words stay in the run panel where the
   button was until the next input edit. It is one input edit, so **Undo** takes all of it back, Modes
   to find and the group index option included, and **Redo** applies it again; before any run *Nothing is computed until you press Run* and *Optical adapter
   ready · explicit Run required*. A run keeps its number while the tab is open (round 17): a new run takes the largest number used
   so far + 1, so when the 20-run limit drops the oldest unpinned run the others keep theirs, and
   Messages names the dropped run (*Run 3 (closed · 4 modes · 700 × 300 nm) was dropped: up to 20 runs are
   kept; pin a run to keep it.*; Add runs from file names its dropped runs the same way). Since round 23
   (E4) every drop word names a run with the parts of its run-list label: the boundary (*closed*,
   *closed near 2.46*, *open (PML 1 µm)*), Modes to find when not 2, *n_g*, then the geometry, so
   *Run 4 (closed · n_g · 600 × 300 nm)* is the run listed as *Run 4 · closed · n_g · 600 × 300 nm ·
   Silicon*; until then it read *Run 4 (600 × 300 nm · 2 modes)*. This holds for the line beside Run
   study, the dropped words, the swap button and the Pin notice; the heated model keeps its own names. Since round
   18 the box beside **Run study** says it before the run, while 20 runs are kept and one is not
   pinned: *If you run: drops Run 3 (closed · 4 modes · 700 × 300 nm) · pin it to keep it* (round 20; it read
   *Running drops …* before, as if a run were under way), with **Pin Run 3**,
   which pins that run and moves the line to the next unpinned run, or removes it. Since round 22
   (V4) Messages then names the run the next result drops instead: *Run 3 pinned. If you run: drops
   Run 4 (closed · 4 modes · 700 × 300 nm) · pin it to keep it* (while a run computes, *Run 3 pinned. When
   this run finishes, Run 4 (…) is dropped*); the usual pin message only when nothing would be
   dropped. Since round 21 the line is hidden while the current inputs equal a run's, when
   Messages says *No need to run: Run 6 already has these results*, and returns once they differ
   from every run (the heated model's line, below, follows the same rule for its model). Since round 21 **Run study** starts at once: the dialog that rounds 19 and 20 showed
   before such a run (*Running drops Run 3 …* with Pin Run 3 and run, Run and Cancel, and its
   *Waiting for your answer* words) is gone, because a run left waiting for an answer computed nothing
   while its user looked away. While the run computes the line reads *When this run finishes, Run 3
   (closed · 4 modes · 700 × 300 nm) is dropped*, and **Pin Run 3** works then too: it keeps Run 3, and the
   line names the next unpinned run, if any. Pin is not offered when pinning would leave fewer
   unpinned runs than the result must drop (the last unpinned run: the result needs its slot). The
   drop happens only when the result arrives, the oldest unpinned run then; Messages adds *Run 3
   (closed · 4 modes · 700 × 300 nm) was dropped* after the run's own message and, when another unpinned run
   exists besides the new result, a button **Keep Run 3, drop Run 4 (closed · 4 modes · 700 × 300 nm)
   instead**, Run 4 being the oldest such run. It brings Run 3 back at its place and drops Run 4:
   *Run 3 (…) is back; Run 4 (…) was dropped instead.*, with no further button. When every other
   earlier run is pinned no swap can be offered, and since round 22 (V4) the words say why: *Run 3
   (…) was dropped; every other earlier run is pinned, so no other run can be dropped instead*. The tab never holds
   more than 20 runs (six before [run retention](#keeping-runs-values-and-fields)). The button works until the next Run study starts or the run list is replaced
   (a file opened, a session restored, runs added from a file, Start new); a stale one does nothing
   and is removed. It is kept in memory only. Add runs from file still names its dropped runs with
   the sentence above. Since run retention the limit is 20
   runs, and their fields are kept within one budget ([Keeping runs](#keeping-runs-values-and-fields)). Since [session version 12](#optical-session-files-version-12) files and browser
   recovery keep the number whenever it is not the run's place in the list, and File › Open, Open
   project and Restore keep it: after a file whose largest number is 8, the next run is Run 9. A
   file of an earlier version numbers its runs from 1 in file order, and runs added from a file
   continue after the largest number (*Added Run 2 and Run 4 of design-b.json as Run 9 and Run
   10.*). No message of an open or a restore speaks about numbering (round 19 said *Runs are
   numbered from 1 in this tab; …* after every open): a session written before version 12 holds no
   run numbers; its runs are numbered by their place in the file. Studio writes an older version
   only when that numbering is exact. A current run that this tab did not
   compute says where it came from instead: *Run 2 · read from file, not recomputed* after Open
   session, *Run 2 · recovered from this browser, not recomputed* after a recovery; the status
   bar adds *has the results of the current inputs* (round 20; it asked *press Run to compute it
   here* before, beside a run that already has them). Run list entries name a run by its number with its
   name, then its boundary, *Pinned · Run 1 · design A · closed · 600 × 300 nm · λ 1550 nm ·
   3:50:12 PM*, and give the time with seconds; the Compare pickers, the Compare headings and the
   n_eff table's run lines name runs the same way. The boundary tag, *closed* or *open (PML 1 µm)*,
   comes right after the run number and name, so a label cut short in a picker still shows it. A
   run of several shapes names each shape and its size, the first three, then *+N more*: *Run 7 ·
   open (PML 1 µm) · Core 500 × 220 + Substrate 3000 × 700 nm · Silicon · λ 1550 nm*. Since round 21
   the tag is followed by what the study computed when it is not the default, so two runs of one
   design read apart: *· 4 modes* (*· 1 mode*) when Modes to find was not 2, and *· n_g* when the
   group index was computed: *Run 7 · open (PML 1 µm) · 4 modes · n_g · Core 500 × 220 + …*. Both come
   before the geometry; a picker too narrow for the label cuts it at its end (the full label is its
   title text), so they stay in view. Compare opens with
   the two newest runs, the older as A and the newer as B (a run just computed is B). A pair
   picked on Compare, or a pair of two named runs, stays when new runs come. For a pair picked by
   hand Compare then reads *Run 5 is newer than this pair · Compare Run 5 with B*, and the button
   compares the newest run (as B) with the pair's B (as A); the pair is never replaced by itself.
   For a pair kept only because both runs are named it offers one action instead (round 24, B4):
   *Run 7 is newer than this pair · Compare the two newest: Run 6 and Run 7*, which shows the two
   newest runs as a new run would (*Compare Run 7 with B* is not offered beside it: one action
   reaches the newest pair). The project file stores that pair, and opening
   it shows it again; a pair read from a file that is not the two newest runs is kept as
   picked, unless both its runs are named: such a pair is kept because they are named (round 25,
   A3), so after a new run Compare offers *Compare the two newest: …* as above. The run
   list shows the newest first, so on Compare the two cards end with a *Compare A* and a *Compare
   B* badge (read out as *· Compare A* and *· Compare B*). A pick whose run is gone sets both back to that pair. Exactly one run card
   reads as selected (the pointer over another card changes only its border). On Compare a click on
   a run in the run list selects it (Run name and the run commands act on it) and Compare stays
   as it is: A and B are chosen with the pickers above the plots (named *Run A* and *Run B* for assistive
   technology, with the full run label as their title, round 17; since round 31, K3, their visible
   labels read *Run A* and *Run B* too, where they read *A* and *B* and three of five testers did not
   find how to choose runs; no horizontal scroll at 1440 × 900 or 390 × 844), and **Open Run 1 · design A in
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
6. **Save** (**File › Save**, Ctrl+S), the first save button, creates a portable [project file](#project-files)
   with every model of the tab, its retained results and view settings; **File › Export › Model with runs
   (session file)…** writes this model alone, named from the application and the local
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
   Studio restart, the start page shows **Continue where you left off**: one way back for each
   piece of work (a project file, or a model's records without one). Its note reads *Restore brings
   back completed runs kept in this browser, without recomputing.* (until round 30 it went on
   to name Open file… as a second way back). The first and most prominent button (filled) is the newest stored session
   with runs, whatever its model (round 19), *Restore newest from this browser: Optical waveguide ·
   6 runs · Run 1, …*, or both models of a project (below). The line under it says how this browser
   copy compares with the file its record names: *Kept in this browser 11:40 AM · not saved to a
   file*; *… · same as heater-study.json, saved 11:12 AM* (or
   *same as heater-study.json as opened* for a file opened here, which has no save time); *… · newer
   than heater-study.json, saved here 11:12 AM* (or *as opened*); *… · last linked to
   heater-study.json* when the record does not say. *Kept in this browser* is the browser copy's
   time; *saved* is only ever a file's save time. *Newer than* compares with the file as this
   browser last saved or opened it: a later save of that file on another computer or in another
   browser profile is not known here (the record stores no file hash or time of its own). When the
   other model of the project has its newest record apart (not the pair) and its runs are not in
   the tab, a second button offers it, *Restore from this browser: Heated silicon waveguide · 1 run ·
   Run 1*, with *Older · kept in this browser …* under it. Every other stored session is folded
   under the closed **Earlier copies in this browser (N)**: *Restore Optical waveguide · 2 runs ·
   Run 1, Run 2*, with *Older copy · kept in this browser 11:12 AM · matched heater-study.json as
   saved 11:12 AM* (or *matched … as opened*, *not saved to a file*, or *last linked to …* when the
   record had changed since that file or does not say: an older copy never says *same as* or
   *newer than*, which a later save may have made stale). **Not now (choose a model below)** closes
   the box to its heading; opening the heading shows the same buttons again. The box stays hidden
   while the tab holds optical runs. (Until round 30 every session was a button of its own, each
   with *· saved …* (*· kept …* since round 29, L2) and *· older*, and each model card repeated its model's newest record.) After a restore, the record
   restored is left out of the lists and the remaining ones stay listed under Workspace tools
   (*Restore earlier session from this browser · …*) without a reload. **Open file…** has one
   fixed place, at the top of the Library (the project name at the right of its row) and above the box and the cards,
   whatever they offer, with no note beside it (until round 32 a line there read *A project file is the copy
   that moves between computers; browser recovery stays in this browser.*). It does what **File › Open…** does. The Library page has one phrase for browser recovery,
   *Restore from this browser*; **Open file…** is for files. A restore opens the page
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
   Continue where you left off › Restore** (browser recovery, which keeps the four newest sessions) or **Open
   session** with the session file that holds them, or that nothing does. While the tab holds none
   of a model's runs and browser recovery holds a session of it, for example after a restart, that
   model's card says so in a line that is not a control, *Kept in this browser · 2 runs · Restore at
   the top of the page*; the restore itself is in the box above. Choosing the card opens the model
   without those runs, and the records stay listed. (Until round 30 the card had its own *Restore
   from this browser · …* button and **Start new (no runs)**, which repeated the box.) Each card ends in **Open model**; the card of a model already in the project, shown or not, ends
   in **Return to Optical waveguide (2 runs)** instead (round 18; *Open model* read as if it might reset
   the model), or **Return to Optical waveguide** for a model without runs; since round 20 the words
   name the model (*Return to Heated silicon waveguide (1 run)*), so two such cards never read alike. Its description ends in
   *Runs stay in this tab when you switch models; this browser can bring completed runs back after you
   close it.* (round 28, G4; *Runs stay in this tab until you close it.* before, which browser recovery
   contradicted): choosing a model keeps the runs this tab holds, and the restore offer brings back the
   browser's runs. Opening a model of the tab that has
   runs lands on its Results, whatever page it was left on (round 17; round 16 returned to Compare
   too): the optical model with the run last viewed, the heated model with its last result page; a
   model without runs opens on Model. The page starts at its top. When the other model of the project is
   in this tab, the line under the newest button ends in *· Heated silicon waveguide · Run 1, Run 2
   already in this tab*, naming the runs the tab holds. Every recovery entry names its
   model, its run count and its runs (*Run N*, with the run's name if it has one), for example
   *Optical waveguide · 2 runs · Run 1 · design A, Run 2*. The Workspace tools list (*Restore earlier
   session from this browser · …*) also names the session file its record was opened from or last
   sent to: *· same as file …json* when the record still matched it, *· file …json, changed since*
   when it did not, *· file …json* for a record written before Studio kept that, and, since round 18,
   the other model of the same project file when browser recovery holds a record of it, *· also in
   this project: Heated silicon waveguide · Run 1*, or *· … (already in this tab)* when the tab holds
   that model's runs (it said *(restored separately)* until round 30).
   Since round 20 the newest offer in the box above the cards
   restores both models of a project while the tab holds runs of neither: *Restore newest from this
   browser: Optical waveguide (6 runs) and Heated silicon waveguide (2 runs)*. Its line says *same as*
   the file only when both records are the same as it, else *newer than*, with the newer of the two
   records' times. It restores the newest record as its own button would, then, once that
   restore has completed (a load question answered with Replace; Cancel stops both), the other
   model's record, found again by its model, time and file, and shows the newest record's model on
   Results; Messages reads *Restored Optical waveguide (6 runs) and Heated silicon waveguide (2 runs)
   from this browser, not recomputed.* (round 19 to 21 added a numbering sentence, gone since
   [version 12](#optical-session-files-version-12)). The project name and file come back as each record holds them (when the records
   name different projects, the newer record's name); when both
   records still matched the same project file the header reads *… · saved …*. If the second restore
   fails, the first stays, Messages names the model not restored (*Heated silicon waveguide was not
   restored: …*) and that model's record stays offered. While the tab holds runs of one of the models the
   offer restores its own model only, as before, and its line names the other *already in this tab*.
   Since round 21 the box does not list the other model's own record again while the newest offer
   restores the pair (now neither as a second button nor as an earlier copy), and an older entry
   leaves the other model out: it named the other model's newest record, whose runs may have been
   made after the older entry was saved. Every restore from this browser
   first writes this tab's pending recovery save (at once, not after its 0.7 s timer), so the record
   it continues is the one stored: before, the second restore of a pair could continue a record
   this tab replaced while the server checked the model, and every later save then read as another
   tab's change (*browser recovery changed in another tab*) and automatic recovery stopped. A
   change another tab made is still detected as before.
   Each stored session is listed once, newest first:
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
*…, current 700 × 300 nm · Silicon; unchanged: λ 1550 nm · core mesh 30 nm*. Since round 23 (E6) the
optical line names every input a run is compared by (its study signature) when either side is not
the default: the shape positions when only they differ (*at Core (-300, 0) nm*), the boundary with
its PML thickness and open edges (*closed window*, *open boundary (PML 1 µm) on left, right and
bottom*), the search (*highest n_eff*, *nearest to n_eff 2.46*, an open boundary's *search near
2.46*), *Modes to find 4* and *group index on* or *off*: *this run 600 × 300 nm · Silicon · closed
window · highest n_eff · Modes to find 2 · group index on, current Core 500 × 220 + Substrate 3000 ×
700 nm · Silicon · open boundary (PML 1 µm) on left, right and bottom · search near 2.46 · Modes to
find 4 · group index off; unchanged: λ 1550 nm · core mesh 30 nm* (until then the boundary, the search
and an unchanged n_g were left out). Runs and inputs of the default study read as before; the step bar's Results step
describes the run shown (*Result for these inputs* or *Current inputs differ from this run*), and
clicking it shows that run. Steady heat and Joule heating results use the same words. In optical
Results the modes table comes first, then the field plot with its sample and line profile. Between
designs, Compare pairs modes by field overlap, not by rank; the dock note on Results and Compare
reads *Each result keeps the inputs it was run with · Compare matches modes by field overlap ·
convergence not certified*.

## Working with a model

Choose a model, select a body or boundary in the model tree or drawing,
and edit its properties in the inspector. A selected shape's **Name** and **Material** fields each
have their own label (`for`), so a screen reader and a test name them by that word alone (round 19;
the Material label used to wrap the list and read its choice too). The optical application runs a real
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
  source: uses n₀ at T_ref (300 K)”. The tree's **!** badge is named with the physics and the
  problem, as its tooltip and its accessible name: *Modes 1: Temperature input has no source: uses
  n₀ at T_ref (300 K)*. Without a coupled temperature the optical solve applies no
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
  “recovered from this browser, not recomputed”) and the footer adds “has the results of
  the current model” (round 20; before, “press Run to compute it here”); a run made in the tab keeps the words above. A named run is “Run N · name” in the dock
  heading and the footer, as in the optical application: “Run 1 · Heater 2e14 · solved from the
  current model”, “Run 1 · Heater 2e14 matches the model · press Run to solve again”, “Model
  edited since Run 1 · Heater 2e14 · press Run to update”.
- **Also solve without heater** (beside Run, *(about 1 s more)*) is on when a model whose optical modes
  take a coupled temperature opens. After the coupled run, Studio solves the optical model alone
  with no temperature input, through the same run route, and fills the heater-off column. It is
  skipped when the kept column has the same content. While no coupling sets an optical
  temperature the option stays in place, disabled, and says “needs a temperature coupling”.
  When a coupling comes back (added again, Undo or Redo) the option returns as it was chosen,
  and Messages adds “Also solve without heater” is ticked again. The label is associated with its
  box (`for`), so a click anywhere on it, the time note included, ticks or unticks it; the box is
  ticked when the model opens, so the first click unticks it (round 19).
- **Results** has a page per physics and a **Coupling check**: the solve order used and, per
  coupling, what was sent (“1,726 node temperatures, 300.0–319.0 K”), what was received
  (“3,334 triangle means (mean of 3 nodes)”) and the check (“Passed · max |received − sent| =
  0 K”). Heat 1 shows the temperature map. Modes 1 shows the answer first, the n_eff table, and
  below it the maps of its coupled input: the temperature and the refractive index (or its
  change n − n₀ = (dn/dT)(T − T_ref), computed by the server from the document's values) on the
  core. The modes table has the optical application's columns, | Mode | n_eff | Polarization |
  Loss (dB/cm) | A_eff (µm²) | ([Modes table](#modes-table); the loss header's second line says *absorption only (closed window)*, or *absorption + leakage into the PML* for a result with an open boundary), names its rows *Mode 1*, …, and the note under it gives the
  ranking sentence, “Modes are ranked by effective index.”, and the number of modes the model asks for, “This model asks for 2 modes: Modes 1 ›
  Modes to find” (the template asks for two, so its table shows a TE-like and a TM-like mode), a link to that setting (after an edit, “This run asked for …”). The n_eff table has “n_eff without heater” and “Δn_eff (coupled − without heater)”, signed and
  with the 8 decimals of n_eff (the template gives +0.00215086). The note under the table says
  what the baseline is: “without heater = Modes 1 alone with no temperature input: every material
  keeps n₀, its index at T_ref = 300 K”. The column is valid while the optical model solved alone
  (the run's document without couplings, loops and thermo-optic keys, compared with sorted keys)
  is the one of the shown run; otherwise it is marked “(other model)”, Δn_eff is left out, and
  **Run Modes 1 alone** refreshes it. A result names its run and does not change when the model
  is edited.
- **Runs.** Up to 20 runs are kept with their values, and their maps within the 16.8 MB budget
  ([keeping heated runs](#keeping-heated-runs-values-and-maps); six runs before H1), with the
  optical rules and words: Results › Runs lists
  “Run N · name · time”, **Run name** (Enter pins) and **Unpin this run**; pinned runs stay, and
  when a 21st run arrives the oldest unpinned run is replaced. Selecting a run shows its result
  and its freshness line; it does not change the model. With 20 pinned runs, Run says to unpin
  one first. Since round 21 Run study starts at once, as in the optical model (round 19's question
  is gone). The line beside it names the run the limit drops: before the run *If you run: drops
  Run 3 (run at 05:31 AM) · pin it to keep it*, while it computes *When this run finishes, Run 3
  (run at 05:31 AM) is dropped*, with **Pin Run 3**. Messages then adds *Run 3 (run at 05:31 AM)
  was dropped* to *Run 7 complete. …*, with **Keep Run 3, drop Run 4 (run at 05:40 AM) instead**
  under the optical rules (said again when the without-heater solves finish). Since round 22 (V4)
  Pin Run 3 says *Run 3 pinned. If you run: drops Run 4 (run at 05:40 AM) · pin it to keep it*,
  and a drop with every other earlier run pinned reads *… was dropped; every other earlier run is
  pinned, so no other run can be dropped instead*, as in the optical model. Without-heater solves
  are not runs and drop nothing.
- **Files.** **File › Save** writes the [project file](#project-files), every model of the tab.
  **File › Export › Model with runs (session file)…** writes this model with its runs, their names
  and pins and the without-heater results to one file, `<model-name>-session-YYYY-MM-DD-HHMM.json` (the model
  name lowercased, other characters as hyphens, at most 40 characters, else `multiphysics`),
  described in [Session files of multiphysics models](#session-files-of-multiphysics-models-version-8).
  When the tab also holds Optical waveguide runs, that message says they are not in this
  file: “The 2 Optical waveguide runs of this tab are not in this file; File › Save keeps them
  with this model in one project file.”
  **File › Open…** opens such a file, an optical session, or a model file alone (“Opened model
  file …: it holds the model but no runs.”). **File › Export › Model file…** writes the document
  alone, as a model file named after the model. The footer uses the optical
  words: “Not saved to a file · kept for recovery in this browser”, “heated-silicon-waveguide-session-….json · downloaded 10:15”, “Opened …”, “Recovered from this browser”;
  the title bar names the [project](#project-files). Another model card keeps this model in the
  project: its card then reads “In this project · N runs” and shows it again, runs and Undo
  included, and nothing is asked. A file that replaces the project asks first when runs are in no
  file (“Replace … ? Heated silicon waveguide (3 runs) has runs in no file. Save project first to
  keep them.”). A browser restore of this model over runs in no file asks “Leave this model? 3
  runs are only in this tab and in browser recovery. Save session first to keep them in a file.”,
  with **Cancel**, **Save session** and **Leave**. The graphics footer names the geometry's length unit
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
- `runs` holds up to six runs in completion order (up to 20 in
  [version 15](#session-files-of-multiphysics-models-version-15)). `job` is the server's job identifier
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
  template mesh are about 2.5 MB). Since run retention the tab keeps maps within the 16.8 MB
  budget ([keeping heated runs](#keeping-heated-runs-values-and-maps)), so Save writes the tab as
  it is; only a tab that holds more than a file can (the selected run alone over the budget, or
  inputs grown by more than 16 KiB since the last arrival) still reaches the question. When it
  does not fit, it writes nothing and asks, naming the
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

- the size and the JSON (a leading byte order mark is removed), at most six runs (20 in version
  15), unique job
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

A version above 17 is refused by name (“This session file is version 18, newer than this Studio
reads (versions 6–17). Open it in a newer Studio.”; versions 9 to 14 and 16 are
[optical sessions](#optical-session-files-version-9), version 15 a multiphysics session of more
than six runs, version 17 one with [compact maps](#session-files-of-multiphysics-models-version-17), and a version 8 layout under version 9 is refused by its first unknown key), as are another `application` (“This session
file holds a “…” model, which this Studio does not read.”), another result (“Run 2 was saved as
result “multiphysics-run-v2”, which this Studio does not read.”) and another document envelope
(the server reader's refusal, named in the run). Session files of versions 6 and 7 open as
before; versions 1 to 5 keep their refusal. A Studio from before version 8 refuses a version 8
file or recovery record with “Unsupported session format or run count.” and keeps its workspace,
so multiphysics sessions need this Studio or a newer one.

**Browser recovery** keeps a multiphysics model in the same store as optical sessions, with the
same limits (one latest and three earlier sessions, each at most 16 MiB, written 0.7 s after a
change, the cross-tab conflict rule). It writes once the model has a run or was edited since it
was opened, as the text Save session would write (version 8, or 15 above six runs): since run
retention it holds the tab. Over 16 MiB (a tab that holds more than a file can) it keeps maps in
the order of run retention, the selected run's, then the pinned runs' and the others' newest
first, as many as fit, without a dialog (before H1, the selected and pinned runs' only), and the
indicator says “kept for recovery in
this browser without the maps of 2 runs · File › Save keeps them”; when even that is over the
limit it writes nothing new (“browser recovery unavailable: session over 16 MiB · File › Save keeps your work”) and the earlier
record stays. **Restore last session from this browser**, **Restore earlier session from this
browser · Heated silicon waveguide · 3 runs · Run 1, Run 2, Run 3 · time** (Workspace tools) and
a restore of a heated record from the Library's **Continue where you left off** run the same
checks as Open session. A restored record that was the same as the session file it was saved to, or opened
from, reads *Recovered from this browser · same as file …json*, as an optical one does. A
template just opened reads *New model · not saved* until its first edit, run or save. When the project
has a project file and holds another model too, the heated model's status bar speaks about the
model within the project, in the header's words, so the two never contradict each other (round
18; the header said *waveguide-AB · waveguide-AB.json · changed since opened* while the status bar
said *New model · not saved*): *Heated silicon waveguide · in project waveguide-AB.json · not saved
since it joined* while the file's model list does not hold it, else *… · in project
heater-study.json · saved 13:15* or *… · changed since saved 13:15*, with the header's browser
recovery words.

The module checks are in `tests/simcase/studio_workspace_multiphysics_session.cjs` (the optical
files of versions 6 and 7 written by the Studio before version 8, in
`tests/simcase/studio_session_fixtures/`, open and are written byte for byte as before),
`tests/simcase/test_studio_multiphysics_session.py` recomputes the digests with Python's
hashlib and its own writer, and the browser check saves, opens and saves again the template, a
0.12 µm mesh and a two-run session (the second file byte-identical, every array equal to the
server's reply as Float64), six runs of a 0.08 µm mesh against the 16.8 MB budget with
Recompute Run 1's maps, 20 runs and the 21st run's drop, the refusals and browser recovery.
Not in version 8: a session mixing optical and multiphysics runs, one
mesh shared between runs, adding runs from a file, and mode fields of coupled runs.

### Keeping heated runs: values and maps

Since slice H1 of run retention (design *Keeping more runs*, section 7) the heated model keeps
the **values** of up to 20 runs and their **maps** within the same budget as the optical model's
fields ([keeping runs](#keeping-runs-values-and-fields)): the 16 MiB session less 16 KiB kept for
the inputs, 16,760,832 bytes, said as 16.8 MB. The tab, File › Save, Export › Model with runs,
the project file's entry and browser recovery hold the same maps.

- **Values.** n_eff, the coupling check, the iteration history and the node and triangle
  counts. Every run keeps them. A run without its maps is about 20 kB in a file (the template
  and its finer meshes) and 14 kB for the heated slab example; 20 such runs are about 0.4 MB.
- **Maps.** The mesh, the heat temperature per node and the coupled input per triangle (the
  temperature, n, k and n − n₀): what the maps of the heat page and the modes page draw. A run
  without maps is written as `"maps": "not kept"` with its counts, the record of
  [version 8](#session-files-of-multiphysics-models-version-8).
- **When maps go.** Only when maps arrive: a new result, a recompute, File › Open, Open project
  or Restore, and **Keep Run N, drop … instead** bringing a run back. Selecting, pinning,
  unpinning, naming a run, the without-heater solves and Show Run N never let maps go.
- **The order.** The maps kept are those of the selected run, then of the run whose maps just
  arrived (a recompute, or a run brought back, when it is not the selected one), then of the
  pinned runs, newest first, then of the other runs, newest first, each while the session stays
  within the budget; maps that do not fit are skipped and the next older run is tried. The
  selected run keeps its maps even alone over the budget; Save then refuses as before (*Run 3
  alone is 18 MB, over the 16 MiB session limit. …*).
- **The words** are the optical ones with *maps* for *fields* and the heated run names. Beside
  **Run study**, from the newest run with maps of the same geometry, mesh, materials, physics and
  couplings: *If you run: Run 3 (run at 14:02) keeps its values, not its maps* with **Pin Run
  3**; with no such run *If you run: older runs' maps may not be kept (16.8 MB limit) · pin a run
  to keep its maps first* when the room left is less than the smallest map kept. While the run
  computes: *When this run finishes, Run 3 (run at 14:02) keeps its values, not its maps*. After
  the result: *Run 3 (run at 14:02) keeps its values; its maps were not kept (16.8 MB limit).*
  with **Recompute Run 3's maps** and, when another unpinned, unselected run has maps at least as
  large, **Keep Run 3's maps, not Run 4's (run at 14:05)** (*Run 3's maps are back; Run 4 (run at
  14:05) keeps its values, not its maps.*). A pinned run's maps: *Run 2 (pinned) keeps its
  values; its maps were not kept: the selected and pinned runs' maps are 17.4 MB, over the 16.8
  MB limit. Unpin a run to keep the newer maps first.* The tree reads *Runs · 9 of 20*, the run
  list *· values only*, and the note under the run list *Up to 20 runs are kept with their
  values. Maps are kept up to 16.8 MB. When a result or a recompute arrives, Studio keeps the
  selected run's maps first, then pinned runs', then the newest. Selecting a run does not bring
  its maps back; Recompute does. Pinned runs stay; when a 21st run arrives, the oldest unpinned
  run is replaced. File › Save keeps every run in one file.*
- **A run without its maps.** Results shows its n_eff table, the coupling check with the stored
  counts and range, and in place of the maps *Run 4's maps are not kept; its n_eff, coupling check
  and iteration history are kept. Maps are kept up to 16.8 MB. …* (a run read from a file
  without maps: *Maps not kept in this file: n_eff, the coupling check and the iteration history
  are.*) with **Recompute Run 4's maps** and, for a run computed in this tab, *· about 10 s*. *No
  need to run* for such a run reads *No need to run: Run 4 already has these values; its maps are
  not kept. Run study adds a copy with the same values* with **Show Run 4** and **Recompute Run
  4's maps**.
- **Recompute Run N's maps** sends the document the run solved to the same run requests. It is
  not a new run: it takes no number, enters no list and leaves the model, Undo, the selected run
  and the without-heater results as they are; the dock and the status read *Recomputing Run 4's
  maps · about 10 s*, and **Stop run** works (*Recompute of Run 4's maps stopped; Run 4 is
  unchanged.*). The node and triangle counts must be the same, and n_eff (real and imaginary) of
  every mode, each heat physics' temperature range, each coupling's max |received − sent| and
  conservation residual, and each iteration step's residuals must match to 1e-12 relative (1e-15
  absolute below 1e-3); the mesh check and the iteration counts exactly. On a match the maps are
  attached to the same run, which keeps its job, number, name, pin, time and stored values: *Run
  4's maps recomputed from its stored model; its values match.*, and the order above applies.
  Otherwise nothing changes: *Run 4's maps were not recomputed: Modes 1 mode 1 n_eff came out
  2.44565014, stored 2.44565013. Run 4 is unchanged; Run study makes a new run from the current
  model.* (with *(stored by Studio 0.9.3; this is 0.9.4)* when the versions differ); a document the
  server now refuses says *Run 4's maps cannot be recomputed:* and the server's words. The heated
  solves are bitwise reproducible single-threaded (measured: the template, its 4-mode and 0.12 µm
  variants and the slab example, each solved twice, gave the same maps to the bit).
- **Measured** (2026-11-25, `tools/studio_heated_retention.mjs`, single-threaded): maps per run as
  text are 0.37 MB for the template (1,726 nodes, 3,334 triangles; 2 or 4 modes), 1.49 MB at a
  0.12 µm mesh, 2.79 MB at 0.08 µm and 2.53 MB for the heated slab example. Of 20 results the
  budget keeps the maps of all 20 template runs (7.7 MB), 10 at 0.12 µm, 6 of the slab and 5 at
  0.08 µm, the newest. Compact (single-precision) maps are not part of H1. Since
  [compact maps](#compact-maps-single-precision) (2026-11-26) the tab keeps 20 at 0.12 µm, 17 of the
  slab and 15 at 0.08 µm (the template's 20 never convert).

The checks are `tests/simcase/studio_heated_retention.cjs` (HK2 to HK4, HK6 to HK9 and HK12 to
HK14: the formats, a seeded sequence of 2000 steps, the order, the words, recompute refusals and
recovery), `tests/simcase/studio_heated_retention_engine.cjs` with engine results (HK1 and HK5),
and the S5 and R21 stages of `tools/studio_browser/studio_multiphysics_session_browser.mjs` (HK10).

### Session files of multiphysics models (version 15)

Version 15 is [version 8](#session-files-of-multiphysics-models-version-8) with up to 20 runs: the
same top-level keys, the same run records (maps kept, or `"maps": "not kept"` with `counts`), the
same digest, number rules and checks. Version 8 holds at most six runs.

- **When it is written.** Only when the session has more than six runs. A session of six runs or
  fewer is written as version 8, byte for byte as before, so an earlier Studio still reads it. A
  version 15 file of six runs or fewer (edited by hand) is read, and written again as version 8.
- **Reading.** File › Open, Open project and Restore read up to 20 runs; a file of 21 runs, or a
  version 8 file of seven, is refused with *Unsupported session format or run count.* A version 15
  file whose `application` is not `"multiphysics"` is refused as in version 8 (*This session file
  holds a “optical” model, which this Studio does not read.*).
- **Earlier Studios.** A Studio that reads up to version 14 (main ddb09a1) refuses a version 15
  file by name before it counts the runs: *This session file is version 15, newer than this Studio
  reads (versions 6–14). Open it in a newer Studio.*, after *Heated silicon waveguide: * for a
  project file's entry, and does not take over a browser-recovery record that holds one. To share
  runs with such a Studio, save at most six of them. The project file stays version 1 (its
  multiphysics entry reads version 8 or 15); the optical sessions, documents, server replies and
  results are unchanged.

The checks are in `tests/simcase/studio_heated_retention.cjs` (HK2: the version 8 sessions of
main ddb09a1, `multiphysics-v8-ddb09a1.json`, written again byte for byte; HK3: the fixture
`multiphysics-v15-thirteen-runs.json` of runs 2 and 4 to 15; HK4: what main ddb09a1 reads,
`refusals-v15-ddb09a1.json`).

### Session files of multiphysics models (version 17)

Version 17 is [version 15](#session-files-of-multiphysics-models-version-15) whose runs may hold
compact maps (design "Session versions 16 and 17", section 3): the same top-level keys, 0 to 20 runs,
the same run records and digest, with `"maps": "compact"` beside `"kept"` and `"not kept"`. A run
with compact maps keeps the server's reply as a kept run does, every value unchanged (n_eff, the heat
range, the coupling check, the iteration history), with these arrays replaced by strings
(encoding `f32-offset-base64-v1`):

```json
"mesh": {
  "encoding": "f32-offset-base64-v1",
  "counts": {"nodes": 12606, "triangles": 24836},
  "node_coordinates": "<base64: nodes × 2 float64, little-endian, metres>",
  "field_units": {"node_coordinates": "m"},
  "triangles": "<base64: triangles × 3 uint32, little-endian>",
  "regions": "<base64: triangles × uint8>",
  "region_names": ["background", "core", "heater"]
},
"temperature": {"unit": "K", "location": "node", "values": "<base64: nodes × float32, T − range.min>"},
"coupled": {
  "temperature": {"unit": "K", "location": "element"},
  "refractive_index": {"location": "element", "n": "<base64: triangles × float32, n − n_base[region]>", "n_base": [1.444, 3.4757, 1.444], "k": null},
  "index_change": "<base64: triangles × float32>", "index_change_base": [0, 1.7e-05, 0]
}
```

- **Values.** Coordinates, triangles and regions are exact. A node temperature reads as `range.min`
  plus its float32 offset, and a triangle map (n, k when it is not null, index_change) as its
  region's base (float64: the value at the region's first triangle, 0 for a region without
  triangles) plus its float32 offset. One rounding of the offset to float32 is at most 2⁻²⁴ of the
  heat range (about 1 µK over 19 K) or of the region's spread (about 7·10⁻¹² for the core's n). The
  coupled temperature is not stored: it reads as the mean of each triangle's 3 decoded node
  temperatures, the rule version 8 checks to 1e-12. Plain float32 values would not do for the index
  map: the core's n spans about 5·10⁻⁶ around 3.48, where the float32 step is 2.4·10⁻⁷.
- **Size.** 4⌈16N/3⌉ + 4⌈12M/3⌉ + 4⌈M/3⌉ characters for the mesh, 4⌈4N/3⌉ per heat physics and
  4⌈4M/3⌉ per triangle map, about 26.7·N + 28.0·M bytes (N nodes, M triangles), with the keys and
  bases (under 0.2 KB) extra; a version 15 run's maps as text take about 2.7 times as much. No
  compression: the size follows from the counts, and every browser writes the same bytes.
- **When it is written.** Only when a run of the session holds compact maps (any run count);
  otherwise version 15 or 8, byte for byte. A compact record is written again from the strings it was
  read from, so a version 17 file read and written again is its own bytes. Maps that cannot be kept
  compact stay text in a version 17 file: more than 256 region names, an offset beyond float32 (an
  overflow, or a nonzero offset below 2⁻¹²⁶), or a coupled map without the node temperatures of its
  coupling's source.
- **Refusals,** each after *Run 2's stored maps are not well formed: * (the existing prefix), then
  every check of version 8 on the decoded maps: *the maps are encoded as "…", which this Studio does
  not read.*; *a compact mesh holds counts, encoding, field_units, node_coordinates, region_names,
  regions, triangles and nothing else.*; *its counts must be whole numbers of nodes and triangles, at
  least 1.*; *triangles holds 123 bytes; its counts give 120.*; *regions is not canonical base64.*;
  *heat1 node temperature holds a value that is not a finite number.*; *refractive_index.n_base must
  hold 2 finite numbers, one per region.*; *a compact coupled temperature holds no values (it is the
  mean of the node temperatures).*; *regions must hold 10 integers in 0–1.*; and in a file of version
  15 or earlier *compact maps are read from a version 17 session file only.* The heat range check of
  version 8 reads, for compact maps: the decoded minimum is `range.min` and the decoded maximum
  `range.min` plus the float32 of `range.max − range.min`.
- **Earlier Studios.** A Studio that reads up to version 15 (main c0dbc09) refuses a version 17 file
  by name: *This session file is version 17, newer than this Studio reads (versions 6–15). Open it in
  a newer Studio.*, after *Heated silicon waveguide: * for a project file's entry, and does not take
  over a browser-recovery record that holds one (`refusals-v17-c0dbc09.json`). The project file stays
  version 1 (its multiphysics entry reads version 8, 15 or 17); the recovery record stays version 1.

The checks are in `tests/simcase/studio_heated_compact_format.cjs` (HQ1 the encoding, HQ7 the round
trip of the fixture `multiphysics-v17-compact.json`, HQ8 the version 8 and 15 fixtures byte for byte,
HQ9 the refusals, HQ10 what main c0dbc09 reads, HQ11 maps that stay text) and, on engine results,
`tests/simcase/studio_heated_retention_engine.cjs` (HQ1 to HQ4; `node tools/studio_heated_retention.mjs
hq <dir> <out>`). Measured on 2026-11-26 (the template, 0.12 µm, 0.08 µm and the heated slab): node
temperatures within 9.53·10⁻⁷ K (at most 0.84 of the bound 2⁻²⁴·span + 2⁻⁵²·|T|), coupled
temperatures within 9.13·10⁻⁷ K, n and index_change within 7.27·10⁻¹²; the range kept exactly.

## Results and files

The notebook retains up to six successful runs, preserving pinned references. Select a mode to inspect
its field or compare two runs. Mode numbers are ranks by effective index; Compare matches modes between
two runs by field overlap.
Field colours use the vector magnitude normalized separately per mode;
they do not represent optical power or a common physical colour scale.

### Modes table

Results show one table per run, | Mode | n_eff | Polarization | Loss (dB/cm) | A_eff (µm²) | n_g |, in the optical
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
- **Modes at the window edge (round 17).** In a closed window a shape that touches the window edge
  meets the PEC walls there, so a mode that lives mostly in it (a substrate slab mode) has an
  n_eff that depends on the window, not only on the core. Studio computes, from the run's stored samples
  and its shapes (the engine and the files are unchanged), for each shape that touches the window
  edge, the share *f* of a mode's |E|² (Σ A_T |E_T|², all three components) over the triangles
  whose centroid lies in that shape (the later shape winning where shapes overlap, as the geometry
  contract layers them) and the share *g* over the triangles whose centroid lies within 300 nm of
  the window edges that shape touches. When *f* > 0.5 and *g* ≥ 0.01 for the shape with the largest
  *f*, a note row under the mode's row reads *Mode 1 is mostly in Substrate (99 % of |E|²), which
  touches the window edge; its n_eff depends on the closed window. Use Open boundary to leave that edge
  open.*, and Compare repeats it for that run (*A · Run 3: Mode 1 is …*),
  which also says why such a run matches none of an open run's modes. Since round 22 (V3), when
  Compare matches no mode and a run's mode 1 has that note, the empty-match line (*No mode of A
  matches a mode of B; the plots show mode 1 of each run, not matched.*) adds, for that run, *A · Run
  6: its modes are mostly in Substrate, which touches the window edge; the core mode was not found.*
  and a link **Open Run 6 in Results** that shows the run under Results with the inputs unchanged.
  With matched modes there is no such line. Since round 18 a row under the
  last such note on Results has **Use Open boundary** and **Set Modes to find to 4** (the run's Modes to
  find + 2, at most 8; *Find 4 modes* before C0): each sets that input with its usual message and
  runs nothing, and is left out when the current inputs already have it. Since C0 no text says that
  more modes reach the core mode: a closed window above a substrate has many substrate modes above
  the core mode (the strip over a substrate's core TE mode is mode 32 of a default closed run). The 0.01 bound on *g* is a
  heuristic chosen after measurement (engine fields, Linux): on the strip over a substrate (Core
  500 × 220 + Substrate 3000 × 700 nm) both modes have *f* 0.994 and *g* 0.72; on a rib drawn over
  a slab that spans the window, the rib mode has *f* 0.60 to 0.71 but *g* 1.4e-4 to 2.5e-3 and is
  not named, while the slab-like modes have *g* 0.087 and more; ribs etched only 20 nm (*g* 0.024 and
  0.046, n_eff moving by about 1e-3 when the window widens) are named. The template, with no shape
  at the window edge, never shows it. Open runs and runs without fields are not checked.
- **Loss (dB/cm)** comes from Im n_eff: dB/cm = 20 · log10(e) · k0 · Im(n_eff) / 100 with k0 = 2π / λ0 in
  1/m (exp(−iωt), Im n_eff > 0 is loss), the engine's `propagation_loss = (40π / ln 10) · Im n_eff
  / λ0` in dB/m divided by 100, shown to 4 significant digits (*37.49 dB/cm*). In a closed window
  the column counts material absorption (k) only, and its header's second line (*absorption only (closed window)*),
  the help of every cell and the note below the table say so: the help reads “Absorption (material k) only; leakage and
  radiation are not computed in a closed window”, the note “Absorption loss counts material
  absorption (k) only. Leakage and radiation are not computed in a closed window.” Where every
  Im n_eff is exactly 0 each row reads *0 dB/cm*, a lossless run rather than a computed
  zero, and the note reads “Absorption loss counts material absorption (k) only: all materials
  have k = 0 at this wavelength, so it is 0 dB/cm. Leakage and radiation are not computed in a
  closed window.” The optical application adds “For leakage, choose Open boundary in Physics ›
  Optical modes.” to the note of a closed run. A run with an
  [open boundary](#open-boundary-in-the-optical-workspace) has its own cells. A multiphysics result with an open boundary (PML) has an Im n_eff that includes
  leakage into the PML, so its header's second line reads *absorption + leakage into the PML*, with the help “Material absorption
  (k) and leakage into the PML of the open boundary” and the note “Loss includes material
  absorption (k) and leakage into the PML of the open boundary. Leakage depends on what lies
  outside the window: shapes touching an open edge continue through the PML.” Since round 24 (B6, a
  coordinator decision) every table names the column **Loss (dB/cm)**, in Results, in Compare and in
  the heated model; a closed window's column read **Absorption loss (dB/cm)** before. Compare shows
  the same value as *Loss A (dB/cm)* and *Loss B (dB/cm)* under *Loss (dB/cm)* with the same second
  line; when one side is closed and the other open the group has no second line, and the note under
  the table says what each side counts. There is no threshold: a nonzero Im n_eff,
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
`open_boundary` block. The page checks version 8; since slice P2 it offers the choice
([open boundary in the optical workspace](#open-boundary-in-the-optical-workspace)). The
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
- since slice T2 a second search of 16 candidates near t_low = (t + n_SiO2) / 2 to two decimals
  is added after the fixed settings: `"pml_additional_searches": [{"target_effective_index": 1.95,
  "pml_search_mode_count": 16}]` for t = 2.46 ([further searches](pml_modes.md#further-searches)).
  t_low is computed in thousandths, halves rounded up (2.20 → 1.82, sapphire 1.60 → 1.52, silicon
  nitride 1.72 → 1.58). Below t = 1.466 there is no second search: t_low would round to the 1.45
  floor (1.465 → 1.45), so such a run searches near t only;
- the group index is not computed with an open boundary.

With every edge closed, or without `openBoundary`, the document is the `optical-shapes-v8`
document byte for byte, and its results are those of that document. A workspace request whose
`em.modes2d` physics has any other `pml` (another thickness, unequal thicknesses or another fixed
value), a target of 1.45 or below, or a domain other than the window grown by the thickness on
exactly the open edges (in nm) is refused with *The open boundary of a workspace run has a PML of 1 µm on each open edge
with strength 3, order 2, physical fraction 0.5, a search of 32 candidates near the target and one
of 16 near (target + 1.444) / 2 to two decimals; a PML check has strength 6 and one search of 16.*
A run (strength 3) must carry exactly the second search of its target, as an exact decimal with
the integer count 16, from t = 1.466; below 1.466, and in a PML check, it carries none. A run
from t = 1.466 without a second search is the document of a page loaded before Studio was updated
to slice T2: it is refused with *This page was loaded before Studio was updated; reload the page
to run again.* No path of the page sends a stored document: a run, the PML check, the preflight
check, the mesh preview and a run made again from a run's inputs all build the document from
the inputs, and session, project and pending-job files keep no document. `/api/workspace/capabilities/v9`
lists `additional_search_count` 16 and `additional_search_target` "(target + n_SiO2) / 2, two
decimals". The PML results are candidates under the [PML mode rules](pml_modes.md).

Limits of the open boundary, from its validation:

- **Two search targets.** The candidates are the eigenvalues nearest **Search near n_eff** and,
  since slice T2, those nearest t_low = (t + n_SiO2) / 2; the PML's own modes crowd the region
  around each. A search near 2.46 alone misses the third mode of a strip over a silicon substrate
  near the cladding index (n ≈ 1.486 + 0.008i, about 2800 dB/cm); the search near 1.95 finds it
  (W1). With the two searches the modes are the eligible candidates of highest Re n_eff, listed by
  descending Re as in a closed run; a candidate that both searches find is kept once. Modes far
  from both targets can still be missed: move Search near n_eff to find them. Below t = 1.466
  there is one search (see above). The ranking relies on the minimum physical fraction 0.5 to
  keep PML-dominated candidates out, and a request for fewer modes than lie above a wanted lower-Re
  mode does not return it ([further searches](pml_modes.md#further-searches)).
- The engine validations of the open boundary (P1's V1 to V8, and P3's mode identity and group
  index) solve the single-search documents of P1 (`build(..., single=True)` in
  `tests/simcase/open_boundary_fixtures.py`): they validate the PML and the post-processing, not
  the selection. The Studio defaults, with both searches, are covered by W1, W4 and W6 and the
  Studio checks.
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

### Closed-window search document (optical-shapes-v10)

`/api/workspace/capabilities/v10` is version 9 with adapter `optical-shapes-v10` and a
`closed_target` block (`default` *(n_max + n_SiO2) / 2 at 1550 nm, two decimals*, `bounds` *above
1.45 and below n_max*). The adapter's builder (`opticalDocument` with `searchTarget`) adds **Search
near n_eff** to a closed window: with every edge closed, `physics.em1` gets
`"target_effective_index": t` after its other keys, and the engine then returns the `mode_count`
eigenvalues nearest *t* (Re > 0, without the 1.45 threshold), listed by descending Re n_eff. No
engine change: `simcase.modes_document` already maps the key to the kernel's target. Without
`searchTarget` the document is the `optical-shapes-v8` (or, with an open edge, `-v9`) document byte
for byte; `tests/simcase/studio_closed_target.cjs` checks 24 closed documents (the template and the
strip over a substrate, 1, 2 and 8 modes, with and without the group index and with every edge
closed) against the ones main 13f07f4 wrote. With an open edge the open boundary keeps its own
target and `searchTarget` is not read.

A workspace request with a closed target names capabilities v10 in its query
(`workspace_capabilities=10`, beside `workspace_instance`). Each other closed target is refused
with its reason: a target that is not a number (*Search near n_eff must be a number (got "2.46").*),
one at or below 1.45 or at or above the design's largest index at 1550 nm (exact decimals; *Search
near n_eff in a closed window must lie above 1.45 and below 3.4777 (the design's largest index)
(got 1.45).*), one with `pml_additional_searches` (*A closed-window search has one target;
pml_additional_searches belongs to an open boundary.*) and one in a request without capabilities v10
(*Search near n_eff in a closed window needs workspace capabilities v10; reload the page.*). The same
documents without a target are taken as before.

Validation (`tests/simcase/test_studio_closed_target.py`, pre-registered; references measured on
main 13f07f4, Linux):

| Check | Case | Result |
|---|---|---|
| K2 | Strip over a substrate (Core 500 × 220 nm, Substrate 3000 × 700 nm), closed @2.46 | 1 mode: 2.43931663 (core confinement 0.912, TE 0.981); 2 modes: 2.48623178 (substrate) and 2.43931663. The default closed run's two modes are substrate modes (3.42534929, 3.39599656); the core TE mode is its mode 32. Re-registered after a CI result (2026-11-24, not blind): the targeted modes equal, within 1e-8, the matching modes of an untargeted closed run of 40 modes on the same mesh, and 2.43931663 and 2.48623178 are references within 2e-4, because the mesh differs between CPUs (below); as first registered (±1e-8 absolute) K2 failed with AVX2 dispatch, −1.93e-5 |
| K3 | Closed @2.46 against the open default (Compare's matching) | the core modes paired, overlap 0.988, Δn_eff −1.95e-3 |
| K4 | 220 nm Si film over the full width, @2.85, element lengths × 1, 2/3, 1/2, 1/3, against the 1D TE transfer matrix with PEC at ±1.2 µm, 2.84948947 | error −4.80e-3, −2.46e-3, −1.99e-3, −1.02e-3 (negative, shrinking; gate \|error\| ≤ 5e-3 at × 1) |
| K5 | The film over the substrate, against 2.84916936 | the film-like mode (confinement 0.94) is mode 2 of 2; its error is within 4.4e-4 of K4's at each level (gate 5e-4) |
| K6 | Template @2.46, 2 modes | the default closed run's n_eff within 5e-15 |
| K7 | Strip over a substrate @2.46, 4 modes, in a window 3, 4, 5 and 6 µm wide, a substrate 500 and 1000 nm thicker and a BOX of 800 and 300 nm | the core mode returned in 8 of 8, as mode 3, 3, 3, 4, 4, 3, 3, 4 |
| K8 | n_g, closed @2.46, 1 mode | 4.19234, against the open run's Re n_g 4.19152 (gate 2e-3) |
| K13 | Template @2.46, 4 modes | mode 4 is 1.39191472 (a reference within 2e-4; it equals the untargeted same-mesh value within 1e-8, re-registered with K2 after +3e-8 with AVX2 dispatch), below the cladding: Studio leaves it out ([search in the closed window](#search-near-n_eff-in-a-closed-window)) |

Limits of a closed search:

- **A fixed target reaches the core mode only when its n_eff lies among the substrate modes nearest
  the target.** A closed window over a silicon substrate has many substrate modes (lateral harmonics
  of the slab between the PEC walls) around the core mode. With 4 modes near 2.46 the core mode of
  the 500 × 220 nm strip is returned, but for other cores (measured after registration, not gated)
  it was returned in 3 of 8: 400, 450, 600 and 700 nm wide and 250 nm tall it was not (the 550 nm
  core mode, 2.511, is mode 31 of a closed run; the 450 nm one, 2.348, mode 34). Small changes
  (480 and 520 nm wide, 230 nm tall, 1500 and 1600 nm, core mesh 25 and 40 nm) kept it in 7 of 8; at
  210 nm tall it mixes with a substrate mode (confinement 0.37 and 0.46) and neither is the core
  mode. For other cores, set Search near n_eff to an estimate of the core's n_eff.
- **Closed and open values differ.** The closed window's PEC walls shift n_eff (−1.95e-3 for the
  strip over a substrate against the open default), and at the default mesh the discretization
  error is of the same size (K4: −4.8e-3). Refine the mesh before a close comparison.
- **The default mesh can differ slightly between computers.** meshine accepts refinement points
  largest circumradius first, and orders equal radii with NumPy's quicksort, whose order of ties
  depends on the CPU instructions NumPy uses (AVX-512 or AVX2). The same inputs can then give a
  mesh with a few nodes moved and n_eff that differs in the 1e-5 to 1e-4 place: K2's core mode is
  2.43931663 with AVX-512 and 2.43929738 with AVX2 dispatch (−1.93e-5); other tie orders moved it
  by up to 1.5e-4. Results on one computer are reproducible; compare values from different
  computers at this level only after refining the mesh.

### Search near n_eff in a closed window

Since slice C2 the page offers the [closed-window search](#closed-window-search-document-optical-shapes-v10).

- **Modes to return.** With *Closed window (PEC)* chosen, **Physics › Optical modes** has one choice,
  **Modes to return**: the radio **Highest n_eff above 1.45** (the default) and the radio **Nearest to
  n_eff** followed by the field **n_eff to search near** (3 decimals, the default (n_max + 1.444)/2
  to 0.01: 2.460 for silicon). Since round 22 (V1) the field is always enabled and typing an index in
  it selects Nearest to n_eff; until then a check box *Search near n_eff* enabled a separate field
  *Search near n_eff (closed window)*, which four of five testers tried first. The meanings are the
  box's: Highest is the box off, Nearest the box on, and the document, the capabilities and the
  session are unchanged. The help reads “Highest n_eff above 1.45: the modes of highest n_eff.
  Nearest to n_eff: the modes nearest the index in the field, listed by n_eff, highest first; modes
  at or below 1.45 are left out. Typing an index selects Nearest to n_eff. Closed and open values
  differ: refine the mesh before a close comparison.” Messages say *Modes to return: nearest to n_eff
  2.460 in the closed window. The next run returns the modes nearest it.* or *Modes to return:
  highest n_eff above 1.45. The next run returns the modes of highest n_eff.*, followed by *No need
  to run: Run N already has these results.* when a kept run has the new inputs. An index outside the
  design's range is refused with its message and the choice stays as it was. The index typed while
  Highest is chosen is kept in memory only. Highest stays the default when a shape touches the
  window edge.
- **The shortcut.** Under a closed run's edge note the round-18 row has **Use Open boundary** and,
  since C2, **Set search near 2.46 · 4 modes** (*Search near 2.46 · 4 modes* until round 22, V5) in
  place of C0's *Set Modes to find to 4*: it selects Nearest to n_eff with the design's default
  target and sets Modes to find to 4, says *… Modes to find set to 4. Press Run study to compute.*
  and runs nothing; it is left out when the inputs already have both. When a kept run has these
  inputs, *No need to run: Run N already has these results.* replaces the last sentence. Four modes reach the core
  mode of the strip over a substrate in every registered variant
  ([K7](#closed-window-search-document-optical-shapes-v10)).
- **Before the run** (round 22, V2). In a closed window with Highest n_eff above 1.45, when a shape
  that touches the window edge has an index at least the highest index of the shapes that do not
  touch it, Physics › Optical modes (above Modes to return) says *Substrate touches the window
  edge and its index is as high as Core's: in a closed window its slab modes come first.* with the
  shape names, and the plan line beside Run study a row under the plan with the short form *Substrate
  touches the window edge: in a closed window its slab modes come first.* (round 23, E1; the full
  sentence is its title). The row is never cut: its words wrap, the buttons move to a line of their
  own when they do not fit beside them, and the box beside Run study grows to hold it (until round 23
  the row was cut to the box, and four of five testers needed the title or the panel to read it;
  checked at 1440 × 900 and 390 × 844). Both places offer **Set search near 2.46 · 4 modes** (the shortcut's target estimate,
  (n_max + 1.444)/2) and **Use Open boundary**; each sets its inputs and runs nothing. The
  shortcut's 4 modes are for the closed window's search (round 29, L1): when the shortcut was the last
  change of Modes to find and the outer boundary then turns to Open boundary, Modes to find goes back
  to the count it had before the shortcut, and Messages says so after the boundary's sentence: *Modes
  to find back to 2: 4 was for the closed window's search near 2.46.* This is an edit of its own, so
  Undo gives back 4 with Open boundary still chosen. Nothing changes when Modes to find was changed by
  hand after the shortcut, was 4 already, or after Undo, Redo or new inputs; turning back to the
  closed window changes nothing either. The warning goes with Nearest to n_eff or Open boundary. While it is shown, **Run study** asks once before it
  runs (round 27, D2), in a dialog *Slab modes first*: *Substrate touches the window edge, so a
  closed-window run returns its slab modes first. Search near the core instead?* with **Set search
  near 2.46 · 4 modes and run** (the warning's shortcut, then the run), **Run as set** (the run as
  without the question: the same document, values and record) and **Cancel** (Escape too; nothing is
  run). Since round 28 (G3), when a run already has the shortcut's results (Nearest to n_eff 2.46,
  Modes to find 4 and the other current inputs: the rule of the panel button's *No need to run*), the
  first button reads **Set search near 2.46 · 4 modes · show Run 6**: it sets the shortcut's inputs,
  with the panel button's message, and shows Run 6 under Results without running a copy; Run as set
  and Cancel are unchanged. Focus starts on the first button. It asks again only after the geometry, the boundary or
  Modes to return changes (a change and back counts); otherwise Run study runs as set at once. It is a geometry and material check with no solve: a
  shape touches the edge when its bounds reach the window, the shape names are those of the
  highest-index edge shape and the highest-index shape away from it (the first of equal ones), and no
  warning is given when no shape, or every shape, touches the edge. The result-side edge note is
  unchanged, and the closed search stays Highest by default. Limitation: Studio compares its 1550 nm
  table (physmat); the ten materials keep the same order, with no ties, at every wavelength from 1400
  to 1700 nm (`tests/simcase/test_studio_round22.py`), so the decision is the same at the run's
  wavelength. Overlapping shapes are compared as drawn, not by what the later shape hides.
- **The run.** A run with Nearest to n_eff writes `target_effective_index` and names capabilities v10.
  Studio keeps only the modes with Re n_eff above 1.45 (decision A1): the line above the table always
  reads *Found k of M modes near n_eff 2.46, above n = 1.45.* (M: Modes to find), and a note under
  the table says *1 mode at or below n = 1.45 was left out.* when the engine returned some below
  (the template @2.46 with 4 modes: 2.44257822, 1.76989777, 1.49297336 listed, 1.39191472 left
  out). The modes keep the engine's order, by descending Re n_eff.
- **The core mode.** In a closed run with Search near n_eff where a shape touches the window edge, a
  mode whose |E|² share (the edge note's share) in one shape that does not touch the edge is above
  0.5 gets a note row: *Mode 2 is the core mode: 64 % of |E|² is in Core, which does not touch the
  window edge.* (the strip over a substrate @2.46 with 2 modes; with 4 modes it is mode 3). The
  share is Studio's unweighted |E|² share; the engine's energy fraction (confinement factor) of the
  same mode is 0.91.
- **Words.** The plan line beside Run study reads *Closed window · near n_eff 2.46 · 2 modes* (since
  round 28, G2, with Modes to find); the next-run
  inputs end *· search near 2.46*; the run list, the Compare pickers and headings and the status line
  tag the run *closed near 2.46* where an untargeted closed run reads *closed*.
- **Runs and files.** A run's settings keep the target: adapter `optical-shapes-v10`, with
  `search_target` after `mode_count`. A session (and a project file's workspace entry) is written
  as **version 11** only when such a run is kept, otherwise as version 10, 9 or 7 byte for byte
  (checked against main 13f07f4); version 11 refuses a targeted run with a mode at or below 1.45, and
  a Studio that reads up to version 10 refuses it with *This session file is version 11, newer than
  this Studio reads (versions 6–10). Open it in a newer Studio.* The study signature includes the
  target, so a changed or removed target needs a run and only an equal one gives *No need to run*.
- **Limitation of this batch.** Modes to return and the target are not saved in model files, project
  inputs or the browser draft (the inputs stay version 7, 8 or 9), and Undo and Redo do not change
  them. A reopened session's runs keep their targets: **Use this run's inputs** on a closed targeted
  run selects Nearest to n_eff with the run's target (*… Modes to return highest n_eff → nearest to
  2.46 …*), so *No need to run* holds again. Since round 22 (V6) its message no longer says that Undo
  takes the target back: with other changes it ends *The next run uses them; Undo takes back the
  other inputs. Modes to return is set and is not part of Undo.*, and with the target alone *The next
  run uses it. Modes to return is set and is not part of Undo.* (until then *Search near n_eff off →
  2.46* and *Undo takes them back*).
- Checks: `tests/simcase/studio_closed_target_page.cjs` (K9, K10, K12, K13 and the pending job),
  `tests/simcase/test_studio_closed_target.py` (K12 on engine fields) and the workspace browser
  check's stage CW.

### Open boundary in the optical workspace

Since slice P2 the page offers the open boundary of
[optical-shapes-v9](#open-boundary-document-optical-shapes-v9). With it, a run's loss includes
leakage out of the window.

**The choice.**

- **Physics › Optical modes** has *Outer boundary: Closed window (PEC) / Open boundary (PML)*.
  Closed is the default. The help reads “Open boundary adds an absorbing layer (PML) outside the
  window, so light that leaves the window is lost. Loss then includes leakage. Shapes touching an
  open edge continue through the layer.” Since round 20 the *Optical adapter scope* note beside it
  names both boundaries, whichever is chosen: *3 × 2.4 µm window, closed (PEC edges) or with an open
  boundary (PML 1 µm outside the open edges, PEC on the closed ones)* (with a closed window it read
  *PEC outer edges* next to the Open boundary choice).
- The choice is a physics setting kept with each run, like Modes to find.
- With Open, every edge is open. **Geometry › Boundaries** lets each edge be closed again: an
  open edge reads *Optical left boundary · Open (PML)*, and a **Close this edge** switch closes or
  reopens it. A closed edge reads as before (PEC). With every edge closed, a run is a closed
  window.
- **Also compute group index** works with Open too (slice P3). The engine's n_g is then complex,
  and the n_g column shows Re n_g (see [mode identity](#mode-identity-with-an-open-boundary)).

**Parameters.**

- The PML is 1 µm thick, shown read-only as *PML 1 µm*; there is no thickness field.
- Strength 3, order 2 and a minimum physical fraction of 0.5 are fixed and listed under
  *Details*: *… · 32 candidates searched near n_eff, 16 near the second index*.
- **Search near n_eff** can be edited. Its default is (n_max + n_SiO2)/2 at 1550 nm rounded to
  0.01 (2.46 for silicon, shown *2.460*). Edits are kept to 3 decimals, and the value shown is
  the value sent. It must lie strictly between 1.45 and n_max.
- The second target is shown beside it as text, not editable, and follows the shown target:
  *Also searches near 1.95, for modes close to the silica index.* (2.20 → 1.82). The help reads
  “Studio searches for modes near this index and near a second index halfway to the silica index
  (1.95). Modes are listed by n_eff, highest first. The default is halfway between the core and
  silica indices: (n_core + 1.444)/2.” (round 18: where 2.46 comes from).
- Below 1.466 there is one search: no second target is shown, and the help keeps P2's words (a
  single target can miss modes far from it, notably near the cladding index) and ends with the same
  sentence on the default, *…: (n_core + 1.444)/2, rounded to 0.01.*

**Study and drawing.**

- Study shows *Open boundary · PML 1 µm · searches near 2.46 and 1.95* (*search near 1.465*
  below 1.466) and the option **Also check the PML (N more solves)**, off by default, with N =
  Modes to find. In the words of two searches a target is written to 3 decimals with one trailing
  zero dropped (2.46, 2.455, 2.50), and t_low to 2.
- The drawing shows a grey band labelled *PML 1 µm* outside each open edge. The band is drawn
  narrower than 1 µm so the window stays in view. The section line ends “… · open boundary
  (PML 1 µm) on N edges”.

**Results of an open run.**

- The table is titled *Modes (open boundary, PML 1 µm)*. Its loss column is **Loss (dB/cm)**,
  with the help “Material absorption (k) and leakage into the PML of the open boundary”.
- The loss uses the same formula (dB/cm = 20 · log10(e) · k0 · Im n_eff / 100), to 4
  significant digits (*29.15 dB/cm*). A number's help adds the measured mesh error: “At the
  default mesh this loss is about 3 % above the converged value (TE-like +2.8 %, TM-like +1.8 %
  on a strip over a substrate).”
- Below 0.01 dB/cm the cell reads **< 0.01 dB/cm**. This includes a negative Im n_eff and one
  the engine labels `numerically_unresolved`. The help reads “Below what this open boundary
  resolves for a 3 × 2.4 µm window (0.01 dB/cm). The mode does not leak measurably here.” A mode
  without Im n_eff reads “—”.
- A negative Im n_eff whose |loss| is 0.01 dB/cm or more reads **not resolved (|loss| < X dB/cm)**,
  X being |loss| rounded up to 2 significant digits (Im n_eff −2.67e-7 at 1550 nm, 0.094 dB/cm,
  reads *not resolved (|loss| < 0.095 dB/cm)*). The help reads “The solve gives a small negative Im
  n_eff within the PML's numerical noise; the loss is below about X dB/cm.” This changes P2's rule
  (V14), which wrote *< 0.01 dB/cm* for any negative Im; the engine may accept such modes as lossless
  within the PML's bound. A negative Im below 0.01 dB/cm keeps *< 0.01 dB/cm*.
- n_eff shows Re as a closed run does, with Im to 3 significant digits: *2.44126325 +
  8.28e-5i*.
- Polarization and A_eff are computed over the 3 × 2.4 µm physical window, with the PML
  excluded. n_g shows Re n_g. See [mode identity](#mode-identity-with-an-open-boundary).
- The note under the table adds “Leakage depends on what lies outside the window: shapes
  touching an open edge continue through the PML.” A closed run's note adds “For leakage, choose
  Open boundary in Physics › Optical modes.”
- The found line is always shown: *Found 2 of 2 modes near n_eff 2.46 and 1.95 (Studio's second
  search, halfway to the silica index). Move Search near n_eff to find other modes.* (round 27, D3: it
  names what the second target is; a result with no mode above 1.45 says *No mode above n = 1.45 was
  found near n_eff 2.46 and 1.95 (Studio's second search, …). …* in the same words). A run of one search (below 1.466, or a run of slice P2) reads as
  before: *Found 2 of 2 modes near n_eff 2.460. Move Search near n_eff (Physics › Optical modes) to
  find other modes.*
- Studio keeps the engine's modes with Re n_eff above 1.45.
- **Other candidates (n) — not shown as modes** lists every searched candidate that is not shown,
  with its n_eff, physical share and reason. The reasons read *Mostly in the PML (a PML mode)*,
  *Gains power (not a passive mode)*, *Not converged (residual above 1e-8)*, *Beyond the modes
  asked for* and *Below the silica index (cladding radiation)*. These rows have no field view.
- With two searches the table also has a **Search** column (*near 2.46*, *near 1.95*). A candidate
  of the second search that repeats one of the first (the engine's `duplicate_of`) is not listed;
  the title counts them: *Other candidates (41) — not shown as modes · 3 found by both searches*.
- The field view, its colour scale and the line profile use the physical window only. The
  engine normalizes an open run's field to its largest |E| there (`physical_max_centroid_magnitude`).

**PML check.**

- With the option on, Studio solves the run's document again once per mode found: PML strength 6,
  a search of 16 candidates and Search near n_eff at that mode's Re n_eff (to 6 decimals). The
  mesh is the same, node for node. The check searches once: the run's second search is left out,
  so the check documents are those of slice P2 byte for byte.
- The candidates of these solves are pooled. Each mode is paired with the nearest eligible
  candidate: one that passed the engine's filter (selected, or set aside only as beyond the
  count) and has Re > 1.45. A pair is accepted when |Δn_eff| ≤ 2e-3.
- A mode is PML-independent when |ΔRe| ≤ 5e-4 and the loss changes by at most
  max(2 %, 0.01 dB/cm).
- Below the display floor the check solve leaves a larger residue than the run's solve on tiny
  losses. When a mode's cell reads *< 0.01 dB/cm* and its check loss is below 0.05 dB/cm, the
  check gives no verdict. It says only that no leakage is resolved; it does not certify
  independence.
- The **PML check** column then reads one of:
  - *PML check: loss changes 0.016 %* (two significant digits below 0.1 %);
  - **Depends on the PML**: *loss changes 12 %* (or *Re n_eff changes 7.0e-4*), with the loss
    cell in italics and the help “This loss changes with the PML; it is not a converged leakage
    loss.”;
  - *PML check: no leakage resolved (both solves below 0.05 dB/cm)*, without italics;
  - *Not found in the check solve*, with the help “The check solve did not find this mode near
    the search value; this does not by itself mean the mode depends on the PML.”
- A mode below the floor whose check loss is 0.05 dB/cm or more keeps *Depends on the PML*: the
  floor moves with the PML.
- The engine's `stability: "not_checked"` stays true of each solve; the run records the check
  (`pml_check`). A check is stored when all its solves are in. Solves finished before a page
  reload are not kept: that check is incomplete and is not stored.
- **How the check was chosen.** A single check solve (strength 6, search 32 near the run's
  target) missed the TM-like mode of the template and of the leakage case. A search of 64 missed
  it too: the target, not the count, decides. Measured one thread, engine level, with the
  non-slow test suite running alongside (times relative):

  | Check | Template | Leakage case | Every mode found again |
  |---|---|---|---|
  | one solve, search 32 near the target | 2.8 s | 35.4 s | no (TM-like missed) |
  | one solve, search 64 | 5.2 s | 91.8 s | no |
  | one solve per mode at its Re, search 32 | 5.0 s | 64.5 s | yes |
  | one solve per mode at its Re, search 16 (shipped) | 2.6 s | 43.8 s | yes |

  The first solves took 3.5 s and 36.3 s.
- **A registered result that failed.** With the per-mode check, the template's TM-like mode was
  registered as PML-independent. It went from 0.00480 to 0.01706 dB/cm, so it read “Depends on
  the PML: loss changes 256 %”. The rule for losses below the floor was added after that result.
  It was confirmed, as registered before measuring, on the template core at 700 × 300 nm with 4
  modes: every mode is below the floor, with check losses of at most 0.00026 dB/cm.
- Results with the check on:
  - the template: both modes *no leakage resolved*;
  - the leakage case: TE-like 29.1528 → 29.1517 dB/cm (*loss changes 0.0038 %*), TM-like
    1005.96 → 1005.80 dB/cm (*0.016 %*), both PML-independent.

**Compare.**

- Each side's loss header follows its own run in its help (*Loss A (dB/cm)*: absorption only, *Loss B (dB/cm)*: with leakage); the group reads *Loss (dB/cm)* without a second line.
- When the two differ, a note reads “A counts material absorption only; B also counts leakage.
  Their difference is not a leakage loss.”
- With an open run, the line above the table names each run *(closed)* or *(open, PML 1 µm)*.
- Matching with an open run is on (slice P3). It compares the fields on the common grid over
  the intersection of the two runs' physical windows. Each matched row names its runs in the
  header, for example *A · Run 1 (closed)* and *B · Run 2 (open, PML 1 µm)*. In slice P2 it was
  off: the blind check V13 (closed against open, η ≥ 0.99) failed with η = 0.9903 for the TE-like
  mode and 0.9875 for the TM-like mode. See
  [mode identity](#mode-identity-with-an-open-boundary) for the diagnosis and the checks that
  replaced it.

**Files.**

- A model file chooses Open as inputs version 9: version 8 with `model.openBoundary {edges:
  {left, right, bottom, top}: "open" | "closed", target}`. `target` (Search near n_eff, 3
  decimals) is written only when it was edited.
- Without Open the file is version 7 or 8 byte for byte, as before. Studio 4b58fb7 (before
  slice P2) refuses an inputs file of version 9 with *Unsupported model file format or version.*
- A session is written as **version 10** when a run has an open boundary or the inputs choose
  Open (inputs version 9). Otherwise it is version 9 or 7, byte for byte as before.
- Version 10 is version 9 plus runs of `optical-shapes-v9`. Their `settings` hold `adapter
  "optical-shapes-v9"`, `boundary "PML"` and `pml {"thickness": "1000 nm", "open_edges": [...],
  "target": "2.460"}`.
- Such a run also keeps `open_boundary`, the engine's candidate record of its search, and
  `pml_check {"pml_strength": 6, "paired": [{"re", "im"} or null per mode]}` when the check ran.
  The digest covers both.
- Slice T2 changes neither the settings nor the file version. A run of two searches keeps the
  engine's record `openphysics.pml-candidates/3`, whose `searches` must be exactly 32 near the
  run's target and 16 near its t_low; any other /3 record is refused as an invalid open boundary
  record. A run with a record /2 (one search: a run of slice P2, or a target below 1.466) reads with
  its words as before. A version 10 file written before slice T2 opens with the same values and
  words, and **Use this run's inputs** followed by a run builds the document of both searches.
  The study signature is unchanged, so such a run still reads as made with the current inputs.
- Its field implies the normalization above.
- **Fields on the physical window only.** An open run keeps the triangles that meet its physical
  window plus a thin margin of 1/150 of the window's longer side, so pictures at the window edge are
  unchanged; the PML beyond it is not kept. (The field view clips to the window with antialiasing, so
  a triangle just outside it tints the edge pixels it partly covers; the margin, 20 nm for the 3 × 2.4
  µm window, covers them whenever the plot spends at least 150 device pixels on that side, as Results
  and Compare always do.) The test is a separating-axis test on the stored coordinates in metres,
  bounds included; the triangles keep the engine's order, their nodes are renumbered in order of
  first use, and no coordinate or sample value changes. For the T16 run (a strip over a substrate,
  open on four edges) it keeps 12,253 of 40,658 triangles. Every triangle whose centroid lies in the window
  is among them, so the physical window, the TE fraction, the effective area, matching, the field
  view and the probe read the same values as with the full samples. The run file of **Export this
  run** holds the same samples and its message says so. A run read from a file (session, project,
  recovery or run file) is never cropped: a file written before this change keeps its full samples
  and is written again byte for byte. A run without valid `physical_bounds` keeps all its samples.
  Two copies of one job, one with full samples and one cropped, are the same result when their
  samples agree on the window. The file version stays 10 and no key is added.
- **Where each mode lies (round 25, A4).** An open run's modes table gets the closed window's note
  rows, with the same thresholds (a share above 0.5; for a shape touching the window edge, at least
  0.01 of |E|² within 300 nm of the edges it touches) and the same shape layering, measured over the
  physical window only: the triangles whose centroid lies in the 3 × 2.4 µm window, so the PML (kept
  in runs read from older files) counts in neither the share nor its total. The core mode reads
  *Mode 3 is the core mode: 64 % of |E|² in the window (PML excluded) is in Core, which does not
  touch the window edge.* A mode mostly in a shape that meets an open edge reads *Mode 2 is mostly in
  Substrate (93 % of |E|² in the window, PML excluded), which continues into the PML at the open
  window edge.*, and at a closed edge of the open run *…, which touches the closed bottom edge; its
  n_eff depends on that closed edge. Open it in Geometry › Boundaries to leave it open.* (*…
  bottom and left edges; … those closed edges. Open them …* for two or more). These words say only
  where the |E|² lies; whether the mode can leak is the [guided or leaky](#guided-or-leaky-open-boundary-modes)
  text that follows them. Compare's edge-note line and its no-match reason stay closed-window only.
- **Guided or leaky (open-mode notes).** Each mode of an open run gets one more sentence, after its
  region note in the same note or as a note of its own. See
  [Guided or leaky open-boundary modes](#guided-or-leaky-open-boundary-modes).
- Slice P3: a new open run also keeps the engine's `te_polarization_fraction` and
  `effective_area` (physical window). With the group index it keeps `group_index` as `{"re",
  "im"}` with `group_index_method`. A closed run's `group_index` stays a list. A run written by
  slice P2 has none of these keys. Studio computes its TE fraction and effective area from its
  stored field over the window that its `open_boundary.physical_bounds` gives, and saves the
  run as it was.
- A [project file](#project-files) holds such a session as its workspace entry: its reader takes
  optical sessions of version 6, 7, 9 and 10.
- A version 9 session does not hold inputs of version 9. Studio 4b58fb7 refuses a version 10
  file with *This session file is version 10, newer than this Studio reads (versions 6–9). Open
  it in a newer Studio.* Multiphysics sessions stay version 8.

**Server.** A workspace request carries `pml_strength` 3 with a search of 32 (a run), or 6 with
a search of 16 (a check solve). Its target may be any value above 1.45, since a check solve aims
at a mode. Anything else is refused by name: “A PML check request (strength 6) searches 16
candidates, and a run (strength 3) searches 32.” or the open boundary's message.
`/api/workspace/capabilities/v9` lists `pml_check_strength` 6 and `pml_check_search_mode_count`
16. This changes P1's contract: P1 refused strength 6 and a search other than 32.

**Validation** (Linux, Python 3.12, Node 22, in the browser check
`tools/studio_browser/studio_workspace_browser.mjs`, stage OB):

- the template, all edges open: both loss cells *< 0.01 dB/cm*, as registered (the engine gives
  TE-like Im n_eff −5.1e-12, `numerically_unresolved`, and TM-like 1.36e-8, 0.0048 dB/cm); 30
  other candidates;
- the leakage case built in Geometry (a silicon substrate x −1500, y −1200, 3000 × 700 nm under
  the core, BOX 500 nm, all edges open): its document is P1's strip over a substrate byte for
  byte. In the Linux container it was measured in, it shows *2.44126325 + 8.28e-5i* / *29.15
  dB/cm* and *1.77279036 + 2.86e-3i* / *1006 dB/cm*, P1's values.
  - As first registered, the check asserted those strings on every platform. The registration
    wrongly assumed platform-independent values, and CI failed on them: ubuntu-24.04 showed TE
    Re 2.44128662 (ΔRe 2.3e-5); macos-15 showed TE “29.18 dB/cm” (+0.10 %) and Re 2.44113899.
  - Re-registered after that result: the screen strings must equal, exactly, those of
    `simcase.run` on the same document on the same machine, formatted by the page's formatter.
    The byte-for-byte document check stays.
  - Values in CI:

    | Platform | TE-like | TM-like |
    |---|---|---|
    | ubuntu-24.04 | 2.44128662 + 8.28e-5i, 29.15 dB/cm | 1.77280379 + 2.86e-3i, 1006 dB/cm |
    | windows-2022 | 2.44128662 + 8.28e-5i, 29.15 dB/cm | 1.77280379 + 2.86e-3i, 1006 dB/cm |
    | macos-15 | 2.44113899 + 8.29e-5i, 29.18 dB/cm | 1.77278771 + 2.86e-3i, 1006 dB/cm |

    The PML check verdicts are the same on every platform. The differences, 1e-4 in Re and 0.1 %
    in loss, are far inside the default mesh's error of about 3 %;
- Search near n_eff 1.600 with 4 modes on that case finds the mode near the cladding index,
  *1.48642654 + 7.92e-3i* / *2789 dB/cm*, as registered.

### Guided or leaky open-boundary modes

Each mode of an open-boundary run gets a sentence that says whether it can leak, from data the
run already stores: Re n_eff, the input shapes, the open edges and the wavelength. It needs no
field, so a run whose fields were made compact or dropped is classified the same. No session,
project or run record changes, and a closed run gets no such text (its page is unchanged).

**The rule.** Beyond an open edge the structure does not change along the edge's normal: the
shapes along that edge continue through the PML, so the layer holds the edge's material profile,
semi-infinite. A mode can carry power away through the edge exactly when Re n_eff lies below the
highest transverse cutoff index of that profile. Studio does not solve the profile; it reads two
bounds off the shapes, with the material indices at the run's wavelength (a frozen physmat table,
1400 to 1700 nm every 10 nm, linearly interpolated, within 1e-4 of physmat at every nanometre):

- n_hi(e), the largest index on the edge (the extruded profile, silica where no shape covers it,
  and any shape that touches the edge without continuing through the layer: a circle's chord, a
  polygon's vertex). The cutoff is at most n_hi(e).
- n_lo(e), the largest index of a material that fills a half-space beyond the edge (one material
  along the whole edge) or a quarter-space (the PML corner at an end of the edge whose other edge
  is also open: the polygon that lies along both edges there, else silica). The cutoff is at least
  n_lo(e); without either, n_lo(e) is −∞.

With x = Re n_eff and δ = 0.02, over the open edges:

| Category | Condition | Text |
|---|---|---|
| leaky into R | some n_lo(e) > x + δ (every such region R, highest index first) | *Mode 2 is a leaky mode: Re n_eff 1.773 is below the index of Substrate (3.478), which reaches the open window edge, so light can leak into Substrate. The loss shown is that leakage; it is part of this structure, not a fault of the solve.* |
| guided | every n_hi(e) < x − δ | *Mode 1 is guided: Re n_eff 2.443 is above the index of every material at the open window edges (the highest is the silica background, 1.444), so it cannot leak. The loss shown is numerical (mesh and PML), not leakage.* |
| no claim (layer) | neither, and a material above x + δ reaches an open edge only as a layer, between closed corners | *Mode 1: Re n_eff 2.441 is below the index of Substrate (3.478), which reaches the open left and right edges only as a layer. Whether light can leak into it depends on that layer's own modes, which Studio does not compute; Studio does not say whether this mode is guided or leaky.* |
| no claim (near) | otherwise: x within δ of an edge index | *Mode 3: Re n_eff 1.460 is within 0.02 of the index of the silica background (1.444) at the open window edge, closer than this solve resolves; Studio does not say whether it is guided or leaky.* |

|x − n| ≤ δ is always on the no-claim side. Re n_eff and the indices are shown to 3 decimals;
the decision uses the unrounded values. δ is 1.5 × the largest measured mesh error of Re n_eff
(1.3e-2 low at the coarsest core mesh, 60 nm; coarse meshes read low). The ten Studio materials
are lossless from 1400 to 1700 nm, so a guided mode's exact Im n_eff is 0 and a leaky mode's loss
is leakage.

**Placement.** When the mode has a [region note](#open-boundary-in-the-optical-workspace) (the
core mode, or a mode mostly in a shape touching the window edge), the sentence follows it in the
same note, its opening reworded: *Mode 1 is the core mode: 64 % of |E|² in the window (PML
excluded) is in Core, which does not touch the window edge. It is a leaky mode: Re n_eff 2.441 is
below …* (*It is guided: …*, *Re n_eff … is within …*). Otherwise it is a note row of its own
under the mode. The loss column, the PML check column, the found line, Compare and the region
words are unchanged; *leaky* beside *Depends on the PML* is consistent (the channel exists, the
loss value is not converged).

**Guard.** The text is checked against the loss with the engine's [gain bound](pml_modes.md#the-gain-bound)
b = max(1e-10, 1e-2 f_pml) max(1, |Re n_eff|), f_pml the stored `pml_l2_fraction` of the mode's
candidate. A guided mode with Im n_eff > b gets no text (the category and the loss disagree, and
saying nothing is better than saying something false). A leaky mode with Im n_eff ≤ b keeps its
first sentence and ends *This solve resolves no leakage loss.*

**What it does not say.** *Guided* does not say the loss shown is small: a near-cutoff guided
mode whose field reaches the PML can show PML noise (0.80 dB/cm measured, −0.65 dB/cm on the PML
check, on the strip over a substrate with only the top edge open). *Leaky* does not say the loss
is converged (mesh refinement and the PML check do) or that the coupling is strong: a channel can
carry little or, for a symmetry-protected bound state, no power. Neither says where the |E|² lies.
There is no radiation-mode or PML-mode category: the physical-fraction filter (0.5) already
removes PML-dominated candidates, and the stored fraction cannot separate a PML mode from a
physical pole; the PML check is the test of PML dependence.

**Limitations.**

- Bounds, not a 1D solve: a layer that reaches an open edge only sideways gets no claim even when
  the mode leaks (the strip over a substrate with the bottom edge closed leaks 2.80 dB/cm
  sideways through the substrate layer).
- Near cutoff: Studio lists modes above Re 1.45, and every listed mode up to Re 1.464 is within δ
  of silica, so in a run whose edges are all silica it gets *no claim (near)*.
- δ covers the measured mesh error with a factor of 1.5; that is a measurement, not a proof.
- The bound uses the largest index for both polarizations; it does not separate a TE-only or
  TM-only channel threshold (both lie below n_hi, so *guided* stays sound).
- Sapphire, lithium niobate and magnesium fluoride are solved as isotropic with the ordinary
  index, and the rule uses the same index: it agrees with the solve, not with the real crystal.
- A touching circle or vertex counts in n_hi though it does not continue through the layer, so it
  can only turn *guided* into *no claim*.
- An absorbing material would need other words and an absorption estimate in the guard; none of
  the ten absorbs in the band.

**Validation.** Pre-registered in the design draft (main 2318e5f) before the implementation;
measured on this branch, Linux:

| Gate | Case | Result |
|---|---|---|
| G1 | T16: the strip over a substrate, every edge open, the default targets (2.46 and 1.95), 4 modes | 2.44126325 + 8.28e-5i, 1.77279036 + 2.86e-3i, 1.48642654 + 7.92e-3i: leaky into Substrate, each Im n_eff above b (4.8e-6, 4.8e-5, 3.2e-4); the three strings exactly as registered, mode 1's after its core note (64 %): passed |
| G2 | The template, every edge open, 2 modes; and near 1.600 with 4 modes | 2.44290906, 1.76999578 and 1.49230387 guided, each within b: passed |
| G3 | The leaky slab, left and right closed, near 2.85 | 2.84472916 and 2.83267892 leaky into Substrate, above b: passed |
| G4 | The strip over a substrate, only the top edge open, single searches near 2.441, 1.773, 1.49 | 2.44081333, 1.77075412, 1.48502123 guided, within b (the last: Im 2.3e-6, b 1.2e-4): passed |
| G5 | The strip over a substrate, bottom edge closed, near 2.441 and 1.773 | 2.44110903 and 1.77061893 no claim (a layer, left and right), the registered string: passed. Both leak (7.96e-6 and 1.49e-4, above b), which the bounds cannot certify |
| G6 | G1 and G2 at core mesh 20 and 60 nm | the same categories; blind: T16's mode 3 at 60 nm, 1.48211701 + 8.22e-3i, leaky into Substrate: passed |
| G7 (blind) | G1 at 1400 and 1700 nm | 2.60967516 and 1.99870109 (1400 nm), 2.27114152 and 1.62593635 (1700 nm) leaky into Substrate: passed |
| G8 | Every mode of G1 to G5 | guided within b, leaky above b: passed |
| G9 | Every closed run of the session fixtures (98 records) | no category text; notes, maps and run records unchanged: passed |
| G10 | The unit cases (no solve) | passed |

G1 to G8 are slow tests, `tests/simcase/test_studio_mode_channel_gate.py` (G1–G5, G8) and
`test_studio_mode_channel_mesh.py` (G6, G7), run with the rest of the suite in CI; G9 and G10 are
`tests/simcase/studio_mode_channel_page.cjs` and `studio_mode_channel.cjs`. The workspace browser
check compares the T16 notes of its leakage case and of its 8-mode run, and the template's guided
note, with the page module's texts for the engine run of the same document on the same machine.
Re n_eff differs between platforms by about 1e-4; the gates compare categories, and strings to 3
decimals, from the same machine's solve.

### Mode identity with an open boundary

Slice P3 gives an open run the TE fraction, the effective area, the group index and matching in
Compare, all defined on its **physical window**. The physical window is the set of triangles whose
centroid lies inside the engine's `physical_bounds`, the 3 × 2.4 µm window without the PML. There
the saved centroid field is the physical E. For a closed run the physical window is the whole
window, so every closed formula and value is unchanged.

- **Polarization** (f_TE) uses the closed formula summed over the physical window. Its help
  reads “TE = share of |E_x|² in |E_x|² + |E_y|², x horizontal, over the 3 × 2.4 µm window, PML
  excluded”.
- **A_eff** is (Σ A_T |E|²)² / Σ A_T |E|⁴ over the same triangles. Its help reads “Effective area
  over the 3 × 2.4 µm window, PML excluded. For a strongly leaking mode it depends on the
  window.”
- The engine writes both values (`mode_postprocessing`, `integration_region: "physical_window"`).
  Studio uses the engine's values, and for a run saved by slice P2 computes the same numbers from
  the stored field. *Run details* name the source: “computed by the engine (or by Studio) from the
  saved field on the physical window (PML excluded)”.
- **n_g** is complex with an open boundary; the column shows Re n_g. Its help adds “With an open
  boundary n_eff and n_g are complex: Re n_g is shown; Im n_g …. At the default mesh n_g is
  about 5e-3 low in the slab check; the error comes from n_eff and shrinks when the core mesh is
  refined.” The PML check's solves leave the group index out.
- **Compare** matches an open run on the intersection of the two physical windows. An open
  sample is used only on a triangle of its physical window.

**Validation** (`tests/simcase/test_open_boundary_mode_identity.py` and, for V11,
`tests/simcase/test_open_boundary_group_index.py`; Linux, Python 3.12, one BLAS thread):

| Check | Case and criterion | Result |
|---|---|---|
| V9 | template open against closed, \|Δf_TE\| ≤ 1e-3 | 1.70e-4 (TE-like 0.98166 → 0.98149), 1.5e-5 (TM-like): passed |
| V9 | the V1 film (TE, PEC side walls) at × 1, ½, ¼: 1 − f_TE ≤ 1e-3 and decreasing; halvings blind | 5.70e-4, 2.76e-4, 1.08e-4: passed |
| V10 | template open against closed, relative ΔA_eff ≤ 1e-2 | 7.2e-4, 9.9e-5: passed |
| V12 | Studio's formula in Node against the engine's on the same samples, ≤ 1e-12 relative; blind | ≤ 3.4e-15 on the template (2,283 of 4,557 triangles in the window) and the strip over a substrate (11,591 of 40,658): passed. The window equals the solver's own physical mask |
| V13a | open template against the same mesh with PEC at the outer edge, η ≥ 0.9999 | 1 − 4e-14, 1 − 2e-11: passed |
| V13b | template closed against open at × 1, both modes paired with their own counterpart (η ≥ 0.8, margin ≥ 0.1) | 0.99033, 0.98754: passed |
| V13c | TE-like 1 − η(closed, open) decreasing at × 1, ½, ¼ | 9.67e-3, 3.15e-3, 9.44e-4: passed. TM-like (reported, not gated): 1.25e-2, 3.94e-3, 1.12e-3. Before the [gain bound](pml_modes.md#the-gain-bound) the open run did not return the mode at × ½ and × ¼ (see the limitations below) |
| V11a | dn_eff/dλ0 of the V1 film against refsol, ≤ 1e-3 relative at × 1, ½ and ¼ (decided after the result; first registered with “not growing”, which FAILED) | 5.61e-4, 7.29e-4, 7.29e-4: passed; the slope settles at a plateau (below) |
| V11b | Re and Im n_g errors against refsol decreasing at × 1, ½, ¼ | Re 5.24e-3, 2.81e-3, 1.50e-3; Im 2.69 %, 1.06 %, 0.40 %: passed |
| V11c | single-point n_g against the tracked sweep, ≤ 1e-12 relative | equal (relative difference 0): passed |

- **V11 as first registered failed.** The gates were |ΔRe n_g| ≤ 1e-3 and Im within 2 % at
  × 1, against refsol's central difference at 1549 and 1551 nm with physmat's dispersion,
  3.706654 − 2.688e-4i. They sat below the default mesh's own n_eff error, which V1 gates only
  at × ¼. V11a–c replaced them after that result.

  | Mesh | Re n_eff error | Re n_g error | Im n_g error |
  |---|---|---|---|
  | × 1 | 4.76e-3 | 5.24e-3 | 2.69 % |
  | × ½ | 2.18e-3 | 2.81e-3 | 1.06 % |
  | × ¼ | 0.87e-3 | 1.50e-3 | 0.40 % |

  The tracked sweep gives the same n_g. Almost all of the error is n_eff's.
- **The plateau of dn_eff/dλ0 (V11a).** The FEM slope settles about 7.3e-4 (relative) from
  refsol's, which is about 6e-4 in Re n_g, against 5.2e-3 at the default mesh. Cases tried at × ½
  (relative slope error):

  | Case | Slope error |
  |---|---|
  | shipped recipe, × ½ (× ¼) | 7.29e-4 (7.29e-4) |
  | PML strength 6 instead of 3 | 7.29e-4 |
  | PML 2 µm instead of 1 µm | 6.84e-4 |
  | constant n for Si and SiO2 in both models | 6.82e-4 |
  | a 2 nm step in both models | 7.29e-4 |
  | far size and element size halved again | 1.18e-3 |
  | refinement distance 2 µm | 1.15e-3 |

  The offset does not change with the PML strength, the dispersion, the difference step or the
  core mesh. It moves −6 % with a 2 µm PML. It grows above 1e-3 when the mesh away from the core
  is refined, while n_eff comes closer to refsol. **Cause not found.** The 1e-3 gate holds on the
  shipped mesh recipe, not on a refined cladding.
- **V13 as first registered** (slice P2, η ≥ 0.99, blind) failed with 0.9903 and 0.9875. The
  cause is the default mesh's discretization error, not the PML:
  - two different meshes of one closed design differ as much (× 1 against × ½: 0.9933 and
    0.9920);
  - the common grid moves η by at most 6e-4 (spacing 15 to 3.75 nm).

  V13a–c replaced the check after that result.
- **Limitations.**
  - Until the [gain bound](pml_modes.md#the-gain-bound), a lossless TM-like mode was dropped on
    refined open meshes: its tiny Im n_eff came out with the wrong sign and the engine rejected
    it as `negative_imaginary_index` (the template's TM-like mode at × ½ and × ¼). The bound
    returns it, labelled `negative_within_pml_bound`.
  - A bent guide and the scalar formulation get none of these values.
  - The effective area of a strongly leaking mode depends on the window.

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
mode. An open run keeps its physical window only: the T16 run is 3.9 MB (13.4 MB with the PML), T16
with 3 modes and the group index 5.6 MB (19.0 MB). The measurement is
`tools/studio_open_field_size.mjs`. Measured on 2026-11-24 with the T18 strip over a silicon
substrate (core mesh 30 nm): a closed run with 2 modes is 2.10 MB, with 4 modes 3.78 MB, closed near
2.46 with 4 modes 3.75 MB, an open run with 2 modes 3.94 MB with or without n_g (the field is 99 % of
each; a run without its field is 3 to 21 kB), so the sixth run of T22 brought the session to 22 MB.
At [single precision](#compact-fields-single-precision) the same fields are 1.02, 1.74, 1.74 and
1.11 MB.
Since [run retention](#keeping-runs-values-and-fields) the optical model keeps its fields within one
budget, so a session never goes over the limit, Save asks nothing and browser recovery writes Save's
text. The question, the refusal and the recovery rules below still apply in the two cases where the
tab holds more than a file can (named in that section).

A session over the limit asks first, as a multiphysics session does: *Keep fields for selected and
pinned runs* writes the other runs without `field`, with their n_eff, TE fractions and effective
areas; Cancel writes nothing; when even the selected and pinned runs are over the limit, the save is
refused, naming the selected run and the pinned runs apart: *The selected run (Run 6) and the pinned
runs (Run 4, Run 5) are 46.2 MB with their fields, over the 16.8 MB session limit. Unpin some of
them.* (*Unpin it.* for one pinned run). Without a pinned run among them it says *The selected run
(Run 6) is 18.9 MB with its fields, over the 16.8 MB session limit. Select a different run before
saving, so this one is saved without its fields, or run it again with fewer modes.* The recovery error
says the same after *Recovery snapshot exceeds 16 MiB:*. When a result takes the session over the
limit its message adds *Session is now 18.9 MB, over the 16.8 MB limit, and File › Save will refuse:*
with the refusal and *Browser recovery is off.*; when the text grew past the limit with no field
arriving, the next result's line reads *Session is now 17.0 MB, over the 16.8 MB limit. Browser
recovery keeps every run's values; the field plots of Run 6 are not kept. File › Save will ask
whether to keep the field plots of the selected and pinned runs only (Runs 1, 2 and 9).* Round 24
(B3) gave these lines one unit, MB to one decimal (two decimals for a size just over 16.8 MB). When
the full text is over the limit, browser
recovery keeps, without asking, the fields of the selected and pinned runs, then (round 23) the
fields of the other runs newest first while the record stays within 16 MiB, and the header names the
runs left out: *… · kept for recovery in this browser without the fields of Run 1 and Run 2*. A
restore of a record that left fields out adds *Fields not kept for Run 1 and Run 2; their n_eff, TE
fractions and effective areas were.* to its message.

### Optical session files (version 12)

Since session version 12 (design *Stable run numbers and the project name after recovery*) an
optical run keeps its number in files and in browser recovery. Version 12 is
[version 9](#optical-session-files-version-9) with the open boundary of version 10 and the
closed-window search of version 11, plus one key per run: `number`, the run's number in the tab,
right after `job` and inside the run's `digest`. The top-level keys are those of version 9. Version
12 holds every run that versions 9 to 11 hold.

- **When it is written.** Exactly when some run's number is not its place in the list, for
  example after the limit dropped Run 1, or after runs were added from a file: Runs 2 to 7 are
  written as version 12. A session whose runs are numbered 1, 2, 3 … in list order is written as
  version 11, 10, 9 or 7, byte for byte as before. File › Save (a session file or a project file's
  optical entry) and browser recovery write the same text.
- **Reading.** File › Open, Open project and Restore keep the stored numbers, so the run list,
  the drop line and its **Pin Run N** button, the Compare pickers, *No need to run: Run N* and the
  recovery lists name the same runs as before. A file of version 6, 7 or 9 to 11 numbers its runs
  from 1 in file order, as before. There is no stored counter: the next run takes the largest
  number + 1 (after a file whose largest number is 8, the next run is Run 9), and the run with the
  largest number is never dropped (the limit keeps the new run; **Keep Run N, drop … instead** and
  Add runs from file drop only other runs). A run whose job comes back keeps its number and its
  place.
- **Checks.** Before the runs are read, each `number` must be present (*Run 3: missing number.*,
  by its place), a whole number of at least 1 within the safe-integer range (*Run 3: invalid run
  number.*), used once (*Two runs have the same number 7.*) and strictly increasing in list order
  (*Run 3 is numbered 5, not after Run 2's 7.*); there is no other upper bound. A number edited
  after the save fails the run's digest (*Run 2 changed after it was saved (its check value does
  not match).*). The run's own checks then name it by its stored number (*Run 6: invalid search
  target. …*). Versions 9 to 11 still refuse a `number` key (*Run 1: unknown key "number".*).
- **Earlier Studios.** A Studio that reads up to version 11 (main fc654fe) refuses a version 12
  file by name: *This session file is version 12, newer than this Studio reads (versions 6–11).
  Open it in a newer Studio.*, after *Optical waveguide: * for a project file's entry. It does not
  take over a browser-recovery record that holds one (it reads the record before it adopts it),
  so it never overwrites that record. The project file stays version 1; the optical documents,
  adapters, requests and results, the multiphysics session (version 8) and the run table CSV are
  unchanged.
- **No numbering sentence.** A session written before version 12 holds no run numbers; its runs
  are numbered by their place in the file. Studio writes an older version only when that
  numbering is exact. So no open or restore message speaks about numbering (round 19's *Runs are
  numbered from 1 in this tab; names and pins are kept.* is gone).
- **Add runs from file** numbers the added runs after the tab's largest number, in file order, and
  says so when a number changes: *Added Run 2 and Run 4 of design-b.json as Run 9 and Run 10.* A
  job already in the tab keeps the tab's number.

The checks are `tests/simcase/studio_session_numbers.cjs` (K1: every earlier optical fixture, the
multiphysics fixture and the project fixture read and written again byte for byte; K2: the version
12 fixture `optical-v12-numbers.json` of runs 3, 5, 6, 7, 8 and 9 and its refusals; K3 and K9: what
main fc654fe reads, `refusals-v12-fc654fe.json`), `tests/simcase/studio_session_numbers_page.cjs`
(K6: a seeded sequence of 2400 results, pins, swaps, imports, saves, opens and restores; K7: the
header lines; K10: no numbering sentence for a version 7, 11 or 12 file) and the K4/K5 stages of
`tools/studio_browser/studio_project_browser.mjs`.

### Keeping runs: values and fields

Since run retention (design *Keeping more runs*, round 24 B1) the optical model keeps the
**values** of up to 20 runs and their **fields** within one budget. The budget is shared by the tab,
File › Save, the project file's optical entry and browser recovery, so what the tab shows is what a
file or a restore brings back. Before, six runs were kept whole: a seventh dropped a run with its
values, and a tab over 16 MiB showed fields that Save asked about and recovery left out.

- **Values.** A run's values are n_eff (real and imaginary), the TE fractions, the effective areas,
  n_g and an open run's candidates. Every run keeps them. A run without its field is 3 to 21 kB in a
  file; 20 such runs are under 0.5 MB.
- **The budget.** It is the 16 MiB session less 16 KiB kept for your inputs: 16,760,832 bytes,
  said as 16.8 MB. The session text also holds the inputs, the comparison and the view, which change
  between results; the 16 KiB lets a tab filled to the budget stay within 16 MiB after such edits.
- **When fields go.** Only when a field arrives: a new result, a recomputed field, Add runs from
  file, File › Open or Restore, and **Keep Run N, drop … instead** bringing a run back. Selecting,
  pinning, unpinning, naming or comparing runs never lets a field go, so the tab may hold more
  fields than the order below would choose now, but never more than the budget.
- **The order.** When a field arrives, the fields kept are those of the selected run, then of the
  run whose field just arrived (a recompute, or a run brought back, when it is not the selected
  one), then of the pinned runs, newest first, then of the other runs, newest first (the largest
  run number first). Each is added while the session stays within the budget; a field that does not
  fit is skipped and the next older one tried. A pin keeps a run's values against the 20-run drop
  and puts its fields ahead of the unpinned runs', but does not guarantee them.
- **The words.** Before a run, when the newest run of the same geometry, boundary and Modes to find
  shows how large the new field will be, the line beside **Run study** names the runs that would keep
  their values only: *If you run: Run 3 (closed · 4 modes · 700 × 300 nm) keeps its values, not its
  fields* with **Pin Run 3** (two or more: *… and Run 5 (…) keep their values, not their fields*);
  with no such run it says *If you run: older runs' fields may not be kept (16.8 MB limit) · pin a
  run to keep its fields first* (round 25, A1; no Pin button, it names no run) when the room left in
  the 16.8 MB is less than the smallest field kept now, and otherwise nothing. Both lines count the
  sizes the result's arrival will apply: in a tab whose fields are still text, a result whose fields
  would not all fit as text makes every field compact first ([compact fields](#compact-fields-single-precision)),
  so the line names only the runs that would go even at single precision (round 26, C1). While the run computes: *When this run finishes, Run 3 (…) keeps
  its values, not its fields*. At 20 runs the line keeps the drop words above. After the result,
  Messages says *Run 3 (…) keeps its values; its fields were not kept (16.8 MB limit).* with
  **Recompute Run 3's fields** and, when another unpinned, unselected run has a field at least as
  large, **Keep Run 3's fields, not Run 4's (…)**, which answers *Run 3's fields are back; Run 4 (…)
  keeps its values, not its fields.* When a pinned run's fields go: *Run 2 (pinned) keeps its values;
  its fields were not kept: the selected and pinned runs' fields are 17.4 MB, over the 16.8 MB limit.
  Unpin a run to keep the newer fields first.* The run list marks such a run *· values only*; the
  tree reads *Runs · 9 of 20*; the note under the run list reads *Up to 20 runs are kept with their
  values. Fields are kept up to 16.8 MB. When a result or a recompute arrives, Studio keeps the
  selected run's fields first, then pinned runs', then the newest. Selecting a run does not bring
  its fields back; Recompute does. Pinned runs stay; when a 21st run arrives, the oldest unpinned
  run is replaced. …* (round 25, A1: fields move only when a field arrives). The header reads *… kept for recovery in this browser*: recovery
  holds the tab.
- **A run without its fields.** Results shows its modes table, its candidates and its inputs line,
  and in place of the field view *Run 4's fields are not kept; its n_eff, TE fractions and effective
  areas are kept. Fields are kept up to 16.8 MB. When a result or a recompute arrives, Studio keeps
  the selected run's fields first, then pinned runs', then the newest. Selecting a run does not
  bring its fields back; Recompute does.* (a run read from a file without fields: *Run 4's fields were not kept in the session
  file. …*) with **Recompute Run 4's fields** and, for a run computed in this tab, *· about 2 min*
  (its wall time; a run opened or restored has none). The field PNG export waits, titled *Recompute
  Run 4's fields first*; the run table CSV works. Compare shows the inputs that differ and the values
  table with the modes listed by number (*Modes of A and B listed by mode number, not matched by
  overlap*), and *Run 4's fields are not kept, so its modes are listed by number and not plotted.*
  with the button; the plots and Δn_eff by overlap come back once both runs have fields. *No need to
  run* for such a run reads *No need to run: Run 4 already has these values; its fields are not kept.
  Run study adds a copy with the same values.* with **Show Run 4** and **Recompute Run 4's fields**.
- **Recompute Run N's fields** sends the document the run was computed with, built from its stored
  inputs and settings as **Use this run's inputs** sets them (Modes to find, the group index with its
  step, the outer boundary, Search near n_eff), to the same validation and run requests. It is not a
  new run: it takes no number, enters no list and leaves the current inputs, Undo and the selected
  run as they are; the job panel reads *Recomputing Run 4's fields · about 2 min* and **Stop waiting**
  works as for a run. Every value the run stores is compared with the recomputed result, each to 1e-12
  relative (1e-15 absolute below 1e-3). On a match the field is attached to the same run, with its
  job, number, name, pin, time and origin: *Run 4's fields recomputed from its stored inputs; its
  values match.*, and the order above applies, since a field has arrived. Otherwise nothing changes:
  *Run 4's fields were not recomputed: mode 1 n_eff came out 2.439316630, stored 2.439316632. Run 4 is
  unchanged. Use this run's inputs and Run study to make a new run.* (with *(stored by Studio 0.9.3;
  this is 0.9.4)* after the values when the versions differ). A document the server now refuses says
  *Run 4's fields cannot be recomputed:* and the server's words. A recompute matches on the same build
  and the same thread setting: the solves are bitwise reproducible then (measured: single-threaded,
  and default threads against default threads). A run computed with a different number of threads
  may not match (an open run differed by up to 5e-11 between one thread and four); Studio then leaves
  it unchanged.
- **Where the tab holds more than a file.** Two cases, each reported by Save and recovery with the
  question, the refusal and the recovery rules of [version 9](#optical-session-files-version-9):
  the selected run alone over the budget (an 8-mode open run can come close), whose field the tab
  keeps while it is selected; and a session grown by more than the 16 KiB kept for the inputs since
  the last arrival. The inputs are bounded (8 optical shapes, 8 Joule shapes, 6 materials), so the
  second is rare; the next arrival chooses the fields within the budget again.
- **Measured** (2026-11-25, `tools/studio_run_retention.mjs`): 20 results of the T18 mix (closed 2
  modes, closed 4 modes, closed near 2.46, open with n_g; Run 2 pinned) keep 4 fields as text; the
  session is at most 16.6 MB after every result, and the 20 records without fields are 0.15 MB. With
  [compact fields](#compact-fields-single-precision) the same 20 results keep 11 fields (Runs 2 and
  11–20).

The checks are `tests/simcase/studio_run_retention_fields.cjs` (the order, the words, a seeded
sequence of 2000 steps for the numbers, the tab against the file and recovery, and the two cases
above), `tests/simcase/studio_run_retention_recompute.cjs`, the tool's `k1` and `k5` commands, and the
RT stage (run retention) of `tools/studio_browser/studio_workspace_browser.mjs`.

### Compact fields (single precision)

Since the design *Compact field encoding* (round 25 A1) a field can be kept at single precision, so
that more fields fit the [16.8 MB budget](#keeping-runs-values-and-fields).

- **Only when needed.** While every field of the tab fits as text, nothing changes: the files are
  written as before. At the first arrival whose fields would not all fit as text (a result, a
  recomputed field, Add runs from file, or **Keep Run N, drop … instead** bringing a run back), every
  field in the tab is kept at single precision, and the order of run retention applies with the
  smaller sizes. Messages says nothing of it (round 27, D1; rounds 25 and 26 wrote a sentence there):
  the note under the run list and the line under a compact run's field view say it where it applies.
  Files saved from then on are optical session version 14, which an earlier Studio refuses by name.
  From then on every field that arrives is kept the
  same way; the tab never converts back. File › Open and Restore keep a file's fields as the file
  holds them unless they would not all fit as text, so a file opened and saved again unchanged is its
  own bytes.
- **What changes.** The field samples are rounded to float32 (about 7 significant digits; at most
  2^-24 relative, about 6e-8). The node coordinates and triangles are kept exactly, so the window, the
  crop and the physical window are unchanged. n_eff, the TE fractions, the effective areas, n_g and an
  open run's candidates are the values the run showed before, stored with it. The field view, the
  probe, the profile, Compare and the PNG exports read the float32 samples, so a restore or an opened
  file shows exactly what the tab showed. Measured on the T18 results: TE fractions and areas
  computed from a compact field differ by at most 7e-9 relative, the normalized field view by 6e-8,
  and the probe's 6-digit text differs by one unit in its last digit for about 1 % of triangles.
- **Words.** Results, under the field view of a compact run: *Field at single precision (float32).
  The values above are the engine's.* Export this run: *… with the run's inputs and fields (fields at
  single precision) …*, a version 14 file. The note under the run list adds *When fields would not
  all fit, they are kept at single precision.* once the tab holds a compact field. The profile CSV
  keeps its header and columns; relative_amplitude [1] holds the float32 sample, normalized.
- **A field single precision cannot hold** (a sample beyond ±3.4e38, or a nonzero sample that would
  become 0 or a subnormal below 1.2e-38) stays as text. Engine fields are normalized to at most 1, so
  only a synthetic or edited file holds one.
- **Full precision.** Once the tab is compact it holds no float64 field. **Recompute Run N's fields**
  brings back a field that was let go, checks every value to 1e-12 and stores it at single precision
  like the others. For float64 samples, use **Use this run's inputs**, then Export solver JSON, and
  run the document with simcase.
- **Limitation.** For a run first opened from a version 6 or 7 file, the stored TE fractions and
  effective areas were computed by Studio from that file's field; after saving, Studio labels them as
  stored values. A run whose TE fractions or effective areas come out not a number (only a synthetic
  file holds one, such as the runs of the project fixture `project-v1.json`) leaves the tab without a
  field budget, as before compact fields: its fields stay as they are.
- **Sizes** (2026-11-25, T18 strip over a silicon substrate, core mesh 30 nm; text → single
  precision): closed, 2 modes 2.25 → 1.02 MB; closed, 4 modes 4.10 → 1.74 MB; closed near 2.46, 4
  modes 4.08 → 1.74 MB; open, 2 modes (with or without n_g) 3.92 → 1.11 MB (6,263 nodes, 12,253
  triangles). A compact field's size follows from its counts: 32·k·T + 4⌈16N/3⌉ + 4⌈12T/3⌉ characters
  and its keys (k modes, N nodes, T triangles). The conversion of a tab of six T18 fields (16.6 MB as
  text) took 112 ms in Node, and of a tab of 11 fields (13.6 MB as text) 68 ms in Chrome. In the
  browser the field view, the line profile and the field PNG of three closed T18 runs were the same
  before and after the conversion, but for 4 pixels by one colour level in one view of 31. Deflate was measured and is not used: 1.05× on open fields, up to 2.8×
  on the closed fields' imaginary parts (half of a closed field's samples are exact zeros).

The checks are `tests/simcase/studio_field_encoding_format.cjs` (the format, F1, F3, F4 and F10),
`tests/simcase/studio_field_encoding_tab.cjs` (F2: no conversion while the fields fit, the same texts as
main 499a0d3; F11: a seeded sequence of 2000 steps with the conversion; F6 and F8: what Studio computes
from a compact field), `tests/simcase/test_studio_field_encoding.py` (F5: the same strings as NumPy),
and `tools/studio_field_encoding.mjs` (`f9`, `f14`, `f16`, `sizes`).

### Compact maps (single precision)

Since the design *Session versions 16 and 17* (S3) a heated run's maps can be kept compact, as
[compact fields](#compact-fields-single-precision) are, so that more maps fit the 16.8 MB budget of
[the heated model's run retention](#session-files-of-multiphysics-models-version-15).

- **Only when needed.** While every map of the tab fits as text, nothing changes: the files are
  version 8 or 15, byte for byte. At the first arrival whose maps would not all fit as text (a result,
  a recompute, Open, Restore, **Keep Run N's maps** bringing maps back), every map in the tab is made
  compact in place, then the order of run retention applies with the smaller sizes; from then on
  every map that arrives is compact, and the tab never converts back. Open and Restore keep a file's
  maps as it holds them unless they would not all fit as text. Messages says nothing of it; the files
  from then on are [version 17](#session-files-of-multiphysics-models-version-17).
- **What changes.** Node temperatures and the index maps read back as float32 offsets from float64
  bases: within 2⁻²⁴ of the heat range or of the region's spread (measured: under 1 µK and 7.3·10⁻¹²).
  The coupled temperature drawn is the mean of each triangle's 3 decoded node temperatures. n_eff, the
  heat range (*Minimum T*, *Maximum T*), the coupling check and the iteration history are the
  server's values, unchanged. On the four measured models the map legends and accessible names are the
  same, no colour of the heat, n and Δn maps changes, and on the core temperature map, which spans only
  0.03 K, 0.27 to 2.3 % of the core's triangles change by one colour level of 255.
- **Words.** Under the maps of a run whose maps are compact: *Maps at single precision (float32). The
  values above are the engine's.* The note under the run list adds *When maps would not all fit, they
  are kept at single precision.* once the tab holds compact maps. *If you run: …* counts the compact
  sizes the next arrival will use.
- **Maps that stay text:** more than 256 region names, a value beyond float32 after its offset, or a
  coupled map without the node temperatures of its coupling's source.
- **Measured** (2026-11-26, `node tools/studio_heated_retention.mjs hq6`, 20 results of each model):
  maps per run compact 0.14 MB for the template (text 0.37 MB), 0.56 MB at 0.12 µm (1.49 MB), 1.03 MB
  at 0.08 µm (2.79 MB) and 0.95 MB for the slab (2.53 MB); the budget keeps 20 template runs (no
  conversion), 20 at 0.12 µm (converted at result 12), 15 at 0.08 µm (at 6) and 17 of the slab (at 7).
  20 of 20 for the finer meshes would take runs that share one stored mesh (coordinates and triangles
  are two thirds of a compact run), which is not part of this design.

The checks are `tests/simcase/studio_heated_compact_tab.cjs` (the tab rule, the maps that stay text,
the estimate, the words, a seeded sequence of 600 steps) and, on engine results,
`tests/simcase/studio_heated_retention_engine.cjs` (HQ5 the Results page, HQ6 the counts; `hq5` and
`hq6` of `tools/studio_heated_retention.mjs`).

### Optical session files (version 13)

Version 13 is [version 12](#optical-session-files-version-12) with up to 20 runs: the same run
records (`number` after `job`, the same keys, the same digest) and top-level keys. Versions 6 to 12
hold at most six runs.

- **When it is written.** Only when the session has more than six runs. A session of six runs or
  fewer is written as version 12, 11, 10, 9 or 7, byte for byte as before, so an earlier Studio still
  reads it. A version 13 file of six runs or fewer (edited by hand) is read.
- **Reading.** File › Open, Open project, Restore and Add runs from file read up to 20 runs; a file
  of 21 runs, or a version 12 file of seven, is refused with *Unsupported session format or run
  count.* The number checks are those of version 12.
- **Earlier Studios.** A Studio that reads up to version 12 (main 3f16709) refuses a version 13 file
  by name before it counts the runs: *This session file is version 13, newer than this Studio reads
  (versions 6–12). Open it in a newer Studio.*, after *Optical waveguide: * for a project file's
  entry, and does not take over a browser-recovery record that holds one. To share runs with such a
  Studio, export at most six of them (Export this run, or a session of six). The project file stays
  version 1; the optical documents, adapters, results, the multiphysics session (version 8) and the
  run table CSV are unchanged.

The checks are `tests/simcase/studio_run_retention_format.cjs` (K2: every earlier fixture written
again byte for byte; K3: the fixture `optical-v13-nine-runs.json` of runs 2 and 4 to 11; K4: what main
3f16709 reads, `refusals-v13-3f16709.json`).

### Optical session files (version 14)

Version 14 is [version 13](#optical-session-files-version-13) whose runs may hold a compact field
([compact fields](#compact-fields-single-precision)): the same top-level keys, 0 to 20 runs, the run
records of version 13 and the same digest. A field is either version 13's nested numbers or a compact
field, with these keys in this order and no other:

```json
"field": {
  "encoding": "f32-base64-v1",
  "counts": {"modes": 2, "nodes": 6263, "triangles": 12253},
  "node_coordinates": "<base64: nodes × 2 float64, little-endian, metres>",
  "triangles": "<base64: triangles × 3 uint32, little-endian>",
  "real": "<base64: modes × triangles × 3 float32, little-endian>",
  "imag": "<base64: the same for the imaginary parts>"
}
```

- **Layout.** Each array is today's nesting flattened: mode, then triangle, then x, y, z; node, then
  x, y; triangle, then its three indices. Base64 is RFC 4648's standard alphabet, padded, without line
  breaks. NumPy's `astype('<f4')`, `'<f8'` and `'<u4'` with the standard library's base64 write the
  same strings.
- **Stored values.** A run with a compact field also stores its TE fractions and effective areas.
- **When it is written.** Only when a run is kept with a compact field; otherwise version 13, 12, 11,
  10, 9 or 7, byte for byte. A version 14 file without a compact field is read. A compact field is
  written again from the strings it was read from, so a version 14 file read and written again is its
  own bytes.
- **Refusals,** each naming the run: *Run 5's field is encoded as "…", which this Studio does not
  read.*; *Run 5's compact field must hold encoding, counts, node_coordinates, triangles, real, imag
  in this order, and nothing else.*; *Run 5's compact field counts must be whole numbers: modes 1 to 8,
  nodes 3 to 250000, triangles 1 to 500000.*; *Run 5's compact field holds 1 modes; the run has 2.*;
  *Run 5's compact field real is not canonical base64.*; *Run 5's compact field triangles holds 36
  bytes; its counts give 24.*; *Run 5's compact field imag holds a value that is not a finite
  number.*; *Run 5's compact field triangle 2 names node 5, outside 0–4.*; *Run 5's compact field
  triangle 1 repeats a node.*; *Run 5 has a compact field and no saved TE fractions and effective
  areas.*; and in a file of version 13 or earlier *Run 3: a compact field is read from a version 14
  session file only.* The decoded field then passes every check of a field of nested numbers.
- **Earlier Studios.** A Studio that reads up to version 13 (main 499a0d3) refuses a version 14 file
  by name: *This session file is version 14, newer than this Studio reads (versions 6–13). Open it in
  a newer Studio.*, after *Optical waveguide: * for a project file's entry, and does not take over a
  browser-recovery record that holds one. The project file stays version 1 (its optical entry reads
  version 14); the recovery record stays version 1; the optical documents, adapters, server replies,
  results and the multiphysics session (version 8) are unchanged.

### Optical session files (version 16)

Version 16 is [version 14](#optical-session-files-version-14) whose open-boundary runs may hold their
time (design "Session versions 16 and 17", amendment A1): the same top-level keys, 0 to 20 runs, run
numbers and compact fields. A run record has the keys of version 14 with two more before `digest`,
both optional and inside the run's digest:

```json
"duration": 61552,
"timings": {"mesh": 2.24, "solve": 57.352},
```

- **`duration`** is the wall time in the tab, from the job's start to its result read, in whole
  milliseconds: the time the [Compute label](#first-optical-study) already showed beside Run study. It is
  kept only for a job the tab followed from its start to its result; a job followed again with
  **Resume** (after Stop waiting or a reload) has none, since its time would hold the time the tab
  was detached.
- **`timings`** is the server's compute time of the result, `{mesh, solve}` in seconds rounded to
  0.001 s, exactly as the result names it; a resumed run keeps it.
- **Where the time is used.** A run's time is its `duration`, else `mesh + solve`. The Compute
  label's *last such run m:ss*, the estimate with group index on (*about N min*) and *Recompute Run
  N's fields · about …* use it, so after File › Open, Open project and Restore they read as in the
  tab that computed the runs. Measured on 2026-11-26 (this repository's container, single threaded,
  a Node client that follows a job as the page does): the T18 open run took 61.6 s (timings 2.24 +
  57.35 s) and with group index 179.2 s (2.235 + 175.21 s): the estimate *about 3 min* (3 × 61.6 s =
  184.7 s, 3.0 % above). Wall time includes polling and the result download (1 to 2 s on these runs);
  a background tab or a sleeping machine can lengthen it, and it is stored as measured.
- **Only open runs.** A closed run never holds either key in a file (its wall time stays in the tab,
  as before), so version 16 is written only when a session holds an open run computed by this Studio;
  otherwise version 14, 13, 12, 11, 10, 9 or 7, byte for byte. A file of an earlier version with a
  new closed run keeps its version; with a new open run it is version 16, and its older run records
  and digests are unchanged.
- **Refusals.** *Run 5: invalid run time.* for a `duration` that is not a whole number of 1 ms to 7
  days, `timings` other than exactly `mesh` then `solve`, each a number of 0 to 604,800 s, or either
  key on a closed run; an edited time without a new digest is refused as *Run 3 changed after it was
  saved (its check value does not match).*; in a file of version 14 or earlier the keys are unknown
  (*Run 2: unknown key "duration".*).
- **Earlier Studios.** A Studio that reads up to version 15 (main c0dbc09) refuses a version 16 file
  by name: *This session file is version 16, newer than this Studio reads (versions 6–15). Open it in
  a newer Studio.*, after *Optical waveguide: * for a project file's entry, and does not take over a
  browser-recovery record that holds one (`refusals-v16-c0dbc09.json`). Session files holding
  open-boundary runs saved by this Studio therefore need this Studio or later. The project file and
  the recovery record stay version 1; the optical documents, adapters and server replies are
  unchanged.
- **Checks.** `tests/simcase/studio_run_time_format.cjs` (RT1 to RT7 and T18-G1, with the fixture
  `optical-v16-times.json` of real runs) and the T18-G1 stage of the workspace browser check (File ›
  Open of that file, then Restore).

### Matching modes in Compare

Compare matches the modes of runs A and B by their fields, so a row pairs the same mode even
when the ranks change between designs (for example a wider core whose second TE-like mode
overtakes the TM-like one). Matching is on for two closed runs (with an open run it is off:
[open boundary](#open-boundary-in-the-optical-workspace)), and the ranks stay in every row.

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
  the absorption loss of A and of B (*Loss A (dB/cm)*, *Loss B (dB/cm)*,
  on matched and unmatched rows: the modes table's value from the saved indices, *mean* of the
  members' dB/cm for a matched pair; optical runs read *0 dB/cm*, as the optical adapter's
  materials are lossless), then *n_g A* and *n_g B* (the modes table's value, *mean* of the
  members' values for a matched pair, **—** with the modes table's help when a run has none). The
  headers are short and grouped: *Polarization*, *n_eff*, *A_eff (µm²)*, *Loss (dB/cm)*
  and *n_g* each over an **A** and a **B** column, *Modes*, *Overlap*, *Δn_eff (B − A)* and *Δ % (of
  A)* over one; a line above the table names run A and run B. Each Polarization cell has two lines,
  the class and then the share (*TE-like* / *98.2 % TE*). At 1440 × 900 every column fits the table's
  box. Where the box is narrower (a phone), the first column stays in view while the others scroll
  sideways inside the box: a shadow at its right edge and the line *Scroll sideways for all 14
  columns ›* show that more columns are hidden. The page does not scroll sideways. A mode
  without a match is headed *1 ↔ —* or *— ↔ 2*, with the full *A mode 2: no match in B (best
  overlap 0.43, with B mode 2)* as its title and accessible name, shows its best overlap in the
  Overlap column on two lines, *best 0.43 (< 0.8, not matched)* (round 17; *(margin < 0.1, not
  matched)* when the best was at least 0.8 but not 0.1 above the next best; the rule itself is
  unchanged), and shows no Δn_eff; the unmatched modes of B follow. Below the table: “Matched by field overlap ≥
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

The job panel shows the submitted dimensions/material, job ID, elapsed time (m:ss), what the
run solves and the result-loading state, for example *Computing job 1a2b3c4d · 12:40 · Open
boundary · 2 modes · searches near 2.46 and 1.95 · PML check (up to 2 more solves)* or *PML check ·
mode 1 of 2*. While an optical job computes, the text then names the step the server reports
(round 25, A5): the solve and the search the engine is at, from the latest `search_started` event of
`simcase.run`'s `on_event` (`step` of `GET /api/jobs/{id}`, see the
[HTTP API](overview.md#the-http-api)), right after the time, for example *Computing job 1a2b3c4d · 1:52 ·
solve 2 of 3 (group index) · search 1 of 2 · Open boundary · 2 modes · searches near 2.46 and 1.95*.
The time and the step are never cut; what the run solves is cut with an ellipsis when the panel is
short of room. Where the time and the longest step cannot share the tab's line (below 661 px, and
from 1001 to 1279 px, where the side panes stand beside the view), the job panel takes a line of its
own below the view's title while it names a step and wraps between its parts, so the tab grows
taller only while a job runs. The words are
*solve s of S* when the run has more than one solve (the group index adds solves 2 and 3, *(group
index)*), *search k of K* when each solve has more than one search (an open boundary's second
search), both when both hold, and none for a job of one step in all (a closed run without the group
index, an open run of one search, a PML check job) or a server that reports no step. A Recompute
job reads *Recomputing Run 4's fields · about 3 min · solve 2 of 3 (group index) · search 1 of 2*.
The words count steps, not time: the searches of a solve take different times (on 2026-11-25 a
T16-like open run with the group index took 207.9 s, searches of 40 s and 26 s), so no percent is
shown. The time estimate stays on the run-plan line (*about 3 min*, round 24 B5). Messages repeats
each of these states and is the one live region that announces them; the job panel's text is not a
live region, so a screen reader reads each state once (round 25, A6; before, both announced every
update). While a job computes, Messages carries the job panel's words without the time
(*Computing job 1a2b3c4d · Open boundary · … · solve 2 of 3 (group index) · search 1 of 2*, and
*· no answer from the server; still checking* while the server does not answer) and is written only
when they change: a screen reader hears the start, each step, a silence and its end, and the job's
end, never the time (before round 25, A5, the time changed the live text about once a second). **Stop waiting** stops browser polling only; the optical
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
While the server answers that the job is running, Studio keeps waiting, however long the
job takes (an open-boundary solve can take a quarter of an hour on a busy machine). Only when
the server stops answering, a status request failing for three minutes, does the panel say
*The server has not answered for three minutes. Resume to check this job again.*; a failed
request is tried again every 0.7 s until then, and the panel adds how long the server has not
answered. Failed requests do not
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
the runs, and the session file once one does. Since round 17 an unavailable recovery says why and
what to do when the reason is known: *browser recovery unavailable: session over 16 MiB · File ›
Save keeps your work* when the selected and pinned runs with their fields are over 16 MiB (two
pinned open runs of a strip over a substrate were, at 13.4 MB each, before an open run kept its
physical window only; now such a run is 3.9 MB), and *browser recovery
unavailable: this browser’s storage is full · File › Save keeps your work* when the browser refuses
the write for space. Since round 18, Messages says it too, once each time recovery turns off: *Browser
recovery is off: this session is over 16 MiB. File › Save keeps your work.* or *Browser recovery is
off: this browser’s storage is full. File › Save keeps your work.* (after a run's result message, on
the same line). An empty new tab does not erase the prior notebook.

After reload, choose the session on the start page's **Continue where you left off** box (one
button per piece of work, the older copies under **Earlier copies in this browser (N)**; a model
card only says *Kept in this browser · N runs · Restore at the top of the page*), or under
Workspace tools → **Restore last session from this browser**.
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

Since [session version 12](#optical-session-files-version-12) the record of either model also
keeps the project's name when the tab's project has one, as an optional browser-only key
`project: {name, from}` (`name` by the project-name rules; `from` is `file` for a name taken from
a file name, `user` for one set with Rename). It is left out for an untitled project, a malformed
one is ignored, and the record stays version 1 (earlier Studios ignore the key). A restore uses it
when the record names no project file (`savedFile.projectName`, which wins when both are present):
the project takes the name, with no project file, so File › Save suggests the name's file
(`both-models.json`) and asks. Until the next change the header reads *both-models · recovered from
this browser · not saved to a file · kept for recovery in this browser* when the record was opened
from no file, *both-models · recovered from this browser · changed since both-models.json, not saved ·
kept for recovery in this browser* when it no longer matched the project file it was opened from
(round 23, E5, HQ decision 2026-11-24-openphysics-studio-round23-choices: it read *not saved to a
file* there, as if no file had held the project), or *both-models ·
recovered from this browser · as opened from both-models.json · kept for recovery in this browser*
when the record still matched the project file it was opened from; a record that names its
project file reads as before (*… · both-models.json · saved …*), and an older record without a name
as before (*Untitled project · …*). After the next change, a project whose record came from a file
(matched or not) keeps naming it in every recovery state: *both-models · changed since
both-models.json, not saved · updating browser recovery*, *… · kept for recovery in this browser*
or *… · kept for recovery in this browser without the fields of Run 6* (round 24, B2: it read *not
saved to a file*, beside the status bar's *Changed since session file both-models.json*). A record of
no file gives the ordinary header (*both-models · not saved to a file · …*), and a project with a
project file of its own keeps its words (*… · both-models.json · changed since opened · …*). A pair restore whose records name different projects
takes the newer record's name, with no extra message.

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
Review the number of new, matching and replaced unpinned runs before applying. The added runs are
numbered after the tab's largest run number, in file order; when a number changes the message
says so (*Added Run 2 and Run 4 of design-b.json as Run 9 and Run 10.*), and a job already in the
tab keeps the tab's number ([version 12](#optical-session-files-version-12)).
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
