# Changed

## English

- `simcase`: **Studio 3D words a mesh estimate over the limit once, in plain words, with the size to use (experimental).** The message now reads, for example, *Component 1 needs about 19,215,000 tetrahedra; the limit is 600,000. Use an element size of at least 6.36 µm.* The suggested size is the smallest that the same estimate accepts: `POST /api/model3d/check` finds it and answers `suggested_size`, `tetrahedra` and `limit`. The engine's sentence, with its formula and key, sits under Details, and Mesh and Run point to Messages. The size field is labelled **Element size**.

  [3D models](docs/packages/simcase/workspace.md#3d-models-experimental).

## 한국어

- `simcase`: **Studio 3D가 한도를 넘는 메시 추정을 쉬운 말로 한 번, 쓸 크기와 함께 보입니다(실험적).** 메시지는 이제 예를 들어 *Component 1 needs about 19,215,000 tetrahedra; the limit is 600,000. Use an element size of at least 6.36 µm.*로 읽힙니다. 제안하는 크기는 같은 추정이 받는 가장 작은 값입니다: `POST /api/model3d/check`가 그것을 찾아 `suggested_size`, `tetrahedra`, `limit`을 답합니다. 식과 키를 담은 엔진의 문장은 Details 아래에 있고, Mesh와 Run은 Messages를 가리킵니다. 크기 칸의 이름은 **Element size**입니다.

  [3D 모델](packages/simcase/workspace.md#3d-모델실험적).
