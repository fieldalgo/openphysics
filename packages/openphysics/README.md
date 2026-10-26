# openphysics

[Documentation](../../docs/packages/openphysics/overview.md)

[Suite documentation](https://github.com/fieldalgo/openphysics/blob/main/docs/README.md)

The OpenPhysics suite in one install. This distribution has no code of its own: it
requires the six OpenPhysics packages, which release together with it.

| package | what it is |
|---|---|
| `galerkin` | finite-element engine |
| `galerkin-refsol` | analytic reference solutions used to validate the engine |
| `meshine` | 2D quality mesher |
| `gmshio` | Gmsh runner and MSH reader |
| `physmat` | materials and optical dispersion |
| `simcase` | model document, headless runner and the optional browser studio |

```bash
pip install openphysics                  # the six packages, headless
pip install "openphysics[studio]"        # plus the local browser Studio
pip install "openphysics[studio,export,rii]"
```

| extra | adds |
|---|---|
| `studio` | `simcase[studio]`: the local browser Studio (FastAPI, Uvicorn) |
| `export` | `simcase[export]`: VTU export for ParaView (meshio) |
| `rii` | `physmat[rii]`: reading a local refractiveindex.info database (PyYAML) |
| `sipi` | `sipi`: signal and power integrity of PCB cross-sections (no further dependencies) |

No extra installs Gmsh. `gmshio` runs Gmsh as a separate program; install it on its
own (for example `pip install gmsh`) if you need it, under Gmsh's own license.

Every package can also be installed on its own. Versions before 0.1.0 (`0.0.1`) were
empty name reservations and install nothing.

Version 0.x is an alpha: the Python API may change between minor versions. The
[changelog](../../CHANGELOG.md) records each release and what stays stable.

Source: https://github.com/fieldalgo/openphysics
