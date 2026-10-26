# Choose units, signs and boundary conditions

**English** | [한국어](../locales/ko/pages/modeling/boundaries-units.md)

[Documentation home](../README.md)

A boundary condition describes the external physical constraint, not a knob to
make a solver accept a model. Start from what is controlled or measured, then
choose a supported interface. The [two-layer wall](../packages/simcase/layered_wall_tutorial.md)
is a concrete fixed-temperature plus convection example.

## Heat boundaries

| Physical situation | Input | Sign and interpretation |
|---|---|---|
| Ideal temperature-controlled surface | Dirichlet temperature in K | The solver determines its heat input as `reaction` |
| No heat exchange | Unspecified natural edge | Insulation; not a fixed temperature |
| Known outward heat flux | `outward_flux`, W/m² | Positive removes heat; negative injects it |
| Exchange with an ambient medium | `convection`, h and ambient K | Outward q·n=h(T−Tamb); a warmer ambient injects heat |

Flux plus convection on the same supported edge is additive. Do not impose either
natural condition on an edge with both endpoints temperature-fixed. JSON side
conditions reject conflicting corner temperatures. Each connected component of
steady heat requires a Dirichlet anchor or positive Robin support; h=0 does not
anchor temperature. A fully insulated transient problem can evolve from an
initial field without a Dirichlet anchor because its storage term matters.
Transient heat currently has no flux/Robin input. The steady heat-to-mechanics
wrapper does not inherit every boundary extension of the standalone heat solver.

For steady heat, `sum(load + reaction)` equals prescribed plus convective outward
heat. Thermostat outward heat is **minus reaction**. A positive reaction is heat
entering the body, not positive outward flow. Exact equations and callback rules:
[flux/Robin contract](../packages/galerkin/thermal_flux_robin.md).

## Electric and mechanical constraints

- Electrical voltage fixes potential. Prescribed outward current density J·n is
  positive leaving the body. The Python electric API has an explicit pure-Neumann
  gauge path; do not infer that the more restricted JSON input supports it.
- Mechanical displacement fixes selected components, not temperature. A connected
  2D body needs independent constraints on its three rigid modes. An arbitrary
  count of three fixed DOFs is not enough if they leave a rotation free.
- Traction is force per area in global Cartesian directions. It is not a scalar
  pressure or total nodal force. Remaining natural boundaries are traction-free
  under the relevant mechanical contract.
- Plane stress and plane strain are different physical approximations, not
  alternative accuracy settings. Thermal expansion also requires a reference
  temperature; fixing thermal nodes never automatically fixes mechanical nodes.

See [electric conduction](../packages/galerkin/electric_steady2d.md),
[elasticity](../packages/galerkin/elasticity2d.md) and
[thermal mechanics](../packages/galerkin/prescribed_temperature_thermoelasticity.md).

## Length and extrusion depth

| Quantity | Unit | Multiply by physical extrusion depth? |
|---|---|---|
| Thermal/mechanical engine coordinates | m | No |
| Temperature, displacement, stress | K, m, Pa | No |
| Heat flux, current density | W/m², A/m² | No |
| Integrated 2D heat/current rate | W/m, A/m | Yes, to obtain W or A |
| Mechanical reaction, elastic energy | N/m, J/m | Yes, to obtain N or J |

Document geometry and mesh sizes use the declared length unit. SI-suffixed
properties keep their indicated units. Meshers have no automatic physical unit
conversion; the thermal/mechanical Python engine expects metres. Optical APIs
have their own wavelength/length contracts; do not apply the SI-engine rule to
every package indiscriminately. Convert Celsius to kelvin before supplying a
Kelvin input; changing a label does not convert a number.

## Optical signs are an interface boundary

`physmat` and JSON use positive extinction coefficient n+ik for passive materials.
The low-level mode solver uses `exp(+i omega t-i beta z)` and negative imaginary
permittivity for passive loss. The document runner performs the conjugation at
the boundary. Do not conjugate document materials again. Forward passive modes
have Im n_eff<0 under this convention. Mode fields have relative normalization,
not automatically V/m or unit optical power. Read the
[lossy-mode contract](../packages/simcase/lossy_modes.md) before comparing fields
or converting attenuation.
