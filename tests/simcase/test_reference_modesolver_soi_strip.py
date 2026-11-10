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
    """The strip from the record's inputs (lengths in um, so the stored record is untouched)."""
    window, core = inputs["window_um"], inputs["core_um"]

    def um(x):
        return f"{x!r} um"
    materials = {name: f"physmat:{inputs[name]}" for name in ("background_material", "core_material")}
    return {
        "openphysics": "0.3",
        "name": "SOI strip, modesolver comparison",
        "geometry": {"length_unit": "um", "depth": None, "domain": dict(window),
                     "background": {"material": materials["background_material"]},
                     "shapes": [{"name": "core", "type": "rect", **core, "material": materials["core_material"],
                                 "element_size": um(0.02 * factor)}]},
        "physics": {"em1": {"type": "em.modes2d", "formulation": "vector", "vacuum_wavelength": "1.55 um",
                            "mode_count": len(inputs["modes"]), "effective_index_threshold": 1.45,
                            "boundary": {side: "pec" for side in ("left", "right", "top", "bottom")}}},
        "mesh": {"element_size": um(0.25 * factor),
                 "grading": {"position": ["0 um", "0.11 um"], "near": um(0.02 * factor), "far": um(0.16 * factor),
                             "refinement_distance": "1 um"}},
        "study": {"type": "sweep", "parameter": "physics.em1.vacuum_wavelength",
                  "values": {"unit": "um", "values": list(inputs["wavelengths_um"])}},
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
    assert list(fine.vacuum_wavelength) == [w * 1e-6 for w in wavelengths]    # the kernel's um times 1e-6
    neff = fine.effective_index[1]
    ng = fine.group_index()[1]

    observables = [
        crosscheck.observable("TE0 n_eff at 1.55 um", "1", "absolute difference", abs(neff[0] - reference_neff[0])),
        crosscheck.observable("TE0 n_g at 1.55 um", "1", "absolute difference", abs(ng[0] - reference_ng[0])),
        crosscheck.observable("TM0 n_eff at 1.55 um", "1", "absolute difference", abs(neff[1] - reference_neff[1])),
        crosscheck.observable("TE0 n_eff at 1.55 um, example mesh", "1", "absolute difference",
                              abs(results[1.0].effective_index[1, 0] - reference_neff[0])),
    ]
    record = crosscheck.make_record(
        case=ref.record["case"], physics=ref.record["physics"], api="simcase.run (em.modes2d vector)",
        discretization={"kind": "edge and nodal finite elements", "mesh": "soi_strip example, lengths halved"},
        tool="modesolver", tool_discretization=ref.record["references"][0]["discretization"],
        matched=ref.record["matched"], not_matched=ref.record["not_matched"], observables=observables,
        analytical_acceptance="tests/simcase/test_vector.py", stopwatch=stopwatch, stored=ref)
    crosscheck.emit(record)
