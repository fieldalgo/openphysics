# Electromagnetics

**English** | [한국어](../locales/ko/pages/physics/electromagnetics.md)

[Documentation home](../README.md)

Start with a waveguide cross-section, then choose scalar/vector modes, a wavelength sweep or a rectangular cavity. Electrostatics and scattering use the Python engine. PML/leaky modes are candidates requiring independent mesh and PML checks, not certified physical poles.

## Execution routes and limits

Waveguide documents and sweeps have JSON/CLI and Studio routes; 3D cavities have JSON/CLI but no Studio route. Read the mode contracts for the limits of each optical study.

## Model documents and workflows

- [Tutorial: analyse your own waveguide](../packages/simcase/waveguide_tutorial.md)
- [Absorbing waveguide modes](../packages/simcase/lossy_modes.md)
- [PML, leaky and constant-radius modes](../packages/simcase/pml_modes.md)
- [Opt-in subspace tracking for vector wavelength sweeps](../packages/simcase/vector_subspace_tracking.md)
- [Rectangular cavity document and results](../packages/simcase/cavity3d.md)


## PCB transmission lines (signal and power integrity)

- [sipi — quasi-static PCB cross-sections: C, L, G, impedance and coupled-line modes](../packages/sipi/overview.md). Python API and [versioned cross-section JSON with impedance design](../packages/sipi/design.md); [uniform-line networks](../packages/sipi/network.md) accept explicit RLGC for S and Touchstone output. Conductor-loss extraction and 3D structures are not implemented.

## Python contracts and formulations

- [Vacuum rectangular PEC cavity solver](../packages/galerkin/cavity_solver.md)
- [Material-loaded rectangular cavity solver](../packages/galerkin/material_cavity.md)
- [Vector eigenspace reliability](../packages/galerkin/eigenspace_reliability.md)
- [Modal complex coordinates](../packages/galerkin/modal_coordinates.md)
- [galerkin — the OpenPhysics finite-element engine](../packages/galerkin/overview.md)


## Validation records

- [galerkin milestone validation (2026-09-05)](../packages/galerkin/milestone_validation.md)
- [Independent validation plan: vacuum PEC rectangular cavities](../packages/galerkin/cavity3d_validation.md)
- [Independent validation of the alternating Kuhn cavity mesh](../packages/galerkin/cavity3d_alternating_validation.md)
- [Rectangular PEC 111 doublet: signed-mean convergence diagnosis](../packages/galerkin/cavity3d_convergence_diagnosis.md)


[Build a model](../modeling/index.md) · [Results and trust](../results/index.md) · [All physics](index.md)
