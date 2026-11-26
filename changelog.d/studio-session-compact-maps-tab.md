# Changed

## English

- Studio: **heated runs keep more maps.** When a heated model's maps would no longer all fit the 16.8 MB budget as text, every map of the tab is kept compact (multiphysics session version 17) and from then on every map that arrives, so 20 results keep 20 maps at a 0.12 µm mesh (10 before), 17 of the heated slab example (6) and 15 at 0.08 µm (5); the template's runs fit as text and never convert. Results says *Maps at single precision (float32). The values above are the engine's.* under such a run's maps and the run list adds *When maps would not all fit, they are kept at single precision.*; Messages says nothing of it. n_eff, the temperature range, the coupling check and the iteration history are unchanged; on the measured models the legends are the same and only the core temperature map (0.03 K wide) changes colour, by one level of 255 on 0.3 to 2.3 % of its triangles. [Compact maps (single precision)](docs/packages/simcase/workspace.md#compact-maps-single-precision).

## 한국어

- Studio: **가열 실행이 맵을 더 많이 보관합니다.** 가열 모델의 맵을 16.8 MB 예산에 더는 모두 텍스트로 담을 수 없게 되면 탭의 모든 맵을 압축해 보관하고(다중물리 세션 버전 17) 그 뒤 도착하는 맵도 모두 압축하므로, 결과 20개에서 0.12 µm 메시는 20개(전에는 10개), 가열 슬래브 예제는 17개(6개), 0.08 µm는 15개(5개)의 맵을 보관합니다. 템플릿 실행은 텍스트로 들어가 변환하지 않습니다. Results는 그런 실행의 맵 아래 *Maps at single precision (float32). The values above are the engine's.*를 보이고 실행 목록 안내에 *When maps would not all fit, they are kept at single precision.*가 붙으며, Messages는 이를 말하지 않습니다. n_eff, 온도 범위, 결합 검사, 반복 기록은 그대로이고, 잰 모델에서 범례는 같으며 코어 온도 맵(0.03 K 폭)만 삼각형의 0.3~2.3 %에서 255단계 중 한 단계 색이 바뀝니다. [압축 맵(단정밀도)](packages/simcase/workspace.md#압축-맵단정밀도).
