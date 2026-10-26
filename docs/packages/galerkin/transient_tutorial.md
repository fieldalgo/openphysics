# Transient heat tutorial: where the input energy goes

**English** | [한국어](../../locales/ko/pages/packages/galerkin/transient_tutorial.md)

Start after the [steady heat tutorial](thermal_tutorial.md). Here the whole
boundary is insulated and heat accumulates instead of leaving through thermostats.
The coefficients are deliberately simple teaching values, not a material database entry.

## 1. Set up and run

Use Python 3.12 or newer and an activated virtual environment; see the
[suite overview](../../overview.md) for checkout setup. From the repository root:

```sh
python -m pip install -e packages/galerkin
python examples/galerkin/transient_heat_uniform.py
```

The [script](../../../examples/galerkin/transient_heat_uniform.py) uses a 1 m × 1 m
square with 4 × 4 cells, initial temperature 300 K, conductivity 2.5 W/(m K),
volumetric heat capacity **c=4 J/(m³ K)** and uniform source **Q=8 W/m³**.
Volumetric heat capacity is density times specific heat; it is not specific heat
in J/(kg K). `dirichlet={}` means no fixed-temperature nodes, hence insulation
on every natural edge. Unlike steady heat, transient heat needs no thermostat
anchor on this fully insulated component.

## 2. Read the temperature and energy histories

```text
Time (s): [0.  0.1 0.3]
Mean temperature (K): [300.  300.2 300.6]
Heat content change (J/m): [0.  0.8 2.4]
Stored power after each step (W/m): [8. 8.]
```

The remaining outputs are flux near roundoff (about 1e-15 W/m² or smaller)
and zero boundary reaction. Last digits can vary by runtime.

The temperature stays spatially uniform, so the diffusion term vanishes:
`c*dT/dt=Q`, or `T(t)=300+2*t` K. On this 1 m² domain, source power per
extrusion depth is 8 W/m. At 0.3 s the stored heat increase is 2.4 J/m.
For a physical depth of 0.01 m, that is 0.024 J; do not multiply temperature by depth.
The script subtracts the initial `heat_content_j_per_m` so the printed value is
an energy **change**, not the absolute heat-content diagnostic.

## 3. Distinguish time samples from time steps

| Array | Shape here | Meaning |
|---|---|---|
| `time_s` | (3,) | Requested times, including the initial time |
| `temperature_k` | (3, 25) | Three nodal states, including the initial field |
| `heat_flux_w_m2` | (3, 32, 2) | Flux per triangle and component at each time |
| `storage_rate_w_per_m` | (2, 25) | Rates for the two completed time intervals |
| `reaction_w_per_m` | (2, 25) | Thermostat reactions after each step, none at t0 |

`temperature_k[0]` is the initial state, not the result of a hidden first step.
Rate row 0 describes the interval from time sample 0 to 1. The solver uses backward
Euler with the supplied, possibly nonuniform time intervals; it does not choose
adaptive steps. All histories are retained, so memory grows with both mesh size
and the number of times. There is no streaming or restart in this API.

## 4. Make controlled changes

Copy the script to a local working file outside `packages/` and change one input.

- Double `heat_source` to 16. The final temperature is 301.2 K and heat increase
  is 4.8 J/m; stored power is 16 W/m.
- Double `volumetric_heat_capacity` to 8. The final temperature is 300.3 K, but
  heat increase remains 2.4 J/m: the same input energy produces a smaller rise.
- Change times to `[0., .05, .1, .2, .3]`. The final uniform temperature is still
  300.6 K. A constant source and spatially uniform field make this an exact
  backward-Euler special case, **not a temporal-convergence study**.

For time-dependent boundaries, initial temperatures at prescribed nodes must
agree with the boundary values at the first time. The solver does not silently
replace inconsistent initial data. Callbacks must be deterministic; source loads
are sampled at the requested right endpoints.

## 5. Go beyond the uniform check

Use the [transient contract](transient_heat.md) for result shapes and initial-data
rules, and the [validation guide](transient_heat_validation.md) for independent
spatial and temporal convergence studies. The larger convergence example there
is a validation workload, not necessary for this first calculation.

This Python API has no flux/Robin input, temperature-dependent properties or
automatic mechanics coupling. The separate [JSON/CLI document](../simcase/thermal_transient2d.md)
and [Studio guide](../simcase/thermal_transient_studio.md) explain their supported
interfaces; running this script itself does not save files or launch a UI.
