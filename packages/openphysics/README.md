# openphysics

[Documentation](../../docs/packages/openphysics/overview.md)

[Suite documentation](https://github.com/fieldalgo/openphysics/blob/main/docs/README.md)

The complete OpenPhysics product in one install: the six packages with the browser
Studio, VTU export for ParaView, the refractiveindex.info reader and `sipi`. This
distribution has no code of its own; it requires those packages, which release together
with it, and gives the `openphysics` command, which opens Studio's model workspace.

| package | what it is |
|---|---|
| `galerkin` | finite-element engine |
| `galerkin-refsol` | analytic reference solutions used to validate the engine |
| `meshine` | 2D quality mesher |
| `gmshio` | Gmsh runner and MSH reader |
| `physmat` | materials and optical dispersion, with the refractiveindex.info reader (PyYAML) |
| `simcase` | model document, headless runner, the browser Studio (FastAPI, Uvicorn) and VTU export (meshio) |
| `sipi` | signal and power integrity of PCB cross-sections |

**0.0.2 is not on PyPI yet.** PyPI holds only the empty `0.0.1` name reservations,
so these commands install nothing useful today, and pip may still report success.
Until the release, [install from a source checkout](../../README.md#install-from-source) or from wheels built
from it, and pin the version (`"openphysics==0.0.2"`) so that pip refuses
instead of picking `0.0.1`. The commands below are for the release.

```bash
pip install openphysics        # the complete product
openphysics                    # open Studio's model workspace in the browser (Ctrl+C stops it)
```

`openphysics --classic` opens the classic optical and thermal editor; `--port`,
`--host` and `--no-browser` work as for `simcase-studio`. The earlier extras
(`studio`, `export`, `rii`, `sipi`) still work and add nothing. To use a library
without Studio, install that package on its own (for example `pip install simcase`).

Nothing installs Gmsh. `gmshio` runs Gmsh as a separate program; install it on its
own (for example `pip install gmsh`) if you need it, under Gmsh's own license.
`meshloom`, the compiled 3D mesher, is installed separately for now.

Every package can also be installed on its own. Version `0.0.1` of every name was an
empty name reservation and installs nothing.

Version 0.x is an alpha: the Python API may change between minor versions. The
[changelog](../../CHANGELOG.md) records each release and what stays stable.

Source: https://github.com/fieldalgo/openphysics
