# Verify a waveguide against the slab solution

**English** | [한국어](../locales/ko/pages/validation/slab-tutorial.md)

[Documentation home](../README.md)

Use a slab whose independent dispersion relation is known before interpreting a
new 2D waveguide. This exercise separates mesh error from the error caused by a
finite outer boundary. Run from the repository root in your activated environment:

```sh
python -m pip install -e packages/galerkin -e packages/galerkin-refsol
python examples/galerkin/slab_convergence.py
```

The [example](../../examples/galerkin/slab_convergence.py) solves a lossless vector
TE slab with film index 3.48, cladding index 1.444, thickness 0.22 µm and wavelength
1.55 µm. These are explicit constant indices, not wavelength-dependent built-ins.
The narrow strip is 0.1 µm wide. All lengths use µm and `k0` uses inverse µm.

## Match the reference problem

`refsol.slab.modes` solves the independent infinite-cladding dispersion relation.
For symmetric TE0, `κd = 2 atan(γ/κ)`, where
`κ = k0 sqrt(n_f² − n_eff²)` and `γ = k0 sqrt(n_eff² − n_clad²)`.
The fundamental reference is approximately **2.851738987**.

The vector strip has PEC side walls to select the x-directed TE family; the
remote top/bottom walls are also PEC. Natural side walls select a different
polarization in this vector setup. Do not copy vector boundary choices into a
scalar formulation without checking its contract. The structured mesh places
both material interfaces exactly on rows, avoiding a moving stair-step interface.

## Refine the mesh with the window fixed

`scale` refines both x and y. At 1.5 µm cladding padding on each side, a local run
produced the following rounded values; these are teaching observations, not new
universal acceptance thresholds.

| Scale | Effective index | Relative error against TE0 |
|---|---|---|
| 1 | 2.849397304 | 8.211e-4 |
| 2 | 2.851146825 | 2.076e-4 |
| 4 | 2.851590520 | 5.206e-5 |

The error drops by about four when both spacings halve. Refining only y can stall
because the vector edge basis couples directions through triangle diagonals,
even when the physical TE field is x-invariant. Keep the materials, wavelength,
window and mode selection fixed during this comparison.

## Enlarge the window with spacing fixed

The second series holds `scale=4` and increases padding, adding rows without
coarsening the mesh. Relative errors for padding 0.1, 0.5 and 1.5 µm are roughly
4.586e-2, 6.530e-5 and 5.206e-5. The narrow window changes the physical boundary
problem; a finer mesh alone cannot recover infinite cladding. At the larger
windows the remaining error is mostly the mesh floor in this example.

The script selects the highest real guided index between the cladding and film
indices, appropriate to this fundamental lossless control. This is not a general
mode tracker or proof that every candidate is physical. Check polarization and
field localization when adapting it. For lossy or leaky modes, use the
[waveguide interpretation guide](../results/waveguide-modes.md) and PML-specific checks.

## Apply the lesson to your model

Record the reference, mode identity, mesh spacings, window sizes and errors.
Choose a tolerance for your intended observable, then refine each numerical axis
separately. A successful TE slab check does not validate arbitrary strip geometry,
material data, absorption or radiation loss. Existing TE/TM polarization and
second-order acceptance checks live in
[the slab tests](../../tests/galerkin/test_slab_modes.py).
See [convergence](convergence.md) and [run records](../results/run-records.md).
