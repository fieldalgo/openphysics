# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Ready-made domains for common electromagnetic benchmark geometries."""

from __future__ import annotations

from .geometry import Circle, Domain, box_sides, rectangle


def rib_waveguide(core_width: float = 3.0, core_thickness: float = 1.0, slab_thickness: float = 0.0,
                  domain_width: float = 18.0, substrate_thickness: float = 10.0,
                  cladding_thickness: float = 3.0, size_core: float = 0.1, size_far: float = 0.5
                  ) -> tuple[Domain, callable]:
    """Hadley (2002) rib waveguide cross-section. Returns (domain, boundary_namer).

    Regions ``core`` (rib + slab), ``box`` (substrate, y<0), ``clad`` (above);
    boundary names left/right/bottom/top.
    """
    w, h, t = core_width / 2, core_thickness, slab_thickness
    W, B, C = domain_width / 2, substrate_thickness, cladding_thickness
    if not 0 <= t < h:
        raise ValueError("slab_thickness must be in [0, core_thickness)")
    d = Domain(size=size_far)
    if t == 0:
        core = [(-w, 0), (w, 0), (w, h), (-w, h)]
        clad = [(-W, 0), (-w, 0), (-w, h), (w, h), (w, 0), (W, 0), (W, C), (-W, C)]
    else:
        core = [(-W, 0), (W, 0), (W, t), (w, t), (w, h), (-w, h), (-w, t), (-W, t)]
        clad = [(-W, t), (-w, t), (-w, h), (w, h), (w, t), (W, t), (W, C), (-W, C)]
    d.add_region("core", core, size=size_core)
    d.add_region("box", rectangle(-W, -B, W, 0), size=size_far)
    d.add_region("clad", clad, size=size_far)
    return d, box_sides(-W, W, -B, C)


def circular_fiber(core_radius: float, domain_radius: float, size_core: float,
                   size_clad: float | None = None, n_core: int = 32) -> Domain:
    """Step-index fiber cross-section: regions ``core`` and ``clad``, boundary ``outer``.
    Both circles are exact: inserted boundary nodes are projected onto them."""
    if not 0 < core_radius < domain_radius:
        raise ValueError("need 0 < core_radius < domain_radius")
    size_clad = 4 * size_core if size_clad is None else size_clad
    core = Circle((0, 0), core_radius, n=n_core)
    outer = Circle((0, 0), domain_radius, n=max(16, n_core // 2))
    d = Domain(size=size_clad)
    d.add_region("core", core, size=size_core)
    d.add_region("clad", outer, holes=[core], size=size_clad)
    return d


def size_graded(size_near: float, size_far: float, dist_max: float, center=(0.0, 0.0)):
    """Radial size function: ``size_near`` at ``center`` growing linearly to ``size_far`` at ``dist_max``."""
    import numpy as np
    cx, cy = center

    def h(x, y):
        r = np.hypot(x - cx, y - cy)
        return size_near + (size_far - size_near) * np.clip(r / dist_max, 0, 1)
    return h
