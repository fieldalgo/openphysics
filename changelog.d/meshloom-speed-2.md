# Changed

## English

- `meshloom`: **meshing is faster again, with the same output.**
  - The quality flips skip a face or an edge whose flip was refused until a tetrahedron on it changes.
  - The input check finds the segments inside each facet from the facet's own points, instead of testing every segment against every facet.

## 한국어

- `meshloom`: **메시 생성이 다시 빨라졌고, 결과는 같습니다.**
  - 품질 flip은 한 번 거절된 면이나 모서리를, 그 위의 사면체가 바뀔 때까지 다시 시도하지 않습니다.
  - 입력 검사는 면 안의 선분을 그 면의 점에서 찾습니다. 모든 선분을 모든 면과 맞춰 보지 않습니다.
