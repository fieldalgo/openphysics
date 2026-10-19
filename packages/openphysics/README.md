# openphysics

[Documentation](docs/overview.md)

[Suite documentation](https://github.com/fieldalgo/openphysics/blob/main/docs/README.md)

Name reservation for the OpenPhysics suite.

This distribution is intentionally empty. OpenPhysics is developed as six packages, each
installable on its own:

| package | what it is |
|---|---|
| `galerkin` | finite-element engine |
| `galerkin-refsol` | analytic reference solutions used to validate the engine |
| `meshine` | 2D quality mesher |
| `gmshio` | Gmsh runner and MSH reader |
| `physmat` | materials and optical dispersion |
| `simcase` | model document, headless runner and the optional browser studio |

Install whichever you need. Installing this distribution does not install any of them; to use
the whole suite, install from a repository checkout as described in the
[repository README](https://github.com/fieldalgo/openphysics/blob/main/README.md).

Source: https://github.com/fieldalgo/openphysics
