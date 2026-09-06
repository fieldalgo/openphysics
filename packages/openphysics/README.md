# simdoc — the model document and its headless runner

A COMSOL-style program is, underneath, a file that describes the model and an
engine that runs the file. `simdoc` is that file format and that engine for the
FieldAlgo stack: a JSON document holds geometry, materials, physics, mesh
settings and the study; one command runs it through meshine (mesh), physmat
(materials) and galerkin (FEM) and writes results. The browser UI that edits
the document is [an optional subpackage](#the-browser-ui) of the same install;
the engine never depends on it.

```bash
pip install git+https://github.com/FieldAlgo/simdoc      # pulls meshine, physmat, galerkin, refsol, shapely
python -m simdoc example soi_strip > model.json
python -m simdoc validate model.json
python -m simdoc run model.json                          # -> model_results/
```

`model_results/` contains `summary.json` (n_eff per study point, group index,
mesh statistics, timings), `fields.npz` (mesh and mode fields), `results.png`
(mesh, mode, sweep), `log.txt`, and a copy of the document.

## The document

```json
{
  "simdoc": "0.2",
  "name": "SOI strip waveguide 500 x 220 nm",
  "units": {"length": "um"},
  "geometry": {
    "domain": {"xmin": -1.5, "xmax": 1.5, "ymin": -1.2, "ymax": 1.2},
    "background": {"material": "SiO2"},
    "shapes": [
      {"name": "core", "type": "rect", "x": -0.25, "y": 0.0, "w": 0.5, "h": 0.22, "material": "Si", "mesh_size": 0.02}
    ]
  },
  "materials": {"myglass": {"n": 1.5}},
  "physics": {
    "em1": {"type": "em.modes2d", "formulation": "scalar", "wavelength": 1.55, "num_modes": 2,
            "boundary": {"left": "pec", "right": "pec", "top": "pec", "bottom": "pec"}}
  },
  "mesh": {"size": 0.25, "grading": {"center": [0.0, 0.11], "near": 0.02, "far": 0.16, "distance": 1.0}},
  "study": {"type": "sweep", "parameter": "physics.em1.wavelength", "values": [1.4, 1.45, 1.5, 1.55, 1.6, 1.65, 1.7]}
}
```

`units` declares one symbol per SI base dimension the physics needs; every
number in the document is then a bare number in that system, and a dimension
the physics requires but the document does not name is an error rather than a
silent metre. `physics` is a map of named physics, so a document can hold more
than one, and a sweep parameter names one of them.

Shapes are `rect`, `circle` or `polygon`; later
shapes cut earlier ones and the background fills what is left (the boolean
work is done with shapely). A circle that nothing overlaps is meshed as an
exact circle. Material names are looked up in `materials` first, then in
physmat's built-ins (`"Si"`, `"SiO2"`, `"Au"`, ...), so dispersion is applied
automatically at every wavelength of a sweep. `study.parameter` is any dotted
path into the document; sweeping a wavelength also yields the group index.

Physics today: `em.modes2d` with the `scalar` formulation (exact for TE slab
modes, an approximation for 2D high-contrast cores). The `vector` formulation
is reserved for the galerkin M3a mode solver and raises a clear error until
it lands. Boundaries: `pec` (field = 0) or `pmc` (natural).

## From Python

```python
from simdoc import Document, run
doc = Document.load("model.json")
res = run(doc)
res.neff                 # (study points, modes)
res.group_index()        # when sweeping wavelength
res.save("out/")
```

`run` is a composition of stages that are public in their own right, so a front
end can mesh without solving and a caching layer can redo only what changed:

```python
from simdoc import build_mesh, solve_point, study_points
model = build_mesh(doc)                  # geometry -> mesh -> materials
parameter, values = study_points(doc)
result = solve_point(model, doc.sole_physics()[1])
```

## The browser UI

`simdoc.studio` is the program part of the stack, and it is optional: a model
tree on the left, geometry / mesh / results views in the middle, a properties
panel on the right, a log at the bottom. It edits the same document a script
edits and asks a local server to mesh and run it with the same engine.

```bash
pip install "simdoc[studio] @ git+https://github.com/FieldAlgo/simdoc"
simdoc-studio                # http://127.0.0.1:8765, opens the browser
python -m simdoc.studio --port 9000 --no-browser
```

The base install stays headless — `fastapi` and `uvicorn` arrive only with the
`studio` extra, so a batch or an HPC user never pulls a web stack to run a
document.

![geometry](docs/geometry.png)
![results](docs/results.png)

- Load an example, open a `.json` from disk, download the edited document.
- Model tree: Units, Domain, Background, shapes (rect / circle / polygon, add,
  reorder, delete), custom materials, Physics, Mesh, Study, Results. Selecting a
  node shows an editable form; every edit updates the geometry view and the JSON
  tab immediately, and the validator's magnitude warnings show up next to it.
- Materials: physmat's built-ins with their source and validity range, plus
  document-level constant materials.
- Generate mesh: meshine through the server, drawn by region, with node and
  triangle counts, minimum angle and mean quality.
- Run: a background job whose log streams back, then the mode field (selectable
  study point and mode), an n_eff-vs-parameter chart and a table with the group
  index.
- JSON tab: edit the document by hand and apply.

The page is a single HTML file with no build step and no external libraries
(canvas drawing only); a framework can come in when the UI grows. Web rather
than desktop so that any front end shares one UI over the same document format,
runs the same on a laptop or a server, and can reach other services over HTTP.

Not yet: mouse sketching and boolean CAD, a 3D viewer, geometry sweeps that
regenerate the mesh, user accounts, projects saved on the server.

### The HTTP API

Used by the page, usable by anything else.

| method | path | purpose |
|---|---|---|
| GET | `/api/examples`, `/api/examples/{name}` | example documents |
| GET | `/api/units` | the declarable base dimensions and their unit symbols |
| GET | `/api/materials` | physmat built-ins: names, aliases, range, source |
| POST | `/api/materials/preview` | n, k of a material over a wavelength range |
| POST | `/api/validate` | `{doc}` -> `{ok, summary, doc, notes}` or `{ok: false, error}` |
| POST | `/api/mesh` | `{doc}` -> nodes, triangles, regions, boundary edges, stats |
| POST | `/api/run` | `{doc}` -> `{job}`; runs in a background thread |
| GET | `/api/jobs/{id}` | status and log lines |
| GET | `/api/jobs/{id}/result` | n_eff, group index, fields, mesh, timings |

`simdoc.studio` may use only simdoc's public API — the names in
`simdoc.__all__`, never a module underneath it. A test enforces that. It keeps
the UI a consumer of the engine rather than a part of it, so it can be lifted
back out into its own distribution as a move rather than a rewrite; when the UI
needs something the engine does not export, the engine exports it on purpose.

## Self-checks

```bash
PYTHONPATH=.:../galerkin:../meshine:../galerkin-refsol:../physmat python3 -m pytest -q tests
```

Documents round-trip through JSON; malformed documents are rejected with
specific messages; boolean geometry tiles the domain exactly (areas checked);
untouched circles keep their nodes on the true circle; and three documents
run end to end against references: a 220 nm Si slab reproduces refsol's TE0
to 1.5e-3 (P1 discretisation), a step-index fiber reproduces the LP01/LP11
scalar modes to 2e-4, and the Hadley rib comes within 5e-4 of the published
quasi-TE value (the remaining gap is the scalar approximation). Sweeps give
falling n_eff and n_g > n_eff.

The studio's endpoints are tested with FastAPI's test client, including a full
run job whose n_eff matches the slab reference; those tests skip when the
`studio` extra is not installed. The page itself was exercised in a browser:
load an example -> edit the units and the physics -> mesh -> run -> results.

## Where this sits

```
simdoc.studio ->  edits the document     (optional, pip install simdoc[studio])
script / CLI  ->  runs the document      simdoc.run
                     |-- meshine   geometry -> mesh
                     |-- physmat   material names -> eps(lambda)
                     |-- galerkin  assembly + eigenproblem
                     '-- refsol    references (tests)
```

## License

Apache License 2.0 - see [LICENSE](LICENSE) and [NOTICE](NOTICE).

Copyright 2026 Yongha Kim (FieldAlgo)
