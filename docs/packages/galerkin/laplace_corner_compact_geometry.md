# Private compact corner partitions

The internal `_laplace_corner_compact_geometry` helper prepares geometry only.
It exports no public symbols and does not change existing geometry or field
solver controls. It returns the existing immutable `CornerPanelGeometry`.

For each edge, the cubic map is
`t^3 / (t^3 + (1-t)^3)`. The first and last four subdivision intervals are
merged into corner-power panels; the remaining panels have constant power.
Even subdivision counts 10 through 512 leave `count - 6` physical panels per
edge. At 10, 12 and 14 subdivisions this gives 4, 6 and 8 panels. The corner
power remains `pi / (2*pi - interior_angle)`, without changing physical weights.

Count 8 is refused: its opposite-origin power panels would meet directly.
For count at least 10, the corner panels are separated by constant panels.
This topology is useful for separately evaluating more polygon faces within
a field solver's existing panel budget. It does not establish field accuracy.

Convexity, separation, strict interior placement, side clearance, metre units,
8192 total geometry panels and unresolved-length checks retain their existing
contracts. The total budget is checked before partition construction. Field
assemblers retain their smaller, separate limits; no field solver adopts this
helper automatically. Existing public geometry still requires at least 16
subdivisions.

Independent checks use rational cubic nodes, analytic triangle/rectangle
corner powers, edge lengths, signed area and endpoint incidence. They also
check reflection, clockwise inputs, exact binary length scaling and immutable
storage. For the old subdivision range, every descriptor is byte-identical
to the existing public geometry on three quadrilaterals and regular polygons.
This is a geometry qualification, not a circular-conductor, dielectric-interface,
fixed-potential guard, field-convergence or platform qualification.

[Two-ground fields](two-ground.md) ·
[한국어](../../locales/ko/pages/packages/galerkin/laplace_corner_compact_geometry.md)
