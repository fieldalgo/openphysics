# Changed

## English

- `simcase`: **Studio's 3D model files keep its runs, and the card has its heat physics (experimental).** A model3d session file (version 1, unreleased) takes an optional `runs` list: up to 10 records of format `thermal-steady3d-run-v1`, each checked on Open (*The model3d session holds 11 runs; at most 10 are kept.*, *Run 1 of the model3d session is not a thermal-steady3d-run-v1 record.*). A file without runs has no `runs` key and is written byte for byte as before; project version 2 is unchanged. The card **Via in a layer stack (3D heat)** now holds Heat transfer (3D): 300 K on `z0`, 1e12 W/m³ in the top silicon, every other outer face insulated. The top silicon is its own material, `Si (top)`, with the properties of `Si`, only because a heat source names a region by its material today.

  [3D models](docs/packages/simcase/workspace.md#3d-models-experimental).

## 한국어

- `simcase`: **Studio의 3D 모델 파일이 실행을 담고, 카드가 열 물리를 갖습니다(실험적).** model3d 세션 파일(버전 1, 미출시)이 선택적 `runs` 목록을 받습니다: `thermal-steady3d-run-v1` 형식의 기록 최대 10개, Open할 때 하나하나 검사(*The model3d session holds 11 runs; at most 10 are kept.*, *Run 1 of the model3d session is not a thermal-steady3d-run-v1 record.*). 실행이 없는 파일에는 `runs` 키가 없고 전과 바이트까지 같게 쓰며, 프로젝트 버전 2는 바뀌지 않습니다. 카드 **Via in a layer stack (3D heat)**은 이제 Heat transfer (3D)를 담습니다: `z0`에 300 K, 위 실리콘에 1e12 W/m³, 나머지 바깥 면은 모두 단열. 위 실리콘은 `Si`와 같은 물성의 제 재료 `Si (top)`인데, 이는 오늘 열원이 영역을 재료 이름으로만 가리키기 때문입니다.

  [3D 모델](packages/simcase/workspace.md#3d-모델실험적).
