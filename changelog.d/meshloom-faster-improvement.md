# Changed

## English

- `meshloom`: **meshing is faster, with the same output.** The mixed-point predicates keep each segment or facet point's interval coordinates instead of rebuilding them at every call; the flips compute each tetrahedron's shape once per decision and the smallest dihedral angle with one arc cosine instead of six; smoothing computes each star's quality once per trial position; the mesh complex's face table and the subfacet and segment tables use a fast hasher instead of SipHash; and edge removal checks its ring without the face table and keeps its ring triangulation's qualities in an array. Every recorded mesh is unchanged (59 comparison inputs and V26's nine cases, bit for bit). V14's graded 1M-tetrahedron cube takes a median of 131 s instead of 175 s (the 60 s bound is still not met); the meshloom test suite runs in about two-thirds of its time. [meshloom limits](docs/packages/meshloom/overview.md#limits).

## 한국어

- `meshloom`: **출력은 같고 메시 생성이 빨라졌습니다.**
  - 혼합점 술어가 선분점·facet점의 구간 좌표를 호출마다 다시 만들지 않고 들고 있습니다.
  - flip은 판정마다 사면체의 shape를 한 번만 계산하고, 최소 이면각을 arc cosine 여섯 번이 아니라 한 번으로 계산합니다.
  - smoothing은 시험 위치마다 별(star)의 품질을 한 번만 계산합니다.
  - 메시 복합체의 면 표와 subfacet·선분 표가 SipHash 대신 빠른 해셔를 씁니다.
  - edge removal은 면 표를 찾지 않고 고리를 검사하며, 고리 삼각분할의 품질을 배열에 둡니다.
  - 기록된 메시는 모두 그대로입니다(비교 입력 59개와 V26 아홉 사례, 비트 단위).
  - V14의 graded 1M 사면체 정육면체는 중앙값 175 s에서 131 s가 됐습니다(60 s 한도는 아직 못 맞춤). meshloom 시험 묶음은 걸리던 시간의 약 3분의 2로 끝납니다. [meshloom 한계](packages/meshloom/overview.md#한계).
