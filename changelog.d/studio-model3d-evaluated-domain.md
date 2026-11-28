# Changed

## English

- `simcase`: **Studio's 3D builder reads a domain bound given by a parameter or an expression (experimental).** `POST /api/model3d/check` now also answers the evaluated `domain`, as numbers in the component's unit. Once the check has answered, the workspace's Domain row, its mesh and element size guards and Add feature's defaults use it whenever a bound is written as a parameter or an expression. Before the check answers, such a bound is unknown, as before.

  [3D models](docs/packages/simcase/workspace.md#3d-models-experimental).

## 한국어

- `simcase`: **Studio의 3D 빌더가 매개변수나 식으로 쓴 영역 경계를 읽습니다(실험적).** `POST /api/model3d/check`가 이제 계산된 `domain`도 구성 요소 단위의 수로 답합니다. 검사가 답하고 나면, 경계를 매개변수나 식으로 썼을 때 작업 공간의 Domain 행, 메시와 요소 크기 범위, Add feature의 기본값이 그것을 씁니다. 검사가 답하기 전에는 그런 경계를 전처럼 알 수 없습니다.

  [3D 모델](packages/simcase/workspace.md#3d-모델실험적).
