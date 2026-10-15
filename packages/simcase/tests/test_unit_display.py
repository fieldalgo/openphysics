# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Output labels must describe the numbers actually written by the document."""

import copy
import json

import numpy as np
import pytest

from simcase import Document, RunResult, examples


@pytest.fixture(params=[
    ("nm", "nm"), ("um", "um"), ("µm", "µm"), ("m", "m"),
    ({"in_m": 1e-10}, "1e-10 m"),
    ({"in_m": 1.23456789e-10}, "1.23456789e-10 m"),
])
def declared_document(request):
    declaration, label = request.param
    doc = Document.from_dict(dict(examples.SLAB_TE_CHECK, units={"length": declaration}))
    return doc, label


def test_summary_labels_document_numbers_without_converting_them(declared_document):
    doc, label = declared_document
    before = copy.deepcopy(doc.data)
    text = doc.summary()
    assert f"y [-1.2, 1.2] [{label}]" in text
    assert f"lambda 1.55 [{label}]" in text
    assert f"mesh 0.01 [{label}]" in text
    assert f"mesh: size 0.25 [{label}]" in text
    assert doc.data == before


@pytest.mark.parametrize("parameter", [None, "physics.em1.wavelength", "physics.em1.num_modes"])
def test_saved_results_label_lengths_but_not_dimensionless_sweeps(
        declared_document, parameter, tmp_path, monkeypatch):
    from matplotlib.figure import Figure

    doc, label = declared_document
    values = [1.55] if parameter is None else [1.5, 1.6] if parameter.endswith(".wavelength") else [1, 2]
    nodes = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    result = RunResult(
        doc, nodes, np.array([[0, 1, 2]]), np.array([0]), ["film"], {"film": "Si"},
        parameter, values, np.full((len(values), 1), 2.8),
        [np.array([[1.0], [2.0], [3.0]]) for _ in values],
    )
    captured = {}
    savefig = Figure.savefig

    def capture_figure(fig, *args, **kwargs):
        captured["axes"] = [(ax.get_xlabel(), ax.get_ylabel(), ax.get_title()) for ax in fig.axes]
        if parameter is not None:
            captured["sweep_values"] = fig.axes[2].lines[0].get_xdata().copy()
        return savefig(fig, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", capture_figure)
    result.save(tmp_path)
    axes = captured["axes"]
    for xlabel, ylabel, _title in axes[:2]:
        assert xlabel == f"x ({label})"
        assert ylabel == f"y ({label})"
    if parameter is None or parameter.endswith(".wavelength"):
        assert f"[{label}]" in axes[1][2]
    else:
        assert f"[{label}]" not in axes[1][2]
    if parameter is not None:
        expected = f"{parameter} ({label})" if parameter.endswith(".wavelength") else parameter
        assert axes[2][0] == expected
        np.testing.assert_array_equal(captured["sweep_values"], values)

    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["units"] == doc["units"]
    assert summary["study"]["values"] == values
    with np.load(tmp_path / "fields.npz") as fields:
        np.testing.assert_array_equal(fields["nodes"], nodes)
    assert (tmp_path / "results.png").stat().st_size > 0
    if isinstance(doc["units"]["length"], dict):
        original = doc["units"]["length"]["in_m"]
        result.summary()["units"]["length"]["in_m"] = 1.0
        assert doc["units"]["length"]["in_m"] == original
