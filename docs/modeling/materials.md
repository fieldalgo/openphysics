# Choose material data and its valid range

**English** | [한국어](../locales/ko/pages/modeling/materials.md)

[Documentation home](../README.md)

Choose a material record for the physical quantity, wavelength and temperature of
interest. A material name alone does not specify all coefficients needed by an
OpenPhysics calculation. This guide connects the [physmat API](../packages/physmat/overview.md)
to the [region model](../packages/galerkin/multimaterial.md).

## Inspect the record before using it

```python
import physmat

si = physmat.get("Si")
wavelength_um = 1.55
print(si.source)
print(si.range_um)
print(si.index(wavelength_um))

conductivity = si.properties["thermal_conductivity"]
print(conductivity.unit, conductivity.source)
k_w_mk = si.get("thermal_conductivity", T=300.0)
print(k_w_mk)
```

`physmat` optical calls take wavelength in **micrometres**, regardless of a
`simcase` document's geometry unit. The built-in Si record covers 1.357–11.04 µm;
1.55 µm is inside it. The default strict check raises `physmat.OutOfRange` outside
the model's range. Disabling a range check does not validate extrapolation.
Inspect the citation and the range of the selected record; different records for
the same substance can describe different samples or measurement conditions.

The Si conductivity above is 148 W/(m K), a handbook value at 300 K. Its source is
attached to the property, separately from the optical model's source. Passing a
new `T` to a constant `Property` returns the same constant. It does not create a
temperature law or establish a valid temperature interval. Callable properties
are possible, but each solver decides which coefficient forms it accepts.

## Keep the physical quantities separate

| Input | Meaning and unit | What to check |
|---|---|---|
| Optical `n`, `k` | Refractive index and extinction coefficient, dimensionless | Wavelength range, dispersion and absorption convention |
| Thermal conductivity | W/(m K) | Sample, temperature and isotropic/anisotropic assumption |
| Density and specific heat | kg/m³ and J/(kg K) | Their product is volumetric heat capacity, J/(m³ K) |
| Electric conductivity | S/m | Electrical model and any explicit temperature law |
| Young's modulus, Poisson ratio, expansion | Pa, dimensionless, 1/K | Mechanical assumptions and stress-free reference temperature |

Optical extinction `k` is not thermal conductivity, and optical permittivity does
not supply a DC electric conductivity. `physmat` provides some non-optical
handbook properties, but does not automatically fill a thermal/Joule/mechanical
model. Copy only the quantities required by the chosen API or document contract,
with explicit units and citations. Missing properties raise `KeyError`; do not
replace them with an unrelated optical value.

## Assign data to the model

For optical JSON, use a built-in material name or the supported custom constant
`n`/`k` or Sellmeier definition. Document wavelength and Sellmeier length inputs
follow the [simcase unit contract](../packages/simcase/overview.md); direct
`physmat` calls still use µm. Do not mix those interfaces' length conventions.

For heat, use the explicit conductivity and heat-capacity fields in the
[region heat contract](../packages/simcase/thermal_regions2d.md). Verify each
shape's material and the background, including uncovered space and overlapping
shape priority. Follow the [two-material wall tutorial](../packages/simcase/layered_wall_tutorial.md)
to inspect the saved region assignment and flux.

For temperature-dependent Joule heating, supply the law supported by the
[Joule contract](../packages/simcase/electric_joule.md) or
[Python workflow](../packages/galerkin/temperature_joule_tutorial.md).
An optical thermo-optic coefficient does not enable an automatic coupled solve.

## Preserve enough information to reproduce the choice

Keep the material source, selected record, coefficients, units, wavelength or
temperature interval and any fit settings with the model. A Drude–Lorentz fit's
error describes its fit samples; check the intended band separately. Mesh
convergence cannot correct an unsuitable material model. Vary uncertain material
coefficients separately from the [numerical convergence checks](../validation/convergence.md).
