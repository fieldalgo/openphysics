# Build a model: geometry, materials and mesh

**English** | [한국어](../locales/ko/pages/modeling/index.md)

[Documentation home](../README.md)

A calculation combines geometry, materials, a mesh, boundary conditions and a study.
`simcase` packages supported combinations into a JSON document; the Python route
composes package APIs explicitly.

| Stage | Responsibility and checks |
|---|---|
| Geometry and regions | Define the `simcase` domain/shapes or the mesher inputs. |
| Materials | Use `physmat` for optical properties/dispersion; follow solver/document contracts for thermal, electric and mechanical coefficients. |
| Mesh | Use `meshine` 2D triangles or the optional `gmshio` route; preserve region names and boundaries. |
| Physics, boundaries and units | Check the model-specific signs, units and boundary conditions in `galerkin`. |
| Study and execution | Select a supported `simcase` single/sweep/time study or explicit Python calls. |

Sharing a repository does not make arbitrary material/mesh/physics combinations
supported. In particular, optical dispersion models do not define thermal or electric conductivity.

## Geometry and mesh

- [meshine — a small quality triangle mesher for multi-material planar domains](../packages/meshine/overview.md)
- [gmshio — Gmsh meshes for the galerkin engine, without linking to Gmsh](../packages/gmshio/overview.md)
- [Tutorial: analyse your own waveguide](../packages/simcase/waveguide_tutorial.md)


## Material properties and region assignment

- [physmat — material properties for physics solvers](../packages/physmat/overview.md)
- [Piecewise-constant materials on named regions](../packages/galerkin/multimaterial.md)
- [Heat documents with material regions](../packages/simcase/thermal_regions2d.md)


## Documents and package boundaries

- [simcase — the model document and its headless runner](../packages/simcase/overview.md)
- [OpenPhysics architecture](../architecture.md)
- [Physics problems](../physics/index.md)
