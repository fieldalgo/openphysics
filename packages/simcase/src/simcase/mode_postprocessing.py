# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Mode power, confinement, overlaps and Gaussian coupling saved with ``em.modes2d`` results.

This module runs in the kernel frame (micrometres, exp(+i omega t)): every number is a direct
call of a ``galerkin.mode_overlap`` kernel (re-exported by ``galerkin.kernels``) on the kernel's
mesh and fields, and ``runner._to_public``
converts the results to SI under exp(-i omega t) once (areas times 1e-12, complex values
conjugated). A reader can recompute them from ``fields.npz`` alone, after taking the saved
arrays back to the kernel frame (tests/simcase/test_modes_postprocessing.py checks that the
saved values are those calls, converted once). The recipe, per study point ``p``:

    nodes = node_coordinates / 1e-6                       the kernel's micrometre mesh
    mesh  = galerkin.Mesh(nodes, triangles, {})
    space = galerkin.EdgeSpace(mesh)                      its edges equal the saved ``edges``
    et    = conj(unnormalized_electric_field_line_integral[p, :, m]) / 1e-6   (line integrals in um)
    ez    = -1j * conj(unnormalized_electric_field_z[p, :, m])                E_z = 1j * ez, the solve_modes gauge
    neff  = conj(effective_index[p, m])
    k0    = 2 * pi / wavelength                           the kernel's wavelength in um (1/um)

vector results (kernel names; saved as)
    mode_power[p, m]          = vector_power(space, et, ez, neff, k0, mu_r=1)
                                -> unnormalized_mode_power = conj(mode_power) * 1e-12
    confinement[p, m, r]      = confinement_factor(space, et, ez, Re eps_r(triangles, wavelength), regions == r)
                                -> confinement_factor
    field_overlap[p]          = overlap_matrix(space, et of all modes, ez of all modes, "field")
                                -> unnormalized_field_overlap = conj(field_overlap) * 1e-12
    coupling_efficiency[p, m] = coupling_efficiency(space, et, ez, et_gauss) with
                                et_gauss, _ = interpolate_vector_field(space, x-polarised Gaussian)
scalar results (phi = conj(unnormalized_mode_field[p, :, m]))
    mode_power[p, m]          = scalar_power(mesh, phi)
                                -> unnormalized_mode_field_square_integral = mode_power * 1e-12
    confinement[p, m, r]      = scalar_confinement_factor(mesh, phi, regions == r)
    field_overlap[p, a, b]    = scalar_overlap(mesh, phi_a, phi_b)
                                -> unnormalized_field_overlap = conj(field_overlap) * 1e-12
    coupling_efficiency[p, m] = scalar_coupling_efficiency(mesh, phi, Gaussian at the nodes)

Units. The saved fields are relative: the largest centroid |E| (vector) or the nodal peak
(scalar) is 1, in no physical unit. Read the vector amplitudes as V/m: then
``unnormalized_mode_power`` is the complex Poynting integral P = 1/2 int (E x H^*) . zhat dA of
that field in watts, Re P the time-averaged power carried in +z; dividing a saved mode by
``sqrt(Re P)`` gives a field that carries 1 W. The imaginary part is reactive and is roundoff
for a lossless mode; a lossy mode (complex ``effective_index``) has a nonzero imaginary part and
its modes are not power-orthogonal. ``unnormalized_mode_field_square_integral`` is int |phi|^2
dA in m^2; ``unnormalized_field_overlap`` is in m^2 too, its diagonal the mass norm int |E|^2
dA (for scalar results equal to the square integral). ``confinement_factor`` (energy fraction
Re eps_r |E|^2 per region, plain |phi|^2 for scalar results) and ``coupling_efficiency`` are
dimensionless; the rows of ``confinement_factor`` sum to 1 because the regions tile the window.

The Gaussian input is E(x, y) = exp(-((x - x0)^2 + (y - y0)^2) / w^2) with the document's
``beam_waist_radius`` w (the 1/e field radius) and ``position`` (x0, y0), handed to this module
in micrometres as ``waist`` and ``center``; it is x-polarised for vector results (compared with
E_t of each mode alone) and a scalar amplitude for scalar results.

TE fraction. ``te_polarization_fraction[p, m]`` (vector results only) is defined on the saved
SI centroid field ``unnormalized_electric_field`` (E_x, E_y, E_z per triangle T) and the triangle
areas A_T of ``node_coordinates``, summed over every triangle of the window, all regions:

    f_TE = sum_T A_T |E_x,T|^2 / sum_T A_T (|E_x,T|^2 + |E_y,T|^2)

with x the document's horizontal axis and E_z left out; f_TM = 1 - f_TE. It needs no kernel
call, so any reader of the saved samples gets the same number (``te_polarization_fraction``).
Two modes whose Re n_eff differ by at most 1e-3 are a degenerate pair: each member's fraction is
then an arbitrary rotation within the pair and only their sum is defined; both are still saved.
The threshold is 1e-3 because the mesh splits a symmetric pair (a square core) by 1e-4 to 6e-4 at
core element sizes of 40 to 10 nm, below the n_eff discretization error at those meshes. A mesh
split above 1e-3, possible on very coarse meshes, is not recognised as a pair, and a member's
fraction is then a rotation chosen by the mesh.

Effective area. ``effective_area[p, m]`` (m^2) is, for vector results, defined on the same saved
centroid field and triangle areas, with all three components, summed over every triangle of the
window, all regions:

    A_eff = (sum_T A_T |E_T|^2)^2 / sum_T A_T |E_T|^4,   |E_T|^2 = |E_x,T|^2 + |E_y,T|^2 + |E_z,T|^2

This is the common form behind commercial mode solvers' "effective area"; it is not the vectorial
nonlinear effective area of Afshar and Monro (which weights by the Poynting vector and E . E). It
converges to the same limit as ``galerkin.kernels.effective_area(..., include_longitudinal=True)``
on the Whitney/P1 field (tests/simcase/test_mode_effective_area.py). For scalar results it is
``scalar_effective_area(mesh, phi)`` in the kernel frame times 1e-12 (|phi|^2 at the nodes, the P1
mass in the numerator). Each member of a degenerate pair has its own value, which depends on the
rotation the mesh chose within the pair.

Open boundary (PML). A vector PML result without a bend gets ``te_polarization_fraction`` and
``effective_area`` only, by the same formulas summed over its physical window: the triangles whose
centroid (p0 + p1 + p2) / 3 lies inside the result's ``physical_bounds`` (``physical_window``, the
bounds included), from ``node_coordinates`` and ``physical_bounds`` in metres. There the saved
centroid field is the physical E (the solver divides the stretched components by the coordinate
factors, which are 1 there); the PML is excluded. Its ``mode_postprocessing`` holds those two keys
and ``integration_region: "physical_window"``. For a closed window the physical window is the
whole window, so the formulas are those above and no key is added.

Not computed: power, confinement, overlaps and coupling of PML results (the saved transverse
coefficients are covariant integrals in complex-stretched coordinates, so the lossless Poynting
formula on the whole window is not the physical power), any value of a PML result with a bend
or of a scalar PML result, and subspace sweeps (cluster frames, not modes). Those gain no keys.
"""

from __future__ import annotations

import math

import numpy as np

from galerkin import EdgeSpace, Mesh
from galerkin.kernels import (confinement_factor, coupling_efficiency, interpolate_vector_field, overlap_matrix,
                              scalar_coupling_efficiency, scalar_confinement_factor, scalar_effective_area,
                              scalar_overlap, scalar_power, vector_power)

__all__ = ["validate_mode_overlap", "gaussian_settings", "vector_postprocessing", "scalar_postprocessing",
           "te_polarization_fraction", "effective_area", "physical_window", "stack_points", "summary_block",
           "open_summary_block", "PHYSICAL_WINDOW"]

#: The one accepted post-processing input, ``results.mode_overlap``.
_OVERLAP_KEYS = frozenset({"gaussian"})
_GAUSSIAN_KEYS = frozenset({"waist", "center"})


def _finite_number(value) -> bool:
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def validate_mode_overlap(results: dict, domain: dict, error: type[Exception]) -> None:
    """``results.mode_overlap`` of the kernel hand-off (micrometres) is absent or
    ``{"gaussian": {"waist": w0, "center": [x, y]}}``.

    Unknown keys at either level are refused, the waist must be a positive finite
    number and the centre must lie inside the geometry window.
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
                    "radius, in micrometres in the kernel hand-off)")
    c = g["center"]
    if not (isinstance(c, list) and len(c) == 2 and all(_finite_number(v) for v in c)):
        raise error("results.mode_overlap.gaussian.center must be [x, y], two finite numbers in micrometres "
                    "(the kernel hand-off)")
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

    transverse (E, M) and longitudinal (N, M) as the kernel's ``VectorField`` holds them, in
    micrometres under exp(+i omega t); ``wavelength`` in micrometres; ``eps_r`` (T,) the kernel's
    complex permittivity (only its real part weights the confinement); ``regions`` (T,)
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
    out = {"mode_power": power, "confinement": confinement, "field_overlap": overlap,
           "effective_area": np.array([scalar_effective_area(mesh, phi[m]) for m in range(modes)])}
    if gaussian is not None:
        amplitude = _gaussian(gaussian)(mesh.nodes[:, 0], mesh.nodes[:, 1])
        out["coupling_efficiency"] = np.array([scalar_coupling_efficiency(mesh, phi[m], amplitude)
                                               for m in range(modes)])
    return out


def physical_window(node_coordinates, triangles, bounds) -> np.ndarray:
    """The physical window of an open-boundary (PML) result: a mask (T,) of the triangles whose
    centroid (p0 + p1 + p2) / 3 lies inside ``bounds`` = [[x0, y0], [x1, y1]] (the result's
    ``physical_bounds``, in the coordinates' unit), the bounds included. Each term is written out so
    that a reader in another language reproduces it exactly."""
    x = np.asarray(node_coordinates, dtype=float)
    t = np.asarray(triangles)
    (x0, y0), (x1, y1) = np.asarray(bounds, dtype=float)
    p0, p1, p2 = x[t[:, 0]], x[t[:, 1]], x[t[:, 2]]
    cx = (p0[:, 0] + p1[:, 0] + p2[:, 0]) / 3.0
    cy = (p0[:, 1] + p1[:, 1] + p2[:, 1]) / 3.0
    return (cx >= x0) & (cx <= x1) & (cy >= y0) & (cy <= y1)


def _areas(node_coordinates, triangles, electric, window):
    x = np.asarray(node_coordinates, dtype=float)
    t = np.asarray(triangles)
    e = np.asarray(electric)
    if window is not None:
        window = np.asarray(window, dtype=bool)
        t, e = t[window], e[window]
    p0, p1, p2 = x[t[:, 0]], x[t[:, 1]], x[t[:, 2]]
    area = 0.5 * np.abs((p1[:, 0] - p0[:, 0]) * (p2[:, 1] - p0[:, 1]) - (p1[:, 1] - p0[:, 1]) * (p2[:, 0] - p0[:, 0]))
    return area, e


def te_polarization_fraction(node_coordinates, triangles, electric, window=None) -> np.ndarray:
    """f_TE (M,) of one study point from the saved centroid field (module docstring).

    ``node_coordinates`` (N, 2), ``triangles`` (T, 3) and ``electric`` (T, M, 3), the complex
    E_x, E_y, E_z of each mode at each triangle centroid; the coordinates' length unit cancels.
    ``window`` (T,) bool: sum over those triangles only (``physical_window`` of an open-boundary
    result); None sums over every triangle. A mode with no transverse field gives NaN. Each term
    is written out (|E|^2 = re^2 + im^2, A_T = |cross| / 2) so that a reader in another language
    reproduces it to rounding.
    """
    area, e = _areas(node_coordinates, triangles, electric, window)
    ex = e[:, :, 0].real ** 2 + e[:, :, 0].imag ** 2
    ey = e[:, :, 1].real ** 2 + e[:, :, 1].imag ** 2
    num = area @ ex
    den = num + area @ ey
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / np.where(den > 0, den, 1.0), np.nan)


def effective_area(node_coordinates, triangles, electric, window=None) -> np.ndarray:
    """A_eff (M,) of one study point from the saved centroid field (module docstring), in the
    coordinates' length unit squared.

    Arguments as ``te_polarization_fraction``. A mode with no field gives NaN. Each term is written
    out (|E|^2 = re^2 + im^2 per component, A_T = |cross| / 2) so that a reader in another language
    reproduces it to rounding.
    """
    area, e = _areas(node_coordinates, triangles, electric, window)
    density = (e[:, :, 0].real ** 2 + e[:, :, 0].imag ** 2) + (e[:, :, 1].real ** 2 + e[:, :, 1].imag ** 2) \
        + (e[:, :, 2].real ** 2 + e[:, :, 2].imag ** 2)
    num = area @ density
    den = area @ (density * density)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num * num / np.where(den > 0, den, 1.0), np.nan)


def stack_points(points: list[dict]) -> dict:
    """Per-point dictionaries -> arrays with a leading study-point axis."""
    return {key: np.stack([p[key] for p in points]) for key in points[0]}


def _part(values):
    """Nested lists of doubles; a value that is not finite is null (value objects, spec §5.1)."""
    a = np.asarray(values)
    if a.ndim == 0:
        x = float(a)
        return x if math.isfinite(x) else None
    return [_part(v) for v in a]


def summary_block(arrays: dict, *, vector: bool, region_names: list[str], gaussian: dict | None) -> dict:
    """The ``mode_postprocessing`` entry of ``summary.json`` from the public arrays (SI, exp(-i
    omega t); ``runner._to_public``): value objects with a description each."""
    from .results_common import TIME_CONVENTION
    out = {
        "recipe": "galerkin.mode_overlap in the kernel frame (the micrometre mesh whose nodes times 1e-6 are "
                  "node_coordinates, the conjugated saved fields under exp(+i omega t), k0 = 2 pi / wavelength "
                  "in 1/um), then areas times 1e-12 and complex values conjugated once; on node_coordinates in "
                  "metres the same calls agree to rounding; see simcase.mode_postprocessing"}
    if vector:
        power = arrays["unnormalized_mode_power"]
        out["unnormalized_mode_power"] = {
            "unit": "W", "re": _part(power.real), "im": _part(power.imag), "time_convention": TIME_CONVENTION,
            "description": "complex Poynting integral 1/2 int (E x H*).z dA of the saved relative field read as "
                           "V/m (max centroid |E| = 1); Re is the +z time-averaged power, Im reactive (roundoff "
                           "when lossless); divide the field by sqrt(Re P) for 1 W"}
    else:
        out["unnormalized_mode_field_square_integral"] = {
            "unit": "m^2", "values": _part(arrays["unnormalized_mode_field_square_integral"]),
            "description": "int |phi|^2 dA of the saved relative field (nodal peak 1)"}
    overlap = arrays["unnormalized_field_overlap"]
    out["confinement_factor"] = {
        "unit": "1", "values": _part(arrays["confinement_factor"]), "regions": list(region_names),
        "description": ("energy fraction int_R Re(eps_r) |E|^2 / int Re(eps_r) |E|^2 per region" if vector
                        else "fraction int_R |phi|^2 / int |phi|^2 per region") + "; rows sum to 1"}
    out["unnormalized_field_overlap"] = {
        "unit": "m^2", "re": _part(overlap.real), "im": _part(overlap.imag), "time_convention": TIME_CONVENTION,
        "description": "<E_a, E_b> = int conj(E_a) . E_b dA of the saved fields (Hermitian); the diagonal is the "
                       "mass norm int |E|^2 dA" + ("" if vector else ", equal to "
                                                   "unnormalized_mode_field_square_integral")}
    if "te_polarization_fraction" in arrays:
        out["te_polarization_fraction"] = {
            "unit": "1", "values": _part(arrays["te_polarization_fraction"]),
            "description": "f_TE = sum_T A_T |E_x|^2 / sum_T A_T (|E_x|^2 + |E_y|^2) on the saved centroid field "
                           "unnormalized_electric_field over every triangle of the window, x horizontal, E_z left "
                           "out; f_TM = 1 - f_TE. For two modes whose Re n_eff differ by at most 1e-3 (a degenerate "
                           "pair) each member's value is an arbitrary rotation within the pair and is still saved; "
                           "only the pair's sum is defined. A mesh split of a symmetric pair above 1e-3 (very "
                           "coarse meshes) is not recognised, and a member's value is then a rotation chosen by "
                           "the mesh"}
    if "effective_area" in arrays:
        out["effective_area"] = {
            "unit": "m^2", "values": _part(arrays["effective_area"]),
            "description": ("A_eff = (sum_T A_T |E|^2)^2 / sum_T A_T |E|^4 on the saved centroid field "
                            "unnormalized_electric_field over every triangle of the window, |E|^2 = |E_x|^2 + "
                            "|E_y|^2 + |E_z|^2; the common mode-solver effective area, not the vectorial "
                            "nonlinear area of Afshar and Monro. Each member of a degenerate pair has its own "
                            "value, which depends on the rotation within the pair" if vector else
                            "A_eff = (int |phi|^2 dA)^2 / int |phi|^4 dA of the saved nodal field (P1 mass, "
                            "degree-4 triangle rule)")}
    if gaussian is not None:
        out["coupling_efficiency"] = {
            "unit": "1", "values": _part(arrays["coupling_efficiency"]),
            "gaussian": {**gaussian, "field": "exp(-((x-x0)^2+(y-y0)^2)/beam_waist_radius^2)"
                         + (", x-polarised" if vector else "")},
            "description": "|<E_mode, E_in>|^2 / (<E_mode, E_mode> <E_in, E_in>) of the Gaussian into each mode"
                           + (" (transverse field only)" if vector else "")}
    return out


#: ``mode_postprocessing.integration_region`` of an open-boundary (PML) result
PHYSICAL_WINDOW = "physical_window"


def open_summary_block(arrays: dict) -> dict:
    """The ``mode_postprocessing`` entry of an open-boundary (PML) vector result: the TE fraction
    and the effective area on the physical window (module docstring), ``integration_region``
    "physical_window"; no power, confinement, overlap or coupling."""
    where = ("over the physical window (the triangles whose centroid lies inside open_boundary's "
             "physical_bounds, bounds included; the PML excluded)")
    return {
        "te_polarization_fraction": {
            "unit": "1", "values": _part(arrays["te_polarization_fraction"]),
            "description": "f_TE = sum_T A_T |E_x|^2 / sum_T A_T (|E_x|^2 + |E_y|^2) on the saved centroid field "
                           f"unnormalized_electric_field {where}, x horizontal, E_z left out; f_TM = 1 - f_TE. For "
                           "two modes whose Re n_eff differ by at most 1e-3 each member's value is an arbitrary "
                           "rotation within the pair; only the pair's sum is defined"},
        "effective_area": {
            "unit": "m^2", "values": _part(arrays["effective_area"]),
            "description": "A_eff = (sum_T A_T |E|^2)^2 / sum_T A_T |E|^4 on the saved centroid field "
                           f"unnormalized_electric_field {where}, |E|^2 = |E_x|^2 + |E_y|^2 + |E_z|^2. For a "
                           "strongly leaking mode it depends on the window. Each member of a degenerate pair has "
                           "its own value"},
        "integration_region": PHYSICAL_WINDOW}
