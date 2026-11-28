# Changed

## English

- `simcase`: **Studio 3D's mesh-estimate refusal offers a size under a minute, with a button per size (experimental).**
  - The second size is now the smallest whose estimated time is at most 45 s, so it reads *under a minute*.
  - Messages reads, for example, *Element size 6.36 µm: about 597,583 tetrahedra (estimated about 6 min). 12.9 µm: under a minute (estimated about 45 s).*
  - **Use 6.36 µm** and **Use 12.9 µm** set Mesh 1's element size (one Undo step).
  - The times are the engine's estimate, not a measurement.

  [3D models](docs/packages/simcase/workspace.md#3d-models-experimental).

## 한국어

- `simcase`: **Studio 3D의 메시 추정 거부가 1분 안의 크기와 크기마다 버튼을 제안합니다(실험적).**
  - 둘째 크기는 이제 추정 시간이 45 s 이하인 가장 작은 값이라 *under a minute*로 읽힙니다.
  - Messages는 예를 들어 *Element size 6.36 µm: about 597,583 tetrahedra (estimated about 6 min). 12.9 µm: under a minute (estimated about 45 s).*로 읽힙니다.
  - **Use 6.36 µm**와 **Use 12.9 µm**는 Mesh 1의 요소 크기를 그 값으로 둡니다(Undo 한 단계).
  - 시간은 엔진의 추정이며 잰 값이 아닙니다.

  [3D 모델](packages/simcase/workspace.md#3d-모델실험적).
