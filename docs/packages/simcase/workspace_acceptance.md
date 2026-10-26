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

## Release decision

Retain each task's actual outcome, time, interventions and failure reason.
Agent-operated browser checks do not replace sessions with first-time users.
Do not mark the workspace production-ready until required CI, packaging,
platform/accessibility checks and the agreed user pilot have been reviewed.
General CAD editing and electric → heat → mechanics → optical coupling remain
separate development work; this checklist does not certify their availability.
