# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Effective area of em.modes2d modes against independent references.

A_eff = (sum_T A_T |E_T|^2)^2 / sum_T A_T |E_T|^4 on the saved centroid field
``unnormalized_electric_field``, |E|^2 = |E_x|^2 + |E_y|^2 + |E_z|^2, over every triangle of the
window (simcase.mode_postprocessing). Pre-registered checks, written before any result was seen:

- V11: an x-polarised Gaussian exp(-r^2 / w0^2) sampled at the triangle centroids of a disk mesh
  of radius R = 4 w0 (built here: ring k holds 6k nodes, ring spacing w0/8, w0/16, w0/32).
  Exact: pi w0^2 (1 - e^{-2a})^2 / (1 - e^{-4a}), a = R^2 / w0^2 = 16, i.e. pi w0^2 to 1e-13
  relative; the polygon's departure from the circle lies where |E|^2 <= e^{-32}. Pass: relative
  error <= 2e-3 at w0/32 and observed order >= 1.8 on both steps.
- V12: the 500 x 220 nm SOI strip (two modes) at core element sizes 40, 20 and 10 nm with every
  mesh length scaled with h, against ``galerkin.kernels.effective_area(include_longitudinal=True)``
  of the same mode rebuilt from the saved arrays by the documented recipe. Pass: relative
  difference <= 1e-3 at 20 nm and strictly decreasing over 40, 20, 10 nm, both modes. The
  transverse-only comparison (the centroid rule on E_t against the kernel's default) is printed
  for the record and not gated: its 20 nm value, 4.6e-4, was measured before this check was
  registered.
- Format: the key is in fields.npz and the summary, a recompute from fields.npz alone equals the
  saved value bit for bit, ``field_layout`` is unchanged, and PML and bend results get no key.
"""
import json
from pathlib import Path

import numpy as np
import pytest

from galerkin import EdgeSpace, Mesh
from galerkin.kernels import effective_area as kernel_effective_area
from simcase import Document, run
from simcase.mode_postprocessing import effective_area

from test_mode_polarization import SIZES, THICKNESS, document, orders, report, strictly_decreasing

ROOT = Path(__file__).resolve().parents[2]
W0, RADIUS = 1.0, 4.0
SPACINGS = (W0 / 8, W0 / 16, W0 / 32)


# -- V11: a known field ---------------------------------------------------------------------------

def disk_mesh(spacing, radius=RADIUS):
    """Quasi-uniform disk: a centre node and rings k = 1..K at radius k * spacing with 6k nodes each,
    neighbouring rings joined by a zipper over the node angles (counter-clockwise triangles)."""
    rings = round(radius / spacing)
    nodes, ring_ids = [[0.0, 0.0]], [[0]]
    for k in range(1, rings + 1):
        n = 6 * k
        angle = 2 * np.pi * np.arange(n) / n
        ring_ids.append(list(range(len(nodes), len(nodes) + n)))
        nodes.extend(np.column_stack([k * spacing * np.cos(angle), k * spacing * np.sin(angle)]).tolist())
    triangles = []
    for inner, outer in zip(ring_ids[:-1], ring_ids[1:]):
        ni, no = len(inner), len(outer)
        if ni == 1:
            triangles += [[inner[0], outer[j], outer[(j + 1) % no]] for j in range(no)]
            continue
        i = j = 0
        while i < ni or j < no:
            # advance on the ring whose next node comes first in angle
            if j < no and (i == ni or (j + 1) / no <= (i + 1) / ni):
                triangles.append([inner[i % ni], outer[j], outer[(j + 1) % no]])
                j += 1
            else:
                triangles.append([inner[i % ni], outer[j % no], inner[(i + 1) % ni]])
                i += 1
    return np.asarray(nodes), np.asarray(triangles)


def gaussian_area():
    a = RADIUS ** 2 / W0 ** 2
    return np.pi * W0 ** 2 * (-np.expm1(-2 * a)) ** 2 / -np.expm1(-4 * a)


def test_v11_gaussian_effective_area_converges_to_pi_w0_squared():
    exact = gaussian_area()
    assert abs(exact / (np.pi * W0 ** 2) - 1) < 1e-13
    errors = []
    for spacing in SPACINGS:
        nodes, triangles = disk_mesh(spacing)
        p0, p1, p2 = (nodes[triangles[:, k]] for k in range(3))
        signed = (p1[:, 0] - p0[:, 0]) * (p2[:, 1] - p0[:, 1]) - (p1[:, 1] - p0[:, 1]) * (p2[:, 0] - p0[:, 0])
        assert np.all(signed > 0)                           # a valid, consistently oriented mesh
        assert abs(0.5 * signed.sum() / (np.pi * RADIUS ** 2) - 1) < 2e-2
        centroid = (p0 + p1 + p2) / 3
        field = np.zeros((len(triangles), 1, 3), dtype=complex)
        field[:, 0, 0] = np.exp(-np.sum(centroid ** 2, axis=1) / W0 ** 2)
        got = effective_area(nodes, triangles, field)[0]
        errors.append((got - exact) / exact)
        print(f"V11 spacing w0/{round(W0 / spacing)}: {len(triangles)} triangles, A_eff {got:.9f}, "
              f"exact {exact:.9f}, relative error {errors[-1]:.3e}")
    report("V11 Gaussian A_eff relative error", errors)
    assert abs(errors[-1]) <= 2e-3, errors
    assert np.all(orders(errors) >= 1.8), orders(errors)


# -- V12: the validated kernel on the same mode ---------------------------------------------------

def scaled_strip(size):
    return document(size, shapes=[{"name": "core", "type": "rect", "x": -0.25, "y": 0.0, "w": 0.5, "h": THICKNESS,
                                   "material": "physmat:Si"}], mode_count=2, scaled=True, centre=THICKNESS / 2)


def kernel_areas(result, p=0):
    """The kernel's A_eff of each saved mode, from the saved arrays alone (the recipe of
    simcase.mode_postprocessing), in m^2: (with E_z, E_t only)."""
    space = EdgeSpace(Mesh(result.node_coordinates / 1e-6, result.triangles, {}))
    vf = result.vector_fields[p]
    assert np.array_equal(space.edges, vf.edges)
    out = []
    for m in range(vf.transverse.shape[1]):
        et = np.conj(vf.transverse[:, m]) / 1e-6
        ez = -1j * np.conj(vf.longitudinal[:, m])
        out.append((kernel_effective_area(space, et, ez, include_longitudinal=True) * 1e-12,
                    kernel_effective_area(space, et, None) * 1e-12))
    return np.asarray(out)


@pytest.fixture(scope="module")
def strips():
    return [run(scaled_strip(h), verbose=False) for h in SIZES]


@pytest.mark.slow
def test_v12_centroid_area_converges_to_the_kernel(strips):
    full, transverse = [], []
    for h, result in zip(SIZES, strips):
        saved = result.postprocessing["effective_area"][0]
        kernel = kernel_areas(result)
        electric = result.vector_fields[0].electric.copy()
        electric[:, :, 2] = 0.0                         # the same centroid rule on E_t alone
        full.append(saved / kernel[:, 0] - 1)
        transverse.append(effective_area(result.node_coordinates, result.triangles, electric) / kernel[:, 1] - 1)
        print(f"V12 h={h * 1e3:.0f} nm: {len(result.triangles)} triangles, A_eff {saved * 1e12} um^2, kernel (E_t+E_z) "
              f"{kernel[:, 0] * 1e12}, kernel (E_t) {kernel[:, 1] * 1e12}")
    full, transverse = np.asarray(full), np.asarray(transverse)
    for m in range(full.shape[1]):
        report(f"V12 mode {m + 1} centroid vs kernel (E_t + E_z) relative difference", full[:, m])
        report(f"V12 mode {m + 1} centroid vs kernel, both E_t only (not gated) relative difference", transverse[:, m])
        assert abs(full[1, m]) <= 1e-3, full[:, m]
        assert strictly_decreasing(full[:, m]), full[:, m]


# -- format -----------------------------------------------------------------------------------------

def test_format_saved_key_recomputes_from_fields_npz_alone(tmp_path):
    result = run(scaled_strip(0.04), verbose=False)
    out = result.save(tmp_path)
    with np.load(out / "fields.npz", allow_pickle=False) as archive:
        saved = {key: archive[key] for key in archive.files}
    assert str(saved["field_layout"]) == "em-modes2d-p1-node-centroid-v2"
    area = saved["effective_area"]
    assert area.shape == saved["effective_index"].shape and area.dtype == float
    for p in range(area.shape[0]):
        again = effective_area(saved["node_coordinates"], saved["triangles"], saved["unnormalized_electric_field"][p])
        assert again.tobytes() == area[p].tobytes()
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    block = summary["mode_postprocessing"]["effective_area"]
    assert block["unit"] == "m^2" == summary["field_units"]["effective_area"]
    assert block["values"] == area.tolist()
    assert "Afshar and Monro" in block["description"]
    assert summary["field_layout"] == "em-modes2d-p1-node-centroid-v2"
    # a strip mode of 500 x 220 nm silicon is a few tenths of a square micrometre
    assert np.all((area > 0.05e-12) & (area < 1e-12)), area


@pytest.mark.parametrize("example", ["pml_leaky_slab.json", "pml_bent_slab.json"])
def test_format_pml_and_bend_results_get_no_effective_area(example, tmp_path):
    d = json.loads((ROOT / "examples/simcase" / example).read_text(encoding="utf-8"))
    d["results"] = {"plots": False}
    d["mesh"]["element_size"] = "0.1 um"
    result = run(Document.from_dict(d), verbose=False)
    assert result.open_boundary is not None and result.postprocessing is None
    result.save(tmp_path)
    with np.load(tmp_path / "fields.npz", allow_pickle=False) as archive:
        assert "effective_area" not in archive.files
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert "mode_postprocessing" not in summary and "effective_area" not in summary.get("field_units", {})
