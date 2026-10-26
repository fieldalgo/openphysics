# Check convergence of your calculation

**English** | [한국어](../locales/ko/pages/validation/convergence.md)

[Documentation home](../README.md)

A small algebraic residual means the discrete equations were solved closely.
Conservation means the reported transfers balance. Neither alone bounds the
error between the discretized model and the physical problem.

## 1. State the quantity and decision first

Choose the quantity you need: temperature at a physical point, integrated heat
flow, displacement, cavity frequency or propagation loss. State an application
accuracy requirement before examining the results. Compare the same physical
quantity, units, boundary conditions and material law in every run.
A new mesh generally changes node IDs: a fixed array index is not a fixed point.
For fields, evaluate consistently on physical locations or integrate a norm;
do not subtract unrelated arrays with the same length.

## 2. Vary one approximation at a time

| Problem | Independent variations to consider |
|---|---|
| Steady heat/electricity/mechanics | Element size near interfaces, loads and gradients; geometry representation |
| Transient heat | Time step at fixed mesh, then mesh with temporal error controlled |
| Closed waveguide modes | Mesh and outer window; candidate selection/tracking |
| PML/open modes | Mesh, physical window, PML thickness and strength independently |
| Cavity | Mesh and the search target/window; mode multiplicity and identification |

Changing material parameters or boundaries is a different physical problem,
not convergence. For modes, compare the same branch or subspace using the
appropriate contract, not simply the first eigenvalue returned.

## 3. Keep a small convergence table

Record mesh/settings, degrees of freedom, quantity, reference error if available,
and change from the preceding resolution. If Q tends to zero, a relative error
can be meaningless; use a justified absolute scale. With known errors and a
uniform factor-two refinement, `p=log(e_coarse/e_fine)/log(2)` estimates observed
order. Without a reference, three-run differences can suggest an asymptotic trend,
but are not proof of true error or an automatic acceptance rule. Non-monotonicity,
roundoff, singularities and competing errors can invalidate such estimates.

Use the wall to practice preserving independent runs:

```sh
python examples/simcase/layered_wall.py out/wall-h4 --mesh-size-mm 4
python examples/simcase/layered_wall.py out/wall-h2 --mesh-size-mm 2
python examples/simcase/layered_wall.py out/wall-h1 --mesh-size-mm 1
```

For this no-source wall the exact piecewise-linear temperature is already in the
P1 space. Near-roundoff errors do **not** measure an order of convergence.
For a nontrivial spatial example, the existing
[coax convergence script](../../examples/galerkin/coax_convergence.py) compares
against a logarithmic exact solution and writes a local `coax_convergence.npz`.
Its >1.8 final-order gate belongs to that registered problem, not every model.

For transient studies compare common physical observation times. Repeat the
finest spatial calculation with a smaller time step to check that temporal
error is not hiding spatial error. The
[transient validation guide](../packages/galerkin/transient_heat_validation.md)
provides a discrete eigenmode temporal test and a separate manufactured PDE test.
Large histories can require substantial memory; inspect its workload first.

## 4. Separate formulation limits from discretization

Refining a plane-strain model cannot make it a plane-stress model. Refining a
perfect-contact interface does not add contact resistance. Changing PML settings
cannot certify every returned candidate as a physical pole. Uniform-temperature
and constant-property examples are useful controls, but cannot qualify arbitrary
heterogeneous or nonlinear problems.

When reporting results, keep the input, code/environment versions, refinement table,
comparison method, observed changes and unresolved limits. Cite the relevant
[independent validation](index.md), and explain what your own study adds.
A good-looking plot, a completed run or passing repository CI is not a substitute
for assessing the resolution of your particular model.
