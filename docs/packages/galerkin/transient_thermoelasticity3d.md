# Quasistatic 3D thermoelasticity from a temperature history

**English** | [한국어](../../locales/ko/pages/packages/galerkin/transient_thermoelasticity3d.md)

Import `solve_thermoelasticity_history_3d` from
`galerkin.transient_thermoelasticity3d`. Supply finite, strictly increasing
`time` values in seconds with shape `(S,)` and finite, nonnegative
`temperature` values in kelvin with shape `(S, N)`. Every row follows the
node order of the same metre-based `Mesh3D`. A transient heat result can supply
its `time` and `temperature` arrays directly.

The material, support and load keywords follow the
[static 3D solver](thermoelasticity3d.md). Each sample is a separate elastic
equilibrium at its given temperature. The calculation assumes small strain and
quasistatic response. By default it solves every stored time, including the
initial time. An explicit `sample_indices` sequence takes distinct, strictly
increasing zero-based indices. To inspect a heater cycle, include the initial
row, the heater switch-off row, and one or more cooldown rows. The solver
validates the complete input history before solving the selected rows.

The result owns its selected `time` array in seconds, `sample_indices` tuple
and `steps` tuple of static elastic results. Each step reports displacement in
metres, dimensionless total strain, stress in Pa and nodal reactions in N.
Altering the original history after the call leaves the selected results intact.

The tests drive the actual elastic solver with an analytical heater-on/off
history. They compare fully clamped stress and nodal reactions with the
hydrostatic solution, and check free expansion and a two-material mesh with
nonuniform nodal temperatures.
