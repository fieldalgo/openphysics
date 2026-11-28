# Fixed

## English

- `simcase`: **Studio's 3D run values name what the energy balance residual is relative to.** The values table said "(… of the source)", but the ratio is the solver's relative conservation residual: the residual divided by the sum of the absolute nodal heat rates. On a run with no heat source, it read as a ratio to 0 W. It now says "(… of the summed heat rates)".

  [3D models](docs/packages/simcase/workspace.md#3d-models-experimental).

## 한국어

- `simcase`: **Studio의 3D 실행 값이 에너지 균형 잔차가 무엇에 대한 비율인지 바르게 밝힙니다.** 값 표는 "(… of the source)"라고 했지만, 그 비율은 해석기의 상대 보존 잔차, 곧 잔차를 절대 절점 열률의 합으로 나눈 값입니다. 열원이 없는 실행에서는 0 W에 대한 비율처럼 읽혔습니다. 이제 "(… of the summed heat rates)"라고 말합니다.

  [3D 모델](packages/simcase/workspace.md#3d-모델실험적).
