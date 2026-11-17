# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Check P3-5 of the galerkin step for the modes: the public SI functions against the kernels.

The cases are four em.modes2d documents of the units batch (P2-1): ``vector_slab`` and
``pml_leaky_slab`` (examples/simcase) and ``em_lossy_film_vector`` and the bent vector case
``em_pml_bent_vector`` (tools/units_batch/fixtures/v03). simcase runs each, and the test records the
kernel call it makes (route K, D1): ``galerkin.kernels.solve_modes`` on the micrometre mesh scaled by
the wavelength, k0 = 2 pi, with the permittivity in exp(+i omega t), and the micrometre inputs of
that solve (mesh, wavelength, PML and bend).

- **Same frame, bitwise.** ``solve_waveguide_modes`` on the metre mesh (the micrometre nodes times
  1e-6) with the metre wavelength, PML and bend, against ``galerkin.kernels.solve_modes`` on the same
  metre inputs through ``to_kernel`` (k0 = 2 pi / vacuum_wavelength, the coordinate factors of the
  same metre PML): every output is ``to_public`` of the kernel's, byte for byte (effective indices,
  line integrals, E_z = to_public(1j * ez)), and so is each post-processing function against its
  kernel on the kernel solve's own outputs.
- **Cross frame, 1e-12.** The public effective indices against simcase's micrometre kernel frame,
  per complex value in kernel order: |a - b| <= 1e-12 |b| with b = to_public of the kernel's value;
  ``mode_power`` against ``vector_power`` on the micrometre mesh (line integrals in um, k0 = 2 pi /
  wavelength in 1/um) times 1e-12 (um^2 to m^2), the same bound, per mode for non-degenerate modes
  and as the sum over a degenerate pair.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pytest

import galerkin.kernels as kernels
import simcase
from galerkin import EdgeSpace, Mesh
from galerkin._conventions import to_kernel, to_public
from galerkin.waveguide import (Bend, ModalPML, cross_power, field_overlap, mode_confinement_factor,
                                mode_coupling_efficiency, mode_effective_area, mode_power, solve_waveguide_modes)
from simcase import physics_em_modes2d, physics_pml_modes

ROOT = Path(__file__).resolve().parents[2]
CASES = {"vector_slab": ROOT / "examples" / "simcase" / "vector_slab.json",
         "pml_leaky_slab": ROOT / "examples" / "simcase" / "pml_leaky_slab.json",
         "em_lossy_film_vector": ROOT / "tools" / "units_batch" / "fixtures" / "v03" / "em_lossy_film_vector.json",
         "em_pml_bent_vector": ROOT / "tools" / "units_batch" / "fixtures" / "v03" / "em_pml_bent_vector.json"}
#: the pre-registered cross-frame bound (spec 7, P3-5), relative to the kernel frame's value
CROSS_FRAME = 1e-12
#: two effective indices this close (relative) belong to a degenerate pair (galerkin.core.eigen.DEGENERATE_GAP)
DEGENERATE = 1e-8


def kernel_frame(path):
    """simcase's run of one document: the micrometre inputs of its vector mode solve and the kernel call it makes."""
    outer, inner = [], []
    solve, kernel = physics_em_modes2d.solve, kernels.solve_modes
    outer_signature, kernel_signature = inspect.signature(solve), inspect.signature(kernel)

    def recording_solve(*args, **kwargs):
        outer.append(outer_signature.bind(*args, **kwargs).arguments)
        return solve(*args, **kwargs)

    def recording_kernel(*args, **kwargs):
        bound = kernel_signature.bind(*args, **kwargs)
        bound.apply_defaults()
        result = kernel(*args, **kwargs)
        inner.append((dict(bound.arguments), result))
        return result

    saved = (physics_em_modes2d.solve, physics_em_modes2d.solve_modes, physics_pml_modes.solve_modes)
    physics_em_modes2d.solve = recording_solve
    physics_em_modes2d.solve_modes = physics_pml_modes.solve_modes = recording_kernel
    try:
        simcase.run(simcase.Document.from_dict(json.loads(Path(path).read_text(encoding="utf-8"))), False)
    finally:
        physics_em_modes2d.solve, physics_em_modes2d.solve_modes, physics_pml_modes.solve_modes = saved
    assert len(outer) == 1 and len(inner) == 1, (len(outer), len(inner))
    return outer[0], inner[0]


def metre_inputs(outer, call):
    """The public inputs in SI of simcase's micrometre solve: nodes, wavelength, PML and bend times 1e-6."""
    um = outer["mesh"]
    mesh = Mesh(um.nodes * 1e-6, um.triangles.copy(), um.boundary, um.boundary_edges)
    pml, bend = outer.get("pml"), outer.get("bend")
    spec = dict(relative_permittivity=to_public(call["eps_r"]), vacuum_wavelength=outer["wavelength"] * 1e-6,
                target_effective_index=call["n_target"], search_mode_count=call["num_modes"],
                pec_nodes=call["pec_nodes"], pec_edges=call["pec_edges"])
    if pml is not None:
        spec["pml"] = ModalPML(pml_thickness={side: width * 1e-6 for side, width in pml["thickness"].items()
                                              if width > 0},
                               pml_strength=pml.get("strength", 3.0), pml_order=pml.get("order", 2))
    if bend is not None:
        spec["bend"] = Bend(bend_radius=bend["radius"] * 1e-6, bend_origin=bend.get("origin", 0.0) * 1e-6,
                            bend_axis=bend.get("axis", "x"))
    return mesh, spec


def kernel_on_metres(mesh, spec):
    """``galerkin.kernels.solve_modes`` on the same metre inputs through ``to_kernel``."""
    factors = None
    if "pml" in spec:
        pml, bend = spec["pml"], spec.get("bend")
        factors = kernels.mode_coordinates(
            mesh, thickness=dict(pml.pml_thickness), strength=pml.pml_strength, order=pml.pml_order,
            bend_radius=None if bend is None else bend.bend_radius, bend_axis="x" if bend is None else bend.bend_axis,
            bend_origin=0.0 if bend is None else bend.bend_origin).factors
    return kernels.solve_modes(mesh, to_kernel(spec["relative_permittivity"]), 2 * np.pi / spec["vacuum_wavelength"],
                               to_kernel(spec["target_effective_index"]), spec["search_mode_count"], to_kernel(1.0),
                               spec["pec_nodes"], pec_edges=spec["pec_edges"], coordinate_factors=factors)


def _bits(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()


def cross_frame_margins(outer, result, modes):
    """|a - b| / (1e-12 |b|) of the effective indices and of the powers (per mode, or per degenerate pair)."""
    (n_um, space_um, et_um, ez_um), wavelength = result, outer["wavelength"]
    n_ref = to_public(n_um)
    a = modes.effective_index
    assert a.shape == n_ref.shape
    index = np.abs(a - n_ref) / (CROSS_FRAME * np.abs(n_ref))
    um = outer["mesh"]
    space = EdgeSpace(Mesh(um.nodes, um.triangles.copy(), um.boundary, um.boundary_edges))
    assert np.array_equal(space.edges, space_um.edges)
    reference = np.array([to_public(kernels.vector_power(space, et_um[j] * wavelength, ez_um[j], n_um[j],
                                                          2 * np.pi / wavelength, 1.0)) * 1e-12
                          for j in range(len(n_um))])
    power = np.array([mode_power(modes, j) for j in range(len(a))])
    groups, j = [], 0
    while j < len(a):
        k = j + 1
        while k < len(a) and abs(n_ref[k] - n_ref[j]) <= DEGENERATE * abs(n_ref[j]):
            k += 1
        groups.append(list(range(j, k)))
        j = k
    margins = [abs(power[g].sum() - reference[g].sum()) / (CROSS_FRAME * abs(reference[g].sum())) for g in groups]
    return index, np.array(margins), groups


@pytest.fixture(scope="module", params=sorted(CASES))
def case(request):
    outer, (call, result) = kernel_frame(CASES[request.param])
    mesh, spec = metre_inputs(outer, call)
    modes = solve_waveguide_modes(mesh, **spec)
    return request.param, outer, result, mesh, spec, modes


def test_the_cases_are_the_vector_documents_of_the_batch(case):
    name, outer, result, mesh, spec, modes = case
    assert outer["formulation"] == "vector" and outer["wavelength"] > 0
    assert ("pml" in spec) == (name in ("pml_leaky_slab", "em_pml_bent_vector"))
    assert ("bend" in spec) == (name == "em_pml_bent_vector")
    # lossy materials (complex permittivity, complex indices): the film and the bent silicon guide; the leaky
    # slab is lossless and its PML makes the indices complex
    assert np.iscomplexobj(spec["relative_permittivity"]) == (name in ("em_lossy_film_vector", "em_pml_bent_vector"))
    assert np.iscomplexobj(modes.effective_index) == (name != "vector_slab")
    assert len(modes.effective_index) >= 1


def test_same_frame_public_outputs_are_to_public_of_the_kernel_bitwise(case):
    name, outer, result, mesh, spec, modes = case
    n, space, et, ez = kernel_on_metres(mesh, spec)
    assert _bits(modes.effective_index, to_public(n))
    assert _bits(modes.unnormalized_electric_field_line_integral, to_public(et))
    assert _bits(modes.unnormalized_electric_field_z, to_public(1j * ez))
    assert np.array_equal(modes.space.edges, space.edges)
    k0 = 2 * np.pi / spec["vacuum_wavelength"]
    assert modes.vacuum_angular_wavenumber == k0
    last = len(n) - 1
    for j in range(len(n)):
        assert _bits(mode_power(modes, j), to_public(kernels.vector_power(space, et[j], ez[j], n[j], k0, 1.0)))
        assert _bits(cross_power(modes, j, modes, last),
                     to_public(kernels.vector_cross_power(space, et[j], ez[j], et[last], ez[last], n[last], k0, 1.0)))
        assert _bits(field_overlap(modes, j, modes, last),
                     to_public(kernels.vector_field_overlap(space, et[j], ez[j], et[last], ez[last])))
        assert _bits(mode_effective_area(modes, j), kernels.effective_area(space, et[j], ez[j]))
        assert _bits(mode_effective_area(modes, j, include_longitudinal=True),
                     kernels.effective_area(space, et[j], ez[j], include_longitudinal=True))
        assert _bits(mode_confinement_factor(modes, j, np.arange(mesh.num_triangles // 2)),
                     kernels.confinement_factor(space, et[j], ez[j], to_kernel(spec["relative_permittivity"]),
                                                np.arange(mesh.num_triangles // 2)))
        assert _bits(mode_coupling_efficiency(modes, j, modes, last),
                     kernels.coupling_efficiency(space, et[j], ez[j], et[last], ez[last]))


def test_cross_frame_against_simcase_micrometre_kernel_frame(case):
    name, outer, result, mesh, spec, modes = case
    index, power, groups = cross_frame_margins(outer, result, modes)
    assert np.all(index <= 1.0), (name, index)
    assert np.all(power <= 1.0), (name, power, groups)
