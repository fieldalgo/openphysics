# Workspace acceptance checklist

**English** | [한국어](../../locales/ko/pages/packages/simcase/workspace_acceptance.md)

Use this checklist with the [workspace guide](workspace.md) when reviewing a
build. Record the commit, wheel hash, OS, Python, browser, commands, outcomes and
failures. A source test pass, an installed-package check and a real browser task
are different evidence. Do not substitute one for another.

## Automated checks

From the repository root, in the configured development environment:

```bash
node --test tests/simcase/*.cjs
python -m pytest -q tests/simcase/test_studio_workspace.py
python tools/check_markdown_links.py
```

Run all `test_studio*.py` modules when changing shared Studio behavior. Follow the
[development guide](../../development.md) for complete CI and distribution checks.
For distribution acceptance, verify that `simcase.__file__` points into the test
installation, serve the installed assets, and record which engine dependencies
are installed or supplied from source. A test with source engine packages does
not establish an independent installation of the whole stack.

## Browser tasks

Start `simcase-studio --workspace` on an unused local port. Use a separate browser
profile or test origin for a fresh-user check; preserve existing sessions first.
The initial Applications page must make live optical calculation and setup-only
coupled physics distinguishable.

| Task | Expected observation |
|---|---|
| Choose Optical waveguide; set 600 × 300 nm and Silicon | Geometry and Study agree; no calculation starts during editing. |
| Enter an out-of-range dimension, then navigate away and back | Invalid draft remains visible; Run is blocked; accepted model is preserved. Correcting it restores readiness. |
| Generate Mesh; change width to 700 nm | Preview belongs to earlier inputs until explicitly regenerated; no silent solve. |
| Check inputs, then change the model | Check report identifies its captured input and becomes stale. Run validates a fresh snapshot. |
| Run at 600 × 300 nm; name and pin the result | Actual fields and two candidate indices appear with job, input and version provenance. |
| Run at 700 × 300 nm; Compare A/B | Captured dimensions and material are identifiable. Candidate ranks are explicitly not matched modes. |
| Add a 3000 × 90 nm silicon slab, draw it earlier than the core, add an air circle and a polygon | The list, drawing and draw order agree; an overlap note names the shape that wins. Out-of-window or crossing values stay as blocked drafts or are refused with the shape unchanged. |
| Drag the core, move it with arrow keys, drag a rectangle edge; Undo and Redo | Each completed gesture is one undoable edit; Escape cancels a preview. The numeric inspector follows every change. |
| Run the multi-shape design; generate its mesh; save and reopen the session; open a version-3 input file | Results, history and comparison name the shape summary; field outlines show every shape. Reopened shapes match. The version-3 file opens as one centred rectangle. |
| Run at 1600 nm / 40 nm core mesh, then 1400 nm / 25 nm; Compare | Results, history and comparison name each captured wavelength and core mesh. Values outside 1400–1700 nm or 20–60 nm stay as blocked drafts. |
| Change candidate/component; inspect a point and a line | Both plots use the same physical coordinates. Values are stored triangle samples with relative normalization, not interpolated absolute fields. |
| Save session and selected run; reopen each | Inputs, result count, names, pins, comparison and view state match the file's scope. File origin is shown; opening does not recompute. |
| Wait for Browser recovery saved; reload; Recover last session | Results and view state return as recovered. No solver starts; input Undo starts at the recovered document. |
| Open an empty session while a completed notebook save is queued | The queued recovery keeps its captured results; the empty session does not erase them. |
| Open a replacement dialog, then let an in-flight calculation complete | Confirming the stale review preserves the new result and asks for another review. |
| Save different names in two tabs of the same origin | The stale tab reports a recovery conflict; Retry and cancelling a recovery preview do not overwrite the newer record. |
| Use current notebook for recovery; cancel, then review and confirm | Cancel keeps the stored record. Confirm replaces only browser recovery, preserving the current model, results and Undo. |
| Change stored recovery in another tab while replacement review is open | Confirmation cannot overwrite the new revision; review again. |
| Stop waiting during a calculation, edit inputs, Resume | The captured job is retrieved without replacing current model inputs. Stop waiting does not cancel server computation. |
| Restart the test server while a job remains attached | The old server identity is rejected; Resume is disabled. Recover a notebook and navigate between pages: the job panel, Study step and footer still require Detach. Detaching preserves inputs and retained results and allows a new explicit Run. Preserve a portable session before this test. |
| Temporarily lose the connection while retrieving a job | Existing results remain visible; Resume retries retrieval of the same captured job after reconnecting. A missing job or a solver-reported failure instead requires Detach. |
| Import a saved run into an existing notebook | Review states additions/replacements; current inputs and input Undo remain. A conflicting payload leaves the whole notebook intact. |
| Pin all six retained runs | New Run is blocked; input checks and mesh preview remain available. Unpinning one restores capacity. |
| Select the heated-waveguide template | Setup and connection editing are available; coupled execution remains unavailable and no fabricated thermal/mechanical results appear. |

Check that the width slider exposes its purpose and unit, and each load/import/
recovery dialog exposes its title and description. Escape cancels a dialog and
returns focus to its opener without changing the model or stored recovery.

Also check keyboard selection, visible focus, panel dividers, long run names,
1280 × 800 and 1920 × 1080 layouts, and 200% zoom in every browser intended for
support. Record untested combinations explicitly. Keep numeric field validation,
undo and file recovery checks separate from visual inspection.

## Local observation, 2026-10-26

On Windows, an installed `2d9966e` simcase wheel was exercised in an embedded
desktop browser and completed two optical designs (600/700 nm width,
300 nm height), naming/pinning, comparison, probe/profile, portable save, reload
and browser recovery. Two retained runs and one pin were restored. Repeating
those captured documents through the Python API produced the same effective
indices in that environment. This checks transport/workflow consistency, not
independent physics accuracy or mesh/window convergence.

After the comparison-layout and launch-option updates, the final `c46970f`
package was built and checked separately. The layout was also inspected in the
source-backed browser; the complete fresh-user flow was not repeated on this
final wheel. Related source Studio Python checks passed (313); source Studio Node checks
passed (202). Installed workspace modules passed 73 Node checks and 12 HTTP/CLI
checks; installed workspace bytes matched the source. Other engine packages
were supplied from the worktree with existing dependencies. Full repository CI,
all-package independent installation, other operating systems/browsers, all
viewport/zoom combinations and a human usability pilot were not established by
this observation. No new third-party dependency was added.

## Recovery observation, 2026-10-27

On Windows, a separately installed `c8ac6d5` simcase wheel was checked after a
restart of its test server. The old job could not resume. Reloading and recovering
the notebook retained the unavailable-job guidance in the job panel, Study and
footer. Detaching the old job preserved the current 880 × 500 nm model and one
pinned 650 × 350 nm result, and enabled a new explicit Run. A preceding source
check stopped observation, edited inputs and resumed the same completed job;
its result retained the submitted inputs without replacing the edited model.

All six implementation packages came from wheels in the test environment;
third-party dependencies reused the existing system environment. This was not a
fresh installation of every dependency. The final installed static files matched
29 source files; 216 Studio JavaScript contracts and 12 workspace HTTP/CLI checks
passed outside the checkout. The earlier complete two-design task was not
repeated at this revision. Other browsers, viewport/zoom combinations and a human
usability pilot remain unverified by this observation.

## Clean installation observation, 2026-10-27

A fresh Windows Python 3.12.3 virtual environment with system site packages
disabled installed seven `ff0b2f6` wheels, built from sdists. Runtime and Studio
dependencies used the repository's existing portable/web pins; `pip check` and
the reviewed license inventory passed. Installed assets matched 29 source files,
and 216 JavaScript contracts plus 12 workspace HTTP/CLI checks passed outside the
checkout. These checks do not replace the full repository CI.

The installed `simcase-studio --workspace` entry point completed 600/700 × 300 nm
silicon designs in a fresh browser origin. Naming/pinning the baseline, comparison,
candidate/component changes, probe/profile, session download, reload/recovery
and reopening the downloaded file preserved two runs, one pin and the view state.
No browser console errors or warnings were observed. Repeating both captured
solver documents through the installed Python API gave identical effective
indices in this environment. This is same-stack transport consistency, not an
independent numerical reference or a new platform/browser support claim.

## Wavelength and mesh observation, 2026-10-26

Source checkout on Linux (Python 3.12, Chromium via Playwright, agent-operated).
An out-of-range 1300 nm draft blocked Run with the 1400–1700 nm hint. Runs at
1600 nm / 40 nm and 1400 nm / 25 nm on a 500 × 220 nm silicon core completed;
history labels and the comparison named both wavelengths and mesh sizes. The
saved session (version 3, about 0.8 MB) reopened in a new tab with both runs and
1400 nm restored. No browser console errors or warnings were observed. The
workspace solver documents for 300 × 220 and 500 × 220 nm silicon and 900 × 500 nm
silicon/silicon nitride cores completed at every corner of 1400/1700 nm and
20/60 nm through the local HTTP API (at most 1.5 s, at most 1.3 MB result
payload). Doubling the window changed the fundamental n_eff by at most 1.6e-3
at 1700 nm in these cases. Windows/macOS, other browsers and human users were not
part of this observation.

## Shape editing observation, 2026-10-27

Source checkout on Linux (Python 3.12, Chromium via Playwright, agent-operated).
Starting from the default core, the workspace added a rectangle, renamed it Slab,
set it to 3000 × 90 nm and moved it earlier than the core. A 4000 nm width stayed
as a blocked draft and Escape restored 3000 nm. Dragging the core, an arrow-key
move and a right-edge drag each produced one edit; an air circle and a polygon
were added, and crossing polygon vertices were refused with the shape unchanged.
Undo and Redo restored the polygon edit. The four-shape design ran (n_eff
2.686937), its mesh preview generated, and the saved version-4 session reopened in
a new tab with the same four shapes. A version-3 input file opened as one centred
650 × 300 nm silicon nitride rectangle. No browser console errors or warnings were
observed.

Through the local HTTP API, the documents generated by the workspace validated,
meshed and solved for a legacy 500 × 220 nm core, a Si/air/Si slot, a rib (slab
and ridge overlapping), a silicon nitride circle, a trapezoid, an air top
cladding, a shape touching the window edge and an eight-shape design (at 1550 nm,
30 nm core mesh, at most 2.2 s and 1.3 MB). Submitted as four corners, the legacy core gave
the same 2275-triangle mesh as the earlier rectangle document and n_eff within 2.5e-15. For the r = 600 nm silicon nitride circle, the two
candidates (1.82841 and 1.82821 at 30 nm; 1.82844 and 1.82827 at 20 nm) approach
the exact step-index HE11 value 1.828466 computed independently from the vector
eigenvalue equation; the PEC window splits the pair. The worst case tried, silicon
filling the window at 20 nm, took 22 s with a 14 MB result. Windows/macOS, other
browsers and human users were not part of this observation.

## Release decision

Retain each task's actual outcome, time, interventions and failure reason.
Agent-operated browser checks do not replace sessions with first-time users.
Do not mark the workspace production-ready until required CI, packaging,
platform/accessibility checks and the agreed user pilot have been reviewed.
General CAD editing and electric → heat → mechanics → optical coupling remain
separate development work; this checklist does not certify their availability.
