# Changed

## English

- `meshloom`: **the mesh complex that refinement changes keeps each tetrahedron's neighbours instead of a table of faces.** A face is found from the tetrahedra around one of its vertices, and the flips read a face's two tetrahedra from the one they already know. Every recorded mesh is unchanged, bit for bit: 59 comparison inputs, V26's nine cases, the six synthetic constrained-Delaunay inputs and the 21 locked V14 surfaces. V14's graded 1M-tetrahedron cube takes a median of 133.1 s against 136.2 s for main, alternating, five runs each on one machine (ranges 132.3–136.5 s and 134.7–139.6 s; the 60 s bound is still not met). [meshloom limits](docs/packages/meshloom/overview.md#limits).

## 한국어

- `meshloom`: **refinement이 바꾸는 메시 복합체가 면 표 대신 사면체마다 이웃을 들고 있습니다.**
  - 면은 그 꼭짓점 하나를 둘러싼 사면체들에서 찾습니다. flip은 이미 아는 사면체에서 면의 두 사면체를 읽습니다.
  - 기록된 메시는 비트 단위로 모두 그대로입니다. 비교 입력 59개, V26 아홉 사례, 합성 constrained Delaunay 입력 여섯 개, 잠긴 V14 표면 21개입니다.
  - V14의 graded 1M 사면체 정육면체는 한 머신에서 main과 번갈아 다섯 번씩 재어 중앙값 133.1 s입니다. main은 136.2 s입니다(범위 132.3–136.5 s, 134.7–139.6 s). 60 s 한도는 아직 못 맞춥니다. [meshloom 한계](packages/meshloom/overview.md#한계).
