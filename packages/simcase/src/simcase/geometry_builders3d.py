# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Cylinders and spheres of a 3d component in meshloom's public builder shapes (stage 5, slice 3).

A 3d component whose features exactly match one of ``meshloom.builder``'s configurations, on its
pm values, is meshed by that builder at the document's h and handed to ``meshloom.generate3d``
unchanged; the builder's tags are then renamed to the document's provenance names:

- ``via_in_slab`` (C4): one z-cylinder spanning the whole domain height, strictly inside it in x-y,
  with a non-void background (the slab);
- ``sphere_in_box`` (C5): one sphere strictly inside the domain, non-void background;
- ``sphere`` (C1): one sphere, void background (the domain only bounds it);
- ``nested_spheres`` (C11): concentric spheres listed outermost first (later wins gives the
  shells), void background; the innermost material may be null (a hole).

The contract's fixed stems refuse a cylinder that crosses or touches a domain side, a sphere that
touches or crosses a domain face and two spheres that touch or cross. Every other cylinder or
sphere configuration is refused with the staging message (``E-3D-COMBINATION``). The curved
surfaces are sampled by the builder (ring and geodesic sampling live in meshloom), and each is
reported as ``I-SURFACE-SAMPLED``. The route is experimental, as the rest of stage 5.
"""

from __future__ import annotations

import math
from fractions import Fraction

from .geometry_document import Component, GeometryError

CODE = "E-3D-COMBINATION"
#: the staging message's account of what a 3d component takes (slice 3)
STAGED = ("is not taken yet in a 3d component; boxes and slab layers are, and cylinders and spheres in meshloom's "
          "builder shapes only (one cylinder through the whole slab, one sphere, concentric spheres)")
CURVED = ("cylinder", "sphere")
_SIDES = (("x", 0, "x0"), ("x", 1, "x1"), ("y", 0, "y0"), ("y", 1, "y1"), ("z", 0, "z0"), ("z", 1, "z1"))


def has_curved(comp: Component) -> bool:
    return any(f.type in CURVED for f in comp.features)


def _path(comp: Component, i: int) -> str:
    return f"geometry.components.{comp.name}.features[{i}]"


def _refuse(message: str, path: str):
    raise GeometryError(message, path=path, code=CODE)


def _num(k: int, comp: Component) -> str:
    """A pm value in the component's length unit, as written."""
    v = Fraction(k, comp.pm_per_unit)
    return str(v.numerator) if v.denominator == 1 else f"{float(v):g}"


def _stems(comp: Component) -> None:
    """The contract's fixed cylinder and sphere stems that builder-shaped documents can meet."""
    dom = comp.domain
    spheres = []
    for i, f in enumerate(comp.features):
        d = f.data
        if f.type == "cylinder":
            for axis, end, side in _SIDES[:4]:
                c, bound = d[f"c{axis}"], dom[f"{axis}{'max' if end else 'min'}"]
                gap = (bound - c) if end else (c - bound)        # distance from the axis to the side, inward
                if gap == d["r"]:
                    _refuse(f"cylinder {f.name!r} touches domain.{side} at one line; move it inside or away", _path(comp, i))
                if -d["r"] < gap < d["r"]:
                    z0, z1 = max(d["zmin"], dom["zmin"]), min(d["zmax"], dom["zmax"])
                    _refuse(f"cylinder {f.name!r} crosses the side domain.{side} between z = {_num(z0, comp)} and "
                            f"{_num(z1, comp)} {comp.length_unit}; a cylinder must lie inside or outside every side "
                            "it spans", _path(comp, i))
        elif f.type == "sphere":
            for axis, end, side in _SIDES:
                c, bound = d[f"c{axis}"], dom[f"{axis}{'max' if end else 'min'}"]
                gap = (bound - c) if end else (c - bound)
                if gap <= d["r"]:
                    _refuse(f"sphere {f.name!r} touches or crosses domain.{side}; a sphere lies strictly inside one "
                            "region", _path(comp, i))
            for j, g in spheres:
                e = g.data
                d2 = sum((d[f"c{a}"] - e[f"c{a}"]) ** 2 for a in "xyz")
                disjoint = d2 > (d["r"] + e["r"]) ** 2
                nested = d2 < (d["r"] - e["r"]) ** 2
                if not (disjoint or nested):
                    _refuse(f"spheres {g.name!r} and {f.name!r} touch or cross; they must be disjoint or strictly "
                            "nested", _path(comp, i))
            spheres.append((i, f))


def recognise(comp: Component):
    """The builder shape of a component with cylinders or spheres: ``(shape, curved feature indices)``;
    refuses by name what no builder takes."""
    _stems(comp)
    feats = comp.features
    curved = [i for i, f in enumerate(feats) if f.type in CURVED]
    first = curved[0]
    if len(curved) != len(feats):
        _staged(comp, first)
    bg = comp.background.get("material")
    dom = comp.domain
    if feats[first].type == "cylinder":
        d = feats[first].data
        if (d["zmin"], d["zmax"]) != (dom["zmin"], dom["zmax"]) or bg is None:
            _staged(comp, first)
        if len(curved) > 1:
            _staged(comp, curved[1])
        return "via_in_slab", curved
    # spheres only
    for i in curved[1:]:
        if feats[i].type != "sphere":
            _staged(comp, i)
    if len(curved) == 1:
        return ("sphere" if bg is None else "sphere_in_box"), curved
    if bg is not None:
        _staged(comp, curved[1])
    c0, r = feats[first].data, feats[first].data["r"]
    for i in curved[1:]:
        d = feats[i].data
        if any(d[f"c{a}"] != c0[f"c{a}"] for a in "xyz") or not d["r"] < r:
            _staged(comp, i)
        r = d["r"]
    return "nested_spheres", curved


def _staged(comp: Component, i: int):
    f = comp.features[i]
    _refuse(f"{f.type} {f.name!r} {STAGED}", _path(comp, i))


def _sizes_refused(comp: Component, opts: dict) -> None:
    where = None
    if opts["controls"]:
        where = opts["controls"][0]["path"]
    elif comp.background.get("mesh_size") is not None:
        where = f"geometry.components.{comp.name}.background.element_size"
    else:
        for i, f in enumerate(comp.features):
            if f.mesh_size is not None:
                where = f"{_path(comp, i)}.element_size"
                break
    if where is not None:
        _refuse(f"{where}: a 3d component with a sampled surface takes one mesh.element_size until a later slice",
                where)
    if comp.selections or comp.boundary_tags:
        what = "selections" if comp.selections else "boundary_tags"
        where = f"geometry.components.{comp.name}.{what}"
        _refuse(f"{where}: {what} are not taken yet with a sampled surface", where)
    if opts["size"] is None:
        raise GeometryError("mesh.element_size: give one size", path="mesh.element_size", code="E-KEY-MISSING")


def _m(k) -> float:
    from .geometry_engine3d import _metres
    return _metres(k)


def build(data: dict, comp: Component, opts: dict):
    """Mesh a builder-shaped component: a ``geometry_engine3d.Mesh3DResult`` (``complex`` is None; the
    exact complex of sampled surfaces is not built yet)."""
    import numpy as np
    import meshloom
    from meshloom import builder
    from galerkin.mesh3d import Mesh3D
    from physmat.units import Diagnostic

    from .geometry_engine3d import TETRAHEDRA_PER_VOLUME, Mesh3DError, Mesh3DResult

    shape, curved = recognise(comp)
    _sizes_refused(comp, opts)
    feats, dom = comp.features, comp.domain
    h = _m(opts["size"])
    bg = comp.background.get("material")
    lo = tuple(_m(dom[f"{a}min"]) for a in "xyz")
    hi = tuple(_m(dom[f"{a}max"]) for a in "xyz")
    region = {i: (feats[i].region if feats[i].material is not None else None) for i in curved}
    if shape == "via_in_slab":
        i = curved[0]
        d = feats[i].data
        args = dict(slab=(lo, hi), radius=_m(d["r"]), axis=(_m(d["cx"]), _m(d["cy"])),
                    names=("background", region[i]))
        exterior = {"bottom": ["domain.z0"], "top": ["domain.z1"], "x0": ["domain.x0"], "x1": ["domain.x1"],
                    "y0": ["domain.y0"], "y1": ["domain.y1"], "via_bottom": [f"{feats[i].id}.bottom", "domain.z0"],
                    "via_top": [f"{feats[i].id}.top", "domain.z1"]}
        interior = {("background", region[i]): f"{feats[i].id}.side"}
        surfaces = {i: ("cylinder", f"{feats[i].id}.side", "via_side")}
        volumes = {region[i]: math.pi * _m(d["r"]) ** 2 * (hi[2] - lo[2])}
        volumes["background"] = (hi[0] - lo[0]) * (hi[1] - lo[1]) * (hi[2] - lo[2]) - volumes[region[i]]
    else:
        centre = tuple(_m(feats[curved[0]].data[f"c{a}"]) for a in "xyz")
        if shape == "sphere_in_box":
            i = curved[0]
            args = dict(box=(lo, hi), center=centre, radius=_m(feats[i].data["r"]), names=("background", region[i]))
            exterior = {a: [f"domain.{a}"] for a in ("x0", "x1", "y0", "y1", "z0", "z1")}
            interior = {("background", region[i]): f"{feats[i].id}.surface"}
            surfaces = {i: ("sphere", f"{feats[i].id}.surface", "sphere")}
        elif shape == "sphere":
            i = curved[0]
            if region[i] is None:
                raise GeometryError(f"component {comp.name!r} has nothing to mesh: every cell is void (material null)",
                                    path=f"geometry.components.{comp.name}")
            args = dict(center=centre, radius=_m(feats[i].data["r"]), name=region[i])
            exterior = {"sphere": [f"{feats[i].id}.surface"]}
            interior = {}
            surfaces = {i: ("sphere", f"{feats[i].id}.surface", "sphere")}
        else:
            inner = curved[::-1]                    # innermost first, as the builder takes radii
            radii = tuple(_m(feats[i].data["r"]) for i in inner)
            args = dict(center=centre, radii=radii, names=tuple(region[i] for i in inner))
            surfaces = {i: ("sphere", f"{feats[i].id}.surface", f"sphere{k}") for k, i in enumerate(inner)}
            exterior, interior = {}, {}
            names = [region[i] for i in inner]
            for k, i in enumerate(inner):
                outside = names[k + 1] if k + 1 < len(names) else None
                if names[k] is not None and outside is not None:
                    interior[(names[k], outside)] = f"{feats[i].id}.surface"
                elif names[k] is not None or outside is not None:
                    exterior[f"sphere{k}"] = [f"{feats[i].id}.surface"]
        volumes = {}
        for k, i in enumerate(curved):
            r = _m(feats[i].data["r"])
            inner_r = _m(feats[curved[k + 1]].data["r"]) if shape == "nested_spheres" and k + 1 < len(curved) else 0.0
            if region[i] is not None:
                volumes[region[i]] = 4 * math.pi / 3 * (r ** 3 - inner_r ** 3)
        if shape == "sphere_in_box":
            volumes["background"] = (hi[0] - lo[0]) * (hi[1] - lo[1]) * (hi[2] - lo[2]) - volumes[region[curved[0]]]
    fn = getattr(builder, shape)
    kwargs = fn(h, **args)

    estimate = TETRAHEDRA_PER_VOLUME * sum(v / h ** 3 for v in volumes.values())
    lowt, hight = estimate * 4e-4, estimate * 6e-4
    info = Diagnostic("I-MESH-ESTIMATE", f"geometry.components.{comp.name}",
                      f"about {estimate:.0f} tetrahedra from the element sizes (T = 6.3 sum(V/h^3)); meshing takes "
                      f"about {lowt:.3g}-{hight:.3g} s at 0.4-0.6 ms per tetrahedron")
    if estimate > opts["element_count_limit"]:
        raise GeometryError(f"component {comp.name!r}: about {estimate:.0f} tetrahedra from the element sizes "
                            f"(T = 6.3 sum(V/h^3)); the limit is {opts['element_count_limit']} "
                            "(mesh.element_count_limit)", path="mesh.element_count_limit", code="E-MESH-ESTIMATE")
    try:
        raw = meshloom.generate3d(h=h, max_points=opts["element_count_limit"], **kwargs)
    except (meshloom.KernelUnavailable, ValueError) as exc:
        prov = sorted({p for _, p, _ in surfaces.values()})
        raise Mesh3DError(f"component {comp.name!r}: meshloom {type(exc).__name__}: {exc}; the sampled surfaces are "
                          f"{', '.join(prov)} (builder.{shape})", cause=exc, provenance=prov) from exc

    names = list(raw["region_names"])
    nodes = np.asarray(raw["nodes"], dtype=np.float64)
    tets = np.asarray(raw["tetrahedra"], dtype=np.int64)
    regions = np.asarray(raw["regions"], dtype=np.int64)
    provenance: dict = {}
    tagged: dict = {}
    for tag, faces in raw["boundary_faces"].items():
        faces = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
        parts = exterior[tag]
        for p in parts:
            provenance.setdefault(p, []).append(faces)
        side = next((p.split(".", 1)[1] for p in parts if p.startswith("domain.")), "void")
        tagged.setdefault(side, []).append(faces)
    interfaces = {}
    for (ia, ib), faces in raw["interfaces"].items():
        faces = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
        na, nb = names[ia], names[ib]
        key = tuple(sorted((na, nb)))
        interfaces[key] = faces if key == (na, nb) else faces[:, [0, 2, 1]]
        part = interior.get((na, nb)) or interior.get((nb, na))
        if part is None:
            raise GeometryError(f"internal: meshloom interface {na!r} / {nb!r} matches no sampled surface")
        provenance.setdefault(part, []).append(faces)
    provenance = {p: np.concatenate(v) for p, v in sorted(provenance.items())}
    tagged = {t: np.concatenate(v) for t, v in sorted(tagged.items())}
    mesh = Mesh3D(nodes, tets, regions=regions, region_names=names, tagged_faces=tagged, interfaces=interfaces)
    mesh.provenance_faces = provenance
    result = Mesh3DResult(mesh, None, provenance, {}, {}, [], [], estimate, kwargs, raw)
    result.diagnostics.append(info)
    for i in curved:
        result.diagnostics.append(_sampled(comp, i, surfaces[i], shape, kwargs, provenance, nodes, h))
    return result


def _sampled(comp, i, surface, shape, kwargs, provenance, nodes, h):
    """``I-SURFACE-SAMPLED`` of one curved surface: its exact parameters, the builder and meshloom's
    versions, the sampling read from the builder's points, and the measured V5 deviation of the mesh
    nodes on it against the exact parameters (pm)."""
    import numpy as np
    import meshloom
    from physmat.units import Diagnostic

    kind, part, tag = surface
    f = comp.features[i]
    d = f.data
    pts = np.asarray(kwargs["points"])
    used = sorted({v for fi, t in enumerate(kwargs["facet_tags"]) if t == tag
                   for loop in kwargs["facets"][fi] for v in loop})
    sample = pts[used]
    if kind == "cylinder":
        c = (Fraction(d["cx"], 10 ** 12), Fraction(d["cy"], 10 ** 12))
        geometry = f"centre ({d['cx']}, {d['cy']}) pm, r = {d['r']} pm, z = {d['zmin']} to {d['zmax']} pm"
        zs = sorted(set(sample[:, 2].tolist()))
        m = int(np.sum(sample[:, 2] == zs[0]))
        r = float(Fraction(d["r"], 10 ** 12))
        sampling = (f"m = {m} points per ring, ring z levels {', '.join(f'{z:.6g}' for z in zs)} m; sagitta bound "
                    f"r(1 - cos(pi/m)) = {r * (1 - math.cos(math.pi / m)):.3e} m")
    else:
        c = tuple(Fraction(d[f"c{a}"], 10 ** 12) for a in "xyz")
        geometry = f"centre ({d['cx']}, {d['cy']}, {d['cz']}) pm, r = {d['r']} pm"
        n = round(math.sqrt((len(used) - 2) / 10))
        sampling = f"frequency n = {n} ({len(used)} points)"
    R = Fraction(d["r"], 10 ** 12)
    norm = 2 * R * (Fraction(math.sqrt(float(sum(x * x for x in c)))) + R)
    worst = 0.0
    for v in np.unique(provenance[part]).tolist():
        p = [Fraction(float(x)) for x in nodes[v]]
        d2 = sum((p[k] - c[k]) ** 2 for k in range(len(c)))
        worst = max(worst, float(abs(d2 - R * R) / norm))
    message = (f"{part}: {kind} sampled by meshloom builder.{shape} (meshloom {meshloom.__version__}, kernel "
               f"{meshloom.kernel_version()}); {geometry}; h = {h:g} m; {sampling}; measured V5 deviation "
               f"{worst:.2e}")
    return Diagnostic("I-SURFACE-SAMPLED", _path(comp, i), message)
