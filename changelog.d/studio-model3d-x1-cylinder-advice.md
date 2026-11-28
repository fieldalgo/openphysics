# Fixed

## English

- `simcase`: **Studio 3D's cylinder advice names only values the engine accepts (experimental).**
  - A cylinder across or touching a domain side now reads, for example, *Keep cx < 0.7 m (cx + r < 1 m): cx = 0.69 m forms. Or r < 0.2 m: r = 0.19 m forms.*
  - The bounds are strict, since the engine refuses a cylinder that touches a side.
  - A value is named only after the server's check has formed the shape and estimated its mesh with it.
  - The *touches … at one line* refusal gets the same plain words.

  [3D models](docs/packages/simcase/workspace.md#3d-models-experimental).

## 한국어

- `simcase`: **Studio 3D의 원기둥 제안이 엔진이 받는 값만 이름 붙입니다(실험적).**
  - 영역 옆면을 가로지르거나 닿는 원기둥은 이제 예를 들어 *Keep cx < 0.7 m (cx + r < 1 m): cx = 0.69 m forms. Or r < 0.2 m: r = 0.19 m forms.*로 읽힙니다.
  - 엔진이 옆면에 닿는 원기둥을 거부하므로 경계는 엄격합니다.
  - 값은 서버 검사가 그 값으로 형상을 만들고 메시를 추정한 뒤에만 이름이 붙습니다.
  - *touches … at one line* 거부도 같은 쉬운 말을 얻습니다.

  [3D 모델](packages/simcase/workspace.md#3d-모델실험적).
