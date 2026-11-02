# Touchstone input and explicit network comparison

**English** | [한국어](../../locales/ko/pages/packages/sipi/touchstone.md)

[Uniform-line networks](network.md) · [Frequency-line inputs](line_model.md)

`sipi.touchstone.loads_touchstone(text, ports=None, port_names=None)` reads a
supported single-ended S-parameter file into the existing immutable
`LineNetwork`. It performs no file or network I/O. Pass file text from the
application or browser; the engine does not infer physical port pairing from a
filename or comment. The format reference is the
[IBIS Touchstone 2.0 specification](https://ibis.org/touchstone_ver2.0/touchstone_ver2_0.pdf).
The parser is an independent implementation of the subset below.

```python
from pathlib import Path
from sipi.touchstone import loads_touchstone, compare_networks

# model is a calculated LineNetwork with a known physical port order.
measured = loads_touchstone(Path("coupon.s2p").read_text(encoding="ascii"),
                            ports=2, port_names=model.port_names)
comparison = compare_networks(measured, model)
print(comparison.max_abs_error)  # maximum absolute complex-S difference
```

The file must actually use the supplied port order. Naming the ports does not
rewire a fixture or de-embed its connections. The runnable
[synthetic example](../../../examples/sipi/compare_networks.py) needs no external
measurement file and does not claim measured material accuracy.

## Accepted input

| Input | Behavior |
|---|---|
| Version 1.0 | Requires caller `ports`, a positive integer. No filename inference. One/two-port records occupy complete individual lines; larger matrices can span lines. |
| Version 2.0 | Requires version, option line, port count, frequency count, network data and end marker. A caller port count must agree. Reference values can span lines. |
| Network samples | S only; RI, magnitude/degree-angle, or dB/degree-angle; Hz/kHz/MHz/GHz. Option defaults follow the standard; explicit option categories may appear in any order. |
| Port order | Two-port 1.0 uses 21_12; 2.0 requires an explicit 21_12 or 12_21 order. Larger full matrices are row-major. |
| Matrix form | Full or 2.0 lower/upper triangular. Triangular values are reflected by transpose, not complex conjugation. |
| References | Positive real, frequency-independent resistance; common option-line value or one 2.0 value per port. No implicit renormalization. |
| Text | ASCII, blank lines and `!` comments; 2.0 information blocks are opaque text, never executed or interpreted as port metadata. |
| Labels | Caller-supplied unique names in file order, otherwise neutral `port1`, `port2`, etc. |

The resulting frequencies are nonnegative, finite and strictly increasing;
DC is accepted. Complex S samples must be finite. Arrays are copied and
read-only. Imported data may describe an active, nonreciprocal or noncausal
network: a successful read is **not** a passivity or measurement certificate.

Unknown or duplicate keywords, unsupported versions, malformed counts, missing
matrix values, nonfinite numbers, negative magnitude-format values and reference
resistances, and content after the end marker are rejected. Additional option
lines are rejected, even though the general standard permits ignoring them.
Mixed-mode metadata, noise records and Y/Z/H/G data are unsupported and rejected;
they are not silently interpreted as single-ended S. This is a strict subset,
not a universal Touchstone importer. The existing single-ended Touchstone 2.0
export round-trips with explicitly supplied labels.

## Comparison contract

`compare_networks(measured, model, interpolation='none')` requires two
`LineNetwork` objects. Port names/order, basis and reference impedances must
match exactly. The caller must resolve any port permutation, calibration or
reference renormalization before comparison. A returned `NetworkComparison`
contains aligned `measured`, unchanged `model`, the chosen `interpolation`,
read-only `delta_s = model.s - measured.s` and scalar `max_abs_error` across all
frequencies and matrix elements. The factory validates these conditions;
direct dataclass construction is not a validation certificate.

By default, every model frequency must exist exactly in the measured grid;
a subset of measured samples is allowed. Missing samples raise an error.
`interpolation='linear'` explicitly interpolates real and imaginary S against
frequency in Hz, at model frequencies, **inside** the measured interval only.
No extrapolation is supported. Complex interpolation preserves neither a fitted
physical model nor sampling adequacy; refine the measured frequency grid near
rapid phase changes and resonances. It is not magnitude/phase interpolation.

Residuals include phase differences, so equal magnitudes can still disagree.
No material fitting, de-embedding, fixture removal, loss attribution or accuracy
claim follows from a small residual. Those require independent measurement and
model assumptions. Comparison itself does not mutate either input.

## Verification

Required tests live in `tests/sipi/test_touchstone.py`. Synthetic matrices are
intentionally nonreciprocal to expose an accidental two-port transpose. Tests
cover 1/2/3/4 ports, both versions, units/formats, both two-port orders,
triangular symmetry, explicit references, strict rejection and own-export
round trips. Format/reference criteria are absolute S difference <=1e-12,
exact frequencies, matching references; own export uses <=1e-14.

On Python 3.12.14, NumPy 2.5.4 and SciPy 1.18.1, independent scikit-rf 2.2.0
reads of five version/format/matrix combinations differed by at most
**1.24e-16** in S, below 1e-12. The reference is BSD-3-Clause, test-only and
never imported by shipped code. No new runtime dependency is added.
Comparison checks include exact-grid subsets, complex phase residuals,
analytically linear complex samples, mismatched labels/basis/references,
extrapolation refusal and calculated-line export/import. These are file-format
and numerical comparison tests, not a measured coupon validation.
