# openphysics

[English](README.md) | [한국어](README.ko.md)

[English / 한국어 documentation and translation status](https://github.com/fieldalgo/openphysics/blob/codex/openphysics-thermal-simcase-release-check/docs/README.md)

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

Install whichever you need. A future release of this distribution will become an umbrella that
pulls in the whole suite; until then it holds the name and points here.

Source: https://github.com/FieldAlgo/openphysics
