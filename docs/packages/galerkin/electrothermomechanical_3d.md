# 3D DC → steady heat → thermoelasticity

**English** | [한국어](../../locales/ko/pages/packages/galerkin/electrothermomechanical_3d.md)

Run the [powered bar example](../../../examples/galerkin/electrothermomechanical_3d.py)
from the repository root with `python examples/galerkin/electrothermomechanical_3d.py`.
The first two solves can also be run by calling the example's `solve_electrothermal_bar(nx)`.

1. Solve [steady DC conduction](electric_steady3d.md) on a `Mesh3D` in metres.
2. Pass its `joule_power_density` (W/m³) to
   [steady heat](thermal3d.md) as `heat_source_density`, preserving tetrahedron order.
3. Pass `heat.temperature` (K) directly to `solve_thermoelasticity_3d` on
   the same mesh. Displacement and support reaction are nodal (N × 3) in
   metres and newtons. Total strain and tensile-positive stress are symmetric
   cell tensors (T × 3 × 3) in unit strain and Pa. Strain uses tensor shear.

The example uses fixed properties and one-way coupling on a static mesh.
A 0.2 m × 0.05 m × 0.05 m bar has 2 V across its ends, conductivity
σ = 10 S/m, and thermal conductivity k = 2 W/(m K). Its left end is at
300 K, its right end convects to 300 K at h = 20 W/(m² K), and the side
faces are insulated. Both ends are axially fixed and all transverse
displacements are fixed. The bar uses ν = 0, E = 70 GPa and
α = 12 µm/(m K), with a stress-free temperature of 300 K.

## Independent reference

Ohm's law gives 0.25 A and 0.5 W with uniform Q = σ(ΔV/L)² = 1000 W/m³.
The temperature rise θ solves −k θ″ = Q, θ(0) = 0 and −k θ′(L) = h θ(L).
Writing θ(x) = b x − c x² gives c = Q/(2k) and
b = (QL + h c L²)/(k + hL). The analytical convection and fixed-end
heat losses are 1/6 W and 1/3 W. The mean temperature rise is 10/3 K.

With ν = 0 and zero transverse displacement, axial equilibrium and the two
axial constraints give σₓₓ = −Eα mean(θ) = −2.8 MPa and
uₓ(x) = α ∫₀ˣ [θ(s) − mean(θ)] ds. The transverse normal stress is −Eαθ,
and all shear vanishes. The support forces on the left and right ends are
+7 kN and −7 kN in the global x direction.

The regression checks electrical and thermal power closure to 10⁻⁹ relative,
including an independent triangular-face integration of convection. It
compares fields and reactions with the analytical values at 4, 8 and 16
axial divisions and one division per transverse direction. At the finest
resolution the relative limits are 2% for temperature rise, 5% for axial
displacement, 15% for the strain and stress tensors, and 3% for end forces.
Temperature, displacement, strain and stress errors must decrease at each
refinement.
