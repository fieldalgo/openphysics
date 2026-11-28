# Changed

## English

- Tests: **each corner-field test module solves a cached geometry once.** In `tests/galerkin/test_laplace_corner_field.py`, `test_laplace_corner_linear_field.py` and the three `test_laplace_corner_harmonic_*field.py` modules, `calculated(i)` and `calculated(i, <default panels>)` were separate `lru_cache` entries, so the same solve ran twice (110–520 s per module on CI runners). The helper now normalizes its arguments before the cache. No test, assertion, tolerance, expected value or marker changes. [Development guide](docs/development.md#what-ci-runs).

## 한국어

- 시험: **corner-field 시험 모듈마다 캐시된 형상을 한 번만 풉니다.** `tests/galerkin/test_laplace_corner_field.py`, `test_laplace_corner_linear_field.py`와 세 `test_laplace_corner_harmonic_*field.py` 모듈에서 `calculated(i)`와 `calculated(i, <기본 패널 수>)`가 서로 다른 `lru_cache` 항목이어서 같은 풀이가 두 번 돌았습니다(CI 러너에서 모듈마다 110–520초). 이제 도우미가 캐시 앞에서 인수를 정규화합니다. 시험, 단언, 허용 오차, 기대값, 표시는 바뀌지 않습니다. [개발 안내](development.md#ci가-돌리는-것).
