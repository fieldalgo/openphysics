# Changed

## English

- `meshloom`: **the improvement phase computes less for the same mesh.** The 3-2 flips and edge removal list their edges vertex by vertex from the tetrahedra around each vertex, already sorted, instead of sorting a list of every edge on each pass. Edge removal keeps each tetrahedron's quality and smallest dihedral angle until one of its vertices moves, and its ring triangulation skips triangles that cannot change its result. Every recorded mesh is unchanged, bit for bit (the same four sets as the neighbour-array change). V14's graded 1M-tetrahedron cube takes a median of 126.4 s (126.3–129.1 s) against 133.1 s with the neighbour arrays alone and 136.2 s for main, alternating, five runs each on one machine; peak memory stays at 0.78 GiB. The 60 s bound is still not met. [meshloom limits](docs/packages/meshloom/overview.md#limits).

## 한국어

- `meshloom`: **개선 단계가 같은 메시를 더 적은 계산으로 만듭니다.**
  - 3-2 flip과 edge removal은 패스마다 모든 간선 목록을 정렬하지 않고, 꼭짓점마다 둘레 사면체에서 정렬된 간선을 바로 만듭니다.
  - edge removal은 사면체의 품질과 최소 이면각을 그 꼭짓점이 움직일 때까지 들고 있습니다. 고리 삼각분할은 결과를 바꿀 수 없는 삼각형을 건너뜁니다.
  - 기록된 메시는 비트 단위로 모두 그대로입니다(이웃 배열 변경과 같은 네 집합).
  - V14의 graded 1M 사면체 정육면체는 한 머신에서 번갈아 다섯 번씩 재어 중앙값 126.4 s(126.3–129.1 s)입니다. 이웃 배열만 있을 때는 133.1 s, main은 136.2 s입니다. peak 메모리는 0.78 GiB 그대로입니다. 60 s 한도는 아직 못 맞춥니다. [meshloom 한계](packages/meshloom/overview.md#한계).
