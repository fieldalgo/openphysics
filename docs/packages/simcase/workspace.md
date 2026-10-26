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
300–900 nm. Height is fixed at 220 nm, wavelength at 1550 nm, core mesh at 30 nm,
the window at [-1.5, 1.5, -1.2, 1.2] µm, PEC boundaries and two candidates.
These fixed settings are visible with the result. Use the existing editor for
other supported optical studies; this workspace does not expose all engine APIs.

Invalid numeric drafts stay visible across navigation. Resolve or discard them
before saving, opening or running. Undo/redo keeps up to 60 edits; result input
restore creates a new edit. Panel widths can be adjusted on wide screens and
are stored in this browser. Revisions identify local editing order, not Git commits.

## Results and files

The notebook retains the last six successful runs. Select a candidate to inspect
its field or compare two runs. Candidate indices are not a mode-tracking result.
Field colours use the vector magnitude normalized separately per candidate;
they do not represent optical power or a common physical colour scale.

Save input JSON to keep the design, or save session JSON to include validated
results. Open restores these files; input-only files are limited to 64 KiB and
sessions to 16 MiB. CSV and PNG exports are available. These version-1 workspace
formats are separate from headless simcase JSON documents. Reloading does not
automatically restore a notebook: save a session first.

The workspace checks `/api/workspace/capabilities` before enabling Run. Contract
version 1 and adapter `optical-fixed-v1` declare the fixed settings above,
`optical: true`, `coupled: false` and `simcase_version`. A missing or incompatible
contract blocks execution; **Check connection** retries. Each submitted run
captures the reported simcase package version and preserves it in session JSON.
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
