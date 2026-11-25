# Added

## English

- Studio server: **the status of a running optical job names its step.** `GET /api/jobs/{id}` returns `step`, the latest `search_started` event of `simcase.run`'s new `on_event` (for example solve 2 of 3, search 1 of 2), `null` before the first event and once the job is done or failed. The result route and every result are unchanged. [The HTTP API](docs/packages/simcase/overview.md#the-http-api).

## 한국어

- Studio 서버: **실행 중인 광학 작업의 상태가 단계를 알립니다.** `GET /api/jobs/{id}`가 `simcase.run`의 새 `on_event`가 낸 최신 `search_started` 이벤트(예: 풀이 2/3, 탐색 1/2)를 `step`으로 돌려주며, 첫 이벤트 전과 작업이 끝나거나 실패한 뒤에는 `null`입니다. 결과 경로와 모든 결과는 그대로입니다. [HTTP API](packages/simcase/overview.md#http-api).
