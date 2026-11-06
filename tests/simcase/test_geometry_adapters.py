# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""sipi cross-sections and hand-built meshine Domains written as version 1 geometry.

The adapters live in their own packages and emit plain dictionaries; here the simcase
reader checks them, and shapely (a test reference only) resolves the later-wins rule
so each region's area can be compared with the area its source defines.
"""

import math

import numpy as np
import pytest
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

import meshine.geometry_v1 as meshine_v1
import sipi.geometry_v1 as sipi_v1
from meshine import Circle, Domain, box_sides, rectangle, shapes
from simcase.geometry_document import RESERVED_IDS, GeometryError, parse, to_v02
from sipi import CrossSection, DielectricRegion, Layer, PolygonTrace, Trace, templates
from sipi.polygons import trace_shape


def test_the_adapters_copy_the_reader_s_id_rules():
    assert sipi_v1.RESERVED_IDS == RESERVED_IDS == meshine_v1.RESERVED_IDS
    from simcase.geometry_document import ID_RE
    assert sipi_v1.ID_RE.pattern == ID_RE.pattern == meshine_v1.ID_RE.pattern


def _shape(f, scale, quad_segs=64):
    scale = float(scale)
    d = f.data
    if f.type == "rect":
        x, y, w, h = (d[k] / scale for k in ("x", "y", "w", "h"))
        return box(x, y, x + w, y + h)
    if f.type == "polygon":
        return Polygon([(x / scale, y / scale) for x, y in d["points"]])
    if f.type == "trapezoid":
        cx, y, w, h, wt = (d[k] / scale for k in ("cx", "y", "w", "h", "w_top"))
        return Polygon([(cx - w / 2, y), (cx + w / 2, y), (cx + wt / 2, y + h), (cx - wt / 2, y + h)])
    if f.type == "circle":
        return Point(d["cx"] / scale, d["cy"] / scale).buffer(d["r"] / scale, quad_segs=quad_segs)
    raise AssertionError(f.type)


def later_wins_areas(comp, scale, quad_segs=64):
    """Region areas under the contract's rule, by shapely (reference only)."""
    feats = [f for f in comp.features if f.type != "segment"]
    shapes_ = [_shape(f, scale, quad_segs) for f in feats]
    areas: dict = {}
    for i, f in enumerate(feats):
        piece = shapes_[i].difference(unary_union(shapes_[i + 1:])) if i + 1 < len(feats) else shapes_[i]
        areas[f.region] = areas.get(f.region, 0.0) + piece.area
    return areas


# ----------------------------------------------------------------- sipi

def _polygon_section(mask=True):
    vertices = np.array([[-.35, .8], [.35, .8], [.25, 1.2], [0, 1.2], [0, 1.05], [-.35, 1.05]]) * 1e-3
    region = np.array([[-.6, .7], [.6, .7], [.6, 1.4], [-.6, 1.4]]) * 1e-3
    return CrossSection([Layer("lower", 1e-3, 4, .01), Layer("upper", 1e-3, 2, .02)],
                        [PolygonTrace("signal", vertices)], 4e-3, top="ground",
                        dielectric_regions=[DielectricRegion("mask", region, 3, .03)] if mask else [])


SECTIONS = {
    "microstrip": lambda: templates.microstrip(width=0.3e-3, substrate_height=0.2e-3, eps_r=4.3, thickness=35e-6),
    "microstrip_thin": lambda: templates.microstrip(width=0.3e-3, substrate_height=0.2e-3, eps_r=4.3),
    "stripline": lambda: templates.stripline(width=0.15e-3, plane_spacing=0.5e-3, eps_r=3.66, thickness=18e-6),
    "coupled": lambda: templates.coupled_microstrip(width=0.2e-3, gap=0.15e-3, substrate_height=0.2e-3,
                                                    eps_r=4.3, thickness=35e-6),
    "coplanar": lambda: templates.grounded_coplanar(width=0.3e-3, gap=0.15e-3, ground_width=0.8e-3,
                                                    substrate_height=0.2e-3, eps_r=4.3, thickness=35e-6),
    "masked": lambda: templates.with_surface_mask(
        templates.microstrip(width=0.3e-3, substrate_height=0.2e-3, eps_r=4.3, thickness=35e-6),
        thickness=20e-6, eps_r=3.5),
    "tapered": lambda: CrossSection([Layer("core", 0.2e-3, 4.3), Layer("air", 1e-3, 1.0)],
                                    [Trace("signal", 0.0, 0.3e-3, 0.2e-3, 35e-6, top_width=0.28e-3)], 4e-3),
    "polygon": _polygon_section,
}


def _sipi_reference(cs):
    """Each region's area from sipi's own shapes: metal cuts regions, regions cut layers."""
    metal = [trace_shape(t) for t in cs.traces if isinstance(t, PolygonTrace) or t.thickness > 0]
    metal_union = unary_union(metal) if metal else Polygon()
    regions = [r._shape for r in cs.dielectric_regions]
    region_union = unary_union(regions) if regions else Polygon()
    ref, y = {}, 0.0
    for lay in cs.layers:
        ref[lay.name] = box(-cs.width / 2, y, cs.width / 2, y + lay.thickness).difference(region_union).difference(
            metal_union).area
        y += lay.thickness
    for reg, shape in zip(cs.dielectric_regions, regions):
        ref[reg.name] = shape.difference(metal_union).area
    for t, shape in zip([t for t in cs.traces if isinstance(t, PolygonTrace) or t.thickness > 0], metal):
        ref[t.name] = shape.area
    return ref


@pytest.mark.parametrize("name", sorted(SECTIONS))
def test_a_cross_section_reads_with_the_areas_sipi_defines(name):
    cs = SECTIONS[name]()
    out = sipi_v1.to_geometry_v1(cs)
    model = parse({"units": out["units"], "geometry": out["geometry"]})
    comp = model.components["section"]
    assert all(abs(r.displacement_pm) <= 1e-6 for r in model.roundings)
    assert [f.name for f in comp.features] == ([lay.name for lay in cs.layers]
                                               + [r.name for r in cs.dielectric_regions]
                                               + [out["renamed"].get(t.name, t.name) for t in cs.traces])
    got = later_wins_areas(comp, model.pm_per_unit)
    for region, area in _sipi_reference(cs).items():
        assert got.get(region, 0.0) == pytest.approx(area, rel=1e-12, abs=1e-24), region
    assert out["conductors"]["signals"] == [t.name for t in cs.traces if not t.ground]
    assert set(out["materials"]) >= {lay.name for lay in cs.layers}


def test_a_zero_thickness_trace_is_a_segment_and_a_name_clash_is_renamed():
    cs = CrossSection([Layer("signal", 0.2e-3, 4.3), Layer("air", 1e-3)],
                      [Trace("signal", 0.0, 0.3e-3, 0.2e-3)], 4e-3)
    out = sipi_v1.to_geometry_v1(cs)
    (seg,) = [f for f in out["geometry"]["components"]["section"]["features"] if f.get("type") == "segment"]
    assert seg["name"] == "signal-trace" and out["renamed"] == {"signal": "signal-trace"}
    assert seg["points"] == [[-0.00015, 0.0002], [0.00015, 0.0002]] and "material" not in seg
    parse({"units": out["units"], "geometry": out["geometry"]})


def test_derived_coordinates_are_written_exactly():
    # 0.1e-3 + 0.2e-3 is not 0.3e-3 in doubles; the layer interface must be exact.
    cs = CrossSection([Layer("a", 0.1e-3, 4.3), Layer("b", 0.2e-3, 2.0), Layer("air", 1e-3)],
                      [Trace("signal", 0.0, 0.3e-3, 0.3e-3, 35e-6)], 4e-3)
    out = sipi_v1.to_geometry_v1(cs)
    feats = out["geometry"]["components"]["section"]["features"]
    assert feats[2]["y"] == "0.0003" or feats[2]["y"] == 0.0003
    model = parse({"units": out["units"], "geometry": out["geometry"]})
    assert model.roundings == []
    assert model.components["section"].features[2].data["y"] == 300_000_000


# ----------------------------------------------------------------- meshine

def _loop_area(loop):
    v = loop.vertices() if isinstance(loop, Circle) else np.asarray(loop, dtype=float)
    x, y = v[:, 0], v[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def _domain_reference(d):
    ref: dict = {}
    for name, loops, _ in d._pending:
        ref[name] = ref.get(name, 0.0) + _loop_area(loops[0]) - sum(_loop_area(h) for h in loops[1:])
    return ref


@pytest.mark.parametrize("slab", [0.0, 0.3])
def test_the_rib_domain_reads_with_its_region_areas(slab):
    d, _namer = shapes.rib_waveguide(slab_thickness=slab, size_core=0.1, size_far=0.6)
    out = meshine_v1.to_geometry_v1(d, length_unit="um")
    model = parse({"units": out["units"], "geometry": out["geometry"]})
    assert model.roundings == []
    got = later_wins_areas(model.components["domain"], model.pm_per_unit)
    for region, area in _domain_reference(d).items():
        assert got[region] == pytest.approx(area, rel=1e-12), region
    assert out["mesh_size"] == 0.6


def test_a_footprint_with_a_filled_hole_needs_no_void():
    d = Domain(size=0.8)
    d.add_region("die_zone", rectangle(-2, -2, 2, 2))
    d.add_region("rest", rectangle(-5, -5, 5, 5), holes=[rectangle(-2, -2, 2, 2)])
    out = meshine_v1.to_geometry_v1(d, length_unit="um")
    feats = out["geometry"]["components"]["domain"]["features"]
    assert [f["name"] for f in feats] == ["rest", "die_zone"]
    model = parse({"units": out["units"], "geometry": out["geometry"]})
    assert later_wins_areas(model.components["domain"], model.pm_per_unit) == {"rest": 84.0, "die_zone": 16.0}


def test_an_unfilled_hole_becomes_void_and_regions_inside_it_still_win():
    d = Domain(size=0.5)
    d.add_region("ring", rectangle(0, 0, 10, 10), holes=[rectangle(2, 2, 8, 8)])
    d.add_region("island", rectangle(4, 4, 6, 6))
    out = meshine_v1.to_geometry_v1(d, length_unit="mm")
    feats = out["geometry"]["components"]["domain"]["features"]
    assert [(f["name"], f["material"]) for f in feats] == [("ring", "ring"), ("ring-hole1", None),
                                                            ("island", "island")]
    model = parse({"units": out["units"], "geometry": out["geometry"]})
    got = later_wins_areas(model.components["domain"], model.pm_per_unit)
    assert got["ring"] == 64.0 and got["island"] == 4.0 and got["ring-hole1"] == 32.0
    with pytest.raises(GeometryError, match="void"):
        to_v02(model)


def test_the_fiber_keeps_exact_circles_and_their_vertex_counts():
    d = shapes.circular_fiber(core_radius=1.0, domain_radius=4.0, size_core=0.2)
    out = meshine_v1.to_geometry_v1(d, length_unit="um")
    feats = out["geometry"]["components"]["domain"]["features"]
    assert [(f["name"], f["type"], f["r"]) for f in feats] == [("clad", "circle", 4.0), ("core", "circle", 1.0)]
    assert sorted(c["circle_segments"] for c in out["mesh_controls"]) == [16, 32]
    model = parse({"units": out["units"], "geometry": out["geometry"]})
    got = later_wins_areas(model.components["domain"], model.pm_per_unit, quad_segs=4096)
    assert got["core"] == pytest.approx(math.pi, rel=1e-6)
    assert got["clad"] == pytest.approx(15 * math.pi, rel=1e-6)


def test_same_name_loops_merge_through_region_and_a_unit_is_required():
    d = Domain()
    d.add_region("pad", rectangle(0, 0, 1, 1))
    d.add_region("pad", rectangle(2, 0, 3, 1))
    d.add_region("gap", rectangle(1, 0, 2, 1))
    out = meshine_v1.to_geometry_v1(d, length_unit="um", materials={"pad": "Cu", "gap": "SiO2"})
    feats = out["geometry"]["components"]["domain"]["features"]
    assert [(f["name"], f.get("region"), f["material"]) for f in feats] == [
        ("pad", None, "Cu"), ("pad-2", "pad", "Cu"), ("gap", None, "SiO2")]
    model = parse({"units": out["units"], "geometry": out["geometry"]})
    assert model.components["domain"].region_names == ["pad", "gap"]
    with pytest.raises(ValueError, match="length_unit"):
        meshine_v1.to_geometry_v1(d, length_unit=None)
    with pytest.raises(TypeError):
        meshine_v1.to_geometry_v1(box_sides(0, 1, 0, 1), length_unit="um")


def test_the_domain_order_does_not_depend_on_the_unit():
    def build(s):
        d = Domain(size=0.5 * s)
        d.add_region("ring", rectangle(0, 0, 10 * s, 10 * s), holes=[rectangle(2 * s, 2 * s, 8 * s, 8 * s)])
        d.add_region("island", rectangle(4 * s, 4 * s, 6 * s, 6 * s))
        d.add_region("cap", rectangle(0, 10 * s, 10 * s, 11 * s))
        return meshine_v1.to_geometry_v1(d, length_unit="um" if s == 1 else "m")
    small, large = build(1e-6), build(1.0)
    names = lambda out: [(f["name"], f["material"]) for f in out["geometry"]["components"]["domain"]["features"]]
    assert names(small) == names(large)
