# Added

## English

- simcase: **`run(doc, on_event=callback)` reports the progress of an optical modes run.** The callback gets one `search_started` event right before each eigensolve search, with the study point, the solve (the group index adds solves 2 and 3) and the search (an open boundary's further searches) and their totals, for example `solve 2 of 3, search 1 of 2`. Results are bit for bit the same with or without it. Only kinds whose new `PhysicsKind.accepts_on_event` is true take the callback (`em.modes2d`); providers' kinds run as before. [The progress events](docs/packages/simcase/overview.md#from-python).

## 한국어

- simcase: **`run(doc, on_event=callback)`이 광학 모드 실행의 진행을 알립니다.** 콜백은 고유값 탐색 직전마다 `search_started` 이벤트 하나를 받으며, study 점, 풀이(군굴절률이 풀이 2와 3을 더함), 탐색(열린 경계의 추가 탐색)과 각 합계를 담습니다. 예: 풀이 2/3, 탐색 1/2. 결과는 콜백이 있든 없든 비트 단위로 같습니다. 새 `PhysicsKind.accepts_on_event`가 참인 종류만 콜백을 받으며(`em.modes2d`), 공급자의 종류는 전처럼 돕니다. [진행 이벤트](packages/simcase/overview.md#python에서-사용).
