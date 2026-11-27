# Added

## English

- `simcase`: **the 3D model in the Studio workspace (experimental).**
  - The Library group "3D models (experimental)" adds the card "Via in a layer stack (3D heat)". Choosing it adds a 3D model to the tab and keeps the other models.
  - The builder tree follows design 5.2: Component 1 · 3D · µm, Parameters, Geometry 1 (Domain, numbered features with the server's coverage words, Form result with region and face counts) and Materials.
  - Add feature offers Box and Layers; Extrude, Cylinder and Sphere are greyed with their reason. Features can be moved (also Alt+Up/Down), duplicated and deleted with Undo; a layers feature can add and remove layers.
  - Property fields take quantities, parameters or expressions and show the SI value or "= t_ox (10 µm)". Studio's range guards use the 2D range sentence and keep a highlighted draft that blocks Save, Mesh and Run. A used parameter is not deleted, and the refusal names its users.
  - Every edit is checked by the server. A refusal shows the engine's words in Messages with the code under Details, marks the feature's tree row, greys the last shape that could be formed, and gives Mesh and Run the reason "Fix 1 problem in Messages to mesh".
  - "Use for → New selection" works from the view and from the faces list, by pointer or keyboard. The 3D model has its own Undo history and saves with the project (version 2) and as a model3d session.
  - Checks: W4, W5, W11, W12 and W13 (part B) in the browser, all at their thresholds.

  [3D models](docs/packages/simcase/workspace.md#3d-models-experimental).

## 한국어

- `simcase`: **Studio 작업 공간의 3D 모델(실험적).**
  - Library 묶음 "3D models (experimental)"에 카드 "Via in a layer stack (3D heat)"가 더해집니다. 고르면 3D 모델이 탭에 더해지고 다른 모델은 그대로입니다.
  - 빌더 트리는 설계 5.2를 따릅니다: Component 1 · 3D · µm, Parameters, Geometry 1(Domain, 서버의 덮임 말이 붙은 번호 특징, 영역과 면 수가 붙은 Form result), Materials.
  - Add feature는 Box와 Layers를 내놓고, Extrude, Cylinder, Sphere는 이유와 함께 흐리게 보입니다. 특징은 이동(Alt+Up/Down도), 복제, Undo가 되는 삭제가 되며, layers 특징은 층을 더하고 뺄 수 있습니다.
  - 속성 칸은 물리량, 매개변수, 식을 받고 SI 값이나 "= t_ox (10 µm)"를 보입니다. Studio의 범위 검사는 2D 범위 문장을 쓰고, Save, Mesh, Run을 막는 강조된 초안을 남깁니다. 쓰이는 매개변수는 지우지 않으며 거부가 쓰는 곳을 밝힙니다.
  - 편집마다 서버가 검사합니다. 거부는 Messages에 엔진의 말을, Details에 코드를 보이고, 특징의 트리 행을 표시하며, 만들 수 있었던 마지막 형상을 흐리게 하고, Mesh와 Run에 "Fix 1 problem in Messages to mesh"라는 이유를 줍니다.
  - "Use for → New selection"은 보기와 면 목록에서, 포인터나 키보드로 됩니다. 3D 모델은 자체 Undo 기록을 갖고 프로젝트(버전 2)와 model3d 세션으로 저장됩니다.
  - 검사: 브라우저의 W4, W5, W11, W12, W13(B 부분), 모두 기준 충족.

  [3D 모델](packages/simcase/workspace.md#3d-모델실험적).
