# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""simcase — the model document and its headless runner.

    from simcase import Document, run
    doc = Document.load("model.json")     # geometry, materials, physics, mesh, study
    result = run(doc)                     # meshine -> physmat -> galerkin
    result.neff, result.group_index()
    result.save("out/")                   # summary.json, fields.npz, results.png

    $ python -m simcase example soi_strip > model.json
    $ python -m simcase run model.json

The document is the contract between users, scripts and the optional studio: a
GUI edits this file; the engine runs it.

``run`` is a composition of stages that are public in their own right, so a GUI
can mesh without solving and a caching layer can redo only what changed:

    model = build_mesh(doc)               # geometry -> mesh -> materials
    parameter, values = study_points(doc)
    result = solve_point(model, doc.sole_physics()[1])
"""

from . import examples
from .geometry import build_domain
from .fields import VectorField
from .runner import MeshedModel, RunResult, build_mesh, run, solve_point, study_points
from .schema import FORMAT, Document, DocumentError
from .units import unit_vocabulary

__version__ = "0.1.0"
__all__ = ["Document", "DocumentError", "FORMAT", "examples", "__version__",
           "build_domain", "build_mesh", "MeshedModel", "study_points", "solve_point",
           "run", "RunResult", "VectorField", "unit_vocabulary"]
