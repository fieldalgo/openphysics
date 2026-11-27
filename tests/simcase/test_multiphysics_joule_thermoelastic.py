# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Closed-form and independent execution checks for the planar electrothermal chain."""
import json
from pathlib import Path

import numpy as np
import pytest

from simcase import Document, run
from simcase.schema import DocumentError


EXAMPLE = (Path(__file__).resolve().parents[2] / "examples" / "simcase"
           / "multiphysics_joule_thermoelastic_strip.json")


def strip():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_strip_analytical_solution_and_refinement():
    errors = []
    for size in (0.1, 0.05, 0.025):
        model = strip()
        model["mesh"]["element_size"] = f"{size} mm"
        result = run(Document.from_dict(model), verbose=False)
        assert result.solve_order == [["dc"], ["heat"], ["structure"]]
        cell_transfer = result.couplings["joule_heat"]
        assert cell_transfer["location"] == "element"
        assert cell_transfer["conservation_residual"] == 0
        assert result.couplings["expansion"]["location"] == "node"
        assert all(c["mesh_signature"] == "match" and c["max_abs_difference"]["value"] == 0
                   for c in result.couplings.values())

        dc, heat, mechanics = (result.results[k] for k in ("dc", "heat", "structure"))
        fields = mechanics.fields
        x = fields["node_coordinates"][:, 0]
        centroid_x = x[fields["triangles"]].mean(axis=1)
        length = 1e-3
        np.testing.assert_allclose(dc.fields["electric_potential"], 0.2 * x / length, atol=1e-12, rtol=0)
        np.testing.assert_allclose(dc.fields["joule_power_density"], 4e7, rtol=1e-10, atol=0)
        assert dc.summary()["balance"]["joule_power_per_depth"]["value"] == pytest.approx(20, rel=1e-11)
        assert heat.diagnostics["generated_heat_rate_per_depth"] == pytest.approx(20, rel=1e-11)
        assert heat.diagnostics["outward_heat_rate_per_depth"] == pytest.approx(20, rel=1e-10)
        np.testing.assert_array_equal(fields["temperature"], heat.temperature)

        # Independent plane strain solution: u_y = 0, sigma_xx = sigma_xy = 0,
        # epsilon_xx = ((1 + nu) / (1 - nu)) * alpha * (T - T_ref).
        rise = 1e7 * x * (length - x)
        ux = (5 / 3) * 1e-5 * 1e7 * (length * x**2 / 2 - x**3 / 3)
        transverse = -(1e10 * 1e-5 / 0.75) * 1e7 * centroid_x * (length - centroid_x)
        stress = np.stack((0 * transverse, transverse, 0 * transverse), axis=1)
        errors.append([np.max(abs(fields["temperature"] - 300 - rise)),
                       np.max(abs(fields["displacement"] - np.stack((ux, 0 * x), axis=1))),
                       np.max(abs(fields["stress"] - stress)),
                       np.max(abs(fields["stress_zz"] - transverse))])

    assert np.all(np.asarray(errors[1:]) < 0.75 * np.asarray(errors[:-1]))
    assert np.all(np.asarray(errors[-1]) < [4e-4, 1.5e-11, 8e3, 3e3])


def test_existing_solvers_agree_on_a_nonuniform_source():
    from galerkin.electric import solve_steady_electric
    from galerkin.joule_heating import solve_steady_joule_heat
    from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity
    from simcase.mechanics_regions import region_mechanics_inputs

    model = strip()
    model["geometry"]["components"]["strip"]["features"] = [
        {"name": "resistive", "type": "rect", "x": 0.5, "y": 0, "w": 0.5, "h": 0.5,
         "material": "resistive"}]
    model["materials"]["resistive"] = {**model["materials"]["strip"], "electrical_conductivity": "250 S/m"}
    doc = Document.from_dict(model)
    result = run(doc, verbose=False)
    dc, heat, mechanics = (result.results[k] for k in ("dc", "heat", "structure"))
    separate_dc = run(doc.views["dc"], verbose=False)
    for key, field in separate_dc.fields.items():
        np.testing.assert_array_equal(dc.fields[key], field)

    mesh = heat.mesh
    electrical = solve_steady_electric(
        mesh, electrical_conductivity={"background": 1000., "resistive": 250.},
        prescribed_electric_potential={**dict.fromkeys(mesh.boundary["left"], 0.),
                                      **dict.fromkeys(mesh.boundary["right"], 0.2)})
    coupled = solve_steady_joule_heat(
        mesh, electrical_result=electrical, thermal_conductivity=2.,
        prescribed_temperature=dict.fromkeys(np.r_[mesh.boundary["left"], mesh.boundary["right"]], 300.))
    source = dc.fields["joule_power_density"]
    assert source.max() > 3 * source.min()
    np.testing.assert_allclose(source, coupled.electrical.joule_power_density, rtol=1e-12)
    np.testing.assert_allclose(heat.temperature, coupled.thermal.temperature, rtol=0, atol=1e-12)
    np.testing.assert_allclose(heat.solution.generated_heat_rate_per_depth,
                               coupled.thermal.generated_heat_rate_per_depth, rtol=1e-12, atol=1e-12)

    snapshot = freeze_temperature(mesh, temperature=coupled.thermal.temperature)
    standalone = solve_thermoelasticity(
        mesh, snapshot, **region_mechanics_inputs(doc.views["structure"], mesh, heat.region_materials))
    np.testing.assert_allclose(mechanics.fields["displacement"], standalone.displacement, rtol=1e-12, atol=1e-20)
    np.testing.assert_allclose(mechanics.fields["stress"], standalone.stress, rtol=1e-12, atol=1e-7)


@pytest.mark.parametrize("name, key, value, message", [
    ("heat", "heat_source_density", "1 W/m^3", "choose one heat source"),
    ("structure", "prescribed_temperature", {"left": "300 K"}, "give heat inputs on the coupled"),
    ("structure", "type", "mechanics.elasticity2d", "is not coupled in this release"),
    ("dc", "type", "joule.temperature2d", "is not coupled in this release"),
])
def test_conflicting_or_unsupported_stages_are_refused(name, key, value, message):
    model = strip()
    model["physics"][name][key] = value
    with pytest.raises(DocumentError, match=message):
        Document.from_dict(model)
