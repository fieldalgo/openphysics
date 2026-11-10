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


def um(x):
    """A length in micrometres, written with the digits of its double."""
    return f"{x!r} um"


def scaled(text, factor):
    """A quantity string with its number times ``factor`` (the double the 0.2 test computed)."""
    number, unit = text.split(" ", 1)
    return f"{float(number) * factor!r} {unit}"


def slab_document(pol="TE", size=0.012, pad=1.5):
    d = copy.deepcopy(examples.VECTOR_SLAB)
    d["geometry"]["domain"].update(ymin=-pad, ymax=0.22 + pad)
    d["geometry"]["shapes"][0]["element_size"] = um(size)
    d["mesh"]["element_size"] = um(5 * size)
    d["mesh"]["grading"].update(near=um(size), far=um(5 * size))
    if pol == "TM":
        d["physics"]["em1"]["boundary"].update(left="pmc", right="pmc")
    return Document.from_dict(d)


@pytest.mark.parametrize("pol", ["TE", "TM"])
def test_vector_slab_reference_polarization_and_mesh_convergence(pol):
    exact = slab.modes(3.48, 1.444, 1.444, 0.22, 1.55, pol)[0]
    errors = []
    for h in (0.024, 0.012, 0.006):
        result = run(slab_document(pol, h), verbose=False)
        errors.append(abs(result.effective_index[0, 0] - exact))
        mesh = Mesh(result.node_coordinates, result.triangles, {})
        E = result.vector_fields[0].electric[:, 0, :]
        energy = np.sum(mesh.areas()[:, None] * abs(E) ** 2, axis=0)
        share_x = energy[0] / sum(energy)
        assert (share_x > 0.99) if pol == "TE" else (share_x < 0.01)
    assert errors[-1] < 2e-4
    assert errors[0] > errors[1] > errors[2]
    assert np.log2(errors[-2] / errors[-1]) > 1.7


@pytest.mark.parametrize("pol", ["TE", "TM"])
def test_vector_slab_domain_padding_is_converged(pol):
    values = [run(slab_document(pol, pad=pad), False).effective_index[0, 0] for pad in (1.5, 2.5)]
    # Domain error must be much smaller than the h=0.012 discretization error.
    assert abs(values[0] - values[1]) < 2e-5


def _refined(d, factor):
    d = copy.deepcopy(d)
    for shape in d["geometry"]["shapes"]:
        if "element_size" in shape:
            shape["element_size"] = scaled(shape["element_size"], factor)
    d["mesh"]["element_size"] = scaled(d["mesh"]["element_size"], factor)
    for key in ("near", "far"):
        d["mesh"]["grading"][key] = scaled(d["mesh"]["grading"][key], factor)
    return Document.from_dict(d)


def test_vector_fiber_family_matches_refsol_and_improves_on_refinement():
    modes = fiber.vector_modes(4.0, 1.45, 1.44, 1.55)
    exact = np.array([m.neff for m in modes for _ in range(2 if m.l else 1)])
    errors = []
    for factor in (1.0, 0.65):
        res = run(_refined(examples.VECTOR_FIBER, factor), verbose=False)
        assert res.effective_index.shape == (1, 6)
        errors.append(np.max(abs(res.effective_index[0] - exact)))
        assert np.max(abs(res.effective_index[0] - exact) / exact) < 5e-5
        # meshine's general mesh does not have the exact rotational symmetry of
        # galerkin's disk_mesh. Do not impose its machine-precision degeneracy.
        assert abs(res.effective_index[0, 0] - res.effective_index[0, 1]) < 1e-5
    assert errors[1] < 0.8 * errors[0]


def test_vector_fiber_outer_wall_is_far_enough():
    d = copy.deepcopy(examples.VECTOR_FIBER)
    near = run(Document.from_dict(d), False).effective_index[0]
    d["geometry"]["domain"] = dict(xmin=-28, xmax=28, ymin=-28, ymax=28)
    far = run(Document.from_dict(d), False).effective_index[0]
    assert np.max(abs(near - far)) < 1e-5


@pytest.mark.slow
def test_vector_hadley_document_matches_reference_and_refines():
    d = copy.deepcopy(examples.HADLEY_RIB_VECTOR)
    exact = benchmarks.rib_neff(0.3)
    errors = [abs(run(_refined(d, s), False).effective_index[0, 0] - exact) for s in (1.0, 0.65)]
    assert errors[0] / exact < 2e-4
    assert errors[1] < 0.8 * errors[0]
    assert errors[1] / exact < 1e-4


def rescale(doc, symbol, ratio):
    """The same slab with its shape numbers written in ``symbol`` (tagged lengths keep their
    units: the geometry's length_unit names the shape numbers only)."""
    d = copy.deepcopy(doc.data)
    d["geometry"]["length_unit"] = symbol
    d["geometry"]["domain"] = {k: float(v) * ratio for k, v in d["geometry"]["domain"].items()}
    for shape in d["geometry"]["shapes"]:
        for key in ("x", "y", "w", "h"):
            shape[key] = float(shape[key]) * ratio
    return Document.from_dict(d)


@pytest.mark.parametrize("symbol,ratio", [("nm", 1e3), ("um", 1.0), ("m", 1e-6)])
def test_vector_units_and_saved_raw_fields_reconstruct_the_physical_field(symbol, ratio, tmp_path):
    doc = rescale(slab_document("TM"), symbol, ratio)
    result = run(doc, verbose=False)
    exact = slab.modes(3.48, 1.444, 1.444, 0.22, 1.55, "TM")[0]
    assert abs(result.effective_index[0, 0] - exact) < 1e-3
    assert result.mode_fields == [] and result.group_index() is None
    out = result.save(tmp_path / symbol)
    summary = json.loads((out / "summary.json").read_text())
    assert "units" not in summary and "mesh_length_unit" not in summary and "length_unit_to_m" not in summary
    assert summary["field_representation"] == "vector-edge-nodal-v2"
    assert summary["returned_mode_count"] == summary["mode_count"] == 1
    # The saved layout and the SI unit of every array are recorded, so a reader needs no
    # document: node coordinates and line integrals in metres.
    assert summary["field_layout"] == "em-modes2d-p1-node-centroid-v2"
    assert summary["field_units"]["node_coordinates"] == "m"
    assert summary["field_units"]["unnormalized_electric_field_line_integral"] == "m"
    assert summary["time_convention"] == "exp(-i omega t)" and summary["propagation"] == "exp(+i beta z)"
    assert (out / "results.png").stat().st_size > 0
    with np.load(out / "fields.npz", allow_pickle=False) as arrays:
        assert "unnormalized_mode_field" not in arrays  # a vector must never masquerade as nodal scalar data
        assert str(arrays["field_layout"]) == "em-modes2d-p1-node-centroid-v2"
        assert "mesh_length_unit" not in arrays and "length_unit_to_m" not in arrays
        assert str(arrays["study_parameter"]) == ""
        mesh = Mesh(arrays["node_coordinates"], arrays["triangles"], {})
        space = EdgeSpace(mesh)
        np.testing.assert_array_equal(space.edges, arrays["edges"])
        electric = arrays["unnormalized_electric_field"][0]
        transverse = arrays["unnormalized_electric_field_line_integral"][0]
        longitudinal = arrays["unnormalized_electric_field_z"][0]
        np.testing.assert_allclose(eval_edge_field(space, transverse[:, 0]), electric[:, 0, :2], atol=1e-12)
        np.testing.assert_allclose(longitudinal[mesh.triangles].mean(axis=1), electric[:, :, 2], atol=1e-12)
        assert np.max(abs(electric[:, :, 2].imag)) > 0.1
        assert np.max(abs(electric[:, :, 2].real)) == 0
        np.testing.assert_allclose(np.linalg.norm(electric, axis=2).max(axis=0), 1.0)
        # Line integrals carry a length (metres here, whatever the document's unit); E samples do not.
        assert np.max(abs(transverse)) / 1e-6 < 0.1
    payload = result.vector_fields[0].to_dict()
    assert payload["components"] == ["x", "y", "z"] and payload["unit"] == "1"
    back = np.array(payload["real"]) + 1j * np.array(payload["imag"])
    np.testing.assert_array_equal(back.transpose(1, 0, 2), result.vector_fields[0].electric)


def test_vector_saved_coefficients_satisfy_the_maxwell_block_system_and_pec():
    doc = slab_document("TM")
    model = build_mesh(doc)
    point = solve_point(model, doc.si["physics"]["em1"])
    f = point["vector_field"]
    # SI throughout: nodes, line integrals and the wavelength in metres; under exp(-i omega t)
    # the saved E_z is the conjugate of the kernel's, so E_z = -1j * ez becomes +1j
    k0 = 2 * np.pi / doc.si["physics"]["em1"]["vacuum_wavelength"]
    beta = k0 * point["effective_index"][0]
    A, B, space = assemble_mode_system(model.mesh, model.relative_permittivity(1.55e-6).real, k0)
    x = np.r_[beta * f.transverse[:, 0], 1j * f.longitudinal[:, 0]]
    pec = np.unique(np.concatenate([model.mesh.boundary[s] for s in ("top", "bottom")]))
    fixed = np.r_[space.boundary_edge_ids(pec), space.num_edges + pec]
    free = np.setdiff1d(np.arange(len(x)), fixed)
    assert np.max(abs(x[fixed])) == 0
    left, right = (A @ x)[free], (-beta**2 * (B @ x))[free]
    assert np.linalg.norm(left - right) / (np.linalg.norm(left) + np.linalg.norm(right)) < 1e-9


def test_vector_single_edge_pmc_wall_is_not_fixed_by_pec_corners():
    d = copy.deepcopy(slab_document(pad=0.5).data)
    d["mesh"]["element_size"] = d["mesh"]["grading"]["far"] = "0.2 um"
    d["physics"]["em1"]["boundary"].update(top="pmc", bottom="pmc")
    doc = Document.from_dict(d)
    model = build_mesh(doc)
    point = solve_point(model, doc.si["physics"]["em1"])
    f = point["vector_field"]
    k0 = 2 * np.pi / 1.55e-6
    beta = k0 * point["effective_index"][0]
    A, B, space = assemble_mode_system(model.mesh, model.relative_permittivity(1.55e-6).real, k0)
    edge_ids = {tuple(edge): i for i, edge in enumerate(space.edges)}
    for side in ("top", "bottom"):
        edges = model.mesh.boundary_edges[side]
        assert len(edges) == 1  # both endpoints belong to neighboring PEC walls
        edge_id = edge_ids[tuple(sorted(edges[0]))]
        assert abs(f.transverse[edge_id, 0]) > 1e-10      # 1e-4 um: line integrals are in metres
    pec = np.unique(np.concatenate([model.mesh.boundary[s] for s in ("left", "right")]))
    pec_edges = [edge_ids[tuple(sorted(edge))] for s in ("left", "right")
                 for edge in model.mesh.boundary_edges[s]]
    x = np.r_[beta * f.transverse[:, 0], 1j * f.longitudinal[:, 0]]
    fixed = np.r_[pec_edges, space.num_edges + pec]
    free = np.setdiff1d(np.arange(len(x)), fixed)
    assert np.max(abs(x[fixed])) == 0
    left, right = (A @ x)[free], (-beta**2 * (B @ x))[free]
    assert np.linalg.norm(left - right) / (np.linalg.norm(left) + np.linalg.norm(right)) < 1e-9


@pytest.mark.parametrize("key,value,code", [
    ("effective_index_threshold", None, "E-VALUE-FORM"), ("effective_index_threshold", True, "E-VALUE-FORM"),
    ("effective_index_threshold", 0, "E-DOMAIN"), ("effective_index_threshold", float("inf"), "E-JSON"),
    ("mode_count", 1.5, None), ("mode_count", float("nan"), "E-JSON"), ("mode_count", True, "E-VALUE-FORM")])
def test_vector_input_contract_rejects_invalid_numbers(key, value, code):
    d = copy.deepcopy(examples.VECTOR_SLAB)
    d["physics"]["em1"][key] = value
    with pytest.raises(DocumentError, match=key) as caught:
        Document.from_dict(d)
    found = [x for x in caught.value.diagnostics if x.path == f"physics.em1.{key}"]
    assert found and (code is None or found[0].code == code), [x.as_dict() for x in caught.value.diagnostics]


@pytest.mark.parametrize("target", ["wavelength", "formulation", "physics_map"])
def test_invalid_vector_sweep_is_rejected_before_meshing(target):
    d = copy.deepcopy(examples.VECTOR_SLAB)
    d["study"] = dict(type="sweep", parameter="physics.em1.vacuum_wavelength", values={"unit": "um", "values": [1.5, 1.6]})
    if target != "wavelength":
        vector_settings = copy.deepcopy(d["physics"]["em1"])
        d["physics"]["em1"]["formulation"] = "scalar"
        del d["physics"]["em1"]["effective_index_threshold"]
        d["study"] = dict(type="sweep", parameter="physics.em1.formulation", values=["scalar", "vector"])
        if target == "physics_map":
            d["study"] = dict(type="sweep", parameter="physics.em1", values=[vector_settings])
    message = {"wavelength": "at least 3", "formulation": "cannot switch to vector",
               "physics_map": "is not a value that can be swept"}[target]
    with pytest.raises(DocumentError, match=message):
        Document.from_dict(d)


def test_vector_zero_index_is_refused_by_the_registry_domain():
    # n = 0 was accepted by the 0.2 reader and refused by the solver; refractive_index > 0 is
    # now a registry domain (phase-2 spec 7.3, an intended tightening)
    d = copy.deepcopy(examples.VECTOR_SLAB)
    d["materials"]["film"] = {"refractive_index": 0.0}
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(d)
    assert [(x.code, x.path) for x in caught.value.diagnostics] == [("E-DOMAIN", "materials.film.refractive_index")]


def test_missing_modes_are_reported_without_padding_and_empty_search_fails():
    d = copy.deepcopy(examples.VECTOR_SLAB)
    d["physics"]["em1"]["mode_count"] = 4
    res = run(Document.from_dict(d), False)
    assert 0 < res.effective_index.shape[1] < 4
    assert res.vector_fields[0].electric.shape[1] == res.effective_index.shape[1]
    assert any("requested 4 modes; found" in line for line in res.log)
    for threshold, message in [(3.479, "no guided"), (3.48, "below the maximum")]:
        d["physics"]["em1"]["effective_index_threshold"] = threshold
        with pytest.raises(ValueError, match=message):
            run(Document.from_dict(d), False)
