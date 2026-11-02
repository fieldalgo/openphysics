# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Dirichlet-only transient heat cases whose histories are frozen as text.

``tests/galerkin/data/transient_heat_dirichlet_48720c9.json`` holds every result
array of these cases as IEEE hexadecimal floats, computed by the solver at
origin/main 48720c9 before outward-flux and convection support was added. The
regression test in ``test_transient_heat_robin.py`` requires the same bits from
the current solver on the recorded platform and library versions, and agreement
to roundoff elsewhere. Regenerate only with the recorded solver revision:

    PYTHONPATH=tests/galerkin python -c "from transient_heat_dirichlet_cases import write; write()"
"""
import dataclasses
import json
from pathlib import Path
import platform

import numpy as np
import scipy

from galerkin.mesh import rectangle_mesh
from galerkin.transient_heat import solve_transient_heat

FIXTURE = Path(__file__).with_name("data")/"transient_heat_dirichlet_48720c9.json"


def ramp_case():
    """Left wall ramp, x-dependent initial field and a space-time source callback."""
    mesh = rectangle_mesh(1.0, 0.5, 6, 4)
    x = mesh.nodes[:, 0]

    def wall(s):
        return 300.0+20.0*min(s/0.1, 1.0)

    def source(points, s):
        return 40.0*(1.0+points[:, 0]*s)
    return dict(mesh=mesh, conductivity=2.0, volumetric_heat_capacity=3.0,
                time_s=[0.0, 0.05, 0.1, 0.2, 0.35], initial_temperature_k=300.0+10.0*x,
                dirichlet={int(i): wall for i in mesh.boundary["left"]}, heat_source=source)


def affine_case():
    """Moving affine field with every exterior node prescribed."""
    mesh = rectangle_mesh(1.0, 1.0, 3, 3)
    times = np.array([0.2, 0.27, 0.5, 0.9])
    exterior = np.unique(np.concatenate(list(mesh.boundary.values())))
    bc = {int(i): (lambda s, x=mesh.nodes[i, 0]: 290+5*x+3*(s-times[0])) for i in exterior}
    return dict(mesh=mesh, conductivity=2.5, volumetric_heat_capacity=4.0, time_s=times,
                initial_temperature_k=290+5*mesh.nodes[:, 0], dirichlet=bc, heat_source=12.0)


CASES = {"ramp": ramp_case, "affine": affine_case}


def environment():
    return {"system": platform.system(), "machine": platform.machine(),
            "numpy": np.__version__, "scipy": scipy.__version__}


def arrays(case):
    """{field: float64 array} of every array field of the case's result."""
    result = solve_transient_heat(**case())
    return {f.name: np.asarray(getattr(result, f.name)) for f in dataclasses.fields(result)
            if isinstance(getattr(result, f.name), np.ndarray)}


def encode(a):
    a = np.asarray(a)
    if a.dtype.kind in "iu":
        return {"shape": list(a.shape), "dtype": "int", "values": a.ravel().tolist()}
    return {"shape": list(a.shape), "dtype": "float",
            "values": [float(v).hex() for v in a.ravel().tolist()]}


def decode(entry):
    if entry["dtype"] == "int":
        return np.array(entry["values"], dtype=np.int64).reshape(entry["shape"])
    return np.array([float.fromhex(v) for v in entry["values"]]).reshape(entry["shape"])


def write(path=FIXTURE):
    data = {"solver": "galerkin.transient_heat at origin/main 48720c9", "environment": environment(),
            "cases": {name: {f: encode(a) for f, a in arrays(case).items()} for name, case in CASES.items()}}
    path.write_text(json.dumps(data, indent=0), encoding="utf-8")


def read(path=FIXTURE):
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["environment"], {name: {f: decode(e) for f, e in case.items()}
                                 for name, case in data["cases"].items()}
