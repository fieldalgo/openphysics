# 3D heater pulse from DC to thermoelasticity

**English** | [한국어](../../locales/ko/pages/packages/galerkin/transient_heater_3d.md)

For temperature-dependent resistance at fixed voltage, see the [feedback example](temperature_dependent_heater_3d.md).

Run `python examples/galerkin/transient_heater_3d.py` from the repository root.
The [example](../../../examples/galerkin/transient_heater_3d.py) uses a single
static `Mesh3D` in metres. It solves both DC states, passes the corresponding
elementwise Joule power density (W/m³) to the transient heat solver in each
interval, and supplies the computed nodal temperature history (K)
to the quasi-static thermoelastic solver. The pulse starts at 1 s and ends
at 3 s. Both switches are time grid points. Each heat step sees the source at
its interval midpoint and each output at a switch includes the interval
that ended there. The example also reports results immediately after each
switch and at 7 s.

The slab is 0.20 m long with a square 0.05 m cross section. Its ends stay at
300 K, including the initial state, and the sides are thermally insulated.
The 2 V energized state with σ = 10 S/m gives Q = 1000 W/m³ and 0.5 W.
Thermal conductivity is 2 W/(m K) and volumetric heat capacity is
1000 J/(m³ K). The solid is fixed axially at both ends and transversely at
every node. With E = 70 GPa, ν = 0, α = 12 × 10⁻⁶/K and stress-free
temperature 300 K, heating produces compressive axial stress. Heat loss
through the ends after cutoff reduces the compression.

## Independent slab solution

For the rise θ = T − 300 K, the one-dimensional equation is
C θₜ − k θₓₓ = Q I(1 ≤ t < 3) with zero end and initial values. Only odd
sine modes contribute. For odd n, put λₙ = (k/C)(nπ/L)²,
a = clamp(t − 1, 0, 2) s and b = max(t − 3, 0) s. The coefficient of
sin(nπx/L) is

```text
Aₙ(t) = [4Q / (C nπ λₙ)] [1 − exp(−λₙ a)] exp(−λₙ b)
```

The spatial mean is Σ 2Aₙ/(nπ). The two fixed ends imply zero mean axial
strain. At ν = 0, the mean axial stress is −Eα mean(θ) (Pa), and the
left and right support forces are −Aσₓₓ and +Aσₓₓ (N), where A is the
cross-sectional area. The exact fields and means come from the independent
Fourier calculation, which takes time and position arrays.

The regression limits the maximum error over the full nodal temperature,
mean axial stress and end-force histories to 6% of each peak exact signal.
It checks continuous temperature at the switches, cooling and stress
relaxation, and independently refines the axial mesh and the time step.
The mesh study uses 4, 8 and 16 axial cells with a common 1/64 s step.
The time study uses 1/4, 1/8 and 1/16 s on a 24-cell axial mesh.
Each has one cell in each transverse direction and is evaluated on shared
output times. Run the reference independently with
`python -m pytest -q tests/galerkin/test_transient_heater_3d.py -k reference`.

In the integrated example, the 2 s pulse deposits 1 J. At 3 s the
midplane rise is 1.52695 K (reference 1.53838 K) and the mean axial
stress is −0.87585 MPa (reference −0.88575 MPa). At 7 s they have
fallen to 0.22860 K and −0.12185 MPa. The full-history errors are
0.94% for temperature and 1.12% for both stress and end forces.

For plotting, the example exposes `solve_heater_history()` returning
`(mesh, electric, heat, solid)`, `slab_reference(time, x)` returning
`(rise, mean_rise)`, and `axial_history(mesh, solid)` returning
`(mean_axial_stress, left_right_reaction)`. Actual fields are available in
`heat.temperature` and `solid.steps`, with their corresponding time arrays.
