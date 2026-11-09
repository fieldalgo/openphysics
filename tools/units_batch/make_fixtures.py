"""Build the frozen 0.2 fixtures of the units-batch harness from the test builders at 627eb28.

Provenance only: it imports today's test builders, so it runs against a checkout of 627eb28
(python make_fixtures.py <627eb28 tree> <output folder>), not against later commits.
The fixtures in fixtures/v02/ were written by it and are not regenerated."""
import copy, json, sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
for p in sorted((ROOT / "packages").glob("*/src")):
    sys.path.insert(0, str(p))
sys.path[:0] = [str(ROOT / "tests" / "simcase"), str(ROOT / "tests" / "_support"), str(ROOT / "tests" / "galerkin")]

import test_thermal_axisymmetric_regions as axi
import test_thermal_length_canonical as tlc
import test_thermal_named_boundaries as tnb
import test_transient_boundary as ttb
import test_electric_regions as ter
import test_joule_regions as tjr
import test_electric_joule as tej
import test_mechanics as tm
import test_mechanics_regions as tmr
import test_length_canonical as lc
import test_lossy_modes as tlm
import test_pml_contract as tpc
import test_modes_postprocessing as tmp
import test_cavity3d_materials as tcm
from simcase import examples

docs = {}

# -- heat ---------------------------------------------------------------------------------------
docs["heat_axisymmetric_cylinder"] = axi.cylinder()
core = {"name": "core", "type": "rect", "x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0, "material": "copperish"}
shell = axi.cylinder(features=[core], materials={"copperish": {"conductivity_w_mk": 2.0, "source": "document value"}},
                     source={"core": axi.Q}, size_mm=0.05)
shell["materials"]["pla"]["conductivity_w_mk"] = 0.5            # as test_g4_2 sets k2 after building
docs["heat_axisymmetric_core_shell"] = shell
docs["heat_axisymmetric_cylinder_transient"] = axi.cylinder_transient()
shell_t = copy.deepcopy(shell)                                  # cylinder_transient's changes on the core and shell
shell_t["name"] = "axisymmetric core and shell transient"
shell_t["units"]["time"] = "s"
shell_t["materials"]["pla"]["volumetric_heat_capacity_j_m3k"] = axi.C_PLA
shell_t["materials"]["copperish"]["volumetric_heat_capacity_j_m3k"] = 3.4e6
shell_t["physics"]["heat1"].update({"type": "thermal.transient2d", "initial_temperature_k": axi.TB})
shell_t["mesh"]["size"] = 0.1
shell_t["study"] = {"type": "transient", "time_s": [0.0, 1.0, 2.0]}
docs["heat_axisymmetric_core_shell_transient"] = shell_t
docs["heat_regions_canonical_steady"] = tlc._problem()
docs["heat_regions_canonical_transient"] = tlc._problem(transient=True)
core = {"name": "core", "type": "rect", "x": 10.0, "y": 5.0, "w": 10.0, "h": 10.0, "material": "steel"}
docs["heat_v1_interior_dirichlet"] = tnb.plate([core], physics={"dirichlet_temperature_k": {"left": 300.0, "right": 300.0, "seam": 340.0}},
                                                selections={"seam": {"boundary": {"of": "core"}}}, size=0.5)
docs["heat_transient_rectangle_sampled"] = ttb.dirichlet_only_documents()["sampled"]
sampled_boundary = copy.deepcopy(examples.EXAMPLES["transient_thermal_boundary"])
sampled_boundary["physics"]["heat1"]["dirichlet_temperature_k"] = {"left": {"values_k": [400.0, 395.0, 390.0, 380.0, 370.0]}}
docs["heat_transient_rectangle_sampled_boundary"] = sampled_boundary
regions_t = tnb.plate([tnb.HOLE], kind="transient", size=1.0,
                      boundary_tags=[{"tag": "inner", "select": {"boundary": {"of": "hole"}}}],
                      physics={"initial_temperature_k": 300.0,
                               "dirichlet_temperature_k": {"left": {"values_k": [300.0, 310.0, 320.0]},
                                                           "inner": {"values_k": [300.0, 330.0, 340.0]}}})
regions_t["study"]["time_s"] = [0.0, 5.0, 10.0]
docs["heat_transient_regions_sampled"] = regions_t

# -- electric and Joule -------------------------------------------------------------------------
docs["electric_e1_series"] = ter.strip([ter.RIGHT_HALF], {"dirichlet_potential_v": {"left": 1.0, "right": 0.0}})
docs["electric_e2_parallel"] = ter.strip([ter.TOP_HALF], {"dirichlet_potential_v": {"left": 2.0, "right": 0.0}})
docs["electric_e3_coax_0p8"] = ter.coax(0.8)
driven = ter.coax(0.8)
driven["physics"]["e"]["dirichlet_potential_v"] = {"rim": 0.0}
driven["physics"]["e"]["outward_current_a_m2"] = {"inner": -10.0}
docs["electric_current_terminal"] = driven
docs["joule_j1_series"] = tjr.strip(tjr.SERIES)
docs["joule_j4_convective"] = tjr.strip(tjr.CONVECTIVE)
docs["joule_j2_coax_0p4"] = tjr.coax(0.4)
j = 0.1 / (tjr.L / tjr.SIGMA["A"] + tjr.L / tjr.SIGMA["B"])
docs["joule_current_terminal"] = tjr.strip({"dirichlet_potential_v": {"right": 0.0}, "outward_current_a_m2": {"left": -j},
                                            "dirichlet_temperature_k": {"left": tjr.T0, "right": tjr.T0}}, size=0.125)
d = tej.data()
p = d["physics"]["electric"]
p["dirichlet_potential_v"] = {"right": 0.}
p["outward_current_a_m2"] = {"left": -2.}
p["dirichlet_temperature_k"] = {}
p["convection"] = {side: dict(h_w_m2k=4., ambient_temperature_k=300.) for side in ("left", "right")}
p["outward_flux_w_m2"] = {"left": .2, "right": .2}
docs["joule_rectangle_robin_and_flux"] = d
d = tej.data("joule_temperature")
d["physics"]["electric"]["iteration"].update(relaxation=1e-12, max_iterations=2)
docs["joule_temperature_iteration_failure"] = d

# -- mechanics ----------------------------------------------------------------------------------
for plane in ("stress", "strain"):
    d = tm.document("mm", 1e3, plane=plane, displacement={"left": {"x": 0.}, "bottom": {"y": 0.}},
                    traction={"right": [3e6, 0.], "top": [0., -1e5]}, body_force=[0., -7.7e4])
    d["geometry"]["domain"] = dict(xmin=-500., xmax=500., ymin=100., ymax=500.)
    docs[f"mechanics_j1_{plane}"] = d
    docs[f"mechanics_k1_{plane}"] = tm.thermo_document(
        "mm", 1e3, plane=plane, domain=(-.5, .5, .1, .5), temperatures={"left": 293.15, "right": 353.15},
        convection={"top": dict(h_w_m2k=25., ambient_temperature_k=300.)}, outward_flux_w_m2={"bottom": 150.},
        heat_source_w_m3=2e4, displacement={"left": {"x": 0.}, "bottom": {"y": 0.}},
        traction={"right": [3e6, 0.], "top": [0., -1e5]}, body_force=[0., -2.7e4])
    docs[f"mechanics_r1_elastic_{plane}"] = tmr.pipe(0.75, plane=plane, body_force_n_m3=[1e5, -2e5],
                                                     traction_pa={"rim": [3e5, -1e5]})
    docs[f"mechanics_r1_thermoelastic_{plane}"] = tmr.layered(
        "mechanics.thermoelastic2d", split="y", size=4.0, nu=0.25, plane=plane,
        displacement_m={"left": {"x": 0.0, "y": 0.0}}, traction_pa={"right": [1e6, 0.0]},
        body_force_n_m3=[0.0, -1e4], heat_source_w_m3={"alu": 2e6}, dirichlet_temperature_k={"left": 300.0},
        convection={"top": {"h_w_m2k": 25.0, "ambient_temperature_k": 290.0}}, outward_flux_w_m2={"bottom": -500.0})
    docs[f"mechanics_r5_{plane}"] = tmr.layered(
        "mechanics.thermoelastic2d", plane=plane, reference_temperature_k=300.0,
        dirichlet_temperature_k={side: 350.0 for side in ("left", "right", "bottom", "top")},
        displacement_m={"left": {"x": 0.0}, "bottom": {"y": 0.0}, "top": {"y": 0.0}})
docs["mechanics_r2_v1_stress"] = tmr.layered(plane="stress", v1=True, displacement_m={"left": {"x": 0.0}, "bottom": {"y": 0.0}},
                                             traction_pa={"right": [1e6, 0.0]})
docs["mechanics_r2_flat_strain"] = tmr.layered(plane="strain", v1=False, displacement_m={"left": {"x": 0.0}, "bottom": {"y": 0.0}},
                                               traction_pa={"right": [1e6, 0.0]})
docs["mechanics_r4_bore_0p5"] = tmr.pipe(0.5, pressure_pa={"bore": tmr.P})
docs["mechanics_r5b"] = tmr.layered("mechanics.thermoelastic2d", size=2.5, reference_temperature_k=300.0,
                                    dirichlet_temperature_k={"left": 400.0, "right": 300.0},
                                    displacement_m={"left": {"x": 0.0}, "bottom": {"y": 0.0}, "top": {"y": 0.0}})
for name, physics in (("elastic_regions", {"displacement_m": {"left": {"x": 1e-7}, "bottom": {"y": 0.0}},
                                           "body_force_n_m3": [1e5, -2e6]}),
                      ("thermoelastic_regions", {"displacement_m": {"left": {"x": 1e-7, "y": 0.0}},
                                                 "body_force_n_m3": [0.0, -1e5], "pressure_pa": {"right": 2e6}})):
    raw = copy.deepcopy(examples.EXAMPLES[name])
    raw["physics"][next(iter(raw["physics"]))].update(physics)
    docs[f"mechanics_unit_variant_{name}"] = raw

# -- em.modes2d ---------------------------------------------------------------------------------
docs["em_sellmeier_range"] = lc._rib_with_polygon_and_sellmeier()
open_low = lc._rib_with_polygon_and_sellmeier()
open_low["materials"]["glass"]["sellmeier"]["range"] = [0.0, 6.7]
docs["em_sellmeier_open_lower_bound"] = open_low
docs["em_lossy_film_vector"] = tlm.document("vector").data
docs["em_pml_scalar"] = tpc.document("scalar").data
docs["em_pml_bent_vector"] = tpc.document("vector", bend=True).data
docs["em_gaussian_overlap_scalar"] = tmp.slab_document("scalar", 0.04)
docs["em_gaussian_overlap_vector"] = tmp.slab_document("vector", 0.04)
sweep = tlm.document("scalar").data
sweep["study"] = dict(type="sweep", parameter="physics.em1.wavelength", values=[1.54, 1.55, 1.56])
docs["em_lossy_scalar_tracked_sweep"] = sweep
for symbol, per_um in lc.SCALES:
    docs[f"em_length_{symbol}_fiber"] = lc._written_in(copy.deepcopy(examples.FIBER), symbol, per_um)
    docs[f"em_length_{symbol}_sellmeier_rib"] = lc._written_in(lc._rib_with_polygon_and_sellmeier(), symbol, per_um)
    docs[f"em_length_{symbol}_vector_slab"] = lc._written_in(copy.deepcopy(examples.VECTOR_SLAB), symbol, per_um)
    docs[f"em_length_{symbol}_subspace_sweep"] = lc._written_in(copy.deepcopy(examples.VECTOR_FIBER_SUBSPACE_SWEEP),
                                                                symbol, per_um)

# -- em.cavity3d --------------------------------------------------------------------------------
d = tcm._small(tcm.slab_document())
d["physics"]["em1"]["boundary"] = {"conductivity_s_per_m": {"zmax": 1e6}}
docs["cavity_wall_conductivity"] = d
d = tcm._small(tcm.slab_document())
d["materials"]["lossy_dielectric"]["relative_permeability"] = [1.5, -0.01]
docs["cavity_complex_permeability"] = d
d = tcm._small(tcm.slab_document())
d["geometry"]["shapes"] = []
d["geometry"]["background"] = {"material": "lossy_dielectric"}
d["physics"]["em1"]["boundary"] = "pec"
d["physics"]["em1"]["target_frequency_hz"] = 80e6
docs["cavity_dielectric_background"] = d

OUT.mkdir(parents=True, exist_ok=True)
for name, doc in docs.items():
    (OUT / f"{name}.json").write_text(json.dumps(doc, indent=2, allow_nan=False) + "\n", encoding="utf-8")
print(len(docs), "fixtures")
