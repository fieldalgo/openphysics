# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""A document's length unit does not reach the mesher or the solver (P2-5 for em.modes2d).

simcase converts every em.modes2d length to micrometres from its exact value
(``float(exact * 10**6)``, one correctly rounded operation) before geometry and
meshing, solves there, and hands coordinates back in metres (the micrometre doubles
times 1e-6). So the same device written in nm, um or m gives meshine and the mode
kernel the same doubles, and from there the same mesh and the same answer, bitwise:
arrays, fields and tracking.

Why bitwise equality is a sound assertion here, under any BLAS kernel: it is not
a claim about rounding inside a solver. It follows from the solver inputs being
the same doubles. The nm and m documents below hold the exact decimal rescaling
of the um numbers (what a person would type), and identical inputs through the same
deterministic code on one machine give identical outputs. If the conversion is not
exact, the meshes differ and these tests fail; that is the point. Nothing here
compares results across machines or kernels.

Values whose micrometre double is not the one a person would type are outside this
contract: one ulp of input can change a mesh (the nm and m twins of the units batch
fixtures, written by float products, are such a case; tools/units_batch/README.md).
"""

from __future__ import annotations

import copy
from decimal import Decimal
import re

import numpy as np
import pytest

from simcase import Document, build_mesh, examples, run, solve_point, study_points, units, views
from simcase.modes_document import kernel_document

#: document units per micrometre, as exact decimals
SCALES = [("nm", "1000"), ("m", "1e-6")]
TAGGED = re.compile(r"(-?[0-9][0-9.eE+-]*) um(\^2)?")


def _exact(value, per_um: str) -> float:
    return float(Decimal(repr(float(value))) * Decimal(per_um))


def _written_in(data: dict, symbol: str, per_um: str) -> dict:
    """The same document typed in another unit: the shape numbers in ``length_unit`` and every
    tagged length (and square length) rescaled as a decimal."""
    d = copy.deepcopy(data)
    g = d["geometry"]
    g["length_unit"] = symbol
    g["domain"] = {k: _exact(v, per_um) for k, v in g["domain"].items()}
    for s in g["shapes"]:
        for k in ("x", "y", "w", "h", "cx", "cy", "r"):
            if k in s:
                s[k] = _exact(s[k], per_um)
        if "points" in s:
            s["points"] = [[_exact(c, per_um) for c in p] for p in s["points"]]

    def retag(node):
        if isinstance(node, dict):
            if node.get("unit") == "um" and isinstance(node.get("values"), list):     # a wavelength list
                return {"unit": symbol, "values": [_exact(v, per_um) for v in node["values"]]}
            return {k: retag(v) for k, v in node.items()}
        if isinstance(node, list):
            return [retag(v) for v in node]
        found = TAGGED.fullmatch(node) if isinstance(node, str) else None
        if found is None:
            return node
        power = 2 if found.group(2) else 1
        return f"{Decimal(found.group(1)) * Decimal(per_um) ** power} {symbol}{found.group(2) or ''}"
    return retag(d)


def _rib_with_polygon_and_sellmeier() -> dict:
    """Every length kind the format has: rect, circle, polygon, grading, Sellmeier resonance and range."""
    d = copy.deepcopy(examples.SLAB_TE_CHECK)
    d["materials"] = {"glass": {"refractive_index": {
        "model": "sellmeier",
        "terms": [{"strength": b, "resonance_wavelength_squared": f"{c ** 2!r} um^2"}
                  for b, c in ((0.6961663, 0.0684043), (0.4079426, 0.1162414), (0.8974794, 9.896161))],
        "valid": {"vacuum_wavelength": ["0.21 um", "6.7 um"]}, "reference_medium": "vacuum"}}}
    d["geometry"]["background"]["material"] = "glass"
    d["geometry"]["shapes"].append({"name": "wedge", "type": "polygon", "material": "physmat:Si",
                                    "points": [[-0.3, -0.6], [0.3, -0.6], [0.2, -0.3], [-0.2, -0.3]]})
    d["geometry"]["shapes"].append({"name": "dot", "type": "circle", "cx": 0.25, "cy": -0.8, "r": 0.08,
                                    "material": "physmat:Si", "element_size": "0.03 um"})
    return d


def _same(a: np.ndarray, b: np.ndarray, what: str):
    a, b = np.asarray(a), np.asarray(b)
    assert a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes(), what


def _same_mesh(a, b):
    _same(a.solver_mesh.nodes, b.solver_mesh.nodes, "micrometre nodes")
    _same(a.tri.nodes, b.tri.nodes, "nodes in metres")
    _same(a.mesh.nodes, b.mesh.nodes, "solver mesh in metres")
    _same(a.tri.triangles, b.tri.triangles, "triangles")
    _same(a.tri.regions, b.tri.regions, "regions")
    assert a.tri.region_names == b.tri.region_names
    assert a.tri.boundary_edges.keys() == b.tri.boundary_edges.keys()
    for side in a.tri.boundary_edges:
        _same(a.tri.boundary_edges[side], b.tri.boundary_edges[side], side)


def test_lengths_convert_exactly_when_the_micrometre_value_is_representable():
    # the kernel hand-off takes each length from its exact value: float(exact * 10**6)
    for symbol, per_um in SCALES:
        k = kernel_document(Document.from_dict(_written_in(examples.VECTOR_SLAB, symbol, per_um)))
        assert k["physics"]["em1"]["wavelength"] == 1.55
        assert k["geometry"]["shapes"][0]["mesh_size"] == 0.012
        assert k["geometry"]["domain"] == {"xmin": -0.05, "xmax": 0.05, "ymin": -1.5, "ymax": 1.72}
        assert k["mesh"]["grading"] == {"center": [0.0, 0.11], "near": 0.012, "far": 0.06, "distance": 1.0}
    # where one binary product, or the SI round trip, misses the decimal by an ulp
    data = copy.deepcopy(examples.VECTOR_SLAB)
    data["geometry"]["shapes"][0]["element_size"] = "1.3e-8 m"
    data["mesh"]["element_size"] = "9 nm"
    data["physics"]["em1"]["vacuum_wavelength"] = "2.2e-7 m"
    k = kernel_document(Document.from_dict(data))
    assert 1.3e-8 * 1e6 != 0.013 and k["geometry"]["shapes"][0]["mesh_size"] == 0.013
    assert 9.0 * 0.001 != 0.009 and k["mesh"]["size"] == 0.009
    assert 2.2e-7 / 1e-6 != 0.22 and k["physics"]["em1"]["wavelength"] == 0.22
    # the format 0.2 helpers (still read by em.cavity3d and the region hand-offs) keep their contract
    nm, m, um = (units.resolve({"length": s}) for s in ("nm", "m", "um"))
    assert units.micrometres_per_length(nm) == units.Fraction(1, 1000)
    assert units.micrometres_per_length(m) == 10 ** 6
    for value in (1.55, 0.22, 0.012, 9.896161 ** 2, 1e-7, 123.456):
        assert units.length_to_micrometres(value, um) == value
    assert units.length_to_micrometres(1550, nm) == 1.55
    assert units.length_to_micrometres(1.3e-8, m) == 0.013
    assert units.length_to_micrometres(1e4, nm, power=2) == 0.01
    np.testing.assert_array_equal(units.lengths_from_micrometres(np.array([1.55, 0.22]), nm), [1550.0, 220.0])


def test_a_micrometre_document_meshes_in_its_own_numbers_and_hands_back_metres():
    """um is the kernel's unit: the hand-off holds the document's numbers, and the nodes in metres are
    the mesher's micrometre nodes times 1e-6."""
    doc = Document.from_dict(_rib_with_polygon_and_sellmeier())
    k = kernel_document(doc)
    assert k["geometry"]["domain"] == {key: float(v) for key, v in doc.data["geometry"]["domain"].items()}
    model = build_mesh(doc)
    _same(model.kernel_tri.nodes, model.solver_mesh.nodes, "kernel nodes")
    _same(model.tri.nodes, views.handback_m(model.kernel_tri.nodes), "hand-back")
    _same(model.mesh.nodes, model.tri.nodes, "solver mesh in metres")


@pytest.mark.parametrize("symbol,per_um", SCALES)
def test_every_length_kind_gives_the_same_mesh_in_any_unit(symbol, per_um):
    base = _rib_with_polygon_and_sellmeier()
    um = build_mesh(Document.from_dict(base))
    other = build_mesh(Document.from_dict(_written_in(base, symbol, per_um)))
    _same_mesh(um, other)
    assert other.tri.nodes[:, 0].min() == pytest.approx(-5e-7, rel=1e-15)        # metres
    assert other.tri.nodes[:, 1].max() == pytest.approx(1.2e-6, rel=1e-15)
    # the Sellmeier glass reaches physmat as the same model
    for wavelength in (1.4e-6, 1.55e-6):
        _same(other.relative_permittivity(wavelength), um.relative_permittivity(wavelength), "permittivity")


@pytest.mark.parametrize("symbol,per_um", SCALES)
def test_a_scalar_run_gives_the_same_answer_in_any_unit(symbol, per_um):
    base = copy.deepcopy(examples.FIBER)
    um = run(Document.from_dict(base), verbose=False)
    other = run(Document.from_dict(_written_in(base, symbol, per_um)), verbose=False)
    for name in ("effective_index", "node_coordinates", "triangles", "regions", "vacuum_wavelength"):
        _same(getattr(other, name), getattr(um, name), name)
    _same(np.stack(other.mode_fields), np.stack(um.mode_fields), "mode fields")
    assert other.vacuum_wavelength.tolist() == [1.55 * 1e-6]             # the kernel's 1.55 times 1e-6
    assert other.summary()["mode_postprocessing"] == um.summary()["mode_postprocessing"]


@pytest.mark.parametrize("symbol,per_um", SCALES)
def test_a_vector_solve_gives_the_same_field_in_any_unit(symbol, per_um):
    base = copy.deepcopy(examples.VECTOR_SLAB)
    um_doc = Document.from_dict(base)
    other_doc = Document.from_dict(_written_in(base, symbol, per_um))
    a = solve_point(build_mesh(um_doc), um_doc.si["physics"]["em1"])
    b = solve_point(build_mesh(other_doc), other_doc.si["physics"]["em1"])
    _same(b["effective_index"], a["effective_index"], "effective_index")
    fa, fb = a["vector_field"], b["vector_field"]
    for name in ("edges", "electric", "longitudinal", "transverse"):          # line integrals in metres
        _same(getattr(fb, name), getattr(fa, name), name)


@pytest.mark.parametrize("symbol,per_um", SCALES)
def test_a_subspace_sweep_gives_the_same_answer_in_any_unit(symbol, per_um):
    base = copy.deepcopy(examples.VECTOR_FIBER_SUBSPACE_SWEEP)
    um = run(Document.from_dict(base), verbose=False)
    other = run(Document.from_dict(_written_in(base, symbol, per_um)), verbose=False)
    _same(other.effective_index, um.effective_index, "effective_index")
    _same(other.vacuum_wavelength, um.vacuum_wavelength, "vacuum_wavelength")
    for fa, fb in zip(um.vector_fields, other.vector_fields):
        for name in ("electric", "longitudinal", "transverse"):
            _same(getattr(fb, name), getattr(fa, name), name)
    for ta, tb in zip(um.frame_transforms, other.frame_transforms):
        _same(tb, ta, "frame transform")
    assert other.mode_tracking["points"] == um.mode_tracking["points"]


def _recorded_kernel_calls(monkeypatch):
    """Record each mode kernel solve: its mesh, permittivity and settings, as bytes and values."""
    from simcase import physics_em_modes2d
    calls = []
    real = physics_em_modes2d.solve

    def recording(mesh, eps, wavelength, boundary, num_modes, formulation, n_cladding, **kwargs):
        calls.append({"nodes": mesh.nodes.tobytes(), "triangles": mesh.triangles.tobytes(),
                      "eps": np.asarray(eps).tobytes(), "wavelength": wavelength, "boundary": dict(boundary),
                      "num_modes": num_modes, "formulation": formulation, "n_cladding": n_cladding, **kwargs})
        return real(mesh, eps, wavelength, boundary, num_modes, formulation, n_cladding, **kwargs)
    monkeypatch.setattr(physics_em_modes2d, "solve", recording)
    return calls


def _stage_calls(doc, calls):
    """solve_point at each study point of ``doc``, from the SI values study_points gives."""
    model = build_mesh(doc)
    parameter, values = study_points(doc)
    start = len(calls)
    for value in values:
        point = doc if parameter is None else doc.with_value(parameter, value)
        solve_point(model, point.si["physics"]["em1"])
    return calls[start:]


def test_run_and_solve_point_hand_the_kernel_the_same_doubles(monkeypatch):
    """Section 3.8: the stage API takes SI (a vacuum wavelength in metres) and gives the mode kernel
    exactly the micrometre doubles run gives it, at every point of the soi_strip sweep. The one
    difference is the candidate count: a tracked sweep searches search_mode_count candidates (its
    default max(2 mode_count, mode_count + 4) = 6 here), a stage solve asks for mode_count."""
    calls = _recorded_kernel_calls(monkeypatch)
    doc = Document.from_dict(copy.deepcopy(examples.SOI_STRIP))
    run(doc, verbose=False)
    by_run = list(calls)
    by_stage = _stage_calls(doc, calls)
    assert len(by_run) == len(by_stage) == 7
    assert [c["num_modes"] for c in by_run] == [6] * 7 and [c["num_modes"] for c in by_stage] == [2] * 7
    for a, b in zip(by_run, by_stage):
        assert {k: v for k, v in a.items() if k != "num_modes"} == {k: v for k, v in b.items() if k != "num_modes"}
    assert [c["wavelength"] for c in by_stage] == [1.4, 1.45, 1.5, 1.55, 1.6, 1.65, 1.7]     # micrometres
    # a single point: every argument is the same
    calls.clear()
    single = copy.deepcopy(examples.SOI_STRIP)
    single["study"] = {"type": "single"}
    doc = Document.from_dict(single)
    run(doc, verbose=False)
    (by_run,) = calls
    (by_stage,) = _stage_calls(doc, calls)
    assert by_run == by_stage and by_stage["wavelength"] == 1.55
