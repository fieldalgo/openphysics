# Region Studio resource observation

[한국어](locales/ko/pages/region_resource_probe.md)

`tools/studio_resources/run_region_resource_workloads.py` measures Studio with
heat documents that have material regions ([Studio region documents](packages/simcase/thermal_studio.md#region-documents)).
Each workload starts the exact source checkout's Studio server in a new loopback
process, requests the capabilities, validates the document and, when validation
accepts it, runs it and polls the job. It is an observation, not a performance
gate: it fails only when a workload's outcome code differs from the fixed one
below, or when a stage fails (the server does not start, an unexpected HTTP
status, a 300 s deadline). Linux only, since the memory figures come from `/proc`.

```sh
python tools/studio_resources/run_region_resource_workloads.py --source-root . --expected-commit FULL_CHECKOUT_SHA --output .validation/region-resource-observation
```

The checkout must be at the expected commit with no changes under `packages/`
or in `tests/simcase/region_studio_fixtures.py`, which generates every document.
The server runs with the checkout's package sources first on `PYTHONPATH` and
refuses to serve if a first-party module comes from anywhere else. Six native
thread variables are set to 1. `--workload NAME` (repeatable) runs a subset for
local work; CI runs all of them once, after the transient observation.

## What is recorded

For each workload, in `region-workloads.json` (`region-resource-workloads-v1`)
next to the generated documents and each server's stderr:

- the outcome: `done`, `validate:<code>` (a validation refusal) or `job:<code>`
  (a job error), and the expected one;
- the document's counts as Studio checks them, computed in the observer's own
  process with the checkout's simcase: shapes, circles and polygon points; the
  boundary crossings, when those three are within Studio's caps; and the loop
  vertices, when the crossings are too;
- validation wall time, as the client measures the request;
- for a run: the run request's wall time (it validates again), the job wall time
  from the accepted run to the terminal status, and the slowest status poll;
- the slowest answer to a capability request that a second client thread sends
  every 100 ms while the validation request runs, and again from the run request
  to the terminal status: how long the server's event loop could not answer while
  validation or a job held the interpreter (polling every 20 ms slowed the jobs
  by up to about 25 % in local runs);
- the result's encoded bytes;
- the server's VmRSS after the capability request (idle) and its VmHWM at the
  end, and their difference.

VmHWM is the process's high-water mark, so it includes startup and validation.
The times include loopback HTTP and polling. One run on a shared host is not a
capacity statement, and the limits stay `candidate-unmeasured`.

## Workloads and expected outcomes

The expected outcomes are fixed in the tool; a different outcome fails the run.

| Workload | Expected |
| --- | --- |
| Steady example, mesh size 2 mm | `done` |
| Steady example, mesh size 0.4 mm (about 9800 nodes) | `done` |
| One strip 0.2 mm high, sized 0.06 mm, in a background sized 1000 mm | `done` |
| The same strip 0.005 mm high, sized 0.01 mm | `job:mesh_limit_exceeded` |
| The steady example plus a steel film 30 mm long and 1e-7 mm thick | `job:mesh_limit_exceeded` |
| 16 isolated circles, 47 rects and a 512-gon (64 shapes, 512 points) | `done` |
| Steady example at global size 0.025 mm, background and plate sized 2 mm | `done` |
| Crossing combs, 63 teeth each (510 points) | `validate:geometry_limit_exceeded` |
| Covered crossings with the most teeth whose crossings stay within 1024 | `done` |
| The same with 16 identical circles after the covering rects, in place of 16 front rects | `done` |
| Covered crossings, 126 teeth (crossings hidden under 4 rects) | `validate:geometry_limit_exceeded` |
| Collinear overlaps: a 512-point polygon split along two lines, 47 rects on the same lines and 16 identical circles | `done` |
| 16 isolated circles, then 16 crossing 32-point stars | `validate:geometry_limit_exceeded` |
| One 511-point sawtooth with tips of about 1 degree | `job:solver_failed` |
| The sawtooth with 10-degree tips, jittered, 60 crossing rects, `min_angle` 33 | `job:mesh_limit_exceeded` |
| 7 concentric rings 0.3 mm apart, sized 0.15 mm, `min_angle` 33 | `job:solver_failed` |
| Transient example, 9 times, mesh size 0.2 mm | `done` |
| Transient example, 64 times, mesh size 0.5 mm | `done` |
| Transient example, 128 times, mesh size 0.25 mm | `job:history_limit_exceeded` |

Without the crossing cap, the covered crossings cost 18.5 s and 32 s (two
measurements) in `Document.from_dict` alone, which validation and a run repeat (see
[mesh limits for callers](packages/simcase/thermal_regions2d.md#mesh-limits-for-callers));
the three crossing documents now stop before `Document.from_dict`. Touching
boundaries and collinear overlaps (shared edges, identical circles) are not
boundary crossings, so `max_boundary_crossings` does not count them, but they
still make the shapes' booleans costlier: the two workloads built from them are
the slowest validations below. The strip, film and 10-degree sawtooth workloads
need meshes far finer than the node cap and show what an over-fine refusal in the
job costs. The 1-degree sawtooth needs one too, but meshine refuses its boundary
first ("cannot resolve", fail-closed) on the micrometre copy simcase meshes, so
it ends as `solver_failed` within a second. Its outcome was first fixed as
`job:mesh_limit_exceeded`, since meshed in millimetres it reaches the node cap,
and was changed to `job:solver_failed` after the first run on micrometre meshes
failed on it; the expectation as first fixed fails. The cause is the factor
1000 from millimetres to micrometres, not the scale: on the copy, meshine
inserts two points at the same place, or within 7e-12 µm, at the midpoints of
56 tooth sides, which the triangulation cannot separate; the document with every
length multiplied by 0.001, 0.5, 2, 3, 7, 10, 100, 999, 1001, 1024 or 1e6 and
meshed as written reaches the node cap, and multiplied by 1000 it fails in the
same way. simcase's own run of the document, without limits or Studio, raises
the same error. The concentric rings show another way a job ends: meshine's
refinement does not converge within its 80 rounds before the node cap stops it,
and the job ends as `solver_failed`.

## One local run

Measured once on Linux (Python 3.12.3, numpy 2.5.4, scipy 1.18.1, shapely 2.2.0
with GEOS 3.14.1, 4 CPUs, native threads 1) on 2026-10-27, with this tool, these
fixtures and these packages; 147 s for all nineteen workloads. Every outcome was
the expected one. Times are client wall times in seconds: validation is the
validate request, run the run request (which validates again), job from the
accepted run to the terminal status, and capability the slowest capability answer
during either. Memory is in MiB, idle being VmRSS after the capability request
and peak the final VmHWM. Counts are shapes / circles / polygon points /
boundary crossings / loop vertices, with – where Studio stops before counting.

| Workload | Counts | Outcome | Validation | Run | Job | Capability | Idle | Peak | Peak − idle | Result bytes |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Steady example, 2 mm | 2 / 1 / 0 / 0 / 44 | `done` | 0.01 | 0.01 | 0.51 | 0.07 | 106 | 117 | 11 | 128,161 |
| Steady example, 0.4 mm | 2 / 1 / 0 / 0 / 136 | `done` | 0.01 | 0.01 | 7.37 | 0.27 | 106 | 148 | 42 | 2,160,269 |
| Strip 0.2 mm, sized 0.06 mm | 1 / 0 / 0 / 0 / 12 | `done` | 0.01 | 0.01 | 9.33 | 0.13 | 106 | 153 | 47 | 2,243,197 |
| Strip 0.005 mm, sized 0.01 mm | 1 / 0 / 0 / 0 / 12 | `job:mesh_limit_exceeded` | 0.01 | 0.01 | 0.81 | 0.08 | 106 | 129 | 23 | – |
| Film 1e-7 mm | 3 / 1 / 0 / 0 / 52 | `job:mesh_limit_exceeded` | 0.02 | 0.02 | 1.49 | 0.09 | 106 | 130 | 24 | – |
| 16 circles, 47 rects, 512-gon | 64 / 16 / 512 / 0 / 1916 | `done` | 0.57 | 0.60 | 8.79 | 0.48 | 106 | 134 | 28 | 976,213 |
| Global size 0.025 mm | 2 / 1 / 0 / 0 / 2022 | `done` | 0.02 | 0.02 | 7.69 | 0.18 | 106 | 135 | 29 | 1,495,931 |
| Crossing combs, 63 teeth | 2 / 0 / 510 / 15,876 / – | `validate:geometry_limit_exceeded` | 0.03 | – | – | 0.01 | 106 | 109 | 3 | – |
| Covered crossings at the cap (15 teeth) | 64 / 0 / 66 / 1023 / 490 | `done` | 0.99 | 1.16 | 3.73 | 0.08 | 106 | 121 | 15 | 203,230 |
| The same with 16 identical circles | 64 / 16 / 66 / 1023 / 618 | `done` | 2.13 | 3.33 | 7.29 | 0.11 | 106 | 128 | 22 | 328,758 |
| Covered crossings, 126 teeth | 64 / 0 / 510 / 64,455 / – | `validate:geometry_limit_exceeded` | 0.08 | – | – | 0.01 | 106 | 112 | 6 | – |
| Collinear overlaps | 64 / 16 / 512 / 0 / 1178 | `done` | 1.76 | 1.96 | 16.73 | 0.12 | 106 | 161 | 55 | 1,969,978 |
| 16 circles, 16 crossing stars | 32 / 16 / 512 / 3840 / – | `validate:geometry_limit_exceeded` | 0.03 | – | – | 0.01 | 106 | 111 | 5 | – |
| Sawtooth, 1-degree tips | 1 / 0 / 511 / 0 / 1026 | `job:solver_failed` | 0.09 | 0.05 | 0.34 | 0.09 | 106 | 115 | 9 | – |
| Sawtooth, 10-degree tips, 60 rects, angle 33 | 61 / 0 / 511 / 120 / 1696 | `job:mesh_limit_exceeded` | 0.39 | 0.38 | 2.92 | 0.09 | 106 | 131 | 25 | – |
| Concentric rings | 7 / 7 / 0 / 0 / 1572 | `job:solver_failed` | 0.04 | 0.03 | 11.71 | 0.12 | 106 | 132 | 26 | – |
| Transient, 9 times, 0.2 mm | 1 / 0 / 0 / 0 / 8 | `done` | 0.02 | 0.02 | 5.03 | 0.28 | 106 | 139 | 33 | 489,771 |
| Transient, 64 times, 0.5 mm | 1 / 0 / 0 / 0 / 8 | `done` | 0.01 | 0.01 | 2.23 | 0.20 | 106 | 134 | 28 | 129,827 |
| Transient, 128 times, 0.25 mm | 1 / 0 / 0 / 0 / 8 | `job:history_limit_exceeded` | 0.01 | 0.01 | 0.17 | 0.01 | 106 | 114 | 9 | – |

In this run, the over-fine documents (strip, film and the 10-degree sawtooth)
were refused in the job after 0.8 to 2.9 s of meshing, the 1-degree sawtooth
ended after 0.3 s and the concentric rings after 11.7 s; two runs on micrometre
meshes before it took 0.8 to 3.0 s, 0.3 to 0.4 s and 10.6 to 12.7 s. Earlier
local runs, before simcase meshed region documents in micrometres, refused the
over-fine documents, the 1-degree sawtooth among them, after 0.4 to 3.8 s on a
faster host and 0.7 to 5.3 s on this one, and ended the rings after 6.1 to 6.9 s
and 9.7 s. The slowest capability answer, 0.48 s, came while a job ran; during
validation it was at most 0.05 s (at most 0.06 s in the earlier runs). Result
bytes can differ by a few bytes between runs. These are one shared-host run's
numbers, not guarantees; a CI run records its own.
