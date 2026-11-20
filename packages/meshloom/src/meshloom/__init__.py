# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""meshloom — tetrahedral meshing with an exact-arithmetic compiled kernel.

``generate3d`` meshes a piecewise-linear complex (closed polyhedral surfaces, several
regions, tagged facets): boundary recovery, constrained Delaunay refinement to a size
and a radius-edge bound, regions, one rounding to doubles and certification. Its output
follows the tetrahedral mesh fields that ``galerkin.from_mesher`` reads. The acceptance
criteria it is graded by are fixed in OpenPhysics's pre-registered 3D validation plan.
The building blocks (exact predicates, the Delaunay kernel, boundary recovery) are in
``meshloom._core``.
"""

__version__ = "0.0.2"

try:
    from . import _kernel
except ImportError as exc:  # no wheel for this platform, or a source tree without a build
    _kernel = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


class KernelUnavailable(RuntimeError):
    """The compiled kernel is not installed for this platform."""


def kernel_available() -> bool:
    """True when the compiled kernel loaded."""
    return _kernel is not None


def kernel_version() -> str:
    """Version the compiled kernel was built as; raises ``KernelUnavailable`` without it."""
    if _kernel is None:
        raise KernelUnavailable(f"meshloom's compiled kernel is not available here: {_IMPORT_ERROR}")
    return _kernel.version()


#: radius-edge bound of quality="guaranteed": refinement provably ends with every
#: tetrahedron at most this ratio when no input angle is below 90 degrees (V7)
GUARANTEED_RATIO = 2.0
#: radius-edge bound of quality="practical" (the default): better shaped tetrahedra, with
#: no termination proof; the point cap ends it with RefineError instead of a hang
PRACTICAL_RATIO = 1.4
#: default size factor: a tetrahedron is split when its circumradius exceeds ALPHA * h.
#: Calibrated once (2026-11-20) so that the median edge over h on the unit cube at
#: h = 0.06 matches the plan's baseline (1.245; 1.356 with factor 1), so that "size h"
#: means the same as the baseline's MeshSizeMax (validation3d.md, size convention)
ALPHA = 0.9181


def generate3d(points, facets, segments=None, *, h, domain="regions", region_points=None, facet_tags=None,
               quality="practical", alpha=ALPHA, max_points=0):
    """Tetrahedral mesh of a piecewise-linear complex.

    ``points`` (n x 3) and ``facets`` (each a list of loops of point indices, the first
    loop the outer boundary) describe the input; ``segments`` (m x 2) adds edges. ``h``
    is the target size, one number or (with ``region_points``) a mapping from region
    name to size: a tetrahedron whose circumradius exceeds ``alpha * h`` is split
    (``ALPHA`` by default, calibrated against the plan's baseline).
    ``quality`` bounds the radius-edge ratio, circumradius over shortest edge:
    ``"guaranteed"`` (``GUARANTEED_RATIO``, provably terminating without input angles
    below 90 degrees) or ``"practical"`` (``PRACTICAL_RATIO``). Near input angles below
    60 degrees skinny tetrahedra are left, and counted in ``stats``. ``domain`` and
    ``region_points`` choose the regions as in ``meshloom._core.mesh_plc``.
    ``facet_tags`` names the facets, one string per facet (facets may share a name); the
    default names facet i ``str(i)``.

    Returns the output contract: ``nodes``, ``tetrahedra``, ``regions``,
    ``region_names``, ``boundary_faces`` and ``boundary_nodes`` by facet index (wound
    outward) by facet tag, ``interfaces`` by region pair, ``node_source`` and ``stats``.
    ``galerkin.from_mesher`` reads it directly. Errors are
    typed ``ValueError`` subclasses: ``InvalidPLC`` (with a witness), ``NotClosed``,
    ``RecoveryError``, ``RefineError`` (the point cap ``max_points``, by default derived
    from the size), ``RoundingError``, ``RegionError`` and ``MeshError``.
    """
    if _kernel is None:
        raise KernelUnavailable(f"meshloom's compiled kernel is not available here: {_IMPORT_ERROR}")
    ratios = {"guaranteed": GUARANTEED_RATIO, "practical": PRACTICAL_RATIO}
    if quality not in ratios:
        raise ValueError(f"quality must be 'guaranteed' or 'practical', got {quality!r}")
    if h is None:
        raise ValueError("h is required: a size, or a mapping from region name to size")
    n = len(facets)
    if facet_tags is None:
        tags = [str(i) for i in range(n)]
    else:
        tags = list(facet_tags)
        if len(tags) != n or not all(isinstance(t, str) and t for t in tags):
            raise ValueError(f"facet_tags must be {n} non-empty strings, one per facet")
    from ._core import mesh_plc
    import numpy as np
    m = mesh_plc(points, facets, segments=segments, domain=domain, region_points=region_points, h=h,
                 ratio=ratios[quality], alpha=alpha, max_points=max_points)
    faces = {}
    for i in sorted(m["boundary_faces"]):
        faces.setdefault(tags[i], []).append(m["boundary_faces"][i])
    m["boundary_faces"] = {t: np.concatenate(v) for t, v in faces.items()}
    m["boundary_nodes"] = {t: np.unique(v) for t, v in m["boundary_faces"].items()}
    return m


def __getattr__(name):  # the typed errors, without importing _core at package import
    if name in _ERRORS:
        from . import _core
        return getattr(_core, name)
    raise AttributeError(f"module 'meshloom' has no attribute {name!r}")


_ERRORS = ("InvalidPLC", "MeshError", "NotClosed", "RecoveryError", "RefineError", "RegionError", "RoundingError")

__all__ = ["ALPHA", "GUARANTEED_RATIO", "KernelUnavailable", "PRACTICAL_RATIO", "generate3d", "kernel_available", "kernel_version",
           "__version__", *_ERRORS]
