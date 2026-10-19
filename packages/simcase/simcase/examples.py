# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Example documents (also used by the tests)."""

import copy
from .thermal_examples import THERMAL_SLAB, THERMAL_MIXED, THERMAL_REGIONS

SOI_STRIP = {
    "openphysics": "0.2",
    "name": "SOI strip waveguide 500 x 220 nm",
    "units": {"length": "um"},
    "geometry": {
        "domain": {"xmin": -1.5, "xmax": 1.5, "ymin": -1.2, "ymax": 1.2},
        "background": {"material": "SiO2"},
        "shapes": [
            {"name": "core", "type": "rect", "x": -0.25, "y": 0.0, "w": 0.5, "h": 0.22, "material": "Si", "mesh_size": 0.02},
        ],
    },
    "physics": {"em1": {"type": "em.modes2d", "formulation": "scalar", "wavelength": 1.55, "num_modes": 2,
                        "boundary": {"left": "pec", "right": "pec", "top": "pec", "bottom": "pec"}}},
    "mesh": {"size": 0.25, "grading": {"center": [0.0, 0.11], "near": 0.02, "far": 0.16, "distance": 1.0}},
    "study": {"type": "sweep", "parameter": "physics.em1.wavelength", "values": [1.40, 1.45, 1.50, 1.55, 1.60, 1.65, 1.70]},
}

SLAB_TE_CHECK = {
    "openphysics": "0.2",
    "name": "220 nm Si slab, TE check against refsol",
    "units": {"length": "um"},
    "geometry": {
        "domain": {"xmin": -0.5, "xmax": 0.5, "ymin": -1.2, "ymax": 1.2},
        "background": {"material": "SiO2"},
        "shapes": [
            {"name": "film", "type": "rect", "x": -0.5, "y": 0.0, "w": 1.0, "h": 0.22, "material": "Si", "mesh_size": 0.01},
        ],
    },
    "physics": {"em1": {"type": "em.modes2d", "formulation": "scalar", "wavelength": 1.55, "num_modes": 1,
                        "boundary": {"left": "pmc", "right": "pmc", "top": "pec", "bottom": "pec"}}},
    "mesh": {"size": 0.25, "grading": {"center": [0.0, 0.11], "near": 0.01, "far": 0.08, "distance": 1.0}},
    "study": {"type": "single"},
}

HADLEY_RIB = {
    "openphysics": "0.2",
    "name": "Hadley 2002 rib waveguide, slab 0.3 um",
    "units": {"length": "um"},
    "geometry": {
        "domain": {"xmin": -9.0, "xmax": 9.0, "ymin": -10.0, "ymax": 3.0},
        "background": {"material": "vacuum"},
        "shapes": [
            {"name": "substrate", "type": "rect", "x": -9.0, "y": -10.0, "w": 18.0, "h": 10.0, "material": "n3.40"},
            {"name": "slab", "type": "rect", "x": -9.0, "y": 0.0, "w": 18.0, "h": 0.3, "material": "n3.44", "mesh_size": 0.1},
            {"name": "rib", "type": "rect", "x": -1.5, "y": 0.0, "w": 3.0, "h": 1.0, "material": "n3.44", "mesh_size": 0.1},
        ],
    },
    "materials": {"n3.40": {"n": 3.40}, "n3.44": {"n": 3.44}},
    "physics": {"em1": {"type": "em.modes2d", "formulation": "scalar", "wavelength": 1.15, "num_modes": 1,
                        "boundary": {"left": "pec", "right": "pec", "top": "pec", "bottom": "pec"}}},
    "mesh": {"size": 0.6, "grading": {"center": [0.0, 0.5], "near": 0.1, "far": 0.6, "distance": 3.0}},
    "study": {"type": "single"},
}

FIBER = {
    "openphysics": "0.2",
    "name": "step-index fiber a = 4 um, n1 = 1.45, n2 = 1.44",
    "units": {"length": "um"},
    "geometry": {
        "domain": {"xmin": -20.0, "xmax": 20.0, "ymin": -20.0, "ymax": 20.0},
        "background": {"material": "clad"},
        "shapes": [
            {"name": "core", "type": "circle", "cx": 0.0, "cy": 0.0, "r": 4.0, "material": "core", "mesh_size": 0.5},
        ],
    },
    "materials": {"core": {"n": 1.45}, "clad": {"n": 1.44}},
    "physics": {"em1": {"type": "em.modes2d", "formulation": "scalar", "wavelength": 1.55, "num_modes": 2,
                        "boundary": {"left": "pec", "right": "pec", "top": "pec", "bottom": "pec"}}},
    "mesh": {"size": 3.0, "grading": {"center": [0.0, 0.0], "near": 0.5, "far": 3.0, "distance": 12.0}},
    "study": {"type": "single"},
}

VECTOR_SLAB = {
    "openphysics": "0.2",
    "name": "220 nm dielectric slab, vector TE",
    "units": {"length": "um"},
    "geometry": {
        "domain": {"xmin": -0.05, "xmax": 0.05, "ymin": -1.5, "ymax": 1.72},
        "background": {"material": "clad"},
        "shapes": [{"name": "film", "type": "rect", "x": -0.05, "y": 0.0,
                    "w": 0.1, "h": 0.22, "material": "film", "mesh_size": 0.012}],
    },
    "materials": {"film": {"n": 3.48}, "clad": {"n": 1.444}},
    "physics": {"em1": {"type": "em.modes2d", "formulation": "vector", "wavelength": 1.55,
                         "num_modes": 1, "n_cladding": 1.444,
                         "boundary": {"left": "pec", "right": "pec", "top": "pec", "bottom": "pec"}}},
    "mesh": {"size": 0.06, "grading": {"center": [0.0, 0.11], "near": 0.012,
                                       "far": 0.06, "distance": 1.0}},
    "study": {"type": "single"},
}

VECTOR_FIBER = copy.deepcopy(FIBER)
VECTOR_FIBER["name"] = "step-index fiber, full vector modes"
VECTOR_FIBER["physics"]["em1"].update(formulation="vector", n_cladding=1.44, num_modes=6)

VECTOR_SLAB_SWEEP = copy.deepcopy(VECTOR_SLAB)
VECTOR_SLAB_SWEEP["name"] = "220 nm dielectric slab, tracked vector TE wavelength sweep"
VECTOR_SLAB_SWEEP["study"] = dict(type="sweep", parameter="physics.em1.wavelength",
                                values=[1.45, 1.50, 1.55, 1.60, 1.65])

EXAMPLES = {"soi_strip": SOI_STRIP, "slab_te_check": SLAB_TE_CHECK, "hadley_rib": HADLEY_RIB,
            "fiber": FIBER, "vector_slab": VECTOR_SLAB, "vector_fiber": VECTOR_FIBER,
            "vector_slab_sweep": VECTOR_SLAB_SWEEP}


CAVITY_BOX = {
    "openphysics": "0.2",
    "name": "Vacuum PEC cube, modes near 250 MHz",
    "units": {"length": "m"},
    "geometry": {
        "domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1, "zmin": 0, "zmax": 1},
        "background": {"material": "vacuum"},
        "shapes": [],
    },
    "physics": {"em1": {"type": "em.cavity3d", "boundary": "pec", "search": "near_target",
                         "target_frequency_hz": 250000000.0, "num_modes": 5}},
    "mesh": {"subdivisions": [6, 6, 6]},
    "study": {"type": "single"},
    "results": {"save_fields": True, "plots": False},
}

EXAMPLES["cavity_box"] = CAVITY_BOX

# Opt-in subspace tracking of the isolated HE11 polarization pair. The next
# guided family (TE01/TM01/HE21) is the observed lower guard.
VECTOR_FIBER_SUBSPACE_SWEEP = copy.deepcopy(VECTOR_FIBER)
VECTOR_FIBER_SUBSPACE_SWEEP["name"] = "step-index fiber, HE11 pair subspace wavelength sweep"
VECTOR_FIBER_SUBSPACE_SWEEP["physics"]["em1"]["num_modes"] = 2
VECTOR_FIBER_SUBSPACE_SWEEP["study"] = {
    "type": "sweep", "parameter": "physics.em1.wavelength", "values": [1.5, 1.525, 1.55, 1.575, 1.6],
    "tracking": {"method": "electric-l2-subspace-v1", "cluster_span_max": 1e-4, "external_gap_min": 1e-3}}
EXAMPLES["vector_fiber_subspace_sweep"] = VECTOR_FIBER_SUBSPACE_SWEEP

# These examples are deliberately excluded from the optional Studio.
EXAMPLES.update(thermal_slab=THERMAL_SLAB, thermal_mixed=THERMAL_MIXED, thermal_regions=THERMAL_REGIONS)

TRANSIENT_THERMAL_UNIFORM = {
    'openphysics': '0.2', 'name': 'Insulated constant-source transient heat',
    'units': {'length': 'm', 'temperature': 'K', 'time': 's'},
    'geometry': {'domain': {'xmin': 0, 'xmax': 1, 'ymin': 0, 'ymax': 1}},
    'materials': {},
    'physics': {'heat1': {'type': 'thermal.transient2d', 'conductivity_w_mk': 2.5,
                         'volumetric_heat_capacity_j_m3k': 4.,
                         'initial_temperature_k': 300., 'dirichlet_temperature_k': {},
                         'heat_source_w_m3': 8.}},
    'mesh': {'subdivisions': [4, 4]},
    'study': {'type': 'transient', 'time_s': [0., .1, .3]},
    'results': {'save_fields': True, 'plots': False},
}
EXAMPLES['transient_thermal_uniform'] = TRANSIENT_THERMAL_UNIFORM


# Constant-boundary steady example; supported by the headless runner only.
THERMAL_BOUNDARY = {
    "openphysics": "0.2",
    "name": "Steady additive outward flux and convection",
    "units": {
        "length": "m",
        "temperature": "K"
    },
    "geometry": {
        "domain": {
            "xmin": 0,
            "xmax": 1,
            "ymin": 0,
            "ymax": 1
        }
    },
    "materials": {},
    "physics": {
        "heat1": {
            "type": "thermal.steady2d",
            "conductivity_w_mk": 2,
            "heat_source_w_m3": 0,
            "dirichlet_temperature_k": {
                "left": 300
            },
            "outward_flux_w_m2": {
                "right": 2
            },
            "convection": {
                "right": {
                    "h_w_m2k": 4,
                    "ambient_temperature_k": 290
                }
            }
        }
    },
    "mesh": {
        "subdivisions": [
            8,
            8
        ]
    },
    "study": {
        "type": "single"
    },
    "results": {
        "save_fields": True,
        "plots": False
    }
}
EXAMPLES['thermal_boundary'] = THERMAL_BOUNDARY
