# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""A document's declared length unit does not reach the mesher or the solver.

simcase converts every em.modes2d length to micrometres before geometry and
meshing, solves there, and hands coordinates back in the document unit. So the
same device written in nm, um or m gives meshine the same doubles, and from there
the same mesh and the same answer.

Why bitwise equality is a sound assertion here, under any BLAS kernel: it is not
a claim about rounding inside a solver. It follows from the solver inputs being
the same doubles. The nm and m documents below hold the exact decimal rescaling
of the um numbers (what a person would type), each length is converted to um
with one correctly rounded operation, and identical inputs through the same
deterministic code on one machine give identical outputs. If the conversion is
not exact, the meshes differ and these tests fail; that is the point. Nothing
here compares results across machines or kernels.

Values that are not exactly representable after conversion are outside this
contract: one ulp of input can change a mesh. The other unit tests (own-mesh
tolerances in test_simcase and test_subspace_sweep) still cover those.
"""

from __future__ import annotations

import copy
from decimal import Decimal

import numpy as np
import pytest

from simcase import Document, build_mesh, examples, run, solve_point, units
from simcase.runner import micrometre_document

#: document units per micrometre, as exact decimals
SCALES = [("nm", "1000"), ("m", "1e-6")]


def _exact(value, per_um: str) -> float:
    return float(Decimal(repr(float(value))) * Decimal(per_um))


def _written_in(doc: dict, symbol: str, per_um: str) -> dict:
    """The same document typed in another unit: every length rescaled as a decimal."""
    d = copy.deepcopy(doc)
    x = lambda v, power=1: _exact(_exact(v, per_um), per_um) if power == 2 else _exact(v, per_um)  # noqa: E731
    d["units"] = dict(d["units"], length=symbol)
    g = d["geometry"]
    g["domain"] = {k: x(v) for k, v in g["domain"].items()}
    for s in g["shapes"]:
        for k in ("x", "y", "w", "h", "cx", "cy", "r", "mesh_size"):
            if k in s:
                s[k] = x(s[k])
        if "points" in s:
            s["points"] = [[x(c) for c in p] for p in s["points"]]
    m = d["mesh"]
    m["size"] = x(m["size"])
    if m.get("grading"):
        gr = m["grading"]
        gr["center"] = [x(c) for c in gr["center"]]
        for k in ("near", "far", "distance"):
            gr[k] = x(gr[k])
    for p in d["physics"].values():
        p["wavelength"] = x(p["wavelength"])
    st = d["study"]
    if st["type"] == "sweep":
        st["values"] = [x(v) for v in st["values"]]
    for spec in d.get("materials", {}).values():
        if "sellmeier" in spec:
            spec["sellmeier"]["C"] = [x(c, 2) for c in spec["sellmeier"]["C"]]
            if "range" in spec["sellmeier"]:
                spec["sellmeier"]["range"] = [x(r) for r in spec["sellmeier"]["range"]]
    return d


def _rib_with_polygon_and_sellmeier() -> dict:
    """Every length kind the format has: rect, circle, polygon, grading, Sellmeier C and range."""
    d = copy.deepcopy(examples.SLAB_TE_CHECK)
    d.setdefault("materials", {})["glass"] = {"sellmeier": {"B": [0.6961663, 0.4079426, 0.8974794],
                                             "C": [0.0684043 ** 2, 0.1162414 ** 2, 9.896161 ** 2],
                                             "range": [0.21, 6.7]}}
    d["geometry"]["background"]["material"] = "glass"
    d["geometry"]["shapes"].append({"name": "wedge", "type": "polygon", "material": "Si",
                                    "points": [[-0.3, -0.6], [0.3, -0.6], [0.2, -0.3], [-0.2, -0.3]]})
    d["geometry"]["shapes"].append({"name": "dot", "type": "circle", "cx": 0.25, "cy": -0.8, "r": 0.08,
                                    "material": "Si", "mesh_size": 0.03})
    return d


def _same_mesh(a, b):
    np.testing.assert_array_equal(a.solver_mesh.nodes, b.solver_mesh.nodes)
    np.testing.assert_array_equal(a.tri.triangles, b.tri.triangles)
    np.testing.assert_array_equal(a.tri.regions, b.tri.regions)
    assert a.tri.region_names == b.tri.region_names
    assert a.tri.boundary_edges.keys() == b.tri.boundary_edges.keys()
    for side in a.tri.boundary_edges:
        np.testing.assert_array_equal(a.tri.boundary_edges[side], b.tri.boundary_edges[side])


def test_lengths_convert_exactly_when_the_micrometre_value_is_representable():
    nm = Document.from_dict(_written_in(examples.SLAB_TE_CHECK, "nm", "1000")).scale
    m = Document.from_dict(_written_in(examples.SLAB_TE_CHECK, "m", "1e-6")).scale
    um = Document.from_dict(copy.deepcopy(examples.SLAB_TE_CHECK)).scale
    assert units.micrometres_per_length(nm) == units.Fraction(1, 1000)
    assert units.micrometres_per_length(m) == 10 ** 6
    for value in (1.55, 0.22, 0.012, 9.896161 ** 2, 1e-7, 123.456):
        assert units.length_to_micrometres(value, um) == value
    assert units.length_to_micrometres(1550, nm) == 1.55
    assert units.length_to_micrometres(1.55e-6, m) == 1.55
    # where one binary product, or the SI round trip, misses the decimal by an ulp
    assert 1.3e-8 * 1e6 != 0.013 and units.length_to_micrometres(1.3e-8, m) == 0.013
    assert 9.0 * 0.001 != 0.009 and units.length_to_micrometres(9.0, nm) == 0.009
    assert 2.2e-7 / 1e-6 != 0.22 and units.length_to_micrometres(2.2e-7, m) == 0.22
    assert units.length_to_micrometres(1e4, nm, power=2) == 0.01
    assert units.length_to_micrometres(float("inf"), nm) == float("inf")
    assert units.to_micrometres(1550.0, nm) == units.length_to_micrometres(1550.0, nm)
    back = units.lengths_from_micrometres(np.array([1.55, 0.22]), nm)
    np.testing.assert_array_equal(back, [1550.0, 220.0])


def test_a_micrometre_document_meshes_exactly_as_before():
    """um is the internal unit, so a um document's mesh and coordinates are the mesher's own."""
    doc = Document.from_dict(_rib_with_polygon_and_sellmeier())
    assert micrometre_document(doc).data == doc.data
    model = build_mesh(doc)
    np.testing.assert_array_equal(model.tri.nodes, model.solver_mesh.nodes)
    np.testing.assert_array_equal(model.mesh.nodes, model.solver_mesh.nodes)


@pytest.mark.parametrize("symbol,per_um", SCALES)
def test_every_length_kind_gives_the_same_mesh_in_any_unit(symbol, per_um):
    base = _rib_with_polygon_and_sellmeier()
    um = build_mesh(Document.from_dict(base))
    other_doc = Document.from_dict(_written_in(base, symbol, per_um))
    other = build_mesh(other_doc)
    _same_mesh(um, other)
    # coordinates come back in the document unit
    np.testing.assert_array_equal(other.tri.nodes, units.lengths_from_micrometres(um.tri.nodes, other_doc.scale))
    np.testing.assert_array_equal(other.mesh.nodes, other.tri.nodes)
    dom = other_doc.domain
    assert other.tri.nodes[:, 0].min() == pytest.approx(dom["xmin"], rel=1e-15)
    assert other.tri.nodes[:, 1].max() == pytest.approx(dom["ymax"], rel=1e-15)
    # the Sellmeier glass reaches physmat as the same model
    for wl_um in (1.4, 1.55):
        wl_doc = _exact(wl_um, per_um)
        np.testing.assert_array_equal(other.eps_per_triangle(wl_doc), um.eps_per_triangle(wl_um))


@pytest.mark.parametrize("symbol,per_um", SCALES)
def test_a_scalar_run_gives_the_same_answer_in_any_unit(symbol, per_um):
    base = copy.deepcopy(examples.FIBER)
    um = run(Document.from_dict(base), verbose=False)
    other = run(Document.from_dict(_written_in(base, symbol, per_um)), verbose=False)
    np.testing.assert_array_equal(other.neff, um.neff)
    np.testing.assert_array_equal(np.stack(other.fields), np.stack(um.fields))
    np.testing.assert_array_equal(other.mesh_triangles, um.mesh_triangles)
    scale = other.doc.scale
    np.testing.assert_array_equal(other.mesh_nodes, units.lengths_from_micrometres(um.mesh_nodes, scale))
    assert other.values == [_exact(1.55, per_um)]


@pytest.mark.parametrize("symbol,per_um", SCALES)
def test_a_vector_solve_gives_the_same_field_in_any_unit(symbol, per_um):
    base = copy.deepcopy(examples.VECTOR_SLAB)
    um_doc = Document.from_dict(base)
    other_doc = Document.from_dict(_written_in(base, symbol, per_um))
    um_model, other_model = build_mesh(um_doc), build_mesh(other_doc)
    a = solve_point(um_model, um_doc.sole_physics()[1])
    b = solve_point(other_model, other_doc.sole_physics()[1])
    np.testing.assert_array_equal(b["neff"], a["neff"])
    fa, fb = a["vector_field"], b["vector_field"]
    np.testing.assert_array_equal(fb.edges, fa.edges)
    np.testing.assert_array_equal(fb.electric, fa.electric)
    np.testing.assert_array_equal(fb.longitudinal, fa.longitudinal)
    # line integrals of E_t carry one length: they come back in the document unit
    np.testing.assert_array_equal(fb.transverse, units.lengths_from_micrometres(fa.transverse, other_doc.scale))


@pytest.mark.parametrize("symbol,per_um", SCALES)
def test_a_subspace_sweep_gives_the_same_answer_in_any_unit(symbol, per_um):
    base = copy.deepcopy(examples.VECTOR_FIBER_SUBSPACE_SWEEP)
    um = run(Document.from_dict(base), verbose=False)
    other = run(Document.from_dict(_written_in(base, symbol, per_um)), verbose=False)
    np.testing.assert_array_equal(other.neff, um.neff)
    for fa, fb in zip(um.vector_fields, other.vector_fields):
        np.testing.assert_array_equal(fb.electric, fa.electric)
        np.testing.assert_array_equal(fb.longitudinal, fa.longitudinal)
    for ta, tb in zip(um.frame_transforms, other.frame_transforms):
        np.testing.assert_array_equal(tb, ta)
    assert other.mode_tracking["points"] == um.mode_tracking["points"]
