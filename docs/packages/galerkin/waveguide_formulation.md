# Waveguide formulation: modes, derivatives, coupling and the SI/PI path

**English** | [한국어](../../locales/ko/pages/packages/galerkin/waveguide_formulation.md)

[galerkin overview](overview.md) · [Theory and numerical methods](../../theory/index.md) · [Electromagnetics route](../../physics/electromagnetics.md)

This page reads the waveguide cross-section solvers as mathematics: what
equation is discretised, with which elements, what the eigenvalue is, how the
effective index and its derivatives are recovered, and where the signal- and
power-integrity package `sipi` takes a different road through the same engine.
Every formula is written as the code implements it, with the module and function
beside it; signs, normalisations and branch choices are the implemented ones,
not a textbook's. The normative contracts, limits and measured validation stay
in the pages this one links to: this page adds no accuracy claim and no new
validation result.

## 1. Problem statement and notation

A guide that does not change along z carries fields of the form

    E(x, y, z, t) = [E_t(x, y) + zhat E_z(x, y)] exp(+i omega t - i beta z)

(`packages/galerkin/src/galerkin/waveguide.py`, module docstring; the same phasor
is stated in [absorbing modes](../simcase/lossy_modes.md) and
[modal coordinates](modal_coordinates.md)). The cross-section Omega is a 2D
domain meshed with P1 triangles (`galerkin.mesh.Mesh`); lengths are in the mesh
length unit, and `k0` is given in that inverse unit. The source-free Maxwell
equations reduce to

    curl ( mu_r^-1 curl E ) - k0^2 eps_r E = 0,     grad = grad_t - i beta zhat.

| Symbol | Meaning | In the code |
|---|---|---|
| `E_t`, `E_z` | transverse and longitudinal electric field of one mode | `et` (edge line integrals of `E_t`), `ez` with `E_z = 1j * ez` (`waveguide.py::solve_modes`) |
| `eps_r` | relative permittivity, scalar or one value per triangle, real or complex | `eps_r` of `solve_modes`, `assemble_mode_system`; `eps_tri` in simcase |
| `mu_r` | relative permeability, scalar or per triangle, real or complex; enters only as `1/mu_r` | `mu_r` (default 1.0); `inv_mu` in `waveguide.py::_mode_blocks` |
| `k0 = 2 pi / lambda0` | vacuum wavenumber in inverse mesh length | `k0`; simcase scales the mesh by the wavelength and passes `k0 = 2 pi` (`simcase/physics_em_modes2d.py::_solve_vector`) |
| `beta` | propagation constant along z | `beta = k0 * n_eff` |
| `n_eff = beta / k0` | effective index, real or complex | `n_eff`, first return value of `solve_modes` |
| `e_t = beta E_t`, `e_z = -i E_z` | scaled unknowns of the mixed formulation | the pencil vector `x = [beta * et; ez]` |
| `lambda = -beta^2` | eigenvalue of the pencil `A x = lambda B x` | `lam0 = -(k0 n_eff)^2` in `waveguide.py::_live_modes` |
| `sigma = -(k0 n_target)^2`, `nu = 1 / (lambda - sigma)` | shift-invert target and the eigenvalue ARPACK actually returns | `sigma`, `nu` in `waveguide.py::_solve_modes_numpy` |
| `(s_x, s_y, h)` | complex coordinate stretch of the two transverse axes and the bend metric, one triple per triangle | `coordinate_factors` (T, 3), from `mode_coordinates.py::mode_coordinates` |
| `phi` | scalar (nodal) mode function of the scalar approximation | `fields` of `physics_em_modes2d.solve(formulation="scalar")` |

Passivity in this phasor means `Im eps_r <= 0` and `Im mu_r <= 0`, and a forward
passive mode has `Im n_eff < 0` (section 4). Material tables written as `n + i k`
are conjugated once, by the simcase document runner
(`simcase/runner.py::_solve_in_micrometres`: `np.conjugate(eps)`), before they
reach the solver.

## 2. Scalar P1 mode eigenproblem

The scalar approximation keeps one field component `phi(x, y)` and the Helmholtz
equation of the cross-section,

    div_t grad_t phi + (k0^2 eps_r - beta^2) phi = 0.

Multiplying by a P1 test function `w`, integrating over Omega and integrating
the Laplacian by parts gives the weak form

    k0^2 int eps_r phi w - int grad phi . grad w = beta^2 int phi w,

with the natural boundary term `int_Gamma w (d phi / d n)` dropped where nothing
is prescribed. With `phi = sum_j phi_j N_j` over the P1 hat functions this is the
generalized eigenproblem

    (k0^2 M_eps - K) phi = beta^2 M phi

implemented in `packages/simcase/src/simcase/physics_em_modes2d.py::solve`
(`formulation="scalar"`), from the galerkin assembly functions:

| Matrix | Integral | Assembly |
|---|---|---|
| `K` | `int grad N_i . grad N_j` | `galerkin.assembly.assemble_stiffness(mesh, 1.0)` → `core/kernels.py::p1_stiffness`, element matrix `(b_i b_j + c_i c_j) / (4 A)` |
| `M` | `int N_i N_j` | `assemble_mass(mesh, 1.0)` → `kernels.p1_mass`, exact `A/12 [[2,1,1],[1,2,1],[1,1,2]]` |
| `M_eps` | `int eps_r N_i N_j` | `assemble_mass(mesh, eps_tri)` with the per-triangle permittivity |

Boundary conditions are per named side of the mesh: `"pec"` removes the nodes
of that side from the unknowns (`phi = 0`, the electric-wall condition for the
TE slab polarisation); `"pmc"` leaves them free, which is the natural Neumann
condition of the weak form. Nothing else is supported on the scalar path.

The solve is SciPy's generalized shift-invert Arnoldi on the free nodes,
`eigsh` for real permittivity and `eigs` for complex, with the mass matrix `M`
as the `M` argument, target `sigma = (k0 n_target)^2` or, without `n_target`,
`(k0 max sqrt(Re eps_r))^2`, and `k = min(num_modes, free - 2)` eigenpairs. Then

- `n_eff = sqrt(lambda) / k0`; for a real problem negative `lambda` is clipped to
  zero before the root, for a complex one the NumPy principal square root is
  taken (`Re >= 0`), and modes are ordered by descending `Re n_eff`;
- `guided = Re n_eff > sqrt(min Re eps_r)` is a candidate flag against the
  lowest material index, not a proof of confinement;
- each field is divided by its coefficient at the node of largest `|phi|`, so
  that peak is exactly `1` (a complex field loses its arbitrary phase there);
  amplitudes are relative, not unit power.

The scalar equation is exact for the TE polarisation of a slab that is invariant
along one transverse axis, and an approximation for a genuinely two-dimensional
high-contrast core, where it cannot split the vector modes (the fibre comparison
in [milestone validation](milestone_validation.md) shows LP11 against the
resolved TE01/TM01/HE21 triple). The low-level scalar coordinate solver of
section 4 (`galerkin.mode_coordinates.solve_scalar_coordinates`) uses the same
equation with stretched coefficients.

The scalar path has no eigenvalue tracking of its own; wavelength sweeps and
their overlap/assignment rules live in simcase and are described in
[absorbing modes](../simcase/lossy_modes.md) and
[subspace tracking](../simcase/vector_subspace_tracking.md). The eigenspace
rules for the vector solver are in [eigenspace reliability](eigenspace_reliability.md).

**Cutoff problem of a closed guide.** Before the dielectric guide, the cutoff
wavenumbers of a PEC guide, `curl curl E = k_c^2 E` with `n x E = 0`, are solved
with the edge elements alone, `S e = k_c^2 M_t e`
(`examples/galerkin/waveguide_modes.py::solve_nedelec`, matrices from
`galerkin.edge.assemble_curlcurl` and `assemble_edge_mass`). The same example
discretises the problem with vector P1 nodal elements on purpose, to show the
spurious eigenvalues that the edge elements remove; the record is in
[milestone validation](milestone_validation.md).

## 3. Full-vector mixed Nédélec/nodal formulation

**Spaces and scaled unknowns.** Across a dielectric interface `E_t` is only
tangentially continuous while `E_z` is continuous, so the two components live in
different spaces (Lee, Sun and Cendes 1991; Jin 2014, waveguide chapter):

- `e_t = beta E_t` in H(curl), lowest-order Nédélec (Whitney) edge elements
  `W_ij = lambda_i grad lambda_j - lambda_j grad lambda_i` whose degree of
  freedom is the line integral along the oriented edge; the global orientation is
  low node id to high, with per-triangle signs
  (`packages/galerkin/src/galerkin/core/spaces.py::EdgeSpace`, local edge `e`
  opposite node `e`, `TRI_LOCAL_EDGES = ((1, 2), (2, 0), (0, 1))`);
- `e_z = -i E_z` in H1, the P1 nodal elements of the mesh.

With `grad = grad_t - i beta zhat` the curl of the ansatz is

    curl E = zhat curl_t E_t - zhat x (grad_t E_z + i beta E_t)
           = (1/beta) zhat curl_t e_t - i zhat x (grad_t e_z + e_t).

The scaling moves `beta` out of the transverse curl and the `-i` makes the
longitudinal unknown real for a real mode, so the resulting pencil is
transpose-symmetric with real matrices for real materials.

**Weak form and matrices.** Pairing the curl-curl equation with test fields of the
same two spaces carrying `exp(+i beta z)` (so that the pairing is the energy
form for real materials and the plain transpose pairing for complex ones), and
multiplying through by `beta^2`, gives

    [ S(1/mu) - k0^2 Mt(eps) ] e_t + beta^2 [ Mt(1/mu) e_t + G(1/mu) e_z ]           = 0
                                   beta^2 [ G(1/mu)^T e_t + K(1/mu) e_z - k0^2 M(eps) e_z ] = 0,

that is `A x = -beta^2 B x` with `x = [e_t; e_z]`,

    A = [ S - k0^2 Mt_eps   0 ]        B = [ Mt_mu   G            ]
        [ 0                 0 ]            [ G^T     K - k0^2 M   ].

`waveguide.py::assemble_mode_system` builds exactly these blocks
(`sp.bmat`), from `waveguide.py::_mode_blocks`:

| Block | Integral | Kernel (`galerkin/core/kernels.py`) | Public assembly |
|---|---|---|---|
| `S` | `int (1/mu_r) curl W_e curl W_f` | `nedelec_curlcurl`; `curl W_ij = 2 grad lambda_i x grad lambda_j` is constant per triangle, so the integral is exact | `galerkin.edge.assemble_curlcurl` |
| `Mt_eps` | `int eps_r W_e . W_f` | `nedelec_mass`, three-point edge-midpoint rule, exact for the quadratic integrand | `assemble_edge_mass` |
| `Mt_mu` | `int (1/mu_r) W_e . W_f` | `nedelec_mass` | `assemble_edge_mass` |
| `G` | `int (1/mu_r) W_e . grad N_n`, rows edges, columns nodes | `nedelec_grad`, closed form `(A/3)(grad lambda_j - grad lambda_i) . grad lambda_k` | `assemble_edge_grad` |
| `K` | `int (1/mu_r) grad N_m . grad N_n` | `p1_stiffness` | `galerkin.assembly.assemble_stiffness` |
| `M` | `int eps_r N_m N_n` | `p1_mass` | `assemble_mass` |

The second row carries no `beta^2`-free term, so `A` has a zero `e_z` block: the
weak longitudinal component of the curl-curl equation is a constraint, and
`beta^2 = 0` is an eigenvalue of multiplicity about the number of free nodes
(the discrete gradients). Guided modes lie at `n_clad < Re n_eff < n_core`, far
from it, and a shift-invert search near `n_target` meets this cluster only when
it asks for more roots than lie closer to the target than `beta^2 = 0`.
This is how the mixed pair suppresses spurious modes: the kernel of the curl is
represented exactly by the edge space and parked at `beta^2 = 0`, instead of
being smeared across the spectrum as nodal vector elements do
(`examples/galerkin/waveguide_modes.py::solve_nodal`).

When a search does reach the cluster, its computed roots usually have `|beta^2|`
at rounding level (at most `1.2e-14 |sigma|` on the slabs of
`tests/galerkin/test_waveguide_static_roots.py`, occasionally exactly 0), and
`E_t = e_t / beta` is undefined for them. `solve_modes` returns no root with
`|beta^2| <= STATIC_ROOT_TOL |sigma|` (`1e-10`, that is `|n_eff| <= 1e-5 |n_target|`)
on any path, so such a search returns fewer roots than `num_modes`. Limitation:
when the nodal block `K - k0^2 M` of `B` is nearly singular, that is `k0^2` is
close to an eigenvalue of `K e_z = lambda M e_z` on the free nodes (a TM cutoff of
the PEC box), the cluster is ill-conditioned and its computed roots can exceed the
tolerance: `2.2e-10 |sigma|` and `6.8e-9 |sigma|` were measured at relative
distances `1e-6` and `1e-8` from such a cutoff on a square guide. Those roots are
returned, with almost no transverse field.

`A` and `B` are transpose-symmetric. For real `eps_r`, `mu_r` they are real
symmetric and `B` is indefinite; for complex materials or coordinate factors they
are complex symmetric, not Hermitian (`waveguide.py` docstring).

**Boundary conditions.** A PEC wall `n x E = 0` fixes two kinds of degrees of
freedom to zero (`waveguide.py::_free_dofs`): the `e_z` values at `pec_nodes`
(default: every node of every named boundary) and the `e_t` line integrals on
`pec_edges`. By default `pec_edges` are the edges owned by exactly one triangle
whose two endpoints are both in `pec_nodes`
(`core/spaces.py::EdgeSpace.boundary_edge_ids`; membership is topological, so a
corner diagonal joining two boundary nodes is not constrained). Explicit
`pec_edges` allow mixed walls: a one-edge PMC wall with PEC corner nodes.
A PMC wall is natural: no constraint, which is the weak statement
`n x (mu_r^-1 curl E) = 0`. The free-DOF pencil is `A[free][:, free]`,
`B[free][:, free]`. simcase maps `boundary = {side: "pec" | "pmc"}` to
`pec_nodes` and `pec_edges` from `mesh.boundary` and `mesh.boundary_edges`
(`physics_em_modes2d.py::_solve_vector`).

**Eigensolve.** `B` is indefinite, so SciPy's generalized ARPACK drivers (which
require a positive semi-definite mass) are not used. Instead the shift-invert
operator is formed and handed over as a standard eigenproblem
(`waveguide.py::_solve_modes_numpy`):

    sigma = -(k0 n_target)^2,    LU of (A - sigma B)   (scipy.sparse.linalg.splu),
    op(v) = (A - sigma B)^-1 B v,     eigs(op, k=num_modes, which="LM", v0=ones),
    lambda = sigma + 1/nu,    beta^2 = -lambda.

`ncv = min(n, max(4 num_modes, 40))`, `maxiter = 20000`, with the fixed start
vector for reproducibility. For a real problem the eigenvalues are taken real,
only `beta^2 > 0` is kept, modes are sorted by descending `beta^2` and
`beta = sqrt(beta^2)`; `n_eff` is then a float64 array. The complex branch is in
section 4.

**Returned quantities and their normalisation.** For each kept eigenvector `v`
(ARPACK returns unit 2-norm vectors on the free DOFs):

1. the phase is fixed by the entry of largest modulus, `v <- v conj(p)/|p|`, so
   that entry is real and positive; a real vector stays exactly real, including a
   negative pivot;
2. `x` is the vector scattered back to all DOFs (zeros on the PEC ones);
3. `et[i] = x[:n_e] / beta` are the edge line integrals of `E_t`;
   `ez[i] = x[n_e:]` with the physical `E_z = 1j * ez[i]`;
4. `n_eff[i] = beta / k0`.

Both coefficient arrays are complex128 even for a real pencil, so that a complex
basis returned for a degenerate eigenspace keeps every direction; no eigenvectors
are mixed or made real ([eigenspace reliability](eigenspace_reliability.md)).
Amplitudes are arbitrary, not unit power. On a 24 x 24 square-core guide the
reconstructed `x = [k0 n_eff et; ez]` has `||x_free||_2 = 1` to 1e-12, a
real positive pivot and a free-DOF pencil residual of 1e-15; the
documented identity is what the code does. `galerkin.edge.eval_edge_field(space, et[i])`
evaluates `E_t` at triangle centroids as `sum_e sign_e et_e W_e(centroid)`.

**The simcase wrapper** (`physics_em_modes2d.py::_solve_vector`) scales the mesh
by the wavelength and solves with `k0 = 2 pi`, asks for `max(2 num_modes, 6)`
candidates at `n_target` (the maximum material index unless given), then either
keeps `n_clad < Re n_eff < n_core` or the candidates nearest `n_target`, both as
filters and not as a completeness statement. It normalises each mode so that the
largest centroid `|E|` is `1`, scales the transverse line integrals back by the
wavelength and stores `E_z = 1j * ez` in a `VectorField`
(`simcase/fields.py`). `physics_em_modes2d.vector_pencil_residuals` recomputes
`||A x + beta^2 B x|| / (||A x|| + |beta^2| ||B x||)` on the free DOFs from the
stored field, the diagnostic the sweeps and the PML contract rely on.

## 4. Complex materials and PML

**Complex `eps_r` and `mu_r`.** Both enter the same six blocks: `eps_r` in
`Mt_eps` and `M`, `1/mu_r` in `S`, `Mt_mu`, `G` and `K` (`_mode_blocks`). The
2D edge kernels accept complex scalar, per-triangle and `(T, 2, 2)` tensor
coefficients (the 3D edge kernels do not, `kernels._real_coefficient`). The
solve switches to the complex branch when any imaginary part is nonzero or
coordinate factors are given (`complex_problem` in `_solve_modes_numpy`); a
lossless input is reduced to its real part first so the real-material path is
unchanged. Passivity with `exp(+i omega t)` is `Im eps_r <= 0` and
`Im mu_r <= 0`; `solve_modes` checks only finiteness, simcase refuses
`Im eps > 0` ("passive modes use Im eps <= 0"). Gain media are unsupported. A
filled PEC guide sees only the product `eps_r mu_r`, which
`tests/galerkin/test_mode_gradients.py::test_complex_mu_matches_the_closed_form`
uses to check the complex `mu_r` path against the complex `eps_r` one.

**Branch and ordering of lossy roots.** From `beta^2 = -(sigma + 1/nu)` the
code takes `beta = sqrt(beta^2)` as a NumPy complex principal square root:
`Re beta >= 0` with the cut on the negative real axis, so a `beta^2` just below
the negative real axis maps to the fourth quadrant. Candidates with finite
`beta` and `Re beta > 0` are kept and ordered by descending `Re beta`, ties by
ascending `Im beta` (`np.lexsort((beta.imag, -beta.real))`). For a passive
forward mode this gives `Im n_eff < 0`; the square-core guide of section 3 with
`eps_core = 2.25 - 0.01i` returns `Im n_eff = -3.35e-3`, which is also the
first-order value `(d n_eff / d eps_core) Im eps_core` of section 5. Amplitude
decays as `exp(-a z)` with `a = -Im beta`, power as `exp(-2 a z)`; the dB/cm
conversion is in [absorbing modes](../simcase/lossy_modes.md). With coordinate
factors every candidate except the static `beta^2 = 0` roots (section 3) is kept
and a nonfinite root is an error, so that the caller records every candidate and
its exclusion reason.

**PML as a complex coordinate stretch.** Open cross-sections are truncated by
stretching the transverse coordinates into the complex plane (Bérenger 1994 for
the split-field layer; Chew and Weedon 1994 for the stretched-coordinate form
used here). `galerkin.mode_coordinates.mode_coordinates` defines, on a
rectangular mesh with up to four PML strips of given thickness, per axis `q`
and depth `d` into a strip,

    s_q = 1 - i strength (d / thickness)^order,         order in {2, 3, 4},
    q~  = q - i sign strength thickness/(order+1) (d / thickness)^(order+1),

evaluated at triangle centroids; outside the strips `s_q = 1`, `q~ = q`. A
constant-radius bend adds the metric `h = 1 + (q~_axis - bend_origin) / R` of
the chosen outward axis (`h = 1` for a straight guide), with propagation
distance the reference arc length `z = R theta`. The factors are the diagonal
Jacobian `J = diag(s_x, s_y, h)`. With `exp(-i k_x x~)` for an outgoing wave in
`+x`, `Im x~ < 0` makes the wave decay, consistent with the `exp(+i omega t)`
phasor.

The stretched problem is the original one with the materials replaced by
`eps' = eps det(J) J^-1 J^-T` and `mu' = mu det(J) J^-1 J^-T` (Teixeira and
Chew 1998), which for a diagonal `J` is

    eps'  = eps  diag( s_y h / s_x,  s_x h / s_y,  s_x s_y / h ),
    1/mu' = (1/mu) diag( s_x / (s_y h),  s_y / (s_x h),  h / (s_x s_y) ).

`_mode_blocks` places these entries as the transverse curl requires: `S` uses
`(1/mu')_zz = (1/mu) h/(s_x s_y)`; `Mt_eps` the tensor `(eps'_xx, eps'_yy)`;
`Mt_mu`, `G` and `K` the tensor `((1/mu')_yy, (1/mu')_xx)`, the two transverse
entries swapped because `zhat x` rotates the axes; `M` uses `eps'_zz`. The
permeability is transformed as well, not an absorbing permittivity alone. The
returned `et`, `ez` are covariant computational components; outside the PML the
physical longitudinal field is `1j * ez / h`, and the simcase candidate solver
divides centroid components by `(s_x, s_y, h)`
(`simcase/physics_pml_modes.py::solve`). The scalar counterpart
(`mode_coordinates.scalar_coordinate_system`) is

    A = k0^2 M(eps h s_x s_y) - K(diag(h s_y / s_x, h s_x / s_y)),   B = M(s_x s_y / h),   A u = beta^2 B u,

solved by `solve_scalar_coordinates` with shift `(k0 n_target)^2`,
`n_eff = sqrt(beta^2)/k0` (principal root) sorted by descending real part.

**Absorbing-modes contract.** A PML pencil is complex symmetric and
non-Hermitian; its spectrum contains artificial layer modes beside the
physical ones, and a finite window with a shift proves neither confinement nor
completeness. `solve_modes` therefore returns candidates with arbitrary
amplitude. The simcase contract ([PML, leaky and bent modes](../simcase/pml_modes.md))
records every searched candidate and accepts one only with `Re n_eff > 0`,
pencil residual `<= 1e-8`, physical-window share of a positive L2 diagnostic
`>= min_physical_fraction` (default 0.1) and
`Im n_eff <= 1e-10 max(1, |Re n_eff|)`; a modulus below that threshold is
labelled `numerically_unresolved` and never clamped. PML outer faces must be
PEC, materials must extend through the layer, and mesh, physical window,
thickness and strength have to be varied independently; a single run reports
`stability: "not_checked"`. Total attenuation mixes absorption and radiation.

The cylindrical PML of `galerkin.pml.radial_pml_coeffs` belongs to the
frequency-domain scattering solver (M2.5) and is written for outgoing waves
`exp(+i k r~)`, that is the `exp(-i omega t)` phasor, with
`s = 1 + i sigma(r)/k` (Collino and Monk 1998). It is not used by the mode
solvers; do not combine its coefficients with the modal factors.

## 5. Derivatives of n_eff and of the fields

`solve_modes` accepts JAX or PyTorch values for `eps_r`, `mu_r` and `k0`
([derivatives](differentiation.md)). The NumPy eigensolve of section 3 runs on
the numbers first. Then, for each returned simple eigenpair `(lambda0, x0)` on
the free DOFs with `lambda0 = -(k0 n_eff)^2` and `x0 = [beta et; ez]`,
`waveguide.py::_live_modes` rebuilds `A` and `B` in the live library from the
same kernels (`_live_blocks`, `_restricted`) and calls
`galerkin.core.eigen.refine`, one Newton step on the eigenproblem bordered by
the normalisation `x^T B x = 1` (transpose, no conjugate):

    [x; lambda] = [x0; lambda0] - J^-1 F,
    J = [[A - lambda0 B, -B x0], [-x0^T B, 0]],   F = [(A - lambda0 B) x0, (1 - x0^T B x0)/2].

`x0` is first rescaled to `x0^T B x0 = 1` (the NumPy solve leaves `||x0||_2 = 1`
instead). The bordered system is solved by the adjoint sparse LU of
`galerkin.core.solve` (JAX `custom_vjp`, PyTorch `autograd.Function`), so the
values stay those of the NumPy solve up to its residual while the derivatives
are the exact implicit ones, for real and complex pencils alike (Andrew, Chu
and Lancaster 1993 for the bordered eigenpair derivative).

For the eigenvalue alone this step is the Hellmann–Feynman expression of a
simple eigenvalue of a transpose-symmetric pencil, whose left eigenvector is
`x` itself,

    d lambda = x^T (dA - lambda dB) x / (x^T B x),

and with `n_eff = sqrt(-lambda)/k0` at fixed `k0`,
`d n_eff = -d lambda / (2 k0^2 n_eff)`. For the permittivity of a set of
triangles `omega`, `dA/d eps = -k0^2 Mt_omega(1)` and `dB/d eps = -k0^2 M_omega(1)`,
so

    d n_eff / d eps_omega = ( e_t^T Mt_omega e_t + beta^2 e_z^T M_omega e_z ) / ( 2 n_eff x^T B x ),

the familiar perturbation integral of `E_t.E_t + E_z.E_z` over the perturbed
region in the pencil's own normalisation (with `x^T B x` of the mass-normalised
vector equal to one). Evaluated from the NumPy solve on the square-core guide,
this matches a central difference of `solve_modes` to 7e-11 relative; the live
path is not restricted to this form because the bordered step also returns the
field derivatives. For `k0`, `dA/dk0 = -2 k0 Mt_eps`, `dB/dk0 = -2 k0 M`, and
the division by `k0` adds `-n_eff/k0`.

After the step the returned gauge is applied again: with the pivot `p` chosen
as the entry the NumPy solve left real and positive (`waveguide.py::_pivot`,
the largest-modulus entry with zero phase when several are equally large),

    x <- x conj(x_p) / ( |x_p| ||x||_2 ),    beta = sqrt(-lambda),    et = x_t / beta,    ez = x_z,

with `n_eff = Re beta / k0` for a real problem and `beta / k0` otherwise. Field
derivatives follow this gauge; gauge-free quantities (overlap magnitudes,
`|E_z|^2/|E_t|^2`, weighted shares of `|E_t|^2` through `eval_edge_field` with
live `dofs`) have gauge-free derivatives.

A multiple eigenvalue makes `J` singular. `core/eigen.py::degenerate_modes`
compares each returned eigenvalue with the others and with the nearest
eigenvalue of the whole free pencil (`neighbour_gap`: dense `eigvals` up to 300
DOFs, otherwise shift-invert Arnoldi for the two eigenvalues nearest `lambda0`);
a relative gap `<= DEGENERATE_GAP = 1e-8` gives that mode its exact values, NaN
derivatives and a `DegenerateModeWarning`. `n_target` only selects modes and has
no derivative; `coordinate_factors`, mesh geometry and the PEC sets are
structure; `assemble_mode_system` refuses live values. The checks are listed in
[derivatives](differentiation.md#validation), `tests/galerkin/test_mode_gradients.py`.

## 6. Coupling: what flows out of a mode solve

`galerkin.coupling` ([contract](coupling.md)) carries a `Field` between kernels:
one real float64 value per node or per triangle of a 2D P1 `Mesh`, with a
recorded SI unit, bound to the mesh's `MeshSignature`; `transfer` is the
identity on the same mesh and `OneWayChain` orders one-way stages.

A mode result is not a `Field`, and no adapter exists:

- `et` lives on edges (a Nédélec space), which the coupling layer excludes;
- `et`, `ez` and `n_eff` of a lossy or PML problem are complex, and `Field`
  refuses complex values;
- the amplitudes are relative, so there is no SI unit to record;
- JAX or PyTorch arrays are refused by `Field` (a field would cut the
  derivative).

What a caller can hand to another physics is a real nodal or elementwise
quantity it derives itself, for example a per-triangle `|E|^2` from
`eval_edge_field` and the centroid mean of `1j * ez`, scaled to a physical power
and declared with its unit as `Field(mesh, values, location="element", unit=...)`.
No electromagnetic absorption source for the heat solvers is provided; the
existing one-way chains are electric-to-heat and heat-to-mechanics. simcase
keeps mode fields in its own `VectorField` with the maximum-magnitude
normalisation of section 3, saved as complex NPZ arrays and real/imaginary JSON
lists ([absorbing modes](../simcase/lossy_modes.md)).

## 7. The SI/PI path: quasi-static cross-sections in `sipi`

[`sipi`](../sipi/overview.md) analyses PCB cross-sections with the same engine
but not with the mode solver. From galerkin it uses

| sipi module | galerkin pieces |
|---|---|
| `sipi/crosssection.py` (`CrossSection.mesh`) | `galerkin.Mesh`, `galerkin.from_mesher` on a meshine triangulation |
| `sipi/quasistatic.py::capacitance_matrix` | `galerkin.assemble_stiffness` (P1 `K` with real or complex `eps_r`), `galerkin.solve_dirichlet` |
| `sipi/conductor.py` (surface-impedance loss) | `assemble_stiffness`, `solve_dirichlet` on the perfect-conductor exterior field |
| `sipi/conductor_diffusion.py` (DC/AC current diffusion) | `assemble_stiffness`, `assemble_mass`, `assemble_load` for the P1 `A_z` diffusion system |
| `sipi/plane.py` (power-plane IR drop) | `galerkin.electric.solve_steady_electric` |

No edge elements, no `solve_modes`, no `k0`: the line is assumed quasi-TEM
(cross-section small against the wavelength), so the transverse field is the
gradient of a potential and the two-dimensional problem is electrostatic (Paul
2008, per-unit-length parameters):

    div ( eps grad V ) = 0  outside the conductors,   V = 1 on conductor j,   V = 0 on the others and the ground,

with `"open"` box sides insulating (natural, zero normal D) and `"ground"` sides
at 0 V. The discrete energy gives the Maxwell capacitance matrix

    C_ij = eps0 V_i^T K V_j,     C = (C + C^T)/2,

equal to the charge read from the residual `K V` on each conductor;
`C0` repeats the solve with every `eps_r = 1`, and
`L = mu0 eps0 C0^-1`. A lossy layer enters as `eps_r (1 - j tan_delta)`
(`sipi/quasistatic.py::line_parameters`; passive `Im eps_r <= 0` in the same
`exp(+j omega t)` sense as the mode solver), the solved matrix is
`C - j C_loss`, and `G(f) = 2 pi f C_loss`. Derived per-unit-length quantities
(`LineParameters`): `z0 = sqrt(L/C)`, `eps_eff = C/C0`, phase velocity
`c/sqrt(eps_eff)`, delay, `loss_tangent = C_loss/C`, even/odd impedances of a
symmetric pair, and the modal decomposition `(L C) v = v/u^2` with modal
`eps_eff = (c/u)^2`. Conductor resistance is a separate surface-impedance
perturbation of the perfect-conductor field
([conductor loss](../sipi/conductor.md)) or an explicit P1 `A_z` diffusion
solve with one longitudinal field constant per conductor group
([current diffusion](../sipi/conductor_diffusion.md)).

Where the two paths diverge:

- the mode solver finds `beta` as an eigenvalue of the full-wave pencil at a
  given `k0`; the SI/PI path takes `beta = omega sqrt(L C)` per quasi-TEM mode
  from static matrices, with no cutoff, no `E_z` and no dispersion from the
  geometry;
- the mode solver's dielectric loss is `Im n_eff` of one eigenpair; the SI/PI
  path carries it as `G`, linear in frequency for a constant `tan_delta`;
- PEC walls bound the mode window and are part of the model, whereas an `"open"`
  wall in `sipi` is an insulator whose truncation error must be checked by
  moving it;
- `sipi` is NumPy-only through `assemble_stiffness` and `solve_dirichlet`, which
  refuse live values; the derivative machinery of section 5 does not reach it.

What they share: the P1 stiffness kernel `kernels.p1_stiffness`, the mesh
contract and `from_mesher`, and the passive sign of complex permittivity.

## 8. Validation pointers and limitations

Measured evidence stays in these pages; this page restates none of their
numbers:

- [milestone validation](milestone_validation.md): M3-prep cutoffs and the
  nodal spurious-mode demonstration, the step-index fibre against the exact
  vector dispersion relation, the slab limit;
- [eigenspace reliability](eigenspace_reliability.md): degenerate pairs, the
  electric-L2 Gram and the independent analytic field oracle;
- [derivatives](differentiation.md#validation): closed-form and central-difference
  gradient checks of `n_eff`, `et`, `ez` and the degenerate rule;
- [absorbing modes](../simcase/lossy_modes.md) and
  [PML, leaky and bent modes](../simcase/pml_modes.md): complex slab roots,
  metal interface, outgoing-slab and bend references, PML/window variation;
- [modal coordinates](modal_coordinates.md) and the
  [scikit-fem comparisons](../../reference-comparisons.md): independent
  assembly plus dense QZ for the straight and bent pencils;
- `tests/galerkin/test_fiber_modes.py`, `test_slab_modes.py`,
  `test_pml_modes.py`, `test_crosscheck_skfem_pml_modes.py`,
  `test_eigenspace_reliability.py`, `test_mode_gradients.py`;
  `tests/simcase/test_lossy_modes.py`, `test_pml_contract.py`,
  `test_vector.py`, `test_vector_sweep.py`;
- [sipi validation](../sipi/overview.md#validation) for the quasi-static path.

Limitations of the formulations as implemented:

- Two-dimensional cross-sections only; materials are isotropic scalars per
  triangle, and the only tensor coefficients the mode solver builds are the
  diagonal PML/bend ones. No anisotropic user input, no gain media.
- A PEC window truncates every closed-guide solve; its position is part of the
  model. PML candidates are heuristics until mesh, window, thickness and
  strength have been varied; attenuation is total, not separated into
  absorption and radiation.
- Fields have relative amplitude: no power normalisation, no orthogonality or
  completeness guarantee, and no identity assignment within a degenerate pair.
- Derivatives exist with respect to `eps_r`, `mu_r` and `k0`, and with respect to
  node positions along a design motion (`motion=`,
  [shape derivatives](shape_derivative.md#waveguide-modes)); not with respect to
  coordinate factors, PML parameters, `n_target` or PEC sets, and not through a
  `Field`.
- The scalar path is exact for the invariant-axis TE slab polarisation only.
- `sipi` is quasi-static and non-magnetic (`mu = mu0` in `L`), with no
  full-wave dispersion, and its per-unit-length loss model is separate from the
  mode solver's complex `n_eff`.

## References

- J.-M. Jin, *The Finite Element Method in Electromagnetics*, 3rd ed.,
  Wiley-IEEE Press, 2014: vector elements, waveguide eigenproblems and the
  anisotropic-medium form of the PML.
- J.-F. Lee, D.-K. Sun and Z. J. Cendes, "Full-wave analysis of dielectric
  waveguides using tangential vector finite elements," *IEEE Trans. Microwave
  Theory Tech.* 39(8), 1991: the mixed edge/nodal formulation with the
  `beta`-scaled transverse unknown.
- J.-C. Nédélec, "Mixed finite elements in R³," *Numer. Math.* 35, 1980; and
  A. Bossavit, *Computational Electromagnetism*, Academic Press, 1998: the
  Whitney edge elements and why nodal vector elements produce spurious modes.
- J.-P. Bérenger, "A perfectly matched layer for the absorption of
  electromagnetic waves," *J. Comput. Phys.* 114, 1994; W. C. Chew and
  W. H. Weedon, "A 3D perfectly matched medium from modified Maxwell's equations
  with stretched coordinates," *Microwave Opt. Technol. Lett.* 7(13), 1994;
  F. L. Teixeira and W. C. Chew, "General closed-form PML constitutive tensors
  to match arbitrary bianisotropic and dispersive linear media," *IEEE Microwave
  Guided Wave Lett.* 8(6), 1998: the stretched-coordinate PML and its material
  tensors.
- F. Collino and P. Monk, "The perfectly matched layer in curvilinear
  coordinates," *SIAM J. Sci. Comput.* 19(6), 1998: the radial PML of
  `galerkin.pml`.
- A. W. Snyder and J. D. Love, *Optical Waveguide Theory*, Chapman and Hall,
  1983: effective-index perturbation integrals and the sign of the loss.
- A. L. Andrew, K.-W. E. Chu and P. Lancaster, "Derivatives of eigenvalues and
  eigenvectors of matrix functions," *SIAM J. Matrix Anal. Appl.* 14(4), 1993:
  the bordered system for eigenpair derivatives.
- R. B. Lehoucq, D. C. Sorensen and C. Yang, *ARPACK Users' Guide*, SIAM, 1998:
  shift-invert Arnoldi as used through `scipy.sparse.linalg.eigs`.
- C. R. Paul, *Analysis of Multiconductor Transmission Lines*, 2nd ed., Wiley,
  2008: quasi-TEM per-unit-length parameters.
