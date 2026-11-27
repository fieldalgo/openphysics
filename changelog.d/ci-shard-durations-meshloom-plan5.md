# Fixed

## English

- CI: **meshloom's new determinism and graded-size test files are in the shard table.** `tools/shards/durations.json` had no entries for `tests/meshloom/test_determinism.py` and `test_graded.py`, so the sixteen source parts counted each as the median file (2.4 s). `test_determinism.py` takes about 10 minutes, and the part holding it took 40.9 minutes on main (run 45880541788) against at most 29.7 for the others. Both files now take their times from that run; no other entry changes. [Development guide](docs/development.md#what-ci-runs).

## 한국어

- CI: **meshloom의 새 결정성·graded 크기 시험 파일이 shard 표에 들어갔습니다.** `tools/shards/durations.json`에 `tests/meshloom/test_determinism.py`와 `test_graded.py`가 없어, 소스 시험 열여섯 부분이 둘을 중앙값 파일(2.4 s)로 셈했습니다. `test_determinism.py`는 약 10분이 걸려, 이 파일이 든 부분이 main에서 40.9분 걸렸습니다(run 45880541788, 다른 부분은 최대 29.7분). 이제 두 파일은 그 run의 시간을 씁니다. 다른 항목은 바뀌지 않습니다. [개발 안내](development.md#ci가-돌리는-것).
