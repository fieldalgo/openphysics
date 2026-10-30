# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""meshloom — tetrahedral meshing with an exact-arithmetic compiled kernel.

There is no mesher yet: the compiled kernel has its first stages, exact
predicates and the Delaunay tetrahedralization of point sets, as internal building
blocks in ``meshloom._core``, and ``generate3d`` is not implemented yet. The acceptance criteria
the mesher will be graded by are fixed in OpenPhysics's pre-registered 3D
validation plan. Output follows the tetrahedral mesh fields that
``galerkin.from_mesher`` reads.
"""

__version__ = "0.1.0"

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


def generate3d(*args, **kwargs):
    """Tetrahedral mesh of a piecewise-linear complex (not implemented in this release)."""
    if _kernel is None:
        raise KernelUnavailable(f"meshloom's compiled kernel is not available here: {_IMPORT_ERROR}")
    raise NotImplementedError("meshloom.generate3d is not implemented yet; use meshine.extrude for layered "
                              "geometry or gmshio for other shapes")


__all__ = ["KernelUnavailable", "generate3d", "kernel_available", "kernel_version", "__version__"]
