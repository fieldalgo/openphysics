# Bundled images, fixtures and data

**English** | [한국어](locales/ko/pages/assets.md)

This inventory connects bundled non-code assets to repository history and
generation inputs. The files listed below stay in the repository; the package
sdists and wheels do not ship them. The repository's original figures,
screenshots and fixtures carry its [Apache-2.0 license](../LICENSE); separately
identified material keeps the terms in [NOTICE](../NOTICE) and package
notices. Historical pictures are illustrations, not results from a new
validation run.

| Asset | Provenance and reproduction input |
|---|---|
| `packages/gmshio/examples/hadley_rib_mesh.png` | `packages/gmshio/examples/hadley_rib_mesh.py`, a plot of the example mesh |
| `packages/meshine/examples/compare_with_gmsh.png` | `packages/meshine/examples/compare_with_gmsh.py`, example mesh comparison |
| `packages/physmat/examples/materials.png` | `packages/physmat/examples/plot_materials.py`, plotted material functions; optical data retains the terms in `packages/physmat/NOTICE` |
| `packages/simcase/docs/geometry.png`, `mesh.png`, `results.png` | Screenshots of the project's own earlier Studio and SOI-strip example, introduced with the UI in commit `f44d7f8373f09ba9a7dbcd04066a0087485a3fd2` and retained through the package rename |
| `packages/simcase/examples/soi_strip_results.png` | SOI-strip example plot introduced with the document runner and input in commit `07d4a89`; the plot path is now `packages/simcase/src/simcase/runner.py` |
| `docs/gallery/heated_plate.webp`, `heated_plate.png`, `coax.png`, `box_cavity.png` | Drawn by `packages/simcase/examples/gallery.py` from `gallery_heated_plate.json`, `gallery_box_cavity.json` and the coax setup in the script; numbers and versions in the [gallery](gallery.md). The plate material values are approximate example inputs |
| `tests/gmshio/data/unit_square.geo`, `unit_square.msh` | Unit-square geometry and its mesh fixture, introduced together with the reader and assertions in commit `b2fe26a`; the `.geo` supplies the points, edges and physical tags |

The four simcase pictures were visually checked against the repository's own
UI/example content during publication review. They retain historical naming
and values. This review did not rerender them byte for byte or rerun the mesh
generator; Git authorship, co-introduction and the corresponding implementation
are the recorded provenance evidence.

Optical table and dispersion-coefficient sources are recorded in
`physmat._tables.REFERENCES`, material source strings and
[physmat/NOTICE](../packages/physmat/NOTICE); the upstream refractiveindex.info
database is CC0 1.0. Published benchmark numbers are attributed in
[galerkin-refsol/NOTICE](../packages/galerkin-refsol/NOTICE). Typical thermal and
mechanical constants labelled as handbook values are approximate example inputs;
the repository does not identify a specific handbook edition for every such
value, and they must not be represented as certified measurements or RII data.

Gmsh is installed separately and invoked through its executable/file interface.
Its program license is distinct from the numerical mesh output. No upstream
solver implementation is bundled in these fixture or image files.
