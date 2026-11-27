# Changed

## English

- meshloom: **the PLC check is faster on coplanar triangles and fans.**
  - Every vertex star of four or more items uses the planar star check, and every segment star uses the direction sort.
  - Vertex-disjoint triangles are decided by the plane test first.
  - A facet's inner sub-segments are looked up by member pairs.
  - Sub-segment grid cells are computed once.
  - Results and meshes are unchanged. `MESHLOOM_PROFILE` also prints the check's step times.

## 한국어

- meshloom: **같은 평면의 삼각형과 부채꼴에서 PLC 검사가 빨라졌습니다.**
  - 항목이 넷 이상인 꼭짓점 star는 모두 평면 star 검사를 쓰고, 선분 star는 모두 방향 정렬을 씁니다.
  - 꼭짓점을 공유하지 않는 삼각형은 평면 검사로 먼저 판정합니다.
  - facet 안쪽 sub-segment는 구성 꼭짓점 쌍으로 찾습니다.
  - sub-segment의 격자 셀은 한 번만 계산합니다.
  - 결과와 메시는 그대로입니다. `MESHLOOM_PROFILE`이 검사의 단계별 시간도 출력합니다.
