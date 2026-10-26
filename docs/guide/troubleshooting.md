# Diagnose model, solver and result errors

**English** | [한국어](../locales/ko/pages/guide/troubleshooting.md)

[Documentation home](../README.md)

Identify the stage that failed before changing inputs. Keep the original model
and complete error text. A rejected input, failed numerical solve, unsupported
viewer and expired UI result are different problems.

## Start with these checks

| Symptom | Check first | Appropriate next action |
|---|---|---|
| Import fails or module has no expected attributes | Active Python environment, local package installs, working directory | Run from repository root; install the required local packages together |
| Unknown field, type, unit or region | Exact document contract; region versus material names | Validate the input and correct the named field; do not silently delete intended physics |
| Steady heat has no temperature reference | Every connected component's Dirichlet/positive Robin support | Specify the physical temperature reference; insulation alone does not anchor steady heat |
| Mechanical rigid-mode/constraint error | Physical supports and independent constrained modes | Correct supports; do not add arbitrary fixed nodes just to remove an error |
| Mesh generation or geometry rejection | Overlap, small gaps/angles, vanished regions, element orientation | Inspect the geometry/mesh diagnostics and simplify a reproducer |
| Transient initial-condition mismatch | Initial field versus boundary values at the first time | Make them physically consistent; the solver does not project initial data |
| Joule iteration fails | Error reason, valid material range, history and nonlinear defects | Inspect feedback and justified initial/iteration settings; do not weaken acceptance gates |
| Save refuses an existing path | Existing files and output ownership | Select a new directory; preserve previous results |
| Export rejects a layout | Saved `field_layout` and exporter support | Keep NPZ/summary; use a supported consumer or report the unsupported export separately |

The [mesh guide](../packages/meshine/overview.md) explains corner handling;
the [Joule tutorial](../packages/galerkin/temperature_joule_tutorial.md) demonstrates
range and iteration failures. Numerical failure does not by itself prove physical
instability, uniqueness failure or a particular transient evolution.

## CLI and Studio are not interchangeable

For document problems, run `python -m simcase validate <model.json>` before a solve.
Validation can reject schema problems; mesh construction and numerical execution
can still fail later. A supported Python API does not guarantee JSON or Studio support.

For Studio, retain the operation/error shown in the interface and distinguish:
connection/capability failure, invalid draft, rejected run, busy/resource limit,
and unavailable result. Do not repeatedly submit a solve to recover a failed read.
A stale view after editing is not a new result for the changed model.

The [experimental workspace](../packages/simcase/workspace.md) has its own capability
and input/session format. Its heated-waveguide application is a setup preview;
visible coupling cards do not mean coupled execution is available. Its candidate
indices do not establish mode tracking, and independently normalized colors are
not a common power scale. Original [steady](../packages/simcase/thermal_studio.md)
and [transient](../packages/simcase/thermal_transient_studio.md) Studio routes have
separate recovery and resource policies.

## A useful report

Provide the minimal input, exact command or UI steps, release/commit, Python and
package versions, complete error and the stage that failed. Include expected
physical behavior and whether the same case works on another resolution or interface.
For a suspected numerical issue, include units, boundary conditions, refinement
settings and the independent reference or conservation check. Do not label a plot
as validation without its input and comparison. Remove confidential model data
before sharing. Follow the [contribution guide](../contributing.md) for reports;
a fully confirmed defect is not required to ask a question.
