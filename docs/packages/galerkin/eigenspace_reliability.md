# Vector eigenspace reliability

`solve_modes` returns complex `et` and `ez` arrays. The physical fields are
`E_t = et` (edge line integrals) and `E_z = 1j * ez` (nodal values).
Reconstruct the original pencil vector as `[beta * et; ez]`, with
`beta = k0 * n_eff`, and apply the same PEC constraints used for the solve.
Do not discard imaginary coefficients in callers. A real material/pencil does
not require every basis returned for a degenerate eigenspace to be real.

## Failure and correction

On Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0, reproduce from the repository root:

```python
import numpy as np
from galerkin import disk_mesh, solve_modes
from galerkin.edge import assemble_edge_mass
from galerkin.assembly import assemble_mass

mesh = disk_mesh((4, 8, 24), (4, 4, 16), 32)
eps = mesh.by_region([1.45**2, 1.44**2, 1.44**2])
neff, space, et, ez = solve_modes(mesh, eps, 2*np.pi/1.50, 1.45, 10)
g = (et[:2].conj() @ (assemble_edge_mass(space, 1.) @ et[:2].T)
     + ez[:2].conj() @ (assemble_mass(mesh, 1.) @ ez[:2].T))
g /= np.sqrt(np.outer(g.diagonal().real, g.diagonal().real))
print(neff[:2], np.linalg.eigvalsh(g))
```

Before correction, the two HE11 fields were identical: normalized electric-L2
Gram eigenvalues `[0, 2]`, despite two effective indices `1.44619559` and small
individual eigenpair residuals. ARPACK returned independent complex directions
with conjugate shift-invert eigenvalues `5.17259007 +/- 8.75e-15j`.
Multiplying each vector by a nonzero phase preserves its span; subsequently
taking its real part does not. The former output conversion lost one direction.

The correction retains each complex eigenvector, with a unit-modulus phase
chosen by its largest coefficient. The phase uses `conj(pivot)/abs(pivot)` so
real vectors remain exactly real, including a negative pivot. Sorting, candidate
selection, eigenvalues, ARPACK controls and physical scaling are unchanged.
No nearby eigenpairs are mixed, whitened or jittered. The positive-real beta
extraction is unchanged; this correction does not add lossy-material support.

After correction the same fixture has normalized Gram eigenvalues approximately
`[0.02040816, 1.97959184]`. It is full rank but not an orthonormal basis in the
physical electric-L2 metric. No orthogonality or completeness guarantee is added.
Individual residuals alone cannot detect a missing direction in a degenerate
pair; test rank and the physical Gram as well. A numerically ill-conditioned
ARPACK input basis is preserved rather than repaired or silently replaced.

## Existing consumers

Simcase already stores complex transverse coefficients, physical complex Ez,
and complex centroid samples, with a common maximum-magnitude normalization.
Its JSON display uses separate real/imaginary lists and its NPZ retains complex
numeric arrays with `allow_pickle=False`. No schema or tracking change is needed.
For a real basis, Ez is in quadrature with Et; an arbitrary complex combination
inside a degenerate space need not have that componentwise phase relation.
The existing singleton sweep still rejects near-degenerate modes. This fix does
not implement subspace tracking or assign individual identities within a pair.

## Regression coverage

Run from the repository root (existing dependencies only):

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -c pyproject.toml -q -ra \
  tests/galerkin/test_eigenspace_reliability.py \
  tests/simcase/test_vector_eigenspace_reliability.py
```

The tests cover repeated 1.50/1.55/1.60 um solves, returned rank and electric-L2
Gram, each original free-DOF pencil residual, columnwise preservation of actual
ARPACK output, and supplied complex phases/order/exact-doublet basis changes.
Only a test double mixes vectors of a common eigenvalue; production never does.
The `1e-8` normalized Gram floor guards retained numerical rank for this fixture;
it is not a spectral clustering tolerance or an orthogonality requirement.

An independent test helper reuses `refsol.fiber.vector_modes` for Bessel roots,
then derives the +/-l electric fields from longitudinal J/K fields and Maxwell's
equations. With time dependence exp(+i omega t) and axial exp(-i beta z),
`Et = (-i beta grad Ez + i k0 zhat cross grad Hz)/(k0^2 n^2-beta^2)`.
Set Ez=f(r)exp(i l phi), Hz=h f(r)exp(i l phi), with continuous normalized
J_l/K_l profiles at the core radius. Continuity of Ephi determines h. Tests
independently check tangential E, normal dielectric displacement, divergence
and component Helmholtz equations away from the interface, for both signs of l.
The root oracle supplies no FEM fields. No external solver source is used.

FE/analytic cross-Grams use direct element polynomials with Duffy tensor Gauss
quadrature, separately per triangle. The polygon/circle interface difference
is retained. The worst principal-angle sine decreases on scale 1/2/3 meshes:
approximately `0.09903 / 0.04962 / 0.03309` at 1.50 um. Quadrature orders 4 and 6
are compared; analytic complex unitary basis rotations must leave the error
unchanged. The first-order field convergence guard is fixture-specific; existing
second-order index convergence and physical TE/TM/HE splitting tests remain.
The fixed radius 24 um comparison does not establish infinite-domain convergence,
cutoff completeness, or accuracy for every fiber family.
