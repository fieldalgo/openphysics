# Changed

## English

- meshloom: **boundary recovery's facet triangulations and facet recovery no longer scan everything on each step.**
  - A facet's constrained Delaunay triangulation now finds each point's cavity by a walk and a search over triangle adjacency, instead of testing every triangle.
  - Facet recovery updates its set of missing subfacets from the faces that change, instead of rebuilding it on every pass.
  - Order and results are unchanged, so meshes are bit-identical.

## 한국어

- meshloom: **경계 복원에서 facet 삼각분할과 facet 복원이 더 이상 단계마다 전체를 훑지 않습니다.**
  - facet의 제약 Delaunay 삼각분할은 이제 모든 삼각형을 검사하지 않고, 삼각형 인접 관계를 따라 걷고 탐색해서 각 점의 공동을 찾습니다.
  - facet 복원은 빠진 subfacet 집합을 pass마다 다시 만들지 않고, 바뀐 면에서만 갱신합니다.
  - 순서와 결과는 그대로라 메시는 비트 단위로 같습니다.
