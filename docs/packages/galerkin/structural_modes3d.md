# Natural frequencies of a supported 3D solid

[한국어](../../locales/ko/pages/packages/galerkin/structural_modes3d.md)

Use the Python function `solve_structural_modes_3d` for small, undamped free vibrations about an unstressed configuration. It returns the lowest requested frequencies and their nodal mode shapes.

```python
from galerkin.mesh3d import box_mesh
from galerkin.structural_modes3d import solve_structural_modes_3d

mesh = box_mesh(0.12, 0.018, 0.012, 48, 6, 6)
clamp = {(n, a): 0.0 for n in mesh.boundary["x0"] for a in range(3)}
modes = solve_structural_modes_3d(
    mesh, youngs_modulus=70e9, poisson_ratio=0.0, mass_density=2700.0,
    prescribed_displacement=clamp, mode_count=2,
)
tip_shapes = modes.mass_normalized_displacement[:, mesh.boundary["x1"], :]
print(modes.frequency)
```

Use a conforming P1 tetrahedral mesh in metres. Young's modulus (Pa), Poisson ratio and mass density (kg/m³) may each be a scalar or a complete map from material region names. The [static elasticity](elasticity3d.md) component numbering and support rules apply. Prescribe zero displacement on the supported components and remove all six rigid motions of each disconnected solid. Remaining surfaces are traction-free. `mode_count` is a positive integer up to the number of free displacement components and defaults to one.

The solver assembles the isotropic elastic stiffness and consistent vector mass, eliminates supported components from both matrices and solves $K u = (2\pi f)^2 M u$. The real frequencies in `frequency` are in Hz, in ascending order. The array `mass_normalized_displacement` has shape (mode, node, xyz), units kg⁻¹ᐟ² and satisfies $U^T M U = I$ with modes as columns. Its amplitude follows this normalization. Its sign is arbitrary, and a repeated frequency defines a modal subspace. `relative_residual` reports $\|Ku-\lambda Mu\|/(\|Ku\|+\|\lambda Mu\|)$ on the free components of each mode. Values above 1e−6 raise an error. Forced response, prestress and damping require separate models.

## Cantilever verification

Run `python examples/galerkin/cantilever_modes_3d.py` from a checkout with the package installed. The rectangular cantilever is 120 × 18 × 12 mm with $E=70$ GPa, $\rho=2700$ kg/m³ and $\nu=0$. Its two lowest modes bend in the thickness and width directions respectively.

| Tetrahedra | First mode (Hz) | Second mode (Hz) |
|---:|---:|---:|
| 1,296 | 819.54 | 1,172.97 |
| 10,368 | 719.92 | 1,055.19 |
| 34,992 | 698.76 | 1,032.13 |
| Euler–Bernoulli slender-beam approximation | 685.43 | 1,028.15 |

The finest mesh differs from beam theory by 1.94% and 0.39%. The solid includes shear deformation and rotary inertia. Coarse linear tetrahedra overestimate bending stiffness in this example. A separate two-material benchmark compares the first five frequencies and mode shapes to independent scikit-fem assembly on the same mesh, and checks mass orthogonality and the free-component residuals.

[Runnable example](../../../examples/galerkin/cantilever_modes_3d.py) · [Independent comparison](../../../tests/galerkin/test_crosscheck_skfem_structural_modes3d.py)
