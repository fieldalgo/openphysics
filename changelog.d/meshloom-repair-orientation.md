# Fixed

## English

- `meshloom`: **the repair after rounding no longer folds the mesh when two adjacent tetrahedra are both inverted.** Rounding points to doubles can turn tetrahedra flat or inverted, and a repair replaces them by flips or cavity fills. A 2-3 flip of two tetrahedra that were both inverted replaced them by three positive ones over the same five points. Their signed coverage there was −1, not +1, so the mesh folded, and certification stopped with `RoundingError` ("both of its tetrahedra on one side"). Every repair operation must now keep the oriented boundary of what it replaces (each face's signed count), which keeps the signed coverage. Other operations now repair what such a flip had folded: of the 400 seeded inputs of the rounding-repair test, 308 mesh validly (285 before) and 91 stop with `RoundingError` (114 before). The case was seen on a triangle surface meshed through its triangles. New test in the kernel's rounding-repair tests (`rust/mesh.rs`).

## 한국어

- `meshloom`: **이웃한 두 사면체가 모두 뒤집혔을 때 반올림 뒤 수리가 더는 메시를 접지 않습니다.** 점을 double로 반올림하면 사면체가 납작해지거나 뒤집힐 수 있고, 수리는 flip이나 공동 채움으로 이를 바꿉니다. 둘 다 뒤집힌 사면체에 2-3 flip을 하면 같은 다섯 점 위의 양수 사면체 셋으로 바뀌었습니다. 그 자리의 부호 있는 덮음은 +1이 아니라 −1이었으므로 메시가 접혔고, 검증이 `RoundingError`("both of its tetrahedra on one side")로 멈췄습니다. 이제 모든 수리 연산은 바꾸는 부분의 방향 있는 경계(면마다 부호 있는 개수)를 지켜야 하고, 그래서 부호 있는 덮음이 보존됩니다. 그런 flip이 접던 곳을 이제 다른 연산이 수리합니다. 반올림 수리 시험의 시드 입력 400개 중 308개가 유효한 메시가 되고(전에는 285개), 91개가 `RoundingError`로 멈춥니다(전에는 114개). 삼각형마다 facet으로 넣은 삼각형 표면에서 나타났습니다. 새 시험은 커널의 반올림 수리 시험(`rust/mesh.rs`)에 있습니다.
