# Tetrahedral mesh format shared by the 3D solvers

**English** | [한국어](../../locales/ko/pages/packages/galerkin/mesh3d_format.md)

[galerkin overview](overview.md)

The 3D solvers of `galerkin` (`solve_cavity`, `solve_material_cavity`,
`thermal3d.solve_steady_heat_3d`, the P1 and Nédélec assemblies) read one mesh
type, `galerkin.Mesh3D`. Meshes built elsewhere reach it through
`galerkin.from_mesher`, which accepts any object or dict with the fields below.
`gmshio.FemMesh3D` (Gmsh, run as a separate process) and `meshine.TetMesh`
(`meshine.extrude`, pure NumPy) carry exactly these fields; this page is the
normative description of the shape they share. Index arrays are 0-based.

## Fields

| Field | Shape and type | Meaning |
|---|---|---|
| `nodes` | `(N, 3)` float | Coordinates. Units are the caller's; the solvers state theirs (the cavity and heat solvers take metres). |
| `tetrahedra` | `(T, 4)` int | Node ids of each tetrahedron. `Mesh3D` stores them as `tets` and swaps two vertices of any negatively oriented tetrahedron so that every volume is positive; the mesher may already hand over positive orientation (meshine checks it exactly). |
| `regions` | `(T,)` int | Region id of each tetrahedron, an index into `region_names`. |
| `region_names` | `list[str]` | Unique names, one per region id. |
| `boundary_faces` | `{name: (F, 3) int}` | Tagged exterior faces. `Mesh3D` stores them as `tagged_faces`; the method `Mesh3D.boundary_faces()` keeps its older meaning, every exterior face as a sorted, untagged node triple. |
| `boundary_nodes` | `{name: (n,) int}`, optional | Node set of each tag. Derived from the faces when absent; when present it must equal `unique(boundary_faces[name])`. `Mesh3D` stores it as `boundary`, which the 2D-style node-set APIs (`solve_dirichlet`) read. |
| `interfaces` | `{(a, b): (F, 3) int}`, optional | Faces between regions `a < b`, wound from `a` to `b`. Stored on `Mesh3D.interfaces`; not verified by galerkin (meshine's `check` does). |

A `Mesh3D` may also carry node sets alone (`boundary`), as `box_mesh` did before
faces were added and as `galerkin.read_msh` does for a file without surface
physical groups. Everything that selects walls by tag (`solve_cavity`,
`solve_material_cavity`, `thermal3d.dirichlet_from_faces`) needs the faces.

## Rules

`Mesh3D.check()` raises `MeshCheckError` listing every violation; `validate()`
returns the list. `from_mesher` runs `check()` on every mesh that arrives with
faces. The rules are those of meshine's `TetMesh` contract
([meshine overview](../meshine/overview.md#tetrahedral-mesh-contract)):

1. **Regions.** `regions` has one id per tetrahedron and every id lies in
   `[0, len(region_names))`. A negative id is refused with the count: gmshio
   gives `-1` to tetrahedra outside every physical volume, so tag every volume
   in the geometry or drop those tetrahedra. `Mesh3D.by_region` refuses negative
   ids too (a negative index would otherwise silently pick the last region).
2. **Every exterior face is tagged exactly once.** An exterior face is a face of
   exactly one tetrahedron. Untagged exterior faces, faces tagged under two
   names and tagged faces that are not exterior are all reported.
3. **Outward winding.** A tagged face `(a, b, c)` has `(b - a) x (c - a)`
   pointing out of the domain. Equivalently, it is an even permutation of the face
   that `OUTWARD_FACES` reads from its positively oriented tetrahedron.
4. **Node sets agree with faces.** `boundary` has the same tags as the faces and
   each set is the unique node list of its faces.

Edges on a wall are derived from the faces, never from node membership: an edge
joining two wall nodes can cross the interior.

## Producers

| Producer | Regions | Face tags |
|---|---|---|
| `galerkin.box_mesh`, the alternating box of the cavity solvers | `domain` | `x0`, `x1`, `y0`, `y1`, `z0`, `z1` |
| `meshine.extrude(footprint, z, materials)` | the material names given per layer | `z0`, `z1` (bottom, top), the footprint's side names (`left`, `right`, `bottom`, `top` from `box_sides`, or any namer), `void` against left-out cells |
| `gmshio.to_fem3d(generate(geo))` | physical volume names, `-1` outside them (refused) | physical surface names, e.g. `pec` from `geo.box_cavity` |
| `galerkin.read_msh` (3D) | physical volume names when every tetrahedron has one | physical surface names, kept as written |

## Naming the walls

Three schemes coexist in the repository:

- **Role names**, one tag for a whole electromagnetic role: `geo.box_cavity`
  tags all six walls `pec` and the volume `cavity`.
- **`x0 x1 y0 y1 z0 z1`**: `box_mesh`, the box cavity solvers' `WALLS`, and
  `extrude`'s `z0`/`z1`.
- **`xmin xmax ymin ymax zmin zmax`**: the simcase JSON cavity document, which
  maps them onto `x0..z1` before calling the solver.

The mesh-accepting solvers do not enforce a scheme: a tag is any string, and a
problem names its walls by the tags its mesh carries. For meshes you build
yourself, the proposal is `x0..z1` for axis-aligned walls (it is what the box
solvers accept directly and what `extrude` produces for the top and bottom) and a
role or part name (`pec`, `port`, `die_top`) for everything else; `xmin..zmax`
stays a JSON spelling. This is a proposal, not a check.

## Example

```python
from meshine import Domain, box_sides, extrude, generate, rectangle
from galerkin import from_mesher

d = Domain(size=0.1)
d.add_region("cavity", rectangle(0, 0, 1.0, 0.8))
tet = extrude(generate(d, box_sides(0, 1.0, 0, 0.8)), [0.0, 0.3, 0.6],
              {"cavity": ["slab", "air"]}, size=0.1)
mesh = from_mesher(tet)           # runs mesh.check()
mesh.tagged_faces.keys()          # z0, z1, left, right, bottom, top
mesh.by_region({"slab": 2.1, "air": 1.0})
```

The consumers are documented in the [cavity solver](cavity_solver.md#external-meshes),
[material cavity](material_cavity.md#external-meshes) and
[3D steady heat](thermal3d.md) pages.
