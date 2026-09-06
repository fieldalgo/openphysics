# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Example documents (also used by the tests)."""

SOI_STRIP = {
    "simdoc": "0.2",
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
    "simdoc": "0.2",
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
    "simdoc": "0.2",
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
    "simdoc": "0.2",
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

EXAMPLES = {"soi_strip": SOI_STRIP, "slab_te_check": SLAB_TE_CHECK, "hadley_rib": HADLEY_RIB, "fiber": FIBER}
