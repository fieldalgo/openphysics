# Fixed

## English

- `simcase`: **Studio's 3D tree no longer marks Heat transfer (3D) for a refusal that blocks meshing.** When the shape forms but meshing is refused (a below-tolerance feature, say), the run reader refuses the same document in the same words. The tree marked both Mesh 1 and Heat transfer (3D). Run's reasons put the mesh refusal first, so only Mesh 1 (or the feature) is marked now.

  [3D models](docs/packages/simcase/workspace.md#3d-models-experimental).

## 한국어

- `simcase`: **Studio의 3D 트리가 메시를 막는 거부로 Heat transfer (3D)를 더는 표시하지 않습니다.** 형상은 만들어지지만 메시가 거부될 때(예: 허용 오차 아래의 특징) run reader도 같은 문서를 같은 말로 거부합니다. 그래서 트리가 Mesh 1과 Heat transfer (3D)를 둘 다 표시했습니다. Run의 이유에서는 메시 거부가 먼저이므로, 이제 Mesh 1(또는 특징)만 표시합니다.

  [3D 모델](packages/simcase/workspace.md#3d-모델실험적).
