# Changed

## English

- Studio: **a warning before a closed run, not only after.** In a closed window with *Highest n_eff above 1.45*, when a shape touching the window edge has an index at least as high as the shapes away from it (T18's silicon substrate under a silicon core), the plan line beside Run study and Physics › Optical modes say *Substrate touches the window edge and its index is as high as Core's: in a closed window its slab modes come first.* with **Set search near 2.46 · 4 modes** and **Use Open boundary**. It is a geometry and material check with no solve; it goes with *Nearest to n_eff* or Open boundary. The result-side edge note and the default search are unchanged. [Workspace](docs/packages/simcase/workspace.md).

## 한국어

- Studio: **닫힌 실행 뒤만이 아니라 앞에서도 경고합니다.** *Highest n_eff above 1.45*를 고른 닫힌 창에서 창 가장자리에 닿는 형상의 굴절률이 가장자리에서 떨어진 형상들만큼 높으면(T18에서 실리콘 코어 아래 실리콘 기판), Run study 옆 계획 줄과 Physics › Optical modes가 **Set search near 2.46 · 4 modes**, **Use Open boundary**와 함께 *Substrate touches the window edge and its index is as high as Core's: in a closed window its slab modes come first.*라고 말합니다. 풀이 없는 형상과 재료 점검이며, *Nearest to n_eff*나 Open boundary를 고르면 사라집니다. 결과 쪽 가장자리 안내와 기본 탐색은 바뀌지 않습니다. [워크스페이스](packages/simcase/workspace.md).
