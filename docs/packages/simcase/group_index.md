# Group index of a single study

**English** | [한국어](../../locales/ko/pages/packages/simcase/group_index.md)

A wavelength sweep already returns the group index `n_g = n_eff − λ0 dn_eff/dλ0`
([overview](overview.md#tracked-vector-wavelength-sweeps)). A single `em.modes2d` study
returns it when the document asks for it:

```json
"results": {"group_index": {"wavelength_step": "1 nm"}}
```

## Contract

- **Definition.** n_g = n_eff − λ0 · dn_eff/dλ0 by a central difference in the vacuum
  wavelength. The run solves its own λ0 point as usual, so `effective_index` and the fields
  are those of the same document without the option. It then solves the same mesh at
  λ0 − Δλ and λ0 + Δλ. Each material is evaluated at each wavelength, exactly as at the
  points of a sweep, so material dispersion is included. A side wavelength outside a
  material's valid range fails the run with the material's own message.
- **Matching.** Each λ0 mode is matched to a candidate of each side solve with the tests of
  the sweep's resolved-mode tracker: `electric-l2-assignment-v1` for vector results,
  `scalar-l2-assignment-v1` for scalar ones. The tests are:
  - the optimal assignment of the normalized squared L2 overlaps;
  - overlap ≥ 0.8;
  - full-assignment margin ≥ 0.1;
  - the match is not the last candidate of a full search;
  - no other candidate, and no other λ0 mode, lies within 1e-5 in n_eff.

  The side solves search the sweep's candidate count, max(2 mode_count, mode_count + 4).
  These are the tracker's default settings. `study.tracking` is not read by a single study.
  The λ0 solve is the run's own, with mode_count candidates, so at λ0 the degeneracy test
  sees only the requested modes and there is no search-boundary test. A requested mode
  close to an unrequested λ0 candidate is caught only where it is still close at a side
  wavelength, which the side solves test against all their candidates. This is weaker than
  the middle point of a sweep.
- **Difference.** The three matched values go through the same second-order `np.gradient`
  as a tracked sweep, on the kernel's micrometre wavelengths λ0 ∓ Δλ. Those are
  `float(exact metres × 10⁶)` of the written values, as a sweep's values are.
- The run checks that the materials are lossless at the three wavelengths before any solve.
- **A mode that is not matched** on either side has no value: `null` in `summary.json`,
  NaN in `fields.npz`. Its reason names the side wavelength and the failed test. The run
  does not fail.

  A sweep fails as a whole in the same case. The single-point option reports the mode it
  cannot identify and keeps the others. The fiber's degenerate HE11 pair is the common
  example.

## Document

| Key | Form | Default | Allowed |
|---|---|---|---|
| `results.group_index` | object | absent: no group index | a `single` study of a lossless entry without `bend` (with `pml` the value is complex) |
| `results.group_index.wavelength_step` | length with its unit (`"1 nm"`, `"0.001 um"`, `{"value": .., "unit": ..}`) | `"1 nm"`, echoed in `defaults_applied` | 1 pm ≤ Δλ ≤ λ0 / 20 (exact), else `E-DOMAIN` |

The key is refused with `E-CONTRACT` in these cases:

- with a sweep (a wavelength sweep already gives `group_index`);
- with `bend`;
- at run time, when a material is lossy at any of the three wavelengths.

Multiphysics documents refuse it as an unknown `results` key (`E-KEY-UNKNOWN`). Readers
before this release refuse it by name:

```text
results.group_index: unknown key "group_index" in results. … (E-KEY-UNKNOWN)
```

## Result

- `group_index`: the existing key and registry quantity, `(points = 1, modes)`, unit 1, in
  `summary.json` and `fields.npz` (`location` `study_points_modes`).
- `group_index_method`, in `summary.json` only:

```json
{"method": "central_difference", "wavelength_step": {"value": 1e-09, "unit": "m"},
 "tracking": "electric-l2-assignment-v1", "reasons": [null, "vacuum_wavelength 1.549 um: …"]}
```

`reasons` has one entry per mode: `null` when the mode has a value, else the reason.

**Open boundary (PML).** With `pml` (no `bend`) n_eff is complex, and so is n_g = n_eff −
λ0 dn_eff/dλ0: `group_index` is then `{"re", "im"}` like `effective_index`. The side solves keep
the entry's PML and target. The matching uses the tracker's physical weights, so the overlaps are
taken on the physical window. The first match is near the target, and the edge of the search is
the candidate farthest from the target, as in a tracked PML sweep. The null rules are the same.
A complex n_g is a spectral derivative, not an energy velocity. Validation (slice P3, V11) uses
the leaky slab of the open-boundary checks: 220 nm Si over 500 nm silica on Si, PEC side walls,
TE, a 1 nm step. The reference is the central difference of
`refsol.lossy_slab.substrate_leaky_mode` at 1549 and 1551 nm with physmat's dispersion,
3.706654 − 2.688e-4i.
- At the default mesh n_g is 5.24e-3 low in Re and 2.7 % off in Im. Almost all of it is the error
  of n_eff itself: Re n_eff is −4.76e-3 off. The error decreases on each halving of the mesh.
- dn_eff/dλ0 is within 1e-3 relative.
- The registered 1e-3 / 2 % gate at the default mesh therefore failed and was replaced after the
  result ([`test_open_boundary_group_index.py`](../../../tests/simcase/test_open_boundary_group_index.py)).

`field_layout` and every other key are unchanged. Results without the option are those of
earlier releases. The log lists the side wavelengths, each null mode with its reason, and
the values. A run takes about three times the solve time of the single point, slightly
more because the side solves search more candidates.

Not computed:

- the field-integral group index;
- lossy modes, and open (PML) modes of a bend;
- coupled multiphysics entries;
- a sweep over any parameter.

## Validation

Registered before the implementation, `tests/simcase/test_group_index_single.py`, Linux,
Python 3.12.

| # | Check | Result |
|---|---|---|
| V8 | 220 nm physmat:Si film spanning the PEC window in physmat:SiO2, λ0 1.55 µm, Δλ = 10 nm, against the central difference of `refsol.slab` TE n_eff at 1.54, 1.55 and 1.56 µm with physmat's indices (n_g = 3.706704). Film element h, background 5h, grading h to 5h, h = 24, 12, 6 nm. Gate: ≤ 3e-3 at 6 nm and strictly decreasing. **Not blind**: the sweep's errors on this mesh family were measured before registration | 3.72e-3, 8.89e-4, 2.29e-4 |
| V9 | the option against the middle point of today's sweep over λ0 ∓ Δλ: tracked vector sweep (Δλ 1 and 10 nm), untracked scalar sweep with mode_count = the option's candidate count. Gate: 1e-12 relative | passed. The scalar fixture was changed after its first result: with the vector fixture's PEC side walls the scalar window is cut off (n_eff = 0), so it now has PMC side walls |
| V10 | round fibre, a = 1.3 µm, core n² = 1 + 1.1 λ²/(λ² − 0.01 µm²) (the Sellmeier core of refsol's fibre tests), cladding 0.9 × core, PEC box ±5a, mode_count 3, Δλ = 1 nm, against `refsol.fiber`'s implicit dispersive group index. Core element h, background 4h, h = 0.16, 0.08, 0.04 µm. Gate: TE01 ≤ 2e-3 relative at 0.04 µm and strictly decreasing; HE11 null with a reason or within the same bound. Blind | TE01 6.18e-4, 2.88e-4, 1.17e-4. HE11: matched at 0.16 and 0.08 µm (relative error ≤ 2e-5), null at 0.04 µm, where the mesh splits the pair by 2.9e-6, below the 1e-5 tolerance: "vacuum_wavelength 1.55 um: near-degenerate with another requested mode" |
| M5-f | refusals for sweeps, PML, bend, coupling and lossy materials; step range edges; unknown keys by name; the option adds only `group_index`, `group_index_method`, their field-map entries and the step default; the λ0 arrays are bit-identical; HE11 alone (degenerate partner) gives null with a reason and the CLI exits 0; a failed side solve gives null with a reason; three solves at the exact side wavelengths | passed |

The refsol fibre tests use cladding 0.993 × core. There, TE01, TM01 and HE21 lie within
about 1e-5 of one another, inside the tracker's degeneracy tolerance. That fixture would
test only the refusal. V10 therefore uses a stronger contrast.
