# Fixed

## English

- `meshloom`: **a closed triangle surface given as one facet per triangle now meshes when its triangles meet at small angles.** Before, an in-plane fan or a needle triangle at 1° or less, or a vertex within 1e-4 of the diagonal from a non-incident edge, made refinement split without end. It stopped only at the point cap with `RefineError`, or not within minutes. The rules that changed:
  - Refinement no longer splits a skinny subfacet or tetrahedron for quality inside an input angle too small for any element to meet the bound: 19.5° for subfacets, and 20.9° for tetrahedra at the default bound 1.4.
  - A subsegment encroached across a small angle between two segments is left.
  - A segment that leaves a facet at less than 60° to its plane and that facet no longer split each other.
  - An unsplit edge between single-triangle facets is held to the subfacet size bound, not the stricter segment bound.
  - Slivers at the fixed vertices of a triangle surface are split.

  Polygon inputs and locked facets are unaffected. On 55 triangle-surface inputs every mesh is valid. They are meshloom's own boundaries of C1–C7, the unit cube, and 30 synthetic small-angle surfaces. One input is slow: C3 at h = 0.8, 24 s against 5.9 s from its builder input. Quality next to small angles is not guaranteed. New tests in `tests/meshloom/test_small_angle_mesh.py`. [meshloom](docs/packages/meshloom/overview.md#limits).

## 한국어

- `meshloom`: **삼각형마다 facet 하나로 준 닫힌 삼각형 표면은 삼각형이 작은 각으로 만나도 이제 메시가 됩니다.** 전에는 1° 이하의 평면 안 부채꼴이나 바늘 삼각형, 또는 이웃하지 않는 변에서 대각선의 1e-4 안에 있는 꼭짓점이 있으면 세분화가 끝없이 나눴습니다. 점 상한에서 `RefineError`로 멈추거나, 몇 분 안에 끝나지 않았습니다. 바뀐 규칙은 다음과 같습니다.
  - 어떤 요소도 기준을 만족할 수 없을 만큼 작은 입력각 안에서는 가는 subfacet이나 사면체를 품질 때문에 나누지 않습니다. 그 각은 subfacet에서 19.5°, 사면체에서 20.9°입니다(기본 기준 1.4일 때).
  - 두 선분 사이의 작은 각을 건너 잠식된 subsegment는 그대로 둡니다.
  - facet에서 그 평면과 60° 미만으로 떠나는 선분과 그 facet은 이제 서로를 나누지 않습니다.
  - 삼각형 하나짜리 facet 사이의 나누지 않은 변은 더 엄격한 선분 기준이 아니라 subfacet 크기 기준을 받습니다.
  - 삼각형 표면의 고정 꼭짓점에 닿은 sliver는 나눕니다.

  다각형 입력과 잠긴 facet은 영향이 없습니다. 삼각형 표면 입력 55개에서 모든 메시가 유효합니다. 입력은 meshloom이 만든 C1–C7의 경계, 단위 정육면체, 작은 각 합성 표면 30개입니다. 한 입력은 느립니다. C3 h = 0.8은 builder 입력으로 5.9초인 것이 24초 걸립니다. 작은 각 옆의 품질은 보장하지 않습니다. 새 시험은 `tests/meshloom/test_small_angle_mesh.py`에 있습니다. [meshloom](packages/meshloom/overview.md#한계).
