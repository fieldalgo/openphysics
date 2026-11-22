# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""TE fraction and loss of em.modes2d vector modes against independent references.

f_TE = sum_T A_T |E_x|^2 / sum_T A_T (|E_x|^2 + |E_y|^2) on the saved centroid field
``unnormalized_electric_field`` (simcase.mode_postprocessing). The references:

- V1/V2: a film spanning the whole window with PEC (TE) or PMC (TM) side walls is the exact
  slab, whose TE mode has f_TE = 1 and TM mode f_TE = 0;
- V3: the slab n_eff of refsol.slab;
- V4: wide cores tend to V1/V2;
- V5: the 400 x 400 nm square's symmetry: its two lowest modes are a degenerate pair, and any
  rotation within the pair keeps the sum of the two fractions at 1;
- V6: first-order perturbation of the lossless run's saved field and power, and the exact
  lossy slab of refsol.lossy_slab;
- V7: propagation_loss by hand.

Every mesh check runs core element sizes 40, 20 and 10 nm and prints each error with the
observed order (pytest -s shows them). The slab limits (V1-V3) scale every mesh length with the
core size; with the template's fixed 160 nm cladding mesh the TM n_eff error floors and changes
sign between 20 and 10 nm, which is not a convergence study.
"""
import json

import numpy as np
import pytest

import physmat
from refsol import lossy_slab, slab
from simcase import Document, run
from simcase.mode_postprocessing import te_polarization_fraction

WAVELENGTH = 1.55e-6
THICKNESS = 0.22                       # um
SIZES = (0.04, 0.02, 0.01)             # core element sizes, um
Z0 = 376.730313668                     # vacuum impedance, ohm (mu0 c with the 2019 SI mu0)
N_SI = float(physmat.material("Si").refractive_index(vacuum_wavelength=WAVELENGTH).real)
N_SIO2 = float(physmat.material("SiO2").refractive_index(vacuum_wavelength=WAVELENGTH).real)


def um(x):
    return f"{x!r} um"


def document(size, *, side="pec", shapes=None, window=(-1.5, 1.5, -1.2, 1.2), mode_count=2, materials=None,
             scaled=False, centre=THICKNESS / 2):
    """The optical template's window, mesh and boundaries with the given cores (lengths in um).

    ``scaled`` makes every mesh length follow the core size (element 6 h, far 4 h) for the slab
    convergence studies; otherwise the cladding keeps the template's 250 and 160 nm.
    """
    x0, x1, y0, y1 = window
    if shapes is None:                 # the film across the whole window
        shapes = [{"name": "core", "type": "rect", "x": x0, "y": 0.0, "w": x1 - x0, "h": THICKNESS,
                   "material": "physmat:Si"}]
    d = {"openphysics": "0.3", "name": "TE fraction check",
         "geometry": {"length_unit": "um", "depth": None, "domain": {"xmin": x0, "xmax": x1, "ymin": y0, "ymax": y1},
                      "background": {"material": "physmat:SiO2"},
                      "shapes": [dict(s, element_size=um(size)) for s in shapes]},
         "physics": {"em1": {"type": "em.modes2d", "formulation": "vector", "vacuum_wavelength": "1550 nm",
                             "mode_count": mode_count, "effective_index_threshold": 1.45,
                             "boundary": {"left": side, "right": side, "top": "pec", "bottom": "pec"}}},
         "mesh": {"element_size": um(6 * size) if scaled else "0.25 um",
                  "grading": {"position": ["0 um", um(centre)], "near": um(size), "far": um(4 * size) if scaled else "0.16 um",
                              "refinement_distance": "1 um"}},
         "study": {"type": "single"}, "results": {"plots": False}}
    if materials:
        d["materials"] = materials
    return Document.from_dict(d)


def strip(size, k=None, w=0.5, h=THICKNESS, mode_count=1):
    """A w x h core on the window's axis, y from 0 to h, the grading centred on it."""
    material, materials = "physmat:Si", None
    if k is not None:
        material, materials = "lossy_si", {"lossy_si": {"refractive_index": {"n": N_SI, "k": k}}}
    return document(size, shapes=[{"name": "core", "type": "rect", "x": -w / 2, "y": 0.0, "w": w, "h": h,
                                   "material": material}], mode_count=mode_count, materials=materials, centre=h / 2)


def fraction(result):
    return result.postprocessing["te_polarization_fraction"][0]


def orders(errors):
    e = np.abs(np.asarray(errors, dtype=float))
    return np.log2(e[:-1] / e[1:])


def report(name, errors):
    print(f"\n{name}: errors {['%.3e' % e for e in errors]}, observed orders {np.round(orders(errors), 2).tolist()}")


def strictly_decreasing(errors):
    e = np.abs(np.asarray(errors, dtype=float))
    return bool(np.all(e[1:] < e[:-1]))


@pytest.fixture(scope="module")
def slab_te():
    return [run(document(h, side="pec", mode_count=1, scaled=True), verbose=False) for h in SIZES]


@pytest.fixture(scope="module")
def slab_tm():
    """The PMC film: the guided spectrum holds TE-like box modes too; TM0 is the mode nearest the slab TM index."""
    reference = slab.modes(refractive_index=(N_SIO2, N_SI, N_SIO2), thickness=THICKNESS * 1e-6,
                           vacuum_wavelength=WAVELENGTH, pol="TM")[0]
    out = []
    for h in SIZES:
        result = run(document(h, side="pmc", mode_count=40, scaled=True), verbose=False)
        out.append((result, int(np.argmin(np.abs(result.effective_index[0] - reference)))))
    return out


# -- V1, V2, V3: the exact slab limit ------------------------------------------------------------------

@pytest.mark.slow
def test_v1_slab_te_limit_fraction_converges(slab_te):
    errors = [1.0 - fraction(r)[0] for r in slab_te]
    report("V1 1 - f_TE (PEC film)", errors)
    assert errors[0] <= 1e-3
    assert strictly_decreasing(errors)
    assert all(e >= 0 for e in errors)


@pytest.mark.slow
def test_v2_slab_tm_limit_fraction_converges(slab_tm):
    errors = [fraction(r)[i] for r, i in slab_tm]
    report("V2 f_TE (PMC film, TM0)", errors)
    assert errors[0] <= 2e-3
    assert strictly_decreasing(errors)


@pytest.mark.slow
def test_v3_slab_limit_effective_index_converges(slab_te, slab_tm):
    for pol, got in (("TE", [r.effective_index[0, 0] for r in slab_te]),
                     ("TM", [r.effective_index[0, i] for r, i in slab_tm])):
        reference = slab.modes(refractive_index=(N_SIO2, N_SI, N_SIO2), thickness=THICKNESS * 1e-6,
                               vacuum_wavelength=WAVELENGTH, pol=pol)[0]
        errors = [float(np.real(n)) - reference for n in got]
        report(f"V3 n_eff - slab {pol} ({reference:.6f})", errors)
        assert strictly_decreasing(errors), pol
        assert abs(errors[-1]) <= 3e-3, pol


# -- V4: wide cores tend to the slab -------------------------------------------------------------------

@pytest.mark.slow
def test_v4_wide_core_tends_to_the_slab_limit():
    te, tm = [], []
    for w in (1.0, 2.0, 4.0):
        half = w / 2 + 1.5
        result = run(document(0.03, window=(-half, half, -1.2, 1.2), mode_count=40,
                              shapes=[{"name": "core", "type": "rect", "x": -w / 2, "y": 0.0, "w": w, "h": THICKNESS,
                                       "material": "physmat:Si"}]), verbose=False)
        f, n = fraction(result), result.effective_index[0].real
        # quasi-TE0: the highest index (TE-like); quasi-TM0: the highest TM-like (f_TE < 1/2) index
        te.append(f[0])
        tm.append(f[np.flatnonzero(f < 0.5)[np.argmax(n[f < 0.5])]])
    print(f"\nV4 quasi-TE0 f_TE {np.round(te, 5).tolist()}, quasi-TM0 f_TE {np.round(tm, 5).tolist()}")
    assert te[0] < te[1] < te[2]
    assert te[2] >= 0.999
    assert tm[2] <= 0.01


# -- V5: the degenerate pair of a square core --------------------------------------------------------------

@pytest.mark.slow
def test_v5_square_core_is_a_degenerate_pair():
    sums, gaps = [], []
    for h in SIZES:
        result = run(strip(h, w=0.4, h=0.4, mode_count=2), verbose=False)
        n, f = result.effective_index[0].real, fraction(result)
        gaps.append(abs(n[0] - n[1]))
        sums.append(f[0] + f[1])
    print(f"\nV5 |dRe n_eff| {['%.2e' % g for g in gaps]}, f_TE sums {np.round(sums, 6).tolist()}")
    assert max(gaps) <= 1e-4
    assert np.all(np.abs(np.asarray(sums) - 1.0) <= 1e-3)


# -- V6, V7: loss ---------------------------------------------------------------------------------------

def triangle_areas(nodes, triangles):
    p0, p1, p2 = (nodes[triangles[:, i]] for i in range(3))
    return 0.5 * np.abs((p1[:, 0] - p0[:, 0]) * (p2[:, 1] - p0[:, 1]) - (p1[:, 1] - p0[:, 1]) * (p2[:, 0] - p0[:, 0]))


def perturbation(lossless, k):
    """Im n_eff = int_core n k |E|^2 dA / (2 Z0 Re P) with the lossless run's saved centroid field
    (V/m), its triangle areas (m^2) and its unnormalized_mode_power (W)."""
    area = triangle_areas(lossless.node_coordinates, lossless.triangles)
    core = np.asarray(lossless.region_names)[lossless.regions] == "core"
    e = lossless.vector_fields[0].electric[:, 0, :]
    power = lossless.postprocessing["unnormalized_mode_power"][0, 0].real
    return float(np.sum(N_SI * k * area[core] * np.sum(np.abs(e[core]) ** 2, axis=1)) / (2 * Z0 * power))


@pytest.mark.slow
@pytest.mark.parametrize("k", [1e-4, 1e-3])
def test_v6_strip_loss_matches_first_order_perturbation(k):
    ratios = []
    for h in SIZES:
        lossless, lossy = run(strip(h), verbose=False), run(strip(h, k), verbose=False)
        ratios.append(lossy.effective_index[0, 0].imag / perturbation(lossless, k))
    print(f"\nV6 strip k={k}: Im n_eff / perturbation {np.round(ratios, 6).tolist()}")
    assert np.all(np.abs(np.asarray(ratios) - 1.0) <= 1e-2)


@pytest.mark.slow
def test_v6_film_loss_matches_the_exact_lossy_slab():
    k = 1e-3
    exact = lossy_slab.three_layer_modes(refractive_index=(N_SIO2, N_SI + 1j * k, N_SIO2), thickness=THICKNESS * 1e-6,
                                         vacuum_wavelength=WAVELENGTH, pol="TE", mode_count=1)[0]
    materials = {"lossy_si": {"refractive_index": {"n": N_SI, "k": k}}}
    shapes = [{"name": "core", "type": "rect", "x": -1.5, "y": 0.0, "w": 3.0, "h": THICKNESS, "material": "lossy_si"}]
    errors = [run(document(h, shapes=shapes, mode_count=1, materials=materials), verbose=False).effective_index[0, 0].imag
              / exact.imag - 1.0 for h in SIZES]
    report(f"V6 film Im n_eff / exact lossy slab ({exact.imag:.6e}) - 1", errors)
    assert np.all(np.abs(errors) <= 1e-2)


@pytest.mark.slow
def test_v7_loss_in_db_per_metre_is_the_formula():
    result = run(strip(0.02, 1e-4), verbose=False)
    im = result.effective_index[0, 0].imag
    by_hand = 40 * np.pi / np.log(10) * im / WAVELENGTH
    assert im > 0
    assert abs(result.propagation_loss()[0, 0] - by_hand) <= 1e-12 * by_hand
    summary = result.summary()
    assert summary["propagation_loss"]["unit"] == "dB/m"
    assert abs(summary["propagation_loss"]["values"][0][0] - by_hand) <= 1e-12 * by_hand
    print(f"\nV7 k=1e-4 strip at 20 nm: {by_hand / 100:.4g} dB/cm")
    assert f"{by_hand / 100:.4g}" == "37.49"


# -- the saved format ----------------------------------------------------------------------------------

def test_te_fraction_is_saved_and_recomputed_from_fields_npz(tmp_path):
    out = strip(0.04, mode_count=2)
    result = run(out, verbose=False)
    result.save(tmp_path)
    with np.load(tmp_path / "fields.npz") as archive:
        saved = {k: archive[k] for k in archive.files}
    assert saved["te_polarization_fraction"].shape == (1, 2)
    recomputed = te_polarization_fraction(saved["node_coordinates"], saved["triangles"],
                                          saved["unnormalized_electric_field"][0])
    assert recomputed.tobytes() == saved["te_polarization_fraction"][0].tobytes()
    assert str(saved["field_layout"]) == "em-modes2d-p1-node-centroid-v2"
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    block = summary["mode_postprocessing"]["te_polarization_fraction"]
    assert block["unit"] == "1" == summary["field_units"]["te_polarization_fraction"]
    assert block["values"] == saved["te_polarization_fraction"].tolist()
    assert "degenerate pair" in block["description"]
    assert summary["field_layout"] == "em-modes2d-p1-node-centroid-v2"
    # the strip's TE0 is TE-like, its TM0 TM-like
    f = saved["te_polarization_fraction"][0]
    assert f[0] > 0.9 and f[1] < 0.1


def test_te_fraction_formula_on_a_hand_case():
    nodes = np.array([[0.0, 0.0], [2.0, 0.0], [0.0, 1.0], [2.0, 1.0]])
    triangles = np.array([[0, 1, 2], [1, 3, 2]])               # areas 1 and 1
    electric = np.zeros((2, 3, 3), dtype=complex)
    electric[:, 0] = [[1, 0, 5], [1j, 0, 0]]                     # pure x, E_z ignored -> 1
    electric[:, 1] = [[0, 1, 0], [0, 1 - 1j, 0]]                 # pure y -> 0
    electric[:, 2] = [[1, 1, 0], [0, 0, 0]]                      # x = y -> 1/2
    got = te_polarization_fraction(nodes, triangles, electric)
    assert got.tolist() == [1.0, 0.0, 0.5]
    nodes[1, 0] = 6.0                                            # areas 3 and 1: 3 / (3 + 1)
    electric[:, 0] = [[1, 0, 0], [0, 1, 0]]
    assert abs(te_polarization_fraction(nodes, triangles, electric)[0] - 3 / 4) < 1e-15
    assert np.isnan(te_polarization_fraction(nodes, triangles, np.zeros((2, 1, 3)))[0])


def test_scalar_results_have_no_te_fraction(tmp_path):
    d = strip(0.04).data
    d["physics"]["em1"]["formulation"] = "scalar"
    del d["physics"]["em1"]["effective_index_threshold"]
    result = run(Document.from_dict(d), verbose=False)
    assert "te_polarization_fraction" not in result.postprocessing
    assert "te_polarization_fraction" not in result.summary()["mode_postprocessing"]


def test_te_fraction_is_a_result_quantity():
    from physmat import units
    q = units.quantity("te_polarization_fraction")
    assert q.unit == "1" and q.kind == "fraction"
