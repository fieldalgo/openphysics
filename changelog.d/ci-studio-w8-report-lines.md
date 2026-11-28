# Fixed

## English

- CI: **the Studio 3D W8 job finds its report lines again.** With `pytest -s`, the progress dot of the first test shares a line with the second test's report (`.W8-run {…}`). The job's `grep '^W8-run '` therefore found nothing and failed on main, even though both tests had passed. It now matches the report wherever it starts on the line (`grep -o 'W8-run {.*'`). The tests and the JUnit count check are unchanged.

## 한국어

- CI: **Studio 3D W8 작업이 보고 줄을 다시 찾습니다.** `pytest -s`에서는 첫 테스트의 진행 점이 두 번째 테스트의 보고와 한 줄을 나눕니다(`.W8-run {…}`). 그래서 작업의 `grep '^W8-run '`이 아무것도 찾지 못해, 두 테스트가 모두 통과했는데도 main에서 실패했습니다. 이제 보고가 줄의 어디에서 시작하든 맞춥니다(`grep -o 'W8-run {.*'`). 테스트와 JUnit 개수 검사는 그대로입니다.
