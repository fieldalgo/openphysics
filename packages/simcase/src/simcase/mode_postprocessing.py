# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Mode power, confinement, overlaps and Gaussian coupling saved with ``em.modes2d`` results.

Every number here is a direct call of ``galerkin.mode_overlap`` on the arrays
that ``RunResult.save`` writes to ``fields.npz``, so a reader can recompute it
from the archive alone (tests/simcase/test_modes_postprocessing.py checks that
the saved values are byte-identical to those calls). The recipe, per study point:

    mesh  = galerkin.Mesh(nodes, triangles, {})          nodes in the document length unit
    space = galerkin.EdgeSpace(mesh)                      its edges equal the saved ``edges``
    et    = vector_transverse[p, :, m]                    line integrals of E_t in the document unit
    ez    = -1j * vector_longitudinal[p, :, m]            E_z = 1j * ez, the solve_modes gauge
    k0    = 2 * pi / wavelength                           wavelength in the document unit (um -> 1/um)

vector results
    mode_power[p, m]          = vector_power(space, et, ez, neff[p, m], k0, mu_r=1)
    confinement[p, m, r]      = confinement_factor(space, et, ez, Re eps_r(triangles, wavelength), regions == r)
    field_overlap[p]          = overlap_matrix(space, et of all modes, ez of all modes, "field")
    coupling_efficiency[p, m] = coupling_efficiency(space, et, ez, et_gauss) with
                                et_gauss, _ = interpolate_vector_field(space, x-polarised Gaussian)
scalar results (``fields[p, :, m]`` = phi)
    mode_power[p, m]          = scalar_power(mesh, phi)
    confinement[p, m, r]      = scalar_confinement_factor(mesh, phi, regions == r)
    field_overlap[p, a, b]    = scalar_overlap(mesh, phi_a, phi_b)
    coupling_efficiency[p, m] = scalar_coupling_efficiency(mesh, phi, Gaussian at the nodes)

Units. The saved fields are relative: the largest centroid |E| (vector) or the
nodal peak (scalar) is 1, in no physical unit. Read the vector amplitudes as
volts per document length unit (V/um for a micrometre document): then
``mode_power`` is the complex Poynting integral P = 1/2 int (E x H^*) . zhat dA
of that field in watts, Re P the time-averaged power carried in +z. Read them
as V/m instead and the power in watts is ``mode_power * length_unit_to_m**2``.
Dividing a saved mode by ``sqrt(Re mode_power)`` gives a field that carries 1 W
(amplitudes in V per document unit). The imaginary part is reactive and is
roundoff for a lossless mode; a lossy mode (complex ``neff``) has a nonzero
imaginary part and its modes are not power-orthogonal. The scalar
``mode_power`` is int |phi|^2 dA in (document unit)^2 of the relative field.
``field_overlap`` carries (document unit)^2 too: its diagonal is int |E|^2 dA,
the mass norm, which for scalar results equals ``mode_power`` exactly.
``confinement`` (energy fraction Re eps_r |E|^2 per region, plain |phi|^2 for
scalar results) and ``coupling_efficiency`` are dimensionless; the rows of
``confinement`` sum to 1 because the regions tile the window.

The Gaussian input is E(x, y) = exp(-((x - cx)^2 + (y - cy)^2) / w0^2) with
``waist`` w0 the 1/e field radius and ``center`` (cx, cy) in the document unit;
it is x-polarised for vector results (compared with E_t of each mode alone) and
a scalar amplitude for scalar results.

Not computed: PML results (the saved transverse coefficients are covariant
integrals in complex-stretched coordinates, so the lossless Poynting formula
on the whole window is not the physical power and the window is not the
physical one) and subspace sweeps (cluster frames, not modes). Those results
gain no new keys.
"""

from __future__ import annotations

import math

import numpy as np

from galerkin import EdgeSpace, Mesh
from galerkin.mode_overlap import (confinement_factor, coupling_efficiency, interpolate_vector_field,
                                   overlap_matrix, scalar_coupling_efficiency, scalar_confinement_factor,
                                   scalar_overlap, scalar_power, vector_power)

__all__ = ["validate_mode_overlap", "gaussian_settings", "vector_postprocessing", "scalar_postprocessing",
           "stack_points", "summary_block"]

#: The one accepted post-processing input, ``results.mode_overlap``.
_OVERLAP_KEYS = frozenset({"gaussian"})
_GAUSSIAN_KEYS = frozenset({"waist", "center"})


def _finite_number(value) -> bool:
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def validate_mode_overlap(results: dict, domain: dict, error: type[Exception]) -> None:
    """``results.mode_overlap`` is absent or ``{"gaussian": {"waist": w0, "center": [x, y]}}``.

    Unknown keys at either level are refused, the waist must be a positive finite
    number and the centre must lie inside the geometry window (document units).
    """
    if "mode_overlap" not in results:
        return
    spec = results["mode_overlap"]
    if not isinstance(spec, dict):
        raise error("results.mode_overlap must be an object, e.g. "
                    '{"gaussian": {"waist": 0.5, "center": [0.0, 0.11]}}')
    unknown = sorted(set(spec) - _OVERLAP_KEYS)
    if unknown:
        raise error(f"results.mode_overlap: unknown key(s) {unknown}; only {sorted(_OVERLAP_KEYS)} are defined")
    if "gaussian" not in spec:
        raise error("results.mode_overlap needs 'gaussian' ({'waist': w0, 'center': [x, y]})")
    g = spec["gaussian"]
    if not isinstance(g, dict):
        raise error("results.mode_overlap.gaussian must be an object with 'waist' and 'center'")
    unknown = sorted(set(g) - _GAUSSIAN_KEYS)
    if unknown:
        raise error(f"results.mode_overlap.gaussian: unknown key(s) {unknown}; "
                    f"only {sorted(_GAUSSIAN_KEYS)} are defined")
    missing = sorted(_GAUSSIAN_KEYS - set(g))
    if missing:
        raise error(f"results.mode_overlap.gaussian: missing {missing}")
    if not _finite_number(g["waist"]) or g["waist"] <= 0:
        raise error("results.mode_overlap.gaussian.waist must be a positive finite number (the 1/e field "
                    "radius, in the document length unit)")
    c = g["center"]
    if not (isinstance(c, list) and len(c) == 2 and all(_finite_number(v) for v in c)):
        raise error("results.mode_overlap.gaussian.center must be [x, y], two finite numbers in the document "
                    "length unit")
    if not (domain["xmin"] <= c[0] <= domain["xmax"] and domain["ymin"] <= c[1] <= domain["ymax"]):
        raise error(f"results.mode_overlap.gaussian.center {c} lies outside the geometry window "
                    f"x [{domain['xmin']}, {domain['xmax']}], y [{domain['ymin']}, {domain['ymax']}]")


def gaussian_settings(results: dict) -> dict | None:
    """``{"waist": float, "center": (x, y)}`` of a validated document, or None."""
    spec = results.get("mode_overlap")
    if spec is None:
        return None
    g = spec["gaussian"]
    return {"waist": float(g["waist"]), "center": (float(g["center"][0]), float(g["center"][1]))}


def _gaussian(settings: dict):
    w0, (cx, cy) = settings["waist"], settings["center"]

    def amplitude(x, y):
        return np.exp(-((np.asarray(x) - cx) ** 2 + (np.asarray(y) - cy) ** 2) / w0 ** 2)
    return amplitude


def _mesh(nodes, triangles) -> Mesh:
    return Mesh(np.asarray(nodes, dtype=float), np.asarray(triangles), {})


def _region_masks(regions, num_regions):
    regions = np.asarray(regions)
    return [regions == r for r in range(num_regions)]


def vector_postprocessing(nodes, triangles, edges, transverse, longitudinal, neff, wavelength, eps_r,
                          regions, num_regions, gaussian: dict | None = None) -> dict:
    """One study point of a vector result (module docstring for the recipe).

    transverse (E, M) and longitudinal (N, M) as ``VectorField`` holds them, in the
    document length unit; ``wavelength`` in the same unit; ``eps_r`` (T,) complex
    permittivity (only its real part weights the confinement); ``regions`` (T,)
    indices below ``num_regions``.
    """
    mesh = _mesh(nodes, triangles)
    space = EdgeSpace(mesh)
    if not np.array_equal(space.edges, np.asarray(edges)):
        raise ValueError("the saved edges do not match EdgeSpace(mesh): the post-processing recipe would "
                         "not reproduce the saved values")
    et = np.asarray(transverse).T                     # (M, E)
    ez = -1j * np.asarray(longitudinal).T             # (M, N): E_z = 1j * ez
    neff = np.asarray(neff)
    k0 = 2.0 * np.pi / float(wavelength)
    eps = np.asarray(eps_r).real
    modes = et.shape[0]
    power = np.empty(modes, dtype=complex)
    confinement = np.full((modes, num_regions), np.nan)
    masks = _region_masks(regions, num_regions)
    for m in range(modes):
        power[m] = vector_power(space, et[m], ez[m], neff[m], k0, 1.0)
        try:
            confinement[m] = [confinement_factor(space, et[m], ez[m], eps, mask) for mask in masks]
        except ValueError:
            pass                                       # no positive energy (e.g. metal-dominated): NaN row
    out = {"mode_power": power, "confinement": confinement,
           "field_overlap": overlap_matrix(space, et, ez, "field")}
    if gaussian is not None:
        g = _gaussian(gaussian)

        def polarised(x, y):
            return np.stack([g(x, y), np.zeros_like(np.asarray(x, dtype=float))], axis=-1)
        et_in, _ = interpolate_vector_field(space, polarised)
        out["coupling_efficiency"] = np.array([coupling_efficiency(space, et[m], ez[m], et_in)
                                               for m in range(modes)])
    return out


def scalar_postprocessing(nodes, triangles, fields, regions, num_regions, gaussian: dict | None = None) -> dict:
    """One study point of a scalar result; ``fields`` (N, M) nodal values, real or complex."""
    mesh = _mesh(nodes, triangles)
    phi = np.asarray(fields).T                        # (M, N)
    modes = phi.shape[0]
    masks = _region_masks(regions, num_regions)
    power = np.array([scalar_power(mesh, phi[m]) for m in range(modes)])
    confinement = np.array([[scalar_confinement_factor(mesh, phi[m], mask) for mask in masks]
                            for m in range(modes)]).reshape(modes, num_regions)
    overlap = np.empty((modes, modes), dtype=complex)
    for a in range(modes):
        for b in range(modes):
            overlap[a, b] = scalar_overlap(mesh, phi[a], phi[b])
    out = {"mode_power": power, "confinement": confinement, "field_overlap": overlap}
    if gaussian is not None:
        amplitude = _gaussian(gaussian)(mesh.nodes[:, 0], mesh.nodes[:, 1])
        out["coupling_efficiency"] = np.array([scalar_coupling_efficiency(mesh, phi[m], amplitude)
                                               for m in range(modes)])
    return out


def stack_points(points: list[dict]) -> dict:
    """Per-point dictionaries -> arrays with a leading study-point axis."""
    return {key: np.stack([p[key] for p in points]) for key in points[0]}


def summary_block(arrays: dict, *, vector: bool, length_unit: str, region_names: list[str],
                  gaussian: dict | None) -> dict:
    """The ``mode_postprocessing`` entry of ``summary.json``: values, unit and description per key."""
    unit2 = f"{length_unit}^2"
    power = arrays["mode_power"]
    out = {
        "recipe": "galerkin.mode_overlap on the saved nodes (document length unit), triangles, edges and fields "
                  "with k0 = 2 pi / wavelength; see simcase.mode_postprocessing",
        "mode_power": {
            "value": power.real.tolist(),
            "unit": f"W for amplitudes in V/{length_unit} (x length_unit_to_m^2 for V/m)" if vector else unit2,
            "description": ("complex Poynting integral 1/2 int (E x H*).z dA of the saved relative field (max "
                            "centroid |E| = 1); Re is the +z time-averaged power, Im reactive (roundoff when "
                            "lossless); divide the field by sqrt(Re mode_power) for 1 W" if vector
                            else "int |phi|^2 dA of the saved relative field (nodal peak 1)")},
        "confinement": {
            "value": arrays["confinement"].tolist(), "regions": list(region_names), "unit": "1",
            "description": ("energy fraction int_R Re(eps_r) |E|^2 / int Re(eps_r) |E|^2 per region" if vector
                            else "fraction int_R |phi|^2 / int |phi|^2 per region") + "; rows sum to 1"},
        "field_overlap": {
            "real": arrays["field_overlap"].real.tolist(), "imag": arrays["field_overlap"].imag.tolist(),
            "unit": unit2,
            "description": "<E_a, E_b> = int conj(E_a) . E_b dA of the saved fields (Hermitian); the diagonal "
                           "is the mass norm int |E|^2 dA" + ("" if vector else ", equal to mode_power")},
    }
    if vector:
        out["mode_power"]["imag"] = power.imag.tolist()
    if gaussian is not None:
        out["coupling_efficiency"] = {
            "value": arrays["coupling_efficiency"].tolist(), "unit": "1",
            "gaussian": {"waist": gaussian["waist"], "center": list(gaussian["center"]), "unit": length_unit,
                         "field": "exp(-((x-cx)^2+(y-cy)^2)/waist^2)" + (", x-polarised" if vector else "")},
            "description": "|<E_mode, E_in>|^2 / (<E_mode, E_mode> <E_in, E_in>) of the Gaussian into each mode"
                           + (" (transverse field only)" if vector else "")}
    return out
