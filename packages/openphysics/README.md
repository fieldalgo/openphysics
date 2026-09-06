# simdoc — the model document and its headless runner

A COMSOL-style program is, underneath, a file that describes the model and an
engine that runs the file. `simdoc` is that file format and that engine for
the FieldAlgo stack, without a GUI yet: a JSON document holds geometry,
materials, physics, mesh settings and the study; one command runs it through
meshine (mesh), physmat (materials) and galerkin (FEM) and writes results.

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
  "simdoc": "0.1",
  "name": "SOI strip waveguide 500 x 220 nm",
  "geometry": {
    "domain": {"xmin": -1.5, "xmax": 1.5, "ymin": -1.2, "ymax": 1.2},
    "background": {"material": "SiO2"},
    "shapes": [
      {"name": "core", "type": "rect", "x": -0.25, "y": 0.0, "w": 0.5, "h": 0.22, "material": "Si", "mesh_size": 0.02}
    ]
  },
  "materials": {"myglass": {"n": 1.5}},
  "physics": {"type": "em.modes2d", "formulation": "scalar", "wavelength": 1.55, "num_modes": 2,
              "boundary": {"left": "pec", "right": "pec", "top": "pec", "bottom": "pec"}},
  "mesh": {"size": 0.25, "grading": {"center": [0.0, 0.11], "near": 0.02, "far": 0.16, "distance": 1.0}},
  "study": {"type": "sweep", "parameter": "physics.wavelength", "values": [1.4, 1.45, 1.5, 1.55, 1.6, 1.65, 1.7]}
}
```

Lengths in micrometres. Shapes are `rect`, `circle` or `polygon`; later
shapes cut earlier ones and the background fills what is left (the boolean
work is done with shapely). A circle that nothing overlaps is meshed as an
exact circle. Material names are looked up in `materials` first, then in
physmat's built-ins (`"Si"`, `"SiO2"`, `"Au"`, ...), so dispersion is applied
automatically at every wavelength of a sweep. `study.parameter` is any dotted
path into the document; sweeping `physics.wavelength` also yields the group
index.

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

## Where this sits

```
GUI (later)  ->  edits the document
script / CLI ->  runs the document       simdoc.run
                    |-- meshine   geometry -> mesh
                    |-- physmat   material names -> eps(lambda)
                    |-- galerkin  assembly + eigenproblem
                    '-- refsol    references (tests)
```

## License

Apache License 2.0 - see [LICENSE](LICENSE) and [NOTICE](NOTICE).

Copyright 2026 Yongha Kim (FieldAlgo)
