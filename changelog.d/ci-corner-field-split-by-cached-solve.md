# Changed

## English

- Tests: **the corner-field test modules are split by the cached solve their tests share.** On a slow CI runner `test_laplace_corner_harmonic_field.py` alone took 29.3 minutes, too long for a test part of at most 30 minutes. The refusals, which share no cached solve, move to `*_refusals.py`; the 16-panel signal-selection tests of the guard and single-active fields move to `*_selection.py`. The scaling tests rejoin their modules, because they share the 32-panel solve. The linear field's reflection tests rejoin its 64-panel solves, its 32-panel tests share `test_laplace_corner_linear_field_32_panel.py`, and its circular limit has its own file. No cached solve now runs twice in a test part, and the same 12583 tests are collected; only 144 test IDs change file. No test body, assertion, tolerance, expected value or marker changes. [Development guide](docs/development.md#what-ci-runs).

## 한국어

- 시험: **corner-field 시험 모듈을 시험들이 함께 쓰는 캐시된 풀이별로 나눕니다.** 느린 CI 러너에서 `test_laplace_corner_harmonic_field.py` 하나만으로 29.3분이 걸려, 30분 이하여야 하는 시험 부분에 너무 깁니다. 캐시된 풀이를 쓰지 않는 거부 시험은 `*_refusals.py`로, guard와 single-active field의 16패널 신호 선택 시험은 `*_selection.py`로 옮깁니다. scaling 시험은 32패널 풀이를 함께 쓰므로 원래 모듈로 돌아갑니다. linear field의 반사 시험은 64패널 풀이 옆으로 돌아가고, 32패널 시험은 `test_laplace_corner_linear_field_32_panel.py`에 모이며, 원형 극한 시험은 자기 파일을 가집니다. 이제 한 시험 부분에서 캐시된 풀이가 두 번 돌지 않고, 수집되는 시험은 그대로 12583개이며 시험 ID 144개만 파일이 바뀝니다. 시험 본문, 단언, 허용 오차, 기대값, 표시는 바뀌지 않습니다. [개발 안내](development.md#ci가-돌리는-것).
