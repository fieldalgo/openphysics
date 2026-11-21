# Workspace quick start

**English** | [한국어](../../locales/ko/pages/packages/simcase/workspace_quickstart.md)

Install the Studio workspace, design two silicon waveguides, compare them and keep
the work across a restart. The [workspace guide](workspace.md) is the full reference.

OpenPhysics 0.0.2 is not on PyPI yet (only empty `0.0.1` name reservations are), so
you install from a folder of wheel files built from the repository (a *wheelhouse*).
Third-party packages such as NumPy and FastAPI still come from PyPI, so the computer
needs internet access during installation.

## 1. Get a wheelhouse

Someone with the repository builds it once, at the commit you are asked to use:

```sh
git clone https://github.com/fieldalgo/openphysics.git
cd openphysics
git checkout <commit>
python3.12 -m venv ../op-build
../op-build/bin/python -m pip wheel --no-deps -w ../wheelhouse packages/galerkin packages/meshine packages/physmat packages/simcase packages/gmshio packages/galerkin-refsol packages/sipi packages/openphysics
```

Copy the `wheelhouse` folder to your home folder.

## 2. Install

You need Python 3.12 or newer from [python.org](https://www.python.org/downloads/)
(on macOS also `brew install python@3.12`). The version check comes first so that an
older Python stops with a clear message; pip would refuse the pinned version on it.

Linux and macOS:

```sh
python3.12 -c "import sys; assert sys.version_info >= (3, 12), sys.version"
python3.12 -m venv ~/op-studio
~/op-studio/bin/python -m pip install --find-links ~/wheelhouse "openphysics==0.0.2"
~/op-studio/bin/openphysics --help
```

Windows (PowerShell; these lines call the environment's programs directly, so no
activation script or execution policy change is needed):

```powershell
py -3.12 -c "import sys; assert sys.version_info >= (3, 12), sys.version"
py -3.12 -m venv "$HOME\op-studio"
& "$HOME\op-studio\Scripts\python.exe" -m pip install --find-links "$HOME\wheelhouse" "openphysics==0.0.2"
& "$HOME\op-studio\Scripts\openphysics.exe" --help
```

If `--help` prints the Studio options, the installation is complete.

## 3. Start and stop Studio

```sh
~/op-studio/bin/openphysics                # Linux, macOS
```

```powershell
& "$HOME\op-studio\Scripts\openphysics.exe"  # Windows
```

The browser opens `http://127.0.0.1:8765/workspace`. Use a current Chrome or Edge.
Keep the terminal open while you work; press **Ctrl+C** in it to stop Studio.

- Always open the same address. Browser recovery belongs to the exact address:
  `localhost` instead of `127.0.0.1`, or another port, starts with no recovery.
- Before starting again, wait until the terminal shows its prompt. If Studio is still
  running on the port, the second start exits and the browser shows the old server.

## 4. Two designs and a comparison

1. On **Choose a starting model**, select **Optical waveguide**. Until you choose one,
   the title reads *No model chosen*, the status bar *Choose an application to start*
   and the Study sequence is empty.
2. In **Geometry**, set the core width to 600 nm and the height to 300 nm. A Width edit
   keeps the core centred (Left x becomes −300 nm) and a Height edit keeps its bottom
   on y = 0, so no **Centre on x = 0** is needed. The material is silicon and the
   wavelength 1550 nm; the step bar shows it as *4. Study · λ 1550 nm · Ready to run*
   (**Study → Edit wavelength** opens **Optical modes** with the field focused).
3. Select **Run optical study**. The result shows the field and the effective index
   of two candidates, and the Study step reads *Run complete*. Type a **Run name**, for
   example *design A*, and press Enter: a named run is pinned, so new runs do not
   replace it.
4. Back in **Geometry**, set the width to 700 nm and run again.
5. Open **Compare**. Runs A and B are chosen for you; a table lists n_eff of A and B,
   Δ (B − A) and Δ % of A for each candidate rank, with each run's name, size and
   wavelength in its column header. Candidate ranks are not matched modes.

## 5. Keep your work

- **Save session** in the ribbon's Project group writes one file with the inputs,
  all completed runs, their names and pins, and the comparison. Use it before you stop.
  The file is named after the application and the local time, for example
  `optical-waveguide-session-2026-11-21-1305.json`, and is handed to your browser's
  downloads (the browser may ask where to save it, or add a number if that name exists).
  Messages reports *Session file … sent to the browser's downloads (check your Downloads
  folder)* and the title shows *Session file … · time* until your next edit or run.
  **More → Save inputs only** keeps the model without results; **Export this run** in
  the Runs list writes one run to its own file.
- After a reload or a restart, the start page shows **Continue where you left off**.
  Recover the last session, an earlier one, or open a session file. On a fresh page
  (default inputs, no runs) it opens at once; otherwise **Open saved session?** lists the
  runs and the comparison that come back and what is replaced. Messages names what was
  opened. The title then reads *Opened …* with the file name, or *Recovered from this
  browser* (with *last session file …* when one was saved), until your next change.
- If you restart Studio while the page is open, the page reconnects by itself. Select
  Run again if it asks you to.
- Input and session files are version 7 (the Joule heating inputs added); version 6 files are
  still read. Files saved by a Studio from before the units
  and naming batch (versions 1 to 5) are refused with a message that names their version,
  and a browser draft from that Studio is not offered: enter the design again and save it.

## Tested platforms

Checked on Linux (Python 3.12.3, headless Chromium) on 2026-11-08 with 0.0.2 wheels
built from the repository: the plain `openphysics==0.0.2` install in a new environment
(15 s with downloads already cached), `openphysics --help`, the `openphysics` command
serving the workspace page, steps 4 and 5, **Ctrl+C**, a restart and recovery from the
start page, which restored the comparison unchanged. **macOS and Windows are not verified
for these steps yet**; earlier Windows checks are listed in the
[acceptance checklist](workspace_acceptance.md). On 2026-11-10, after the units and naming
batch moved the file versions and the capability check to version 6, steps 4 and 5, a restart
and the recovery were checked again on Linux with
`tools/studio_browser/studio_workspace_browser.mjs` against an installed simcase wheel
(headless Chrome), not through the `openphysics` installation above. On 2026-11-16, with the
files and the capability check at version 7, the same script passed on Linux against the source
tree (headless Chromium, Python 3.13), not an installed wheel. On 2026-11-20, with the
workbench layout (ribbon, Settings beside the model builder, study dock), it passed again on
Linux against an editable install of the source tree (headless Chromium, Python 3.12).
