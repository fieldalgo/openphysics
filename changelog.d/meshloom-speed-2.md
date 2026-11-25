# Changed

## English

- `meshloom`: **meshing is faster again, with the same output.**
  - The quality flips skip a face or an edge whose flip was refused until a tetrahedron on it changes.
  - The input check finds the segments inside each facet from the facet's own points, instead of testing every segment against every facet.
  - `mesh_plc` runs the input check once instead of twice. An invalid input raises the same `InvalidPLC` with the same witness.
  - The exact orientation test keeps its intermediate values on the stack instead of allocating them.

## 한국어

- `meshloom`: **메시 생성이 다시 빨라졌고, 결과는 같습니다.**
  - 품질 flip은 한 번 거절된 면이나 모서리를, 그 위의 사면체가 바뀔 때까지 다시 시도하지 않습니다.
  - 입력 검사는 면 안의 선분을 그 면의 점에서 찾습니다. 모든 선분을 모든 면과 맞춰 보지 않습니다.
  - `mesh_plc`는 입력 검사를 두 번이 아니라 한 번 합니다. 잘못된 입력은 같은 근거와 함께 같은 `InvalidPLC`를 냅니다.
  - 정확한 orientation 판정은 중간값을 할당하지 않고 스택에 둡니다.
