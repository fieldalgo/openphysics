# DC and AC conductor current diffusion

**English** | [한국어](../../locales/ko/pages/packages/sipi/conductor_diffusion.md)

[Cross-sections](overview.md) · [Uniform-line networks](network.md)

`sipi.conductor_diffusion.conductor_impedance` solves longitudinal currents
inside finite metal volumes and the surrounding magnetic field. It extracts
series impedance Z, resistance R and **total** inductance L, including the metal
interior. It supports DC and resolved skin/proximity current redistribution;
it does not extrapolate a high-frequency surface resistance to DC.

## Construct a volume mesh

```python
from sipi import microstrip
from sipi.conductor_mesh import mesh_conductor_section

section = microstrip(width=.4e-3, substrate_height=.5e-3, thickness=.1e-3,
                     eps_r=4, air_height=.5e-3, box_width=2e-3)
volume = mesh_conductor_section(section, ground_thickness=.1e-3, padding=2e-3,
                               metal_size=25e-6, far_size=.25e-3, grade=.1)
series = volume.impedance([0, 1e3, 1e5], conductivity=58e6, keep_fields=True)
print(series.R[:, 0, 0])  # ohm/m
print(series.L[:, 0, 0])  # H/m, including internal inductance
```

The runnable [example](../../../examples/sipi/conductor_diffusion.py) reports
resolution and conservation diagnostics as well. All lengths are metres;
frequencies are Hz, conductivity is S/m. `relative_permeability=1` is uniform
**everywhere**, including nonconducting regions.

`mesh_conductor_section` accepts a `CrossSection` with positive-thickness
rectangular or centred tapered traces. It preserves signal names/order.
All ground traces and box grounds belong to one common return group:

- Bottom/top grounds become finite plates of width `section.width`, extending
  outward from the dielectric box by `ground_thickness`.
- Side grounds become outward strips of that thickness, joining horizontal
  plates without overlapping their areas.
- The magnetic box extends `padding` beyond this construction on each side;
  its exterior nodes fix Az=0. Nonconducting regions and metal interiors both
  have conforming P1 triangles. Dielectric permittivity is not used here.
- `metal_size`, `far_size` and `grade` control target mesh sizes. They are not
  measured edge lengths or accuracy estimates. `0 < min_angle < 34`,
  `far_size >= metal_size > 0`, `grade >= 0`, positive thickness/padding apply.

The existing dielectric-only `CrossSection.mesh()` has holes for conductors
and cannot be passed as a metal-volume mesh. Its box boundary and the finite
plates above are different physical boundary contracts. Existing JSON v1/v2
save the cross-section only: **no volume-mesh JSON contract or automatic
matched-geometry dielectric/conductor extraction is provided by this API**.

## Direct mesh contract and formulation

`conductor_impedance(mesh, frequency, signals=..., ground=...,
conductivity=..., magnetic_boundary=...)` accepts a galerkin triangular mesh.
`signals` maps signal names to **triangle indices** in metal volumes; `ground`
is another triangle set. Different groups cannot overlap or touch at nodes.
Disconnected pieces of the reference share one longitudinal electric-field
constant. `magnetic_boundary` contains exterior **node indices** fixing Az=0;
other exterior edges have the zero natural magnetic flux condition. Choose the
boundary deliberately and test domain enlargement.

With exp(+jωt), uniform positive conductivity σ in metal (zero outside),
uniform permeability µ, and P1 basis φ, the assembled problem is

```text
Kij = integral grad(phi_i).grad(phi_j)/mu
Mij = integral sigma*phi_i*phi_j
Qig = integral sigma*chi_g*phi_i
Dgg = sigma*area_g
(K + j*omega*M) A - Q E = 0
D E - j*omega*Q.T A = I
```

For N signals, the current matrix S has identity signal rows and a final row
of −1 for the common return. Each column excites +1 A in one signal and −1 A
in the reference; other signals carry zero net current. The solver uses a
small current-constraint Schur system after the magnetic solve; Z=S.T E.
R=Re Z and L=Im Z/ω. At DC, E=D⁻¹S, K A=Q E, and L=A.T K A. This is a DC
energy limit, not division by zero. The DC resistance is the exact polygonal
area result `diag(1/(sigma*signal_area)) + 1/(sigma*ground_area)`.

Frequencies must be nonnegative and strictly increasing. At every positive
frequency the solver requires σ/(ωε₀) >= 1000 and **every actual metal triangle
edge <= skin depth**, δ=sqrt(2/(ωµσ)). This is a necessary resolution gate,
not a convergence certificate. High frequencies can require many triangles.
There is no automatic surface/volume switch or unverified interpolation.

## Results and propagation

For F frequencies, N signals and G=N+1 conductor groups:

| Field | Shape and units |
|---|---|
| `Z`, `R`, `L` | (F,N,N); ohm/m, ohm/m, H/m |
| `voltage_gradient` | (F,G,N), V/m for unit-current excitations |
| `current_integrals` | (F,G,N), A; checked against S |
| `skin_depth`, `max_edge_over_skin_depth` | (F,), m and dimensionless; DC gives infinity and zero |
| `current_error`, `power_error`, `magnetic_energy_error` | (F,), maximum current residual in A and relative energy residuals |
| `vector_potential` | Optional (F,nodes,N), Wb/m |
| `current_density` | Optional (F,triangles,N), A/m²; **element-centre** Jz, zero outside metal, not peak current |

`keep_fields=True` retains the two field arrays; otherwise both are None.
Results copy/freeze their arrays. Direct construction of the result dataclass
is not an independent validation certificate. The solve checks current error
<=1e-10 A, Joule/impedance and magnetic-energy/L relative residuals <=1e-9,
and impedance reciprocity <=1e-10. Local consistent P1 mass integration avoids
subtracting large global electric-field terms in the Joule check.

`series.network(C=..., G=..., length=..., z_ref=50)` propagates using this R
and **total L exactly once**. The caller must supply C/G for the same conductor
geometry/reference order and appropriate electric boundary. Do not add a
separate external L or silently mix finite plates with infinite box grounds.
The generic propagation test supplies explicit C/G; it is not an independent
dielectric extraction for these volumes.

## Validation and limits

The required tests are `tests/sipi/test_conductor_diffusion.py` and
`tests/sipi/test_conductor_mesh.py`. Measured on Python 3.12, NumPy 2.5.4,
SciPy 1.18.1, scikit-fem 12.0.2; the latter is test-only, with no new runtime
dependency.

| Case | Acceptance | Measured |
|---|---|---|
| Solid coax centre a=.5 mm, finite return b=1.5/c=2 mm, σ=58 MS/m; 100 Hz–1 MHz | Independent cylindrical Bessel solution; decreasing error, finest R/L/Z within 1% | 1 MHz R error 1.7341% → .44448% → .11380% for radial counts 16/32/64 and 256 angular cells; finest L error .01542% |
| Same coax at DC | Circle-to-polygon R error <.1%; L vs 100 Hz within 1% | R error .01004%; L passes |
| Two rectangular signals and return, DC | Exact polygon-area resistance matrix, relative 1e-10 | Pass; AC current redistribution, reciprocal/passive network also checked |
| Independent scikit-fem P1 forms, direct augmented solve, 10 kHz coax | Same-mesh Z relative difference <1e-9 | 9.40e-15; does not establish mesh convergence |
| Microstrip in example, metal size 50→25 µm and exterior refinement, 100 kHz | R/L mesh change <1% | R .51886357→.51887859 ohm/m; L 485.2423→489.1627 nH/m |
| Same fine microstrip, padding 2→4 mm | L change <2% | 489.1627→495.2537 nH/m; boundary error remains separate |
| Rectangle/taper, upper/lower/side/coplanar grounds | Metal areas and DC R relative 1e-10 | Pass |

The Bessel reference uses k=sqrt(jωµσ), solid-centre I0/I1 and finite-tube
I/K modified Bessel solutions with H(b)=I/(2πb), H(c)=0, plus external
jωµ ln(b/a)/(2π). It resolves skin depth across the metal; the independent
assembly comparison tests the algebra on a common mesh. These are separate
forms of evidence, not an accuracy promise for every PCB geometry.

This is a 2D longitudinal magnetoquasistatic model. Displacement current in
metal, radiation, roughness, temperature-dependent or different conductor
conductivities, nonuniform/nonlinear magnetic media, and 3D transitions are
not implemented. Refine both metal and exterior meshes and enlarge the
magnetic boundary for each new geometry/frequency range.
