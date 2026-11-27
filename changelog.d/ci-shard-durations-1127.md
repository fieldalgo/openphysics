# Fixed

## English

- CI: **the sixteen source-test parts are balanced again.** `tools/shards/durations.json` is rebuilt from the JUnit XML of main run 45983151154 (all sixteen parts green). By the old table each part planned 24.9–25.2 minutes of tests, but the parts took 10.8–31.3 minutes, and the longest job took 34.1 minutes: several files had grown since the table was built, the corner-field studies and the cavity slab refinement by 4–6 minutes each. The new table plans 21.8–22.7 minutes per part. No test, marker, tolerance or time limit changes. [Development guide](docs/development.md#what-ci-runs).

## 한국어

- CI: **소스 시험 열여섯 부분이 다시 고르게 나뉩니다.** `tools/shards/durations.json`을 main run 45983151154(열여섯 부분 모두 green)의 JUnit XML로 다시 만들었습니다. 옛 표로는 부분마다 시험 24.9–25.2분을 계획했지만, 실제로는 10.8–31.3분이 걸렸고 가장 긴 job은 34.1분이었습니다. 표를 만든 뒤 늘어난 파일들 때문입니다. corner-field 연구와 공진기 slab 세분화가 각각 4–6분 늘었습니다. 새 표는 부분마다 21.8–22.7분을 계획합니다. 시험, 표시, 허용 오차, 시간 한도는 바뀌지 않습니다. [개발 안내](development.md#ci가-돌리는-것).
