# Fixed

## English

- `simcase`: **Studio 3D's cut is drawn in colour, not near white (experimental).**
  - The surface and cut colours are handed to the renderer as linear light. Before, three.js lifted them toward white.
  - The cut has its own saturated map (blue, cyan, green, amber, red), because a cut's temperatures often sit mid-range, where the surface map's light centre reads as white.
  - Both legends sit above the view, in sight.

  [3D models](docs/packages/simcase/workspace.md#3d-models-experimental).

## 한국어

- `simcase`: **Studio 3D의 단면이 거의 흰색이 아니라 색으로 그려집니다(실험적).**
  - 면과 단면의 색을 렌더러에 선형 빛으로 넘깁니다. 전에는 three.js가 흰색 쪽으로 들떴습니다.
  - 단면은 채도 높은 제 지도(파랑, 청록, 초록, 호박색, 빨강)를 씁니다. 단면 온도는 흔히 범위 가운데에 몰리는데, 면 지도의 밝은 가운데는 흰색처럼 보이기 때문입니다.
  - 두 범례는 보기 위에 있어 늘 보입니다.

  [3D 모델](packages/simcase/workspace.md#3d-모델실험적).
