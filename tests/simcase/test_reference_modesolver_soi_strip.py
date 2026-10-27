# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""SOI strip TE0/TM0 against stored modesolver values (finite differences).

The stored record holds modesolver 3.0.2 n_eff on four uniform grids at 1.50,
1.55 and 1.60 um. This test rebuilds the same strip from the record's inputs,
solves it with simcase on the example mesh and on a mesh with every length
setting halved, and reports the differences from the modesolver values
Richardson-extrapolated over its three finest grids. A different
discretization is report-only: there are no gates, and the analytical checks
of the vector solver stay in test_vector.py.
"""
import importlib.util
from pathlib import Path

import numpy as np
import pytest
from reference_loader import load_reference

from simcase import Document, run

HERE = Path(__file__).resolve().parent
RECORD = HERE / "reference_values" / "modesolver" / "soi_strip_modes.json"


def crosscheck_helpers():
    spec = importlib.util.spec_from_file_location("crosscheck", HERE.parent / "galerkin" / "crosscheck.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def document(inputs, factor):
    window, core = inputs["window_um"], inputs["core_um"]
    return {
        "openphysics": "0.2",
        "name": "SOI strip, modesolver comparison",
        "units": {"length": "um"},
        "geometry": {"domain": dict(window), "background": {"material": inputs["background_material"]},
                     "shapes": [{"name": "core", "type": "rect", **core, "material": inputs["core_material"],
                                 "mesh_size": 0.02 * factor}]},
        "physics": {"em1": {"type": "em.modes2d", "formulation": "vector", "wavelength": 1.55,
                            "num_modes": len(inputs["modes"]), "n_cladding": 1.45,
                            "boundary": {side: "pec" for side in ("left", "right", "top", "bottom")}}},
        "mesh": {"size": 0.25 * factor, "grading": {"center": [0.0, 0.11], "near": 0.02 * factor,
                                                    "far": 0.16 * factor, "distance": 1.0}},
        "study": {"type": "sweep", "parameter": "physics.em1.wavelength", "values": inputs["wavelengths_um"]},
    }


def extrapolate(f):
    """Richardson with the observed order for three values on grids halving each time."""
    f1, f2, f3 = f
    order = np.log(abs((f1 - f2) / (f2 - f3))) / np.log(2.0)
    return f3 + (f3 - f2) / (2.0**order - 1.0)


def group_index(neff, wavelengths):
    """n_g at the middle wavelength from the central difference, as in the record."""
    return neff[..., 1, :] - wavelengths[1] * (neff[..., 2, :] - neff[..., 0, :]) / (wavelengths[2] - wavelengths[0])


@pytest.mark.slow
def test_soi_strip_against_stored_modesolver_values():
    ref = load_reference(RECORD.parent / "soi_strip_modes.json")
    crosscheck = crosscheck_helpers()
    wavelengths = ref.arrays["wavelength_um"]
    finest = ref.arrays["neff"][1:]              # h = 0.01, 0.005, 0.0025 um; 0.02 is pre-asymptotic
    reference_neff = extrapolate(finest[:, 1, :])
    reference_ng = extrapolate(group_index(finest, wavelengths))

    stopwatch = crosscheck.Stopwatch()
    with stopwatch("openphysics"):
        results = {f: run(Document.from_dict(document(ref.inputs, f)), verbose=False) for f in (1.0, 0.5)}
    fine = results[0.5]
    assert list(fine.values) == list(wavelengths)
    neff = fine.neff[1]
    ng = fine.group_index()[1]

    observables = [
        crosscheck.observable("TE0 n_eff at 1.55 um", "1", "absolute difference", abs(neff[0] - reference_neff[0])),
        crosscheck.observable("TE0 n_g at 1.55 um", "1", "absolute difference", abs(ng[0] - reference_ng[0])),
        crosscheck.observable("TM0 n_eff at 1.55 um", "1", "absolute difference", abs(neff[1] - reference_neff[1])),
        crosscheck.observable("TE0 n_eff at 1.55 um, example mesh", "1", "absolute difference",
                              abs(results[1.0].neff[1, 0] - reference_neff[0])),
    ]
    record = crosscheck.make_record(
        case=ref.record["case"], physics=ref.record["physics"], api="simcase.run (em.modes2d vector)",
        discretization={"kind": "edge and nodal finite elements", "mesh": "soi_strip example, lengths halved"},
        tool="modesolver", tool_discretization=ref.record["references"][0]["discretization"],
        matched=ref.record["matched"], not_matched=ref.record["not_matched"], observables=observables,
        analytical_acceptance="tests/simcase/test_vector.py", stopwatch=stopwatch, stored=ref)
    crosscheck.emit(record)
