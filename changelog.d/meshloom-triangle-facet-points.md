# Changed

## English

- meshloom: **a facet that is one triangle is triangulated with only the points on it.** Before, the PLC check gave a facet every point in its plane inside its bounding box. A point off the triangle cannot change the constrained triangulation inside it, because the triangle's edges are constraints. Fan caps carried hundreds of such points per facet. The triangles are the same, and their order in the output can change. Polygon facets keep the old rule.

## 한국어

- meshloom: **삼각형 하나인 facet은 그 위의 점만으로 삼각분할합니다.** 전에는 PLC 검사가 facet에 경계 상자 안의, 같은 평면 위의 점을 모두 주었습니다. 삼각형 변이 제약이므로, 삼각형 밖의 점은 안쪽 제약 삼각분할을 바꿀 수 없습니다. 부채꼴 뚜껑에서는 facet마다 이런 점이 수백 개 붙었습니다. 삼각형은 같고, 출력에서의 순서는 바뀔 수 있습니다. 다각형 facet은 예전 규칙을 따릅니다.
