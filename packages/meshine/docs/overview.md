# meshine — a small quality triangle mesher for multi-material planar domains

**English** | [한국어](locales/ko/pages/overview.md)

[English / 한국어 documentation and translation status](https://github.com/fieldalgo/openphysics/blob/develop/docs/README.md)

Constrained Delaunay refinement (Ruppert's algorithm) written in Python on top
of scipy's Delaunay. Describe a cross-section as named material regions —
polygons and circles that tile the domain, holes allowed — and get back a
conforming triangle mesh with a guaranteed minimum angle, per-region size
control, one region id per triangle, and boundary edges grouped by name.

Depends on numpy and scipy only. No external mesher, no GPL code.

```python
from meshine import Domain, Circle, generate, box_sides, rectangle

d = Domain(size=0.3)
d.add_region("core", rectangle(-1, 0, 1, 0.5), size=0.05)
d.add_region("clad", [(-3, -2), (3, -2), (3, 0.5), (1, 0.5), (1, 0), (-1, 0), (-1, 0.5), (-3, 0.5)])
d.add_region("clad", rectangle(-3, 0.5, 3, 2))
mesh = generate(d, box_sides(-3, 3, -2, 2), min_angle=28)

mesh.nodes            # (N, 2)
mesh.triangles        # (T, 3) counter-clockwise
mesh.regions          # (T,) index into mesh.region_names == ["core", "clad"]
mesh.boundary_edges   # {"left": (E, 2), "right": ..., "top": ..., "bottom": ...}
mesh.interfaces       # {("clad", "core"): (E, 2)}  edges between materials
mesh.min_angle(), mesh.quality(), mesh.region_area("core")
```

Shared edges and T-junctions between regions are resolved automatically.
Circles are exact: nodes the refinement inserts on a circular boundary are
projected onto the true circle, so a fiber core really is round.

The mesher is never told what a length is, and there is no absolute length
constant anywhere in the package. Point merging and boundary classification are
a dimensionless fraction of the domain's own bounding-box diagonal, and the
degeneracy test compares a triangle's area to its own edge lengths, so the same
cross-section meshes to the same geometry whether it is written in micrometres
or in kilometres. Triangle counts legally differ a little between scales,
because refinement rounds differently; region areas, the angle bound and the
boundary names do not.

```python
from meshine import shapes
d, namer = shapes.rib_waveguide(slab_thickness=0.3, size_core=0.1, size_far=0.5)   # Hadley 2002
mesh = generate(d, namer, size_fn=shapes.size_graded(0.1, 0.5, dist_max=3.0, center=(0, 0.5)))
mesh = generate(shapes.circular_fiber(core_radius=4.0, domain_radius=20.0, size_core=0.4))

d = Domain(size=0.3)                                  # PEC cylinder in a circular air domain
d.add_region("air", Circle((0, 0), 4.0), holes=[Circle((0, 0), 1.0)])
mesh = generate(d, lambda mid: "pec" if abs(complex(*mid)) < 2 else "abc")
```

## How it works

Each round: triangulate all points (Qhull); split any input segment that is
missing from the triangulation or whose diametral circle contains another
vertex; then, for triangles inside the domain that are too thin (angle below
`min_angle`) or too big (circumradius above `size_factor * h`), insert their
circumcenters — unless a circumcenter would encroach a segment, in which case
that segment is split instead. Repeat until nothing is bad. This is Ruppert's
rule set; it terminates with the requested angle bound for reasonable input
(right-angled geometries up to about 30°). A final Laplacian pass moves
interior nodes only where no incident triangle gets worse.

Points are inserted in batches with a separation filter and the point set is
re-triangulated each round, so the code stays about 300 lines. A 10k-triangle
rib cross-section takes about a second.

## Self-checks

```bash
# From the repository root
python -m pip install pytest -e packages/meshine
python -m pytest -q packages/meshine/tests
```

Checked properties: polygonal region areas reproduced to 1e-9; every triangle
positively oriented; the tagged boundary equals the set of edges used by
exactly one triangle (watertight, no gaps or overlaps); interface edges are
shared by exactly two triangles of the two named materials; the requested
minimum angle holds; edge lengths follow per-region sizes and a size function;
fiber interface nodes lie on the true circle to 1e-12 with second-order area
convergence; holes are left empty; and edge-midpoint quadrature of a smooth
function converges at second order on a deliberately irregular mesh.

Scale is checked separately: the same device written at five length scales
spanning twelve decades gives the same region-area fractions, the same angle
bound and the same boundary names, and each comparison fails as vacuous if its
scale ratio turns out to be 1.0. An empty mesh is refused by `generate` with a
message naming the count that was zero and which of the two causes it was,
rather than returned for a reduction several frames later to trip over.

`examples/compare_with_gmsh.py` draws the same rib waveguide meshed here and
by Gmsh (through the `gmshio` package) side by side. Gmsh's Frontal-Delaunay
still produces higher mean quality (0.98 vs 0.93 radius ratio) and smoother
grading; meshine's guarantee is the angle bound.

## Limits

- 2D only. Tetrahedral meshing is a different problem; use Gmsh via `gmshio` for 3D.
- Input angles below ~60° between segments can prevent reaching high `min_angle` values; lower the bound (Ruppert's proof covers 20.7°).
- Curved boundaries: circles are built in; other curves can be added as polylines (or by adding a `project` method to a loop object).

## License

Apache License 2.0 - see [LICENSE](../LICENSE) and [NOTICE](../NOTICE).

Copyright 2026 Yongha Kim (FieldAlgo)
