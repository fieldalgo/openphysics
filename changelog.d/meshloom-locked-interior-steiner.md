# Changed

## English

- `meshloom`: **locked facets keep their triangles even when boundary recovery needs points on them.** With `locked_facets`, recovery may put points on a locked facet or its edges. `mesh_plc` and `generate3d` raised `RecoveryError` there; now they move each such point into the domain. The fans of facet triangles around the point are triangulated again without it, and the space around it is refilled from a new point inside, or the point is collapsed onto a neighbour on its segment. Every new tetrahedron has exact `orient3d` > 0. A closed triangle surface (STL-like) can now be meshed with its triangles kept, as Gmsh does: on the V14 benchmark surfaces C1–C6 this works at all sizes. On the 15° wedge C7 it still raises `RecoveryError`. Meshes that need no point moved are unchanged. `stats` counts the moved points (`locked_points_moved`, `locked_interior_points`, `locked_cells`, `locked_collapsed`). [meshloom limits](docs/packages/meshloom/overview.md#limits).

## 한국어

- `meshloom`: **경계 복원이 잠긴 facet 위에 점을 넣어야 할 때도 그 삼각형이 그대로 남습니다.** `locked_facets`를 주면 복원이 잠긴 facet이나 그 변 위에 점을 넣을 수 있습니다. 전에는 `mesh_plc`와 `generate3d`가 그때 `RecoveryError`를 냈지만, 이제 그 점을 영역 안으로 옮깁니다. 그 점 둘레의 facet 삼각형 부채꼴을 그 점 없이 다시 삼각분할하고, 둘레 공간을 안쪽의 새 점에서 다시 채우거나, 그 점을 선분 위 이웃 점으로 접습니다. 새 사면체는 모두 정확 `orient3d` > 0입니다. 닫힌 삼각형 표면(STL 같은 입력)을 Gmsh처럼 삼각형을 그대로 둔 채 메시로 만들 수 있습니다. V14 벤치마크 표면 C1–C6에서는 모든 크기에서 됩니다. 15° 쐐기 C7에서는 여전히 `RecoveryError`를 냅니다. 옮길 점이 없는 메시는 그대로입니다. `stats`가 옮긴 점을 셉니다(`locked_points_moved`, `locked_interior_points`, `locked_cells`, `locked_collapsed`). [meshloom 한계](packages/meshloom/overview.md#한계).
