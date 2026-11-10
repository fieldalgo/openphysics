# Reading version 1 geometry (stage 1)

**English** | [한국어](../../locales/ko/pages/packages/simcase/geometry_reader.md)

[Documentation home](../../README.md)

`simcase.geometry_document` reads the version 1 `geometry` block defined by the
[geometry document contract](geometry_document.md). It is stage 1 of that
contract: it parses, validates and quantizes, and it hands geometry to the
existing builders. The [stage 2 engine](geometry_engine.md) builds the region
complex from what this reader parses.

## In a document

A [format 0.3](document_format.md) document (`"openphysics": "0.3"`) carries
`"version": 1` in its `geometry` block, and each component declares its
`length_unit` (and a `2d` component its `depth`). `Document.from_dict` and
`Document.load` read such a block with `parse`. The document keeps the block as
written (`doc.data`); a 2D region component is read through the accessors
`doc.domain`, `doc.background` and `doc.regions()`, and a homogeneous rectangle
or a box-only 3D component is compiled with `to_v02` to the flat block its kind
reads (`doc.geometry_flat`). The mesh comes from the
[stage 2 engine](geometry_engine.md), which keeps the parsed model
(`doc.geometry_model`). A block without `version` is one of the flat forms of
format 0.3. `parse` refuses a document of another format by name (`E-FORMAT` at
`openphysics`), as `Document.from_dict` does: format 0.2 is not read.

- `doc.geometry_source` holds the version 1 block as written, and `doc.save`,
  `doc.to_dict` and `doc.copy` keep it.
- Each value moved onto the 1 pm grid is a coded diagnostic at its path
  (`I-PM-ROUNDING` for a shift below 10⁻³ pm, `W-PM-ROUNDING` above), and it is
  listed in `model.roundings`.

```python
from simcase.geometry_document import parse, from_v02, layer_stack

model = parse({"openphysics": "0.3", "geometry": {
    "version": 1,
    "parameters": {"w": {"value": "500 nm"}, "t": {"value": "220 nm"}},
    "components": {"xs": {
        "dimension": "2d", "length_unit": "nm", "depth": None,
        "domain": {"xmin": -1500, "xmax": 1500, "ymin": -1200, "ymax": 1200},
        "background": {"material": "SiO2"},
        "features": [{"name": "core", "type": "rect", "x": "-w/2", "y": 0,
                      "w": "w", "h": "t", "material": "Si"}]}}}})
model.components["xs"].features[0].data   # {'x': -250000, 'y': 0, 'w': 500000, 'h': 220000} (pm)
model.roundings                          # [] : every value was already on the 1 pm grid
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
- **Flat blocks.** `from_v02` writes a flat `geometry` block (with its
  `length_unit` and `depth`) as version 1, and `to_v02` compiles a 2D component,
  or a box-only 3D component, back to the flat block (without element sizes). A
  trapezoid becomes the polygon of its exact corners.
- **Layer stacks.** `layer_stack` turns a `layers` feature into the z levels (pm)
  and the region × layer table that `meshine.extrude` takes. A cell is named by its
  explicit `region`, otherwise by its material.

```python
stack = layer_stack(model, "pkg")
mesh = meshine.extrude(footprint, [model.components["pkg"].to_unit(z) for z in stack.levels],
                       stack.table_for(footprint.region_names), size=0.4)
```

## Adapters from sipi and meshine

Two packages write their own geometry as version 1 blocks. They emit plain
dictionaries in format 0.3 and do not depend on simcase; `parse` checks what they
write, with the envelope added. Each component declares its `length_unit` and
`depth` (null, per metre of depth).

```python
from sipi import geometry_v1 as sipi_v1
out = sipi_v1.to_geometry_v1(section)          # a sipi CrossSection, in metres
model = parse({"openphysics": "0.3", "geometry": out["geometry"]})
out["materials"], out["conductors"], out["boundaries"], out["renamed"]

from meshine import geometry_v1 as meshine_v1
out = meshine_v1.to_geometry_v1(domain, length_unit="um")   # a Domain before build()
model = parse({"openphysics": "0.3", "geometry": out["geometry"]})
out["mesh"]        # {"element_size": "0.6 um", "controls": [{"select": ..., "circle_segment_count": 32}]}
```

- **sipi:** one component in metres; layers bottom-up, then local dielectric
  regions, then traces in trace order, so later features win as sipi's own cuts do.
  Each layer and region's material carries `relative_permittivity` and
  `loss_tangent`. A rectangle trace is a
  `rect`, a tapered one a `trapezoid`, a zero-thickness one a `segment` and a
  `PolygonTrace` a `polygon`. A trace whose name a layer or region already uses is
  renamed `<name>-trace` and listed in `renamed`. Derived coordinates (a trace's
  lower-left corner, layer interfaces) are written exactly.
- **meshine:** regions in containment order; a hole that no region fills exactly
  becomes a void feature, and regions inside it still come later. Same-name loops
  merge through `region`. A `Domain` has no unit and no materials, so
  `length_unit` is required, one of `pm nm Angstrom um mm cm m in mil` (another
  declaration, such as `{"in_m": ...}`, is refused naming them), and each region's
  material is its name unless `materials` maps it. A region's own size is its
  feature's `element_size`, the default size is `mesh.element_size` and each
  `Circle`'s vertex count is a `circle_segment_count` control. A boundary-name
  callback cannot be carried over.

`examples/simcase/geometry_v1_soi_strip.json` is the SOI strip example written
with version 1 geometry and parameters; `geometry_v1_imprint_rib.json` is a rib
waveguide whose slab and rib are one silicon, with `finalize: "imprint"`
keeping the etch line and selections naming it and the rib walls.

## What it does not do yet

- Resolve selectors or build the region complex: the
  [stage 2 engine](geometry_engine.md) does that, and it meshes the document.
- Load cylinders, spheres and `extrude` features into a `Document`: their
  kinds read the flat compilation, which has no form for them, so `to_v02`
  refuses them by name. A 2D region component (`path`, merged regions, void,
  `imprint`, `segment` included) stays in the document as written and is read
  through `doc.domain`, `doc.background` and `doc.regions()`; an axisymmetric
  component runs in steady region heat only. A homogeneous rectangle and a
  box-only 3D component are compiled to the flat block.
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
- The flat geometry blocks of all 51 current simcase documents (the built-in
  examples and `examples/simcase/*.json`) go to version 1 and back unchanged
  (without their element sizes), with no rounding; the version 1 form of each
  cavity document hands the solver the same input, and that of the region heat
  example agrees with its flat original within 2 × 10⁻³ of the temperature rise
  (the engine meshes it, in another vertex order).
- The 1 pm grid, half-to-even rounding, the range limit and the `length_unit`
  declarations.
- Expression kinds, cycles, division by zero and refused tokens.
- The layers form of `examples/meshine/extrude_chip.py` gives the same mesh as the
  direct `extrude` call, node for node.
- Analytic heat flow: a three-layer series stack between two fixed temperatures,
  and a circular via in void, match ΔT·A/Σ(tᵢ/kᵢ) and σ·A·ΔT/L to a relative
  10⁻⁹ (measured about 2 × 10⁻¹⁴). The via's A is the meshed 32-gon, 0.64 % below
  the circle's area.
