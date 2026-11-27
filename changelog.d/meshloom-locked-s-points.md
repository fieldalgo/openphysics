# Fixed

## English

- `meshloom`: **locked facets that need Steiner points work again.** Since the predicate speed-up of 2026-11-27 (main `6a5b88e8`), the step that moves recovery's points off locked facets took the recovered points without their cached interval coordinates, so a later point's coordinates were read for the first recovered point. A predicate could then take a wrong sign: on locked triangle surfaces of three-region meshes it panicked (`index out of bounds` in `locked.rs`) or refused with a different `RecoveryError`. The points now go in through the same path as everywhere else; on all 21 locked V14 surfaces, the meshes are again bit for bit those of main before that change; and the predicate entry points check in every build that the cache matches the points. A test meshes the locked boundary and interface triangles of meshloom's own C3 mesh. [meshloom limits](docs/packages/meshloom/overview.md#limits).

## 한국어

- `meshloom`: **Steiner 점이 필요한 잠긴 facet이 다시 메싱됩니다.**
  - 2026-11-27 술어 가속(main `6a5b88e8`)부터, 잠긴 facet 위의 복원 점을 옮기는 단계가 복원 점을 캐시된 구간 좌표 없이 받았습니다. 그래서 첫 복원 점의 좌표 대신 나중 점의 좌표를 읽었습니다.
  - 그 결과 술어가 틀린 부호를 낼 수 있었습니다. 세 영역 메시의 잠긴 삼각형 표면에서는 panic이 나거나(`locked.rs`의 `index out of bounds`), 다른 `RecoveryError`로 거부했습니다.
  - 이제 점이 다른 곳과 같은 경로로 들어갑니다. 잠긴 V14 표면 21개 모두에서 메시는 그 변경 전 main과 비트 단위로 같습니다. 술어 입구는 모든 빌드에서 캐시와 점이 맞는지 확인합니다.
  - 시험 하나가 meshloom 자신의 C3 메시에서 나온 경계·경계면 삼각형을 잠가서 메싱합니다. [meshloom 한계](packages/meshloom/overview.md#한계).
