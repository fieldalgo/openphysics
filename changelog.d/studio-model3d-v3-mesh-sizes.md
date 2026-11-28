# Changed

## English

- `simcase`: **Studio 3D's mesh-size refusal gives a size that meshes in about a minute (experimental).**
  - Beside the smallest element size the limit accepts, Messages gives the smallest size estimated at 60 s or less, each with its estimate: *Element size 6.36 µm meshes about 597,583 tetrahedra (estimated about 6 min); 11.7 µm about 98,783 (estimated about 1 min).* These are the engine's estimates, not measured times.
  - The check's refusal carries `suggested_minute`, `suggested_tetrahedra`, `suggested_seconds`, `minute_tetrahedra` and `minute_seconds`.
  - The tree's Mesh 1 row reads *too fine*.

  [3D models](docs/packages/simcase/workspace.md#3d-models-experimental).

## 한국어

- `simcase`: **Studio 3D의 메시 크기 거부가 약 1분에 메시되는 크기를 줍니다(실험적).**
  - Messages는 한도가 받는 가장 작은 요소 크기 옆에 추정 60 s 이하인 가장 작은 크기를 각각의 추정과 함께 줍니다: *Element size 6.36 µm meshes about 597,583 tetrahedra (estimated about 6 min); 11.7 µm about 98,783 (estimated about 1 min).* 이는 엔진의 추정이며 잰 시간이 아닙니다.
  - 검사의 거부에 `suggested_minute`, `suggested_tetrahedra`, `suggested_seconds`, `minute_tetrahedra`, `minute_seconds`가 붙습니다.
  - 트리의 Mesh 1 행은 *too fine*으로 읽힙니다.

  [3D 모델](packages/simcase/workspace.md#3d-모델실험적).
