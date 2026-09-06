# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""simdoc — the model document and its headless runner.

    from simdoc import Document, run
    doc = Document.load("model.json")     # geometry, materials, physics, mesh, study
    result = run(doc)                     # meshine -> physmat -> galerkin
    result.neff, result.group_index()
    result.save("out/")                   # summary.json, fields.npz, results.png

    $ python -m simdoc example soi_strip > model.json
    $ python -m simdoc run model.json

The document is the contract between users, scripts and any future GUI: a
GUI edits this file; the engine runs it.
"""

from . import examples
from .runner import RunResult, run
from .schema import FORMAT, Document, DocumentError

__version__ = "0.1.0"
__all__ = ["Document", "DocumentError", "FORMAT", "run", "RunResult", "examples", "__version__"]
