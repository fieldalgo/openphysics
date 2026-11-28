# Forced vibration of a supported 3D solid

[한국어](../../locales/ko/pages/packages/galerkin/structural_harmonic3d.md)

Use `galerkin.structural_harmonic3d.solve_structural_harmonic_3d` to calculate the steady periodic displacement and elastic stress produced by a sinusoidal load. Each frequency solves a linear system on the tetrahedral mesh.

```python
import numpy as np
from galerkin.mesh3d import box_mesh
from galerkin.structural_harmonic3d import solve_structural_harmonic_3d

mesh = box_mesh(.12, .018, .012, 32, 4, 4)
clamp = {(n, a): 0.0 for n in mesh.boundary["x0"] for a in range(3)}
response = solve_structural_harmonic_3d(
    mesh, youngs_modulus=70e9, poisson_ratio=0., mass_density=2700.,
    prescribed_displacement=clamp, frequency=[0., 500., 700., 900.],
    traction={"x1": (0., 0., 1000.)}, stiffness_proportional_damping_coefficient=1e-5,
)
tip = response.displacement[:, mesh.boundary["x1"], 2].mean(axis=1)
print(np.abs(tip) * 1e6, np.angle(tip, deg=True))  # micrometres and degrees
```

Lengths are in metres. Supply Young's modulus (Pa), Poisson ratio and mass density (kg/m³) as scalars or named-region mappings, with zero prescribed displacement on the supports. Each connected solid must have its rigid motions restrained. The one-dimensional `frequency` input accepts nonnegative Hz in the order to be returned. A single Cartesian body force density (N/m³) and constant Cartesian tractions (Pa) on named exterior faces may have complex amplitudes. They apply across the sweep. Each force component is a peak phasor under the convention $f(t)=\operatorname{Re}(\hat f e^{-i\omega t})$.

With $\omega=2\pi f$, the solver uses $[K-\omega^2 M-i\omega C]\hat u=\hat F$. Rayleigh damping uses $C=\alpha M+\beta K$. The two nonnegative coefficients are `mass_proportional_damping_coefficient` ($\alpha$, s⁻¹) and `stiffness_proportional_damping_coefficient` ($\beta$, s). Omitting a coefficient or giving `None` sets its contribution to zero. At zero frequency the operator reduces to static elasticity. At an undamped natural frequency a unique steady response does not exist. Supply physical damping for a finite resonant response.

| Result | Shape | Meaning |
|---|---|---|
| `frequency` | (F,) | Hz in input order |
| `displacement` | (F,N,3) | Complex nodal displacement in m |
| `stress` | (F,T,3,3) | Complex symmetric elastic stress in Pa, tension positive |
| `reaction_force` | (F,N,3) | Dynamic support reaction in N, zero on free components |
| `relative_residual` | (F,) | Dimensionless equilibrium check on the free components |

Here F, N and T are the counts of frequencies, nodes and tetrahedra. Stress is recovered from the elastic strain. The support reactions also include inertia and Rayleigh damping. For a component driven by a real positive reference load, a positive displacement phase in this convention denotes a time lag. For each frequency the residual is divided by the sum of the norms of the stiffness, inertia and applied-load terms, including their damping weights. The calculation raises an error above a relative residual of 1e−6. This linear model assumes small strain about an unstressed configuration.

The runnable example applies a 1 N downward load to the end of a 120 × 18 × 12 mm cantilever. Its 10,368-tetrahedron mesh gives a first bending frequency of 719.92 Hz. With 2% damping specified for that mode, the mean downward tip displacement has an amplitude of 2.855 µm at zero frequency and 69.197 µm at the first natural frequency, where it lags the load by 89.92°. At 34,992 tetrahedra (refinement 9), the first frequency is 698.76 Hz. The corresponding static and resonant amplitudes are 3.033 and 73.518 µm. The tests also refine a rod against its analytical axial wave solution and compare displacement, elastic stress and support reactions on a two-material solid with an independent scikit-fem modal expansion.

[Runnable cantilever sweep](../../../examples/galerkin/cantilever_frequency_response_3d.py) · [Analytical tests](../../../tests/galerkin/test_structural_harmonic3d.py) · [Independent finite element comparison](../../../tests/galerkin/test_crosscheck_skfem_structural_harmonic3d.py) · [Natural frequencies and mode shapes](structural_modes3d.md)
