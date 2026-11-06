# Geometry document: stage 0 contract

**English** | [한국어](../../locales/ko/pages/packages/simcase/geometry_document.md)

[Documentation home](../../README.md)

Status: **Accepted on 2026-11-03.** The
[stage 1 reader](geometry_reader.md) reads version 1 geometry blocks in
documents and gives the runners the 0.2 form for validation and recording; the
[stage 2 engine](geometry_engine.md) builds the region complex, selectors and
provenance of 2D and axisymmetric components and meshes version 1 documents
(2026-11-04); the runners do not read the complex itself yet. Repository facts were checked against `main` at `015a6d8`.

How the page is organised:
- Sections marked **frozen** are fixed since the page was accepted. The SHA-256 of
  the accepted page is recorded, and frozen sections now change only through a
  dated amendment listed in [Changes to this page](#changes-to-this-page).
- Keywords marked **reserved** are defined by a later stage. Until then, every
  reader refuses them by name.
- JSON contract (decided 2026-11-03): the envelope stays `"openphysics": "0.2"`,
  and only the `geometry` block carries `"version": 1`. A block without `version`
  is the 0.2 form and keeps working unchanged; no document is migrated. Studio
  projects and sipi JSON keep their own formats for now.

## Purpose and scope

All OpenPhysics physics should refer to one geometry document. Today geometry
is written in several separate ways:
- simcase shapes (`packages/simcase/src/simcase/geometry.py:107-142`)
- a meshine `Domain` built by hand (`packages/meshine/src/meshine/geometry.py:118-208`)
- `meshine.extrude` (`packages/meshine/src/meshine/extrude.py:33-60`)
- gmshio `.geo` text (`packages/gmshio/src/gmshio/geo.py:42-126`)
- sipi cross-sections, conductor-section meshes and power planes
  (`packages/sipi/src/sipi/crosssection.py:175-206`,
  `packages/sipi/src/sipi/conductor_mesh.py:59-164`,
  `packages/sipi/src/sipi/plane.py:181-218`)
- cavity boxes (`packages/simcase/src/simcase/cavity.py:104-145`)
- galerkin structured generators (`packages/galerkin/src/galerkin/mesh.py:81-260`,
  `packages/galerkin/src/galerkin/mesh3d.py:124-161`)
- Studio workspace files (`packages/simcase/src/simcase/studio/static/workspace-project.mjs:21-70`)

This page defines the one geometry block that all of them compile to.

**Frozen since acceptance:**
- the top-level structure;
- units and the fixed 1 pm internal grid;
- length and ratio parameters;
- the 2D, 2.5D and box features;
- the later-wins rule and the optional `imprint` finalize;
- the region complex and its provenance names;
- mesh tags and selectors;
- how physics, materials, mesh controls and studies refer to geometry;
- the mapping of current representations.

**Defined, but with no consumer before a later stage:** `path` and `segment`
in FEM (stage 2); `cylinder` and `sphere` (stage 5).

**Reserved:**
- component and feature keywords: `periodic`, `ellipse`, `rotation`, `axis` values
  other than `"z"`, `offset`, `surface`, layer `below`/`above`;
- parameter kinds `angle` and `count`;
- selector keys `inside`, `kind`, `all`, `except` and `covered_by`;
- 3D `imprint`;
- the mesh fields `node_feature` and `node_param`;
- any persisted form of the region complex.

**Not decided here:**
- the stage 2 exact 2D engine, or any code;
- mesh deformation and adjoints, which belong to galerkin;
- 3D arrangements beyond the box rule;
- periodic boundaries in meshers or galerkin;
- the Wavebit adapter (see the [stage 3 preview](#stage-3-preview-wavebit-not-frozen));
- ECAD and STEP import, curved B-rep and NURBS;
- the Studio editor.

## Where the evaluator lives

The evaluator reads a geometry block, resolves the booleans and builds the region
complex. It lives in simcase and uses pure Python with exact integer and rational
arithmetic. No compiled code is added outside meshloom.

The evaluator must work without shapely. Shapely wheels carry GEOS
(LGPL-2.1), and sipi's browser calculator would ship it to the browser; the
stage 2 exact 2D engine replaces shapely in any case. The evaluator module itself
imports only the standard library and NumPy.

scipy is not restricted. sipi, galerkin and meshine already depend on it
(`packages/sipi/pyproject.toml:26`), and it is BSD-3-Clause. The runner chain
imports shapely (`packages/simcase/src/simcase/geometry.py:18-20`), so `import
simcase` loads that chain only when a public name such as `simcase.Document` is
first used. Importing `simcase.geometry_document` loads neither scipy nor
shapely.

## Top-level structure (frozen)

```json
"units": {"length": "m"},
"geometry": {
  "version": 1,
  "parameters": {"<param>": {"value": <number|expression>, "kind": "length" | "ratio", "range": [lo, hi]}},
  "components": {
    "<component>": {
      "dimension": "2d" | "axisymmetric" | "3d",
      "domain": {...},
      "background": {"material": <name|null>, "mesh_size": <length>},
      "features": [{"id": "...", "name": "...", "type": "...", ...}, ...],
      "finalize": "later_wins" | "imprint",
      "selections": {"<selection>": <selector>},
      "boundary_tags": [{"tag": "<mesh tag>", "select": <selector>}, ...]
    }
  }
}
```

The other envelope keys keep their meaning: `units`, `materials`, `physics`,
`mesh` and `study` (`packages/simcase/src/simcase/schema.py:51-69`). A `geometry`
block without `version` is the 0.2 form, and an adapter reads it (see the
[mapping](#mapping-of-current-representations-frozen)).

### Version

`version` is an integer. It belongs to the geometry block and does not replace
the envelope's `openphysics` string. The envelope stays `"0.2"` and moves only
when a change breaks compatibility.

### Units

Geometry numbers are in the document's `units.length`.

**Declared unit required.** A document with a version 1 geometry block must
declare `units.length`. An undeclared length is refused. `units.resolve` treats
an absent dimension as SI (`packages/simcase/src/simcase/units.py:103-104`), but
every kind that reads geometry already refuses an undeclared length:
- `em.modes2d`: `packages/simcase/src/simcase/schema.py:55,333-341`
- `thermal.steady2d`: `packages/simcase/src/simcase/thermal.py:63-65`
- region heat: `packages/simcase/src/simcase/thermal_regions.py:229-231`
- `em.cavity3d`: `packages/simcase/src/simcase/cavity.py:169-170`

**Default for new documents.** New documents written by Studio and the API
declare `"m"`.

**Unchanged rules:**
- The unit symbols and the `{"in_m": x}` escape hatch
  (`packages/simcase/src/simcase/units.py:35-37,124-146`).
- Tagged `[value, "unit"]` pairs are refused
  (`packages/simcase/src/simcase/schema.py:110-118`).

**No angles.** Version 1 has no angle quantities.

### Internal grid: 1 pm (frozen)

Exact geometry works on integers of **1 pm** (10⁻¹² m). The document unit is
chosen separately. The grid is fixed and documents cannot change it.

1. **Reading.** A JSON number is read as the shortest decimal that round-trips
   the parsed double. The unit conversion reads numbers this way today
   (`packages/simcase/src/simcase/units.py:322-325`). So a literal with more than
   17 significant digits is read as its double.
2. **Evaluation.** Expressions are evaluated in exact rational arithmetic.
3. **Scaling.** The result is multiplied by the exact ratio of the document
   length unit to 1 pm. For decimal units (nm, um, mm, m and the others in
   `packages/simcase/src/simcase/units.py:35-37`), an integer value in the
   document unit is an integer number of pm.
4. **Rounding, once.** A result that is not an integer is rounded half-to-even to
   the nearest pm, at reading time only. Each rounding is reported with its JSON
   path, the written value and the displacement. Nothing is rounded again later.

**Defining values** are a feature's own fields after expression evaluation, for
example:
- rect `x, y, w, h`; circle `cx, cy, r`; polygon `points`;
- trapezoid `cx, y, w, w_top, h`;
- box bounds; layer `z0` and thicknesses; domain bounds.

**Derived points are never quantized.** Derived points are points computed from
defining values:
- a rect's far corner `x + w`;
- a trapezoid's corners `cx ± w/2`;
- line and curve intersections;
- the point where a layer interface splits a sloped trapezoid side.

They are kept as exact rationals, or as exact constructions for curve
intersections (stage 2), and they record the provenance of the curves they come
from. Quantizing them would kink straight faces
(`packages/sipi/src/sipi/crosssection.py:294-326`).

**Range.** A coordinate must satisfy |k| < 2⁶³ pm, about 9.2 × 10⁶ m. A component
that exceeds this is refused, and the refusal names the extent.

**What the grid buys.** A touch stays a touch whatever unit the document declares.
Today an 8 × 8 grid of touching rectangles written in metres counts 4 crossings,
while its micrometre copy counts 0
(`packages/simcase/src/simcase/complexity.py:74-80`).

**What the grid does not fix.** The meshers' relative tolerances still apply
after the hand-off: `MERGE_EPS = 1e-9` and `SNAP_EPS = 3e-8` of the bounding-box
diagonal (`packages/meshine/src/meshine/geometry.py:33,57`). A 1 nm feature in a
10 cm domain (ratio 10⁻⁸) is below `SNAP_EPS`. Validation therefore refuses,
before the hand-off, any feature whose size relative to its component's
bounding-box diagonal is below the receiving mesher's tolerance, and names the
feature, its size and the ratio. Nothing disappears silently. Meshing such
multi-scale geometry correctly is a long-term item and is not scheduled in
stages 0–6.

**Hand-off to meshine.** meshine receives micrometre doubles. Each coordinate of
k pm becomes k/10⁶ µm, rounded once. Corners are computed exactly before that
single rounding, so a mesh can differ from today's 0.2 mesh at rounding level.

Example: `examples/simcase/pml_leaky_slab.json` (in µm) has a substrate with
`y = 0.47` and `h = 2.0`. Today its top edge is the floating-point sum 0.47 + 2.0
= 2.4699999999999998 (`packages/simcase/src/simcase/geometry.py:43-44`;
`packages/simcase/src/simcase/runner.py:130-135`). Under this contract it is 2.47.

Bitwise identity with today's meshes is not an acceptance criterion. Analytic,
independent-reference and stored-value checks must still pass at their current
thresholds.

**Hand-off to meshloom (a proposal for the meshloom 3D work, not decided here).**
meshloom would receive integer pm counts as doubles (exact for |k| ≤ 2⁵³, about
9 km) together with a separate scale. Whatever form is chosen, the output
guarantees in `docs/packages/meshine/validation3d.md:44` must hold on the
coordinates galerkin finally receives. That includes exact `orient3d > 0` on the
output doubles.

### Parameters (frozen)

`parameters` maps a name to `{"value": <number | expression>, "kind": ..., "range": [lo, hi]}`.

- **Names** match `^[A-Za-z_][A-Za-z0-9_]*$`.
- **Kinds.** `kind` is `length` (the default, in the document length unit) or
  `ratio` (dimensionless). The kinds `angle` and `count` are reserved.
- **Expressions** may use decimal literals, parameter names, `+ - * /`, unary
  minus and parentheses. Nothing else is allowed: no `min`, `max`, `sqrt` or
  trigonometry. Expressions are evaluated in exact rational arithmetic.
- **Kind rules:**
  - `+` and `-` need operands of the same kind;
  - length × ratio is a length;
  - length ÷ length is a ratio;
  - length × length is refused;
  - dividing by a length is refused unless the dividend is a length;
  - a decimal literal has no kind of its own: in `+` and `-` it takes the other
    operand's kind, and in `×` and `÷` it is a ratio. So `-w/2` and `t + 100` are
    lengths when `w` and `t` are.
- **Errors.** A cycle or a division by zero is an error that names the parameter.
- **Range.** The optional `range` bounds the parameter. Sweeps and derivatives use
  it, and so does a consumer that needs a static bounding box.

Any numeric geometry field may be an expression. That includes domain bounds,
feature fields, layer thicknesses, `mesh_size` and `mesh.controls`. Physics
fields are not geometry, and this page does not give them expressions.

### Components (frozen)

A component is one geometric model with one dimension.

- **`2d`**: x–y coordinates. `domain` is `{xmin, xmax, ymin, ymax}`, and it is the
  clip box, as today (`packages/simcase/src/simcase/geometry.py:110-111`).
- **`axisymmetric`**: the same 2D features read as (r, z).
  - `xmin ≥ 0` is required, and features that reach r < 0 are refused.
  - The domain side at r = 0 is named `axis` only when `xmin == 0`. Otherwise it
    is `left`.
  - `main` at `015a6d8` has no axisymmetric runner. Branch
    `codex/axisymmetric-thermal-lens` at `2c58b05` was not checked. When it lands,
    its tag names are aligned with this rule.
- **`3d`**: `domain` is `{xmin, xmax, ymin, ymax, zmin, zmax}`, as in the cavity
  (`packages/simcase/src/simcase/cavity.py:104-145`).

**`background`** is the region that fills the rest of the domain. It is named
`background`, and that name stays reserved
(`packages/simcase/src/simcase/geometry.py:133-136`;
`packages/simcase/src/simcase/schema.py:283-284`). Its `material` has three
forms:
- a material name;
- `null`: the rest of the domain is void. It is not meshed, and its border is
  exterior boundary.
- **no `material` key**: the background is a homogeneous body whose properties
  the physics supplies. This form is allowed only in a component without
  features, and only for physics kinds that take homogeneous properties. Those are
  today's rectangle documents, where for example `thermal.steady2d` requires
  `materials == {}` (`packages/simcase/src/simcase/thermal.py:93-94`).

**Naming the component.** A physics entry names its component with
`"component": "<name>"`. The key may be left out when exactly one component is
not used as a footprint.

`periodic` is reserved.

### Features (frozen)

`features` is an ordered list, and the order is semantic: later features win (see
the [boolean rule](#boolean-rule-frozen)). Each feature has these fields:

**`name`** is the region name, a non-empty string, unique among the component's
features.
- It has today's role. Material tables, physics keys and result keys use it
  (`packages/simcase/src/simcase/thermal_regions.py:189-199,405-414`).
- Any string allowed today stays valid, except `background`.
- Writing MSH refuses names that contain a quote or a newline
  (`packages/meshine/src/meshine/mesh3d.py:329-333`). That is a limit of the
  writer, not a document rule.

**`id`** is the identifier used in provenance names and selectors.
- It matches `^[A-Za-z_][A-Za-z0-9_-]{0,63}$` and is unique within the component.
- It defaults to `name` when `name` matches that grammar and is not reserved.
  Otherwise it is required.
- Reserved ids, matched case-insensitively (Studio already compares names that
  way, `packages/simcase/src/simcase/studio/static/workspace-shapes.mjs:58`):
  `background`, `domain`, `exterior`, `outer`, `void`, `axis`, `left`, `right`,
  `bottom`, `top`, `x0`–`z1` and `xmin`–`zmax`.

**`region`** (optional, defaults to `name`) puts several features into one
region. meshine and gmshio already merge pieces with the same name
(`packages/meshine/src/meshine/refine.py:691-696`;
`packages/gmshio/src/gmshio/geo.py:113-115`). Two cases are refused:
- a merge of features whose materials differ;
- a `region` value equal to the `name` of a feature outside that region.

**`material`** is a material name, or `null` for void.

**`mesh_size`** is optional and keeps its current meaning.

**Sub-names.** Every name that becomes a provenance part follows the part grammar
`[A-Za-z0-9_-]+`. That covers layer names, polygon `edges`, path segment names
and footprint parts.

### Finalize (frozen)

`finalize` chooses how evaluation treats boundaries that a later feature covers.

| Mode | Regions and materials | Covered boundaries |
|---|---|---|
| `later_wins` (default) | as today | removed |
| `imprint` (2D) | as today: the material still comes from the latest covering feature | kept as internal curves that carry provenance |

`imprint` is the optional mode that preserves interfaces. It is not a union: it
never merges regions and never changes a material.

**Realization.** `imprint` needs the region complex, so it arrives with the stage 2
engine. The stage 1 reader parses the keyword, and its compiler to the 0.2 builder
refuses it by name, since that builder removes covered boundaries. The engine will split a region into
pieces that share its region name. meshine merges such pieces and keeps the shared
segment as a constraint, but it does not report it as an interface
(`packages/meshine/src/meshine/refine.py:690-707`), so the engine lists these
curves in the new `provenance_edges` field (see [Mesh tags](#mesh-tags-frozen)).

3D `imprint` is reserved.

## Feature vocabulary (frozen unless marked)

Each feature type fixes its fields and its **parts**. A part is a named piece of
the feature's boundary, and provenance names are built from parts.

### 2D and axisymmetric

| `type` | Fields | Parts | Consumers |
|---|---|---|---|
| `rect` | `x, y, w, h` (lower-left corner and size; `w, h > 0`) | `left, right, bottom, top` | all 2D |
| `circle` | `cx, cy, r` | `boundary` | all 2D |
| `polygon` | `points` (≥ 3, implicitly closed, simple); optional `edges` (one part name per edge) | `e1..eN` (the edge from point i to point i+1), or the `edges` names | all 2D |
| `trapezoid` | `cx` (centre), `y` (bottom), `w` (bottom width), `h > 0`; optional `w_top` (default `w`) | `bottom, top, left, right` | sipi adapter; FEM 2D |
| `segment` | `points` (an open polyline); no `material` | `line` | sipi adapter now; FEM from stage 2 |
| `path` | `start: [x, y]`, `segments: [{"line": [x, y]} \| {"arc": {"center": [cx, cy], "to": [x, y], "ccw": bool}}]`, closed back to `start`; optional `name` per segment | `s1..sN`, or the segment names | none before stage 2 |

Rules:
- **`rect` and `trapezoid` stay distinct kinds from `polygon`.** No adapter turns
  them into polygons.
- **`segment` has no area.** It is a codimension-1 curve imprinted into the
  region that contains it, as sipi's zero-thickness strips are
  (`packages/sipi/src/sipi/crosssection.py:314-320,348-352`). A later area feature
  removes the part of it that it covers. meshine `Domain` takes only region loops
  (`packages/meshine/src/meshine/geometry.py:118-121`), so FEM accepts `segment`
  from stage 2.
- **Arcs in a `path`.** The radius is the distance from the current point to
  `center`. The end point is where the circle meets the ray from `center` through
  `to`. That end point is a derived point, equal to `to` when `to` lies on the
  circle. An arc of zero length, or one whose `to` equals `center`, is refused.

### 2.5D (inside a `3d` component)

| `type` | Fields | Parts |
|---|---|---|
| `extrude` | `profile` (one inline 2D feature without `id`), `zmin, zmax`; `axis: "z"` | `bottom, top`; the sides take the profile's part names (`pad.left`, `via.boundary`) |
| `layers` | `z0` (base); `layers: [{name, thickness, material \| footprint + map, region?}]` | see below |

Rules for `layers`:
- **Slab layer.** A layer with `material` and no `footprint` is a slab across the
  domain's x–y extent.
- **Footprint layer.** A layer with `footprint` names a 2D component. That
  component's domain x–y extent must equal this component's.
- **`map`.** `map` sends each footprint region name to a material name, to `null`
  (void), or to `{"material": ..., "region": ...}`. Without `map`, the footprint
  regions keep their own materials. This is the table `meshine.extrude` takes,
  with callables written out as entries
  (`packages/meshine/src/meshine/extrude.py:13-18,36-41`).
- **Region name of a layer cell.** It is the explicit `region` if one is given,
  otherwise the material name. That is `meshine.extrude`'s rule. Two footprint
  regions mapped to the same material therefore merge, as today. Give them a
  `region` to keep them apart.
- **z levels** are cumulative exact sums of the thicknesses. They are affine in
  the thicknesses, as in the extruder.
- **Provenance names:**
  - layer cells: `<id>.<layer>`;
  - horizontal faces: `<id>.<layer>.bottom` and `<id>.<layer>.top`;
  - side faces: `<id>.<layer>.<footprint feature id>.<part>`, or
    `<id>.<layer>.domain.<side>` on the footprint's domain sides.
- `below` and `above` (half-space media) are reserved.

### 3D

| `type` | Fields | Parts | Consumers |
|---|---|---|---|
| `box` | `xmin, xmax, ymin, ymax, zmin, zmax` (the cavity form) | `x0, x1, y0, y1, z0, z1` | `em.cavity3d` now; meshloom from stage 5 |
| `cylinder` | `cx, cy, r, zmin, zmax`; `axis: "z"` | `side, bottom, top` | none before stage 5 |
| `sphere` | `cx, cy, cz, r` | `surface` | none before stage 5 |

`docs/packages/meshine/validation3d.md:76-95` lists the pre-registered 3D cases,
which use boxes, cylinders and spheres.

**Proposed compile conditions for stage 5 (not frozen).** These still need
agreement with meshloom's 3D plan:
- Boxes may overlap, and the later box wins.
- A cylinder runs along z. Each cap lies on a layer plane, on a domain z face, or
  inside one region. Where it crosses a box face, the cap lies entirely inside
  that face.
- Spheres touch nothing: they are standalone or strictly nested.
- Anything else goes to gmshio in a separate process, which is new work. Until
  that exists, it is refused, and the refusal names the features.

**Inputs that stay meshloom API inputs.** Raw piecewise-linear complexes, fuzz
inputs and imported surfaces with arbitrary doubles (cases C7, C10, C13 and C14 in
`docs/packages/meshine/validation3d.md:76-95`) are not geometry documents.
Rounding them to a grid would defeat what those cases test.

## Boolean rule (frozen)

The default is today's rule, "later wins"
(`packages/simcase/src/simcase/geometry.py:107-142`):
- **Clipping.** Every feature is clipped to the domain.
- **Regions.** The region of feature i is clip(i) minus the union of clip(j) for
  every later feature j > i.
- **Background.** `background` is the domain minus all features.
- **No merging by material.** Features are never merged because they share a
  material. Two touching features with the same material stay two regions with an
  interface between them. Only `region` merges features.
- **Covered features.** A feature that later features cover completely yields no
  region. What a selection that names it does is set by the
  [selector rules](#selector-rules-frozen).
- **Disjoint pieces.** One region may consist of several disjoint faces, as with a
  MultiPolygon today (`packages/simcase/src/simcase/geometry.py:213-216`).
- **Slivers.** Today's relative rule stays: a piece whose exact area is below
  `AREA_EPS = 1e-12` × the domain area is a sliver
  (`packages/simcase/src/simcase/geometry.py:27-38`). The response depends on the
  physics, as today: a note for EM and a refusal for region heat
  (`packages/simcase/src/simcase/thermal_regions.py:139-157`).
- **3D.** The same rule applies, limited to the stage 5 combinations. The cavity
  keeps its structured-grid centroid rule
  (`packages/galerkin/src/galerkin/material_cavity.py:342-346`) and its
  grid-plane check (`packages/simcase/src/simcase/cavity.py:130-141`). Both are
  mesh and physics checks, not geometry.

When regions overlap, meshine on its own gives the area to the **earlier** region
(`packages/meshine/src/meshine/refine.py:430-436`). Evaluation therefore resolves
booleans before the hand-off and never passes overlapping features to `Domain`.

## Output: the region complex (frozen)

Evaluating a component produces an in-memory region complex. Version 1 has no
persisted format for it. Diagnostic dumps are not a contract.

**Cells** are faces in 2D and volumes in 3D. Each cell has a region name, a
material and the provenance of its feature.

**Curves (2D) and surfaces (3D)** each carry:
- `kind`: `line`, `arc` or `circle` in 2D; `plane`, `cylinder` or `sphere` in 3D;
- exact parameters: end points, centre, radius, axis;
- a **provenance set**: every feature part, domain sides included, whose source
  curve or surface contains the entity. This holds whether or not that feature
  owns an adjacent cell. Example: a via's bottom cap lying on the stack's bottom
  plane carries both `via3.bottom` and `stack.sub.bottom`.
- the cell on each side, or `exterior`.

**Vertices** are grid points or derived constructions.

Provenance grammar:

```text
provenance := id "." part ( "." part )*
id         := a feature id, "domain" or "background"
part       := [A-Za-z0-9_-]+
```

Examples: `via3.side`, `core.top`, `stack.sub.bottom`,
`stack.top.die.left`, `domain.bottom`.

The 2D domain sides are `domain.left`, `domain.right`, `domain.bottom` and
`domain.top`, with `domain.axis` in axisymmetric components. The 3D domain faces
are `domain.x0` to `domain.z1`.

### Mesh tags (frozen)

The shared mesh type does not change: `nodes`, cells, `regions`, `region_names`,
`boundary_edges` / `boundary_faces`, `boundary_nodes` and optional `interfaces`
(`packages/galerkin/src/galerkin/interop.py:55-111`;
`docs/packages/meshine/validation3d.md:38-54`). Every exterior edge or face
carries exactly one tag.

**Default tags** are exactly what each consumer emits today. No existing tag
changes.

| Consumer | Default exterior tags |
|---|---|
| 2D through meshine | `left, right, bottom, top` from `box_sides`; `outer` for any other edge (`packages/meshine/src/meshine/geometry.py:297-318`) |
| axisymmetric | the same, with `axis` replacing `left` when `xmin == 0` |
| 2.5D through `meshine.extrude` | `z0`, `z1`, the footprint's own side tags, and `void` (`packages/meshine/src/meshine/extrude.py:33-60`) |
| `em.cavity3d` | `x0`–`z1`, with `xmin`–`zmax` as aliases (`packages/simcase/src/simcase/cavity.py:46`) |

**`boundary_tags`** is an optional ordered list of `{"tag": ..., "select": <boundary selector>}`.
- An exterior entity takes the tag of the first entry whose selection contains it.
  If no entry contains it, it keeps its default tag.
- A tag may not equal a region name, because gmshio refuses one name used in two
  dimensions (`packages/gmshio/src/gmshio/mesh.py:101-102`).
- A tag may not contain a quote or a newline.

`boundary_tags` reproduces the tags that code reads today:
- the constant `outer` in sipi (`packages/sipi/src/sipi/conductor_mesh.py:157,163`;
  `packages/sipi/src/sipi/crosssection.py:380`) and in galerkin
  (`packages/galerkin/src/galerkin/solver.py:33`);
- the terminal, `outline` and `cutout` tags of a power plane
  (`packages/sipi/src/sipi/plane.py:220-285`);
- `inner` and `outer` of the annulus (`packages/galerkin/src/galerkin/mesh.py:118-148`).

**New optional fields (additive).** `provenance_edges` (2D) and
`provenance_faces` (3D) map each provenance name to the `(E, 2)` / `(F, 3)` mesh
entities that carry it:
- An entity with several provenance names appears under each of them.
- Internal curves kept by `imprint` also appear there.
- Selections resolve against these fields, so a selection can cover part of a
  side tag. Example: a terminal on part of `left`.
- galerkin does not read these fields yet. It also ignores `interfaces`, and in 3D
  it keeps only boundary node sets
  (`packages/galerkin/src/galerkin/interop.py:100-111`). Consumers of the new
  fields wait for that work.

**Unchanged.** Interfaces keep the sorted region-pair key
(`packages/meshine/src/meshine/refine.py:704-707`;
`packages/meshine/src/meshine/mesh3d.py:43-55`).

**Exact circles.** A circle or arc keeps one curve identity: every region that
touches it receives the same `meshine.Circle` object. This replaces two
heuristics, the 5 % area match of holes and the `round(·, 12)` key
(`packages/simcase/src/simcase/geometry.py:187,223-227`). meshine still has only
full circles (`packages/meshine/src/meshine/geometry.py:60-81`), so arcs in the
mesh wait for stage 2.

## Selector rules (frozen)

A selector is `{"region": <expr>}` or `{"boundary": <expr>}`, with an optional
`"optional": true`. An expression is either a string or an object with exactly
one key.

**String resolution** depends on the entity type. A region string never resolves
to a boundary, and a boundary string never resolves to a region.

For `region` strings, in this order:
1. a named selection of region type;
2. a region name;
3. a feature id, which means the regions that feature owns.

When steps 2 and 3 match the same feature (the default `id` = `name`), that
counts as one match. A string that matches different entities is refused.

For `boundary` strings, in this order:
1. a named selection of boundary type;
2. a mesh tag: a default tag from the table above or a declared `boundary_tags`
   tag. It selects exactly the entities that carry that tag.
3. a provenance name (it contains a dot);
4. a feature id, which means every curve or surface whose provenance names that
   feature.

Because of this split, a region named `top`, which is valid in 0.2, does not
clash with the side `top`. Selection names follow the `id` grammar and its
reserved list. They may not equal a region name or a mesh tag.

**Object keys:**

| Key | Meaning |
|---|---|
| `{"feature": "via3"}` | the regions the feature owns; for `boundary`, every entity whose provenance names it |
| `{"provenance": "via3.side"}` | the entities that carry that provenance name |
| `{"material": "Cu"}` | the regions with that material; for `boundary`, their outer boundary |
| `{"between": [A, B]}` | boundary only: entities with a cell of A on one side and a cell of B, or `"exterior"`, on the other |
| `{"of": A}` | boundary only: the boundary of the region set A |
| `{"any": [...]}` | the union of the listed selectors |

The keys `inside`, `kind`, `all`, `except` and `covered_by` are reserved.

**Empty results:**
- **Named selections.** A selection in `selections` or `boundary_tags` that
  resolves to nothing is an error at evaluation, and the error names the
  selection. `"optional": true` turns this off. In a sweep the error belongs to
  the sweep point where it happens.
- **Physics keys** that name a region keep today's behaviour for each kind:
  - validation accepts a shape that later shapes cover completely
    (`packages/simcase/src/simcase/thermal_regions.py:139-146,189-199`);
  - at run time, region heat refuses a heat source on a region that did not
    survive (`packages/simcase/src/simcase/thermal_regions.py:330-336`);
  - EM accepts covered shapes.

**No raw ids.** Selectors never contain node, edge, face, cell or kernel ids. The
polygon edge parts `e1..eN` refer to the author's point order, not to engine
entities.

**Stability.** `feature`, `provenance`, `material`, `between`, `of` and `any`, and
names that resolve to them, keep their meaning under any parameter change that
keeps the topology.

## How the rest of the document refers to geometry (frozen)

**Physics.** Existing keys keep their shape:
- A key that names a side is a boundary string, so `boundary: {left: pec}` still
  validates (`packages/simcase/src/simcase/schema.py:316-318`).
- A key that names a region is a region string, so
  `heat_source_w_m3: {heater: ...}` still validates
  (`packages/simcase/src/simcase/thermal_regions.py:189-199`).
- Other boundary names, such as `heater_top`, are allowed by this contract but
  accepted by no runner yet. Today region heat refuses any tag that is not a side
  (`packages/simcase/src/simcase/thermal_regions.py:285-288`), and EM requires
  exactly the four sides.

**Materials** are assigned per feature through `material`, then resolved through
`materials` and physmat, as today.

**Mesh.** These stay as they are:
- `mesh.size`, `min_angle` and `grading`
  (`packages/simcase/src/simcase/schema.py:351-355`);
- feature `mesh_size`;
- `mesh.subdivisions`, which stays a mesh setting.

A new optional list, `mesh.controls`, holds entries of these forms:
- `{"select": <name>, "size": h}`: a uniform size on the selection;
- `{"select": <name>, "circle_segments": n}`: the circle vertex count. Today it is
  `n = max(16, int(2πr/(size/2)))`
  (`packages/simcase/src/simcase/geometry.py:198`), and `n = 32` for sipi planes
  (`packages/sipi/src/sipi/plane.py:42`).
- `{"select": <name>, "z_divisions": n}`: layer divisions;
- `{"select": <name>, "near": h0, "far": h1, "distance": d}`: a size that grows
  linearly with distance from the selection, the gmshio Threshold field
  (`packages/gmshio/src/gmshio/geo.py:254-258`).

**Studies.** A sweep may name `geometry.parameters.<p>.value`. Runners that build
the mesh once keep refusing this
(`packages/simcase/src/simcase/schema.py:367-371`) until they remesh at each point.

## Parameters, sweeps and derivatives (frozen)

- **Sweeps.** Each sweep point evaluates the geometry again from the parameters.
  The topology may change between points, and any change is reported.
- **Design velocity.** For each length parameter p, evaluation supplies
  V = ∂x/∂p for defining values, derived points and curve parameters. V is taken
  from the exact, unrounded expressions. Moving mesh nodes and adjoints belong to
  galerkin.
- **Topology changes.** A topology change at p refuses the derivative and names
  the features involved. The engine never differentiates silently across a
  topology change. The exact probe (step size and degeneracy test) is defined by
  the stage 4 amendment.

## Consumers

Every consumer refuses what it cannot take, and the refusal names the feature or
keyword.

| Consumer | Takes | Refuses |
|---|---|---|
| FEM 2D (meshine) | `2d` components (and `axisymmetric` once a runner exists); `rect`, `circle`, `polygon`, `trapezoid` | `path` and `segment` until stage 2; reserved keywords |
| [stage 2 engine](geometry_engine.md) (`simcase.geometry_engine`) | `2d` and `axisymmetric` components with every 2D feature, both finalize modes, void and merged regions; its hand-off gives meshine the complex as loops; the runners read such a document through `doc.regions()`, and `mesh.controls` `circle_segments` and `size` reach its hand-off (2026-11-06) | `3d`; a `path` whose boundary meets itself; an arc whose `to` is not on its circle (the end point must be a grid point); at the hand-off, a `segment` curve inside one cell; axisymmetric in every runner, void in the runners (no physics for its border yet) |
| FEM 2.5D (`meshine.extrude`) | `layers`, and `extrude` along z | sloped or curved sidewalls: the extruder makes vertical prisms only (`packages/meshine/src/meshine/extrude.py:4-19`) |
| `em.cavity3d` | `box` with the grid-plane rule | other 3D features |
| FEM 3D (meshloom, stage 5) | the stage 5 combinations | everything else, until a gmshio route exists |
| sipi | `2d` components through its adapter, which keeps sipi's overlap refusals (`packages/sipi/src/sipi/crosssection.py:216-239`) | — |
| Wavebit RCWA and FDTD | defined by the stage 3 amendment | — |

## Examples

### A 2D thermo-optic cross-section with parameters and selections

```json
{
  "openphysics": "0.2",
  "name": "Heated SOI strip",
  "units": {"length": "nm", "temperature": "K"},
  "geometry": {
    "version": 1,
    "parameters": {"w": {"value": 500}, "t": {"value": 220}, "gap": {"value": 1000, "range": [500, 2000]}},
    "components": {
      "xs": {
        "dimension": "2d",
        "domain": {"xmin": -3000, "xmax": 3000, "ymin": -2000, "ymax": 3000},
        "background": {"material": "SiO2"},
        "features": [
          {"name": "core", "type": "rect", "x": "-w/2", "y": 0, "w": "w", "h": "t", "material": "Si", "mesh_size": 20},
          {"name": "heater", "type": "rect", "x": -1000, "y": "t + gap", "w": 2000, "h": 100, "material": "heater_metal"}
        ],
        "finalize": "later_wins",
        "selections": {
          "heater_top": {"boundary": "heater.top"},
          "core_wall": {"boundary": {"between": ["core", "background"]}}
        }
      }
    }
  }
}
```

The `physics`, `materials` and `mesh` blocks are left out and work as today.
`dirichlet_temperature_k: {"bottom": 300}` resolves `bottom` as a mesh tag, and
`heat_source_w_m3: {"heater": 1e15}` resolves `heater` as a region. A sweep point
with `w = 501` gives `x = -250.5` nm, which is −250500 pm and lies on the grid.

### A sipi microstrip with a tapered trace

The box is 4 mm wide, h = 0.2 mm, the copper is 35 µm thick, and the document
unit is `m`:

```json
"features": [
  {"name": "substrate", "type": "rect", "x": -0.002, "y": 0, "w": 0.004, "h": 0.0002, "material": "substrate"},
  {"name": "air", "type": "rect", "x": -0.002, "y": 0.0002, "w": 0.004, "h": 0.002035, "material": "air"},
  {"name": "signal", "type": "trapezoid", "cx": 0, "y": 0.0002, "w": 0.0003, "w_top": 0.00028, "h": 0.000035, "material": "conductor"}
],
"boundary_tags": [{"tag": "outer", "select": {"boundary": {"between": [{"any": ["substrate", "air"]}, "exterior"]}}}]
```

How it maps from sipi:
- **Materials.** The layers' `eps_r` and `tan_delta` become `materials` entries
  named `substrate` and `air`.
- **Physics** names the conductors:
  `"conductors": {"signals": ["signal"], "reference": {"boundary": "bottom"}}`.
- **Order.** The layers come first, bottom-up, and the traces come after them.
  That reproduces sipi's rule that a conductor cuts the dielectric
  (`packages/sipi/src/sipi/crosssection.py:294-326,354-368`).
- **Two meshing roles.** The electrostatic consumer meshes only regions that are
  not conductors, so conductors are holes, as today. The conductor-section
  consumer meshes them as metal
  (`packages/sipi/src/sipi/conductor_mesh.py:59-164`).

### A 2.5D package stack with a via

```json
"components": {
  "plan": {"dimension": "2d", "domain": {"xmin": 0, "xmax": 10000, "ymin": 0, "ymax": 10000},
           "background": {"material": "mold"},
           "features": [
             {"name": "die", "type": "rect", "x": 3000, "y": 3000, "w": 4000, "h": 4000, "material": "Si"},
             {"name": "via3", "type": "circle", "cx": 1500, "cy": 1500, "r": 150, "material": "Cu"}]},
  "pkg": {"dimension": "3d", "domain": {"xmin": 0, "xmax": 10000, "ymin": 0, "ymax": 10000, "zmin": 0, "zmax": 2500},
          "background": {"material": null},
          "features": [
            {"name": "stack", "type": "layers", "z0": 0, "layers": [
              {"name": "sub", "thickness": 1000, "footprint": "plan", "map": {"die": "FR4", "via3": "Cu", "background": "FR4"}},
              {"name": "top", "thickness": 1500, "footprint": "plan", "map": {"die": "Si", "via3": "mold", "background": "mold"}}]}
          ],
          "selections": {"via_wall": {"boundary": "stack.sub.via3.boundary"}, "sink": {"boundary": "stack.sub.bottom"}}}
}
```

The layer cells are named `FR4`, `Cu`, `Si` and `mold`, following the extrude
rule. `meshine.extrude` can take this stack today. The default tags are `z0`,
`z1`, the footprint's sides and `void`.

## Mapping of current representations (frozen)

Terms used in the table:
- **LOSS**: information this contract cannot hold.
- **Rename**: a name changes and the change is reported.
- **Rounding**: a value moves onto the 1 pm grid once, with a report.
- **Behaviour**: a validation change that loses no geometry.

| Current representation | Source | Expressed as | Loss and changes |
|---|---|---|---|
| simcase 0.2 `geometry.domain/background/shapes` (`rect`, `circle`, `polygon`, `name`, `material`, `mesh_size`) | `packages/simcase/src/simcase/schema.py:278-292`; `packages/simcase/src/simcase/geometry.py:41-49` | One `2d` component with `finalize: later_wins`. Shapes become features, and `name` stays the region name. `id` = `name` when it fits the grammar and is not reserved, otherwise `s<i>` (list position). Physics keys and result keys are unchanged. | No LOSS. Rounding: values off the 1 pm grid are rounded; none in `examples/simcase` (see the appendix). Behaviour: (1) one validator replaces the weaker EM validator (`packages/simcase/src/simcase/schema.py:278-292`) and the region-heat one (`packages/simcase/src/simcase/thermal_regions.py:44-75`), so EM documents with self-intersecting polygons or non-finite numbers are refused; (2) corners are exact and then rounded once, so meshes differ from today at rounding level |
| Isolated exact circle; hole heuristic | `packages/simcase/src/simcase/geometry.py:71-104,216-229` | `circle` kind in the complex, with one shared curve identity | None. The heuristic is removed. |
| Occluded circle (128-gon) | `packages/simcase/src/simcase/geometry.py:46` | `circle`; after booleans, the arcs come with stage 2 | None in the document. Until stage 2 the mesh still uses the polygon. |
| MultiPolygon region; sliver rules | `packages/simcase/src/simcase/geometry.py:27-38,213-216` | One region with several faces; the same `AREA_EPS` rule | None |
| Rectangle documents (thermal, electric, Joule, uniform transient) | `packages/simcase/src/simcase/thermal.py:80-99`; `packages/simcase/src/simcase/steady_boundary_contract.py:59-71`; `packages/simcase/src/simcase/electric_joule.py:27-37` | A `2d` component with a domain, no features and a background without a `material` key. `mesh.subdivisions` stays in `mesh`. | None. A 0.2 document keeps today's dispatch by key presence (`packages/simcase/src/simcase/thermal_regions.py:30-36`); in version 1 the background without a `material` key marks the homogeneous body. |
| `em.cavity3d` boxes and wall keys | `packages/simcase/src/simcase/cavity.py:46,104-145` | A `3d` component with `box` features and later-wins. Default tags are `x0`–`z1`, with the `xmin`–`zmax` aliases. The grid-plane and centroid rules stay mesh checks. | Rename: a box named `background` (legal today, `packages/simcase/src/simcase/cavity.py:121-124`) is renamed. Gain: box names now reach the region complex (today only bounds and material reach the solver, `packages/simcase/src/simcase/cavity.py:400-406`). |
| PML thickness, bend, grading centre | `packages/simcase/src/simcase/pml_contract.py:18-41`; `packages/simcase/src/simcase/schema.py:351-355` | Unchanged physics and mesh fields | None |
| Region complexity guard; Studio limits | `packages/simcase/src/simcase/complexity.py:46-93`; `packages/simcase/src/simcase/studio/thermal_regions_api.py:47-60` | Unchanged, counted on features | None |
| Classic Studio | `packages/simcase/src/simcase/studio/static/index.html:750` | Edits the document, as now | None |
| Studio workspace project and session v1–v5; capability endpoints | `packages/simcase/src/simcase/studio/static/workspace-project.mjs:21-70`; `packages/simcase/src/simcase/studio/static/workspace-notebook.mjs:9-23`; `packages/simcase/src/simcase/studio/server.py:80-135` | Application formats that compile to geometry v1, with no geometry semantics of their own. Shapes become features: `name` is the display name, and `id` is generated when the name has spaces. The window becomes `domain`. The heat plate becomes a rectangle document. | LOSS for drafts only: shapes with no material (`''`). Rounding: Studio keeps values to 10⁻⁶ nm (`packages/simcase/src/simcase/studio/static/workspace-shapes.mjs:15-16`), and moves skip that tidy step (`packages/simcase/src/simcase/studio/static/workspace-shape-editor.mjs:9-16`). Anything below 1 pm is rounded. These formats stay for now; whether they retire is decided separately, after looking at real user files. |
| Studio optical solver document (`s1..sN`, rects written as polygons) | `packages/simcase/src/simcase/studio/static/workspace-shapes.mjs:91-98` | A 0.2 document, as in row 1 | That document is already lossy compared with the project. The contract is fed from the project, not from it. |
| sipi `CrossSection`: layers, traces (rect, trapezoid, zero thickness), box side flags, ground flag | `packages/sipi/src/sipi/crosssection.py:42-206` | A `2d` component: full-width layer `rect`s bottom-up, then the traces in trace order as `rect`, `trapezoid` or `segment`. `eps_r` and `tan_delta` become `materials` entries named after the layer. Physics gets `conductors` (ordered `signals`, plus a `reference` selection that holds the ground traces and grounded sides). The side flags become physics on side tags. `outer` comes from `boundary_tags`. | No LOSS of geometry. Rename: a layer and a trace with the same name (allowed today, because the lists are checked separately, `packages/sipi/src/sipi/crosssection.py:195-200`) would merge as regions, so one of them is renamed. Rounding: template arithmetic such as `(w+gap)/2` (`packages/sipi/src/sipi/templates.py:65`) gives values like 0.00015000000000000001 m, about 10⁻⁸ pm off the grid. Behaviour: the rectangular path's exact float coincidences (`packages/sipi/src/sipi/crosssection.py:319,348-353`) can change, which the identity test `tests/sipi/test_manufacturing_sections.py:19` would see (open question). Overlap and touch refusals (`packages/sipi/src/sipi/crosssection.py:216-239`) stay in the adapter, so later-wins never resolves a sipi overlap. Selections replace the tolerance-based conductor node pick (`packages/sipi/src/sipi/crosssection.py:389-410`). |
| sipi local dielectric regions and polygon conductors (`DielectricRegion`, `PolygonTrace`, cross-section v3) | `packages/sipi/src/sipi/polygons.py` | `polygon` features: the regions after the layers and before the traces, so a region cuts the layers it lies in and a conductor cuts both. Written by `sipi.geometry_v1.to_geometry_v1`. | None. Rounding: offset mask corners carry floating-point residues of at most 10⁻⁶ pm. |
| sipi JSON `sipi.cross-section/1,/2` and the line and volume wrappers | `packages/sipi/src/sipi/document.py:13-161`; `packages/sipi/src/sipi/line_model.py`; `packages/sipi/src/sipi/volume_line.py` | Application formats that compile to geometry v1. The schema version (/1 or /2) is a property of the sipi format. | None. Template parameters are not stored today. |
| sipi conductor-section mesh (`signal-<i>`, `reference`, `_bottom`/`_top`/`_side`, `ground_thickness`) | `packages/sipi/src/sipi/conductor_mesh.py:59-164` | Built by that consumer from the same geometry plus its mesh options | None. The synthetic names become a mesh detail of that consumer. |
| sipi `PowerPlane`: outline, holes, three kinds of terminal | `packages/sipi/src/sipi/plane.py:42-71,181-286` | The outline is a `polygon` or `circle` with region `copper`. Holes are later features with `material: null`. A whole-loop terminal is `{"boundary": {"feature": <id>}}`. An edge terminal is an `any` of named polygon `edges`. `boundary_tags` reproduces the terminal names, `outline` and `cutout`. Thickness goes to physics, and the circle `n` becomes `circle_segments`. | None. The adapter refuses overlapping holes and holes outside the outline; today they fail at `packages/sipi/src/sipi/plane.py:282-285`. |
| meshine `Domain` built directly (regions tile, same-name merge, `Circle`) | `packages/meshine/src/meshine/geometry.py:104-208` | Features, with `region` for merges. `domain` is the bounding box of all loops and `background` is `null`. `box_sides` gives the default tags, a constant name becomes one `boundary_tags` entry, and per-loop names become per-feature entries. | LOSS: arbitrary coordinate callbacks for `boundary_names`. |
| `meshine.shapes` rib and fiber | `packages/meshine/src/meshine/shapes.py:11-49` | Features; the fiber's `outer` comes from `boundary_tags` | None |
| `meshine.extrude` (region × layer → material or None, z levels, `z0`/`z1`/`void`) | `packages/meshine/src/meshine/extrude.py:33-60` | `layers` with `footprint` and `map`. Callables become tables, divisions become `z_divisions`, and custom `bottom`/`top`/`void` names are mesh options of the extrude consumer. | LOSS: a footprint given only as a ready-made `TriMesh` is not geometry and stays a mesh-level API. |
| gmshio `Geo` polygons; ready-made rib, fiber and box cavity | `packages/gmshio/src/gmshio/geo.py:42-126,227-302` | Features. `pec` is a `boundary_tags` entry covering every box face. The Threshold field becomes a distance-graded `mesh.controls` entry. | LOSS: `raw()` `.geo` text and Gmsh field syntax |
| galerkin structured generators: rectangle, annulus (`inner`/`outer`), disk and layered rectangle (`layer0..`), box (`x0`–`z1`) | `packages/galerkin/src/galerkin/mesh.py:81-260`; `packages/galerkin/src/galerkin/mesh3d.py:124-161` | Domain only; a circle with an inner void circle, tags from `boundary_tags`; nested circles or rects named `layer<i>`; a 3D domain. Structured meshing stays a mesh option. | None |
| meshloom point sets | `packages/meshloom/src/meshloom/_core.py:60-77` | Not geometry | — |
| meshloom builders (planned) and raw-double inputs | `packages/meshloom/src/meshloom/__init__.py:41-46`; `docs/packages/meshine/validation3d.md:76-95` | Builders become stage 5 features | Raw PLC, fuzz and imported-surface inputs stay meshloom API inputs, out of scope. |
| Wavebit RCWA and FDTD scenes | Wavebit API | Stage 3 amendment | Not part of this frozen mapping |

## Appendix: walk of current examples

The walk was made against `main` at `015a6d8`. It checks that every value which
would become a defining value lies on the 1 pm grid in its declared unit, and
that every name maps to an `id` without renaming.

**simcase documents.** The 20 built-in examples (`packages/simcase/src/simcase/examples.py`,
including the thermal and electric examples it registers) and the 25
`examples/simcase/*.json` files: 45 documents, 364 numbers inside their
`geometry` blocks.
- All 45 declare `units.length`.
- All 364 numbers are integer numbers of pm. No rounding is needed.
- No shape name needs a generated `id`.
- One rounding-level corner change is known: `pml_leaky_slab.json` (see the
  [internal grid](#internal-grid-1-pm-frozen)).

**sipi.** Every `CrossSection` and `PowerPlane` built while running `tests/sipi`
was recorded. sipi documents in `docs/packages/sipi` contain no cross-section
JSON, only dielectric documents.
- 778 cross-sections, 75 distinct, with 608 length values in metres. 20 values
  lie off the grid by at most 10⁻⁷ pm. They are floating-point residues of
  template arithmetic, such as a width of `0.0005499999999999999` m, and would be
  rounded once with a report.
- The lower-left `x` of a trace written as `rect` is its centre minus half its
  width. No recorded trace puts that value off the grid other than through the
  same residues. An odd number of pm in width would put it half a pm off.
- No section has a layer and a trace with the same name.
- 8 power planes with 68 values: all on the grid.

**Studio projects.** The repository holds no saved project files. The shapes in
the Studio tests (`tests/simcase/studio_workspace_*.cjs`) are integer nm or
0.5 nm, all on the grid. Names with spaces or markup, such as `Wedge <b>`, take a
generated `id`, as the [mapping](#mapping-of-current-representations-frozen) says.

**meshine, gmshio and galerkin examples.** `examples/meshine/extrude_chip.py`,
`examples/meshine/compare_with_gmsh.py`, `examples/gmshio/hadley_rib_mesh.py`
and the galerkin examples that call `rectangle_mesh`, `annulus_mesh`, `disk_mesh`,
`layered_rectangle_mesh` and `box_mesh` use short decimal values (for example
`rectangle(-5, -5, 5, 5)`, z levels `0, 1, 1.5, 2.5`, slab `0.3`, `0.5e-3`). All
lie on the grid.
- The `rest` region of `extrude_chip.py`, a rectangle with a hole, becomes a
  `rect` feature followed by the later `die_zone` feature. The per-layer material
  lists become `layers` entries with a `map`.
- The rib's tiled `core`, `box` and `clad` loops become features that do not
  overlap, so the boolean rule changes nothing.
- The Threshold field of the gmshio rib becomes one distance-graded
  `mesh.controls` entry on the `core` selection.

**Finding: inputs without a unit.** meshine `Domain`, gmshio `Geo` and the
galerkin generators take bare numbers. Their adapters therefore take the length
unit from the caller and refuse to run without one.

**Adapters.** `sipi.geometry_v1.to_geometry_v1` writes a `CrossSection` and
`meshine.geometry_v1.to_geometry_v1` writes a hand-built `Domain` (with a required
`length_unit`) as version 1 blocks; see the [stage 1 reader](geometry_reader.md).

## Stage 3 preview: Wavebit (not frozen)

This section is not normative. It lists what the stage 3 amendment has to add.
The Wavebit facts behind it were not checked against a Wavebit checkout at a named
commit. The amendment must cite the public Wavebit repository at a specific SHA.

- **Periodic cell:** two lattice vectors, including oblique and hexagonal cells,
  stored exactly. That needs an `(a, b, angle)` form or `√` in expressions.
- **Periodic semantics:** features wrap instead of being clipped, and the lattice
  cell is the fundamental domain.
- **New features:** an `ellipse` kind; free `rotation` together with its angle
  unit; extrusion along x and y; a rotated 3D box.
- **Layers:** z-invariant layers with half-space media (`below` / `above`).
- **Lowering rules:** an extruded circle becomes a cylinder, not a prism.
- **Out of scope:** raster permittivity layers are material data, not geometry.

## Resolved questions (2026-11-02)

1. Features below the meshers' relative tolerances are refused at validation
   with their name, size and ratio. Supporting them is a long-term item.
2. sipi's rectangular-limit identity test stays as it is until the stage 1
   adapter exists. Replacing node identity by a comparison against analytical
   or stored references at the existing tolerances then needs a separate
   decision. Tolerances are not loosened.
3. The evaluator stays in simcase. It must work without shapely; scipy is not
   restricted (see [Where the evaluator lives](#where-the-evaluator-lives)).
4. sipi JSON and Studio projects keep their own formats and are read through
   the stage 1 adapters. Whether they retire is decided separately, after looking
   at real user files. New geometry features land in version 1 first.
5. Wavebit lowering (periodic cells, ellipses, rotation, angles, x/y extrusion)
   is deferred to a stage 3 amendment. The
   [stage 3 preview](#stage-3-preview-wavebit-not-frozen) stays non-normative.

## Open questions

1. Point selectors (a reference node, a probe) are not defined. Which stage adds
   them?

## Changes to this page

Frozen sections change only through dated amendments listed here. Other sections
(the stage 3 preview, the open questions and anything marked "not frozen") are
updated through ordinary pull requests as the stages are built, and the change is
listed here too.

- 2026-11-03: Stated the JSON decision where the page still called it open (the
  envelope stays `"0.2"`; 0.2 rectangle documents keep their dispatch); said that
  Studio and sipi formats stay until user files are reviewed; moved `imprint` to the
  stage 2 engine, the stage 1 compiler refusing it by name.
- 2026-11-03: Added the sipi v3 row (local dielectric regions and polygon
  conductors) to the mapping and named the sipi and meshine adapters.
- 2026-11-03: Accepted. Frozen sections are fixed from this version on.
- 2026-11-04: Status and the consumers table name the stage 2 engine, which
  meshes version 1 documents, and what it refuses (not frozen sections). Frozen text is unchanged: the engine's
  grid-point rule for arc end points is a consumer refusal the contract allows.
