# Changed

## English

- CI: **the installed-platforms jobs stop at 60 minutes instead of 40.** On main they take 28 to 30 minutes on Ubuntu, macOS and Windows (run 45343712559, 2026-11-24), and a Windows runner about 1.5 times slower ran past 40 minutes on a pull request whose change did not touch the slow step. The limit only stops hung runs; no check is removed. [Development guide](docs/development.md#what-ci-runs).

## 한국어

- CI: **설치 플랫폼 작업이 40분 대신 60분에 멈춥니다.** main에서 Ubuntu, macOS, Windows 모두 28–30분이 걸리고(실행 45343712559, 2026-11-24), 약 1.5배 느린 Windows 러너가 느린 단계를 건드리지 않은 pull request에서 40분을 넘었습니다. 이 제한은 멈춘 실행만 끊으며, 빠지는 검사는 없습니다. [개발 안내](development.md#ci가-돌리는-것).
