# Reading version 1 geometry (stage 1)

**English** | [한국어](../../locales/ko/pages/packages/simcase/geometry_reader.md)

[Documentation home](../../README.md)

`simcase.geometry_document` reads the version 1 `geometry` block defined by the
[geometry document contract](geometry_document.md). It is stage 1 of that
contract: it parses, validates and quantizes, and it hands geometry to the
existing builders.

## In a document

A document keeps `"openphysics": "0.2"`; only its `geometry` block carries
`"version": 1`. `Document.from_dict` and `Document.load` read such a block with
`parse`, compile it with `to_v02` and give the runners the 0.2 form, so every
runner works unchanged and refuses what it cannot take. A block without
`version` is read as before.

- `doc.data` holds the compiled 0.2 geometry. Results that record the document
  record this form, which is what was calculated.
- `doc.geometry_source` holds the version 1 block as written, and `doc.save`,
  `doc.to_dict` and `doc.copy` keep it.
- Each value moved onto the 1 pm grid is listed in `doc.geometry_roundings` and
  reported in `doc.notes`.

```python
from simcase.geometry_document import parse, to_v02, from_v02, layer_stack

model = parse({"units": {"length": "nm"}, "geometry": {
    "version": 1,
    "parameters": {"w": {"value": 500}, "t": {"value": 220}},
    "components": {"xs": {
        "dimension": "2d",
        "domain": {"xmin": -1500, "xmax": 1500, "ymin": -1200, "ymax": 1200},
        "background": {"material": "SiO2"},
        "features": [{"name": "core", "type": "rect", "x": "-w/2", "y": 0,
                      "w": "w", "h": "t", "material": "Si"}]}}}})
model.components["xs"].features[0].data   # {'x': -250000, 'y': 0, 'w': 500000, 'h': 220000} (pm)
model.roundings                          # [] : every value was already on the 1 pm grid
to_v02(model)                            # the 0.2 geometry block, in nm
```

## What it does

- **Validation.** Names, ids, the reserved ids and keywords, duplicate names,
  region merges with different materials, simple polygons, positive sizes and
  selector syntax. Every refusal is a `GeometryError` that names the JSON path.
- **Expressions.** Parameter values and geometry fields may be expressions with
  `+ - * /`, parentheses, decimal literals and parameter names. They are evaluated
  in exact rational arithmetic with the contract's kind rules.
- **The 1 pm grid.** Every defining value becomes an integer number of pm. A value
  that is not already on the grid is rounded half to even, once, and listed in
  `model.roundings` with its path, the written value and the displacement.
- **Small features.** A feature smaller than the mesher's relative tolerance
  (3 × 10⁻⁸ of the component's bounding-box diagonal) is refused by name instead
  of vanishing in the mesh. Meshing such multi-scale geometry is not supported.
- **0.2 documents.** `from_v02` writes a 0.2 `geometry` block as version 1 and
  `to_v02` compiles a 2D component, or a box-only 3D component, back. The 0.2
  builder still resolves the later-wins booleans with shapely; the exact 2D engine
  of stage 2 replaces it. A trapezoid becomes the polygon of its exact corners.
- **Layer stacks.** `layer_stack` turns a `layers` feature into the z levels (pm)
  and the region × layer table that `meshine.extrude` takes. A cell is named by its
  explicit `region`, otherwise by its material.

```python
stack = layer_stack(model, "pkg")
mesh = meshine.extrude(footprint, [model.to_unit(z) for z in stack.levels],
                       stack.table_for(footprint.region_names), size=0.4)
```

## Adapters from sipi and meshine

Two packages write their own geometry as version 1 blocks. They emit plain
dictionaries and do not depend on simcase; `parse` checks what they write.

```python
from sipi import geometry_v1 as sipi_v1
out = sipi_v1.to_geometry_v1(section)          # a sipi CrossSection, in metres
model = parse({"units": out["units"], "geometry": out["geometry"]})
out["materials"], out["conductors"], out["boundaries"], out["renamed"]

from meshine import geometry_v1 as meshine_v1
out = meshine_v1.to_geometry_v1(domain, length_unit="um")   # a Domain before build()
out["mesh_size"], out["mesh_controls"]         # default size, Circle vertex counts
```

- **sipi:** layers bottom-up, then local dielectric regions, then traces in trace
  order, so later features win as sipi's own cuts do. A rectangle trace is a
  `rect`, a tapered one a `trapezoid`, a zero-thickness one a `segment` and a
  `PolygonTrace` a `polygon`. A trace whose name a layer or region already uses is
  renamed `<name>-trace` and listed in `renamed`. Derived coordinates (a trace's
  lower-left corner, layer interfaces) are written exactly.
- **meshine:** regions in containment order; a hole that no region fills exactly
  becomes a void feature, and regions inside it still come later. Same-name loops
  merge through `region`. A `Domain` has no unit and no materials, so
  `length_unit` is required and each region's material is its name unless
  `materials` maps it. A boundary-name callback cannot be carried over.

`examples/simcase/geometry_v1_soi_strip.json` is the SOI strip example written
with version 1 geometry and parameters.

## What it does not do yet

- Resolve selectors, build the region complex or write provenance names to a mesh
  (they need the stage 2 engine).
- Mesh `path` and `segment` features, merged regions, axisymmetric components,
  cylinders, spheres, `extrude` features, `finalize: "imprint"` and void
  (`material: null`). They are parsed and refused by the compilers with their names.
- Supply design velocities (stage 4).

Importing `simcase.geometry_document` loads neither scipy nor shapely:
`import simcase` loads its runner chain only when a public name such as
`simcase.Document` is first used.

## Checks

`tests/simcase/test_geometry_adapters.py`: eight sipi sections (microstrip,
stripline, coupled, coplanar, surface-masked, tapered, zero-thickness, polygon
conductor with a local region) give each region the area sipi's own shapes define
to a relative 10⁻¹² (measured 4 × 10⁻¹⁶), with roundings only on input residues
(at most 2 × 10⁻⁷ pm); the meshine rib, footprint and hole domains match their loop
areas, and the fiber keeps exact circles. The version 1 SOI strip example loads to
the same `Document.data` as `soi_strip.json`.


`tests/simcase/test_geometry_document.py`:
- All 45 current simcase documents (the built-in examples and
  `examples/simcase/*.json`) go from 0.2 to version 1 and back unchanged, with no
  rounding, and each one written with version 1 geometry loads to the same
  `Document.data`. The region heat example gives identical temperatures.
- The 1 pm grid, half-to-even rounding, the range limit and unit declarations.
- Expression kinds, cycles, division by zero and refused tokens.
- The layers form of `examples/meshine/extrude_chip.py` gives the same mesh as the
  direct `extrude` call, node for node.
- Analytic heat flow: a three-layer series stack between two fixed temperatures,
  and a circular via in void, match ΔT·A/Σ(tᵢ/kᵢ) and σ·A·ΔT/L to a relative
  10⁻⁹ (measured about 2 × 10⁻¹⁴). The via's A is the meshed 32-gon, 0.64 % below
  the circle's area.
