# Added

## English

- CI tooling: **`tools/shards/openphysics_shard.py --slowest` builds the test-part table from several runs.** It reads one folder of JUnit XML per complete set of sixteen parts and keeps each test file's longest time. A part runs on one runner, and a table from one run mixes fast and slow runners. Rebalanced from the eleven sets of main runs on 2026-11-27 and 2026-11-28 with such single-run tables, the slowest part would have taken 31–39 minutes of tests on the slowest runners seen; balanced by the slowest times, 25.2 minutes. `--update` is unchanged. [Development guide](docs/development.md#what-ci-runs).

## 한국어

- CI 도구: **`tools/shards/openphysics_shard.py --slowest`가 여러 실행으로 시험 부분 표를 만듭니다.** 열여섯 부분 한 벌마다 JUnit XML 폴더 하나를 읽고, 시험 파일마다 가장 긴 시간을 남깁니다. 한 부분은 러너 하나에서 도는데, 한 실행으로 만든 표에는 빠른 러너와 느린 러너가 섞여 있습니다. 2026-11-27과 2026-11-28 main 실행의 열한 벌을 이런 단일 실행 표로 다시 나누면, 지금까지 본 가장 느린 러너에서 가장 긴 부분이 시험 31–39분이었을 것입니다. 가장 느린 시간으로 나누면 25.2분입니다. `--update`는 그대로입니다. [개발 안내](development.md#ci가-돌리는-것).
