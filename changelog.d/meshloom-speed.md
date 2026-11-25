# Changed

## English

- `meshloom`: **meshing is 1.4–2.5 times faster, with the same output.**
  - The exact orientation and insphere tests take the adaptive double predicates whenever every point is a double triple: an input point or a volume Steiner point.
  - Two other exact tests now try an interval filter first.
  - The quality flips test the cheap shape criterion before the exact orientations, and remember shapes during a pass.

  The meshes are unchanged: same nodes, tetrahedra and regions. On the 21 benchmark surfaces of the 3D plan (V14) the time from the surface falls by 1.43–2.53 times. meshloom is still 2.4–38.5 times slower than Gmsh there; the speed work goes on.

## 한국어

- `meshloom`: **메시 생성이 1.4–2.5배 빨라졌고, 결과는 같습니다.**
  - 정확한 orientation·insphere 판정은 모든 점이 double 세 개(입력점이나 부피 Steiner 점)이면 적응형 double 술어를 씁니다.
  - 다른 정확 판정 두 개는 이제 구간 필터를 먼저 씁니다.
  - 품질 flip은 정확한 orientation보다 싼 모양 판정을 먼저 하고, 한 패스 동안 모양 값을 기억합니다.

  메시는 그대로입니다(노드, 사면체, 영역이 같음). 3D 계획의 벤치마크 표면 21개(V14)에서 표면부터의 시간이 1.43–2.53배 줄었습니다. 그래도 그곳에서 Gmsh보다 2.4–38.5배 느리고, 속도 작업은 이어집니다.
