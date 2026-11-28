# Fixed

## English

- CI: **the sixteen test parts are balanced for the slowest runner seen.** `tools/shards/durations.json` is rebuilt with `--slowest` from eleven complete sets of parts of main runs on 2026-11-27 and 2026-11-28: seven source sets and four installed sets. In those runs the test jobs took 12–38 minutes against a 21.8-minute plan; by the new table each part plans 24.9 minutes of tests on the slowest runner seen. The tests that the corner-field split moved are counted in their new files, less the cached solves they no longer repeat. No test, marker, tolerance or time limit changes. [Development guide](docs/development.md#what-ci-runs).

## 한국어

- CI: **시험 열여섯 부분이 지금까지 본 가장 느린 러너 기준으로 나뉩니다.** `tools/shards/durations.json`을 `--slowest`로 다시 만들었습니다. 2026-11-27과 2026-11-28 main 실행에서 나온 부분 전체 열한 벌(소스 일곱 벌, 설치본 네 벌)을 썼습니다. 그 실행들에서 시험 job은 계획 21.8분에 대해 12–38분이 걸렸습니다. 새 표로는 가장 느린 러너에서 부분마다 시험 24.9분을 계획합니다. corner-field 분할로 옮긴 시험은 새 파일에 넣어 셌고, 더는 반복하지 않는 캐시된 풀이 시간은 뺐습니다. 시험, 표시, 허용 오차, 시간 한도는 바뀌지 않습니다. [개발 안내](development.md#ci가-돌리는-것).
