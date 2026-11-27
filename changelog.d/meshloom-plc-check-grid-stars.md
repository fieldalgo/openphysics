# Changed

## English

- meshloom: **the PLC check's time grows about linearly on large triangle surfaces.**
  - Candidate pairs come from a uniform grid. Pairs of cells that share a vertex are checked in that vertex's star, and a large planar fan is checked at once by the angular order of its rays.
  - Each facet looks up its coplanar points in the grid.
  - Points are checked once, not once per facet.
  - An invalid input is reported with the same witness as before. Results and meshes are unchanged; `pairs_tested` counts fewer pairs.

## 한국어

- meshloom: **큰 삼각형 곡면에서 PLC 검사 시간이 면 수에 거의 비례해 늘어납니다.**
  - 후보 쌍은 균일 격자에서 고릅니다. 꼭짓점을 공유하는 셀 쌍은 그 꼭짓점의 star에서 검사하고, 큰 평면 부채꼴은 반직선의 각 순서로 한 번에 검사합니다.
  - 각 facet은 같은 평면의 점을 격자에서 찾습니다.
  - 점은 facet마다 다시 검사하지 않고 한 번만 검사합니다.
  - 유효하지 않은 입력은 전과 같은 witness로 보고합니다. 결과와 메시는 그대로이고, `pairs_tested`가 세는 쌍은 줄어듭니다.
