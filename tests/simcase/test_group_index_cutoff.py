# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The group index of a wavelength sweep whose scalar mode is cut off.

Pre-registered before the fix. A cut-off scalar mode (beta^2 <= 0) is returned as the fill
n_eff = 0 (the lossless square root is clipped at 0), and the sweep's difference turned that
fill into n_g = 0, a value no mode has. The fix is a value correction only: n_g is null (NaN)
at every point whose difference uses a cut-off value, the log says why, and every other value
is unchanged bit for bit. No result key is added; effective_index keeps the value it had.

C1: the 220 nm physmat:Si film of test_group_index_single with its pec side walls (the 0.1 um
window cuts the scalar field off): every n_g null in summary.json (NaN in the result),
effective_index still 0, one log line per point. (fields.npz holds n_g of a tracked sweep only;
this scalar sweep is untracked.)
C2: the difference on synthetic arrays, first and second order: NaN exactly at the stencil
points of the cut-off value, every other value equal to the unchanged formula.
C3: a guided scalar sweep: no null, and n_g equals the formula on its public n_eff and
wavelengths to 1e-13 relative (the run differences micrometre wavelengths, the formula here the
public metres times 1e6, so the last bits may differ; C2 checks the unchanged values bit for bit).
"""

import copy
import json

import numpy as np
import pytest

from simcase import Document, examples, run
from simcase.runner import _kernel_group_index


def um(x):
    return f"{x!r} um"


def film(h=0.02, side="pec"):
    d = copy.deepcopy(examples.VECTOR_SLAB)
    d["geometry"]["background"]["material"] = "physmat:SiO2"
    d["geometry"]["shapes"][0]["material"] = "physmat:Si"
    d.pop("materials")
    d["geometry"]["shapes"][0]["element_size"] = um(h)
    d["mesh"]["element_size"] = um(5 * h)
    d["mesh"]["grading"].update(near=um(h), far=um(5 * h))
    d["physics"]["em1"].update(formulation="scalar", mode_count=1)
    del d["physics"]["em1"]["effective_index_threshold"]
    d["physics"]["em1"]["boundary"].update(left=side, right=side)
    d["study"] = {"type": "sweep", "parameter": "physics.em1.vacuum_wavelength",
                  "values": {"unit": "um", "values": [1.54, 1.55, 1.56]}}
    d["results"] = {}
    return d


def formula(neff, wl, order):
    return neff - wl[:, None] * np.gradient(neff, wl, axis=0, edge_order=order)


def test_c1_cut_off_film_has_no_group_index(tmp_path):
    res = run(Document.from_dict(film()), verbose=False)
    assert np.all(res.effective_index == 0.0)          # the fill value, as before
    assert np.all(np.isnan(res.group_index()))
    res.save(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["group_index"]["values"] == [[None], [None], [None]]
    assert summary["effective_index"]["values"] == [[0.0], [0.0], [0.0]]
    lines = [line for line in res.log if line.startswith("n_g undefined at ")]
    assert lines == [f"n_g undefined at vacuum_wavelength {w} um, mode 1: n_eff^2 <= 0 (cut off) "
                     "at a wavelength of its difference" for w in ("1.54", "1.55", "1.56")]


@pytest.mark.parametrize("tracked", [False, True])
def test_c2_nan_exactly_on_the_stencil_of_a_cut_off_value(tracked):
    wl = np.array([1.50, 1.52, 1.55, 1.57, 1.60, 1.62])
    good = np.stack([2.9 - 0.4 * wl, 2.1 - 0.3 * wl ** 2], axis=1)
    neff = good.copy()
    neff[3, 0] = 0.0                                   # mode 1 cut off at the fourth point
    ng = _kernel_group_index("physics.em1.wavelength", wl, neff, vector=False, tracked=tracked)
    order = 2 if tracked else 1
    # interior central differences read i - 1 and i + 1, so points 2, 3 and 4 use point 3; the
    # second-order end formula at the last point reads points 3, 4 and 5
    bad = {2, 3, 4, 5} if tracked else {2, 3, 4}
    for i in range(len(wl)):
        assert np.isnan(ng[i, 0]) == (i in bad), i
    keep = [i for i in range(len(wl)) if i not in bad]
    assert np.array_equal(ng[keep, 0], formula(neff, wl, order)[keep, 0])
    # the other mode is untouched, bit for bit
    assert np.array_equal(ng[:, 1], formula(good, wl, order)[:, 1])


def test_c2_end_point_and_complex_index():
    wl = np.array([1.54, 1.55, 1.56])
    neff = np.array([[0.0], [2.0], [1.99]])
    # second order at the ends uses three points: every point reads the cut-off first point
    assert np.all(np.isnan(_kernel_group_index("x.wavelength", wl, neff, False, True)))
    # first order: the first two points use it, the last does not
    ng = _kernel_group_index("x.wavelength", wl, neff, False, False)
    assert np.isnan(ng[0, 0]) and np.isnan(ng[1, 0]) and np.isfinite(ng[2, 0])
    # complex n_eff (a lossy run, tracked) is never a fill value
    cneff = neff.astype(complex) + 1e-6j
    assert np.all(np.isfinite(_kernel_group_index("x.wavelength", wl, cneff, False, True)))


def test_c3_guided_sweep_is_unchanged():
    res = run(Document.from_dict(film(side="pmc")), verbose=False)
    neff = res.effective_index
    assert np.all(neff > 1.44)
    wl = res.vacuum_wavelength * 1e6
    tracked = res.mode_tracking is not None
    ng = res.group_index()
    assert np.all(np.isfinite(ng))
    np.testing.assert_allclose(ng, formula(neff, wl, 2 if tracked else 1), rtol=1e-13, atol=0)
    assert not any(line.startswith("n_g undefined") for line in res.log)
