# Added

## English

- `simcase`: **the 3D model in Studio files (experimental).**
  - A model3d session file (`application` `"model3d"`, its own version 1) holds a 3D model's document, with the 16 MiB session limit. File › Open reads it by its own rules before the optical and multiphysics version rules, which are unchanged.
  - Project files gain version 2, which adds the kind `model3d` (card `layer-stack-3d`, at most one per project). A project without a 3D model is still written as version 1, byte for byte, and version 1 files are read as before. A newer file is now refused as "This project file is version 3, newer than this Studio reads (version 2)".
  - The workspace builder that creates a 3D model comes with the next step; until then such files are made by hand.
  - Check: W11 without runs, file part (the document digest equal after save and read, for session and project; the version 1 fixture rewritten byte for byte).

  [3D models](docs/packages/simcase/workspace.md#3d-models-experimental).

## 한국어

- `simcase`: **Studio 파일 안의 3D 모델(실험적).**
  - model3d 세션 파일(`application` `"model3d"`, 자체 버전 1)이 3D 모델의 문서를 세션 한도 16 MiB로 담습니다. File › Open은 광학과 다중물리 버전 규칙보다 먼저 자체 규칙으로 읽으며, 그 규칙은 바뀌지 않습니다.
  - 프로젝트 파일에 종류 `model3d`(카드 `layer-stack-3d`, 프로젝트마다 많아야 하나)를 더한 버전 2가 생깁니다. 3D 모델이 없는 프로젝트는 여전히 바이트까지 같은 버전 1로 쓰고, 버전 1 파일은 전처럼 읽습니다. 더 새 파일은 이제 "This project file is version 3, newer than this Studio reads (version 2)"로 거부합니다.
  - 3D 모델을 만드는 작업 공간 빌더는 다음 단계에서 옵니다. 그때까지 그런 파일은 손으로 만든 것입니다.
  - 검사: W11 실행 없음, 파일 부분(세션과 프로젝트에서 저장하고 읽은 뒤 문서 digest가 같음; 버전 1 fixture를 바이트까지 같게 다시 씀).

  [3D 모델](packages/simcase/workspace.md#3d-모델실험적).
