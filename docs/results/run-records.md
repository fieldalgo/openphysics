# Keep a reproducible calculation record

**English** | [한국어](../locales/ko/pages/results/run-records.md)

[Documentation home](../README.md)

A saved field is useful only when its model, code and assumptions can be recovered.
This example adds a small local record to the existing
[two-material wall](../packages/simcase/layered_wall_tutorial.md) result bundle.
After installing simcase, run from the repository root into a new or empty directory:

```sh
python examples/simcase/record_wall_run.py out/wall-recorded
```

The [script](../../examples/simcase/record_wall_run.py) solves the shipped wall
without changing its inputs. In addition to `model.json`, `summary.json`,
`fields.npz` and `log.txt`, it writes:

| File | Meaning |
|---|---|
| `input.json` | Exact source JSON bytes read before the solve |
| `run-record.json` | UTC start/end, Git commit and pre-run dirty flag, Python/platform, selected installed package versions, material records and file SHA-256 hashes |

The record's schema is example-specific, not a new simcase result contract.
Its hashes cover the saved files including `input.json`, excluding the record
itself. It intentionally says `convergence: not_checked`: a successful execution
is not convergence evidence. Check a bundle with:

```python
import hashlib
import json
from pathlib import Path

folder = Path("out/wall-recorded")
record = json.loads((folder / "run-record.json").read_text(encoding="utf-8"))
for name, expected in record["sha256"].items():
    actual = hashlib.sha256((folder / name).read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f"Changed result file: {name}")
print(record["git_commit"], record["git_dirty_before_run"])
print(record["convergence"])
```

## Know what the record does not prove

Git metadata describes this checkout; installed packages may come from a different
checkout or wheel. Use the documented editable installation or preserve the exact
wheel/environment lock used. The selected version list is not a complete dependency
lock or a guarantee of bitwise reproduction across platforms and numerical libraries.

A dirty flag of `true` means the commit alone cannot reproduce the working tree;
archive the relevant changes and untracked source inputs, or commit the work and
rerun. `null` means Git metadata was unavailable. Avoid modifying code or inputs
while a run is in progress. Hashes detect changes relative to this record; they
are not signatures, source authentication or proof of correct physics.

## Add the evidence for a numerical claim

Keep a short comparison table beside separate run folders:

| Item | Record explicitly |
|---|---|
| Physical claim | Quantity, location/time/mode, units and required tolerance |
| Material data | Source record and revision, wavelength/temperature range, any fit coefficients |
| External inputs | Mesh/data files and their hashes; database revision if used |
| Numerical settings | Mesh/window/time-step/PML settings and the input for each run |
| Independent comparison | Analytical relation or reference tool/version and observed error |
| Convergence | Values on successive refinements, change/error and the chosen acceptance criterion |
| Verification | Exact test command, exit status and optional skips; distinguish local checks from CI |

For this wall, use its series-resistance solution and mesh comparison in the
[tutorial](../packages/simcase/layered_wall_tutorial.md). For waveguides, start with
the [slab control](../validation/slab-tutorial.md). Do not label a run converged
merely because another example passed. Keep raw bundles alongside viewing exports,
and use [saved-field guidance](saved-results.md) for units and associations.
