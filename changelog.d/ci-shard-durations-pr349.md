# Fixed

## English

- CI: **the source-test parts are balanced again.** `tools/shards/durations.json` is rebuilt from the JUnit XML of run 45409971229 (PR #349, all eight parts green) and now lists every collected test file; 30 files were missing and were each counted as the median, a few seconds. One of them, `tests/simcase/test_studio_closed_target.py`, takes about 3 minutes on CI: with it unlisted, part 5 ran 27 minutes by the run's own times and was cancelled at the 45-minute limit on main (run 45415835896) on a slow runner. The new table plans 21.5 minutes of tests per part. No test, marker, tolerance or time limit changes. [Development guide](docs/development.md#what-ci-runs).

## 한국어

- CI: **소스 시험 부분들이 다시 고르게 나뉩니다.** `tools/shards/durations.json`을 실행 45409971229(PR #349, 여덟 부분 모두 통과)의 JUnit XML로 다시 만들어, 수집한 모든 시험 파일이 들어 있습니다. 빠져 있던 30개 파일은 각각 중앙값(몇 초)으로 셌습니다. 그중 `tests/simcase/test_studio_closed_target.py`는 CI에서 약 3분이 걸려, 표에 없는 동안 5번째 부분이 그 실행의 시간으로 27분이었고 느린 러너에서 main(실행 45415835896)의 45분 제한에 닿아 취소되었습니다. 새 표는 부분마다 시험 21.5분을 계획합니다. 바뀌는 시험, 마커, 허용 오차, 시간 제한은 없습니다. [개발 안내](development.md#ci가-돌리는-것).
