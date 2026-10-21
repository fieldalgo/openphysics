# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Document-to-vector checks against independent references and field invariants."""

import copy
import json

import numpy as np
import pytest

from galerkin import EdgeSpace, Mesh, assemble_mode_system, eval_edge_field
from refsol import benchmarks, fiber, slab
from simcase import Document, DocumentError, build_mesh, examples, run, solve_point


def slab_document(pol="TE", size=0.012, pad=1.5):
    d = copy.deepcopy(examples.VECTOR_SLAB)
    d["geometry"]["domain"].update(ymin=-pad, ymax=0.22 + pad)
    d["geometry"]["shapes"][0]["mesh_size"] = size
    d["mesh"]["size"] = 5 * size
    d["mesh"]["grading"].update(near=size, far=5 * size)
    if pol == "TM":
        d["physics"]["em1"]["boundary"].update(left="pmc", right="pmc")
    return Document.from_dict(d)


@pytest.mark.parametrize("pol", ["TE", "TM"])
def test_vector_slab_reference_polarization_and_mesh_convergence(pol):
    exact = slab.modes(3.48, 1.444, 1.444, 0.22, 1.55, pol)[0]
    errors = []
    for h in (0.024, 0.012, 0.006):
        result = run(slab_document(pol, h), verbose=False)
        errors.append(abs(result.neff[0, 0] - exact))
        mesh = Mesh(result.mesh_nodes, result.mesh_triangles, {})
        E = result.vector_fields[0].electric[:, 0, :]
        energy = np.sum(mesh.areas()[:, None] * abs(E) ** 2, axis=0)
        share_x = energy[0] / sum(energy)
        assert (share_x > 0.99) if pol == "TE" else (share_x < 0.01)
    assert errors[-1] < 2e-4
    assert errors[0] > errors[1] > errors[2]
    assert np.log2(errors[-2] / errors[-1]) > 1.7


@pytest.mark.parametrize("pol", ["TE", "TM"])
def test_vector_slab_domain_padding_is_converged(pol):
    values = [run(slab_document(pol, pad=pad), False).neff[0, 0] for pad in (1.5, 2.5)]
    # Domain error must be much smaller than the h=0.012 discretization error.
    assert abs(values[0] - values[1]) < 2e-5


def _refined(d, factor):
    d = copy.deepcopy(d)
    for shape in d["geometry"]["shapes"]:
        if "mesh_size" in shape:
            shape["mesh_size"] *= factor
    d["mesh"]["size"] *= factor
    for key in ("near", "far"):
        d["mesh"]["grading"][key] *= factor
    return Document.from_dict(d)


def test_vector_fiber_family_matches_refsol_and_improves_on_refinement():
    modes = fiber.vector_modes(4.0, 1.45, 1.44, 1.55)
    exact = np.array([m.neff for m in modes for _ in range(2 if m.l else 1)])
    errors = []
    for factor in (1.0, 0.65):
        res = run(_refined(examples.VECTOR_FIBER, factor), verbose=False)
        assert res.neff.shape == (1, 6)
        errors.append(np.max(abs(res.neff[0] - exact)))
        assert np.max(abs(res.neff[0] - exact) / exact) < 5e-5
        # meshine's general mesh does not have the exact rotational symmetry of
        # galerkin's disk_mesh. Do not impose its machine-precision degeneracy.
        assert abs(res.neff[0, 0] - res.neff[0, 1]) < 1e-5
    assert errors[1] < 0.8 * errors[0]


def test_vector_fiber_outer_wall_is_far_enough():
    d = copy.deepcopy(examples.VECTOR_FIBER)
    near = run(Document.from_dict(d), False).neff[0]
    d["geometry"]["domain"] = dict(xmin=-28, xmax=28, ymin=-28, ymax=28)
    far = run(Document.from_dict(d), False).neff[0]
    assert np.max(abs(near - far)) < 1e-5


@pytest.mark.slow
def test_vector_hadley_document_matches_reference_and_refines():
    d = copy.deepcopy(examples.HADLEY_RIB_VECTOR)
    exact = benchmarks.rib_neff(0.3)
    errors = [abs(run(_refined(d, s), False).neff[0, 0] - exact) for s in (1.0, 0.65)]
    assert errors[0] / exact < 2e-4
    assert errors[1] < 0.8 * errors[0]
    assert errors[1] / exact < 1e-4


def rescale(doc, symbol, ratio):
    d = copy.deepcopy(doc.data)
    d["units"]["length"] = symbol
    d["geometry"]["domain"] = {k: v * ratio for k, v in d["geometry"]["domain"].items()}
    for shape in d["geometry"]["shapes"]:
        for key in ("x", "y", "w", "h", "mesh_size"):
            shape[key] *= ratio
    d["mesh"]["size"] *= ratio
    gr = d["mesh"]["grading"]
    gr["center"] = [v * ratio for v in gr["center"]]
    for key in ("near", "far", "distance"):
        gr[key] *= ratio
    d["physics"]["em1"]["wavelength"] *= ratio
    return Document.from_dict(d)


@pytest.mark.parametrize("symbol,ratio", [("nm", 1e3), ("um", 1.0), ("m", 1e-6)])
def test_vector_units_and_saved_raw_fields_reconstruct_the_physical_field(symbol, ratio, tmp_path):
    doc = rescale(slab_document("TM"), symbol, ratio)
    result = run(doc, verbose=False)
    exact = slab.modes(3.48, 1.444, 1.444, 0.22, 1.55, "TM")[0]
    assert abs(result.neff[0, 0] - exact) < 1e-3
    assert result.fields == [] and result.group_index() is None
    out = result.save(tmp_path / symbol)
    summary = json.loads((out / "summary.json").read_text())
    assert summary["units"] == {"length": symbol}
    assert summary["field_representation"] == "vector-edge-nodal-v1"
    assert summary["returned_modes"] == summary["requested_modes"] == 1
    assert (out / "results.png").stat().st_size > 0
    with np.load(out / "fields.npz", allow_pickle=False) as arrays:
        assert "fields" not in arrays  # a vector must never masquerade as nodal scalar data
        mesh = Mesh(arrays["nodes"], arrays["triangles"], {})
        space = EdgeSpace(mesh)
        np.testing.assert_array_equal(space.edges, arrays["edges"])
        electric = arrays["vector_electric"][0]
        transverse = arrays["vector_transverse"][0]
        longitudinal = arrays["vector_longitudinal"][0]
        np.testing.assert_allclose(eval_edge_field(space, transverse[:, 0]), electric[:, 0, :2], atol=1e-12)
        np.testing.assert_allclose(longitudinal[mesh.triangles].mean(axis=1), electric[:, :, 2], atol=1e-12)
        assert np.max(abs(electric[:, :, 2].imag)) > 0.1
        assert np.max(abs(electric[:, :, 2].real)) == 0
        np.testing.assert_allclose(np.linalg.norm(electric, axis=2).max(axis=0), 1.0)
        # Raw transverse integrals scale with the declared length; E samples do not.
        assert np.max(abs(transverse)) / ratio < 0.1
    payload = result.vector_fields[0].to_dict()
    back = np.array(payload["real"]) + 1j * np.array(payload["imag"])
    np.testing.assert_array_equal(back.transpose(1, 0, 2), result.vector_fields[0].electric)


def test_vector_saved_coefficients_satisfy_the_maxwell_block_system_and_pec():
    doc = slab_document("TM")
    model = build_mesh(doc)
    point = solve_point(model, doc.sole_physics()[1])
    f = point["vector_field"]
    k0 = 2 * np.pi / doc["physics"]["em1"]["wavelength"]
    beta = k0 * point["neff"][0]
    A, B, space = assemble_mode_system(model.mesh, model.eps_per_triangle(1.55).real, k0)
    x = np.r_[beta * f.transverse[:, 0], -1j * f.longitudinal[:, 0]]
    pec = np.unique(np.concatenate([model.mesh.boundary[s] for s in ("top", "bottom")]))
    fixed = np.r_[space.boundary_edge_ids(pec), space.num_edges + pec]
    free = np.setdiff1d(np.arange(len(x)), fixed)
    assert np.max(abs(x[fixed])) == 0
    left, right = (A @ x)[free], (-beta**2 * (B @ x))[free]
    assert np.linalg.norm(left - right) / (np.linalg.norm(left) + np.linalg.norm(right)) < 1e-9


def test_vector_single_edge_pmc_wall_is_not_fixed_by_pec_corners():
    d = copy.deepcopy(slab_document(pad=0.5).data)
    d["mesh"]["size"] = d["mesh"]["grading"]["far"] = 0.2
    d["physics"]["em1"]["boundary"].update(top="pmc", bottom="pmc")
    doc = Document.from_dict(d)
    model = build_mesh(doc)
    point = solve_point(model, doc.sole_physics()[1])
    f = point["vector_field"]
    k0 = 2 * np.pi / 1.55
    beta = k0 * point["neff"][0]
    A, B, space = assemble_mode_system(model.mesh, model.eps_per_triangle(1.55).real, k0)
    edge_ids = {tuple(edge): i for i, edge in enumerate(space.edges)}
    for side in ("top", "bottom"):
        edges = model.mesh.boundary_edges[side]
        assert len(edges) == 1  # both endpoints belong to neighboring PEC walls
        edge_id = edge_ids[tuple(sorted(edges[0]))]
        assert abs(f.transverse[edge_id, 0]) > 1e-4
    pec = np.unique(np.concatenate([model.mesh.boundary[s] for s in ("left", "right")]))
    pec_edges = [edge_ids[tuple(sorted(edge))] for s in ("left", "right")
                 for edge in model.mesh.boundary_edges[s]]
    x = np.r_[beta * f.transverse[:, 0], -1j * f.longitudinal[:, 0]]
    fixed = np.r_[pec_edges, space.num_edges + pec]
    free = np.setdiff1d(np.arange(len(x)), fixed)
    assert np.max(abs(x[fixed])) == 0
    left, right = (A @ x)[free], (-beta**2 * (B @ x))[free]
    assert np.linalg.norm(left - right) / (np.linalg.norm(left) + np.linalg.norm(right)) < 1e-9


@pytest.mark.parametrize("key,value", [("n_cladding", None), ("n_cladding", True), ("n_cladding", 0),
    ("n_cladding", float("inf")), ("num_modes", 1.5), ("num_modes", float("nan")), ("num_modes", True)])
def test_vector_input_contract_rejects_invalid_numbers(key, value):
    d = copy.deepcopy(examples.VECTOR_SLAB)
    d["physics"]["em1"][key] = value
    with pytest.raises(DocumentError, match=key):
        Document.from_dict(d)


@pytest.mark.parametrize("target", ["wavelength", "formulation", "physics_map"])
def test_invalid_vector_sweep_is_rejected_before_meshing(target):
    d = copy.deepcopy(examples.VECTOR_SLAB)
    d["study"] = dict(type="sweep", parameter="physics.em1.wavelength", values=[1.5, 1.6])
    if target != "wavelength":
        vector_settings = copy.deepcopy(d["physics"]["em1"])
        d["physics"]["em1"]["formulation"] = "scalar"
        d["study"] = dict(type="sweep", parameter="physics.em1.formulation", values=["scalar", "vector"])
        if target == "physics_map":
            d["study"] = dict(type="sweep", parameter="physics.em1", values=[vector_settings])
    message = "at least 3" if target == "wavelength" else "cannot switch to vector"
    with pytest.raises(DocumentError, match=message):
        Document.from_dict(d)


def test_vector_loss_and_nonpositive_permittivity_are_refused():
    for material, error, text in [({"n": 3.48, "k": 0.01}, NotImplementedError, "lossy"),
                                  ({"n": 0.0}, ValueError, "positive")]:
        d = copy.deepcopy(examples.VECTOR_SLAB)
        d["materials"]["film"] = material
        with pytest.raises(error, match=text):
            run(Document.from_dict(d), False)


def test_missing_modes_are_reported_without_padding_and_empty_search_fails():
    d = copy.deepcopy(examples.VECTOR_SLAB)
    d["physics"]["em1"]["num_modes"] = 4
    res = run(Document.from_dict(d), False)
    assert 0 < res.neff.shape[1] < 4
    assert res.vector_fields[0].electric.shape[1] == res.neff.shape[1]
    assert any("requested 4 modes; found" in line for line in res.log)
    for threshold, message in [(3.479, "no guided"), (3.48, "below the maximum")]:
        d["physics"]["em1"]["n_cladding"] = threshold
        with pytest.raises(ValueError, match=message):
            run(Document.from_dict(d), False)
