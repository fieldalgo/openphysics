# Public-reference benchmarks: bimetal strip and NAFEMS T4

**English** | [한국어](../../locales/ko/pages/packages/galerkin/public_benchmarks.md)

Two problems whose answers are published and can be checked by anyone, solved
with the existing `galerkin` steady heat and prescribed-temperature mechanical
stages and compared with exact references and mesh refinement. No engine code
changed; the references are the new modules `refsol.bimetal` and
`refsol.thermal_convection`, which import no engine code. The gates are in
`tests/galerkin/test_public_benchmarks.py`; the picture is drawn by
`examples/galerkin/public_benchmarks.py`.

![Bimetal strip, NAFEMS T4 and mesh convergence](../../gallery/public_benchmarks.png)

## Bimetal strip (Timoshenko 1925)

**Reference.** S. Timoshenko, "Analysis of Bi-Metal Thermostats",
J. Opt. Soc. Am. 11(3), 233-255 (1925),
[doi:10.1364/JOSA.11.000233](https://doi.org/10.1364/JOSA.11.000233). Two
bonded layers of thickness t1, t2 (moduli E1, E2, expansions alpha1, alpha2)
heated uniformly by dT bend with the curvature

    kappa = 6 (alpha2 - alpha1) dT (1+m)^2 / (h [3 (1+m)^2 + (1+m n)(m^2 + 1/(m n))]),
    m = t1/t2, n = E1/E2, h = t1 + t2.

`refsol.bimetal.curvature` derives kappa from the zero axial force and zero
bending moment of the beam cross section (any number of layers);
`timoshenko_curvature` is the closed form above, `villarceau_curvature` the
equivalent form printed in the Wikipedia article
[Bimetallic strip](https://en.wikipedia.org/wiki/Bimetallic_strip) (accessed
2026-10-22, attributed there to Villarceau 1863), and
`stoney_uniaxial_curvature` the beam form of Stoney's relation
kappa = 6 sigma_f t_f/(E_s t_s^2) (G. G. Stoney, Proc. R. Soc. Lond. A 82,
172-175 (1909), [doi:10.1098/rspa.1909.0021](https://doi.org/10.1098/rspa.1909.0021)).
`tests/refsol/test_bimetal_reference.py` checks that the three forms agree to
1e-10 on random layer data, that the thin-film limit tends to Stoney's form,
and that `strip_fields` carries no section force or moment, is continuous at
the interface, has the plane-stress strains (finite differences) and the
closed-form curvature on its x = 0 face. The equibiaxial plate form of Stoney's
relation with (1 - nu_s) is a plate result and is not represented here.

**Why the beam formula is an exact 2D reference.** The beam field
eps_yy = a + b x, sigma_yy = E_i (a + b x - alpha_i dT), sigma_xx = sigma_xy = 0
satisfies equilibrium, compatibility, interface continuity and the traction-free
faces exactly in plane stress. On the end faces it leaves a self-equilibrated
axial stress. With that stress applied as the end traction the beam field is the
exact plane-stress solution, so the P1 solution must converge to it at the
usual rates. With traction-free ends it is the Saint-Venant solution: the
difference is confined to a few thicknesses from each end.

**Case.** Layer 1: 0.5 mm, E 200 GPa, nu 0.3, alpha 12e-6 1/K (steel-like);
layer 2: 0.5 mm, E 70 GPa, nu 0.33, alpha 23e-6 1/K (aluminium-like); length
20 mm (20 thicknesses); dT = +100 K from Tref = 293.15 K; plane stress;
handbook-type example constants, not certified data. kappa = 1.53425 1/m
(radius 0.652 m). Mesh `layered_rectangle_mesh([t1, h], L, [n, n], 40 n)`:
2n square cells across the thickness, 40n along the strip. Supports fix u at
(0, 0) and u_x at (0, L); the reference uses the same rigid-body choice. The
curvature of the solution is -2 times the quadratic coefficient of a parabola
fitted to u_x on the x = 0 face nodes (whole face with the exact end traction,
central half with free ends).

Exact end traction (`test_bimetal_strip_converges_to_the_timoshenko_field`,
`slow`), local run 2026-10-22 (macOS, Python 3.12, numpy 2.5.4, scipy 1.18.1):

| n | triangles | displacement L2, relative | order | stress L2, relative | order | curvature error |
|---|---|---|---|---|---|---|
| 1 | 160 | 4.96e-1 | | 1.03 | | -51.2 % |
| 2 | 640 | 2.01e-1 | 1.30 | 6.85e-1 | 0.58 | -20.8 % |
| 4 | 2 560 | 5.97e-2 | 1.75 | 3.81e-1 | 0.85 | -6.15 % |
| 8 | 10 240 | 1.57e-2 | 1.93 | 1.97e-1 | 0.96 | -1.61 % |
| 16 | 40 960 | 3.98e-3 | 1.98 | 9.91e-2 | 0.99 | -0.41 % |

Gates (n = 1, 2, 4, 8): displacement and curvature orders >= 1.6 and stress
order >= 0.8 on the last two intervals; curvature error and displacement error
at n = 8 <= 2.5e-2; support reactions <= 1e-9 E alpha dT h. The quick test
(`test_bimetal_closed_form_and_quick_mesh`, n = 4, both end conditions) gates
the central-half curvature at 8e-2. The coarse meshes are far off because P1
triangles are stiff in bending (two elements across the thickness at n = 1);
the error falls at second order, as the figure shows.

Free ends (`test_free_ended_strip_has_the_timoshenko_curvature_away_from_the_ends`,
`slow`): the central-half curvature of the free-ended strip equals that of the
exact-traction strip to 2e-10 relative at n = 4 and 8 (gate 1e-4), so on this
20-thickness strip the end effect does not reach the central half; its error
against the closed form is the same -6.15 % and -1.61 %. The whole-face fit and
the global L2 errors of the free-ended strip do see the end zones (displacement
L2 5.8e-3 instead of 4.0e-3 at n = 16) and are reported, not gated.

## NAFEMS T4: two-dimensional heat transfer with convection

**Reference.** A 0.6 m by 1.0 m rectangle, conductivity 52 W/(m K), no source;
the edge y = 0 at 100 °C, the edge x = 0 insulated, the edges x = 0.6 m and
y = 1.0 m convecting with h = 750 W/(m² K) to 0 °C; target temperature 18.3 °C
at (0.6, 0.2) m. The statement and target are reproduced from two public
benchmark documents that cite NAFEMS: DIANA FEA,
[Two-Dimensional Heat Transfer with Convection](https://tutorials.dianafea.com/2DHeatTransferConvection.pdf)
(citing NAFEMS, *The Standard NAFEMS Benchmarks*, 1990) and FEATool
Multiphysics [ex_heattransfer4.m](https://www.featool.com/doc/ex__heattransfer4_8m)
(citing A. D. Cameron, J. A. Casey and G. B. Simpson, *Benchmark Tests for
Thermal Analysis*, NAFEMS, 1986); both accessed 2026-10-22. Only the published
numbers are reproduced ([NOTICE](../../../packages/galerkin-refsol/NOTICE)).
The target is quoted to 0.1 °C.

`refsol.thermal_convection.series` is the separation-of-variables solution of
the same boundary-value problem: cos(lam_n x) with lam_n tan(lam_n W) = h/k,
the y dependence satisfying the top Robin condition, coefficients from the hot
edge. It gives T(0.6, 0.2) = 18.2538 °C, inside the quoted precision of the
NAFEMS value. `tests/refsol/test_thermal_convection_reference.py` checks the
eigenvalue equation, Laplace's equation and Fourier's law by finite
differences, the Robin, insulated and hot-edge conditions, geometric
convergence of the interior values, and linearity in the temperature offset.

**Case.** `rectangle_mesh(0.6, 1.0, 6n, 10n)`, square cells of 0.1 m / n; hot
edge as Dirichlet 373.15 K; `convection={'right': (750, 273.15), 'top': (750, 273.15)}`;
the untagged left edge is insulated by default. The target point is a mesh node
for every n.

| n | triangles | T(0.6, 0.2), °C | error vs series, °C | order | L2 error, relative (whole) | order | L2 error, relative (y >= 0.1 m) | order |
|---|---|---|---|---|---|---|---|---|
| 1 | 120 | 17.2813 | -0.972 | | 1.85e-2 | | 7.53e-3 | |
| 2 | 480 | 18.0048 | -0.249 | 1.97 | 6.12e-3 | 1.59 | 1.97e-3 | 1.93 |
| 4 | 1 920 | 18.1936 | -0.0602 | 2.05 | 1.95e-3 | 1.65 | 5.02e-4 | 1.97 |
| 8 | 7 680 | 18.2389 | -0.0149 | 2.02 | 6.00e-4 | 1.70 | 1.26e-4 | 1.99 |
| 16 | 30 720 | 18.2500 | -0.00371 | 2.00 | 1.79e-4 | 1.74 | 3.15e-5 | 2.00 |
| 32 | 122 880 | 18.2528 | -0.00093 | 2.00 | 5.30e-5 | 1.76 | 7.89e-6 | 2.00 |

Gates (`test_nafems_t4_converges_at_second_order_away_from_the_hot_corner`,
`slow`, n = 2, 4, 8, 16): point and far-field L2 orders >= 1.8 and whole-domain
L2 order >= 1.5 on the last two intervals; point error at n = 16 <= 1e-2 °C and
far-field L2 error <= 1e-4. The quick test (n = 8) gates the point value at
2.5e-2 °C from the series and at the quoted precision 0.1 °C from the NAFEMS
value. The whole-domain L2 rate stays below two because of the corner at
(0.6, 0), where the 100 °C edge meets the convecting edge; away from the hot
edge the rate is two.

## Scope and limits

- Plane stress, small strain, uniform temperature, P1 triangles; the strip
  reference is a beam field and holds for plane stress only.
- The NAFEMS target is a published number quoted to 0.1 °C; the acceptance
  gates use the exact series of the stated problem, and the published value is
  checked at its quoted precision.
- Agreement with these references is evidence for the heat and mechanical
  stages on these problems. It says nothing about temperature-dependent
  materials, contact, plasticity, creep or any lifetime quantity.

## Reproduce

```bash
python -m pytest -q tests/refsol/test_bimetal_reference.py tests/refsol/test_thermal_convection_reference.py tests/galerkin/test_public_benchmarks.py
python examples/galerkin/public_benchmarks.py out-dir        # figure and numbers; --quick for coarse meshes
```
