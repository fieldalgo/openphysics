# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The group index of a single ``em.modes2d`` study (``results.group_index``).

n_g = n_eff - lambda0 dn_eff/dlambda0 by a central difference in the vacuum wavelength: the
mesh of the study is solved again at lambda0 - step and lambda0 + step, each material evaluated
at each wavelength (so the material dispersion is included), exactly as a wavelength sweep
solves its points. Each mode of the lambda0 solve is matched to a candidate of each side solve
with the resolved-mode tracker's own tests (``tracking.match_modes``); the difference is that
of a tracked sweep (``runner._kernel_group_index``, second-order ``np.gradient``) on the three
matched values. A mode that is not matched on either side has no value (NaN, null in JSON) and
a reason; the run does not fail. With an open boundary (pml, no bend) n_eff and so n_g are
complex: the side solves keep the entry's target and PML, and the overlaps of the matching are
taken on the physical window (the tracker's physical weights), as in a tracked sweep. Everything here is in the kernel frame (micrometres,
exp(+i omega t)); ``runner._to_public`` converts once.
"""

from __future__ import annotations

import numpy as np

from .schema import DocumentError
from .tracking import ModeTracker, match_modes, tracking_settings

#: the tracker names of the matching (the resolved-mode assignment of the sweep path)
VECTOR_TRACKING = "electric-l2-assignment-v1"
SCALAR_TRACKING = "scalar-l2-assignment-v1"


def check_lossless(model, wavelengths: list[float]) -> None:
    """Refuse ``results.group_index`` when a material is lossy at one of the three wavelengths
    (called before any solve)."""
    for wavelength in wavelengths:
        if np.any(np.asarray(model._permittivity(wavelength)).imag != 0):
            raise DocumentError(f"results.group_index: the materials are lossy at vacuum_wavelength "
                                f"{wavelength:g} um; the group index of lossy modes is not computed",
                                path="results.group_index")


def single_point(model, physics: dict, wavelengths: list[float], neff0, field0, say) -> dict:
    """``{"values": (1, M), "tracking": name, "reasons": [M]}`` in the kernel frame.

    ``physics`` is the kernel's entry, ``wavelengths`` the kernel wavelengths (um)
    ``[lambda0 - step, lambda0, lambda0 + step]``, ``neff0`` and ``field0`` the lambda0 solve
    (the run's own result, unchanged)."""
    from .runner import _kernel_solve

    vector = physics["formulation"] == "vector"
    requested = len(neff0)
    check_lossless(model, wavelengths)
    settings = tracking_settings(int(physics["num_modes"]))     # the search a sweep of this entry makes
    weights, seed = 1.0, None
    if "pml" in physics:
        # an open boundary: the overlaps of the matching on the physical window and the first match
        # near the target, as a tracked sweep of the same entry makes them (runner.run)
        from .physics_pml_modes import coordinates
        weights = coordinates(model.solver_mesh, physics["pml"], physics.get("bend")).physical.astype(float)
        seed = physics["n_target"]
    tracker = ModeTracker(model.solver_mesh, requested, settings, scalar=not vector, physical_weights=weights,
                          seed_target=seed)
    key = "vector_field" if vector else "fields"
    name = VECTOR_TRACKING if vector else SCALAR_TRACKING
    say(f"group index: central difference over {wavelengths[0]:g}, {wavelengths[1]:g} and {wavelengths[2]:g} um; "
        f"modes matched by L2 overlap ({name})")
    matched = np.full((3, requested), np.nan, dtype=np.asarray(neff0).dtype if np.iscomplexobj(neff0) else float)
    matched[1] = neff0
    reasons: list[str | None] = [None] * requested
    # the lambda0 solve has mode_count candidates: two requested modes within the tolerance there
    reference = np.asarray(neff0)
    for mode in range(requested):
        others = np.delete(reference, mode)
        if len(others) and np.min(abs(others - reference[mode])) <= settings["degeneracy_tolerance"]:
            reasons[mode] = (f"vacuum_wavelength {wavelengths[1]:g} um: near-degenerate with another requested "
                             f"mode within n_eff tolerance {settings['degeneracy_tolerance']:g}")
    for row in (0, 2):
        wavelength = wavelengths[row]
        location = f"vacuum_wavelength {wavelength:g} um"
        try:
            res = _kernel_solve(model, dict(physics, wavelength=wavelength, num_modes=settings["search_modes"]))
        except (ValueError, RuntimeError) as exc:
            columns, side = np.full(requested, -1), [f"{location}: the solve failed ({exc})"] * requested
        else:
            columns, side = match_modes(tracker, field0, res["neff"], res[key], location)
            for mode, column in enumerate(columns):
                if column >= 0:
                    matched[row, mode] = res["neff"][column]
        for mode, reason in enumerate(side):
            if reasons[mode] is None and reason is not None:
                reasons[mode] = reason
    wl = np.asarray(wavelengths, dtype=float)
    group = matched - wl[:, None] * np.gradient(matched, wl, axis=0, edge_order=2)
    values = group[1:2].copy()
    for mode, reason in enumerate(reasons):
        if reason is not None:
            values[0, mode] = np.nan
            say(f"  mode {mode + 1}: no group index ({reason})")
    say("  n_g = " + ", ".join("null" if not np.isfinite(g) else f"{g.real:.6f}" for g in values[0]))
    return {"values": values, "tracking": name, "reasons": reasons}
