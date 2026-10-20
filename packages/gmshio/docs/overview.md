# gmshio — Gmsh meshes for the galerkin engine, without linking to Gmsh

**English** | [한국어](locales/ko/pages/overview.md)

[English / 한국어 documentation and translation status](https://github.com/fieldalgo/openphysics/blob/main/docs/README.md)

Writes `.geo` scripts, runs the `gmsh` command-line program as a separate
process, and reads the resulting MSH 4.1 file into numpy arrays that a
finite-element code can use directly: node coordinates, consistently oriented
elements, one region id per element, and boundary facets grouped by name.

Gmsh is GPL. This package never imports Gmsh's Python API or links against
its library — it only executes the program and parses its output — so the
solver that depends on `gmshio` keeps its own license. `gmshio` itself
depends on numpy alone.

## Install

```bash
# From the repository root
python -m pip install -e packages/gmshio
# plus a gmsh executable, one of:
pip install gmsh            # PyPI wheel ships the program
# or a system package / download from https://gmsh.info, or set GMSH_EXECUTABLE
```

## Usage

```python
from gmshio import geo, generate, to_fem2d, to_fem3d, read_msh

# 1. a ready-made benchmark geometry -> .geo text -> gmsh -> Mesh -> FEM arrays
mesh = generate(geo.rib_waveguide(slab_thickness=0.3, lc_core=0.1), dim=2)
fem = to_fem2d(mesh)
fem.nodes            # (N, 2)
fem.triangles        # (T, 3) counter-clockwise
fem.regions          # (T,) index into fem.region_names == ["core", "box", "clad"]
fem.boundary_edges   # {"left": (E, 2), "right": ..., "top": ..., "bottom": ...}
fem.region_area("core")   # 7.5 exactly (polygonal regions are reproduced exactly)

# 2. your own planar geometry: list material regions as polygons that tile the domain
g = geo.Geo()
g.add_region("core", [(-1, 0), (1, 0), (1, 0.5), (-1, 0.5)], lc=0.05)
g.add_region("clad", [(-3, -2), (3, -2), (3, 0.5), (1, 0.5), (1, 0), (-1, 0), (-1, 0.5), (-3, 0.5)], lc=0.3)
g.add_region("clad", [(-3, 0.5), (3, 0.5), (3, 2), (-3, 2)], lc=0.3)
fem = to_fem2d(generate(g.render(geo.box_sides(-3, 3, -2, 2)), dim=2))
# shared edges and T-junctions between polygons are resolved automatically

# 3. 3D
fem3 = to_fem3d(generate(geo.box_cavity(1.0, 0.5, 0.75, lc=0.1), dim=3))
fem3.tetrahedra, fem3.boundary_faces["pec"]

# 4. read a .msh you produced yourself (MSH 4.1 ASCII)
mesh = read_msh("model.msh")
mesh.cells("triangle"), mesh.physical_tags("triangle"), mesh.cells_in("pec", "line")
```

A `.geo` script is written in whatever unit its author chose, so `gmshio` holds no
absolute length constant. Point merging and T-junction splitting in `Geo` are a
dimensionless fraction of the geometry's own bounding-box diagonal, and `to_fem2d`
judges planarity against the mesh's own in-plane extent, so the same geometry
resolves to the same topology whether it is written in micrometres or kilometres.

Ready-made geometries in `gmshio.geo`:

| function | what | regions / boundaries |
|---|---|---|
| `rib_waveguide(...)` | Hadley (2002) rib waveguide cross-section: 3 µm × 1 µm rib, slab 0–0.7 µm, 18 µm wide domain, 10 µm substrate, 3 µm cladding | `core`, `box`, `clad` / `left right top bottom` |
| `circular_fiber(a, R, lc_core)` | step-index fiber: circular core in circular cladding, exact arcs | `core`, `clad` / `outer` |
| `box_cavity(a, b, d, lc)` | rectangular resonator | `cavity` / `pec` |

## Self-checks

```bash
# From the repository root
python -m pip install pytest -e packages/gmshio
python -m pytest -q tests/gmshio
```

The tests check what a solver relies on rather than the reader against
itself: polygonal region areas and box volumes are reproduced exactly, every
element is positively oriented, the tagged boundary coincides with the set of
edges (faces) used by exactly one element, interface nodes of the fiber lie
on the true circle to 1e-9, and the circle's polygonal area error decreases
at second order. Tests that need the executable are skipped when it is
missing.

## Scope and limits

- MSH 4.1 ASCII only (`gmsh -format msh41`). Binary and older versions are rejected with a clear message.
- `to_fem2d` / `to_fem3d` accept first-order triangles / tetrahedra; the raw `Mesh` keeps any element type Gmsh produced.
- `Geo` handles straight-sided polygons; curved geometry is written by hand (see `circular_fiber`) or with Gmsh's OpenCASCADE kernel via `Geo.raw` / your own `.geo`.

## License

Apache License 2.0 - see [LICENSE](../LICENSE) and [NOTICE](../NOTICE).

Copyright 2026 Yongha Kim (FieldAlgo)

Gmsh is a separate program under GPL-2.0-or-later. It is neither distributed
with nor linked into this package: `gmshio` writes a `.geo` script, runs the
`gmsh` executable as a child process, and reads back the `.msh` file. The GPL
therefore does not extend to `gmshio` or to code that uses it. Install Gmsh
yourself under its own license.

This project is not affiliated with, endorsed by, or supported by the Gmsh
project.
