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

__version__ = "0.0.2"
__all__ = ["Document", "DocumentError", "FORMAT", "examples", "__version__",
           "build_domain", "build_mesh", "MeshedModel", "study_points", "solve_point",
           "run", "RunResult", "ElectricJouleRunResult", "MechanicsRunResult", "CavityRunResult", "ThermalRunResult", "TransientThermalRunResult", "SubspaceSweepResult", "VectorField", "ModeTrackingError", "ModeSelectionError", "unit_vocabulary",
           "MeshLimitError", "check_mesh_limits", "RegionComplexity", "region_complexity", "has_region_geometry", "void_area_m2",
           "GeometryError", "parse_geometry", "evaluate_geometry"]


_loading = False


def _load_runner() -> None:
    """Import the runner chain, in the order the package always imported it.

    ``import simcase`` alone stays light, so a consumer of a light submodule such as
    ``simcase.geometry_document`` does not pull in scipy, shapely or the solvers.
    The first access to any public name below loads all of them, with the same
    import side effects as before.
    """
    global _loading
    _loading = True
    try:
        _import_runner()
    finally:
        _loading = False


def _import_runner() -> None:
    from .electric_joule import ElectricJouleRunResult
    from .mechanics import MechanicsRunResult
    from .cavity import CavityRunResult
    from .thermal import ThermalRunResult
    from .transient_thermal import TransientThermalRunResult
    from . import examples
    from .geometry import build_domain
    from .mesh_limits import MeshLimitError, check_mesh_limits
    from .complexity import RegionComplexity, region_complexity
    from .thermal_regions import has_region_geometry, void_area_m2
    from .fields import VectorField
    from .runner import MeshedModel, RunResult, build_mesh, run, solve_point, study_points
    from .schema import FORMAT, Document, DocumentError
    from .subspace_result import SubspaceSweepResult
    from .tracking import ModeTrackingError
    from .physics_pml_modes import ModeSelectionError
    from .units import unit_vocabulary
    from .geometry_document import GeometryError, parse as parse_geometry
    from .geometry_engine import evaluate as evaluate_geometry
    names = dict(locals())
    globals().update({k: names[k] for k in __all__ if k != "__version__"})


def __getattr__(name: str):
    if name in __all__ and not _loading:
        _load_runner()
        return globals()[name]
    raise AttributeError(f"module 'simcase' has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(__all__))
