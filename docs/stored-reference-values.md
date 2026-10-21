# Stored reference values

**English** | [한국어](locales/ko/pages/stored-reference-values.md)

Stored results let tests compare with an independent tool without installing or
running it. They are code-to-code evidence, never analytical acceptance or mesh
convergence evidence. No physics value records are included yet.

## Layout and use

Records live at `tests/<import>/reference_values/<tool>/<case>.json`. Reproducible
pip-only generators may live beside them with hash-pinned requirements (VCS
sources pinned to a full commit). Otherwise their public location is the literal
`private research repository`. Only numeric outputs and provenance belong here,
never third-party code or data.

`tests/_support/reference_loader.py` is an unshipped helper, available through the
root pytest `pythonpath` setting. Do not add `tests/conftest.py`: that can make
`tests/refsol` shadow the absent answer-key package. Only modules named
`test_reference_*.py` or `test_crosscheck_*.py` may import the loader. The flat
consumer-copy lists in the distribution/platform tools must never include them.
The full installed suite copies the helper, records and root configuration.

A consumer lists its repository-relative path in `consumers`, calls
`load_reference` with an expression containing the record's literal filename,
and builds the problem from `ref.inputs`. Numeric arrays are in `ref.arrays` and
are read-only. Compare with gates owned by the test; do not store gates in data.
Call `make_record(..., stored=ref)` from `tests/galerkin/crosscheck.py`, selecting
the exact `tool` and its recorded `tool_discretization`. Case and physics must
match. The tool's installed metadata is never queried. The emitted record uses
`wall_time_s.reference = null` and carries historical generation cost and hashes
under `stored_reference`; it never claims the reference tool ran now.
Different-discretization comparisons are report-only. Existing analytical and
same-discretization criteria remain unchanged.

## Contract v1

The schema is `openphysics.reference-values/1`. Wavebit uses its own namespace
with the same hash conventions. Every record has these fields:

| Fields | Meaning |
|---|---|
| `case`, `physics`, `comparison`, `role` | Identity; comparison is `same-discretization`, `different-discretization` or `structure-oracle` |
| `references` | Nonempty list: `tool`, exact `version`, `build`, `modified` (`value`, `description`), `license` (SPDX matching the inventory), `source`, `install` (`kind`, `command`, `lock`), `settings`, `discretization`, `arrays` (name globs), `execution`, `independence` |
| Reference independence | `execution`: `separate-process`, `in-process` or `unknown`; `independence`: `product_loaded`, `inputs_from_product` |
| `generator` | `path`, LF-normalized `sha256`, `command`, `product_commit`, `clean` |
| `generated_utc`, `environment` | UTC timestamp; environment has `python`, `numpy`, `os`, `cpu`, `dtype`, `backend/device` |
| `cost` | `compile_s`, `compute_s`, `wall_time_s`, `peak_rss_mb`, `threads`, `not_measured` |
| `inputs` | Inputs used to reconstruct the case |
| `matched`, `not_matched`, `reference_self_check`, `failed_or_discarded`, `not_run` | Lists preserving matched conditions, discrepancies, self-checks, failures and missing execution |
| `values` or `payload` | Exactly one representation, described below |
| `values_sha256`, `content_sha256` | Numerical and input/content hashes |
| `consumers` | Nonempty list of tracked test paths that explicitly load this record |
| `provenance_status`, `not_recorded` | `complete` or `reconstructed`; map from every null field's dotted path (list indices as `[0]`) to its reason and consulted source |
| `regeneration` | List of `date`, `mode`, `reason`, `previous_content_sha256`, `content_sha256`, `tool_version`, `review`, `approval` |

Inline `values` is a list of `{name, unit, dtype, shape, data}`. Use explicit
NumPy dtype strings, such as `<f8`. Complex arrays replace `data` with `real`
and `imag` lists and use a complex dtype such as `<c16`. All arrays must be
finite and covered by exactly one reference's globs. `metadata` is reserved.
A payload has `file` (relative to the record), `format` (`npz` or `json`),
`file_sha256` and `arrays` (names). JSON payloads use the inline list format;
NPZ files contain only numeric arrays and are loaded without pickle.

Limits: record 1 MiB, payload (also expanded NPZ) and total array bytes 512 KiB,
repository total 10 MiB. Paths cannot escape their directory. Strings must not
contain absolute/home/drive paths, private coordination paths, session URLs or
private research repository names. Use `private research repository` instead.
`gate` and `tolerance` keys are forbidden at every depth. AGPL references must
be unmodified. Unknown metadata uses null with a `not_recorded` explanation;
unknown versions or unknown numerical content cannot become validated oracles.

## Hashes and updates

`values_sha256`: for arrays sorted by name (excluding `metadata`), append UTF-8
name, NUL, `dtype.str`, NUL, `repr(shape)`, NUL, C-order bytes to SHA-256.
`content_sha256`: SHA-256 of UTF-8 canonical JSON of
`{"inputs": inputs, "values_sha256": values_sha256}`, with `sort_keys=True`,
`separators=(",", ":")`, `allow_nan=False`, `ensure_ascii=False`.
Payload and generator file hashes cover bytes, normalizing CRLF/CR to LF for text.

The shared vector `x=[0.1,0.2]` (`<f8`), `z=[1+2j]` (`<c16`) gives
`5b1e6695fa1d3df431519ed94c7096a82b5d1ca875872559f67e1cab86e1ce2e`.
With inputs `{"eps":{"real":4.0,"imag":-0.04},"modes":2}`, the content hash is
`63ad3eaeaed8bee68b8cc4ff62997c2fddd92f443327e07d926189d5fde7dea0`.

Generators must default to compare mode: temporary output, per-array diff,
nonzero exit on differences, no writes to tests. `--restamp --reason` may only
change provenance, retaining identical input/content and value hashes.
`--rebaseline --reason` requires the pinned tool version and a reviewed change
showing per-key differences; never regenerate to make a failing test pass.
Each regeneration entry records both old and resulting content hashes; adjacent
entries must join and the final result must equal the record's current hash.
Approval text contains a maintainer/date description, not private links.
No generator or rebaseline command is provided by the reader.

## Auditing

`python -m pytest -q tools/tests/test_reference_values.py` checks the tracked
repository, inventory licenses, generators, consumers, orphan payloads, copy
boundaries, shared vector and deliberate corruptions. Runtime loading repeats
schema, finite-value, size and hash checks in installed suites without `tools/`.
The `external_tools` inventory block describes separately executed tools using
`spdx`, `url`, and `reference` (`mode`, `execution`, `modules`, `imported_by`,
`values`, `generators`, `light`). It does not install or admit dependencies.
NGSolve is stored-only because reported cases reach 63 seconds and 1.8 GB;
its value list is empty until a reviewed record is added. New tools and their
records must land together. Import-zone enforcement is a separate check;
this audit only enforces the loader and flat-copy boundary.
