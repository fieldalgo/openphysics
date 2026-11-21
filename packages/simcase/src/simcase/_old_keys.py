# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The 0.2 key names and their format 0.3 names, for "did you mean" text only.

The reader looks a key up here only after it found no slot for it (``E-KEY-UNKNOWN``). It
reads no document: a 0.2 document stops at ``E-FORMAT`` before any key is looked at. An entry
is ``(old key, new key, where, note)``; ``where`` limits it to keys whose parent path matches
that regular expression (None: anywhere).
"""

from __future__ import annotations

import re

_NEGATE = "the value changes sign: inward = -outward, so write the negated value"

ENTRIES = (
    # mesh and geometry (shared)
    ("mesh_size", "element_size", None, "with its unit, such as \"0.5 um\""),
    ("size", "element_size", r"^mesh(\.controls\[\d+\])?$", "with its unit, such as \"0.2 um\""),
    ("min_angle", "minimum_angle", r"^mesh$", "with its unit, such as \"28 deg\""),
    ("subdivisions", "subdivision_count", r"^mesh$", None),
    ("center", "position", r"^(mesh\.grading|results\.mode_overlap\.gaussian)$", "a list of quantity strings"),
    ("distance", "refinement_distance", r"^mesh(\.grading|\.controls\[\d+\])$", "with its unit"),
    ("circle_segments", "circle_segment_count", r"^mesh\.controls\[\d+\]$", None),
    ("time_s", "time", r"^study$", "a tagged array such as {\"unit\": \"s\", \"values\": [0, 1]}"),
    # materials
    ("n", "refractive_index", r"^materials", "with k as {\"n\": .., \"k\": ..}"),
    ("k", "refractive_index", r"^materials", "{\"n\": .., \"k\": ..}"),
    ("sellmeier", "refractive_index", r"^materials", "the model form {\"model\": \"sellmeier\", ...}"),
    ("conductivity_w_mk", "thermal_conductivity", None, "with its unit, such as \"45 W/(m K)\""),
    ("thermal_conductivity_w_mk", "thermal_conductivity", None, "with its unit, such as \"45 W/(m K)\""),
    ("volumetric_heat_capacity_j_m3k", "volumetric_heat_capacity", None, "with its unit"),
    ("electrical_conductivity_s_m", "electrical_conductivity", None, "with its unit, such as \"58 MS/m\""),
    ("conductivity_s_m", "electrical_conductivity", None, "with its unit, such as \"58 MS/m\""),
    ("young_modulus_pa", "youngs_modulus", None, "with its unit, such as \"200 GPa\""),
    ("thermal_expansion_per_k", "linear_expansion_coefficient", None, "with its unit, such as \"12 ppm/K\""),
    # heat
    ("heat_source_w_m3", "heat_source_density", None, "with its unit"),
    ("dirichlet_temperature_k", "prescribed_temperature", None, "each value with its unit, such as \"300 K\""),
    ("outward_flux_w_m2", "inward_heat_flux", None, _NEGATE),
    ("h_w_m2k", "heat_transfer_coefficient", None, "with its unit"),
    ("ambient_temperature_k", "ambient_temperature", None, "with its unit"),
    ("initial_temperature_k", "initial_temperature", None, "with its unit"),
    ("origin_temperature_k", "reference_temperature", None, "with its unit"),
    ("gradient_k_per_m", "temperature_gradient", None, "with its unit"),
    ("values_k", "values", None, "a tagged array {\"unit\": \"K\", \"values\": [...]}"),
    # electric and Joule
    ("dirichlet_potential_v", "prescribed_electric_potential", None, "each value with its unit, such as \"0 V\""),
    ("outward_current_a_m2", "inward_current_density", None, _NEGATE),
    ("conductivity_model", "electrical_conductivity", None, "the model form {\"model\": \"linear_resistivity\", ...}"),
    ("reference_conductivity_s_m", "reference_conductivity", None, "with its unit"),
    ("reference_temperature_k", "reference_temperature", r"electrical_conductivity|conductivity_model",
     "with its unit"),
    ("alpha_per_k", "resistivity_temperature_coefficient", None, "with its unit"),
    ("temperature_range_k", "valid", None, "{\"temperature\": [\"290 K\", \"400 K\"]}"),
    ("relaxation", "relaxation_factor", None, None),
    ("temperature_atol_k", "temperature_tolerance", None, "with its unit, such as \"1e-8 K\""),
    ("max_iterations", "iteration_limit", None, None),
    # mechanics
    ("reference_temperature_k", "stress_free_temperature", r"^physics", "with its unit"),
    ("displacement_m", "prescribed_displacement", None, "components with their unit, such as {\"x\": \"0 mm\"}"),
    ("traction_pa", "traction", None, "a list of quantity strings"),
    ("body_force_n_m3", "body_force_density", None, "a list of quantity strings"),
    ("pressure_pa", "gauge_pressure", None, "with its unit"),
    # em
    ("wavelength", "vacuum_wavelength", r"^physics", "with its unit, such as \"1.55 um\""),
    ("num_modes", "mode_count", r"^physics", None),
    ("n_target", "target_effective_index", None, None),
    ("n_cladding", "effective_index_threshold", None, None),
    ("thickness", "pml_thickness", r"\.pml$", "each side with its unit"),
    ("strength", "pml_strength", r"\.pml$", None),
    ("order", "pml_order", r"\.pml$", None),
    ("min_physical_fraction", "pml_minimum_physical_fraction", r"\.pml$", None),
    ("radius", "bend_radius", r"\.bend$", "with its unit"),
    ("origin", "bend_origin", r"\.bend$", "with its unit"),
    ("waist", "beam_waist_radius", None, "with its unit"),
    ("search_modes", "search_mode_count", None, None),
    ("min_overlap", "mode_tracking_threshold", None, None),
    ("min_margin", "mode_tracking_margin_threshold", None, None),
    ("cluster_span_max", "cluster_span_tolerance", None, None),
    ("external_gap_min", "cluster_gap_threshold", None, None),
    ("A", "constant", None, None),
    ("B", "terms", None, "[{\"strength\": .., \"resonance_wavelength_squared\": ..}]"),
    ("C", "terms", None, "[{\"strength\": .., \"resonance_wavelength_squared\": ..}]"),
    ("range", "valid", r"refractive_index", "{\"vacuum_wavelength\": [lo, hi]}"),
    # cavity
    ("target_frequency_hz", "target_frequency", None, "with its unit, such as \"250 MHz\""),
    ("conductivity_s_per_m", "electrical_conductivity", None, "with its unit"),
)


def suggest(key: str, parent_path: str) -> tuple[str, str | None] | None:
    """``(new name, note)`` of an old key under ``parent_path``, or None."""
    for old, new, where, note in ENTRIES:
        if old == key and (where is None or re.search(where, parent_path)):
            return new, note
    return None
