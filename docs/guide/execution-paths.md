# Choose Python, JSON/CLI or Studio

**English** | [한국어](../locales/ko/pages/guide/execution-paths.md)

[Documentation home](../README.md)

Start with the physical problem and required controls. OpenPhysics shares engines
across interfaces, but the interfaces do not expose identical capabilities.

| Route | Choose it when | Boundary |
|---|---|---|
| Direct Python package APIs | You need mechanics, explicit heat → mechanics coupling or low-level numerical control | Assemble the supported mesh, coefficient and boundary objects yourself |
| Python `Document` + `run` | You want to automate supported simcase models in Python | Uses the same document contract as JSON/CLI |
| JSON/CLI | You need repeatable model validation, batch execution and saved results | One supported physics entry per document; a document is not an arbitrary multiphysics graph |
| Original Studio at `/` | You want browser editing of 2D optical or rectangular steady/transient heat models | No cavity, material-region heat, electric/Joule or mechanics editor |
| Experimental workspace at `/workspace` | You want the bounded optical workflow and its session notebook | Fixed optical adapter; heated-waveguide screen is a setup preview |

## Find the route for a physical problem

[The supported-document table](../packages/simcase/overview.md#supported-documents)
is the JSON/CLI entry point: waveguides, rectangular cavities, rectangular
steady/transient heat including named material regions, and the supported
electric/Joule models. Model-specific contracts define boundaries, studies and
coefficient restrictions. A Python engine feature does not automatically add a
JSON field or a Studio control.

Use [direct Python mechanics](../packages/galerkin/thermal_mechanical_workflow.md)
for heat → thermoelasticity. Follow the
[temperature-dependent Joule tutorial](../packages/galerkin/temperature_joule_tutorial.md)
for explicit nonlinear control. For headless multi-material heat, start with the
[two-material wall](../packages/simcase/layered_wall_tutorial.md).

## Validate and run a document

After the [simcase installation](../packages/simcase/overview.md), run from the
repository root with the supplied wall model:

```sh
python -m simcase validate examples/simcase/layered_wall.json
python -m simcase run examples/simcase/layered_wall.json -o out/wall-cli
```

Use a new or empty output directory. Validation checks document rules; it does not
prove mesh convergence, conservation or physical validity. Inspect the
[saved results](../results/saved-results.md) and perform the relevant
[convergence checks](../validation/convergence.md).

## Choose the browser workflow deliberately

The original Studio and experimental workspace are served by `simcase-studio`,
but their saved files have different contracts. Original editors use supported
simcase model documents. Workspace input/session JSON is its own format; a
session may contain results, and is not a headless solver document. Follow the
[workspace guide](../packages/simcase/workspace.md) for its fixed geometry,
wavelength, material choices, exports and restoration limits.

The heated-waveguide workspace preview does not calculate coupled thermal–optical
results. Switch to a supported document or Python workflow when you need controls
outside that adapter. Keep the model and run settings with exported images:
an image alone does not preserve the calculation.
