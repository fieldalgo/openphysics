# Interpret thermal expansion, stress and reactions

**English** | [한국어](../locales/ko/pages/results/thermoelastic-controls.md)

[Documentation home](../README.md)

Follow the [first heat → mechanics tutorial](../packages/galerkin/thermoelastic_tutorial.md)
for the coupled sequence. Here, prescribe a uniform temperature to isolate the
mechanical interpretation. The example requires `galerkin` and runs from the
repository root; it does not solve heat or certify a coupled calculation.

```sh
python examples/galerkin/thermoelastic_controls.py
```

The [example](../../examples/galerkin/thermoelastic_controls.py) uses a 1 m square,
E=70 GPa, ν=0.3, α=12e-6/K, T=313.15 K and stress-free Tref=293.15 K.
Thus `a = α(T−Tref) = 2.4e-4`. Temperature values remain absolute kelvin.

## Compare constraints with independent uniform solutions

| Model | Displacement | Normal stress | Energy per depth |
|---|---|---|---|
| Free in-plane, plane stress | `u=a(x,y)` | All normal stresses zero | 0 J/m |
| Free in-plane, plane strain | `u=(1+ν)a(x,y)` | σxx=σyy=0; σzz=−Ea=−16.8 MPa | 2016 J/m |
| Blocked boundary, plane strain | `u=0` | σxx=σyy=σzz=−Ea/(1−2ν)=−42 MPa | 15120 J/m |

The first two cases pin bottom-left x/y and bottom-right y to remove rigid motion
without blocking uniform in-plane expansion. Those node IDs apply only to this
structured mesh. The blocked case fixes both components on every boundary node.
A temperature boundary does not impose a displacement support.

Plane strain sets εzz=0, so the material cannot freely expand out of plane.
Its free in-plane state therefore has nonzero compressive σzz and physical energy.
For area A, the two plane-strain energies above are `A E a²/2` and
`3 A E a²/[2(1−2ν)]`, from the original 3D elastic energy. Do not replace that
energy with half the displacement dotted into the thermal-equivalent load.
Small residual stresses in the nominally stress-free result are floating-point error.

## Read reactions and locations correctly

`displacement` is nodal in m. `stress` contains centroid `(σxx,σyy,τxy)` in Pa;
`sigma_zz` is separate. For nonuniform P1 temperature, stress generally varies
inside each triangle: centroid values are samples, not a complete constant field.
This example's uniform temperature makes the analytic stresses uniform.

`reaction` contains support forces per extrusion depth, N/m. With no physical
body force or traction, their sum and the support moment should be near zero.
The example prints both. Opposing nonzero reactions in the blocked case balance;
zero net reaction does not mean the body is stress-free. For these metre-scale
controls, roundoff residuals are of order 1e-7 N/m against MPa stresses.
Use scale-aware tolerances when adapting the check.

Thermal-equivalent load is an assembly term, not an extra external physical force.
For loaded models, include physical body force and total boundary traction in
force/moment balance. Multiply N/m and J/m by actual depth in m to obtain N and J;
moment per depth has unit N. See the
[mechanical-stage contract](../packages/galerkin/prescribed_temperature_thermoelasticity.md)
and [total traction contract](../packages/galerkin/thermoelastic_traction.md).

## Transfer to nonuniform heat results

Check the reference temperature, supports, plane reduction and transferred mesh
identity before interpreting stress. Refine displacement, energy and stresses away
from singular support corners separately; a growing peak at an idealized corner
is not automatically a solver bug or a converged material failure prediction.
The steady heat → mechanics workflow is one-way and small-strain. It does not
feed deformation back into heat or perform structural dynamics. Keep the
[run record](run-records.md) and the [convergence evidence](../validation/convergence.md)
with any reported stress.
