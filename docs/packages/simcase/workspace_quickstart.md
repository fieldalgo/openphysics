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
(on macOS also `brew install python@3.12`). The version check comes first because an
older Python would quietly install the empty `0.0.1` package instead.

Linux and macOS:

```sh
python3.12 -c "import sys; assert sys.version_info >= (3, 12), sys.version"
python3.12 -m venv ~/op-studio
~/op-studio/bin/python -m pip install --find-links ~/wheelhouse "openphysics[studio]==0.0.2"
~/op-studio/bin/simcase-studio --help
```

Windows (PowerShell; these lines call the environment's programs directly, so no
activation script or execution policy change is needed):

```powershell
py -3.12 -c "import sys; assert sys.version_info >= (3, 12), sys.version"
py -3.12 -m venv "$HOME\op-studio"
& "$HOME\op-studio\Scripts\python.exe" -m pip install --find-links "$HOME\wheelhouse" "openphysics[studio]==0.0.2"
& "$HOME\op-studio\Scripts\simcase-studio.exe" --help
```

If `--help` prints the Studio options, the installation is complete.

## 3. Start and stop Studio

```sh
~/op-studio/bin/simcase-studio --workspace                # Linux, macOS
```

```powershell
& "$HOME\op-studio\Scripts\simcase-studio.exe" --workspace  # Windows
```

The browser opens `http://127.0.0.1:8765/workspace`. Use a current Chrome or Edge.
Keep the terminal open while you work; press **Ctrl+C** in it to stop Studio.

- Always open the same address. Browser recovery belongs to the exact address:
  `localhost` instead of `127.0.0.1`, or another port, starts with no recovery.
- Before starting again, wait until the terminal shows its prompt. If Studio is still
  running on the port, the second start exits and the browser shows the old server.

## 4. Two designs and a comparison

1. On **Choose a starting model**, select **Optical waveguide**.
2. In **Geometry**, set the core width to 600 nm and the height to 300 nm. The
   material is silicon and the wavelength 1550 nm (change it in **Optical modes**).
3. Select **Run optical study**. The result shows the field and the effective index
   of two candidates. Name the run and select **Pin selected run**.
4. Back in **Geometry**, set the width to 700 nm and run again.
5. Open **Compare**. Runs A and B are chosen for you; the comparison shows the
   difference in effective index. Candidate ranks are not matched modes.

## 5. Keep your work

- **Save session** (the first save button) writes one file with the inputs, all
  completed runs, their names and pins, and the comparison. Use it before you stop.
  **Save inputs only** keeps the model without results.
- After a reload or a restart, the start page shows **Continue where you left off**.
  Recover the last session, an earlier one, or open a session file.
- If you restart Studio while the page is open, the page reconnects by itself. Select
  Run again if it asks you to.

## Tested platforms

Checked on Linux (Python 3.12.3, headless Chromium) on 2026-11-08 with 0.0.2 wheels
built from the repository: the pinned install in a new environment (14 s with downloads
already cached), steps 4 and 5, **Ctrl+C**, a restart and recovery from the start
page, which restored the comparison unchanged. **macOS and Windows are not verified
for these steps yet**; earlier Windows checks are listed in the
[acceptance checklist](workspace_acceptance.md).
