# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Example documents (also used by the tests)."""

import copy
from .thermal_examples import THERMAL_SLAB, THERMAL_MIXED, THERMAL_REGIONS, TRANSIENT_THERMAL_REGIONS

_PEC = {"left": "pec", "right": "pec", "top": "pec", "bottom": "pec"}

SOI_STRIP = {
    "openphysics": "0.3",
    "name": "SOI strip waveguide 500 x 220 nm",
    "geometry": {
        "length_unit": "um", "depth": None,
        "domain": {"xmin": -1.5, "xmax": 1.5, "ymin": -1.2, "ymax": 1.2},
        "background": {"material": "physmat:SiO2"},
        "shapes": [
            {"name": "core", "type": "rect", "x": -0.25, "y": 0.0, "w": 0.5, "h": 0.22, "material": "physmat:Si",
             "element_size": "0.02 um"},
        ],
    },
    "physics": {"em1": {"type": "em.modes2d", "formulation": "vector", "vacuum_wavelength": "1.55 um",
                        "mode_count": 2, "effective_index_threshold": 1.45, "boundary": dict(_PEC)}},
    "mesh": {"element_size": "0.25 um",
             "grading": {"position": ["0 um", "0.11 um"], "near": "0.02 um", "far": "0.16 um",
                         "refinement_distance": "1 um"}},
    "study": {"type": "sweep", "parameter": "physics.em1.vacuum_wavelength",
              "values": {"unit": "um", "values": [1.4, 1.45, 1.5, 1.55, 1.6, 1.65, 1.7]}},
}

SLAB_TE_CHECK = {
    "openphysics": "0.3",
    "name": "220 nm Si slab, TE check against refsol",
    "geometry": {
        "length_unit": "um", "depth": None,
        "domain": {"xmin": -0.5, "xmax": 0.5, "ymin": -1.2, "ymax": 1.2},
        "background": {"material": "physmat:SiO2"},
        "shapes": [
            {"name": "film", "type": "rect", "x": -0.5, "y": 0.0, "w": 1.0, "h": 0.22, "material": "physmat:Si",
             "element_size": "0.01 um"},
        ],
    },
    "physics": {"em1": {"type": "em.modes2d", "formulation": "scalar", "vacuum_wavelength": "1.55 um",
                        "mode_count": 1,
                        "boundary": {"left": "pmc", "right": "pmc", "top": "pec", "bottom": "pec"}}},
    "mesh": {"element_size": "0.25 um",
             "grading": {"position": ["0 um", "0.11 um"], "near": "0.01 um", "far": "0.08 um",
                         "refinement_distance": "1 um"}},
    "study": {"type": "single"},
}

HADLEY_RIB = {
    "openphysics": "0.3",
    "name": "Hadley 2002 rib waveguide, slab 0.3 um",
    "geometry": {
        "length_unit": "um", "depth": None,
        "domain": {"xmin": -9.0, "xmax": 9.0, "ymin": -10.0, "ymax": 3.0},
        "background": {"material": "physmat:vacuum"},
        "shapes": [
            {"name": "substrate", "type": "rect", "x": -9.0, "y": -10.0, "w": 18.0, "h": 10.0, "material": "n3.40"},
            {"name": "slab", "type": "rect", "x": -9.0, "y": 0.0, "w": 18.0, "h": 0.3, "material": "n3.44",
             "element_size": "0.1 um"},
            {"name": "rib", "type": "rect", "x": -1.5, "y": 0.0, "w": 3.0, "h": 1.0, "material": "n3.44",
             "element_size": "0.1 um"},
        ],
    },
    "materials": {"n3.40": {"refractive_index": 3.4}, "n3.44": {"refractive_index": 3.44}},
    "physics": {"em1": {"type": "em.modes2d", "formulation": "scalar", "vacuum_wavelength": "1.15 um",
                        "mode_count": 1, "boundary": dict(_PEC)}},
    "mesh": {"element_size": "0.6 um",
             "grading": {"position": ["0 um", "0.5 um"], "near": "0.1 um", "far": "0.6 um",
                         "refinement_distance": "3 um"}},
    "study": {"type": "single"},
}

FIBER = {
    "openphysics": "0.3",
    "name": "step-index fiber a = 4 um, n1 = 1.45, n2 = 1.44",
    "geometry": {
        "length_unit": "um", "depth": None,
        "domain": {"xmin": -20.0, "xmax": 20.0, "ymin": -20.0, "ymax": 20.0},
        "background": {"material": "clad"},
        "shapes": [
            {"name": "core", "type": "circle", "cx": 0.0, "cy": 0.0, "r": 4.0, "material": "core",
             "element_size": "0.5 um"},
        ],
    },
    "materials": {"core": {"refractive_index": 1.45}, "clad": {"refractive_index": 1.44}},
    "physics": {"em1": {"type": "em.modes2d", "formulation": "scalar", "vacuum_wavelength": "1.55 um",
                        "mode_count": 2, "boundary": dict(_PEC)}},
    "mesh": {"element_size": "3 um",
             "grading": {"position": ["0 um", "0 um"], "near": "0.5 um", "far": "3 um",
                         "refinement_distance": "12 um"}},
    "study": {"type": "single"},
}

VECTOR_SLAB = {
    "openphysics": "0.3",
    "name": "220 nm dielectric slab, vector TE",
    "geometry": {
        "length_unit": "um", "depth": None,
        "domain": {"xmin": -0.05, "xmax": 0.05, "ymin": -1.5, "ymax": 1.72},
        "background": {"material": "clad"},
        "shapes": [{"name": "film", "type": "rect", "x": -0.05, "y": 0.0, "w": 0.1, "h": 0.22, "material": "film",
                    "element_size": "0.012 um"}],
    },
    "materials": {"film": {"refractive_index": 3.48}, "clad": {"refractive_index": 1.444}},
    "physics": {"em1": {"type": "em.modes2d", "formulation": "vector", "vacuum_wavelength": "1.55 um",
                        "mode_count": 1, "effective_index_threshold": 1.444, "boundary": dict(_PEC)}},
    "mesh": {"element_size": "0.06 um",
             "grading": {"position": ["0 um", "0.11 um"], "near": "0.012 um", "far": "0.06 um",
                         "refinement_distance": "1 um"}},
    "study": {"type": "single"},
}

VECTOR_FIBER = copy.deepcopy(FIBER)
VECTOR_FIBER["name"] = "step-index fiber, full vector modes"
VECTOR_FIBER["physics"]["em1"].update(formulation="vector", mode_count=6, effective_index_threshold=1.44)

HADLEY_RIB_VECTOR = copy.deepcopy(HADLEY_RIB)
HADLEY_RIB_VECTOR["name"] = "Hadley 2002 rib waveguide, slab 0.3 um, full vector"
# 3.4 is the substrate index. The side slabs guide modes above it, so this interval
# also holds slab modes; mode_count = 1 keeps only the highest, the rib mode.
HADLEY_RIB_VECTOR["physics"]["em1"].update(formulation="vector", effective_index_threshold=3.4)

VECTOR_SLAB_SWEEP = copy.deepcopy(VECTOR_SLAB)
VECTOR_SLAB_SWEEP["name"] = "220 nm dielectric slab, tracked vector TE wavelength sweep"
VECTOR_SLAB_SWEEP["study"] = dict(type="sweep", parameter="physics.em1.vacuum_wavelength",
                                  values={"unit": "um", "values": [1.45, 1.5, 1.55, 1.6, 1.65]})

EXAMPLES = {"soi_strip": SOI_STRIP, "slab_te_check": SLAB_TE_CHECK, "hadley_rib": HADLEY_RIB,
            "hadley_rib_vector": HADLEY_RIB_VECTOR, "fiber": FIBER, "vector_slab": VECTOR_SLAB, "vector_fiber": VECTOR_FIBER,
            "vector_slab_sweep": VECTOR_SLAB_SWEEP}


CAVITY_BOX = {
    "openphysics": "0.3",
    "name": "Vacuum PEC cube, modes near 250 MHz",
    "geometry": {
        "length_unit": "m",
        "domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1, "zmin": 0, "zmax": 1},
        "background": {"material": "physmat:vacuum"},
        "shapes": [],
    },
    "physics": {"em1": {"type": "em.cavity3d", "boundary": "pec", "search": "near_target",
                         "target_frequency": "250 MHz", "mode_count": 5}},
    "mesh": {"subdivision_count": [6, 6, 6]},
    "study": {"type": "single"},
    "results": {"save_fields": True, "plots": False},
}

EXAMPLES["cavity_box"] = CAVITY_BOX

CAVITY_LOSSY_SLAB = {
    "openphysics": "0.3",
    "name": "Copper box with a lossy dielectric slab, Q near 150 MHz",
    "geometry": {
        "length_unit": "m",
        "domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 0.8, "zmin": 0, "zmax": 0.6},
        "background": {"material": "physmat:vacuum"},
        "shapes": [{"type": "box", "name": "slab", "material": "lossy_dielectric",
                    "xmin": 0, "xmax": 1, "ymin": 0, "ymax": 0.8, "zmin": 0, "zmax": 0.3}],
    },
    # exp(-i omega t): Im relative_permittivity >= 0 is loss
    "materials": {"lossy_dielectric": {"relative_permittivity": {"re": 4.0, "im": 0.04}}},
    "physics": {"em1": {"type": "em.cavity3d", "boundary": {"electrical_conductivity": "58 MS/m"},
                         "search": "near_target", "target_frequency": "150 MHz",
                         "mode_count": 3}},
    "mesh": {"subdivision_count": [8, 8, 8]},
    "study": {"type": "single"},
    "results": {"save_fields": True, "plots": False},
}

EXAMPLES["cavity_lossy_slab"] = CAVITY_LOSSY_SLAB

# Opt-in subspace tracking of the isolated HE11 polarization pair. The next
# guided family (TE01/TM01/HE21) is the observed lower guard.
VECTOR_FIBER_SUBSPACE_SWEEP = copy.deepcopy(VECTOR_FIBER)
VECTOR_FIBER_SUBSPACE_SWEEP["name"] = "step-index fiber, HE11 pair subspace wavelength sweep"
VECTOR_FIBER_SUBSPACE_SWEEP["physics"]["em1"]["mode_count"] = 2
VECTOR_FIBER_SUBSPACE_SWEEP["study"] = {
    "type": "sweep", "parameter": "physics.em1.vacuum_wavelength",
    "values": {"unit": "um", "values": [1.5, 1.525, 1.55, 1.575, 1.6]},
    "tracking": {"method": "electric-l2-subspace-v1", "cluster_span_tolerance": 1e-4, "cluster_gap_threshold": 1e-3}}
EXAMPLES["vector_fiber_subspace_sweep"] = VECTOR_FIBER_SUBSPACE_SWEEP

# These examples are deliberately excluded from the optional Studio.
EXAMPLES.update(thermal_slab=THERMAL_SLAB, thermal_mixed=THERMAL_MIXED, thermal_regions=THERMAL_REGIONS)

TRANSIENT_THERMAL_UNIFORM = {
    'openphysics': '0.3', 'name': 'Insulated constant-source transient heat',
    'geometry': {'length_unit': 'm', 'depth': None, 'domain': {'xmin': 0, 'xmax': 1, 'ymin': 0, 'ymax': 1}},
    'materials': {},
    'physics': {'heat1': {'type': 'thermal.transient2d', 'thermal_conductivity': '2.5 W/(m K)',
                         # c = 4 J/(m^3 K) is below the plausibility band: a manufactured solution
                         'volumetric_heat_capacity': {'value': '4 J/(m^3 K)',
                                                      'accept': {'W-MAGNITUDE': 'manufactured solution'}},
                         'initial_temperature': '300 K', 'prescribed_temperature': {},
                         'heat_source_density': '8 W/m^3'}},
    'mesh': {'subdivision_count': [4, 4]},
    'study': {'type': 'transient', 'time': {'unit': 's', 'values': [0., .1, .3]}},
    'results': {'save_fields': True, 'plots': False},
}
EXAMPLES['transient_thermal_uniform'] = TRANSIENT_THERMAL_UNIFORM
EXAMPLES['transient_thermal_regions'] = TRANSIENT_THERMAL_REGIONS


# Constant-boundary steady example; supported by the headless runner only.
THERMAL_BOUNDARY = {
    'openphysics': '0.3', 'name': 'Steady additive outward flux and convection',
    'geometry': {'length_unit': 'm', 'depth': None, 'domain': {'xmin': 0, 'xmax': 1, 'ymin': 0, 'ymax': 1}},
    'materials': {},
    'physics': {'heat1': {'type': 'thermal.steady2d', 'thermal_conductivity': '2 W/(m K)',
                          'heat_source_density': '0 W/m^3', 'prescribed_temperature': {'left': '300 K'},
                          # 2 W/m^2 leaves the body through the right side
                          'inward_heat_flux': {'right': '-2 W/m^2'},
                          'convection': {'right': {'heat_transfer_coefficient': '4 W/(m^2 K)',
                                                   'ambient_temperature': '290 K'}}}},
    'mesh': {'subdivision_count': [8, 8]},
    'study': {'type': 'single'},
    'results': {'save_fields': True, 'plots': False},
}
EXAMPLES['thermal_boundary'] = THERMAL_BOUNDARY

# Convective cooling of a slab: insulated at x=0, convection at x=L, insulated top and
# bottom, so the field is one-dimensional in x and comparable with the
# refsol.transient_heat_robin.ConvectiveSlab series. Headless runner only (boundary layout).
TRANSIENT_THERMAL_BOUNDARY = {
    'openphysics': '0.3', 'name': 'Convective cooling of a slab',
    'geometry': {'length_unit': 'm', 'depth': None, 'domain': {'xmin': 0, 'xmax': 0.05, 'ymin': 0, 'ymax': 0.01}},
    'materials': {},
    'physics': {'heat1': {'type': 'thermal.transient2d', 'thermal_conductivity': '50 W/(m K)',
                         'volumetric_heat_capacity': '3600000 J/(m^3 K)',
                         'initial_temperature': '400 K', 'prescribed_temperature': {},
                         'heat_source_density': '0 W/m^3',
                         'convection': {'right': {'heat_transfer_coefficient': '500 W/(m^2 K)',
                                                  'ambient_temperature': '300 K'}}}},
    'mesh': {'subdivision_count': [20, 2]},
    'study': {'type': 'transient', 'time': {'unit': 's', 'values': [0., 10., 20., 40., 80.]}},
    'results': {'save_fields': True, 'plots': False},
}
EXAMPLES['transient_thermal_boundary'] = TRANSIENT_THERMAL_BOUNDARY

from .electric_examples import ELECTRIC_RECTANGLE, JOULE_RECTANGLE, JOULE_TEMPERATURE
EXAMPLES.update(electric_rectangle=ELECTRIC_RECTANGLE, joule_rectangle=JOULE_RECTANGLE,
                joule_temperature=JOULE_TEMPERATURE)

from .mechanics_examples import ELASTIC_PLATE, ELASTIC_REGIONS, THERMOELASTIC_BAR, THERMOELASTIC_REGIONS
EXAMPLES.update(elastic_plate=ELASTIC_PLATE, thermoelastic_bar=THERMOELASTIC_BAR,
                elastic_regions=ELASTIC_REGIONS, thermoelastic_regions=THERMOELASTIC_REGIONS)
