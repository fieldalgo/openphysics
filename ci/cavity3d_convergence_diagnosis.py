# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Diagnose the fixed rectangular 111 doublet gate without changing its verdict.

Run from the repository root with an approved cavity implementation present.
Outputs JSON only. Supplemental meshes and quadrature checks are diagnostics,
not replacements for the fixed n=4,8,16 acceptance test.
"""
from __future__ import annotations

import argparse
from itertools import combinations, product
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np
import scipy
import scipy.linalg as la

ROOT = Path(__file__).resolve().parents[1]
for package in (ROOT / "packages").iterdir():
    if (package / "pyproject.toml").exists():
        sys.path.insert(0, str(package))

from galerkin import solve_cavity_box  # noqa: E402
from refsol.metallic import rect_cavity_resonances  # noqa: E402

C0 = 299792458.0
SIDES = np.array((1., .8, .6))
EDGES = tuple(combinations(range(4), 2))


def independent_vertices(result):
    """Evaluate Whitney fields at vertices using raw oriented edge integrals."""
    mesh, coefficients = result.mesh, result.edge_coefficients[:, -2:]
    lookup = {tuple(edge): i for i, edge in enumerate(result.space.edges)}
    tet = mesh.tets
    points = mesh.nodes[tet]
    gradient = np.empty((len(tet), 4, 3))
    gradient[:, 1:] = np.linalg.inv(points[:, 1:] - points[:, :1]).transpose(0, 2, 1)
    gradient[:, 0] = -gradient[:, 1:].sum(axis=1)
    field = np.zeros((len(tet), 4, 3, 2))
    for i, j in EDGES:
        ids = np.array([lookup[tuple(sorted((int(a), int(b))))]
                        for a, b in tet[:, (i, j)]])
        signs = np.where(tet[:, i] < tet[:, j], 1, -1)
        local = coefficients[ids] * signs[:, None]
        field[:, i] += gradient[:, j, :, None] * local[:, None, :]
        field[:, j] -= gradient[:, i, :, None] * local[:, None, :]
    return field


def tetra_rule(order):
    """Tensor Gauss rule under a Duffy map; weights integrate a unit tetrahedron."""
    x, weights = np.polynomial.legendre.leggauss(order)
    x, weights = (x + 1) / 2, weights / 2
    bary, out = [], []
    for i, j, k in product(range(order), repeat=3):
        r, s, t = x[[i, j, k]]
        bary.append(((1-r)*(1-s)*(1-t), r, (1-r)*s, (1-r)*(1-s)*t))
        out.append(weights[i]*weights[j]*weights[k]*(1-r)**2*(1-s))
    np.testing.assert_allclose(sum(out), 1/6, rtol=1e-14, atol=0)
    return np.asarray(bary), np.asarray(out)


def overlaps(result, vertex_field, order):
    """Continuum L2 overlap with both exact transverse 111 polarizations."""
    wavevector = np.pi / SIDES
    amplitudes = la.null_space(wavevector[None, :]) * np.sqrt(8 / SIDES.prod())
    bary, weight = tetra_rule(order)
    overlap, exact_gram, fe_gram = np.zeros((2, 2)), np.zeros((2, 2)), np.zeros((2, 2))
    mesh = result.mesh
    for start in range(0, len(mesh.tets), 512):
        end = start + 512
        points = mesh.nodes[mesh.tets[start:end]]
        determinant = abs(np.linalg.det(points[:, 1:] - points[:, :1]))
        coordinates = np.einsum("qi,tid->tqd", bary, points)
        phase = coordinates * wavevector
        sine, cosine = np.sin(phase), np.cos(phase)
        shapes = np.stack((cosine[..., 0]*sine[..., 1]*sine[..., 2],
                           sine[..., 0]*cosine[..., 1]*sine[..., 2],
                           sine[..., 0]*sine[..., 1]*cosine[..., 2]), axis=-1)
        exact = shapes[..., None] * amplitudes
        discrete = np.einsum("qi,tidk->tqdk", bary, vertex_field[start:end])
        physical_weight = determinant[:, None] * weight
        overlap += np.einsum("tq,tqdl,tqdk->lk", physical_weight, exact, discrete)
        exact_gram += np.einsum("tq,tqdl,tqdk->lk", physical_weight, exact, exact)
        fe_gram += np.einsum("tq,tqdl,tqdk->lk", physical_weight, discrete, discrete)
    singular_values = np.linalg.svd(overlap, compute_uv=False)
    projection_mass = np.sum(overlap**2, axis=0)
    relative_eigenvalues = result.eigenvalues_m2[-2:] / np.sum(wavevector**2)
    return {
        "order": order, "overlap": overlap.tolist(),
        "exact_gram_error": float(np.max(abs(exact_gram - np.eye(2)))),
        "fe_gram_error": float(np.max(abs(fe_gram - np.eye(2)))),
        "singular_values": singular_values.tolist(),
        "max_principal_sine": float(np.sqrt(max(0., 1 - singular_values.min()**2))),
        "rms_projection_l2_gap": float(np.sqrt(max(0., (2 - np.sum(overlap**2))/2))),
        "per_mode_projection_l2_gap": np.sqrt(np.maximum(0., 1-projection_mass)).tolist(),
        # Integration by parts gives <curl FE,curl exact> = lambda_exact <FE,exact>.
        # This is distance to the L2-projected exact subspace, not to a labeled TE vector.
        "per_mode_projected_curl_relative_error": np.sqrt(np.maximum(
            0., relative_eigenvalues - projection_mass)).tolist(),
    }


def observed_orders(rows, key):
    out = []
    for a, b in zip(rows[:-1], rows[1:]):
        va, vb = np.asarray(a[key]), np.asarray(b[key])
        out.append((np.log(abs(va)/abs(vb)) / np.log(b["n"]/a["n"])).tolist())
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--meshes", type=int, nargs="+", default=[4, 8, 16])
    parser.add_argument("--quadrature-orders", type=int, nargs="+", default=[4, 5])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if any(n < 2 for n in args.meshes) or any(q < 2 for q in args.quadrature_orders):
        parser.error("meshes and quadrature orders must be >=2")
    exact = float(np.sum((np.pi/SIDES)**2))
    fundamental = rect_cavity_resonances(*SIDES, n_max=4)[0][0]
    rows = []
    for n in sorted(set(args.meshes)):
        started = time.monotonic()
        result = solve_cavity_box(SIDES, (n, n, n), num_modes=5,
                                 target_frequency_hz=C0*np.sqrt(1.3*fundamental)/(2*np.pi))
        vertices = independent_vertices(result)
        signed = result.eigenvalues_m2[-2:] / exact - 1
        integrals = [overlaps(result, vertices, q) for q in args.quadrature_orders]
        row = {"n": n, "eigenvalues_m2": result.eigenvalues_m2.tolist(),
               "signed_relative_errors": signed.tolist(),
               "signed_mean_error": float(signed.mean()),
               "rms_eigenvalue_error": float(np.sqrt(np.mean(signed**2))),
               "max_eigenvalue_error": float(max(abs(signed))),
               "relative_split": float(np.ptp(signed)),
               "cancellation_ratio": float(abs(signed.mean()) / np.mean(abs(signed))),
               "relative_residuals": result.relative_residuals.tolist(),
               "quadrature": integrals,
               "subspace_gap": integrals[-1]["max_principal_sine"],
               "seconds": time.monotonic()-started}
        rows.append(row)
        print(json.dumps(row), flush=True)
    fixed = [row for row in rows if row["n"] in (4, 8, 16)]
    summary = {"signed_mean_orders": observed_orders(rows, "signed_mean_error"),
               "individual_eigenvalue_orders": observed_orders(rows, "signed_relative_errors"),
               "rms_eigenvalue_orders": observed_orders(rows, "rms_eigenvalue_error"),
               "subspace_gap_orders": observed_orders(rows, "subspace_gap")}
    if len(fixed) == 3:
        summary["fixed_mesh_mean_orders"] = observed_orders(fixed, "signed_mean_error")
        summary["fixed_gate_pass"] = bool(summary["fixed_mesh_mean_orders"][-1] > 1.8)
    report = {"environment": {"python": platform.python_version(), "numpy": np.__version__,
                               "scipy": scipy.__version__},
              "exact_111_eigenvalue_m2": exact, "sides_m": SIDES.tolist(),
              "rows": rows, "summary": summary}
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
